from typing import Optional

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from app.config import Settings


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
            return None

        client = Client(self.settings.twilio_account_sid, self.settings.twilio_auth_token)
        body = f"🏠 New Hot Lead: {lead_name}\n\n📝 Summary: {summary}"

        try:
            message = client.messages.create(
                from_=self.settings.twilio_from_number,
                to=self.settings.manager_phone_number,
                body=body,
            )
            return message.sid
        except TwilioRestException:
            return None
