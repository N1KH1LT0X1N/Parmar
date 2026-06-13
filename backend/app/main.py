import asyncio
import csv
import io
import logging
import re
import secrets
import uuid
from collections.abc import Sequence
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any, TypedDict

import phonenumbers
from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from phonenumbers import NumberParseException
from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select
from twilio.request_validator import RequestValidator

from app.audit import (
    cleanup_retention_data,
    mark_webhook_event_status,
    payload_sha256,
    register_webhook_event_attempt,
    write_audit_event,
)
from app.config import Settings, get_settings
from app.database import get_engine, get_session
from app.models import (
    ACTIVE_LEAD_STATUSES,
    CampaignJob,
    CONTACT_OUTCOME_CALL_FAILED,
    CONTACT_OUTCOME_CALLBACK_REQUESTED,
    CONTACT_OUTCOME_DNC_REQUESTED,
    CONTACT_OUTCOME_NOT_INTERESTED,
    CONTACT_OUTCOME_NO_ANSWER,
    CONTACT_OUTCOME_QUALIFIED,
    CONTACT_OUTCOME_UNKNOWN,
    CONTACT_OUTCOME_VOICEMAIL,
    CONTACT_OUTCOME_WRONG_NUMBER,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PROCESSING,
    JOB_STATUS_QUEUED,
    Lead,
    LEAD_STATUS_CALLING,
    LEAD_STATUS_COMPLETED,
    LEAD_STATUS_DNC,
    LEAD_STATUS_FAILED,
    LEAD_STATUS_PENDING,
    LEAD_STATUS_QUEUED,
    LEAD_STATUS_VOICEMAIL,
    MAX_CSV_SIZE_BYTES,
    MAX_ERROR_DETAIL_LENGTH,
    MAX_SUMMARY_LENGTH,
    TERMINAL_STATUSES,
)
from app.schemas import (
    APIMessage,
    CampaignResponse,
    DashboardAuthRequest,
    DashboardAuthResponse,
    LeadListResponse,
    LeadRecord,
    LeadStats,
    ManagerStatus,
    UploadResponse,
    VapiPreflightResponse,
    WebhookResponse,
)
from app.security import (
    InMemoryRateLimiter,
    build_dashboard_session_token,
    enforce_rate_limit,
    has_valid_dashboard_session,
    require_dashboard_auth,
)
from app.services.classifier import classify_interest, is_hot_lead
from app.services.twilio_service import TwilioService
from app.services.vapi import VapiService

logger = logging.getLogger("outbound_calling")

_PHONE_PATTERN = re.compile(r"\+\d{8,15}")
_E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
_DNC_HINT_PATTERN = re.compile(
    r"(do not call|don't call|stop call|stop calling|do not contact|remove my number|unsubscribe|stop contacting)",
    re.IGNORECASE,
)
_WRONG_NUMBER_HINT_PATTERN = re.compile(r"(wrong number|not my number|incorrect number)", re.IGNORECASE)
_CALLBACK_HINT_PATTERN = re.compile(r"(call later|callback|call back|follow up later)", re.IGNORECASE)
_NO_ANSWER_HINT_PATTERN = re.compile(r"(no answer|unanswered|busy)", re.IGNORECASE)
_DELETABLE_LEAD_STATUSES = TERMINAL_STATUSES | {LEAD_STATUS_FAILED}


class PIIRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _PHONE_PATTERN.sub(_mask_phone, record.msg)
        if record.args:
            sanitized_args: list[Any] = []
            for arg in record.args:
                if isinstance(arg, str):
                    sanitized_args.append(_PHONE_PATTERN.sub(_mask_phone, arg))
                else:
                    sanitized_args.append(arg)
            record.args = tuple(sanitized_args)
        return True


class LeadCSVRow(TypedDict):
    name: str
    phone: str
    location: str | None
    budget_range: str | None
    bhk_preference: str | None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _mask_phone(match: re.Match[str]) -> str:
    value = match.group(0)
    if len(value) <= 4:
        return "****"
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


def _truncate(value: str, max_len: int) -> str:
    if len(value) <= max_len:
        return value
    return value[: max_len - 3] + "..."


def _normalize_phone(raw_phone: str) -> str | None:
    cleaned = raw_phone.strip()
    if not cleaned:
        return None

    digits_only = re.sub(r"\D", "", cleaned)
    candidates = [cleaned]
    if digits_only and digits_only != cleaned:
        candidates.append(digits_only)

    parsed = None
    for candidate in candidates:
        try:
            parsed = phonenumbers.parse(candidate, "IN")
        except NumberParseException:
            continue
        if phonenumbers.is_possible_number(parsed) and phonenumbers.is_valid_number(parsed):
            break
    else:
        return None

    normalized = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
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

    header_map: dict[str, str] = {}
    for field_name in reader.fieldnames:
        header_map[field_name.strip().lower()] = field_name

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


def _summary_from_webhook(message: dict[str, Any]) -> str:
    artifact = message.get("artifact", {}) if isinstance(message.get("artifact"), dict) else {}
    transcript = artifact.get("transcript", "")
    analysis = message.get("analysis", {}) if isinstance(message.get("analysis"), dict) else {}
    summary = analysis.get("summary") or transcript or "No summary provided"
    return _truncate(str(summary), MAX_SUMMARY_LENGTH)


def _extract_structured_analysis(message: dict[str, Any]) -> dict[str, Any]:
    analysis = message.get("analysis") if isinstance(message.get("analysis"), dict) else {}
    candidates = [
        analysis.get("structuredData"),
        analysis.get("dataCollection"),
        analysis.get("extractedData"),
        message.get("structuredData"),
        message.get("dataCollection"),
    ]
    merged: dict[str, Any] = {}
    for candidate in candidates:
        if isinstance(candidate, dict):
            merged.update({str(key): value for key, value in candidate.items()})
    return merged


