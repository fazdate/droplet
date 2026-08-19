"""Species identification/lookup/manual-create + AI-assisted plant creation —
plan section 4.4 (add-a-plant flow)."""

import asyncio
import datetime as dt
import logging
import time
from collections.abc import Awaitable, Sequence

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.clients.ai import AiVisionClient
from app.clients.perenual import PerenualClient
from app.clients.wikipedia import fetch_reference_image_url
from app.config import Settings
from app.deps import get_ai_client, get_db, get_http_client, get_perenual_client, get_settings
from app.languages import DEFAULT_LANGUAGE
from app.models.orm import Plant, Room, Species
from app.presenters import plant_to_out
from app.schemas import (
    IdentifyCandidateOut,
    IdentifyResponse,
    PlantCreate,
    PlantOut,
    SpeciesLookupResponse,
    SpeciesManualCreate,
)
from app.rate_limit import limiter
from app.services.photo_storage import save_upload
from app.services.plants import create_plant, find_or_create_species_manual
from app.services.species_resolution import get_or_create_species
from app.utils.errors import not_found

LOG = logging.getLogger(__name__)

router = APIRouter(tags=["species"])


def _candidate_out(species: Species, confidence: float | None) -> IdentifyCandidateOut:
    return IdentifyCandidateOut(
        species_id=species.id,
        scientific_name=species.scientific_name,
        common_name=species.common_name,
        confidence=confidence,
        reference_image_url=species.reference_image_url,
    )


async def _resolve_candidates_concurrently(
    db: Session,
    candidates: Sequence[tuple[str, str | None, float | None]],
    *,
    perenual_client: PerenualClient,
    ai_client: AiVisionClient,
    http_client: httpx.AsyncClient,
    refresh_common_name: bool,
    language: str,
) -> list[IdentifyCandidateOut]:
    """Resolves (cache-lookup or create) a species per ``(scientific_name,
    common_name, confidence)`` candidate.

    Candidates are fully independent, so their care-data/reference-image
    network calls (the slow part of an identify/lookup request — see
    TODO.md "Speed up plant identification") are run concurrently via
    asyncio.gather rather than one after another. Candidates are deduplicated
    by scientific_name first (e.g. the model can repeat a name across
    tiers) so two concurrent tasks never race to create the same
    not-yet-cached species row.
    """
    unique_candidates: list[tuple[str, str | None, float | None]] = []
    seen_names: set[str] = set()
    for candidate in candidates:
        name = candidate[0]
        if name not in seen_names:
            seen_names.add(name)
            unique_candidates.append(candidate)

    def _fetch_reference_image(name: str) -> Awaitable[str | None]:
        return fetch_reference_image_url(name, client=http_client)

    resolved = await asyncio.gather(
        *(
            get_or_create_species(
                db,
                scientific_name=name,
                common_name=common_name,
                perenual_client=perenual_client,
                ai_client=ai_client,
                reference_image_fetcher=_fetch_reference_image,
                refresh_common_name=refresh_common_name,
                language=language,
            )
            for name, common_name, _confidence in unique_candidates
        )
    )
    species_by_name = {name: species for (name, _common_name, _confidence), species in zip(unique_candidates, resolved)}
    return [_candidate_out(species_by_name[name], confidence) for name, _common_name, confidence in candidates]


