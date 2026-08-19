"""Snooze / away / HA action-webhook endpoints — plan sections 4.3, 4.8, 4.9."""

import datetime as dt
import re

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.ha import HomeAssistantClient
from app.config import Settings
from app.deps import get_db, get_settings
from app.models.orm import Plant, Room
from app.schemas import AwayRequest, HaActionRequest, SnoozeRequest
from app.services.settings_store import set_away_until
from app.services.watering import water_plant

router = APIRouter(tags=["notifications"])


@router.post("/api/plants/{plant_id}/snooze", status_code=200)
def snooze_plant(plant_id: int, payload: SnoozeRequest, db: Session = Depends(get_db)) -> dict:
    plant = db.get(Plant, plant_id)
    if plant is None:
        raise HTTPException(status_code=404, detail="Plant not found")
    if payload.days is not None:
        delta = dt.timedelta(days=payload.days)
    else:
        delta = dt.timedelta(minutes=payload.minutes or 0)
    plant.snoozed_until = dt.datetime.now(dt.timezone.utc) + delta
    db.flush()
    return {"plant_id": plant_id, "snoozed_until": plant.snoozed_until}


@router.post("/api/away", status_code=200)
def set_away(payload: AwayRequest, db: Session = Depends(get_db)) -> dict:
    if payload.until is not None:
        until = dt.datetime.fromisoformat(payload.until.replace("Z", "+00:00"))
    elif payload.days is not None:
        until = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=payload.days)
    else:
        until = None
    set_away_until(db, until)
    return {"away_until": until}


def _check_webhook_secret(settings: Settings, x_webhook_secret: str | None) -> None:
    if x_webhook_secret != settings.ha_webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


def _clear_notification_tags(settings: Settings, tags: list[str]) -> None:
    if not settings.notify_targets:
        return
    unique_tags = sorted({tag for tag in tags if tag})
    if not unique_tags:
        return
    ha_client = HomeAssistantClient(base_url=settings.ha_base_url, token=settings.ha_long_lived_token)
    for tag in unique_tags:
        ha_client.clear_notification(targets=settings.notify_targets, tag=tag)


@router.post("/api/ha/action", status_code=200)
def ha_action(
    payload: HaActionRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    x_webhook_secret: str | None = Header(default=None),
) -> dict:
    _check_webhook_secret(settings, x_webhook_secret)

    action = payload.action
    now = dt.datetime.now(dt.timezone.utc)

    if action.startswith("WATERED_ROOM_"):
        room_id = int(action.removeprefix("WATERED_ROOM_"))
        room = db.get(Room, room_id)
        if room is None:
            raise HTTPException(status_code=404, detail="Room not found")
        plants = db.scalars(select(Plant).where(Plant.room_id == room_id)).all()
        for plant in plants:
            water_plant(db, plant, now=now, source="notification", hemisphere=settings.hemisphere)
        db.flush()
        _clear_notification_tags(settings, [payload.tag or f"room-{room_id}"])
        return {"applied": action}

    if action.startswith("WATERED_"):
        plant_id = int(action.removeprefix("WATERED_"))
        plant = db.get(Plant, plant_id)
        if plant is None:
            raise HTTPException(status_code=404, detail="Plant not found")
        water_plant(db, plant, now=now, source="notification", hemisphere=settings.hemisphere)
        db.flush()
        _clear_notification_tags(settings, [payload.tag or f"plant-{plant_id}"])
        return {"applied": action}

    snooze_match = re.match(r"^SNOOZE_(\d+)([DM])_(\d+)$", action)
    if snooze_match is not None:
        amount = int(snooze_match.group(1))
        unit = snooze_match.group(2)
        plant_id = int(snooze_match.group(3))
        plant = db.get(Plant, plant_id)
        if plant is None:
            raise HTTPException(status_code=404, detail="Plant not found")
        if unit == "D":
            plant.snoozed_until = now + dt.timedelta(days=amount)
        else:
            plant.snoozed_until = now + dt.timedelta(minutes=amount)
        db.flush()
        _clear_notification_tags(settings, [payload.tag or f"plant-{plant_id}"])
        return {"applied": action}

    if action == "AWAY_3D":
        plants = db.scalars(select(Plant)).all()
        tags_to_clear = [f"plant-{plant.id}" for plant in plants]
        tags_to_clear.extend({f"room-{plant.room_id}" for plant in plants})
        set_away_until(db, now + dt.timedelta(days=3))
        _clear_notification_tags(settings, [payload.tag, *tags_to_clear])
        return {"applied": action}

    raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
