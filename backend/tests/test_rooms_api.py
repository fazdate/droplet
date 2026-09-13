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


def test_room_out_should_include_climate_fields(client: TestClient) -> None:
    created = client.post("/api/rooms", json={"name": "Balcony"}).json()

    for field in (
        "temperature_entity_id",
        "humidity_entity_id",
        "climate_temp_c",
        "climate_humidity",
        "climate_vpd_kpa",
        "climate_updated_at",
    ):
        assert field in created
        assert created[field] is None


def test_should_set_climate_entities(client: TestClient) -> None:
    created = client.post("/api/rooms", json={"name": "Balcony"}).json()

    response = client.post(
        f"/api/rooms/{created['id']}/climate-entities",
        json={"temperature_entity_id": "sensor.balcony_temp", "humidity_entity_id": "sensor.balcony_humidity"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["temperature_entity_id"] == "sensor.balcony_temp"
    assert body["humidity_entity_id"] == "sensor.balcony_humidity"


def test_should_clear_climate_entities_with_null(client: TestClient) -> None:
    created = client.post("/api/rooms", json={"name": "Balcony"}).json()
    client.post(
        f"/api/rooms/{created['id']}/climate-entities",
        json={"temperature_entity_id": "sensor.balcony_temp", "humidity_entity_id": "sensor.balcony_humidity"},
    )

    response = client.post(
        f"/api/rooms/{created['id']}/climate-entities",
        json={"temperature_entity_id": None, "humidity_entity_id": None},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["temperature_entity_id"] is None
    assert body["humidity_entity_id"] is None


def test_should_reject_malformed_entity_id(client: TestClient) -> None:
    created = client.post("/api/rooms", json={"name": "Balcony"}).json()

    response = client.post(
        f"/api/rooms/{created['id']}/climate-entities",
        json={"temperature_entity_id": "not-an-entity-id", "humidity_entity_id": None},
    )

    assert response.status_code == 422


def test_should_404_when_setting_climate_entities_on_missing_room(client: TestClient) -> None:
    response = client.post(
        "/api/rooms/999/climate-entities",
        json={"temperature_entity_id": None, "humidity_entity_id": None},
    )

    assert response.status_code == 404


def test_room_summary_out_should_include_climate_fields(client: TestClient) -> None:
    created = client.post("/api/rooms", json={"name": "Balcony"}).json()
    client.post(
        f"/api/rooms/{created['id']}/climate-entities",
        json={"temperature_entity_id": "sensor.balcony_temp", "humidity_entity_id": "sensor.balcony_humidity"},
    )

    response = client.get("/api/rooms")

    assert response.status_code == 200
    balcony = next(r for r in response.json() if r["id"] == created["id"])
    assert balcony["temperature_entity_id"] == "sensor.balcony_temp"
    assert balcony["humidity_entity_id"] == "sensor.balcony_humidity"
