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

from app.models.orm import Species
from app.languages import DEFAULT_LANGUAGE
from app.services.care_resolution import resolve_care_data

LOG = logging.getLogger(__name__)


async def _resolve_common_name(
    scientific_name: str,
    *,
    ai_client,
    perenual_client,
    language: str = DEFAULT_LANGUAGE,
) -> str | None:
    """Attempts to resolve a common name for a species, trying multiple sources.
    
    Returns None if no common name can be resolved, leaving the caller to decide
    whether to use the scientific name as a fallback.
    """
    # First try: ask the AI provider to resolve the species name and get its common name
    try:
        candidates = await ai_client.resolve_species_by_name(scientific_name, language=language)
        if candidates and candidates[0].common_name:
            return candidates[0].common_name
    except Exception:
        LOG.debug("AI common name resolution failed for %r", scientific_name, exc_info=True)

    # Second try: search Perenual for the scientific name
    if perenual_client is not None:
        try:
            matches = await perenual_client.search_species(scientific_name)
            if matches and matches[0].get("common_name"):
                return matches[0]["common_name"]
        except Exception:
            LOG.debug("Perenual common name lookup failed for %r", scientific_name, exc_info=True)

    return None


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
        # The numeric interval/seasonal_profile stay cached regardless of
        # language (they're language-independent), but callers that pass
        # ``refresh_common_name=True`` (i.e. the photo-identify flow, where
        # the AI provider is re-asked for the name in the currently configured
        # language every time — see AiVisionClient.identify_species) get the
        # display name kept in sync too. Without this, a species first
        # resolved under one Settings.language would keep showing that
        # language's name forever, even after the deployment's language
        # setting changes. Text-search hits (Perenual, always English) never
        # refresh an existing row so a search in the "wrong" language can't
        # clobber an already-translated name.
        if refresh_common_name and common_name and existing.common_name != common_name:
            existing.common_name = common_name
            session.flush()
        # A reference image can be missing simply because the lookup failed
        # transiently, or because the exact name resolved at creation time
        # (e.g. a cultivar string like "... 'Neon Robusta'") didn't have its
        # own Wikipedia page. Retry on every re-identify rather than leaving
        # the species without an illustration forever.
        if refresh_common_name and existing.reference_image_url is None:
            existing.reference_image_url = await reference_image_fetcher(scientific_name)
            session.flush()
        # Unlike the interval, light/soil/notes are free text and thus
        # language-dependent — re-resolve them on the next re-identify when
        # they were resolved under a different Settings.language than the one
        # now configured, same rationale as the common_name refresh above.
        # care_language is None both for genuinely-unresolved species (nothing
        # to refresh — retrying that on every re-identify would multiply AI
        # calls for good) and for rows created before this column existed,
        # which nonetheless already carry real (always-English, since the old
        # describe_care had no language parameter) text — those must still be
        # treated as DEFAULT_LANGUAGE here, or they'd be stuck in English
        # forever.
        has_care_text = existing.light is not None or existing.soil is not None or existing.notes is not None
        effective_care_language = existing.care_language or ("en" if has_care_text else None)
        if refresh_common_name and effective_care_language is not None and effective_care_language != language:
            try:
                care = await ai_client.describe_care(scientific_name, language=language)
            except Exception:
                care = None
            if care is not None:
                existing.light = care.get("light")
                existing.soil = care.get("soil")
                existing.notes = care.get("notes")
                existing.care_language = language
                session.flush()
        return existing

    # Care-data resolution (Perenual/LLM/default), reference-image lookup, and
    # common-name resolution (AI -> Perenual -> fallback) are independent
    # network calls, so run them concurrently rather than sequentially.
    # Only resolve common name if one wasn't provided.
    if common_name:
        care, reference_image_url = await asyncio.gather(
            resolve_care_data(scientific_name, perenual_client=perenual_client, ai_client=ai_client, language=language),
            reference_image_fetcher(scientific_name),
        )
        final_common_name = common_name
    else:
        care, reference_image_url, resolved_common_name = await asyncio.gather(
            resolve_care_data(scientific_name, perenual_client=perenual_client, ai_client=ai_client, language=language),
            reference_image_fetcher(scientific_name),
            _resolve_common_name(scientific_name, ai_client=ai_client, perenual_client=perenual_client, language=language),
        )
        final_common_name = resolved_common_name

    species = Species(
        scientific_name=scientific_name,
        common_name=final_common_name,
        reference_image_url=reference_image_url,
        watering_interval_days=care.interval_days,
        seasonal_profile=care.seasonal_profile,
        light=care.light,
        soil=care.soil,
        notes=care.notes,
        source=care.source,
        care_language=care.care_language,
    )
    session.add(species)
    session.flush()
    return species
