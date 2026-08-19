"""Tests for static frontend mounting in the FastAPI app factory."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def _settings(monkeypatch, tmp_path) -> Settings:
    monkeypatch.setenv("AI_API_KEY", "x")
    monkeypatch.setenv("HA_BASE_URL", "http://ha.local")
    monkeypatch.setenv("HA_LONG_LIVED_TOKEN", "x")
    monkeypatch.setenv("HA_WEBHOOK_SECRET", "x")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.sqlite3"))
    return Settings()


def test_should_serve_index_html_when_static_dir_configured(monkeypatch, tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html>Plants App</html>")

    settings = _settings(monkeypatch, tmp_path)
    app = create_app(settings=settings, static_dir=static_dir)
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Plants App" in response.text


def test_should_not_mount_static_when_dir_missing(monkeypatch, tmp_path) -> None:
    settings = _settings(monkeypatch, tmp_path)
    app = create_app(settings=settings, static_dir=tmp_path / "does-not-exist")
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200


def test_should_still_serve_api_routes_when_static_mounted(monkeypatch, tmp_path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html>Plants App</html>")

    settings = _settings(monkeypatch, tmp_path)
    app = create_app(settings=settings, static_dir=static_dir)
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
