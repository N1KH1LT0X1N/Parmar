import asyncio
import csv
import io
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import TypedDict
from collections.abc import Sequence

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, col, select

from app.config import Settings, get_settings
from app.database import create_db_and_tables, get_session
from app.models import (
    Lead,
    LEAD_STATUS_CALLING,
    LEAD_STATUS_COMPLETED,
    LEAD_STATUS_FAILED,
    LEAD_STATUS_PENDING,
    LEAD_STATUS_QUEUED,
    LEAD_STATUS_VOICEMAIL,
    MAX_CSV_SIZE_BYTES,
    MAX_ERROR_DETAIL_LENGTH,
    TERMINAL_STATUSES,
)
from app.schemas import CampaignResponse, ManagerStatus, UploadResponse, WebhookResponse
from app.services.classifier import classify_interest, is_hot_lead
from app.services.twilio_service import TwilioService
from app.services.vapi import VapiService

logger = logging.getLogger("parmar")


class CampaignQueue:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._queue: asyncio.Queue[int] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._workers = [asyncio.create_task(self._worker(i)) for i in range(self.settings.max_concurrent_calls)]
        logger.info("Campaign queue started with %d worker(s)", self.settings.max_concurrent_calls)

    async def stop(self) -> None:
        self._running = False
        for task in self._workers:
            task.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers = []
        logger.info("Campaign queue stopped")

    async def enqueue_many(self, lead_ids: Sequence[int]) -> None:
        for lead_id in lead_ids:
            await self._queue.put(lead_id)

    async def _worker(self, worker_id: int) -> None:
        settings = get_settings()
        while True:
            lead_id = await self._queue.get()
            try:
                logger.info("[worker-%d] Processing lead %d", worker_id, lead_id)
                await process_single_lead(lead_id, settings)
            except Exception:
                logger.exception("[worker-%d] Unhandled error processing lead %d", worker_id, lead_id)
            finally:
                self._queue.task_done()


async def process_single_lead(lead_id: int, settings: Settings) -> None:
    from app.database import get_engine

    with Session(get_engine()) as session:
        lead = session.get(Lead, lead_id)
        if not lead:
            logger.warning("Lead %d not found, skipping", lead_id)
            return

        vapi = VapiService(settings)
        try:
            call_id = await vapi.create_outbound_call(lead)
        except Exception as exc:
            lead.status = LEAD_STATUS_FAILED
            lead.summary = f"Call init failed: {type(exc).__name__}: {str(exc)[:MAX_ERROR_DETAIL_LENGTH]}"
            lead.updated_at = datetime.now(timezone.utc)
            session.add(lead)
            session.commit()
            logger.error("Lead %d call failed: %s", lead_id, exc)
            return

        lead.status = LEAD_STATUS_CALLING
        lead.call_id = call_id
        lead.updated_at = datetime.now(timezone.utc)
        session.add(lead)
        session.commit()
        logger.info("Lead %d now calling (call_id=%s)", lead_id, call_id)


class LeadCSVRow(TypedDict):
    name: str
    phone: str
    location: str | None
    budget_range: str | None
    bhk_preference: str | None


_E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")


def _normalize_phone(raw_phone: str) -> str | None:
    cleaned = raw_phone.strip()
    if not cleaned:
        return None

    if cleaned.startswith("+"):
        normalized = "+" + re.sub(r"\D", "", cleaned[1:])
    else:
        digits = re.sub(r"\D", "", cleaned)
        if len(digits) == 10:
            normalized = "+91" + digits
        elif digits.startswith("91") and len(digits) == 12:
            normalized = "+" + digits
        elif digits.startswith("0") and len(digits) == 11:
            normalized = "+91" + digits[1:]
        else:
            normalized = "+" + digits

    if not _E164_PATTERN.match(normalized):
        return None
    return normalized


