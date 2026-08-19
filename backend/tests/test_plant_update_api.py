"""Tests for PATCH-style plant update + reset-to-recommended-interval endpoints
— plan section 4.3/4.6."""

import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.models.orm import Plant, Room, Species


def _seed_plant(engine: Engine, **overrides) -> int:
    with Session(engine) as session:
        room = Room(name="Kitchen")
        species = Species(scientific_name="Basil", watering_interval_days=4)
        session.add_all([room, species])
        session.commit()
        plant = Plant(
            nickname=overrides.pop("nickname", "Basil"),
            species_id=species.id,
            room_id=room.id,
            photo_path="p.jpg",
            **overrides,
        )
        session.add(plant)
        session.commit()
        return plant.id


def test_should_update_nickname(client: TestClient, engine: Engine) -> None:
    plant_id = _seed_plant(engine)

    response = client.post(f"/api/plants/{plant_id}", json={"nickname": "New name"})

    assert response.status_code == 200
    assert response.json()["nickname"] == "New name"


def test_should_mark_nickname_as_custom_after_rename(client: TestClient, engine: Engine) -> None:
    plant_id = _seed_plant(engine, nickname_is_custom=False)

    response = client.post(f"/api/plants/{plant_id}", json={"nickname": "New name"})

    assert response.status_code == 200
    assert response.json()["nickname_is_custom"] is True


def test_should_ignore_blank_nickname_on_update(client: TestClient, engine: Engine) -> None:
    plant_id = _seed_plant(engine, nickname="Basil", nickname_is_custom=False)

    response = client.post(f"/api/plants/{plant_id}", json={"nickname": "   "})

    assert response.status_code == 200
    body = response.json()
    assert body["nickname"] == "Basil"
    assert body["nickname_is_custom"] is False


def test_should_update_interval_override_and_recompute_next_due(
    client: TestClient, engine: Engine, frozen_now: dt.datetime
) -> None:
    from freezegun import freeze_time

    plant_id = _seed_plant(
        engine, last_watered_at=frozen_now - dt.timedelta(days=1), seasonal_adjust_enabled=False
    )

    with freeze_time(frozen_now):
        response = client.post(f"/api/plants/{plant_id}", json={"interval_override": 10})

    assert response.status_code == 200
    with Session(engine) as session:
        plant = session.get(Plant, plant_id)
        assert plant.watering_interval_days_override == 10
        assert plant.next_due_at == frozen_now - dt.timedelta(days=1) + dt.timedelta(days=10)


def test_should_move_plant_to_different_room(client: TestClient, engine: Engine) -> None:
    plant_id = _seed_plant(engine)
    with Session(engine) as session:
        new_room = Room(name="Bedroom")
        session.add(new_room)
        session.commit()
        new_room_id = new_room.id

    response = client.post(f"/api/plants/{plant_id}", json={"room_id": new_room_id})

    assert response.status_code == 200
    assert response.json()["room_id"] == new_room_id


def test_should_toggle_seasonal_adjust(client: TestClient, engine: Engine) -> None:
    plant_id = _seed_plant(engine)

    response = client.post(f"/api/plants/{plant_id}", json={"seasonal_adjust_enabled": False})

    assert response.status_code == 200
    assert response.json()["seasonal_adjust_enabled"] is False


def test_should_404_when_patching_missing_plant(client: TestClient) -> None:
    response = client.post("/api/plants/999", json={"nickname": "x"})

    assert response.status_code == 404


def test_should_reset_interval_override_and_recompute_next_due(
    client: TestClient, engine: Engine, frozen_now: dt.datetime
) -> None:
    from freezegun import freeze_time

    plant_id = _seed_plant(
        engine,
        watering_interval_days_override=99,
        last_watered_at=frozen_now - dt.timedelta(days=1),
        seasonal_adjust_enabled=False,
    )

    with freeze_time(frozen_now):
        response = client.delete(f"/api/plants/{plant_id}/interval-override")

    assert response.status_code == 200
    with Session(engine) as session:
        plant = session.get(Plant, plant_id)
        assert plant.watering_interval_days_override is None
        # falls back to species interval (4 days)
        assert plant.next_due_at == frozen_now - dt.timedelta(days=1) + dt.timedelta(days=4)


def test_should_404_when_resetting_missing_plant(client: TestClient) -> None:
    response = client.delete("/api/plants/999/interval-override")

    assert response.status_code == 404


def test_should_noop_when_resetting_plant_with_no_override(client: TestClient, engine: Engine) -> None:
    plant_id = _seed_plant(engine)

    response = client.delete(f"/api/plants/{plant_id}/interval-override")

    assert response.status_code == 200
    assert response.json()["watering_interval_days_override"] is None
