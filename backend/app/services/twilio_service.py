import logging
import secrets
import time
from dataclasses import dataclass
from typing import Optional

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from app.config import Settings

logger = logging.getLogger("parmar.twilio")

_MAX_BODY_LENGTH = 1600  # WhatsApp message limit


@dataclass
class _CircuitState:
    failure_count: int = 0
    opened_until: float = 0.0


class TwilioService:
    _circuit_state = _CircuitState()

    def __init__(self, settings: Settings):
        self.settings = settings

    def is_configured(self) -> bool:
        return all(
            [
                self.settings.twilio_account_sid,
                self.settings.twilio_auth_token,
                self.settings.twilio_from_number,
                self.settings.manager_phone_number,
            ]
        )

    def send_hot_lead_summary(self, lead_name: str, summary: str) -> Optional[str]:
        if not self.is_configured():
            logger.warning("Twilio not configured; skipping hot lead notification for %s", lead_name)
            return None

        if time.monotonic() < self._circuit_state.opened_until:
            logger.warning("Twilio circuit breaker open; skipping send for %s", lead_name)
            return None

        client = Client(self.settings.twilio_account_sid, self.settings.twilio_auth_token)
        body = f"New Hot Lead: {lead_name}\n\nSummary: {summary}"
        if len(body) > _MAX_BODY_LENGTH:
            body = body[: _MAX_BODY_LENGTH - 3] + "..."

        for attempt in range(1, self.settings.twilio_max_retries + 1):
            try:
                message = client.messages.create(
                    from_=self.settings.twilio_from_number,
                    to=self.settings.manager_phone_number,
                    body=body,
                )
                self._record_success()
                logger.info("WhatsApp notification sent to manager (sid=%s) for lead %s", message.sid, lead_name)
                return message.sid

            except TwilioRestException as exc:
                retryable = exc.status is not None and int(exc.status) >= 500
                logger.error("Twilio send failed for lead %s: [%s] %s", lead_name, exc.code, exc.msg)
                if (not retryable) or attempt >= self.settings.twilio_max_retries:
                    self._record_failure()
                    return None

            except Exception:
                logger.exception("Unexpected Twilio send failure for lead %s", lead_name)
                if attempt >= self.settings.twilio_max_retries:
                    self._record_failure()
                    return None

            jitter = secrets.randbelow(201) / 1000
            backoff = min(2 ** (attempt - 1), 4) + jitter
            time.sleep(backoff)

        self._record_failure()
        return None

    def _record_success(self) -> None:
        self._circuit_state.failure_count = 0
        self._circuit_state.opened_until = 0.0

    def _record_failure(self) -> None:
        self._circuit_state.failure_count += 1
        if self._circuit_state.failure_count >= self.settings.twilio_circuit_failure_threshold:
            self._circuit_state.opened_until = time.monotonic() + self.settings.twilio_circuit_open_seconds
            self._circuit_state.failure_count = 0
