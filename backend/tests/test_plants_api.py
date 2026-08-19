"""Tests for /api/plants endpoints and watering/undo flows."""

import datetime as dt
import io
from pathlib import Path

from fastapi.testclient import TestClient
from freezegun import freeze_time
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.orm import Plant, Room, Species, WateringEvent


def _seed_room_species(engine: Engine) -> tuple[int, int]:
    with Session(engine) as session:
        room = Room(name="Living room")
        species = Species(scientific_name="Monstera deliciosa", watering_interval_days=7, seasonal_profile="tropical")
        session.add_all([room, species])
        session.commit()
        return room.id, species.id


def _seed_plant(engine: Engine, room_id: int, species_id: int, **overrides) -> int:
    with Session(engine) as session:
        plant = Plant(
            nickname=overrides.pop("nickname", "Monstera deliciosa"),
            species_id=species_id,
            room_id=room_id,
            photo_path=overrides.pop("photo_path", "photos/m1.jpg"),
            **overrides,
        )
        session.add(plant)
        session.commit()
        return plant.id


def test_should_list_plants_grouped_with_overdue_flag(client: TestClient, engine: Engine, frozen_now: dt.datetime) -> None:
    room_id, species_id = _seed_room_species(engine)
    overdue_id = _seed_plant(
        engine,
        room_id,
        species_id,
        nickname="Overdue",
        last_watered_at=frozen_now - dt.timedelta(days=10),
        next_due_at=frozen_now - dt.timedelta(days=3),
    )

    with freeze_time(frozen_now):
        response = client.get("/api/plants")

    assert response.status_code == 200
    plants = response.json()
    overdue = next(p for p in plants if p["id"] == overdue_id)
    assert overdue["is_overdue"] is True
    assert overdue["room_name"] == "Living room"
    assert overdue["species_common_name"] is None


def test_should_expose_species_care_instructions_on_plant(client: TestClient, engine: Engine, frozen_now: dt.datetime) -> None:
    with Session(engine) as session:
        room = Room(name="Living room")
        species = Species(
            scientific_name="Monstera deliciosa",
            watering_interval_days=7,
            seasonal_profile="tropical",
            light="Bright indirect light",
            soil="Well-draining potting mix",
            notes="Wipe leaves occasionally to keep them dust-free.",
            care_language="en",
        )
        session.add_all([room, species])
        session.commit()
        room_id, species_id = room.id, species.id
    plant_id = _seed_plant(engine, room_id, species_id)

    with freeze_time(frozen_now):
        response = client.get("/api/plants")

    plant = next(p for p in response.json() if p["id"] == plant_id)
    assert plant["light"] == "Bright indirect light"
    assert plant["soil"] == "Well-draining potting mix"
    assert plant["notes"] == "Wipe leaves occasionally to keep them dust-free."


def test_should_expose_null_care_instructions_when_species_lacks_them(
    client: TestClient, engine: Engine, frozen_now: dt.datetime
) -> None:
    room_id, species_id = _seed_room_species(engine)
    plant_id = _seed_plant(engine, room_id, species_id)

    with freeze_time(frozen_now):
        response = client.get("/api/plants")

    plant = next(p for p in response.json() if p["id"] == plant_id)
    assert plant["light"] is None
    assert plant["soil"] is None
    assert plant["notes"] is None


def test_should_404_when_watering_missing_plant(client: TestClient) -> None:
    response = client.post("/api/plants/999/water")

    assert response.status_code == 404


def test_should_water_single_plant_and_recompute_next_due(client: TestClient, engine: Engine, frozen_now: dt.datetime) -> None:
    room_id, species_id = _seed_room_species(engine)
    plant_id = _seed_plant(engine, room_id, species_id)

    with freeze_time(frozen_now):
        response = client.post(f"/api/plants/{plant_id}/water")

    assert response.status_code == 200
    body = response.json()
    assert body["plant_ids"] == [plant_id]
    assert "undo_token" in body

    with Session(engine) as session:
        plant = session.get(Plant, plant_id)
        assert plant.last_watered_at == frozen_now
        # tropical profile in August -> peak factor 0.95 * 7 = round(6.65) = 7
        assert plant.next_due_at == frozen_now + dt.timedelta(days=7)
        events = session.query(WateringEvent).filter_by(plant_id=plant_id).all()
        assert len(events) == 1
        assert events[0].source == "app_single"


def test_should_water_entire_room_with_single_undo_token(client: TestClient, engine: Engine, frozen_now: dt.datetime) -> None:
    room_id, species_id = _seed_room_species(engine)
    p1 = _seed_plant(engine, room_id, species_id, nickname="A", photo_path="a.jpg")
    p2 = _seed_plant(engine, room_id, species_id, nickname="B", photo_path="b.jpg")

    with freeze_time(frozen_now):
        response = client.post(f"/api/rooms/{room_id}/water")

    assert response.status_code == 200
    body = response.json()
    assert set(body["plant_ids"]) == {p1, p2}

    with Session(engine) as session:
        for pid in (p1, p2):
            plant = session.get(Plant, pid)
            assert plant.last_watered_at == frozen_now


