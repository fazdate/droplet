"""Daily batch cadence recompute — CLIMATE_CADENCE_PLAN.md phase 3.

Applies each plant's *current* month and its room's *current* climate factor
to the stored `next_due_at`, so a room's sensor readings (and the calendar)
keep the due date honest even for plants nobody has touched today. This batch
operation does not exist elsewhere — only per-plant paths (watering,
interval/seasonal-adjust edits) write `next_due_at`.
"""

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.orm import Plant
from app.services.climate import room_climate_factors
from app.services.schedule import compute_effective_interval, compute_next_due_at, resolve_base_interval

# Hysteresis: a recompute only overwrites next_due_at if it would actually
# move by half a day or more, so a sensor's small day-to-day wobble doesn't
# rewrite the stored due date (and the UI's due/overdue badge) for no
# perceptible reason.
_MIN_MOVE = dt.timedelta(hours=12)


def run_cadence_recompute(session: Session, *, now: dt.datetime, hemisphere: str) -> None:
    factors = room_climate_factors(session, now=now)

    plants = session.scalars(
        select(Plant).where(Plant.last_watered_at.is_not(None)).options(joinedload(Plant.species))
    ).all()

    for plant in plants:
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
            climate_factor=factors.get(plant.room_id, 1.0),
        )
        new_due_at = compute_next_due_at(
            last_watered_at=plant.last_watered_at, effective_interval_days=effective_interval
        )
        if plant.next_due_at is None or abs(new_due_at - plant.next_due_at) >= _MIN_MOVE:
            plant.next_due_at = new_due_at

    session.flush()
