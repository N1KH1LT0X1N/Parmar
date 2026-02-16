import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlmodel import Session, delete, select

from app.config import Settings
from app.models import (
    AuditEvent,
    CampaignJob,
    JOB_TERMINAL_STATUSES,
    MAX_AUDIT_DETAIL_LENGTH,
    ProcessedWebhookEvent,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def payload_sha256(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def write_audit_event(
    session: Session,
    *,
    event_type: str,
    source: str,
    lead_id: int | None = None,
    call_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    detail_text: str | None = None
    if details is not None:
        detail_text = json.dumps(details, separators=(",", ":"), ensure_ascii=True)
        if len(detail_text) > MAX_AUDIT_DETAIL_LENGTH:
            detail_text = detail_text[: MAX_AUDIT_DETAIL_LENGTH - 3] + "..."

    session.add(
        AuditEvent(
            event_type=event_type,
            source=source,
            lead_id=lead_id,
            call_id=call_id,
            details=detail_text,
            created_at=utcnow(),
        )
    )


def register_webhook_event_attempt(
    session: Session,
    *,
    provider: str,
    event_key: str,
    payload: dict[str, Any],
    dedupe_ttl_seconds: int,
) -> bool:
    existing = session.exec(
        select(ProcessedWebhookEvent).where(
            ProcessedWebhookEvent.provider == provider,
            ProcessedWebhookEvent.event_key == event_key,
        )
    ).first()

    now = utcnow()
    if existing:
        is_fresh_duplicate = (now - as_utc(existing.last_seen_at)).total_seconds() <= dedupe_ttl_seconds
        if not is_fresh_duplicate:
            existing.payload_hash = payload_sha256(payload)
            existing.status = "received"
            existing.process_count = 1
            existing.first_seen_at = now
            existing.last_seen_at = now
            session.add(existing)
            return False

        existing.process_count += 1
        existing.last_seen_at = now
        session.add(existing)
        return True

    session.add(
        ProcessedWebhookEvent(
            provider=provider,
            event_key=event_key,
            payload_hash=payload_sha256(payload),
            status="received",
            process_count=1,
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    return False


def mark_webhook_event_status(
    session: Session,
    *,
    provider: str,
    event_key: str,
    status: str,
) -> None:
    event = session.exec(
        select(ProcessedWebhookEvent).where(
            ProcessedWebhookEvent.provider == provider,
            ProcessedWebhookEvent.event_key == event_key,
        )
    ).first()
    if not event:
        return
    event.status = status
    event.last_seen_at = utcnow()
    session.add(event)


def cleanup_retention_data(session: Session, settings: Settings) -> None:
    now = utcnow()
    webhook_cutoff = now - timedelta(days=settings.webhook_retention_days)
    audit_cutoff = now - timedelta(days=settings.audit_retention_days)
    job_cutoff = now - timedelta(days=settings.job_retention_days)

    session.exec(delete(ProcessedWebhookEvent).where(ProcessedWebhookEvent.last_seen_at < webhook_cutoff))
    session.exec(delete(AuditEvent).where(AuditEvent.created_at < audit_cutoff))
    session.exec(
        delete(CampaignJob).where(
            CampaignJob.finished_at < job_cutoff,
            CampaignJob.status.in_(tuple(JOB_TERMINAL_STATUSES)),
        )
    )
