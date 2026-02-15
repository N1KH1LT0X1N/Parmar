import os
import time
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session


@pytest.fixture(scope="session")
def app(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "test.db"

    os.environ["DATABASE_URL"] = f"sqlite:///{db_file.as_posix()}"
    os.environ["VAPI_API_KEY"] = "test-key"
    os.environ["VAPI_ASSISTANT_ID"] = "assistant-id"
    os.environ["VAPI_PHONE_NUMBER_ID"] = "phone-number-id"
    os.environ["TWILIO_FROM_NUMBER"] = "whatsapp:+14155238886"
    os.environ["MANAGER_PHONE_NUMBER"] = "whatsapp:+919999999999"
    os.environ["MANAGER_JOIN_CODE"] = "join demo-room"
    os.environ["MAX_CONCURRENT_CALLS"] = "1"

    from app.config import get_settings
    from app.database import get_engine

    get_settings.cache_clear()
    get_engine.cache_clear()

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
