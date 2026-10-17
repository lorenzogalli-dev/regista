import os

import pytest
from fastapi.testclient import TestClient

from api import db
from api.main import app


def _client_with_db(ok: bool) -> TestClient:
    async def fake_ping() -> bool:
        return ok

    app.dependency_overrides[db.ping] = fake_ping
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_health_ok() -> None:
    with _client_with_db(True) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": "ok"}


def test_health_db_down() -> None:
    with _client_with_db(False) as client:
        r = client.get("/health")
    assert r.status_code == 503
    assert r.json()["db"] == "unreachable"


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")
def test_health_real_database() -> None:
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200, r.text
