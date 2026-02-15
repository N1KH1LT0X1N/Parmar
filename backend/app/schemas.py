from pydantic import BaseModel


class APIMessage(BaseModel):
    message: str


class ManagerStatus(BaseModel):
    connected: bool
    join_code: str
    sandbox_number: str
