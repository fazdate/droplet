"""Tests for scripts/preview_climate_cadence.py (CLIMATE_CADENCE_PLAN.md verification)."""

import datetime as dt

from sqlalchemy.orm import Session

from app.db import create_db_engine, init_db
from app.models.orm import Plant, Room, Species
from scripts.preview_climate_cadence import preview_climate_cadence


def _seed(db_path: str) -> tuple[int, dt.datetime]:
    engine = create_db_engine(f"sqlite:///{db_path}")
    init_db(engine)
    with Session(engine) as session:
        room = Room(name="Balcony")
        species = Species(scientific_name="Ficus", watering_interval_days=7, seasonal_profile="temperate")
        session.add_all([room, species])
        session.commit()
        last_watered = dt.datetime(2026, 1, 1, 9, 0, tzinfo=dt.timezone.utc)
        plant = Plant(
            nickname="Fig",
            species_id=species.id,
            room_id=room.id,
            photo_path="p.jpg",
            last_watered_at=last_watered,
            next_due_at=last_watered + dt.timedelta(days=10),  # January dormancy factor
        )
        session.add(plant)
        session.commit()
        return plant.id, last_watered


def test_dry_run_should_not_modify_the_database(tmp_path) -> None:
    db_path = str(tmp_path / "test.sqlite3")
    plant_id, last_watered = _seed(db_path)
    original_due = last_watered + dt.timedelta(days=10)

    now = dt.datetime(2026, 5, 1, 9, 0, tzinfo=dt.timezone.utc)
    rooms, plants = preview_climate_cadence(db_path=db_path, hemisphere="northern", apply=False, now=now)

    assert len(plants) == 1
    assert plants[0].current_next_due_at == original_due
    assert plants[0].proposed_next_due_at == last_watered + dt.timedelta(days=7)

    engine = create_db_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        plant = session.get(Plant, plant_id)
        assert plant.next_due_at == original_due  # unchanged — dry run only


def test_apply_should_commit_the_recompute(tmp_path) -> None:
    db_path = str(tmp_path / "test.sqlite3")
    plant_id, last_watered = _seed(db_path)

    now = dt.datetime(2026, 5, 1, 9, 0, tzinfo=dt.timezone.utc)
    preview_climate_cadence(db_path=db_path, hemisphere="northern", apply=True, now=now)

    engine = create_db_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        plant = session.get(Plant, plant_id)
        assert plant.next_due_at == last_watered + dt.timedelta(days=7)


def test_room_without_sensors_reports_factor_1(tmp_path) -> None:
    db_path = str(tmp_path / "test.sqlite3")
    _seed(db_path)

    now = dt.datetime(2026, 5, 1, 9, 0, tzinfo=dt.timezone.utc)
    rooms, _plants = preview_climate_cadence(db_path=db_path, hemisphere="northern", apply=False, now=now)

    assert len(rooms) == 1
    assert rooms[0].factor == 1.0
