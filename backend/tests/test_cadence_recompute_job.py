"""Tests for app.services.cadence_recompute.run_cadence_recompute —
CLIMATE_CADENCE_PLAN.md phase 3."""

import datetime as dt

from freezegun import freeze_time
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.orm import Base, Plant, Room, Species
from app.services.cadence_recompute import run_cadence_recompute


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_plant(session: Session, room: Room, species: Species, **overrides) -> Plant:
    plant = Plant(nickname="Plant", species_id=species.id, room_id=room.id, photo_path="p.jpg", **overrides)
    session.add(plant)
    session.commit()
    return plant


def test_should_use_current_month_not_last_watered_month() -> None:
    """A plant watered in January (dormancy, factor 1.4) should be recomputed
    using May's factor (shoulder, 1.0) when the job runs in May — the latent
    bug the plan calls out in the old _recompute_next_due."""
    with _session() as session:
        room = Room(name="Kitchen")
        species = Species(scientific_name="Ficus", watering_interval_days=7, seasonal_profile="temperate")
        session.add_all([room, species])
        session.commit()
        last_watered = dt.datetime(2026, 1, 10, 9, 0, tzinfo=dt.timezone.utc)
        plant = _seed_plant(
            session,
            room,
            species,
            last_watered_at=last_watered,
            next_due_at=last_watered + dt.timedelta(days=10),  # 7 * 1.4 (January factor)
        )

        now = dt.datetime(2026, 5, 15, 9, 0, tzinfo=dt.timezone.utc)
        run_cadence_recompute(session, now=now, hemisphere="northern")

        session.refresh(plant)
        assert plant.next_due_at == last_watered + dt.timedelta(days=7)  # May shoulder factor 1.0


def test_should_suppress_moves_under_12_hours() -> None:
    with _session() as session:
        room = Room(name="Kitchen")
        species = Species(scientific_name="Ficus", watering_interval_days=7, seasonal_profile="temperate")
        session.add_all([room, species])
        session.commit()
        last_watered = dt.datetime(2026, 5, 1, 9, 0, tzinfo=dt.timezone.utc)
        original_due = last_watered + dt.timedelta(days=7, hours=5)  # would move by only 5h if recomputed
        plant = _seed_plant(session, room, species, last_watered_at=last_watered, next_due_at=original_due)

        now = dt.datetime(2026, 5, 5, 9, 0, tzinfo=dt.timezone.utc)
        run_cadence_recompute(session, now=now, hemisphere="northern")

        session.refresh(plant)
        assert plant.next_due_at == original_due


def test_should_apply_moves_of_12_hours_or_more() -> None:
    with _session() as session:
        room = Room(name="Kitchen")
        species = Species(scientific_name="Ficus", watering_interval_days=7, seasonal_profile="temperate")
        session.add_all([room, species])
        session.commit()
        last_watered = dt.datetime(2026, 1, 1, 9, 0, tzinfo=dt.timezone.utc)
        # Seed with a due date far off from what May's factor would compute (7 days)
        original_due = last_watered + dt.timedelta(days=10)
        plant = _seed_plant(session, room, species, last_watered_at=last_watered, next_due_at=original_due)

        now = dt.datetime(2026, 5, 1, 9, 0, tzinfo=dt.timezone.utc)
        run_cadence_recompute(session, now=now, hemisphere="northern")

        session.refresh(plant)
        assert plant.next_due_at == last_watered + dt.timedelta(days=7)


def test_should_not_touch_last_notified_at_or_snoozed_until() -> None:
    with _session() as session:
        room = Room(name="Kitchen")
        species = Species(scientific_name="Ficus", watering_interval_days=7, seasonal_profile="temperate")
        session.add_all([room, species])
        session.commit()
        last_watered = dt.datetime(2026, 1, 1, 9, 0, tzinfo=dt.timezone.utc)
        last_notified = dt.datetime(2026, 6, 30, 9, 0, tzinfo=dt.timezone.utc)
        snoozed_until = dt.datetime(2026, 7, 2, 9, 0, tzinfo=dt.timezone.utc)
        plant = _seed_plant(
            session,
            room,
            species,
            last_watered_at=last_watered,
            next_due_at=last_watered + dt.timedelta(days=10),
            last_notified_at=last_notified,
            snoozed_until=snoozed_until,
        )

        now = dt.datetime(2026, 7, 1, 9, 0, tzinfo=dt.timezone.utc)
        run_cadence_recompute(session, now=now, hemisphere="northern")

        session.refresh(plant)
        assert plant.last_watered_at == last_watered
        assert plant.last_notified_at == last_notified
        assert plant.snoozed_until == snoozed_until


def test_should_skip_plants_never_watered() -> None:
    with _session() as session:
        room = Room(name="Kitchen")
        species = Species(scientific_name="Ficus", watering_interval_days=7, seasonal_profile="temperate")
        session.add_all([room, species])
        session.commit()
        plant = _seed_plant(session, room, species, last_watered_at=None, next_due_at=None)

        now = dt.datetime(2026, 7, 1, 9, 0, tzinfo=dt.timezone.utc)
        run_cadence_recompute(session, now=now, hemisphere="northern")

        session.refresh(plant)
        assert plant.next_due_at is None


def test_should_leave_due_date_unchanged_for_room_without_sensors() -> None:
    with _session() as session:
        room = Room(name="Kitchen")  # no temperature_entity_id/humidity_entity_id
        species = Species(scientific_name="Ficus", watering_interval_days=7, seasonal_profile="temperate")
        session.add_all([room, species])
        session.commit()
        last_watered = dt.datetime(2026, 5, 1, 9, 0, tzinfo=dt.timezone.utc)
        original_due = last_watered + dt.timedelta(days=7)  # already matches shoulder-month, no-climate math
        plant = _seed_plant(session, room, species, last_watered_at=last_watered, next_due_at=original_due)

        now = dt.datetime(2026, 5, 10, 9, 0, tzinfo=dt.timezone.utc)
        run_cadence_recompute(session, now=now, hemisphere="northern")

        session.refresh(plant)
        assert plant.next_due_at == original_due
