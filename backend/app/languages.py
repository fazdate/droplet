"""Supported deployment languages and shared helpers."""

from typing import Final

DEFAULT_LANGUAGE: Final[str] = "en"

SUPPORTED_LANGUAGES: Final[dict[str, str]] = {
    "en": "English",
    "hu": "Hungarian",
}


def supported_language_codes() -> tuple[str, ...]:
    return tuple(SUPPORTED_LANGUAGES)


def is_supported_language(language: str) -> bool:
    return language in SUPPORTED_LANGUAGES


def language_name(language: str) -> str:
    return SUPPORTED_LANGUAGES.get(language, SUPPORTED_LANGUAGES[DEFAULT_LANGUAGE])
