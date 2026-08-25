"""Tests for scripts.backfill_care_language."""

from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.orm import Session

from app.clients.ai import AiVisionClient
from app.config import Settings
from app.db import create_db_engine, init_db
from app.models.orm import Species, SpeciesCareText, SpeciesCommonName
from scripts.backfill_care_language import backfill


def _seed_species(engine, **overrides) -> None:
    with Session(engine) as session:
        session.add(
            Species(
                scientific_name=overrides.pop("scientific_name", "Monstera deliciosa"),
                watering_interval_days=overrides.pop("watering_interval_days", 7),
                source=overrides.pop("source", "perenual"),
                **overrides,
            )
        )
        session.commit()


def _settings(monkeypatch, tmp_path, *, language: str = "hu") -> Settings:
    monkeypatch.setenv("AI_API_KEY", "x")
    monkeypatch.setenv("HA_BASE_URL", "http://ha.local")
    monkeypatch.setenv("HA_LONG_LIVED_TOKEN", "x")
    monkeypatch.setenv("HA_WEBHOOK_SECRET", "x")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("PHOTOS_DIR", str(tmp_path / "photos"))
    monkeypatch.setenv("LANGUAGE", language)
    return Settings()


async def test_should_refresh_legacy_species_with_text_but_no_care_language(monkeypatch, tmp_path) -> None:
    settings = _settings(monkeypatch, tmp_path)
    engine = create_db_engine(f"sqlite:///{settings.db_path}")
    init_db(engine)
    _seed_species(engine, light="bright indirect", soil="well-draining", notes="Likes humidity.", care_language=None)
    ai = MagicMock(spec=AiVisionClient)
    ai.describe_care = AsyncMock(
        side_effect=[
            {"light": "bright indirect", "soil": "well-draining", "notes": "Likes humidity."},
            {"light": "fényes, közvetett fény", "soil": "jól áteresztő talaj", "notes": "Szereti a párát."},
        ]
    )

    updated = await backfill(db_path=settings.db_path, settings=settings, ai_client=ai)

    assert updated == ["Monstera deliciosa"]
    assert ai.describe_care.call_count == 2
    with Session(engine) as session:
        species = session.query(Species).one()
        assert species.light == "fényes, közvetett fény"
        assert species.care_language == "hu"
        assert species.care_text_for("en") == ("bright indirect", "well-draining", "Likes humidity.")
        assert species.care_text_for("hu") == ("fényes, közvetett fény", "jól áteresztő talaj", "Szereti a párát.")


async def test_should_skip_species_already_cached_in_both_languages(monkeypatch, tmp_path) -> None:
    settings = _settings(monkeypatch, tmp_path, language="en")
    engine = create_db_engine(f"sqlite:///{settings.db_path}")
    init_db(engine)
    with Session(engine) as session:
        species = Species(
            scientific_name="Monstera deliciosa",
            watering_interval_days=7,
            source="perenual",
            care_language="en",
            common_name="Swiss cheese plant",
            common_name_language="en",
        )
        species.care_texts.extend(
            [
                SpeciesCareText(language="en", light="bright indirect"),
                SpeciesCareText(language="hu", light="fényes, közvetett fény"),
            ]
        )
        species.common_names.extend(
            [
                SpeciesCommonName(language="en", common_name="Swiss cheese plant"),
                SpeciesCommonName(language="hu", common_name="Szörnyeteg növény"),
            ]
        )
        session.add(species)
        session.commit()
    ai = MagicMock(spec=AiVisionClient)
    ai.describe_care = AsyncMock()

    updated = await backfill(db_path=settings.db_path, settings=settings, ai_client=ai)

    assert updated == []
    ai.describe_care.assert_not_called()


async def test_should_skip_species_with_no_care_text_at_all(monkeypatch, tmp_path) -> None:
    settings = _settings(monkeypatch, tmp_path)
    engine = create_db_engine(f"sqlite:///{settings.db_path}")
    init_db(engine)
    _seed_species(engine, care_language=None)
    ai = MagicMock(spec=AiVisionClient)
    ai.describe_care = AsyncMock(
        side_effect=[
            {"light": "bright indirect", "soil": "well-draining"},
            {"light": "fényes, közvetett fény", "soil": "jól áteresztő talaj"},
        ]
    )

    updated = await backfill(db_path=settings.db_path, settings=settings, ai_client=ai)

    assert updated == ["Monstera deliciosa"]
    assert ai.describe_care.call_count == 2


async def test_dry_run_should_not_persist_changes(monkeypatch, tmp_path) -> None:
    settings = _settings(monkeypatch, tmp_path)
    engine = create_db_engine(f"sqlite:///{settings.db_path}")
    init_db(engine)
    _seed_species(engine, light="bright indirect", care_language=None)
    ai = MagicMock(spec=AiVisionClient)
    ai.describe_care = AsyncMock(
        side_effect=[
            {"light": "bright indirect"},
            {"light": "fényes, közvetett fény"},
        ]
    )

    updated = await backfill(db_path=settings.db_path, settings=settings, ai_client=ai, dry_run=True)

    assert updated == ["Monstera deliciosa"]
    with Session(engine) as session:
        species = session.query(Species).one()
        assert species.light == "bright indirect"
        assert species.care_language is None
