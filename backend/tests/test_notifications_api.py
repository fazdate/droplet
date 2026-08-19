"""Tests for snooze/away/ha-action endpoints — plan sections 4.3, 4.8, 4.9."""

import datetime as dt

from fastapi.testclient import TestClient
from freezegun import freeze_time
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.clients.ha import HomeAssistantClient
from app.config import Settings
from app.db import create_db_engine, init_db
from app.main import create_app
from app.models.orm import Plant, Room, Species, WateringEvent
from app.services.settings_store import get_away_until


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


def test_should_snooze_plant_for_given_days(client: TestClient, engine: Engine, frozen_now: dt.datetime) -> None:
    plant_id = _seed_plant(engine)

    with freeze_time(frozen_now):
        response = client.post(f"/api/plants/{plant_id}/snooze", json={"days": 2})

    assert response.status_code == 200
    with Session(engine) as session:
        plant = session.get(Plant, plant_id)
        assert plant.snoozed_until == frozen_now + dt.timedelta(days=2)


def test_should_snooze_plant_for_given_minutes(client: TestClient, engine: Engine, frozen_now: dt.datetime) -> None:
    plant_id = _seed_plant(engine)

    with freeze_time(frozen_now):
        response = client.post(f"/api/plants/{plant_id}/snooze", json={"minutes": 1})

    assert response.status_code == 200
    with Session(engine) as session:
        plant = session.get(Plant, plant_id)
        assert plant.snoozed_until == frozen_now + dt.timedelta(minutes=1)


def test_should_reject_snooze_payload_when_days_and_minutes_both_set(client: TestClient, engine: Engine) -> None:
    plant_id = _seed_plant(engine)
    response = client.post(f"/api/plants/{plant_id}/snooze", json={"days": 1, "minutes": 1})
    assert response.status_code == 422


def test_should_404_when_snoozing_missing_plant(client: TestClient) -> None:
    response = client.post("/api/plants/999/snooze", json={"days": 1})

    assert response.status_code == 404


def test_should_set_away_until_from_days(client: TestClient, engine: Engine, frozen_now: dt.datetime) -> None:
    with freeze_time(frozen_now):
        response = client.post("/api/away", json={"days": 3})

    assert response.status_code == 200
    with Session(engine) as session:
        assert get_away_until(session) == frozen_now + dt.timedelta(days=3)


def test_should_set_away_until_from_explicit_date(client: TestClient, engine: Engine) -> None:
    until = "2026-09-01T00:00:00Z"

    response = client.post("/api/away", json={"until": until})

    assert response.status_code == 200
    with Session(engine) as session:
        assert get_away_until(session) == dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)


def test_should_clear_away_when_days_and_until_both_omitted(client: TestClient, engine: Engine) -> None:
    with Session(engine) as session:
        from app.services.settings_store import set_away_until

        set_away_until(session, dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc))
        session.commit()

    response = client.post("/api/away", json={})

    assert response.status_code == 200
    with Session(engine) as session:
        assert get_away_until(session) is None


def test_should_reject_ha_action_without_valid_secret(client: TestClient) -> None:
    response = client.post("/api/ha/action", json={"action": "WATERED_1"})

    assert response.status_code == 401


def test_should_water_plant_via_ha_action_watered(client: TestClient, engine: Engine, frozen_now: dt.datetime) -> None:
    plant_id = _seed_plant(engine, next_due_at=frozen_now - dt.timedelta(days=1))

    with freeze_time(frozen_now):
        response = client.post(
            "/api/ha/action",
            json={"action": f"WATERED_{plant_id}"},
            headers={"X-Webhook-Secret": "x"},
        )

    assert response.status_code == 200
    with Session(engine) as session:
        plant = session.get(Plant, plant_id)
        assert plant.last_watered_at == frozen_now
        assert session.query(WateringEvent).filter_by(plant_id=plant_id, source="notification").count() == 1


