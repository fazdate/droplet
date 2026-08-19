"""Application configuration loaded from environment variables / .env file."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.languages import DEFAULT_LANGUAGE, is_supported_language, supported_language_codes


class Settings(BaseSettings):
    """Central config. See ``.env.example`` for the full list of variables.

    Secrets (AI API key, HA long-lived token, HA webhook secret) are required
    and must never be committed; everything else has a sane default for a
    generic self-hosted deployment.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Secrets (required, no defaults) ---
    ai_api_key: str
    ha_base_url: str
    ha_long_lived_token: str
    ha_webhook_secret: str

    # --- AI species identification / diagnosis ---
    ai_api_style: str = "openai"
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4.1-mini"
    ai_api_version: str = "2024-10-21"
    # Diagnosing visible plant issues is less frequent and typically benefits
    # from a stronger model than routine identification.
    ai_diagnose_model: str = "gpt-4.1"
    # Empty by default: Perenual is optional (free-tier key the project owner
    # can add later); the care-data resolution chain falls back to the LLM and
    # category defaults when this is unset.
    perenual_api_key: str = ""

    # --- Deployment ---
    app_public_url: str = "http://localhost:8080"
    db_path: str = "data/droplet.sqlite3"
    photos_dir: str = "data/photos"

    # --- Notifications ---
    # Comma-separated list of HA notify targets, e.g. "mobile_app_phone1,mobile_app_phone2".
    # Kept as a raw string field (not list[str]) because pydantic-settings tries to
    # JSON-decode list-typed env vars before any validator runs.
    notify_targets_raw: str = Field(default="", alias="NOTIFY_TARGETS")
    quiet_hours_start: int = 22
    quiet_hours_end: int = 8
    # IANA timezone name (e.g. "Europe/Budapest") used to interpret
    # quiet_hours_start/end and the twice-daily escalation slots (09:00/18:00)
    # in the household's local time rather than UTC. Defaults to UTC so a
    # fresh deployment behaves predictably until the owner sets this.
    timezone: str = "UTC"

    # --- Seasonal cadence ---
    hemisphere: str = "northern"

    # --- Language ---
    # Static deployment setting (no in-app switcher): matches the language of
    # the phone(s) that receive push notifications via HA, and the language the
    # AI model is asked to use for plant names and care guidance. Supported
    # values are listed in app.languages.SUPPORTED_LANGUAGES.
    language: str = DEFAULT_LANGUAGE

    @property
    def notify_targets(self) -> list[str]:
        return [item.strip() for item in self.notify_targets_raw.split(",") if item.strip()]

    @staticmethod
    def _supported_language_error() -> ValueError:
        supported = ", ".join(supported_language_codes())
        return ValueError(f"LANGUAGE must be one of: {supported}")

    @field_validator("language")
    @classmethod
    def _validate_language(cls, value: str) -> str:
        if not is_supported_language(value):
            raise cls._supported_language_error()
        return value
