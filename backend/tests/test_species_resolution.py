"""Tests for app.services.species_resolution.get_or_create_species."""

from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.clients.ai import AiVisionClient
from app.clients.perenual import PerenualCareDetails, PerenualClient
from app.models.orm import Base, Species
from app.services.species_resolution import get_or_create_species


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


async def test_should_create_new_species_with_resolved_care_data() -> None:
    with _session() as session:
        perenual = MagicMock(spec=PerenualClient)
        perenual.search_species.return_value = [{"id": 1, "scientific_name": "Monstera deliciosa", "watering": "average"}]
        perenual.get_care_details.return_value = PerenualCareDetails(interval_days=8, light=None, soil=None)
        ai = MagicMock(spec=AiVisionClient)
        ai.describe_care = AsyncMock(
            side_effect=[
                {
                    "watering_interval_days": 7,
                    "light": "bright indirect",
                    "soil": "well-draining",
                    "notes": "Likes humidity.",
                    "seasonal_profile": "tropical",
                },
                {
                    "watering_interval_days": 7,
                    "light": "fényes, közvetett fény",
                    "soil": "jól áteresztő talaj",
                    "notes": "Szereti a párát.",
                    "seasonal_profile": "tropical",
                },
            ]
        )

        species = await get_or_create_species(
            session,
            scientific_name="Monstera deliciosa",
            common_name="Swiss cheese plant",
            perenual_client=perenual,
            ai_client=ai,
            reference_image_fetcher=AsyncMock(return_value="https://example.com/img.jpg"),
        )

        assert species.id is not None
        assert species.watering_interval_days == 8
        assert species.source == "perenual"
        assert species.reference_image_url == "https://example.com/img.jpg"
        assert species.care_text_record_for("en") is not None
        assert species.care_text_record_for("hu") is not None
        assert session.query(Species).count() == 1


async def test_should_reuse_cached_non_manual_species_without_calling_external_apis() -> None:
    with _session() as session:
        session.add(Species(scientific_name="Monstera deliciosa", watering_interval_days=7, source="perenual"))
        session.commit()
        perenual = MagicMock(spec=PerenualClient)
        ai = MagicMock(spec=AiVisionClient)
        ai.describe_care = AsyncMock(return_value={})

        species = await get_or_create_species(
            session,
            scientific_name="Monstera deliciosa",
            common_name=None,
            perenual_client=perenual,
            ai_client=ai,
            reference_image_fetcher=AsyncMock(),
        )

        assert session.query(Species).count() == 1
        perenual.search_species.assert_not_called()
        ai.describe_care.assert_not_called()
        assert species.scientific_name == "Monstera deliciosa"


async def test_should_not_reuse_manual_species_for_ai_identification() -> None:
    with _session() as session:
        session.add(Species(scientific_name="Monstera deliciosa", watering_interval_days=99, source="manual"))
        session.commit()
        perenual = MagicMock(spec=PerenualClient)
        perenual.search_species.return_value = []
        ai = MagicMock(spec=AiVisionClient)
        ai.describe_care = AsyncMock(return_value={"watering_interval_days": 7, "seasonal_profile": "tropical"})

        species = await get_or_create_species(
            session,
            scientific_name="Monstera deliciosa",
            common_name="Swiss cheese plant",
            perenual_client=perenual,
            ai_client=ai,
            reference_image_fetcher=AsyncMock(return_value=None),
        )

        assert session.query(Species).count() == 2
        assert species.source == "llm"


async def test_should_retry_reference_image_for_cached_species_missing_one_when_refreshing() -> None:
    with _session() as session:
        session.add(
            Species(scientific_name="Monstera deliciosa", watering_interval_days=7, source="llm", reference_image_url=None)
        )
        session.commit()
        fetcher = AsyncMock(return_value="https://example.com/monstera.jpg")
        ai = MagicMock(spec=AiVisionClient)
        ai.describe_care = AsyncMock(return_value={})

        species = await get_or_create_species(
            session,
            scientific_name="Monstera deliciosa",
            common_name="Swiss cheese plant",
            perenual_client=MagicMock(spec=PerenualClient),
            ai_client=ai,
            reference_image_fetcher=fetcher,
            refresh_common_name=True,
        )

        fetcher.assert_called_once_with("Monstera deliciosa")
        assert species.reference_image_url == "https://example.com/monstera.jpg"


async def test_should_not_retry_reference_image_when_not_refreshing() -> None:
    with _session() as session:
        session.add(
            Species(scientific_name="Monstera deliciosa", watering_interval_days=7, source="llm", reference_image_url=None)
        )
        session.commit()
        fetcher = AsyncMock(return_value="https://example.com/monstera.jpg")
        ai = MagicMock(spec=AiVisionClient)
        ai.describe_care = AsyncMock(return_value={})

        species = await get_or_create_species(
            session,
            scientific_name="Monstera deliciosa",
            common_name=None,
            perenual_client=MagicMock(spec=PerenualClient),
            ai_client=ai,
            reference_image_fetcher=fetcher,
        )

        fetcher.assert_not_called()
        assert species.reference_image_url is None


