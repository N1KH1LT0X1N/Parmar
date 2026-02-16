from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Parmar Properties AI Agent API"
    database_url: str = "sqlite:///./database.db"

    vapi_api_key: str = Field(default="", validation_alias=AliasChoices("VAPI_API_KEY", "VAPI_PRIVATE_KEY"))
    vapi_assistant_id: str = ""
    vapi_phone_number_id: str = ""
    vapi_api_url: str = "https://api.vapi.ai/call"
    vapi_webhook_url: str = ""  # Optional reference; configure webhooks in Vapi assistant/dashboard settings

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    manager_phone_number: str = ""
    manager_join_code: str = ""

    max_concurrent_calls: int = Field(default=1, ge=1, le=10)
    env_validation_mode: Literal["warn", "strict"] = "warn"

    def startup_validation_errors(self) -> list[str]:
        errors: list[str] = []

        if not self.vapi_api_key:
            errors.append("VAPI_API_KEY is missing")
        if not self.vapi_assistant_id:
            errors.append("VAPI_ASSISTANT_ID is missing")
        if not self.vapi_phone_number_id:
            errors.append("VAPI_PHONE_NUMBER_ID is missing")

        twilio_fields = {
            "TWILIO_ACCOUNT_SID": self.twilio_account_sid,
            "TWILIO_AUTH_TOKEN": self.twilio_auth_token,
            "TWILIO_FROM_NUMBER": self.twilio_from_number,
            "MANAGER_PHONE_NUMBER": self.manager_phone_number,
        }
        missing_twilio = [name for name, value in twilio_fields.items() if not value]
        if missing_twilio:
            errors.append(f"Twilio/manager config incomplete: {', '.join(missing_twilio)}")

        return errors


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
