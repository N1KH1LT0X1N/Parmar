from pydantic import BaseModel


class APIMessage(BaseModel):
    message: str


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


class VapiPreflightResponse(BaseModel):
    ok: bool
    errors: list[str]
    warnings: list[str]
    details: dict[str, object]
