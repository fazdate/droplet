#!/usr/bin/env python3
"""One-off backfill: refresh multilingual care text and common names on existing species.

The app now stores care instructions per language so it can display whatever
the current deployment language needs. This script fills in missing language
rows for already-existing species without requiring the user to re-photograph
each plant.

Usage:
    python -m scripts.backfill_care_language [--dry-run]
"""

import argparse
import asyncio

import httpx
from sqlalchemy.orm import Session

from app.clients.ai import AiVisionClient
from app.config import Settings
from app.db import create_db_engine, init_db, session_scope
from app.languages import supported_language_codes
from app.models.orm import Species, SpeciesCareText, SpeciesCommonName
from app.services.care_resolution import CareText, resolve_care_data
from app.services.species_resolution import resolve_common_names


def _stale_species(session: Session) -> list[Species]:
    return [
        species
        for species in session.query(Species).all()
        if any(not species.has_care_text_for(language) for language in supported_language_codes())
        or any(not species.has_common_name_for(language) for language in supported_language_codes())
    ]


def _apply_care_data(species: Species, care_texts: dict[str, CareText], *, current_language: str) -> None:
    for language, text in care_texts.items():
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

    snapshot = care_texts.get(current_language) or next(iter(care_texts.values()), CareText(None, None, None))
    species.light = snapshot.light
    species.soil = snapshot.soil
    species.notes = snapshot.notes
    species.care_language = current_language if current_language in care_texts else next(iter(care_texts), None)


def _apply_common_names(species: Species, common_names: dict[str, str], *, current_language: str) -> None:
    for language, common_name in common_names.items():
        record = species.common_name_record_for(language)
        if record is None:
            record = SpeciesCommonName(language=language, common_name=common_name)
            species.common_names.append(record)
        else:
            record.common_name = common_name

    if current_language in common_names:
        species.common_name = common_names[current_language]
        species.common_name_language = current_language
    elif common_names:
        first_language, first_common_name = next(iter(common_names.items()))
        species.common_name = first_common_name
        species.common_name_language = first_language


async def backfill(
    *, db_path: str, settings: Settings, ai_client: AiVisionClient | None = None, dry_run: bool = False
) -> list[str]:
    engine = create_db_engine(f"sqlite:///{db_path}")
    init_db(engine)

    http_client = httpx.AsyncClient() if ai_client is None else None
    owned_ai_client = ai_client or AiVisionClient(
        api_style=settings.ai_api_style,
        base_url=settings.ai_base_url,
        api_key=settings.ai_api_key,
        model=settings.ai_model,
        api_version=settings.ai_api_version,
        http_client=http_client,
    )

    updated: list[str] = []
    try:
        with session_scope(engine) as session:
            for species in _stale_species(session):
                care = await resolve_care_data(
                    species.scientific_name,
                    perenual_client=None,
                    ai_client=owned_ai_client,
                    language=settings.language,
                )
                common_names = await resolve_common_names(
                    species.scientific_name,
                    ai_client=owned_ai_client,
                    perenual_client=None,
                    language=settings.language,
                )

                if not dry_run:
                    _apply_care_data(species, care.care_texts, current_language=care.care_language or settings.language)
                    species.light = care.light
                    species.soil = care.soil
                    species.notes = care.notes
                    species.care_language = care.care_language
                    _apply_common_names(species, common_names, current_language=settings.language)
                updated.append(species.scientific_name)
    finally:
        if http_client is not None:
            await http_client.aclose()

    return updated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-resolve multilingual care text and common names for already-existing species."
    )
    parser.add_argument("--dry-run", action="store_true", help="List what would be updated without saving it")
    args = parser.parse_args()

    settings = Settings()
    updated = asyncio.run(backfill(db_path=settings.db_path, settings=settings, dry_run=args.dry_run))

    verb = "Would update" if args.dry_run else "Updated"
    print(f"{verb} {len(updated)} species to language={settings.language!r}{':' if updated else ''}")
    for name in updated:
        print(f"  {name}")


if __name__ == "__main__":
    main()
