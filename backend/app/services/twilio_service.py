import logging
from typing import Optional

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from app.config import Settings

logger = logging.getLogger("parmar.twilio")

_MAX_BODY_LENGTH = 1600  # WhatsApp message limit


class TwilioService:
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
            logger.warning("Twilio not configured — skipping hot lead notification for %s", lead_name)
            return None

        client = Client(self.settings.twilio_account_sid, self.settings.twilio_auth_token)
        body = f"🏠 New Hot Lead: {lead_name}\n\n📝 Summary: {summary}"
        if len(body) > _MAX_BODY_LENGTH:
            body = body[:_MAX_BODY_LENGTH - 3] + "..."

        try:
            message = client.messages.create(
                from_=self.settings.twilio_from_number,
                to=self.settings.manager_phone_number,
                body=body,
            )
            logger.info("WhatsApp notification sent to manager (sid=%s) for lead %s", message.sid, lead_name)
            return message.sid
        except TwilioRestException as exc:
            logger.error("Twilio send failed for lead %s: [%d] %s", lead_name, exc.code, exc.msg)
            return None
