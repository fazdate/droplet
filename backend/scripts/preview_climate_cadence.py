#!/usr/bin/env python3
"""Preview (and optionally apply) the climate-aware cadence recompute —
CLIMATE_CADENCE_PLAN.md.

Because the daily cadence_recompute scheduler job silently moves plants'
next_due_at in the background, this script is the practical way to inspect
what it would do: for each room, its configured entities, latest/smoothed
readings and resulting climate factor; and for each plant, its current vs.
proposed next_due_at. No separate backfill script is needed since the daily
job itself is the backfill — this is purely an inspection/manual-trigger tool.

Usage:
    python -m scripts.preview_climate_cadence [--apply]
"""

import argparse
import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import Settings
from app.db import create_db_engine, init_db, session_scope
from app.models.orm import Plant, Room
from app.services.cadence_recompute import run_cadence_recompute
from app.services.climate import climate_factor_for_room, room_climate_factors
from app.services.schedule import compute_effective_interval, compute_next_due_at, resolve_base_interval


@dataclass(frozen=True)
class RoomPreview:
    name: str
    temperature_entity_id: str | None
    humidity_entity_id: str | None
    climate_temp_c: float | None
    climate_humidity: float | None
    climate_vpd_kpa: float | None
    factor: float


@dataclass(frozen=True)
class PlantPreview:
    nickname: str
    current_next_due_at: dt.datetime | None
    proposed_next_due_at: dt.datetime


def build_preview(session: Session, *, now: dt.datetime, hemisphere: str) -> tuple[list[RoomPreview], list[PlantPreview]]:
    factors = room_climate_factors(session, now=now)

    rooms = session.scalars(select(Room)).all()
    room_previews = [
        RoomPreview(
            name=room.name,
            temperature_entity_id=room.temperature_entity_id,
            humidity_entity_id=room.humidity_entity_id,
            climate_temp_c=room.climate_temp_c,
            climate_humidity=room.climate_humidity,
            climate_vpd_kpa=room.climate_vpd_kpa,
            factor=climate_factor_for_room(room, now),
        )
        for room in rooms
    ]

    plants = session.scalars(
        select(Plant).where(Plant.last_watered_at.is_not(None)).options(joinedload(Plant.species))
    ).all()
    plant_previews = []
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
        proposed = compute_next_due_at(
            last_watered_at=plant.last_watered_at, effective_interval_days=effective_interval
        )
        plant_previews.append(
            PlantPreview(nickname=plant.nickname, current_next_due_at=plant.next_due_at, proposed_next_due_at=proposed)
        )

    return room_previews, plant_previews


def _print_preview(rooms: list[RoomPreview], plants: list[PlantPreview]) -> None:
    print("Rooms:")
    for room in rooms:
        if room.temperature_entity_id is None and room.humidity_entity_id is None:
            print(f"  {room.name}: no sensors configured (factor 1.00)")
            continue
        print(
            f"  {room.name}: temp={room.temperature_entity_id} humidity={room.humidity_entity_id} "
            f"latest={room.climate_temp_c}°C/{room.climate_humidity}% "
            f"smoothed_vpd={room.climate_vpd_kpa} factor={room.factor:.2f}"
        )

    print("Plants:")
    for plant in plants:
        print(f"  {plant.nickname}: current={plant.current_next_due_at} proposed={plant.proposed_next_due_at}")


def preview_climate_cadence(
    *, db_path: str, hemisphere: str, apply: bool, now: dt.datetime | None = None
) -> tuple[list[RoomPreview], list[PlantPreview]]:
    now = now or dt.datetime.now(dt.timezone.utc)
    engine = create_db_engine(f"sqlite:///{db_path}")
    init_db(engine)

    with session_scope(engine) as session:
        rooms, plants = build_preview(session, now=now, hemisphere=hemisphere)
        _print_preview(rooms, plants)

        if apply:
            run_cadence_recompute(session, now=now, hemisphere=hemisphere)
            print("Applied.")
        else:
            print("Dry run only — pass --apply to commit these changes.")

    return rooms, plants


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview the climate-aware cadence recompute.")
    parser.add_argument("--apply", action="store_true", help="Commit the recompute instead of only previewing it")
    args = parser.parse_args()

    settings = Settings()
    preview_climate_cadence(db_path=settings.db_path, hemisphere=settings.hemisphere, apply=args.apply)


if __name__ == "__main__":
    main()
