from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


# ---------- Lead status constants ----------
LEAD_STATUS_PENDING = "pending"
LEAD_STATUS_QUEUED = "queued"
LEAD_STATUS_CALLING = "calling"
LEAD_STATUS_COMPLETED = "completed"
LEAD_STATUS_FAILED = "failed"
LEAD_STATUS_VOICEMAIL = "voicemail"
LEAD_STATUS_DNC = "dnc"

ALL_LEAD_STATUSES = {
    LEAD_STATUS_PENDING,
    LEAD_STATUS_QUEUED,
    LEAD_STATUS_CALLING,
    LEAD_STATUS_COMPLETED,
    LEAD_STATUS_FAILED,
    LEAD_STATUS_VOICEMAIL,
    LEAD_STATUS_DNC,
}

TERMINAL_STATUSES = {
    LEAD_STATUS_COMPLETED,
    LEAD_STATUS_VOICEMAIL,
    LEAD_STATUS_DNC,
}

ACTIVE_LEAD_STATUSES = {
    LEAD_STATUS_PENDING,
    LEAD_STATUS_QUEUED,
    LEAD_STATUS_CALLING,
}

# ---------- Lead outcome constants ----------
CONTACT_OUTCOME_QUALIFIED = "qualified"
CONTACT_OUTCOME_NOT_INTERESTED = "not_interested"
CONTACT_OUTCOME_WRONG_NUMBER = "wrong_number"
CONTACT_OUTCOME_DNC_REQUESTED = "dnc_requested"
CONTACT_OUTCOME_CALLBACK_REQUESTED = "callback_requested"
CONTACT_OUTCOME_VOICEMAIL = "voicemail"
CONTACT_OUTCOME_NO_ANSWER = "no_answer"
CONTACT_OUTCOME_CALL_FAILED = "call_failed"
CONTACT_OUTCOME_UNKNOWN = "unknown"

ALL_CONTACT_OUTCOMES = {
    CONTACT_OUTCOME_QUALIFIED,
    CONTACT_OUTCOME_NOT_INTERESTED,
    CONTACT_OUTCOME_WRONG_NUMBER,
    CONTACT_OUTCOME_DNC_REQUESTED,
    CONTACT_OUTCOME_CALLBACK_REQUESTED,
    CONTACT_OUTCOME_VOICEMAIL,
    CONTACT_OUTCOME_NO_ANSWER,
    CONTACT_OUTCOME_CALL_FAILED,
    CONTACT_OUTCOME_UNKNOWN,
}

# ---------- Campaign job constants ----------
JOB_STATUS_QUEUED = "queued"
JOB_STATUS_PROCESSING = "processing"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"

JOB_TERMINAL_STATUSES = {JOB_STATUS_COMPLETED, JOB_STATUS_FAILED}

# ---------- Constants ----------
MAX_SUMMARY_LENGTH = 500
MAX_ERROR_DETAIL_LENGTH = 220
MAX_CSV_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_AUDIT_DETAIL_LENGTH = 2000


class Lead(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=200)
    phone: str = Field(index=True, max_length=20, unique=True)
    location: Optional[str] = Field(default=None, max_length=200)
    budget_range: Optional[str] = Field(default=None, max_length=100)
    bhk_preference: Optional[str] = Field(default=None, max_length=50)

    status: str = Field(default=LEAD_STATUS_PENDING, index=True)
    interest_level: Optional[str] = Field(default=None, max_length=20)
    contact_outcome: Optional[str] = Field(default=None, index=True, max_length=40)
    summary: Optional[str] = Field(default=None, max_length=MAX_SUMMARY_LENGTH)
    call_id: Optional[str] = Field(default=None, index=True, max_length=80, unique=True)

    do_not_contact: bool = Field(default=False, index=True)
    dnc_reason: Optional[str] = Field(default=None, max_length=250)
    dnc_updated_at: Optional[datetime] = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    updated_at: Optional[datetime] = Field(default=None)


class CampaignJob(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    lead_id: int = Field(foreign_key="lead.id", index=True)

    status: str = Field(default=JOB_STATUS_QUEUED, index=True)
    attempt_count: int = Field(default=0, ge=0)
    last_error: Optional[str] = Field(default=None, max_length=MAX_ERROR_DETAIL_LENGTH)

    scheduled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    lease_until: Optional[datetime] = Field(default=None, index=True)
    started_at: Optional[datetime] = Field(default=None)
    finished_at: Optional[datetime] = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    updated_at: Optional[datetime] = Field(default=None)


class ProcessedWebhookEvent(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("provider", "event_key", name="uq_provider_event_key"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    provider: str = Field(index=True, max_length=40)
    event_key: str = Field(index=True, max_length=255)
    payload_hash: str = Field(max_length=64)

    status: str = Field(default="received", max_length=40)
    process_count: int = Field(default=1, ge=1)

    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)


class AuditEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_type: str = Field(index=True, max_length=80)
    source: str = Field(index=True, max_length=40)

    lead_id: Optional[int] = Field(default=None, index=True)
    call_id: Optional[str] = Field(default=None, index=True, max_length=80)
    details: Optional[str] = Field(default=None, max_length=MAX_AUDIT_DETAIL_LENGTH)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
