import logging
from typing import Any

import httpx

from app.config import Settings
from app.models import Lead

logger = logging.getLogger("parmar.vapi")

_MAX_RETRIES = 2
_TIMEOUT_SECONDS = 25


class VapiService:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def create_outbound_call(self, lead: Lead) -> str:
        if not self.settings.vapi_api_key:
            raise RuntimeError("VAPI_API_KEY is missing")
        if not self.settings.vapi_assistant_id:
            raise RuntimeError("VAPI_ASSISTANT_ID is missing")
        if not self.settings.vapi_phone_number_id:
            raise RuntimeError("VAPI_PHONE_NUMBER_ID is missing")

        payload: dict[str, Any] = {
            "assistantId": self.settings.vapi_assistant_id,
            "phoneNumberId": self.settings.vapi_phone_number_id,
            "customer": {
                "number": lead.phone,
                "name": lead.name,
            },
            "assistantOverrides": {
                "variableValues": {
                    "name": lead.name,
                    "location": lead.location or "",
                    "budget_range": lead.budget_range or "",
                    "bhk_preference": lead.bhk_preference or "",
                }
            },
        }

        headers = {
            "Authorization": f"Bearer {self.settings.vapi_api_key}",
            "Content-Type": "application/json",
        }

        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                    response = await client.post(self.settings.vapi_api_url, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()

                call_id = data.get("id")
                if not call_id:
                    raise RuntimeError("Vapi response did not include call id")

                logger.info("Outbound call created for %s (call_id=%s)", lead.name, call_id)
                return call_id

            except httpx.TimeoutException as exc:
                last_exc = exc
                logger.warning("Vapi timeout (attempt %d/%d) for %s", attempt, _MAX_RETRIES, lead.name)
            except httpx.HTTPStatusError as exc:
                # Don't retry client errors (4xx)
                if 400 <= exc.response.status_code < 500:
                    logger.error("Vapi client error %d for %s: %s", exc.response.status_code, lead.name, exc.response.text[:200])
                    raise
                last_exc = exc
                logger.warning("Vapi server error %d (attempt %d/%d) for %s", exc.response.status_code, attempt, _MAX_RETRIES, lead.name)

        raise last_exc or RuntimeError("Vapi call failed after retries")
