import asyncio

from sqlmodel import Session, select

from app.database import get_engine
from app.main import process_single_lead
from app.models import Lead


def test_upload_and_list_leads(client):
    csv_content = "Name,Phone,Location,BudgetRange,BHKPreference\nAmit,+919876543210,Juhu,2-3Cr,2BHK\n"
    response = client.post(
        "/upload",
        files={"file": ("leads.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 200
    assert "Uploaded 1 leads" in response.json()["message"]

    leads_response = client.get("/leads")
    assert leads_response.status_code == 200
    leads = leads_response.json()
    assert len(leads) >= 1
    assert leads[-1]["name"] == "Amit"


def test_upload_rejects_invalid_csv_columns(client):
    csv_content = "FirstName,PhoneNumber\nAmit,+919876543210\n"
    response = client.post(
        "/upload",
        files={"file": ("leads.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 400
    assert "Name and Phone" in response.json()["detail"]


def test_start_campaign_marks_pending_as_queued(client, db_session):
    lead = Lead(name="Priya", phone="+919988776655", status="pending")
    db_session.add(lead)
    db_session.commit()

    response = client.post("/start-campaign")
    assert response.status_code == 200
    assert "Queued" in response.json()["message"]

    with Session(get_engine()) as session:
        refreshed = session.exec(select(Lead).where(Lead.name == "Priya")).first()
        assert refreshed is not None
        assert refreshed.status in {"queued", "calling", "failed"}


def test_process_single_lead_marks_calling(db_session, monkeypatch):
    lead = Lead(name="Rina", phone="+919977665544", status="queued")
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    async def fake_create_outbound_call(self, lead_obj):
        return "test-call-xyz"

    monkeypatch.setattr("app.services.vapi.VapiService.create_outbound_call", fake_create_outbound_call)

    from app.config import get_settings

    assert lead.id is not None
    asyncio.run(process_single_lead(lead.id, get_settings()))

    with Session(get_engine()) as session:
        refreshed = session.exec(select(Lead).where(Lead.id == lead.id)).first()
        assert refreshed is not None
        assert refreshed.status == "calling"
        assert refreshed.call_id == "test-call-xyz"


def test_webhook_updates_lead_and_triggers_hot_notification(client, db_session, monkeypatch):
    lead = Lead(name="Raj", phone="+919900000000", status="calling", call_id="call-abc")
    db_session.add(lead)
    db_session.commit()

    sent = {"count": 0}

    def fake_send(self, lead_name, summary):
        sent["count"] += 1
        return "SM123"

    monkeypatch.setattr("app.services.twilio_service.TwilioService.send_hot_lead_summary", fake_send)

    payload = {
        "message": {
            "type": "end-of-call-report",
            "endedReason": "hangup",
            "call": {"id": "call-abc"},
            "artifact": {
                "transcript": "Customer interested in 2BHK in Bandra with 3 crore budget this month"
            },
            "analysis": {
                "summary": "Customer interested in 2BHK in Bandra with 3 crore budget this month"
            },
        }
    }

    response = client.post("/webhook/vapi", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    refreshed = db_session.exec(select(Lead).where(Lead.call_id == "call-abc")).first()
    assert refreshed is not None
    assert refreshed.status == "completed"
    assert refreshed.interest_level == "high"
    assert sent["count"] == 1


def test_webhook_ignores_non_terminal_event(client):
    payload = {"message": {"type": "status-update"}}
    response = client.post("/webhook/vapi", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
