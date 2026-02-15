import asyncio
import csv
import io
from contextlib import asynccontextmanager
from typing import TypedDict
from collections.abc import Sequence

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, col, select

from app.config import Settings, get_settings
from app.database import create_db_and_tables, get_session
from app.models import Lead
from app.schemas import ManagerStatus
from app.services.classifier import classify_interest, is_hot_lead
from app.services.twilio_service import TwilioService
from app.services.vapi import VapiService


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
        self._workers = [asyncio.create_task(self._worker()) for _ in range(self.settings.max_concurrent_calls)]

    async def stop(self) -> None:
        self._running = False
        for task in self._workers:
            task.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers = []

    async def enqueue_many(self, lead_ids: Sequence[int]) -> None:
        for lead_id in lead_ids:
            await self._queue.put(lead_id)

    async def _worker(self) -> None:
        settings = get_settings()
        while True:
            lead_id = await self._queue.get()
            try:
                await process_single_lead(lead_id, settings)
            finally:
                self._queue.task_done()


async def process_single_lead(lead_id: int, settings: Settings) -> None:
    from app.database import get_engine

    with Session(get_engine()) as session:
        lead = session.get(Lead, lead_id)
        if not lead:
            return

        vapi = VapiService(settings)
        try:
            call_id = await vapi.create_outbound_call(lead)
        except Exception as exc:
            lead.status = "failed"
            lead.summary = f"Call init failed: {type(exc).__name__}: {str(exc)[:220]}"
            session.add(lead)
            session.commit()
            return

        lead.status = "calling"
        lead.call_id = call_id
        session.add(lead)
        session.commit()


class LeadCSVRow(TypedDict):
    name: str
    phone: str
    location: str | None
    budget_range: str | None
    bhk_preference: str | None


def _parse_csv(contents: bytes) -> list[LeadCSVRow]:
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded") from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV headers are missing")

    required = {"Name", "Phone"}
    if not required.issubset(set(reader.fieldnames)):
        raise HTTPException(status_code=400, detail="CSV must include Name and Phone columns")

    rows: list[LeadCSVRow] = []
    for row in reader:
        name = (row.get("Name") or "").strip()
        phone = (row.get("Phone") or "").strip()
        if not name or not phone:
            continue
        rows.append(
            {
                "name": name,
                "phone": phone,
                "location": (row.get("Location") or "").strip() or None,
                "budget_range": (row.get("BudgetRange") or "").strip() or None,
                "bhk_preference": (row.get("BHKPreference") or "").strip() or None,
            }
        )
    return rows


def create_app() -> FastAPI:
    settings = get_settings()
    queue = CampaignQueue(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        validation_errors = settings.startup_validation_errors()
        if validation_errors:
            message = " | ".join(validation_errors)
            if settings.env_validation_mode == "strict":
                raise RuntimeError(f"Startup env validation failed: {message}")
            print(f"[startup-warning] {message}")

        create_db_and_tables()
        await queue.start()
        yield
        await queue.stop()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/upload")
    async def upload_leads(file: UploadFile = File(...), session: Session = Depends(get_session)):
        filename = file.filename or ""
        if not filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="Only CSV files are supported in Phase 1")

        contents = await file.read()
        rows = _parse_csv(contents)
        if not rows:
            raise HTTPException(status_code=400, detail="No valid leads found in CSV")

        created = 0
        for row in rows:
            lead = Lead(
                name=row["name"],
                phone=row["phone"],
                location=row["location"],
                budget_range=row["budget_range"],
                bhk_preference=row["bhk_preference"],
            )
            session.add(lead)
            created += 1

        session.commit()
        return {"message": f"Uploaded {created} leads"}

    @app.get("/leads")
    def list_leads(session: Session = Depends(get_session)):
        statement = select(Lead).order_by(col(Lead.id))
        return session.exec(statement).all()

    @app.post("/start-campaign")
    async def start_campaign(session: Session = Depends(get_session)):
        pending = session.exec(select(Lead).where(Lead.status == "pending")).all()

        ids: list[int] = []
        for lead in pending:
            lead.status = "queued"
            session.add(lead)
            if lead.id is not None:
                ids.append(lead.id)

        session.commit()
        await queue.enqueue_many(ids)
        return {"message": f"Queued {len(ids)} calls"}

    @app.get("/manager-status", response_model=ManagerStatus)
    def manager_status(current_settings: Settings = Depends(get_settings)):
        return ManagerStatus(
            connected=bool(current_settings.twilio_from_number and current_settings.manager_phone_number),
            join_code=current_settings.manager_join_code,
            sandbox_number=current_settings.twilio_from_number,
        )

    @app.post("/webhook/vapi")
    async def vapi_webhook(payload: dict, session: Session = Depends(get_session), current_settings: Settings = Depends(get_settings)):
        message = payload.get("message", {})
        event_type = message.get("type")
        if event_type != "end-of-call-report":
            return {"status": "ignored"}

        call = message.get("call", {})
        call_id = call.get("id")
        if not call_id:
            raise HTTPException(status_code=400, detail="Missing call id")

        lead = session.exec(select(Lead).where(Lead.call_id == call_id)).first()
        if not lead:
            return {"status": "unknown_call"}

        artifact = message.get("artifact", {})
        transcript = artifact.get("transcript", "")
        summary = message.get("analysis", {}).get("summary") or transcript[:350] or "No summary provided"
        ended_reason = message.get("endedReason", "")

        lead.summary = summary
        lead.interest_level = classify_interest(summary, ended_reason)
        lead.status = "voicemail" if "voicemail" in ended_reason.lower() else "completed"
        session.add(lead)
        session.commit()

        if is_hot_lead(lead.interest_level, summary):
            twilio_service = TwilioService(current_settings)
            twilio_service.send_hot_lead_summary(lead.name, summary)

        return {"status": "ok"}

    return app


app = create_app()
