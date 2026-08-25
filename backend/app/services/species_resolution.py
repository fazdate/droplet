"""Species cache-or-create.

Reuses an existing non-manual Species row by scientific_name if present;
otherwise resolves care data (Perenual -> LLM -> defaults), a reference
image, and a common name (AI -> Perenual -> scientific_name fallback),
then creates+caches the row.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.ai import AiVisionClient
from app.clients.perenual import PerenualClient
from app.languages import DEFAULT_LANGUAGE, supported_language_codes
from app.models.orm import Species, SpeciesCareText, SpeciesCommonName
from app.services.care_resolution import CareData, CareText, resolve_care_data

LOG = logging.getLogger(__name__)


def _apply_care_text(species: Species, language: str, text: CareText) -> None:
    record = species.care_text_record_for(language)
    if record is None:
        record = SpeciesCareText(language=language)
        species.care_texts.append(record)

    if text.light is not None:
        record.light = text.light
    if text.soil is not None:
        record.soil = text.soil
    if text.notes is not None:
        record.notes = text.notes


def _apply_common_name(species: Species, language: str, common_name: str, *, snapshot: bool = False) -> None:
    record = species.common_name_record_for(language)
    if record is None:
        record = SpeciesCommonName(language=language, common_name=common_name)
        species.common_names.append(record)
    else:
        record.common_name = common_name

    if snapshot:
        species.common_name = common_name
        species.common_name_language = language


def _sync_legacy_snapshot(species: Species, care: CareData) -> None:
    species.light = care.light
    species.soil = care.soil
    species.notes = care.notes
    species.care_language = care.care_language


def _merge_care_data(species: Species, care: CareData) -> None:
    _sync_legacy_snapshot(species, care)
    for language, text in care.care_texts.items():
        _apply_care_text(species, language, text)


async def _resolve_common_name(
    scientific_name: str,
    *,
    ai_client,
    perenual_client,
    language: str = DEFAULT_LANGUAGE,
) -> str | None:
    """Attempts to resolve a common name for a species, trying multiple sources."""
    try:
        candidates = await ai_client.resolve_species_by_name(scientific_name, language=language)
        if candidates and candidates[0].common_name:
            return candidates[0].common_name
    except Exception:
        LOG.debug("AI common name resolution failed for %r", scientific_name, exc_info=True)

    if perenual_client is not None:
        try:
            matches = await perenual_client.search_species(scientific_name)
            if not isinstance(matches, list):
                matches = []
            if matches and matches[0].get("common_name"):
                return matches[0]["common_name"]
        except Exception:
            LOG.debug("Perenual common name lookup failed for %r", scientific_name, exc_info=True)

    return None


async def resolve_common_names(
    scientific_name: str,
    *,
    ai_client,
    perenual_client,
    language: str = DEFAULT_LANGUAGE,
    provided_common_name: str | None = None,
) -> dict[str, str]:
    common_names: dict[str, str] = {}
    if provided_common_name:
        common_names[language] = provided_common_name

    for candidate_language in supported_language_codes():
        if candidate_language in common_names:
            continue
        try:
            candidates = await ai_client.resolve_species_by_name(scientific_name, language=candidate_language)
        except Exception:
            LOG.debug(
                "AI common name resolution failed for %r (language=%s)", scientific_name, candidate_language, exc_info=True
            )
            candidates = []
        if not isinstance(candidates, list):
            candidates = []
        if candidates and candidates[0].common_name:
            common_names[candidate_language] = candidates[0].common_name

    if "en" not in common_names and perenual_client is not None:
        try:
            matches = await perenual_client.search_species(scientific_name)
            if not isinstance(matches, list):
                matches = []
            if matches and matches[0].get("common_name"):
                common_names["en"] = matches[0]["common_name"]
        except Exception:
            LOG.debug("Perenual common name lookup failed for %r", scientific_name, exc_info=True)

    return common_names


async def get_or_create_species(
    session: Session,
    *,
    scientific_name: str,
    common_name: str | None,
    perenual_client,
    ai_client,
    reference_image_fetcher: Callable[[str], Awaitable[str | None]],
    refresh_common_name: bool = False,
    language: str = DEFAULT_LANGUAGE,
) -> Species:
    existing = session.scalars(
        select(Species).where(Species.scientific_name == scientific_name, Species.source != "manual")
    ).first()
    if existing is not None:
        if refresh_common_name and common_name:
            _apply_common_name(existing, language, common_name, snapshot=True)
            session.flush()
        if refresh_common_name and existing.reference_image_url is None:
            existing.reference_image_url = await reference_image_fetcher(scientific_name)
            session.flush()

        missing_care_languages = [candidate for candidate in supported_language_codes() if not existing.has_care_text_for(candidate)]
        missing_common_languages = [candidate for candidate in supported_language_codes() if not existing.has_common_name_for(candidate)]
        if refresh_common_name and (missing_care_languages or missing_common_languages):
            care = await resolve_care_data(
                scientific_name, perenual_client=perenual_client, ai_client=ai_client, language=language
            )
            _merge_care_data(existing, care)
            common_names = await resolve_common_names(
                scientific_name,
                ai_client=ai_client,
                perenual_client=perenual_client,
                language=language,
                provided_common_name=common_name if refresh_common_name else None,
            )
            for common_language, value in common_names.items():
                _apply_common_name(existing, common_language, value)
            snapshot_common_name = common_names.get(language) or common_name or existing.common_name
            if snapshot_common_name is not None:
                existing.common_name = snapshot_common_name
                existing.common_name_language = language if common_name or language in common_names else existing.common_name_language
            session.flush()
        return existing

    care, reference_image_url = await asyncio.gather(
        resolve_care_data(scientific_name, perenual_client=perenual_client, ai_client=ai_client, language=language),
        reference_image_fetcher(scientific_name),
    )

    common_names = await resolve_common_names(
        scientific_name,
        ai_client=ai_client,
        perenual_client=perenual_client,
        language=language,
        provided_common_name=common_name,
    )
    final_common_name = common_names.get(language) or common_name or next(iter(common_names.values()), None)

    species = Species(
        scientific_name=scientific_name,
        common_name=final_common_name,
        common_name_language=language if final_common_name is not None else None,
        reference_image_url=reference_image_url,
        watering_interval_days=care.interval_days,
        seasonal_profile=care.seasonal_profile,
        light=care.light,
        soil=care.soil,
        notes=care.notes,
        source=care.source,
        care_language=care.care_language,
    )
    for language_code, text in care.care_texts.items():
        _apply_care_text(species, language_code, text)
    for common_language, value in common_names.items():
        _apply_common_name(species, common_language, value)
    if final_common_name is not None:
        species.common_name = final_common_name
        species.common_name_language = language

    session.add(species)
    session.flush()
    return species
