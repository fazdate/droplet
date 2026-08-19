"""Plants API: listing, watering (single + room), undo — plan section 4.3."""

import datetime as dt
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.clients.ai import AiDiagnoseError, AiUnavailableError, AiVisionClient
from app.config import Settings
from app.deps import get_db, get_diagnose_ai_client, get_settings
from app.models.orm import Plant, Room, WateringEvent
from app.presenters import plant_to_out
from app.schemas import DiagnoseIssueOut, DiagnoseResponse, PlantOut, PlantUpdate, UndoRequest, UndoResult, WaterResult
from app.services.photo_storage import save_upload
from app.services.schedule import compute_effective_interval, compute_next_due_at, resolve_base_interval
from app.services.thumbnails import thumbnail_filename, thumbnails_dir
from app.services.watering import water_plant
from app.utils.errors import not_found

router = APIRouter(tags=["plants"])

UNDO_WINDOW = dt.timedelta(minutes=5)


def _recompute_next_due(plant: Plant, hemisphere: str) -> None:
    """Recomputes next_due_at from the plant's last watering (if any) whenever
    the interval override or seasonal-adjust flag changes — plan 4.6:
    "Changing the cadence recomputes next_due_at from last_watered_at immediately"."""
    if plant.last_watered_at is None:
        return
    base_interval = resolve_base_interval(
        species_interval_days=plant.species.watering_interval_days,
        plant_override_days=plant.watering_interval_days_override,
    )
    effective_interval = compute_effective_interval(
        base_interval_days=base_interval,
        month=plant.last_watered_at.month,
        profile=plant.species.seasonal_profile,
        hemisphere=hemisphere,
        seasonal_adjust_enabled=plant.seasonal_adjust_enabled,
    )
    plant.next_due_at = compute_next_due_at(
        last_watered_at=plant.last_watered_at, effective_interval_days=effective_interval
    )


def _get_undo_store(request: Request) -> dict:
    return request.app.state.undo_store


