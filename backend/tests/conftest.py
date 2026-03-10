import os
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlmodel import Session


@pytest.fixture
def app(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[2]
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("VAPI_API_KEY", "test-key")
    monkeypatch.setenv("VAPI_ASSISTANT_ID", "assistant-id")
    monkeypatch.setenv("VAPI_PHONE_NUMBER_ID", "phone-number-id")
    monkeypatch.setenv("VAPI_PREFLIGHT_REQUIRED_FOR_CAMPAIGN", "false")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "whatsapp:+14155238886")
    monkeypatch.setenv("MANAGER_PHONE_NUMBER", "whatsapp:+919999999999")
    monkeypatch.setenv("MANAGER_JOIN_CODE", "join demo-room")
    monkeypatch.setenv("MAX_CONCURRENT_CALLS", "1")

    from app.config import get_settings
    from app.database import get_engine

    get_settings.cache_clear()
    get_engine.cache_clear()

    alembic_config = Config(str(repo_root / "backend" / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(repo_root / "backend" / "alembic"))
    command.upgrade(alembic_config, "head")

    from app.main import create_app

    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    from app.database import get_engine

    with Session(get_engine()) as session:
        yield session


@pytest.fixture
def wait_for():
    def _wait_for(check: Callable[[], bool], timeout_seconds: float = 2.5):
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if check():
                return True
            time.sleep(0.05)
        return False

    return _wait_for
