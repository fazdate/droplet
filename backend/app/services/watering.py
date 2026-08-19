"""Watering service: applies a watering action to a Plant + records the event."""

import datetime as dt

from sqlalchemy.orm import Session

from app.models.orm import Plant, WateringEvent
from app.services.schedule import compute_effective_interval, compute_next_due_at, resolve_base_interval


def water_plant(session: Session, plant: Plant, *, now: dt.datetime, source: str, hemisphere: str) -> WateringEvent:
    """Records a watering event and recomputes the plant's next due date.

    Caller is responsible for committing/flushing the session.
    """
    base_interval = resolve_base_interval(
        species_interval_days=plant.species.watering_interval_days,
        plant_override_days=plant.watering_interval_days_override,
    )
    effective_interval = compute_effective_interval(
        base_interval_days=base_interval,
        month=now.month,
        profile=plant.species.seasonal_profile,
        hemisphere=hemisphere,
        seasonal_adjust_enabled=plant.seasonal_adjust_enabled,
    )

    plant.last_watered_at = now
    plant.next_due_at = compute_next_due_at(last_watered_at=now, effective_interval_days=effective_interval)
    plant.last_notified_at = None

    event = WateringEvent(plant_id=plant.id, watered_at=now, source=source)
    session.add(event)
    session.flush()
    return event
