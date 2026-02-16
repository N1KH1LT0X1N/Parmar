import asyncio
import logging
import secrets
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings
from app.models import Lead

logger = logging.getLogger("parmar.vapi")


@dataclass
class _CircuitState:
    failure_count: int = 0
    opened_until: float = 0.0


class VapiService:
    _circuit_state = _CircuitState()
    _circuit_lock = asyncio.Lock()

    def __init__(self, settings: Settings):
        self.settings = settings

    async def create_outbound_call(self, lead: Lead) -> str:
        if not self.settings.vapi_api_key:
            raise RuntimeError("VAPI_API_KEY is missing")
        if not self.settings.vapi_assistant_id:
            raise RuntimeError("VAPI_ASSISTANT_ID is missing")
        if not self.settings.vapi_phone_number_id:
            raise RuntimeError("VAPI_PHONE_NUMBER_ID is missing")

        await self._ensure_circuit_closed()

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
        for attempt in range(1, self.settings.vapi_max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.settings.vapi_timeout_seconds) as client:
                    response = await client.post(self.settings.vapi_api_url, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()

                call_id = self._extract_call_id(data)
                await self._record_success()
                logger.info("Outbound call created for lead_id=%s (call_id=%s)", lead.id, call_id)
                return call_id

            except httpx.TimeoutException as exc:
                last_exc = exc
                logger.warning("Vapi timeout (attempt %d/%d) for lead_id=%s", attempt, self.settings.vapi_max_retries, lead.id)

            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                # Do not retry client-side errors.
                if 400 <= status_code < 500:
                    await self._record_failure()
                    logger.error("Vapi client error %d for lead_id=%s", status_code, lead.id)
                    raise

                last_exc = exc
                logger.warning(
                    "Vapi server error %d (attempt %d/%d) for lead_id=%s",
                    status_code,
                    attempt,
                    self.settings.vapi_max_retries,
                    lead.id,
                )

            except Exception as exc:  # defensive fallback
                last_exc = exc
                logger.exception("Unexpected Vapi error for lead_id=%s on attempt %d", lead.id, attempt)

            if attempt < self.settings.vapi_max_retries:
                # Exponential backoff with bounded jitter from a secure PRNG.
                jitter = secrets.randbelow(251) / 1000
                backoff = min(2 ** (attempt - 1), 8) + jitter
                await asyncio.sleep(backoff)

        await self._record_failure()
        raise last_exc or RuntimeError("Vapi call failed after retries")

    @staticmethod
    def _extract_call_id(payload: Any) -> str:
        if isinstance(payload, Mapping):
            call_id = payload.get("id")
            if isinstance(call_id, str) and call_id:
                return call_id
        raise RuntimeError("Vapi response did not include call id")

    async def _ensure_circuit_closed(self) -> None:
        async with self._circuit_lock:
            if time.monotonic() < self._circuit_state.opened_until:
                raise RuntimeError("Vapi circuit breaker is open")

    async def _record_success(self) -> None:
        async with self._circuit_lock:
            self._circuit_state.failure_count = 0
            self._circuit_state.opened_until = 0.0

    async def _record_failure(self) -> None:
        async with self._circuit_lock:
            self._circuit_state.failure_count += 1
            if self._circuit_state.failure_count >= self.settings.vapi_circuit_failure_threshold:
                self._circuit_state.opened_until = time.monotonic() + self.settings.vapi_circuit_open_seconds
                self._circuit_state.failure_count = 0