def test_should_undo_watering_within_window(client: TestClient, engine: Engine, frozen_now: dt.datetime) -> None:
    room_id, species_id = _seed_room_species(engine)
    plant_id = _seed_plant(
        engine,
        room_id,
        species_id,
        last_watered_at=frozen_now - dt.timedelta(days=5),
        next_due_at=frozen_now + dt.timedelta(days=2),
    )

    with freeze_time(frozen_now):
        water_response = client.post(f"/api/plants/{plant_id}/water")
        token = water_response.json()["undo_token"]

        undo_response = client.post("/api/undo", json={"token": token})

    assert undo_response.status_code == 200
    assert undo_response.json()["restored_plant_ids"] == [plant_id]

    with Session(engine) as session:
        plant = session.get(Plant, plant_id)
        assert plant.last_watered_at == frozen_now - dt.timedelta(days=5)
        assert plant.next_due_at == frozen_now + dt.timedelta(days=2)
        assert session.query(WateringEvent).filter_by(plant_id=plant_id).count() == 0


def test_should_reject_undo_with_unknown_token(client: TestClient) -> None:
    response = client.post("/api/undo", json={"token": "does-not-exist"})

    assert response.status_code == 404


def test_should_reject_undo_after_5_minute_window(client: TestClient, engine: Engine, frozen_now: dt.datetime) -> None:
    room_id, species_id = _seed_room_species(engine)
    plant_id = _seed_plant(engine, room_id, species_id)

    with freeze_time(frozen_now):
        token = client.post(f"/api/plants/{plant_id}/water").json()["undo_token"]

    with freeze_time(frozen_now + dt.timedelta(minutes=6)):
        response = client.post("/api/undo", json={"token": token})

    assert response.status_code == 410


def test_should_delete_plant_and_its_watering_history(client: TestClient, engine: Engine, frozen_now: dt.datetime) -> None:
    room_id, species_id = _seed_room_species(engine)
    plant_id = _seed_plant(engine, room_id, species_id)

    with freeze_time(frozen_now):
        client.post(f"/api/plants/{plant_id}/water")

    response = client.delete(f"/api/plants/{plant_id}")

    assert response.status_code == 204
    with Session(engine) as session:
        assert session.get(Plant, plant_id) is None
        assert session.query(WateringEvent).filter_by(plant_id=plant_id).count() == 0

    listing = client.get("/api/plants")
    assert all(p["id"] != plant_id for p in listing.json())


def test_should_delete_plants_uploaded_photo_file(client: TestClient, engine: Engine, settings: Settings) -> None:
    room_id, species_id = _seed_room_species(engine)
    photos_dir = Path(settings.photos_dir)
    photos_dir.mkdir(parents=True, exist_ok=True)
    photo_path = photos_dir / "delete-me.jpg"
    photo_path.write_bytes(b"fake-image-bytes")
    plant_id = _seed_plant(engine, room_id, species_id, photo_path="delete-me.jpg")

    response = client.delete(f"/api/plants/{plant_id}")

    assert response.status_code == 204
    assert not photo_path.exists()


def test_should_404_when_deleting_missing_plant(client: TestClient) -> None:
    response = client.delete("/api/plants/999")

    assert response.status_code == 404


def test_should_replace_plant_photo_and_delete_old_file(
    client: TestClient, engine: Engine, settings: Settings
) -> None:
    room_id, species_id = _seed_room_species(engine)
    photos_dir = Path(settings.photos_dir)
    photos_dir.mkdir(parents=True, exist_ok=True)
    old_photo_path = photos_dir / "old.jpg"
    old_photo_path.write_bytes(b"old-image-bytes")
    plant_id = _seed_plant(engine, room_id, species_id, photo_path="old.jpg")

    files = {"photo": ("new.jpg", io.BytesIO(b"new-image-bytes"), "image/jpeg")}
    response = client.post(f"/api/plants/{plant_id}/photo", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["photo_path"] != "old.jpg"
    assert body["photo_path"].endswith(".jpg")
    assert not old_photo_path.exists()
    assert (photos_dir / body["photo_path"]).read_bytes() == b"new-image-bytes"

    with Session(engine) as session:
        assert session.get(Plant, plant_id).photo_path == body["photo_path"]


def test_should_404_when_updating_photo_of_missing_plant(client: TestClient) -> None:
    files = {"photo": ("new.jpg", io.BytesIO(b"new-image-bytes"), "image/jpeg")}

    response = client.post("/api/plants/999/photo", files=files)

    assert response.status_code == 404
