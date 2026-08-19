"""Tests for the pure watering service used by the plants/rooms routers."""

import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.orm import Base, Plant, Room, Species, WateringEvent
from app.services.watering import water_plant


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_should_update_plant_and_create_event_on_watering() -> None:
    with _session() as session:
        room = Room(name="Living room")
        species = Species(scientific_name="Monstera deliciosa", watering_interval_days=7, seasonal_profile="tropical")
        session.add_all([room, species])
        session.commit()
        plant = Plant(nickname="M1", species_id=species.id, room_id=room.id, photo_path="m1.jpg")
        session.add(plant)
        session.commit()

        now = dt.datetime(2026, 8, 17, 9, 0, tzinfo=dt.timezone.utc)
        event = water_plant(session, plant, now=now, source="app_single", hemisphere="northern")
        session.commit()

        assert plant.last_watered_at == now
        # tropical peak factor 0.95 * 7 = round(6.65) = 7
        assert plant.next_due_at == now + dt.timedelta(days=7)
        assert event.source == "app_single"
        assert session.query(WateringEvent).count() == 1


def test_should_respect_plant_interval_override_and_seasonal_opt_out() -> None:
    with _session() as session:
        room = Room(name="Office")
        species = Species(scientific_name="Sansevieria", watering_interval_days=14, seasonal_profile="succulent")
        session.add_all([room, species])
        session.commit()
        plant = Plant(
            nickname="S1",
            species_id=species.id,
            room_id=room.id,
            photo_path="s1.jpg",
            watering_interval_days_override=5,
            seasonal_adjust_enabled=False,
        )
        session.add(plant)
        session.commit()

        now = dt.datetime(2026, 1, 15, 9, 0, tzinfo=dt.timezone.utc)
        water_plant(session, plant, now=now, source="manual", hemisphere="northern")

        assert plant.next_due_at == now + dt.timedelta(days=5)
