import asyncio

from app.config import Settings
from app.models import Lead
from app.services.vapi import VapiService


def test_create_outbound_call_does_not_send_webhook_url(monkeypatch):
    settings = Settings(
        vapi_api_key="test-key",
        vapi_assistant_id="assistant-id",
        vapi_phone_number_id="phone-number-id",
        vapi_webhook_url="https://example.ngrok-free.app/webhook/vapi",
    )
    lead = Lead(name="Nikhil", phone="+919876543210", location="Bandra")

    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "call-123"}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json, headers):
            captured["url"] = url
            captured["payload"] = json
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr("app.services.vapi.httpx.AsyncClient", FakeAsyncClient)

    call_id = asyncio.run(VapiService(settings).create_outbound_call(lead))

    assert call_id == "call-123"
    assert "webhookUrl" not in captured["payload"]
    assert captured["payload"]["assistantId"] == "assistant-id"
    assert captured["payload"]["phoneNumberId"] == "phone-number-id"
