"""Tests for the FastAPI app factory and health endpoint."""

import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import create_app
from app.services.settings_store import set_last_notification_error


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("AI_API_KEY", "x")
    monkeypatch.setenv("HA_BASE_URL", "http://ha.local")
    monkeypatch.setenv("HA_LONG_LIVED_TOKEN", "x")
    monkeypatch.setenv("HA_WEBHOOK_SECRET", "x")
    return TestClient(create_app())


def test_should_return_ok_status_on_health_check(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "last_notification_error": None,
        "last_notification_error_at": None,
    }


def test_should_surface_last_notification_error_on_health_check(settings, engine, client) -> None:
    at = dt.datetime(2026, 8, 18, 9, 0, tzinfo=dt.timezone.utc)

    with Session(engine) as session:
        set_last_notification_error(session, message="401 Client Error: Unauthorized", at=at)
        session.commit()

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "last_notification_error": "401 Client Error: Unauthorized",
        "last_notification_error_at": at.isoformat(),
    }
