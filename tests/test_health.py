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


def test_front_end_routes_fall_back_to_the_app_shell_but_api_stays_404(
    tmp_path, monkeypatch
) -> None:
    import importlib

    import api.main

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>app</title>")
    monkeypatch.setenv("WEB_DIST", str(dist))
    main = importlib.reload(api.main)
    client = TestClient(main.app)
    assert "app" in client.get("/broadcast").text
    assert client.get("/control?run=x").status_code == 200
    assert client.get("/api/nope").status_code == 404
    assert client.get("/api/matches/..%2Fx").status_code == 404
    monkeypatch.delenv("WEB_DIST")
    importlib.reload(api.main)
