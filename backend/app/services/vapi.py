from typing import Any

import httpx

from app.config import Settings
from app.models import Lead


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

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(self.settings.vapi_api_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        call_id = data.get("id")
        if not call_id:
            raise RuntimeError("Vapi response did not include call id")
        return call_id
