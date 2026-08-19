"""Tests for app.scheduler: wiring run_notification_tick into APScheduler."""

import datetime as dt
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.orm import Base
from app.scheduler import build_scheduler, make_tick_callable
from app.services.settings_store import get_last_notification_error, set_last_notification_error


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


def test_build_scheduler_registers_30_minute_job(monkeypatch) -> None:
    settings = _settings(monkeypatch)
    session_factory = MagicMock()

    scheduler = build_scheduler(session_factory=session_factory, settings=settings)

    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.id == "notification_tick"
    assert job.trigger.interval == dt.timedelta(minutes=30)


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
