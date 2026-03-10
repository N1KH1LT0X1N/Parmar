from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(REPO_ROOT / ".env"), extra="ignore")

    app_name: str = "Parmar Properties AI Agent API"
    database_url: str = "sqlite:///./database.db"

    vapi_api_key: str = Field(default="", validation_alias=AliasChoices("VAPI_API_KEY", "VAPI_PRIVATE_KEY"))
    vapi_assistant_id: str = ""
    vapi_phone_number_id: str = ""
    vapi_base_url: str = "https://api.vapi.ai"
    vapi_api_url: str = "https://api.vapi.ai/call"
    vapi_assistant_api_base_url: str = "https://api.vapi.ai/assistant"
    vapi_webhook_url: str = ""  # Optional reference only
    vapi_webhook_secret: str = ""
    vapi_preflight_required_for_campaign: bool = True
    vapi_preflight_timeout_seconds: int = Field(default=15, ge=5, le=120)
    vapi_require_assistant_server_config: bool = True
    vapi_expected_server_url: str = ""
    vapi_verify_assistant_before_call: bool = False
    vapi_assistant_verify_timeout_seconds: int = Field(default=10, ge=3, le=60)
    vapi_expected_assistant_name: str = ""
    vapi_expected_prompt_contains: str = ""
    vapi_max_retries: int = Field(default=3, ge=1, le=10)
    vapi_timeout_seconds: int = Field(default=25, ge=5, le=120)
    vapi_circuit_failure_threshold: int = Field(default=3, ge=1, le=20)
    vapi_circuit_open_seconds: int = Field(default=30, ge=5, le=600)

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    manager_phone_number: str = ""
    manager_join_code: str = ""
    twilio_validate_signature: bool = False
    twilio_max_retries: int = Field(default=2, ge=1, le=10)
    twilio_circuit_failure_threshold: int = Field(default=3, ge=1, le=20)
    twilio_circuit_open_seconds: int = Field(default=30, ge=5, le=600)

    dashboard_api_key: str = ""
    dashboard_api_key_header: str = "X-API-Key"
    dashboard_session_secret: str = ""
    dashboard_session_cookie_name: str = "parmar_dashboard_session"
    dashboard_session_ttl_seconds: int = Field(default=8 * 60 * 60, ge=300, le=7 * 24 * 60 * 60)
    dashboard_session_secure: bool = False
    dashboard_session_same_site: Literal["lax", "strict", "none"] = "lax"

    max_concurrent_calls: int = Field(default=1, ge=1, le=10)
    max_call_attempts: int = Field(default=3, ge=1, le=10)
    job_poll_interval_seconds: float = Field(default=0.5, ge=0.1, le=10.0)
    job_lease_seconds: int = Field(default=60, ge=10, le=600)

    env_validation_mode: Literal["warn", "strict"] = "warn"
    enable_test_endpoints: bool = False

    rate_limit_dashboard_per_minute: int = Field(default=120, ge=10, le=5000)
    rate_limit_upload_per_minute: int = Field(default=30, ge=1, le=1000)
    rate_limit_campaign_per_minute: int = Field(default=20, ge=1, le=1000)
    rate_limit_webhook_per_minute: int = Field(default=300, ge=10, le=10000)

    webhook_dedupe_ttl_seconds: int = Field(default=24 * 60 * 60, ge=60, le=7 * 24 * 60 * 60)
    webhook_retention_days: int = Field(default=30, ge=1, le=365)
    audit_retention_days: int = Field(default=30, ge=1, le=365)
    job_retention_days: int = Field(default=7, ge=1, le=365)

    security_headers_enabled: bool = True
    cors_allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    log_pii_redaction_enabled: bool = True
    trust_proxy_headers: bool = False

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

        if not self.dashboard_api_key:
            errors.append("DASHBOARD_API_KEY is missing (recommended for protected dashboard endpoints)")

        return errors

    def parsed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    def dashboard_auth_enabled(self) -> bool:
        return bool(self.dashboard_api_key)

    def dashboard_session_signing_secret(self) -> str:
        return self.dashboard_session_secret or self.dashboard_api_key


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
