import asyncio
import hashlib
import logging
import secrets
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

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

    def _api_base_url(self) -> str:
        configured_base = self.settings.vapi_base_url.strip()
        if configured_base:
            return configured_base.rstrip("/")

        parsed = urlparse(self.settings.vapi_api_url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        return "https://api.vapi.ai"

    async def preflight_check(self) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        details: dict[str, Any] = {
            "assistant_id": self.settings.vapi_assistant_id,
            "phone_number_id": self.settings.vapi_phone_number_id,
        }

        if not self.settings.vapi_api_key:
            errors.append("VAPI_API_KEY is missing")
        if not self.settings.vapi_assistant_id:
            errors.append("VAPI_ASSISTANT_ID is missing")
        if not self.settings.vapi_phone_number_id:
            errors.append("VAPI_PHONE_NUMBER_ID is missing")

        if errors:
            return {"ok": False, "errors": errors, "warnings": warnings, "details": details}

        headers = {
            "Authorization": f"Bearer {self.settings.vapi_api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.settings.vapi_preflight_timeout_seconds) as client:
                assistant_url = f"{self.settings.vapi_assistant_api_base_url.rstrip('/')}/{self.settings.vapi_assistant_id}"
                assistant_response = await client.get(assistant_url, headers=headers)
                if assistant_response.status_code >= 400:
                    errors.append(
                        f"assistant_lookup_failed: status={assistant_response.status_code} body={assistant_response.text[:300]}"
                    )
                else:
                    try:
                        assistant_payload = assistant_response.json()
                    except ValueError:
                        errors.append("assistant_lookup_failed: invalid_json_response")
                        assistant_payload = {}

                    assistant_name = str(assistant_payload.get("name", "")).strip() if isinstance(assistant_payload, Mapping) else ""
                    details["assistant_name"] = assistant_name

                    server_config = assistant_payload.get("server") if isinstance(assistant_payload, Mapping) else None
                    details["assistant_has_server"] = bool(server_config)
                    if self.settings.vapi_require_assistant_server_config and not server_config:
                        errors.append("assistant_server_missing: assistant has no server URL configured for webhooks")
                    if isinstance(server_config, Mapping):
                        server_url = str(server_config.get("url", "")).strip()
                        details["assistant_server_url"] = server_url
                        expected_server_url = self.settings.vapi_expected_server_url.strip()
                        if expected_server_url and server_url != expected_server_url:
                            errors.append(
                                f"assistant_server_url_mismatch: expected={expected_server_url} actual={server_url or '<empty>'}"
                            )

                phone_number_url = f"{self._api_base_url()}/phone-number"
                phone_response = await client.get(phone_number_url, headers=headers)
                if phone_response.status_code >= 400:
                    errors.append(
                        f"phone_number_lookup_failed: status={phone_response.status_code} body={phone_response.text[:300]}"
                    )
                else:
                    try:
                        phone_payload = phone_response.json()
                    except ValueError:
                        errors.append("phone_number_lookup_failed: invalid_json_response")
                        phone_payload = []

                    phone_items = phone_payload if isinstance(phone_payload, list) else []
                    known_ids = {str(item.get("id", "")).strip() for item in phone_items if isinstance(item, Mapping)}
                    details["available_phone_number_ids"] = sorted(id_value for id_value in known_ids if id_value)
                    if self.settings.vapi_phone_number_id not in known_ids:
                        errors.append(
                            f"phone_number_missing: {self.settings.vapi_phone_number_id} not found in Vapi account"
                        )
        except httpx.TimeoutException as exc:
            errors.append(f"preflight_timeout: {type(exc).__name__}")
        except httpx.HTTPError as exc:
            errors.append(f"preflight_http_error: {type(exc).__name__}: {str(exc)}")
        except Exception as exc:
            errors.append(f"preflight_unexpected_error: {type(exc).__name__}: {str(exc)}")

        if not details.get("available_phone_number_ids"):
            warnings.append("No phone numbers listed for current Vapi API key")

        return {"ok": not errors, "errors": errors, "warnings": warnings, "details": details}

    @staticmethod
    def _normalize_variable_values(lead: Lead) -> dict[str, str]:
        values: dict[str, str] = {
            "name": lead.name,
            "client_name": lead.name,
            "customer_name": lead.name,
            "phone": lead.phone,
            "customer_phone": lead.phone,
        }

        if lead.location:
            values["location"] = lead.location
            values["preferred_location"] = lead.location
        if lead.budget_range:
            values["budget_range"] = lead.budget_range
            values["budget"] = lead.budget_range
        if lead.bhk_preference:
            values["bhk_preference"] = lead.bhk_preference
            values["bhk"] = lead.bhk_preference

        notes_parts = [part for part in [lead.location, lead.budget_range, lead.bhk_preference] if part]
        if notes_parts:
            values["notes"] = " | ".join(notes_parts)

        return {key: value.strip() for key, value in values.items() if isinstance(value, str) and value.strip()}

    @staticmethod
    def _flatten_text(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, Mapping):
            return "\n".join(VapiService._flatten_text(v) for v in value.values())
        if isinstance(value, list):
            return "\n".join(VapiService._flatten_text(item) for item in value)
        return ""

    async def _verify_assistant_snapshot(self, headers: Mapping[str, str]) -> None:
        if not self.settings.vapi_verify_assistant_before_call:
            return

        assistant_url = f"{self.settings.vapi_assistant_api_base_url.rstrip('/')}/{self.settings.vapi_assistant_id}"
        async with httpx.AsyncClient(timeout=self.settings.vapi_assistant_verify_timeout_seconds) as client:
            response = await client.get(assistant_url, headers=headers)
            response.raise_for_status()
            assistant = response.json()

        if not isinstance(assistant, Mapping):
            raise RuntimeError("Vapi assistant verification failed: unexpected response shape")

        assistant_name = str(assistant.get("name", "")).strip()
        flattened = self._flatten_text(assistant)
        prompt_hash = hashlib.sha256(flattened.encode("utf-8")).hexdigest()[:16]

        if self.settings.vapi_expected_assistant_name and assistant_name != self.settings.vapi_expected_assistant_name:
            raise RuntimeError(
                "Vapi assistant verification failed: "
                f"expected name '{self.settings.vapi_expected_assistant_name}', got '{assistant_name or 'unknown'}'"
            )

        expected_snippet = self.settings.vapi_expected_prompt_contains.strip()
        if expected_snippet and expected_snippet.lower() not in flattened.lower():
            raise RuntimeError(
                "Vapi assistant verification failed: expected prompt snippet not found in assistant configuration"
            )

        logger.info(
            "Vapi assistant verification passed (assistant_id=%s name=%s prompt_fingerprint=%s)",
            self.settings.vapi_assistant_id,
            assistant_name or "<unnamed>",
            prompt_hash,
        )

    async def create_outbound_call(self, lead: Lead) -> str:
        if not self.settings.vapi_api_key:
            raise RuntimeError("VAPI_API_KEY is missing")
        if not self.settings.vapi_assistant_id:
            raise RuntimeError("VAPI_ASSISTANT_ID is missing")
        if not self.settings.vapi_phone_number_id:
            raise RuntimeError("VAPI_PHONE_NUMBER_ID is missing")

        await self._ensure_circuit_closed()

        headers = {
            "Authorization": f"Bearer {self.settings.vapi_api_key}",
            "Content-Type": "application/json",
        }
        await self._verify_assistant_snapshot(headers)

        variable_values = self._normalize_variable_values(lead)

        payload: dict[str, Any] = {
            "assistantId": self.settings.vapi_assistant_id,
            "phoneNumberId": self.settings.vapi_phone_number_id,
            "customer": {
                "number": lead.phone,
                "name": lead.name,
            },
            "assistantOverrides": {
                "variableValues": variable_values,
            },
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
                    response_preview = exc.response.text
                    if len(response_preview) > 500:
                        response_preview = response_preview[:497] + "..."
                    logger.error(
                        "Vapi client error %d for lead_id=%s response=%s",
                        status_code,
                        lead.id,
                        response_preview,
                    )
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
