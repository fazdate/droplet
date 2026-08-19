"""Shared pytest fixtures for API-level tests."""

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import create_db_engine, init_db
from app.main import create_app


@pytest.fixture
def settings(monkeypatch, tmp_path) -> Settings:
    monkeypatch.setenv("AI_API_KEY", "x")
    monkeypatch.setenv("HA_BASE_URL", "http://ha.local")
    monkeypatch.setenv("HA_LONG_LIVED_TOKEN", "x")
    monkeypatch.setenv("HA_WEBHOOK_SECRET", "x")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("PHOTOS_DIR", str(tmp_path / "photos"))
    return Settings()


@pytest.fixture
def engine(settings: Settings):
    eng = create_db_engine(f"sqlite:///{settings.db_path}")
    init_db(eng)
    return eng


@pytest.fixture
def client(settings: Settings, engine) -> TestClient:
    app = create_app(settings=settings, engine=engine)
    return TestClient(app)


@pytest.fixture
def frozen_now() -> dt.datetime:
    return dt.datetime(2026, 8, 17, 9, 0, tzinfo=dt.timezone.utc)