def _parse_csv(contents: bytes) -> tuple[list[LeadCSVRow], int]:
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded") from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV headers are missing")

    # Case-insensitive header matching
    header_map: dict[str, str] = {}
    for fn in reader.fieldnames:
        header_map[fn.strip().lower()] = fn

    if "name" not in header_map or "phone" not in header_map:
        raise HTTPException(status_code=400, detail="CSV must include Name and Phone columns")

    name_col = header_map["name"]
    phone_col = header_map["phone"]
    location_col = header_map.get("location")
    budget_col = header_map.get("budgetrange")
    bhk_col = header_map.get("bhkpreference")

    rows: list[LeadCSVRow] = []
    skipped_invalid = 0
    seen_phones: set[str] = set()

    for row in reader:
        name = (row.get(name_col) or "").strip()
        phone = _normalize_phone((row.get(phone_col) or "").strip())
        if not name or not phone:
            skipped_invalid += 1
            continue
        if phone in seen_phones:
            skipped_invalid += 1
            continue
        seen_phones.add(phone)
        rows.append(
            {
                "name": name,
                "phone": phone,
                "location": (row.get(location_col) or "").strip() or None if location_col else None,
                "budget_range": (row.get(budget_col) or "").strip() or None if budget_col else None,
                "bhk_preference": (row.get(bhk_col) or "").strip() or None if bhk_col else None,
            }
        )
    return rows, skipped_invalid


