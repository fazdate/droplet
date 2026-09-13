"""Tests for app.scheduler: wiring run_notification_tick into APScheduler."""

import datetime as dt
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.orm import Base
from app.scheduler import build_scheduler, make_cadence_recompute_callable, make_climate_poll_callable, make_tick_callable
from app.services.settings_store import (
    get_last_climate_error,
    get_last_notification_error,
    set_last_climate_error,
    set_last_notification_error,
)


def _settings(monkeypatch) -> Settings:
    monkeypatch.setenv("AI_API_KEY", "x")
    monkeypatch.setenv("HA_BASE_URL", "http://ha.local")
    monkeypatch.setenv("HA_LONG_LIVED_TOKEN", "x")
    monkeypatch.setenv("HA_WEBHOOK_SECRET", "x")
    monkeypatch.setenv("NOTIFY_TARGETS", "mobile_app_phone1")
    monkeypatch.setenv("TIMEZONE", "Europe/Budapest")
    return Settings()


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_make_tick_callable_invokes_run_notification_tick_with_fresh_session(monkeypatch) -> None:
    settings = _settings(monkeypatch)
    fake_session = MagicMock()
    session_factory = MagicMock(return_value=fake_session)
    ha_client = MagicMock()

    tick = make_tick_callable(session_factory=session_factory, ha_client=ha_client, settings=settings)

    import app.scheduler as scheduler_module

    called = {}

    def fake_run_notification_tick(session, **kwargs):
        called["session"] = session
        called["kwargs"] = kwargs
        return []

    monkeypatch.setattr(scheduler_module, "run_notification_tick", fake_run_notification_tick)

    tick()

    assert called["session"] is fake_session
    assert called["kwargs"]["ha_client"] is ha_client
    assert called["kwargs"]["notify_targets"] == ["mobile_app_phone1"]
    assert called["kwargs"]["quiet_hours_start"] == settings.quiet_hours_start
    assert called["kwargs"]["timezone_name"] == "Europe/Budapest"
    fake_session.close.assert_called_once()