def test_should_water_room_via_ha_action_watered_room(client: TestClient, engine: Engine, frozen_now: dt.datetime) -> None:
    plant_id = _seed_plant(engine)
    with Session(engine) as session:
        room_id = session.get(Plant, plant_id).room_id

    with freeze_time(frozen_now):
        response = client.post(
            "/api/ha/action",
            json={"action": f"WATERED_ROOM_{room_id}"},
            headers={"X-Webhook-Secret": "x"},
        )

    assert response.status_code == 200
    with Session(engine) as session:
        assert session.get(Plant, plant_id).last_watered_at == frozen_now


def test_should_snooze_plant_1d_via_ha_action(client: TestClient, engine: Engine, frozen_now: dt.datetime) -> None:
    plant_id = _seed_plant(engine)

    with freeze_time(frozen_now):
        response = client.post(
            "/api/ha/action",
            json={"action": f"SNOOZE_1D_{plant_id}"},
            headers={"X-Webhook-Secret": "x"},
        )

    assert response.status_code == 200
    with Session(engine) as session:
        assert session.get(Plant, plant_id).snoozed_until == frozen_now + dt.timedelta(days=1)


def test_should_snooze_plant_1m_via_ha_action(client: TestClient, engine: Engine, frozen_now: dt.datetime) -> None:
    plant_id = _seed_plant(engine)

    with freeze_time(frozen_now):
        response = client.post(
            "/api/ha/action",
            json={"action": f"SNOOZE_1M_{plant_id}"},
            headers={"X-Webhook-Secret": "x"},
        )

    assert response.status_code == 200
    with Session(engine) as session:
        assert session.get(Plant, plant_id).snoozed_until == frozen_now + dt.timedelta(minutes=1)


def test_should_set_away_3d_via_ha_action(client: TestClient, engine: Engine, frozen_now: dt.datetime) -> None:
    with freeze_time(frozen_now):
        response = client.post(
            "/api/ha/action",
            json={"action": "AWAY_3D"},
            headers={"X-Webhook-Secret": "x"},
        )

    assert response.status_code == 200
    with Session(engine) as session:
        assert get_away_until(session) == frozen_now + dt.timedelta(days=3)


def test_should_reject_unknown_ha_action(client: TestClient) -> None:
    response = client.post("/api/ha/action", json={"action": "BOGUS"}, headers={"X-Webhook-Secret": "x"})

    assert response.status_code == 400


def test_should_clear_notification_tag_when_single_plant_action_is_applied(
    monkeypatch, tmp_path, frozen_now: dt.datetime
) -> None:
    monkeypatch.setenv("AI_API_KEY", "x")
    monkeypatch.setenv("HA_BASE_URL", "http://ha.local")
    monkeypatch.setenv("HA_LONG_LIVED_TOKEN", "x")
    monkeypatch.setenv("HA_WEBHOOK_SECRET", "x")
    monkeypatch.setenv("NOTIFY_TARGETS", "mobile_app_phone1")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("PHOTOS_DIR", str(tmp_path / "photos"))
    settings = Settings()
    engine = create_db_engine(f"sqlite:///{settings.db_path}")
    init_db(engine)
    app = create_app(settings=settings, engine=engine)
    client = TestClient(app)
    plant_id = _seed_plant(engine, next_due_at=frozen_now - dt.timedelta(days=1))

    cleared_tags: list[tuple[list[str], str]] = []

    def fake_clear_notification(self, *, targets: list[str], tag: str) -> None:
        cleared_tags.append((targets, tag))

    monkeypatch.setattr(HomeAssistantClient, "clear_notification", fake_clear_notification)

    with freeze_time(frozen_now):
        response = client.post(
            "/api/ha/action",
            json={"action": f"WATERED_{plant_id}", "tag": f"plant-{plant_id}"},
            headers={"X-Webhook-Secret": "x"},
        )

    assert response.status_code == 200
    assert cleared_tags == [(["mobile_app_phone1"], f"plant-{plant_id}")]
