"""Shared Plant ORM -> schema conversion, used by both the plants router and
the species/add-plant router."""

import datetime as dt

from app.models.orm import Plant
from app.schemas import PlantOut
from app.services.schedule import compute_effective_interval


def plant_to_out(plant: Plant, now: dt.datetime, hemisphere: str) -> PlantOut:
    recommended_interval_days = compute_effective_interval(
        base_interval_days=plant.species.watering_interval_days,
        month=now.month,
        profile=plant.species.seasonal_profile,
        hemisphere=hemisphere,
        seasonal_adjust_enabled=plant.seasonal_adjust_enabled,
    )
    return PlantOut(
        id=plant.id,
        nickname=plant.nickname,
        nickname_is_custom=plant.nickname_is_custom,
        room_id=plant.room_id,
        room_name=plant.room.name,
        species_id=plant.species_id,
        species_common_name=plant.species.common_name,
        photo_path=plant.photo_path,
        next_due_at=plant.next_due_at,
        last_watered_at=plant.last_watered_at,
        is_overdue=plant.next_due_at is not None and plant.next_due_at < now,
        watering_interval_days_override=plant.watering_interval_days_override,
        seasonal_adjust_enabled=plant.seasonal_adjust_enabled,
        recommended_interval_days=recommended_interval_days,
        care_source=plant.species.source,
        light=plant.species.light,
        soil=plant.species.soil,
        notes=plant.species.notes,
    )