@router.get("/api/plants", response_model=list[PlantOut])
def list_plants(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> list[PlantOut]:
    now = dt.datetime.now(dt.timezone.utc)
    plants = db.scalars(
        select(Plant).options(joinedload(Plant.room), joinedload(Plant.species))
    ).all()
    return [plant_to_out(plant, now, settings.hemisphere) for plant in plants]


def _record_undo(store: dict, entries: list[dict]) -> str:
    token = str(uuid.uuid4())
    store[token] = {"created_at": dt.datetime.now(dt.timezone.utc), "entries": entries}
    return token


def _water_and_capture(
    session: Session, plant: Plant, *, now: dt.datetime, source: str, hemisphere: str
) -> dict:
    prev_last_watered_at = plant.last_watered_at
    prev_next_due_at = plant.next_due_at
    prev_last_notified_at = plant.last_notified_at
    event = water_plant(session, plant, now=now, source=source, hemisphere=hemisphere)
    return {
        "plant_id": plant.id,
        "event_id": event.id,
        "prev_last_watered_at": prev_last_watered_at,
        "prev_next_due_at": prev_next_due_at,
        "prev_last_notified_at": prev_last_notified_at,
    }


@router.post("/api/plants/{plant_id}/water", response_model=WaterResult)
def water_single_plant(
    plant_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> WaterResult:
    plant = db.get(Plant, plant_id)
    if plant is None:
        raise not_found("Plant")

    now = dt.datetime.now(dt.timezone.utc)
    entry = _water_and_capture(db, plant, now=now, source="app_single", hemisphere=settings.hemisphere)
    db.flush()

    token = _record_undo(_get_undo_store(request), [entry])
    return WaterResult(undo_token=token, plant_ids=[plant.id])


@router.post("/api/rooms/{room_id}/water", response_model=WaterResult)
def water_room(
    room_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> WaterResult:
    room = db.get(Room, room_id)
    if room is None:
        raise not_found("Room")

    now = dt.datetime.now(dt.timezone.utc)
    plants = db.scalars(select(Plant).where(Plant.room_id == room_id)).all()
    entries = [
        _water_and_capture(db, plant, now=now, source="app_room", hemisphere=settings.hemisphere)
        for plant in plants
    ]
    db.flush()

    token = _record_undo(_get_undo_store(request), entries)
    return WaterResult(undo_token=token, plant_ids=[e["plant_id"] for e in entries])


@router.post("/api/undo", response_model=UndoResult)
def undo(payload: UndoRequest, request: Request, db: Session = Depends(get_db)) -> UndoResult:
    store = _get_undo_store(request)
    record = store.get(payload.token)
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown or already-used undo token")

    now = dt.datetime.now(dt.timezone.utc)
    if now - record["created_at"] > UNDO_WINDOW:
        del store[payload.token]
        raise HTTPException(status_code=410, detail="Undo window expired")

    restored_ids = []
    for entry in record["entries"]:
        plant = db.get(Plant, entry["plant_id"])
        if plant is not None:
            plant.last_watered_at = entry["prev_last_watered_at"]
            plant.next_due_at = entry["prev_next_due_at"]
            plant.last_notified_at = entry["prev_last_notified_at"]
        event = db.get(WateringEvent, entry["event_id"])
        if event is not None:
            db.delete(event)
        restored_ids.append(entry["plant_id"])

    db.flush()
    del store[payload.token]
    return UndoResult(restored_plant_ids=restored_ids)


@router.post("/api/plants/{plant_id}", response_model=PlantOut)
def update_plant(
    plant_id: int,
    payload: PlantUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PlantOut:
    plant = db.get(Plant, plant_id)
    if plant is None:
        raise not_found("Plant")

    fields_set = payload.model_fields_set
    if "nickname" in fields_set and payload.nickname is not None and payload.nickname.strip():
        plant.nickname = payload.nickname.strip()
        # An explicit rename (creation flow's nickname prompt already covers
        # the initial name) — plan TODO: "Rename plant/nickname" hidden
        # behind the "⋮" detail menu.
        plant.nickname_is_custom = True
    if "room_id" in fields_set and payload.room_id is not None:
        room = db.get(Room, payload.room_id)
        if room is None:
            raise not_found("Room")
        plant.room_id = payload.room_id

    cadence_changed = False
    if "interval_override" in fields_set:
        plant.watering_interval_days_override = payload.interval_override
        cadence_changed = True
    if "seasonal_adjust_enabled" in fields_set and payload.seasonal_adjust_enabled is not None:
        plant.seasonal_adjust_enabled = payload.seasonal_adjust_enabled
        cadence_changed = True

    if cadence_changed:
        _recompute_next_due(plant, settings.hemisphere)

    db.flush()
    db.refresh(plant)
    return plant_to_out(plant, dt.datetime.now(dt.timezone.utc), settings.hemisphere)


@router.post("/api/plants/{plant_id}/photo", response_model=PlantOut)
async def update_plant_photo(
    plant_id: int,
    photo: UploadFile,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PlantOut:
    """Replaces a plant's photo (TODO.md: "Option to add new picture for the
    plant"). Deliberately not exposed as a frequently-used action in the UI —
    it's tucked behind the plant's "⋮" detail menu."""
    plant = db.get(Plant, plant_id)
    if plant is None:
        raise not_found("Plant")

    content = await photo.read()
    photos_dir = Path(settings.photos_dir)
    new_photo_id = save_upload(photos_dir, original_filename=photo.filename or "upload.jpg", content=content)

    old_photo_id = plant.photo_path
    plant.photo_path = new_photo_id
    db.flush()
    db.refresh(plant)

    # Best-effort cleanup of the now-orphaned old photo + its cached
    # thumbnail, mirroring delete_plant's cleanup below.
    (photos_dir / old_photo_id).unlink(missing_ok=True)
    (thumbnails_dir(photos_dir) / thumbnail_filename(old_photo_id)).unlink(missing_ok=True)

    return plant_to_out(plant, dt.datetime.now(dt.timezone.utc), settings.hemisphere)


@router.post("/api/plants/{plant_id}/diagnose", response_model=DiagnoseResponse)
async def diagnose_plant_issues(
    plant_id: int,
    photo: UploadFile,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    diagnose_client: AiVisionClient = Depends(get_diagnose_ai_client),
) -> DiagnoseResponse:
    """Diagnoses visible issues (yellowing leaves, pests, wilting, etc.) from a
    fresh photo of an existing plant and suggests fixes — plan TODO: "Recognize
    issues with the plants... provide suggestions for how to fix them", tucked
    behind the plant's "⋮" detail menu like the other rarely-used actions.
    The uploaded photo is only used for this one-off diagnosis; unlike
    update_plant_photo it is not saved or attached to the plant."""
    plant = db.scalars(
        select(Plant).where(Plant.id == plant_id).options(joinedload(Plant.species))
    ).unique().one_or_none()
    if plant is None:
        raise not_found("Plant")

    content = await photo.read()
    species_name = plant.species.common_name or plant.species.scientific_name

    try:
        result = await diagnose_client.diagnose_plant(
            image_bytes=content,
            mime_type=photo.content_type or "image/jpeg",
            species_name=species_name,
            language=settings.language,
        )
    except AiUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Diagnosis is temporarily unavailable, please try again later") from exc
    except AiDiagnoseError as exc:
        raise HTTPException(status_code=502, detail="Could not diagnose this photo, please try again") from exc

    return DiagnoseResponse(
        healthy=result.healthy,
        issues=[DiagnoseIssueOut(issue=i.issue, suggestion=i.suggestion) for i in result.issues],
    )


@router.delete("/api/plants/{plant_id}", status_code=204)
def delete_plant(
    plant_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> Response:
    """Removes a plant permanently (TODO.md: "Option to remove a plant").
    Watering history cascades via the ORM relationship; the uploaded photo
    file is best-effort cleaned up too since nothing else references it."""
    plant = db.get(Plant, plant_id)
    if plant is None:
        raise not_found("Plant")

    photo_path = Path(settings.photos_dir) / plant.photo_path
    db.delete(plant)
    db.flush()

    photo_path.unlink(missing_ok=True)
    return Response(status_code=204)


@router.delete("/api/plants/{plant_id}/interval-override", response_model=PlantOut)
def reset_interval_override(
    plant_id: int, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> PlantOut:
    plant = db.get(Plant, plant_id)
    if plant is None:
        raise not_found("Plant")

    plant.watering_interval_days_override = None
    _recompute_next_due(plant, settings.hemisphere)
    db.flush()
    db.refresh(plant)
    return plant_to_out(plant, dt.datetime.now(dt.timezone.utc), settings.hemisphere)