def create_app() -> FastAPI:
    settings = get_settings()
    queue = CampaignQueue(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        )
        validation_errors = settings.startup_validation_errors()
        if validation_errors:
            message = " | ".join(validation_errors)
            if settings.env_validation_mode == "strict":
                raise RuntimeError(f"Startup env validation failed: {message}")
            logger.warning("Env validation: %s", message)

        create_db_and_tables()
        await queue.start()
        logger.info("Application started")
        yield
        await queue.stop()
        logger.info("Application shut down")

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------- Health ----------

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    # ---------- Upload ----------

    @app.post("/upload", response_model=UploadResponse)
    async def upload_leads(file: UploadFile = File(...), session: Session = Depends(get_session)):
        filename = file.filename or ""
        if not filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="Only CSV files are supported")

        contents = await file.read()
        if len(contents) > MAX_CSV_SIZE_BYTES:
            raise HTTPException(status_code=400, detail=f"CSV file exceeds {MAX_CSV_SIZE_BYTES // (1024*1024)}MB limit")
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        rows, skipped_invalid = _parse_csv(contents)
        if not rows:
            raise HTTPException(status_code=400, detail="No valid leads found in CSV")

        # Deduplicate against existing phones in DB
        existing_phones = set(
            session.exec(select(Lead.phone)).all()
        )

        created = 0
        for row in rows:
            if row["phone"] in existing_phones:
                skipped_invalid += 1
                continue
            lead = Lead(
                name=row["name"],
                phone=row["phone"],
                location=row["location"],
                budget_range=row["budget_range"],
                bhk_preference=row["bhk_preference"],
            )
            session.add(lead)
            existing_phones.add(row["phone"])
            created += 1

        session.commit()
        logger.info("Uploaded %d leads (skipped %d)", created, skipped_invalid)
        return UploadResponse(
            message=f"Uploaded {created} leads" + (f" (skipped {skipped_invalid} invalid/duplicate rows)" if skipped_invalid else ""),
            created=created,
            skipped=skipped_invalid,
        )

    # ---------- List leads ----------

    @app.get("/leads")
    def list_leads(session: Session = Depends(get_session)):
        statement = select(Lead).order_by(col(Lead.id))
        return session.exec(statement).all()

    # ---------- Campaign ----------

    @app.post("/start-campaign", response_model=CampaignResponse)
    async def start_campaign(session: Session = Depends(get_session)):
        pending = session.exec(select(Lead).where(Lead.status == LEAD_STATUS_PENDING)).all()

        if not pending:
            return CampaignResponse(message="No pending leads to queue", queued=0)

        ids: list[int] = []
        now = datetime.now(timezone.utc)
        for lead in pending:
            lead.status = LEAD_STATUS_QUEUED
            lead.updated_at = now
            session.add(lead)
            if lead.id is not None:
                ids.append(lead.id)

        session.commit()
        await queue.enqueue_many(ids)
        logger.info("Campaign started: queued %d leads", len(ids))
        return CampaignResponse(message=f"Queued {len(ids)} calls", queued=len(ids))

    # ---------- Manager status ----------

    @app.get("/manager-status", response_model=ManagerStatus)
    def manager_status(current_settings: Settings = Depends(get_settings)):
        return ManagerStatus(
            connected=bool(current_settings.twilio_from_number and current_settings.manager_phone_number),
            join_code=current_settings.manager_join_code,
            sandbox_number=current_settings.twilio_from_number,
        )

    # ---------- Webhook ----------

    @app.post("/webhook/vapi", response_model=WebhookResponse)
    async def vapi_webhook(payload: dict, session: Session = Depends(get_session), current_settings: Settings = Depends(get_settings)):
        message = payload.get("message", {})
        event_type = message.get("type")
        if event_type != "end-of-call-report":
            return WebhookResponse(status="ignored")

        call = message.get("call", {})
        call_id = call.get("id")
        if not call_id:
            raise HTTPException(status_code=400, detail="Missing call id")

        lead = session.exec(select(Lead).where(Lead.call_id == call_id)).first()
        if not lead:
            logger.warning("Webhook for unknown call_id=%s", call_id)
            return WebhookResponse(status="unknown_call")

        artifact = message.get("artifact", {})
        transcript = artifact.get("transcript", "")
        summary = message.get("analysis", {}).get("summary") or transcript[:350] or "No summary provided"
        ended_reason = message.get("endedReason", "")

        already_final = lead.status in TERMINAL_STATUSES
        if already_final and lead.summary == summary:
            return WebhookResponse(status="duplicate_ignored")

        lead.summary = summary
        lead.interest_level = classify_interest(summary, ended_reason)
        lead.status = LEAD_STATUS_VOICEMAIL if "voicemail" in ended_reason.lower() else LEAD_STATUS_COMPLETED
        lead.updated_at = datetime.now(timezone.utc)
        session.add(lead)
        session.commit()

        logger.info("Lead %s webhook processed: status=%s interest=%s", lead.id, lead.status, lead.interest_level)

        if (not already_final) and is_hot_lead(lead.interest_level, summary):
            twilio_service = TwilioService(current_settings)
            sid = twilio_service.send_hot_lead_summary(lead.name, summary)
            if sid:
                logger.info("Hot lead notification sent for %s (sid=%s)", lead.name, sid)
            else:
                logger.warning("Failed to send hot lead notification for %s", lead.name)

        return WebhookResponse(status="ok")

    # ---------- Manual webhook test endpoint (for debugging/testing) ----------

    @app.post("/test/mark-call-completed/{call_id}")
    def test_mark_call_completed(
        call_id: str, 
        summary: str = "Customer expressed interest in scheduling a site visit to Bandra property. Budget range is around 2-3 crore. Timeline is within 2-3 months.",
        session: Session = Depends(get_session),
        current_settings: Settings = Depends(get_settings)
    ):
        """Test endpoint to manually complete a call with optional summary. Used for testing the full call completion + hot lead notification flow."""
        lead = session.exec(select(Lead).where(Lead.call_id == call_id)).first()
        if not lead:
            raise HTTPException(status_code=404, detail=f"Call {call_id} not found")

        if lead.status in TERMINAL_STATUSES:
            return {"status": "already_completed", "lead_status": lead.status}

        # Update lead with call outcome
        lead.status = LEAD_STATUS_COMPLETED
        lead.summary = summary
        lead.interest_level = classify_interest(summary)
        lead.updated_at = datetime.now(timezone.utc)
        session.add(lead)
        session.commit()
        
        logger.info("Test endpoint: Lead %s completed with summary", lead.id)
        
        # Check if hot lead and send notification
        response_data = {
            "status": "ok",
            "lead_id": lead.id,
            "lead_status": lead.status,
            "interest_level": lead.interest_level,
            "summary": summary,
            "whatsapp_sent": False
        }
        
        if is_hot_lead(lead.interest_level, summary):
            response_data["is_hot_lead"] = True
            twilio_service = TwilioService(current_settings)
            if not twilio_service.is_configured():
                response_data["whatsapp_error"] = "Twilio not configured"
                logger.warning("Twilio not configured for lead %s", lead.name)
            else:
                sid = twilio_service.send_hot_lead_summary(lead.name, summary)
                if sid:
                    logger.info("Hot lead WhatsApp notification sent for %s (sid=%s)", lead.name, sid)
                    response_data["whatsapp_sent"] = True
                    response_data["whatsapp_sid"] = sid
                else:
                    response_data["whatsapp_error"] = "Failed to send via Twilio"
                    logger.warning("Failed to send WhatsApp notification for %s", lead.name)
        else:
            response_data["is_hot_lead"] = False
            response_data["whatsapp_reason"] = f"Not classified as hot lead (interest={lead.interest_level})"
        
        return response_data

    # ---------- Test endpoint by lead ID (for testing without Vapi) ----------

    @app.post("/test/lead/{lead_id}/simulate-completion")
    def test_lead_simulate_completion(
        lead_id: int,
        summary: str = "Customer expressed interest in scheduling a site visit to Bandra property. Budget range is around 2-3 crore. Timeline is within 2-3 months.",
        session: Session = Depends(get_session),
        current_settings: Settings = Depends(get_settings)
    ):
        """Test endpoint to simulate call completion on a specific lead by ID (for testing without Vapi)."""
        lead = session.get(Lead, lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")

        if lead.status in TERMINAL_STATUSES:
            return {"status": "already_completed", "lead_status": lead.status}

        # Update lead with call outcome
        lead.status = LEAD_STATUS_COMPLETED
        lead.summary = summary
        lead.interest_level = classify_interest(summary)
        lead.updated_at = datetime.now(timezone.utc)
        session.add(lead)
        session.commit()
        
        logger.info("Test endpoint (by ID): Lead %s completed with summary", lead.id)
        
        # Check if hot lead and send notification
        response_data = {
            "status": "ok",
            "lead_id": lead.id,
            "lead_name": lead.name,
            "lead_status": lead.status,
            "interest_level": lead.interest_level,
            "summary": summary[:100] + "..." if len(summary) > 100 else summary,
            "whatsapp_sent": False
        }
        
        if is_hot_lead(lead.interest_level, summary):
            response_data["is_hot_lead"] = True
            twilio_service = TwilioService(current_settings)
            if not twilio_service.is_configured():
                response_data["whatsapp_error"] = "Twilio not configured"
                logger.warning("Twilio not configured for lead %s", lead.name)
            else:
                sid = twilio_service.send_hot_lead_summary(lead.name, summary)
                if sid:
                    logger.info("Hot lead WhatsApp notification sent for %s (sid=%s)", lead.name, sid)
                    response_data["whatsapp_sent"] = True
                    response_data["whatsapp_sid"] = sid
                else:
                    response_data["whatsapp_error"] = "Failed to send via Twilio"
                    logger.warning("Failed to send WhatsApp notification for %s", lead.name)
        else:
            response_data["is_hot_lead"] = False
            response_data["whatsapp_reason"] = f"Not classified as hot lead (interest={lead.interest_level})"
        
        return response_data

    # ---------- Twilio webhook for WhatsApp status callbacks ----------

    @app.post("/webhook/twilio-status")
    async def twilio_status_callback(request: dict):
        """
        Twilio status callback endpoint for WhatsApp message delivery notifications.
        Receives updates whenever a message status changes (sent, delivered, failed, read, etc.)
        """
        message_sid = request.get("MessageSid", "unknown")
        message_status = request.get("MessageStatus", "unknown")
        account_sid = request.get("AccountSid", "")
        
        log_msg = f"WhatsApp status update: SID={message_sid}, Status={message_status}"
        
        if message_status == "delivered":
            logger.info(f"✓ {log_msg}")
        elif message_status == "read":
            logger.info(f"✓ {log_msg}")
        elif message_status == "failed":
            error_msg = request.get("ErrorMessage", "Unknown error")
            logger.warning(f"✗ {log_msg} - Error: {error_msg}")
        else:
            logger.debug(log_msg)
        
        # Return 200 OK to Twilio
        return {"status": "ok"}

    return app


app = create_app()
