import asyncio

from sqlmodel import Session, select

from app.database import get_engine
from app.main import process_single_lead
from app.models import Lead


# ---------- Health ----------

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------- Upload ----------

def test_upload_and_list_leads(client):
    csv_content = "Name,Phone,Location,BudgetRange,BHKPreference\nAmit,+919876543210,Juhu,2-3Cr,2BHK\n"
    response = client.post(
        "/upload",
        files={"file": ("leads.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created"] >= 1
    assert "Uploaded" in data["message"]

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


def test_upload_rejects_non_csv_file(client):
    response = client.post(
        "/upload",
        files={"file": ("leads.txt", "some text", "text/plain")},
    )
    assert response.status_code == 400
    assert "CSV" in response.json()["detail"]


def test_upload_rejects_empty_file(client):
    response = client.post(
        "/upload",
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert response.status_code == 400


def test_upload_rejects_csv_without_valid_rows(client):
    csv_content = "Name,Phone\n,\n,\n"
    response = client.post(
        "/upload",
        files={"file": ("leads.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 400
    assert "No valid leads" in response.json()["detail"]


def test_upload_normalizes_indian_phone_format(client):
    csv_content = "Name,Phone\nNikhil,91-9867477169\n"
    response = client.post(
        "/upload",
        files={"file": ("leads.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 200

    leads_response = client.get("/leads")
    leads = leads_response.json()
    assert any(lead["phone"] == "+919867477169" for lead in leads)


def test_upload_case_insensitive_headers(client):
    csv_content = "name,phone\nCaseTest,+919000000001\n"
    response = client.post(
        "/upload",
        files={"file": ("leads.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["created"] >= 1


def test_upload_skips_duplicate_phones_within_csv(client):
    csv_content = "Name,Phone\nA,+919000000010\nB,+919000000010\n"
    response = client.post(
        "/upload",
        files={"file": ("leads.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["skipped"] >= 1


def test_upload_skips_duplicate_phones_against_db(client):
    # First upload
    csv_content = "Name,Phone\nFirst,+919000000020\n"
    client.post("/upload", files={"file": ("leads.csv", csv_content, "text/csv")})

    # Second upload with same phone
    csv_content2 = "Name,Phone\nSecond,+919000000020\n"
    response = client.post("/upload", files={"file": ("leads.csv", csv_content2, "text/csv")})
    assert response.status_code == 200
    assert response.json()["skipped"] >= 1


def test_upload_reports_skipped_invalid_rows(client):
    csv_content = "Name,Phone\nValid,+919876543211\n,+919876543212\nAlso Valid,invalid-phone\n"
    response = client.post(
        "/upload",
        files={"file": ("leads.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["skipped"] >= 1


# ---------- Campaign ----------

def test_start_campaign_marks_pending_as_queued(client, db_session):
    lead = Lead(name="Priya", phone="+919988776655", status="pending")
    db_session.add(lead)
    db_session.commit()

    response = client.post("/start-campaign")
    assert response.status_code == 200
    data = response.json()
    assert "Queued" in data["message"]
    assert data["queued"] >= 1

    with Session(get_engine()) as session:
        refreshed = session.exec(select(Lead).where(Lead.name == "Priya")).first()
        assert refreshed is not None
        assert refreshed.status in {"queued", "calling", "failed"}


def test_start_campaign_no_pending_leads(client):
    response = client.post("/start-campaign")
    assert response.status_code == 200
    data = response.json()
    assert data["queued"] == 0


# ---------- Manager status ----------

def test_manager_status_endpoint(client):
    response = client.get("/manager-status")
    assert response.status_code == 200
    data = response.json()
    assert "connected" in data
    assert "join_code" in data
    assert "sandbox_number" in data


# ---------- Process lead ----------

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
        assert refreshed.updated_at is not None


def test_process_single_lead_marks_failed_with_reason(db_session, monkeypatch):
    lead = Lead(name="Error Lead", phone="+919900112233", status="queued")
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    async def fake_create_outbound_call(self, lead_obj):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("app.services.vapi.VapiService.create_outbound_call", fake_create_outbound_call)

    from app.config import get_settings

    assert lead.id is not None
    asyncio.run(process_single_lead(lead.id, get_settings()))

    with Session(get_engine()) as session:
        refreshed = session.exec(select(Lead).where(Lead.id == lead.id)).first()
        assert refreshed is not None
        assert refreshed.status == "failed"
        assert refreshed.summary is not None
        assert "provider unavailable" in refreshed.summary


def test_process_single_lead_nonexistent_id(db_session, monkeypatch):
    """Processing a non-existent lead should not raise."""
    from app.config import get_settings
    asyncio.run(process_single_lead(999999, get_settings()))


# ---------- Webhook ----------

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
    assert refreshed.updated_at is not None
    assert sent["count"] == 1


def test_webhook_ignores_non_terminal_event(client):
    payload = {"message": {"type": "status-update"}}
    response = client.post("/webhook/vapi", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


def test_webhook_rejects_missing_call_id(client):
    payload = {
        "message": {
            "type": "end-of-call-report",
            "call": {},
        }
    }
    response = client.post("/webhook/vapi", json=payload)
    assert response.status_code == 400


def test_webhook_handles_unknown_call_id(client):
    payload = {
        "message": {
            "type": "end-of-call-report",
            "call": {"id": "call-nonexistent"},
            "endedReason": "hangup",
            "artifact": {"transcript": "test"},
        }
    }
    response = client.post("/webhook/vapi", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "unknown_call"


def test_webhook_voicemail_status(client, db_session, monkeypatch):
    lead = Lead(name="VM Lead", phone="+919800000001", status="calling", call_id="call-vm")
    db_session.add(lead)
    db_session.commit()

    monkeypatch.setattr("app.services.twilio_service.TwilioService.send_hot_lead_summary", lambda *a, **kw: None)

    payload = {
        "message": {
            "type": "end-of-call-report",
            "endedReason": "voicemail",
            "call": {"id": "call-vm"},
            "artifact": {"transcript": "Left voicemail"},
            "analysis": {"summary": "Left voicemail message"},
        }
    }

    response = client.post("/webhook/vapi", json=payload)
    assert response.status_code == 200

    refreshed = db_session.exec(select(Lead).where(Lead.call_id == "call-vm")).first()
    assert refreshed is not None
    assert refreshed.status == "voicemail"


def test_webhook_duplicate_is_idempotent(client, db_session, monkeypatch):
    lead = Lead(name="Dup Lead", phone="+919811111111", status="calling", call_id="call-dup")
    db_session.add(lead)
    db_session.commit()

    sent = {"count": 0}

    def fake_send(self, lead_name, summary):
        sent["count"] += 1
        return "SM_DUP"

    monkeypatch.setattr("app.services.twilio_service.TwilioService.send_hot_lead_summary", fake_send)

    payload = {
        "message": {
            "type": "end-of-call-report",
            "endedReason": "hangup",
            "call": {"id": "call-dup"},
            "analysis": {"summary": "Customer interested in 2BHK in Bandra with 3 crore budget"},
            "artifact": {"transcript": "Customer interested in 2BHK in Bandra with 3 crore budget"},
        }
    }

    first = client.post("/webhook/vapi", json=payload)
    second = client.post("/webhook/vapi", json=payload)

    assert first.status_code == 200
    assert first.json()["status"] == "ok"
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate_ignored"
    assert sent["count"] == 1
