import asyncio

import httpx

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
    variable_values = captured["payload"]["assistantOverrides"]["variableValues"]
    assert variable_values["name"] == "Nikhil"
    assert variable_values["client_name"] == "Nikhil"
    assert variable_values["customer_name"] == "Nikhil"
    assert variable_values["phone"] == "+919876543210"
    assert variable_values["location"] == "Bandra"
    assert variable_values["preferred_location"] == "Bandra"
    assert variable_values["notes"] == "Bandra"
    assert "budget_range" not in variable_values
    assert "bhk_preference" not in variable_values


def test_preflight_check_handles_transport_errors(monkeypatch):
    settings = Settings(
        vapi_api_key="test-key",
        vapi_assistant_id="assistant-id",
        vapi_phone_number_id="phone-number-id",
    )

    class FailingAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr("app.services.vapi.httpx.AsyncClient", FailingAsyncClient)

    result = asyncio.run(VapiService(settings).preflight_check())

    assert result["ok"] is False
    assert any("preflight_http_error" in error for error in result["errors"])
