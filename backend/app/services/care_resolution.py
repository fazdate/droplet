"""Layered watering-interval/care resolution.

Perenual benchmark -> model-derived answer -> category default map. The
per-plant manual override lives on the Plant row itself and is applied in
app.services.schedule, not here.
"""

import logging
from dataclasses import dataclass

from app.clients.perenual import CATEGORY_DEFAULT_DAYS
from app.languages import DEFAULT_LANGUAGE

LOG = logging.getLogger(__name__)

_DEFAULT_INTERVAL_DAYS = 7
_DEFAULT_SEASONAL_PROFILE = "temperate"


@dataclass(frozen=True)
class CareData:
    interval_days: int
    seasonal_profile: str
    light: str | None
    soil: str | None
    notes: str | None
    source: str  # perenual | llm | default
    # Language light/soil/notes are written in, or None if none of them were
    # resolved (nothing to display/refresh either way).
    care_language: str | None


async def resolve_care_data(species_name: str, *, perenual_client, ai_client, language: str = DEFAULT_LANGUAGE) -> CareData:
    interval_days: int | None = None
    source: str | None = None
    light: str | None = None
    soil: str | None = None
    perenual_search_interval: int | None = None

    if perenual_client is not None:
        matches = await perenual_client.search_species(species_name)
        if matches:
            perenual_search_interval = CATEGORY_DEFAULT_DAYS.get(matches[0].get("watering"))
            details = await perenual_client.get_care_details(matches[0]["id"])
            if details is not None and details.interval_days is not None:
                interval_days = details.interval_days
                source = "perenual"
                # Perenual has no language parameter — its light/soil text is
                # always English, so it's only safe to use as-is for an
                # English deployment. Non-English deployments still need the
                # model below for localized text, even though the interval
                # itself is already resolved from Perenual.
                if language == DEFAULT_LANGUAGE:
                    light = details.light
                    soil = details.soil
            elif perenual_search_interval is not None:
                interval_days = perenual_search_interval
                source = "perenual"

    notes: str | None = None
    seasonal_profile = _DEFAULT_SEASONAL_PROFILE
    if interval_days is None or language != DEFAULT_LANGUAGE:
        try:
            care = await ai_client.describe_care(species_name, language=language)
        except Exception:
            LOG.info("AI care-data lookup failed for %r", species_name, exc_info=True)
            care = None
        if care is not None:
            llm_interval = care.get("watering_interval_days")
            if interval_days is None and llm_interval is not None:
                interval_days = llm_interval
                source = "llm"
            if light is None:
                light = care.get("light")
            if soil is None:
                soil = care.get("soil")
            notes = care.get("notes")
            seasonal_profile = care.get("seasonal_profile", _DEFAULT_SEASONAL_PROFILE)

    care_language = language if any(value is not None for value in (light, soil, notes)) else None

    if interval_days is None:
        interval_days = _DEFAULT_INTERVAL_DAYS
        source = "default"

    return CareData(
        interval_days=interval_days,
        seasonal_profile=seasonal_profile,
        light=light,
        soil=soil,
        notes=notes,
        source=source or "default",
        care_language=care_language,
    )
