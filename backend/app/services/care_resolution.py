"""Layered watering-interval/care resolution.

Perenual benchmark -> model-derived answer -> category default map. The
per-plant manual override lives on the Plant row itself and is applied in
app.services.schedule, not here.
"""

import asyncio
import logging
from dataclasses import dataclass

from app.clients.perenual import CATEGORY_DEFAULT_DAYS
from app.languages import DEFAULT_LANGUAGE, supported_language_codes

LOG = logging.getLogger(__name__)

_DEFAULT_INTERVAL_DAYS = 7
_DEFAULT_SEASONAL_PROFILE = "temperate"


@dataclass(frozen=True)
class CareText:
    light: str | None
    soil: str | None
    notes: str | None


@dataclass(frozen=True)
class CareData:
    interval_days: int
    seasonal_profile: str
    light: str | None
    soil: str | None
    notes: str | None
    source: str  # perenual | llm | default
    care_language: str | None
    care_texts: dict[str, CareText]


def _has_text(text: CareText) -> bool:
    return any(value is not None for value in (text.light, text.soil, text.notes))


def _merge_texts(base: CareText | None, update: dict | None) -> CareText:
    return CareText(
        light=(update or {}).get("light") if (update or {}).get("light") is not None else (base.light if base else None),
        soil=(update or {}).get("soil") if (update or {}).get("soil") is not None else (base.soil if base else None),
        notes=(update or {}).get("notes") if (update or {}).get("notes") is not None else (base.notes if base else None),
    )


def _select_snapshot(language: str, care_texts: dict[str, CareText]) -> tuple[str | None, CareText | None]:
    if language in care_texts and _has_text(care_texts[language]):
        return language, care_texts[language]
    for candidate, text in care_texts.items():
        if candidate != language and _has_text(text):
            return candidate, text
    return None, None


async def _safe_describe_care(ai_client, species_name: str, language: str) -> dict | None:
    try:
        return await ai_client.describe_care(species_name, language=language)
    except Exception:
        LOG.info("AI care-data lookup failed for %r (language=%s)", species_name, language, exc_info=True)
        return None


async def resolve_care_data(
    species_name: str, *, perenual_client, ai_client, language: str = DEFAULT_LANGUAGE
) -> CareData:
    interval_days: int | None = None
    source: str | None = None
    perenual_light: str | None = None
    perenual_soil: str | None = None
    perenual_search_interval: int | None = None

    if perenual_client is not None:
        matches = await perenual_client.search_species(species_name)
        if isinstance(matches, list) and matches:
            perenual_search_interval = CATEGORY_DEFAULT_DAYS.get(matches[0].get("watering"))
            details = await perenual_client.get_care_details(matches[0]["id"])
            if details is not None and details.interval_days is not None:
                interval_days = details.interval_days
                source = "perenual"
                perenual_light = details.light
                perenual_soil = details.soil
            elif perenual_search_interval is not None:
                interval_days = perenual_search_interval
                source = "perenual"

    care_texts: dict[str, CareText] = {}
    ai_results = await asyncio.gather(
        *(_safe_describe_care(ai_client, species_name, candidate) for candidate in supported_language_codes())
    )

    for candidate_language, ai_result in zip(supported_language_codes(), ai_results, strict=False):
        text = CareText(light=None, soil=None, notes=None)
        if candidate_language == DEFAULT_LANGUAGE:
            text = CareText(light=perenual_light, soil=perenual_soil, notes=None)
        if ai_result is not None:
            text = _merge_texts(text, ai_result)
            llm_interval = ai_result.get("watering_interval_days")
            if interval_days is None and llm_interval is not None:
                interval_days = llm_interval
                source = "llm"
        if _has_text(text):
            care_texts[candidate_language] = text

    current_language, snapshot = _select_snapshot(language, care_texts)
    if snapshot is None:
        current_language = None
        snapshot = CareText(light=None, soil=None, notes=None)

    if interval_days is None:
        interval_days = _DEFAULT_INTERVAL_DAYS
        source = "default"

    seasonal_profile = _DEFAULT_SEASONAL_PROFILE
    for candidate in ai_results:
        if candidate is not None and candidate.get("seasonal_profile") is not None:
            seasonal_profile = candidate["seasonal_profile"]
            if seasonal_profile != _DEFAULT_SEASONAL_PROFILE:
                break

    return CareData(
        interval_days=interval_days,
        seasonal_profile=seasonal_profile,
        light=snapshot.light,
        soil=snapshot.soil,
        notes=snapshot.notes,
        source=source or "default",
        care_language=current_language,
        care_texts=care_texts,
    )
