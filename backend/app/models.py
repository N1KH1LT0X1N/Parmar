from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Lead(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone: str
    location: Optional[str] = None
    budget_range: Optional[str] = None
    bhk_preference: Optional[str] = None

    status: str = Field(default="pending")
    interest_level: Optional[str] = None
    summary: Optional[str] = None
    call_id: Optional[str] = Field(default=None, index=True)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
