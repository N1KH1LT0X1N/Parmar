from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


# ---------- Lead status constants ----------
LEAD_STATUS_PENDING = "pending"
LEAD_STATUS_QUEUED = "queued"
LEAD_STATUS_CALLING = "calling"
LEAD_STATUS_COMPLETED = "completed"
LEAD_STATUS_FAILED = "failed"
LEAD_STATUS_VOICEMAIL = "voicemail"

ALL_LEAD_STATUSES = {
    LEAD_STATUS_PENDING,
    LEAD_STATUS_QUEUED,
    LEAD_STATUS_CALLING,
    LEAD_STATUS_COMPLETED,
    LEAD_STATUS_FAILED,
    LEAD_STATUS_VOICEMAIL,
}

TERMINAL_STATUSES = {LEAD_STATUS_COMPLETED, LEAD_STATUS_VOICEMAIL}

# ---------- Constants ----------
MAX_SUMMARY_LENGTH = 500
MAX_ERROR_DETAIL_LENGTH = 220
MAX_CSV_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


class Lead(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=200)
    phone: str = Field(index=True, max_length=20)
    location: Optional[str] = Field(default=None, max_length=200)
    budget_range: Optional[str] = Field(default=None, max_length=100)
    bhk_preference: Optional[str] = Field(default=None, max_length=50)

    status: str = Field(default=LEAD_STATUS_PENDING)
    interest_level: Optional[str] = None
    summary: Optional[str] = None
    call_id: Optional[str] = Field(default=None, index=True)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = Field(default=None)
