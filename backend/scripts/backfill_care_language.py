#!/usr/bin/env python3
"""One-off backfill: re-resolve stale-language care text on existing species.

The `Species.care_language` column (added alongside the "Provide care
instructions" feature) is used by `app.services.species_resolution` to
re-resolve `light`/`soil`/`notes` in the deployment's configured language on
the next photo re-identify. But species created *before* that column existed
have `care_language=None` even though they already carry real (always-
English, since the old `describe_care` had no language parameter) text — and
nobody re-identifies an already-added plant just to pick up a translation.

This script does that refresh once, for every already-existing species whose
text isn't already in `Settings.language`, without requiring the user to
re-photograph each plant.

Usage:
    python -m scripts.backfill_care_language [--dry-run]
"""

import argparse
import asyncio

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.ai import AiVisionClient
from app.config import Settings
from app.db import create_db_engine, init_db, session_scope
from app.models.orm import Species


def _stale_species(session: Session, language: str) -> list[Species]:
    """Species with real light/soil/notes text not already in `language` —
    covers both pre-care_language rows (care_language is None) and rows
    resolved under a different Settings.language."""
    candidates = session.scalars(
        select(Species).where(Species.light.is_not(None) | Species.soil.is_not(None) | Species.notes.is_not(None))
    ).all()
    return [s for s in candidates if (s.care_language or "en") != language]


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
            for species in _stale_species(session, settings.language):
                try:
                    care = await owned_ai_client.describe_care(species.scientific_name, language=settings.language)
                except Exception as exc:
                    print(f"  skipped {species.scientific_name!r}: {exc}")
                    continue

                if not dry_run:
                    species.light = care.get("light")
                    species.soil = care.get("soil")
                    species.notes = care.get("notes")
                    species.care_language = settings.language
                updated.append(species.scientific_name)
    finally:
        if http_client is not None:
            await http_client.aclose()

    return updated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-resolve light/soil/notes for already-existing species not yet in the configured language."
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
