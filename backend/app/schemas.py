from pydantic import BaseModel, ConfigDict


class APIMessage(BaseModel):
    message: str


class LeadRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    location: str | None = None
    budget_range: str | None = None
    bhk_preference: str | None = None
    status: str
    interest_level: str | None = None
    contact_outcome: str | None = None
    summary: str | None = None
    call_id: str | None = None
    do_not_contact: bool
    dnc_reason: str | None = None


class UploadResponse(BaseModel):
    message: str
    created: int
    skipped: int


class CampaignResponse(BaseModel):
    message: str
    queued: int


class ManagerStatus(BaseModel):
    connected: bool
    join_code: str
    sandbox_number: str


class WebhookResponse(BaseModel):
    status: str


class LeadStats(BaseModel):
    pending: int = 0
    queued: int = 0
    calling: int = 0
    completed: int = 0
    failed: int = 0
    voicemail: int = 0
    dnc: int = 0


class LeadListResponse(BaseModel):
    items: list[LeadRecord]
    total: int
    limit: int
    offset: int
    stats: LeadStats


class DashboardAuthRequest(BaseModel):
    password: str


class DashboardAuthResponse(BaseModel):
    authenticated: bool
    auth_required: bool


class VapiPreflightResponse(BaseModel):
    ok: bool
    errors: list[str]
    warnings: list[str]
    details: dict[str, object]