def _normalized_interest_level(structured: dict[str, Any], summary: str, ended_reason: str) -> str:
    raw_interest = structured.get("interest_level") or structured.get("interestLevel")
    if isinstance(raw_interest, str):
        normalized = raw_interest.strip().lower().replace("-", "_")
        if normalized in {"high", "medium", "low", "none"}:
            return normalized
        if normalized in {"hot", "qualified"}:
            return "high"
        if normalized in {"warm", "maybe"}:
            return "medium"
        if normalized in {"cold", "not_interested", "not interested"}:
            return "none"
    return classify_interest(summary, ended_reason)


def _determine_contact_outcome(
    *,
    summary: str,
    ended_reason: str,
    interest_level: str,
    structured: dict[str, Any],
) -> str:
    raw_outcome = structured.get("contact_outcome") or structured.get("contactOutcome") or structured.get("call_outcome")
    if isinstance(raw_outcome, str):
        normalized = raw_outcome.strip().lower().replace(" ", "_")
        if normalized in {
            CONTACT_OUTCOME_QUALIFIED,
            CONTACT_OUTCOME_NOT_INTERESTED,
            CONTACT_OUTCOME_WRONG_NUMBER,
            CONTACT_OUTCOME_DNC_REQUESTED,
            CONTACT_OUTCOME_CALLBACK_REQUESTED,
            CONTACT_OUTCOME_VOICEMAIL,
            CONTACT_OUTCOME_NO_ANSWER,
            CONTACT_OUTCOME_CALL_FAILED,
            CONTACT_OUTCOME_UNKNOWN,
        }:
            return normalized

    combined = f"{summary} {ended_reason}".lower()
    if _DNC_HINT_PATTERN.search(combined):
        return CONTACT_OUTCOME_DNC_REQUESTED
    if _WRONG_NUMBER_HINT_PATTERN.search(combined):
        return CONTACT_OUTCOME_WRONG_NUMBER
    if "voicemail" in combined:
        return CONTACT_OUTCOME_VOICEMAIL
    if _NO_ANSWER_HINT_PATTERN.search(combined):
        return CONTACT_OUTCOME_NO_ANSWER
    if _CALLBACK_HINT_PATTERN.search(combined):
        return CONTACT_OUTCOME_CALLBACK_REQUESTED
    if interest_level == "high":
        return CONTACT_OUTCOME_QUALIFIED
    if interest_level == "none":
        return CONTACT_OUTCOME_NOT_INTERESTED
    return CONTACT_OUTCOME_UNKNOWN


def _status_from_contact_outcome(contact_outcome: str) -> str:
    if contact_outcome == CONTACT_OUTCOME_DNC_REQUESTED:
        return LEAD_STATUS_DNC
    if contact_outcome == CONTACT_OUTCOME_VOICEMAIL:
        return LEAD_STATUS_VOICEMAIL
    return LEAD_STATUS_COMPLETED