async def test_should_not_refetch_reference_image_when_already_present() -> None:
    with _session() as session:
        session.add(
            Species(
                scientific_name="Monstera deliciosa",
                watering_interval_days=7,
                source="llm",
                reference_image_url="https://example.com/existing.jpg",
            )
        )
        session.commit()
        fetcher = AsyncMock(return_value="https://example.com/new.jpg")
        ai = MagicMock(spec=AiVisionClient)
        ai.describe_care = AsyncMock(return_value={})

        species = await get_or_create_species(
            session,
            scientific_name="Monstera deliciosa",
            common_name=None,
            perenual_client=MagicMock(spec=PerenualClient),
            ai_client=ai,
            reference_image_fetcher=fetcher,
            refresh_common_name=True,
        )

        fetcher.assert_not_called()
        assert species.reference_image_url == "https://example.com/existing.jpg"


async def test_should_refresh_care_text_on_language_mismatch_when_refreshing() -> None:
    with _session() as session:
        session.add(
            Species(
                scientific_name="Monstera deliciosa",
                watering_interval_days=7,
                source="perenual",
                light="bright indirect",
                soil="well-draining",
                care_language="en",
            )
        )
        session.commit()
        ai = MagicMock(spec=AiVisionClient)
        ai.describe_care = AsyncMock(
            side_effect=[
                {"light": "bright indirect", "soil": "well-draining", "notes": "Likes humidity."},
                {"light": "fényes, közvetett fény", "soil": "jól áteresztő talaj", "notes": "Szereti a párát."},
            ]
        )

        species = await get_or_create_species(
            session,
            scientific_name="Monstera deliciosa",
            common_name=None,
            perenual_client=MagicMock(spec=PerenualClient),
            ai_client=ai,
            reference_image_fetcher=AsyncMock(return_value=None),
            refresh_common_name=True,
            language="hu",
        )

        assert ai.describe_care.call_count == 2
        assert species.light == "fényes, közvetett fény"
        assert species.soil == "jól áteresztő talaj"
        assert species.notes == "Szereti a párát."
        assert species.care_language == "hu"
        assert species.watering_interval_days == 7
        assert species.source == "perenual"
        assert species.care_text_record_for("en") is not None
        assert species.care_text_record_for("hu") is not None


async def test_should_refresh_care_text_when_language_unchanged_but_secondary_language_is_missing() -> None:
    with _session() as session:
        session.add(
            Species(
                scientific_name="Monstera deliciosa",
                watering_interval_days=7,
                source="perenual",
                light="bright indirect",
                care_language="en",
            )
        )
        session.commit()
        ai = MagicMock(spec=AiVisionClient)
        ai.describe_care = AsyncMock(return_value={"light": "bright indirect"})

        species = await get_or_create_species(
            session,
            scientific_name="Monstera deliciosa",
            common_name=None,
            perenual_client=MagicMock(spec=PerenualClient),
            ai_client=ai,
            reference_image_fetcher=AsyncMock(return_value=None),
            refresh_common_name=True,
            language="en",
        )

        assert ai.describe_care.call_count == 2
        assert species.care_text_record_for("hu") is not None


async def test_should_refresh_legacy_care_text_with_no_care_language_recorded() -> None:
    with _session() as session:
        session.add(
            Species(
                scientific_name="Monstera deliciosa",
                watering_interval_days=7,
                source="perenual",
                light="bright indirect",
                soil="well-draining",
                notes="Likes humidity.",
                care_language=None,
            )
        )
        session.commit()
        ai = MagicMock(spec=AiVisionClient)
        ai.describe_care = AsyncMock(
            side_effect=[
                {"light": "bright indirect", "soil": "well-draining", "notes": "Likes humidity."},
                {"light": "fényes, közvetett fény", "soil": "jól áteresztő talaj", "notes": "Szereti a párát."},
            ]
        )

        species = await get_or_create_species(
            session,
            scientific_name="Monstera deliciosa",
            common_name=None,
            perenual_client=MagicMock(spec=PerenualClient),
            ai_client=ai,
            reference_image_fetcher=AsyncMock(return_value=None),
            refresh_common_name=True,
            language="hu",
        )

        assert ai.describe_care.call_count == 2
        assert species.light == "fényes, közvetett fény"
        assert species.care_language == "hu"
        assert species.care_text_record_for("en") is not None
        assert species.care_text_record_for("hu") is not None


async def test_should_refresh_care_text_even_when_no_text_was_cached_yet() -> None:
    with _session() as session:
        session.add(Species(scientific_name="Monstera deliciosa", watering_interval_days=7, source="perenual", care_language=None))
        session.commit()
        ai = MagicMock(spec=AiVisionClient)
        ai.describe_care = AsyncMock(
            side_effect=[
                {"light": "bright indirect", "soil": "well-draining", "notes": "Likes humidity."},
                {"light": "fényes, közvetett fény", "soil": "jól áteresztő talaj", "notes": "Szereti a párát."},
            ]
        )

        species = await get_or_create_species(
            session,
            scientific_name="Monstera deliciosa",
            common_name=None,
            perenual_client=MagicMock(spec=PerenualClient),
            ai_client=ai,
            reference_image_fetcher=AsyncMock(return_value=None),
            refresh_common_name=True,
            language="hu",
        )

        assert ai.describe_care.call_count == 2
        assert species.care_text_record_for("en") is not None
        assert species.care_text_record_for("hu") is not None
