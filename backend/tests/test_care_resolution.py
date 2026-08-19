"""Tests for app.services.care_resolution."""

from unittest.mock import MagicMock

from app.clients.ai import AiVisionClient
from app.clients.perenual import PerenualCareDetails, PerenualClient
from app.services.care_resolution import resolve_care_data


async def test_should_prefer_perenual_when_species_found_and_interval_available() -> None:
    perenual = MagicMock(spec=PerenualClient)
    perenual.search_species.return_value = [{"id": 1, "scientific_name": "Monstera deliciosa", "watering": "average"}]
    perenual.get_care_details.return_value = PerenualCareDetails(interval_days=8, light=None, soil=None)
    ai = MagicMock(spec=AiVisionClient)

    result = await resolve_care_data("Monstera deliciosa", perenual_client=perenual, ai_client=ai)

    assert result.interval_days == 8
    assert result.source == "perenual"
    ai.describe_care.assert_not_called()


async def test_should_use_perenual_sunlight_and_soil_for_english_deployment() -> None:
    perenual = MagicMock(spec=PerenualClient)
    perenual.search_species.return_value = [{"id": 1, "scientific_name": "Monstera deliciosa", "watering": "average"}]
    perenual.get_care_details.return_value = PerenualCareDetails(
        interval_days=8, light="bright indirect", soil="well-draining"
    )
    ai = MagicMock(spec=AiVisionClient)

    result = await resolve_care_data("Monstera deliciosa", perenual_client=perenual, ai_client=ai, language="en")

    assert result.light == "bright indirect"
    assert result.soil == "well-draining"
    assert result.care_language == "en"
    ai.describe_care.assert_not_called()


async def test_should_fall_back_to_ai_when_perenual_has_no_match() -> None:
    perenual = MagicMock(spec=PerenualClient)
    perenual.search_species.return_value = []
    ai = MagicMock(spec=AiVisionClient)
    ai.describe_care.return_value = {
        "watering_interval_days": 10,
        "light": "low",
        "soil": "peat",
        "notes": "hardy",
        "seasonal_profile": "succulent",
    }

    result = await resolve_care_data("My rare plant", perenual_client=perenual, ai_client=ai)

    assert result.interval_days == 10
    assert result.source == "llm"
    assert result.seasonal_profile == "succulent"
    assert result.light == "low"


async def test_should_keep_perenual_search_interval_when_details_are_missing() -> None:
    perenual = MagicMock(spec=PerenualClient)
    perenual.search_species.return_value = [{"id": 1, "scientific_name": "X", "watering": "average"}]
    perenual.get_care_details.return_value = PerenualCareDetails(interval_days=None, light=None, soil=None)
    ai = MagicMock(spec=AiVisionClient)

    result = await resolve_care_data("X", perenual_client=perenual, ai_client=ai)

    assert result.interval_days == 7
    assert result.source == "perenual"
    ai.describe_care.assert_not_called()


async def test_should_fall_back_to_default_when_ai_also_fails() -> None:
    perenual = MagicMock(spec=PerenualClient)
    perenual.search_species.return_value = []
    ai = MagicMock(spec=AiVisionClient)
    ai.describe_care.side_effect = Exception("provider down")

    result = await resolve_care_data("Mystery plant", perenual_client=perenual, ai_client=ai)

    assert result.interval_days == 7
    assert result.source == "default"
    assert result.seasonal_profile == "temperate"
    assert result.care_language is None


async def test_should_skip_perenual_when_client_disabled() -> None:
    ai = MagicMock(spec=AiVisionClient)
    ai.describe_care.return_value = {"watering_interval_days": 5, "seasonal_profile": "tropical"}

    result = await resolve_care_data("X", perenual_client=None, ai_client=ai)

    assert result.source == "llm"
    assert result.interval_days == 5


async def test_should_ask_ai_for_localized_care_text_even_when_perenual_has_the_interval() -> None:
    perenual = MagicMock(spec=PerenualClient)
    perenual.search_species.return_value = [{"id": 1, "scientific_name": "Monstera deliciosa", "watering": "average"}]
    perenual.get_care_details.return_value = PerenualCareDetails(
        interval_days=8, light="bright indirect", soil="well-draining"
    )
    ai = MagicMock(spec=AiVisionClient)
    ai.describe_care.return_value = {
        "light": "fényes, közvetett fény",
        "soil": "jól áteresztő talaj",
        "notes": "Szereti a párát.",
        "seasonal_profile": "tropical",
    }

    result = await resolve_care_data("Monstera deliciosa", perenual_client=perenual, ai_client=ai, language="hu")

    ai.describe_care.assert_called_once_with("Monstera deliciosa", language="hu")
    assert result.interval_days == 8
    assert result.source == "perenual"
    assert result.light == "fényes, közvetett fény"
    assert result.soil == "jól áteresztő talaj"
    assert result.notes == "Szereti a párát."
    assert result.care_language == "hu"


async def test_should_report_no_care_language_when_no_free_text_resolved() -> None:
    perenual = MagicMock(spec=PerenualClient)
    perenual.search_species.return_value = [{"id": 1, "scientific_name": "X", "watering": "average"}]
    perenual.get_care_details.return_value = PerenualCareDetails(interval_days=8, light=None, soil=None)
    ai = MagicMock(spec=AiVisionClient)

    result = await resolve_care_data("X", perenual_client=perenual, ai_client=ai, language="en")

    assert result.light is None
    assert result.soil is None
    assert result.care_language is None
