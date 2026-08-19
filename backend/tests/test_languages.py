"""Tests for the shared backend language registry."""

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.languages import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, language_name, supported_language_codes


def test_should_expose_supported_language_codes() -> None:
    assert DEFAULT_LANGUAGE == "en"
    assert supported_language_codes() == ("en", "hu")
    assert SUPPORTED_LANGUAGES["hu"] == "Hungarian"


def test_should_fall_back_to_english_for_unknown_language_name() -> None:
    assert language_name("de") == "English"


def test_should_reject_unknown_language_when_loading_settings(monkeypatch) -> None:
    monkeypatch.setenv("AI_API_KEY", "x")
    monkeypatch.setenv("HA_BASE_URL", "http://ha.local")
    monkeypatch.setenv("HA_LONG_LIVED_TOKEN", "x")
    monkeypatch.setenv("HA_WEBHOOK_SECRET", "x")
    monkeypatch.setenv("LANGUAGE", "de")

    with pytest.raises(ValidationError, match="LANGUAGE must be one of"):
        Settings()
