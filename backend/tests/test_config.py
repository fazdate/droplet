"""Tests for app.config.Settings."""

import pytest

from app.config import Settings


def test_should_load_defaults_when_only_required_env_vars_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_PUBLIC_URL", raising=False)
    monkeypatch.setenv("AI_API_KEY", "ai-secret")
    monkeypatch.setenv("HA_BASE_URL", "http://ha.local:8123")
    monkeypatch.setenv("HA_LONG_LIVED_TOKEN", "ha-token")
    monkeypatch.setenv("HA_WEBHOOK_SECRET", "webhook-secret")

    settings = Settings()

    assert settings.ai_api_key == "ai-secret"
    assert settings.ha_base_url == "http://ha.local:8123"
    assert settings.ha_long_lived_token == "ha-token"
    assert settings.ha_webhook_secret == "webhook-secret"
    assert settings.ai_api_style == "openai"
    assert settings.ai_base_url == "https://api.openai.com/v1"
    assert settings.ai_model == "gpt-4.1-mini"
    assert settings.ai_diagnose_model == "gpt-4.1"
    assert settings.app_public_url == "http://localhost:8080"
    assert settings.db_path == "data/droplet.sqlite3"
    assert settings.photos_dir == "data/photos"
    assert settings.notify_targets == []
    assert settings.quiet_hours_start == 22
    assert settings.quiet_hours_end == 8
    assert settings.timezone == "UTC"
    assert settings.hemisphere == "northern"


def test_should_override_defaults_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_API_KEY", "x")
    monkeypatch.setenv("HA_BASE_URL", "http://ha.local")
    monkeypatch.setenv("HA_LONG_LIVED_TOKEN", "x")
    monkeypatch.setenv("HA_WEBHOOK_SECRET", "x")
    monkeypatch.setenv("AI_API_STYLE", "azure-openai")
    monkeypatch.setenv("AI_BASE_URL", "https://provider.example")
    monkeypatch.setenv("AI_MODEL", "vision-deployment")
    monkeypatch.setenv("AI_DIAGNOSE_MODEL", "diagnose-deployment")
    monkeypatch.setenv("AI_API_VERSION", "2024-12-01-preview")
    monkeypatch.setenv("APP_PUBLIC_URL", "http://droplet.local:8080")
    monkeypatch.setenv("NOTIFY_TARGETS", "mobile_app_phone1,mobile_app_phone2")
    monkeypatch.setenv("QUIET_HOURS_START", "23")
    monkeypatch.setenv("QUIET_HOURS_END", "7")
    monkeypatch.setenv("TIMEZONE", "Europe/Budapest")
    monkeypatch.setenv("HEMISPHERE", "southern")

    settings = Settings()

    assert settings.ai_api_style == "azure-openai"
    assert settings.ai_base_url == "https://provider.example"
    assert settings.ai_model == "vision-deployment"
    assert settings.ai_diagnose_model == "diagnose-deployment"
    assert settings.ai_api_version == "2024-12-01-preview"
    assert settings.app_public_url == "http://droplet.local:8080"
    assert settings.notify_targets == ["mobile_app_phone1", "mobile_app_phone2"]
    assert settings.quiet_hours_start == 23
    assert settings.quiet_hours_end == 7
    assert settings.timezone == "Europe/Budapest"
    assert settings.hemisphere == "southern"


def test_should_raise_when_required_secret_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.setenv("HA_BASE_URL", "http://ha.local")
    monkeypatch.setenv("HA_LONG_LIVED_TOKEN", "x")
    monkeypatch.setenv("HA_WEBHOOK_SECRET", "x")

    with pytest.raises(Exception):
        Settings()
