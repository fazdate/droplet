"""Tests for app.services.plants: room/species lookup-or-create + plant creation."""

import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.orm import Base, Room, Species
from app.services.plants import create_plant, find_or_create_room, find_or_create_species_manual


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_should_create_room_when_missing() -> None:
    with _session() as session:
        room = find_or_create_room(session, "Living room")

        assert room.id is not None
        assert session.query(Room).count() == 1


def test_should_reuse_existing_room_by_name() -> None:
    with _session() as session:
        first = find_or_create_room(session, "Living room")
        session.commit()

        second = find_or_create_room(session, "Living room")

        assert second.id == first.id
        assert session.query(Room).count() == 1


def test_should_create_manual_species_with_given_interval() -> None:
    with _session() as session:
        species = find_or_create_species_manual(
            session, name="My weird cactus", interval_days=20, seasonal_profile="succulent"
        )

        assert species.id is not None
        assert species.scientific_name == "My weird cactus"
        assert species.watering_interval_days == 20
        assert species.source == "manual"
        assert species.seasonal_profile == "succulent"


def test_should_reuse_existing_manual_species_by_name() -> None:
    with _session() as session:
        first = find_or_create_species_manual(session, name="My weird cactus", interval_days=20)
        session.commit()

        second = find_or_create_species_manual(session, name="My weird cactus", interval_days=999)

        assert second.id == first.id
        assert second.watering_interval_days == 20  # reused, not overwritten
        assert session.query(Species).count() == 1


def test_should_create_plant_due_immediately_with_no_watering_history() -> None:
    with _session() as session:
        room = find_or_create_room(session, "Kitchen")
        species = find_or_create_species_manual(session, name="Herb", interval_days=4)
        session.commit()
        now = dt.datetime(2026, 8, 17, 9, 0, tzinfo=dt.timezone.utc)

        plant = create_plant(
            session,
            nickname="Basil",
            room=room,
            species=species,
            photo_path="photos/basil.jpg",
            now=now,
        )

        assert plant.id is not None
        assert plant.last_watered_at is None
        assert plant.next_due_at == now
