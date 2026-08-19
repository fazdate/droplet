"""Tests for app.services.scheduler_job.run_notification_tick — plan section 4.8."""

import datetime as dt
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.orm import Base, Plant, Room, Species
from app.services.scheduler_job import run_notification_tick
from app.services.settings_store import set_away_until


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed(session: Session, *, room_name="Kitchen", n=1, next_due_at=None, **plant_overrides):
    room = session.query(Room).filter_by(name=room_name).first()
    if room is None:
        room = Room(name=room_name)
        session.add(room)
        session.commit()
    species = Species(scientific_name=f"Species{n}", watering_interval_days=7)
    session.add(species)
    session.commit()
    plant = Plant(
        nickname=f"Plant{n}",
        species_id=species.id,
        room_id=room.id,
        photo_path="p.jpg",
        next_due_at=next_due_at,
        **plant_overrides,
    )
    session.add(plant)
    session.commit()
    return plant


def test_should_send_per_plant_notification_and_stamp_last_notified_at() -> None:
    with _session() as session:
        now = dt.datetime(2026, 8, 17, 9, 30, tzinfo=dt.timezone.utc)
        plant = _seed(session, next_due_at=now - dt.timedelta(hours=1))
        ha_client = MagicMock()

        run_notification_tick(
            session,
            ha_client=ha_client,
            now=now,
            notify_targets=["mobile_app_phone1"],
            quiet_hours_start=22,
            quiet_hours_end=8,
            click_action="http://localhost:8080/",
        )

        ha_client.notify.assert_called_once()
        call_kwargs = ha_client.notify.call_args.kwargs
        assert call_kwargs["tag"] == f"plant-{plant.id}"
        assert call_kwargs["targets"] == ["mobile_app_phone1"]

        session.refresh(plant)
        assert plant.last_notified_at == now


def test_should_not_notify_when_away(monkeypatch=None) -> None:
    with _session() as session:
        now = dt.datetime(2026, 8, 17, 9, 30, tzinfo=dt.timezone.utc)
        _seed(session, next_due_at=now - dt.timedelta(hours=1))
        set_away_until(session, now + dt.timedelta(days=3))
        session.commit()
        ha_client = MagicMock()

        run_notification_tick(
            session,
            ha_client=ha_client,
            now=now,
            notify_targets=["mobile_app_phone1"],
            quiet_hours_start=22,
            quiet_hours_end=8,
            click_action="http://x",
        )

        ha_client.notify.assert_not_called()


def test_should_batch_room_when_multiple_plants_overdue() -> None:
    with _session() as session:
        now = dt.datetime(2026, 8, 17, 9, 30, tzinfo=dt.timezone.utc)
        room = Room(name="Kitchen")
        species = Species(scientific_name="S", watering_interval_days=7)
        session.add_all([room, species])
        session.commit()
        for i in range(2):
            session.add(
                Plant(
                    nickname=f"P{i}",
                    species_id=species.id,
                    room_id=room.id,
                    photo_path="p.jpg",
                    next_due_at=now - dt.timedelta(hours=1),
                )
            )
        session.commit()
        ha_client = MagicMock()

        run_notification_tick(
            session,
            ha_client=ha_client,
            now=now,
            notify_targets=["mobile_app_phone1"],
            quiet_hours_start=22,
            quiet_hours_end=8,
            click_action="http://x",
        )

        ha_client.notify.assert_called_once()
        assert ha_client.notify.call_args.kwargs["tag"] == f"room-{room.id}"


def test_should_not_notify_outside_due_window() -> None:
    with _session() as session:
        now = dt.datetime(2026, 8, 17, 9, 30, tzinfo=dt.timezone.utc)
        _seed(session, next_due_at=now + dt.timedelta(days=1))
        ha_client = MagicMock()

        run_notification_tick(
            session,
            ha_client=ha_client,
            now=now,
            notify_targets=["mobile_app_phone1"],
            quiet_hours_start=22,
            quiet_hours_end=8,
            click_action="http://x",
        )

        ha_client.notify.assert_not_called()


def test_should_respect_local_quiet_hours_when_timezone_name_given() -> None:
    with _session() as session:
        # 20:00 UTC is daytime by raw UTC hour, but 22:00 CEST (Europe/Budapest)
        # -> should be treated as quiet and skipped.
        now = dt.datetime(2026, 8, 17, 20, 0, tzinfo=dt.timezone.utc)
        _seed(session, next_due_at=now - dt.timedelta(hours=1))
        ha_client = MagicMock()

        run_notification_tick(
            session,
            ha_client=ha_client,
            now=now,
            notify_targets=["mobile_app_phone1"],
            quiet_hours_start=22,
            quiet_hours_end=8,
            click_action="http://x",
            timezone_name="Europe/Budapest",
        )

        ha_client.notify.assert_not_called()