@router.post("/api/identify", response_model=IdentifyResponse)
@limiter.limit("10/minute")
async def identify_plant(
    request: Request,
    photo: UploadFile,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    ai_client: AiVisionClient = Depends(get_ai_client),
    perenual_client: PerenualClient = Depends(get_perenual_client),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> IdentifyResponse:
    # Timed at each phase (see TODO.md "Speed up plant identification
    # further") so a slow request's bottleneck — the AI vision call vs. the
    # per-candidate care-data/reference-image resolution — is visible in logs
    # instead of only the total request time uvicorn's access log shows.
    request_start = time.monotonic()
    content = await photo.read()
    photo_id = save_upload(settings.photos_dir, original_filename=photo.filename or "upload.jpg", content=content)

    identify_start = time.monotonic()
    candidates = await ai_client.identify_species(
        image_bytes=content, mime_type=photo.content_type or "image/jpeg", language=settings.language
    )
    LOG.info("AI identify_species took %.2fs, returned %d candidates", time.monotonic() - identify_start, len(candidates))

    resolve_start = time.monotonic()
    out_candidates = await _resolve_candidates_concurrently(
        db,
        [(c.scientific_name, c.common_name, c.confidence) for c in candidates[:3]],
        perenual_client=perenual_client,
        ai_client=ai_client,
        http_client=http_client,
        refresh_common_name=True,
        language=settings.language,
    )
    LOG.info("Resolving %d identify candidates took %.2fs", len(candidates[:3]), time.monotonic() - resolve_start)

    db.flush()
    LOG.info("Total /api/identify request took %.2fs", time.monotonic() - request_start)
    return IdentifyResponse(photo_id=photo_id, candidates=out_candidates)


@router.get("/api/species/lookup", response_model=SpeciesLookupResponse)
async def lookup_species(
    q: str = Query(min_length=1),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    ai_client: AiVisionClient = Depends(get_ai_client),
    perenual_client: PerenualClient = Depends(get_perenual_client),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> SpeciesLookupResponse:
    pattern = f"%{q}%"
    existing = db.scalars(
        select(Species).where(
            or_(Species.scientific_name.ilike(pattern), Species.common_name.ilike(pattern))
        )
    ).all()
    known_names = {s.scientific_name for s in existing}

    candidates = [_candidate_out(s, None) for s in existing]

    perenual_hits = [
        (name, hit.get("common_name"), None)
        for hit in (await perenual_client.search_species(q))[:3]
        if (name := hit.get("scientific_name")) and name not in known_names
    ]
    if perenual_hits:
        candidates.extend(
            await _resolve_candidates_concurrently(
                db,
                perenual_hits,
                perenual_client=perenual_client,
                ai_client=ai_client,
                http_client=http_client,
                refresh_common_name=False,
                language=settings.language,
            )
        )
        known_names.update(name for name, _common_name, _confidence in perenual_hits)

    # Perenual's text search only understands English, so a query typed in the
    # deployment's configured non-English language (e.g. Hungarian) finds
    # nothing there even for well-known species. Fall back to asking the LLM
    # to resolve the name once the cheaper lookups above come up empty.
    if not candidates and settings.language != DEFAULT_LANGUAGE:
        llm_hits = [
            (c.scientific_name, c.common_name, c.confidence)
            for c in (await ai_client.resolve_species_by_name(q, language=settings.language))[:3]
            if c.scientific_name not in known_names
        ]
        if llm_hits:
            candidates.extend(
                await _resolve_candidates_concurrently(
                    db,
                    llm_hits,
                    perenual_client=perenual_client,
                    ai_client=ai_client,
                    http_client=http_client,
                    refresh_common_name=True,
                    language=settings.language,
                )
            )

    db.flush()
    return SpeciesLookupResponse(candidates=candidates)


@router.post("/api/species/manual", status_code=201)
def create_manual_species(payload: SpeciesManualCreate, db: Session = Depends(get_db)) -> dict:
    species = find_or_create_species_manual(
        db,
        name=payload.name,
        interval_days=payload.interval_days,
        seasonal_profile=payload.seasonal_profile,
    )
    db.flush()
    return {"species_id": species.id, "scientific_name": species.scientific_name}


def _derive_nickname(db: Session, species: Species) -> str:
    # Return just the species name without numeric suffixes. Multiple plants of
    # the same species will have the same display name, but they can be
    # distinguished by their photos, and users can set custom nicknames if needed.
    return species.common_name or species.scientific_name


@router.post("/api/plants", response_model=PlantOut, status_code=201)
def create_plant_endpoint(
    payload: PlantCreate, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> PlantOut:
    species = db.get(Species, payload.species_id)
    if species is None:
        raise not_found("Species")
    room = db.get(Room, payload.room_id)
    if room is None:
        raise not_found("Room")

    is_custom_nickname = bool(payload.nickname and payload.nickname.strip())
    nickname = payload.nickname.strip() if is_custom_nickname else _derive_nickname(db, species)
    now = dt.datetime.now(dt.timezone.utc)

    plant = create_plant(
        db,
        nickname=nickname,
        room=room,
        species=species,
        photo_path=payload.photo_id,
        now=now,
        nickname_is_custom=is_custom_nickname,
    )
    if payload.interval_override is not None:
        plant.watering_interval_days_override = payload.interval_override
    db.flush()
    db.refresh(plant)

    return plant_to_out(plant, now, settings.hemisphere)
