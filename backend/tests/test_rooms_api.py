"""Tests for /api/rooms endpoints."""

import datetime as dt

from fastapi.testclient import TestClient
from freezegun import freeze_time
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.models.orm import Plant, Room, Species


def test_should_create_room(client: TestClient) -> None:
    response = client.post("/api/rooms", json={"name": "Living room"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Living room"
    assert body["id"] is not None


def test_should_reject_duplicate_room_name(client: TestClient) -> None:
    client.post("/api/rooms", json={"name": "Living room"})

    response = client.post("/api/rooms", json={"name": "Living room"})

    assert response.status_code == 409


def test_should_rename_room(client: TestClient) -> None:
    created = client.post("/api/rooms", json={"name": "Living room"}).json()

    response = client.post(f"/api/rooms/{created['id']}", json={"name": "Lounge"})

    assert response.status_code == 200
    assert response.json()["name"] == "Lounge"


def test_should_404_when_renaming_missing_room(client: TestClient) -> None:
    response = client.post("/api/rooms/999", json={"name": "X"})

    assert response.status_code == 404


def test_should_list_rooms_with_due_and_overdue_counts(client: TestClient, engine: Engine, frozen_now: dt.datetime) -> None:
    with Session(engine) as session:
        room = Room(name="Kitchen")
        species = Species(scientific_name="Ficus lyrata", watering_interval_days=7)
        session.add_all([room, species])
        session.commit()

        overdue_plant = Plant(
            nickname="Overdue Fig",
            species_id=species.id,
            room_id=room.id,
            photo_path="p1.jpg",
            last_watered_at=frozen_now - dt.timedelta(days=10),
            next_due_at=frozen_now - dt.timedelta(days=3),
        )
        due_soon_plant = Plant(
            nickname="Fine Fig",
            species_id=species.id,
            room_id=room.id,
            photo_path="p2.jpg",
            last_watered_at=frozen_now - dt.timedelta(days=1),
            next_due_at=frozen_now + dt.timedelta(days=6),
        )
        session.add_all([overdue_plant, due_soon_plant])
        session.commit()
        room_id = room.id

    with freeze_time(frozen_now):
        response = client.get("/api/rooms")

    assert response.status_code == 200
    rooms = response.json()
    kitchen = next(r for r in rooms if r["id"] == room_id)
    assert kitchen["plant_count"] == 2
    assert kitchen["overdue_count"] == 1


def test_should_delete_empty_room(client: TestClient, engine: Engine) -> None:
    created = client.post("/api/rooms", json={"name": "Empty room"}).json()

    response = client.delete(f"/api/rooms/{created['id']}")

    assert response.status_code == 204
    with Session(engine) as session:
        assert session.get(Room, created["id"]) is None


def test_should_404_when_deleting_missing_room(client: TestClient) -> None:
    response = client.delete("/api/rooms/999")

    assert response.status_code == 404


def test_should_reject_deleting_room_with_plants(client: TestClient, engine: Engine) -> None:
    with Session(engine) as session:
        room = Room(name="Living room")
        species = Species(scientific_name="Ficus lyrata", watering_interval_days=7)
        session.add_all([room, species])
        session.commit()
        session.add(Plant(nickname="Fig", species_id=species.id, room_id=room.id, photo_path="p1.jpg"))
        session.commit()
        room_id = room.id

    response = client.delete(f"/api/rooms/{room_id}")

    assert response.status_code == 409
    with Session(engine) as session:
        assert session.get(Room, room_id) is not None
