"""Tests for SQLAlchemy models: schema, defaults, relationships."""

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.orm import Base, Plant, Room, Species, WateringEvent


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_should_create_room_with_defaults(session: Session) -> None:
    room = Room(name="Living room")
    session.add(room)
    session.commit()

    assert room.id is not None
    assert room.name == "Living room"
    assert room.sort_order == 0


def test_should_create_species_with_required_fields_and_source_default(session: Session) -> None:
    species = Species(
        scientific_name="Monstera deliciosa",
        common_name="Swiss cheese plant",
        watering_interval_days=7,
    )
    session.add(species)
    session.commit()

    assert species.id is not None
    assert species.source == "manual"
    assert species.reference_image_url is None
    assert species.seasonal_profile == "temperate"


def test_should_create_plant_linked_to_species_and_room(session: Session) -> None:
    room = Room(name="Bedroom")
    species = Species(scientific_name="Sansevieria trifasciata", watering_interval_days=14)
    session.add_all([room, species])
    session.commit()

    plant = Plant(
        nickname="Snakey",
        species_id=species.id,
        room_id=room.id,
        photo_path="photos/snakey.jpg",
    )
    session.add(plant)
    session.commit()

    assert plant.id is not None
    assert plant.watering_interval_days_override is None
    assert plant.seasonal_adjust_enabled is True
    assert plant.last_watered_at is None
    assert plant.next_due_at is None
    assert plant.snoozed_until is None
    assert plant.species.scientific_name == "Sansevieria trifasciata"
    assert plant.room.name == "Bedroom"


def test_should_record_watering_event_with_source(session: Session) -> None:
    room = Room(name="Kitchen")
    species = Species(scientific_name="Chlorophytum comosum", watering_interval_days=7)
    session.add_all([room, species])
    session.commit()
    plant = Plant(nickname="Spider", species_id=species.id, room_id=room.id, photo_path="p.jpg")
    session.add(plant)
    session.commit()

    event = WateringEvent(
        plant_id=plant.id,
        watered_at=dt.datetime(2026, 8, 17, 9, 0, tzinfo=dt.timezone.utc),
        source="app_single",
    )
    session.add(event)
    session.commit()

    assert event.id is not None
    assert event.plant.nickname == "Spider"


def test_should_cascade_delete_plant_watering_events_when_plant_deleted(session: Session) -> None:
    room = Room(name="Office")
    species = Species(scientific_name="Epipremnum aureum", watering_interval_days=7)
    session.add_all([room, species])
    session.commit()
    plant = Plant(nickname="Pothos", species_id=species.id, room_id=room.id, photo_path="p.jpg")
    session.add(plant)
    session.commit()
    event = WateringEvent(plant_id=plant.id, watered_at=dt.datetime.now(dt.timezone.utc), source="manual")
    session.add(event)
    session.commit()

    session.delete(plant)
    session.commit()

    assert session.query(WateringEvent).filter_by(id=event.id).first() is None