def test_make_tick_callable_closes_session_even_on_error(monkeypatch) -> None:
    settings = _settings(monkeypatch)
    fake_session = MagicMock()
    session_factory = MagicMock(return_value=fake_session)
    ha_client = MagicMock()

    tick = make_tick_callable(session_factory=session_factory, ha_client=ha_client, settings=settings)

    import app.scheduler as scheduler_module

    def boom(session, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(scheduler_module, "run_notification_tick", boom)

    tick()  # should not raise — errors are logged, not propagated

    fake_session.close.assert_called_once()


def _cron_field(trigger, name: str):
    return next(field for field in trigger.fields if field.name == name)


def test_build_scheduler_registers_all_three_jobs(monkeypatch) -> None:
    settings = _settings(monkeypatch)
    session_factory = MagicMock()

    scheduler = build_scheduler(session_factory=session_factory, settings=settings)

    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert set(jobs) == {"notification_tick", "climate_poll", "cadence_recompute"}
    assert jobs["notification_tick"].trigger.interval == dt.timedelta(minutes=30)
    assert jobs["climate_poll"].trigger.interval == dt.timedelta(minutes=30)
    assert str(_cron_field(jobs["cadence_recompute"].trigger, "hour")) == "3"


def test_tick_records_last_notification_error_on_ha_failure(monkeypatch) -> None:
    settings = _settings(monkeypatch)
    engine = _engine()
    session_factory = lambda: Session(engine)  # noqa: E731
    ha_client = MagicMock()

    tick = make_tick_callable(session_factory=session_factory, ha_client=ha_client, settings=settings)

    import app.scheduler as scheduler_module

    def boom(session, **kwargs):
        raise RuntimeError("401 Client Error: Unauthorized")

    monkeypatch.setattr(scheduler_module, "run_notification_tick", boom)

    tick()  # should not raise — errors are recorded, not propagated

    with Session(engine) as session:
        error = get_last_notification_error(session)
        assert error is not None
        assert error["message"] == "401 Client Error: Unauthorized"
        assert error["at"] is not None


def test_tick_clears_last_notification_error_after_a_successful_run(monkeypatch) -> None:
    settings = _settings(monkeypatch)
    engine = _engine()
    with Session(engine) as session:
        set_last_notification_error(
            session, message="boom", at=dt.datetime(2026, 8, 18, tzinfo=dt.timezone.utc)
        )
        session.commit()
    session_factory = lambda: Session(engine)  # noqa: E731
    ha_client = MagicMock()

    tick = make_tick_callable(session_factory=session_factory, ha_client=ha_client, settings=settings)

    import app.scheduler as scheduler_module

    monkeypatch.setattr(scheduler_module, "run_notification_tick", lambda session, **kwargs: [])

    tick()

    with Session(engine) as session:
        assert get_last_notification_error(session) is None


def test_climate_poll_tick_records_last_climate_error_on_failure(monkeypatch) -> None:
    engine = _engine()
    session_factory = lambda: Session(engine)  # noqa: E731
    ha_client = MagicMock()

    tick = make_climate_poll_callable(session_factory=session_factory, ha_client=ha_client)

    import app.scheduler as scheduler_module

    def boom(session, **kwargs):
        raise RuntimeError("HA unreachable")

    monkeypatch.setattr(scheduler_module, "poll_room_climate", boom)

    tick()  # should not raise

    with Session(engine) as session:
        error = get_last_climate_error(session)
        assert error is not None
        assert error["message"] == "HA unreachable"


def test_climate_poll_tick_clears_last_climate_error_after_success(monkeypatch) -> None:
    engine = _engine()
    with Session(engine) as session:
        set_last_climate_error(session, message="boom", at=dt.datetime(2026, 8, 18, tzinfo=dt.timezone.utc))
        session.commit()
    session_factory = lambda: Session(engine)  # noqa: E731
    ha_client = MagicMock()

    tick = make_climate_poll_callable(session_factory=session_factory, ha_client=ha_client)

    import app.scheduler as scheduler_module

    monkeypatch.setattr(scheduler_module, "poll_room_climate", lambda session, **kwargs: None)

    tick()

    with Session(engine) as session:
        assert get_last_climate_error(session) is None


def test_climate_poll_tick_does_not_touch_last_notification_error(monkeypatch) -> None:
    engine = _engine()
    with Session(engine) as session:
        set_last_notification_error(session, message="notification boom", at=dt.datetime(2026, 8, 18, tzinfo=dt.timezone.utc))
        session.commit()
    session_factory = lambda: Session(engine)  # noqa: E731
    ha_client = MagicMock()

    tick = make_climate_poll_callable(session_factory=session_factory, ha_client=ha_client)

    import app.scheduler as scheduler_module

    monkeypatch.setattr(scheduler_module, "poll_room_climate", lambda session, **kwargs: None)

    tick()

    with Session(engine) as session:
        assert get_last_notification_error(session)["message"] == "notification boom"


def test_cadence_recompute_tick_does_not_raise_on_failure(monkeypatch) -> None:
    settings = _settings(monkeypatch)
    engine = _engine()
    session_factory = lambda: Session(engine)  # noqa: E731

    tick = make_cadence_recompute_callable(session_factory=session_factory, settings=settings)

    import app.scheduler as scheduler_module

    def boom(session, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(scheduler_module, "run_cadence_recompute", boom)

    tick()  # should not raise — logged, not propagated


def test_cadence_recompute_tick_invokes_run_cadence_recompute_with_fresh_session(monkeypatch) -> None:
    settings = _settings(monkeypatch)
    fake_session = MagicMock()
    session_factory = MagicMock(return_value=fake_session)

    tick = make_cadence_recompute_callable(session_factory=session_factory, settings=settings)

    import app.scheduler as scheduler_module

    called = {}

    def fake_run_cadence_recompute(session, **kwargs):
        called["session"] = session
        called["kwargs"] = kwargs

    monkeypatch.setattr(scheduler_module, "run_cadence_recompute", fake_run_cadence_recompute)

    tick()

    assert called["session"] is fake_session
    assert called["kwargs"]["hemisphere"] == settings.hemisphere
    fake_session.close.assert_called_once()