def _lead_snapshot(lead: Lead) -> Lead:
    return Lead(
        id=lead.id,
        name=lead.name,
        phone=lead.phone,
        location=lead.location,
        budget_range=lead.budget_range,
        bhk_preference=lead.bhk_preference,
        status=lead.status,
        interest_level=lead.interest_level,
        contact_outcome=lead.contact_outcome,
        summary=lead.summary,
        call_id=lead.call_id,
        do_not_contact=lead.do_not_contact,
        dnc_reason=lead.dnc_reason,
        dnc_updated_at=lead.dnc_updated_at,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


def _extract_vapi_event_key(payload: dict[str, Any], message: dict[str, Any], call_id: str, event_type: str) -> str:
    message_id = message.get("id")
    if isinstance(message_id, str) and message_id.strip():
        return f"event:{message_id.strip()}"
    if call_id:
        return f"call:{call_id}:{event_type or 'unknown'}"
    return f"payload:{payload_sha256(payload)}"


def _extract_twilio_event_key(payload: dict[str, str]) -> str:
    message_sid = payload.get("MessageSid", "").strip()
    message_status = payload.get("MessageStatus", "").strip()
    if message_sid:
        return f"{message_sid}:{message_status or 'unknown'}"
    return f"payload:{payload_sha256(payload)}"


async def _attempt_outbound_call(lead: Lead, settings: Settings) -> str:
    vapi = VapiService(settings)
    return await vapi.create_outbound_call(lead)


async def process_single_lead(lead_id: int, settings: Settings) -> None:
    with Session(get_engine()) as session:
        lead = session.get(Lead, lead_id)
        if not lead:
            logger.warning("Lead %d not found, skipping", lead_id)
            return

        now = _utcnow()
        if lead.do_not_contact:
            lead.status = LEAD_STATUS_DNC
            lead.contact_outcome = CONTACT_OUTCOME_DNC_REQUESTED
            lead.updated_at = now
            session.add(lead)
            write_audit_event(
                session,
                event_type="lead_skipped_dnc",
                source="campaign_worker",
                lead_id=lead.id,
                details={"reason": lead.dnc_reason or "do_not_contact"},
            )
            session.commit()
            return

        lead_snapshot = _lead_snapshot(lead)

        try:
            call_id = await _attempt_outbound_call(lead_snapshot, settings)
        except Exception as exc:
            lead.status = LEAD_STATUS_FAILED
            lead.contact_outcome = CONTACT_OUTCOME_CALL_FAILED
            lead.summary = _truncate(f"Call init failed: {type(exc).__name__}: {str(exc)}", MAX_SUMMARY_LENGTH)
            lead.updated_at = now
            session.add(lead)
            write_audit_event(
                session,
                event_type="lead_call_failed",
                source="campaign_worker",
                lead_id=lead.id,
                details={"error": _truncate(str(exc), MAX_ERROR_DETAIL_LENGTH)},
            )
            session.commit()
            logger.error("Lead %d call failed: %s", lead_id, exc)
            return

        lead.status = LEAD_STATUS_CALLING
        lead.contact_outcome = None
        lead.call_id = call_id
        lead.updated_at = now
        session.add(lead)
        write_audit_event(
            session,
            event_type="lead_call_started",
            source="campaign_worker",
            lead_id=lead.id,
            call_id=call_id,
        )
        session.commit()
        logger.info("Lead %d now calling (call_id=%s)", lead_id, call_id)

class CampaignQueue:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._workers: list[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._recover_stale_jobs()
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

    async def enqueue_many(self, lead_ids: Sequence[int]) -> int:
        if not lead_ids:
            return 0

        with Session(get_engine()) as session:
            active_lead_ids = set(
                session.exec(
                    select(CampaignJob.lead_id).where(
                        CampaignJob.lead_id.in_(list(lead_ids)),
                        CampaignJob.status.in_((JOB_STATUS_QUEUED, JOB_STATUS_PROCESSING)),
                    )
                ).all()
            )

            now = _utcnow()
            created = 0
            for lead_id in lead_ids:
                if lead_id in active_lead_ids:
                    continue
                session.add(
                    CampaignJob(
                        lead_id=lead_id,
                        status=JOB_STATUS_QUEUED,
                        attempt_count=0,
                        scheduled_at=now,
                        created_at=now,
                        updated_at=now,
                    )
                )
                created += 1

            session.commit()
            return created

    def _recover_stale_jobs(self) -> None:
        with Session(get_engine()) as session:
            now = _utcnow()
            stale_jobs = session.exec(
                select(CampaignJob).where(
                    CampaignJob.status == JOB_STATUS_PROCESSING,
                    CampaignJob.lease_until.is_not(None),
                    CampaignJob.lease_until < now,
                )
            ).all()
            for job in stale_jobs:
                job.status = JOB_STATUS_QUEUED
                job.lease_until = None
                job.scheduled_at = now
                job.updated_at = now
                session.add(job)
            session.commit()

    async def _worker(self, worker_id: int) -> None:
        while self._running:
            try:
                job_id = await self._claim_next_job()
            except Exception:
                logger.exception("[worker-%d] Failed to claim next job", worker_id)
                await asyncio.sleep(self.settings.job_poll_interval_seconds)
                continue

            if job_id is None:
                await asyncio.sleep(self.settings.job_poll_interval_seconds)
                continue

            try:
                await self._process_job(job_id=job_id, worker_id=worker_id)
            except Exception:
                logger.exception("[worker-%d] Unhandled error processing job %d", worker_id, job_id)

    async def _claim_next_job(self) -> int | None:
        with Session(get_engine()) as session:
            now = _utcnow()
            lease_until = now + timedelta(seconds=self.settings.job_lease_seconds)
            result = session.exec(
                text(
                    """
                    UPDATE campaignjob
                    SET status = :processing_status,
                        attempt_count = attempt_count + 1,
                        started_at = COALESCE(started_at, :now),
                        lease_until = :lease_until,
                        updated_at = :now
                    WHERE id = (
                        SELECT id
                        FROM campaignjob
                        WHERE status = :queued_status
                          AND scheduled_at <= :now
                        ORDER BY id
                        LIMIT 1
                    )
                    RETURNING id
                    """
                ),
                params={
                    "processing_status": JOB_STATUS_PROCESSING,
                    "queued_status": JOB_STATUS_QUEUED,
                    "now": now,
                    "lease_until": lease_until,
                },
            ).first()
            if not result:
                session.rollback()
                return None

            session.commit()
            if isinstance(result, tuple):
                return int(result[0])
            if hasattr(result, "_mapping"):
                return int(next(iter(result._mapping.values())))
            return int(result)

    async def _process_job(self, job_id: int, worker_id: int) -> None:
        with Session(get_engine()) as session:
            job = session.get(CampaignJob, job_id)
            if not job:
                return

            lead = session.get(Lead, job.lead_id)
            now = _utcnow()

            if not lead:
                job.status = JOB_STATUS_FAILED
                job.finished_at = now
                job.last_error = "Lead not found"
                job.lease_until = None
                job.updated_at = now
                session.add(job)
                write_audit_event(
                    session,
                    event_type="campaign_job_failed",
                    source="campaign_worker",
                    details={"job_id": job_id, "error": "Lead not found"},
                )
                session.commit()
                return

            if lead.do_not_contact:
                lead.status = LEAD_STATUS_DNC
                lead.contact_outcome = CONTACT_OUTCOME_DNC_REQUESTED
                lead.updated_at = now

                job.status = JOB_STATUS_COMPLETED
                job.finished_at = now
                job.lease_until = None
                job.updated_at = now

                session.add(lead)
                session.add(job)
                write_audit_event(
                    session,
                    event_type="campaign_job_skipped_dnc",
                    source="campaign_worker",
                    lead_id=lead.id,
                    details={"job_id": job_id},
                )
                session.commit()
                return

            lead_snapshot = _lead_snapshot(lead)
            lead_id = lead.id
            attempt_count = job.attempt_count

        try:
            call_id = await _attempt_outbound_call(lead_snapshot, self.settings)
        except Exception as exc:
            with Session(get_engine()) as session:
                job = session.get(CampaignJob, job_id)
                lead = session.get(Lead, lead_id) if lead_id is not None else None
                if not job:
                    return

                now = _utcnow()
                job.last_error = _truncate(str(exc), MAX_ERROR_DETAIL_LENGTH)
                job.lease_until = None
                job.updated_at = now

                if attempt_count < self.settings.max_call_attempts:
                    retry_delay = min(2 ** max(attempt_count - 1, 0), 60)
                    job.status = JOB_STATUS_QUEUED
                    job.scheduled_at = now + timedelta(seconds=retry_delay)
                else:
                    job.status = JOB_STATUS_FAILED
                    job.finished_at = now
                    if lead:
                        lead.status = LEAD_STATUS_FAILED
                        lead.contact_outcome = CONTACT_OUTCOME_CALL_FAILED
                        lead.summary = _truncate(
                            f"Call init failed: {type(exc).__name__}: {str(exc)}",
                            MAX_SUMMARY_LENGTH,
                        )
                        lead.updated_at = now
                        session.add(lead)

                session.add(job)
                write_audit_event(
                    session,
                    event_type="campaign_job_error",
                    source="campaign_worker",
                    lead_id=lead.id if lead else None,
                    details={"job_id": job_id, "attempt": attempt_count, "error": job.last_error},
                )
                session.commit()
            logger.error("[worker-%d] job=%d lead=%s call failed: %s", worker_id, job_id, lead_id, exc)
            return

        with Session(get_engine()) as session:
            job = session.get(CampaignJob, job_id)
            lead = session.get(Lead, lead_id) if lead_id is not None else None
            if not job or not lead:
                return

            now = _utcnow()
            lead.status = LEAD_STATUS_CALLING
            lead.contact_outcome = None
            lead.call_id = call_id
            lead.updated_at = now

            job.status = JOB_STATUS_COMPLETED
            job.finished_at = now
            job.lease_until = None
            job.updated_at = now

            session.add(lead)
            session.add(job)
            write_audit_event(
                session,
                event_type="campaign_job_call_started",
                source="campaign_worker",
                lead_id=lead.id,
                call_id=call_id,
                details={"job_id": job_id, "attempt": job.attempt_count},
            )
            session.commit()
        logger.info("[worker-%d] job=%d lead=%d now calling (call_id=%s)", worker_id, job_id, lead.id, call_id)


def _lead_stats_from_rows(rows: Sequence[tuple[str, int]]) -> LeadStats:
    counts = {status: count for status, count in rows}
    return LeadStats(
        pending=int(counts.get(LEAD_STATUS_PENDING, 0)),
        queued=int(counts.get(LEAD_STATUS_QUEUED, 0)),
        calling=int(counts.get(LEAD_STATUS_CALLING, 0)),
        completed=int(counts.get(LEAD_STATUS_COMPLETED, 0)),
        failed=int(counts.get(LEAD_STATUS_FAILED, 0)),
        voicemail=int(counts.get(LEAD_STATUS_VOICEMAIL, 0)),
        dnc=int(counts.get(LEAD_STATUS_DNC, 0)),
    )


def _send_hot_lead_notification_task(
    *,
    settings: Settings,
    lead_id: int,
    call_id: str,
    lead_name: str,
    summary: str,
) -> None:
    sid = None
    try:
        sid = TwilioService(settings).send_hot_lead_summary(lead_name, summary)
    except Exception:
        logger.exception("Hot lead notification failed for lead_id=%s", lead_id)

    with Session(get_engine()) as session:
        write_audit_event(
            session,
            event_type="hot_lead_notification_attempt",
            source="twilio",
            lead_id=lead_id,
            call_id=call_id,
            details={"success": bool(sid), "sid": sid},
        )
        session.commit()

    if sid:
        logger.info("Hot lead notification sent for %s (sid=%s)", lead_name, sid)
    else:
        logger.warning("Hot lead notification failed for %s", lead_name)


def _configure_logging(current_settings: Settings) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    if not current_settings.log_pii_redaction_enabled:
        return

    redaction_filter = PIIRedactionFilter()
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        has_filter = any(isinstance(existing_filter, PIIRedactionFilter) for existing_filter in handler.filters)
        if not has_filter:
            handler.addFilter(redaction_filter)


def _validate_startup_environment(current_settings: Settings) -> None:
    validation_errors = current_settings.startup_validation_errors()
    if not validation_errors:
        return

    message = " | ".join(validation_errors)
    if current_settings.env_validation_mode == "strict":
        raise RuntimeError(f"Startup env validation failed: {message}")
    logger.warning("Env validation: %s", message)


def create_app() -> FastAPI:
    settings = get_settings()
    queue = CampaignQueue(settings)
    limiter = InMemoryRateLimiter()
    twilio_validator = RequestValidator(settings.twilio_auth_token) if settings.twilio_auth_token else None

    @asynccontextmanager
    async def lifespan(app_instance: FastAPI):
        _configure_logging(settings)
        _validate_startup_environment(settings)

        with Session(get_engine()) as startup_session:
            cleanup_retention_data(startup_session, settings)
            startup_session.commit()

        await queue.start()
        app_instance.state.campaign_queue = queue
        app_instance.state.rate_limiter = limiter

        logger.info("Application started")
        try:
            yield
        finally:
            await queue.stop()
            logger.info("Application shut down")

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.parsed_cors_origins() or ["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        started = perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (perf_counter() - started) * 1000
            logger.exception(
                "request_failed method=%s path=%s duration_ms=%.2f request_id=%s",
                request.method,
                request.url.path,
                duration_ms,
                request_id,
            )
            raise

        duration_ms = (perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id

        if settings.security_headers_enabled:
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        logger.info(
            "request method=%s path=%s status=%d duration_ms=%.2f request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response

    async def _enforce_dashboard_request_limits(request: Request, bucket: str, bucket_limit: int) -> None:
        await enforce_rate_limit(
            request=request,
            limiter=limiter,
            bucket="dashboard",
            max_per_minute=settings.rate_limit_dashboard_per_minute,
            trust_proxy_headers=settings.trust_proxy_headers,
        )
        await enforce_rate_limit(
            request=request,
            limiter=limiter,
            bucket=bucket,
            max_per_minute=bucket_limit,
            trust_proxy_headers=settings.trust_proxy_headers,
        )

    def _apply_dashboard_session_cookie(response: Response) -> None:
        response.set_cookie(
            key=settings.dashboard_session_cookie_name,
            value=build_dashboard_session_token(settings),
            httponly=True,
            secure=settings.dashboard_session_secure,
            samesite=settings.dashboard_session_same_site,
            max_age=settings.dashboard_session_ttl_seconds,
        )

    def _clear_dashboard_session_cookie(response: Response) -> None:
        response.delete_cookie(
            key=settings.dashboard_session_cookie_name,
            secure=settings.dashboard_session_secure,
            samesite=settings.dashboard_session_same_site,
        )

    async def _run_vapi_preflight_or_raise(session: Session) -> None:
        if not settings.vapi_preflight_required_for_campaign:
            return

        preflight = await VapiService(settings).preflight_check()
        if preflight.get("ok"):
            return

        write_audit_event(
            session,
            event_type="vapi_preflight_failed",
            source="dashboard",
            details={
                "errors": preflight.get("errors", []),
                "warnings": preflight.get("warnings", []),
            },
        )
        session.commit()
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Vapi preflight failed",
                "errors": preflight.get("errors", []),
                "warnings": preflight.get("warnings", []),
            },
        )

    def _validate_vapi_secret(request: Request) -> None:
        if not settings.vapi_webhook_secret:
            return

        provided = request.headers.get("X-Vapi-Secret", "")
        if not provided or not secrets.compare_digest(provided, settings.vapi_webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid Vapi webhook secret")

    def _validate_twilio_signature(request: Request, payload: dict[str, str]) -> None:
        if not settings.twilio_validate_signature:
            return

        signature = request.headers.get("X-Twilio-Signature", "")
        if not signature:
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")
        if not twilio_validator:
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

        if not twilio_validator.validate(str(request.url), payload, signature):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    @app.get("/ready")
    async def readiness(session: Session = Depends(get_session)):
        try:
            session.exec(select(Lead.id).limit(1)).all()
        except Exception as exc:
            logger.error("Readiness check failed: %s", exc)
            raise HTTPException(status_code=503, detail="not_ready") from exc
        return {"status": "ready"}

    @app.get("/auth/dashboard/status", response_model=DashboardAuthResponse)
    async def dashboard_auth_status(request: Request, current_settings: Settings = Depends(get_settings)):
        auth_required = current_settings.dashboard_auth_enabled()
        return DashboardAuthResponse(
            authenticated=has_valid_dashboard_session(request, current_settings) if auth_required else True,
            auth_required=auth_required,
        )

    @app.post("/auth/dashboard/login", response_model=DashboardAuthResponse)
    async def dashboard_login(
        payload: DashboardAuthRequest,
        response: Response,
        current_settings: Settings = Depends(get_settings),
    ):
        if not current_settings.dashboard_auth_enabled():
            return DashboardAuthResponse(authenticated=True, auth_required=False)

        if not secrets.compare_digest(payload.password, current_settings.dashboard_api_key):
            raise HTTPException(status_code=401, detail="Invalid dashboard credentials")

        _apply_dashboard_session_cookie(response)
        return DashboardAuthResponse(authenticated=True, auth_required=True)

    @app.post("/auth/dashboard/logout", response_model=DashboardAuthResponse)
    async def dashboard_logout(response: Response, current_settings: Settings = Depends(get_settings)):
        _clear_dashboard_session_cookie(response)
        return DashboardAuthResponse(authenticated=False, auth_required=current_settings.dashboard_auth_enabled())

    @app.post("/upload", response_model=UploadResponse, dependencies=[Depends(require_dashboard_auth)])
    async def upload_leads(
        request: Request,
        file: UploadFile = File(...),
        session: Session = Depends(get_session),
    ):
        await _enforce_dashboard_request_limits(
            request=request,
            bucket="dashboard-upload",
            bucket_limit=settings.rate_limit_upload_per_minute,
        )

        filename = file.filename or ""
        if not filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="Only CSV files are supported")

        contents = await file.read()
        if len(contents) > MAX_CSV_SIZE_BYTES:
            raise HTTPException(status_code=400, detail=f"CSV file exceeds {MAX_CSV_SIZE_BYTES // (1024 * 1024)}MB limit")
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        rows, skipped_invalid = _parse_csv(contents)
        if not rows:
            raise HTTPException(status_code=400, detail="No valid leads found in CSV")

        candidate_phones = [row["phone"] for row in rows]
        existing_phones = set(session.exec(select(Lead.phone).where(Lead.phone.in_(candidate_phones))).all())

        now = _utcnow()
        leads_to_create: list[Lead] = []
        for row in rows:
            if row["phone"] in existing_phones:
                skipped_invalid += 1
                continue
            existing_phones.add(row["phone"])
            leads_to_create.append(
                Lead(
                    name=row["name"],
                    phone=row["phone"],
                    location=row["location"],
                    budget_range=row["budget_range"],
                    bhk_preference=row["bhk_preference"],
                    status=LEAD_STATUS_PENDING,
                    created_at=now,
                )
            )

        created = 0
        if leads_to_create:
            session.add_all(leads_to_create)
            try:
                session.commit()
                created = len(leads_to_create)
            except IntegrityError:
                session.rollback()
                for lead in leads_to_create:
                    session.add(lead)
                    try:
                        session.commit()
                        created += 1
                    except IntegrityError:
                        session.rollback()
                        skipped_invalid += 1

        write_audit_event(
            session,
            event_type="dashboard_upload",
            source="dashboard",
            details={"created": created, "skipped": skipped_invalid},
        )
        session.commit()

        logger.info("Uploaded %d leads (skipped %d)", created, skipped_invalid)
        return UploadResponse(
            message=f"Uploaded {created} leads"
            + (f" (skipped {skipped_invalid} invalid/duplicate rows)" if skipped_invalid else ""),
            created=created,
            skipped=skipped_invalid,
        )

    @app.get("/leads", response_model=LeadListResponse, dependencies=[Depends(require_dashboard_auth)])
    async def list_leads(
        request: Request,
        session: Session = Depends(get_session),
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        search: str | None = None,
        active_only: bool = False,
    ):
        await _enforce_dashboard_request_limits(
            request=request,
            bucket="dashboard-leads",
            bucket_limit=settings.rate_limit_dashboard_per_minute,
        )
        limit = max(1, min(limit, 200))
        offset = max(0, offset)

        filters: list[Any] = []
        if status:
            filters.append(Lead.status == status.strip().lower())
        if active_only:
            filters.append(Lead.status.in_(tuple(ACTIVE_LEAD_STATUSES)))
        if search and search.strip():
            term = search.strip()
            filters.append(
                or_(
                    Lead.name.contains(term),
                    Lead.phone.contains(term),
                    Lead.location.contains(term),
                )
            )

        statement = select(Lead)
        total_statement = select(func.count()).select_from(Lead)
        stats_statement = select(Lead.status, func.count()).group_by(Lead.status)
        for condition in filters:
            statement = statement.where(condition)
            total_statement = total_statement.where(condition)
            stats_statement = stats_statement.where(condition)

        items = session.exec(statement.order_by(col(Lead.id)).offset(offset).limit(limit)).all()
        total = int(session.exec(total_statement).one())
        stats_rows = session.exec(stats_statement).all()
        return LeadListResponse(
            items=[LeadRecord.model_validate(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
            stats=_lead_stats_from_rows(stats_rows),
        )

    @app.post("/start-campaign", response_model=CampaignResponse, dependencies=[Depends(require_dashboard_auth)])
    async def start_campaign(request: Request, session: Session = Depends(get_session)):
        await _enforce_dashboard_request_limits(
            request=request,
            bucket="dashboard-campaign",
            bucket_limit=settings.rate_limit_campaign_per_minute,
        )

        await _run_vapi_preflight_or_raise(session)

        pending = session.exec(select(Lead).where(Lead.status == LEAD_STATUS_PENDING)).all()
        if not pending:
            return CampaignResponse(message="No pending leads to queue", queued=0)

        ids: list[int] = []
        skipped_dnc = 0
        now = _utcnow()
        for lead in pending:
            if lead.do_not_contact:
                lead.status = LEAD_STATUS_DNC
                lead.contact_outcome = CONTACT_OUTCOME_DNC_REQUESTED
                lead.updated_at = now
                skipped_dnc += 1
                session.add(lead)
                continue

            lead.status = LEAD_STATUS_QUEUED
            lead.updated_at = now
            session.add(lead)
            if lead.id is not None:
                ids.append(lead.id)

        session.commit()
        queued_count = await queue.enqueue_many(ids)

        write_audit_event(
            session,
            event_type="campaign_started",
            source="dashboard",
            details={"requested": len(ids), "queued": queued_count, "skipped_dnc": skipped_dnc},
        )
        session.commit()

        logger.info("Campaign started: requested=%d queued=%d skipped_dnc=%d", len(ids), queued_count, skipped_dnc)
        return CampaignResponse(message=f"Queued {queued_count} calls", queued=queued_count)

    @app.get("/manager-status", response_model=ManagerStatus, dependencies=[Depends(require_dashboard_auth)])
    async def manager_status(request: Request, current_settings: Settings = Depends(get_settings)):
        await _enforce_dashboard_request_limits(
            request=request,
            bucket="dashboard-manager-status",
            bucket_limit=settings.rate_limit_dashboard_per_minute,
        )
        return ManagerStatus(
            connected=bool(current_settings.twilio_from_number and current_settings.manager_phone_number),
            join_code=current_settings.manager_join_code,
            sandbox_number=current_settings.twilio_from_number,
        )

    @app.get("/diagnostics/vapi-preflight", response_model=VapiPreflightResponse, dependencies=[Depends(require_dashboard_auth)])
    async def diagnostics_vapi_preflight(request: Request):
        await _enforce_dashboard_request_limits(
            request=request,
            bucket="dashboard-vapi-preflight",
            bucket_limit=settings.rate_limit_dashboard_per_minute,
        )
        preflight = await VapiService(settings).preflight_check()
        return VapiPreflightResponse(
            ok=bool(preflight.get("ok")),
            errors=list(preflight.get("errors", [])),
            warnings=list(preflight.get("warnings", [])),
            details=dict(preflight.get("details", {})),
        )

    @app.post("/leads/{lead_id}/do-not-contact", response_model=WebhookResponse, dependencies=[Depends(require_dashboard_auth)])
    async def mark_do_not_contact(
        lead_id: int,
        request: Request,
        payload: dict[str, Any] | None = None,
        session: Session = Depends(get_session),
    ):
        await _enforce_dashboard_request_limits(
            request=request,
            bucket="dashboard-dnc",
            bucket_limit=settings.rate_limit_campaign_per_minute,
        )

        lead = session.get(Lead, lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")

        reason = "manual_dnc"
        if isinstance(payload, dict):
            provided_reason = payload.get("reason")
            if isinstance(provided_reason, str) and provided_reason.strip():
                reason = _truncate(provided_reason.strip(), 250)

        now = _utcnow()
        lead.do_not_contact = True
        lead.dnc_reason = reason
        lead.dnc_updated_at = now
        lead.status = LEAD_STATUS_DNC
        lead.contact_outcome = CONTACT_OUTCOME_DNC_REQUESTED
        lead.updated_at = now
        session.add(lead)

        write_audit_event(
            session,
            event_type="lead_dnc_marked",
            source="dashboard",
            lead_id=lead.id,
            details={"reason": reason},
        )
        session.commit()
        return WebhookResponse(status="ok")

    @app.delete("/leads/{lead_id}", response_model=APIMessage, dependencies=[Depends(require_dashboard_auth)])
    async def delete_lead(
        lead_id: int,
        request: Request,
        session: Session = Depends(get_session),
    ):
        await _enforce_dashboard_request_limits(
            request=request,
            bucket="dashboard-delete-lead",
            bucket_limit=settings.rate_limit_campaign_per_minute,
        )

        lead = session.get(Lead, lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")

        if lead.status not in _DELETABLE_LEAD_STATUSES:
            raise HTTPException(
                status_code=409,
                detail="Only completed, failed, voicemail, or do-not-contact leads can be deleted",
            )

        deleted_name = lead.name
        deleted_phone = lead.phone
        campaign_jobs = session.exec(select(CampaignJob).where(CampaignJob.lead_id == lead.id)).all()
        for job in campaign_jobs:
            session.delete(job)

        session.delete(lead)
        write_audit_event(
            session,
            event_type="lead_deleted",
            source="dashboard",
            lead_id=lead_id,
            details={"name": deleted_name, "phone": deleted_phone, "status": lead.status},
        )
        session.commit()
        return APIMessage(message=f"Deleted lead {deleted_name}")

    @app.post("/webhook/vapi", response_model=WebhookResponse)
    async def vapi_webhook(
        request: Request,
        payload: dict[str, Any],
        background_tasks: BackgroundTasks,
        session: Session = Depends(get_session),
        current_settings: Settings = Depends(get_settings),
    ):
        await enforce_rate_limit(
            request=request,
            limiter=limiter,
            bucket="webhook-vapi",
            max_per_minute=settings.rate_limit_webhook_per_minute,
            trust_proxy_headers=settings.trust_proxy_headers,
        )
        _validate_vapi_secret(request)

        message = payload.get("message", {})
        if not isinstance(message, dict):
            raise HTTPException(status_code=400, detail="Invalid webhook payload")

        event_type = str(message.get("type", "")).strip()
        call = message.get("call", {})
        call_id = str(call.get("id", "")).strip() if isinstance(call, dict) else ""
        event_key = _extract_vapi_event_key(payload=payload, message=message, call_id=call_id, event_type=event_type)

        is_duplicate = register_webhook_event_attempt(
            session,
            provider="vapi",
            event_key=event_key,
            payload=payload,
            dedupe_ttl_seconds=settings.webhook_dedupe_ttl_seconds,
        )
        if is_duplicate:
            mark_webhook_event_status(session, provider="vapi", event_key=event_key, status="duplicate")
            session.commit()
            return WebhookResponse(status="duplicate_ignored")

        if event_type != "end-of-call-report":
            mark_webhook_event_status(session, provider="vapi", event_key=event_key, status="ignored")
            write_audit_event(
                session,
                event_type="vapi_webhook_ignored",
                source="vapi_webhook",
                call_id=call_id or None,
                details={"event_type": event_type},
            )
            session.commit()
            return WebhookResponse(status="ignored")

        if not call_id:
            mark_webhook_event_status(session, provider="vapi", event_key=event_key, status="invalid")
            session.commit()
            raise HTTPException(status_code=400, detail="Missing call id")

        lead = session.exec(select(Lead).where(Lead.call_id == call_id)).first()
        if not lead:
            mark_webhook_event_status(session, provider="vapi", event_key=event_key, status="unknown_call")
            write_audit_event(
                session,
                event_type="vapi_unknown_call",
                source="vapi_webhook",
                call_id=call_id,
            )
            session.commit()
            logger.warning("Webhook for unknown call_id=%s", call_id)
            return WebhookResponse(status="unknown_call")

        summary = _summary_from_webhook(message)
        ended_reason = str(message.get("endedReason", "") or "")
        structured = _extract_structured_analysis(message)
        interest_level = _normalized_interest_level(structured, summary, ended_reason)
        contact_outcome = _determine_contact_outcome(
            summary=summary,
            ended_reason=ended_reason,
            interest_level=interest_level,
            structured=structured,
        )
        next_status = _status_from_contact_outcome(contact_outcome)

        already_final = lead.status in TERMINAL_STATUSES
        same_terminal_update = (
            already_final
            and lead.status == next_status
            and (lead.summary or "") == summary
            and (lead.interest_level or "") == (interest_level or "")
            and (lead.contact_outcome or "") == contact_outcome
        )
        if same_terminal_update:
            mark_webhook_event_status(session, provider="vapi", event_key=event_key, status="duplicate")
            session.commit()
            return WebhookResponse(status="duplicate_ignored")

        now = _utcnow()
        lead.summary = summary
        lead.interest_level = interest_level
        lead.contact_outcome = contact_outcome
        lead.status = next_status
        lead.updated_at = now
        if contact_outcome == CONTACT_OUTCOME_DNC_REQUESTED:
            lead.do_not_contact = True
            lead.dnc_reason = _truncate(f"webhook:{ended_reason or contact_outcome}", 250)
            lead.dnc_updated_at = now
        session.add(lead)

        write_audit_event(
            session,
            event_type="vapi_call_completed",
            source="vapi_webhook",
            lead_id=lead.id,
            call_id=call_id,
            details={
                "status": next_status,
                "interest_level": interest_level,
                "contact_outcome": contact_outcome,
                "ended_reason": ended_reason,
            },
        )
        mark_webhook_event_status(session, provider="vapi", event_key=event_key, status="processed")
        session.commit()

        logger.info("Lead %s webhook processed: status=%s interest=%s", lead.id, lead.status, lead.interest_level)

        should_notify_hot_lead = (not already_final) and next_status == LEAD_STATUS_COMPLETED and is_hot_lead(interest_level, summary)
        if should_notify_hot_lead:
            background_tasks.add_task(
                _send_hot_lead_notification_task,
                settings=current_settings,
                lead_id=lead.id,
                call_id=call_id,
                lead_name=lead.name,
                summary=summary,
            )

        return WebhookResponse(status="ok")

    @app.post("/webhook/twilio-status", response_model=WebhookResponse)
    async def twilio_status_callback(request: Request, session: Session = Depends(get_session)):
        await enforce_rate_limit(
            request=request,
            limiter=limiter,
            bucket="webhook-twilio",
            max_per_minute=settings.rate_limit_webhook_per_minute,
            trust_proxy_headers=settings.trust_proxy_headers,
        )

        form_data = await request.form()
        payload = {key: str(value) for key, value in form_data.items()}
        _validate_twilio_signature(request, payload)

        event_key = _extract_twilio_event_key(payload)
        is_duplicate = register_webhook_event_attempt(
            session,
            provider="twilio_status",
            event_key=event_key,
            payload=payload,
            dedupe_ttl_seconds=settings.webhook_dedupe_ttl_seconds,
        )
        if is_duplicate:
            mark_webhook_event_status(session, provider="twilio_status", event_key=event_key, status="duplicate")
            session.commit()
            return WebhookResponse(status="duplicate_ignored")

        message_sid = payload.get("MessageSid", "unknown")
        message_status = payload.get("MessageStatus", "unknown")

        write_audit_event(
            session,
            event_type="twilio_status_callback",
            source="twilio_webhook",
            details={
                "message_sid": message_sid,
                "status": message_status,
                "error_code": payload.get("ErrorCode"),
                "error_message": payload.get("ErrorMessage"),
            },
        )
        mark_webhook_event_status(session, provider="twilio_status", event_key=event_key, status="processed")
        session.commit()

        if message_status in {"delivered", "read"}:
            logger.info("Twilio status callback: sid=%s status=%s", message_sid, message_status)
        elif message_status == "failed":
            logger.warning(
                "Twilio status callback failed: sid=%s status=%s error=%s",
                message_sid,
                message_status,
                payload.get("ErrorMessage", ""),
            )
        else:
            logger.debug("Twilio status callback: sid=%s status=%s", message_sid, message_status)

        return WebhookResponse(status="ok")

    if settings.enable_test_endpoints:

        @app.post("/test/mark-call-completed/{call_id}")
        async def test_mark_call_completed(
            call_id: str,
            summary: str = (
                "Customer expressed interest in scheduling a site visit to Bandra property. "
                "Budget range is around 2-3 crore. Timeline is within 2-3 months."
            ),
            session: Session = Depends(get_session),
            current_settings: Settings = Depends(get_settings),
        ):
            lead = session.exec(select(Lead).where(Lead.call_id == call_id)).first()
            if not lead:
                raise HTTPException(status_code=404, detail=f"Call {call_id} not found")

            if lead.status in TERMINAL_STATUSES:
                return {"status": "already_completed", "lead_status": lead.status}

            safe_summary = _truncate(summary, MAX_SUMMARY_LENGTH)
            lead.status = LEAD_STATUS_COMPLETED
            lead.summary = safe_summary
            lead.interest_level = classify_interest(safe_summary)
            lead.contact_outcome = CONTACT_OUTCOME_QUALIFIED if lead.interest_level == "high" else CONTACT_OUTCOME_UNKNOWN
            lead.updated_at = _utcnow()
            session.add(lead)
            session.commit()

            response_data: dict[str, Any] = {
                "status": "ok",
                "lead_id": lead.id,
                "lead_status": lead.status,
                "interest_level": lead.interest_level,
                "summary": safe_summary,
                "whatsapp_sent": False,
            }

            if is_hot_lead(lead.interest_level, safe_summary):
                twilio_service = TwilioService(current_settings)
                sid = twilio_service.send_hot_lead_summary(lead.name, safe_summary)
                response_data["is_hot_lead"] = True
                if sid:
                    response_data["whatsapp_sent"] = True
                    response_data["whatsapp_sid"] = sid
                else:
                    response_data["whatsapp_error"] = "Failed to send via Twilio"
            else:
                response_data["is_hot_lead"] = False
                response_data["whatsapp_reason"] = f"Not classified as hot lead (interest={lead.interest_level})"

            return response_data

        @app.post("/test/lead/{lead_id}/simulate-completion")
        async def test_lead_simulate_completion(
            lead_id: int,
            summary: str = (
                "Customer expressed interest in scheduling a site visit to Bandra property. "
                "Budget range is around 2-3 crore. Timeline is within 2-3 months."
            ),
            session: Session = Depends(get_session),
            current_settings: Settings = Depends(get_settings),
        ):
            lead = session.get(Lead, lead_id)
            if not lead:
                raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")

            if lead.status in TERMINAL_STATUSES:
                return {"status": "already_completed", "lead_status": lead.status}

            safe_summary = _truncate(summary, MAX_SUMMARY_LENGTH)
            lead.status = LEAD_STATUS_COMPLETED
            lead.summary = safe_summary
            lead.interest_level = classify_interest(safe_summary)
            lead.contact_outcome = CONTACT_OUTCOME_QUALIFIED if lead.interest_level == "high" else CONTACT_OUTCOME_UNKNOWN
            lead.updated_at = _utcnow()
            session.add(lead)
            session.commit()

            response_data: dict[str, Any] = {
                "status": "ok",
                "lead_id": lead.id,
                "lead_name": lead.name,
                "lead_status": lead.status,
                "interest_level": lead.interest_level,
                "summary": safe_summary[:100] + "..." if len(safe_summary) > 100 else safe_summary,
                "whatsapp_sent": False,
            }

            if is_hot_lead(lead.interest_level, safe_summary):
                twilio_service = TwilioService(current_settings)
                sid = twilio_service.send_hot_lead_summary(lead.name, safe_summary)
                response_data["is_hot_lead"] = True
                if sid:
                    response_data["whatsapp_sent"] = True
                    response_data["whatsapp_sid"] = sid
                else:
                    response_data["whatsapp_error"] = "Failed to send via Twilio"
            else:
                response_data["is_hot_lead"] = False
                response_data["whatsapp_reason"] = f"Not classified as hot lead (interest={lead.interest_level})"

            return response_data

    return app


app = create_app()
