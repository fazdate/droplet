"""Tests for app.services.settings_store: DB-backed key/value settings."""

import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.orm import Base
from app.services.settings_store import (
    get_away_until,
    get_last_notification_error,
    set_away_until,
    set_last_notification_error,
)


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_should_return_none_when_away_until_not_set() -> None:
    with _session() as session:
        assert get_away_until(session) is None


def test_should_round_trip_away_until() -> None:
    with _session() as session:
        until = dt.datetime(2026, 9, 1, 0, 0, tzinfo=dt.timezone.utc)

        set_away_until(session, until)

        assert get_away_until(session) == until


def test_should_clear_away_until_when_set_to_none() -> None:
    with _session() as session:
        set_away_until(session, dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc))

        set_away_until(session, None)

        assert get_away_until(session) is None


def test_should_return_none_when_no_notification_error_recorded() -> None:
    with _session() as session:
        assert get_last_notification_error(session) is None


def test_should_round_trip_last_notification_error() -> None:
    with _session() as session:
        at = dt.datetime(2026, 8, 18, 9, 0, tzinfo=dt.timezone.utc)

        set_last_notification_error(session, message="401 Client Error: Unauthorized", at=at)

        assert get_last_notification_error(session) == {
            "message": "401 Client Error: Unauthorized",
            "at": at.isoformat(),
        }


def test_should_clear_last_notification_error_when_message_is_none() -> None:
    with _session() as session:
        set_last_notification_error(
            session, message="boom", at=dt.datetime(2026, 8, 18, tzinfo=dt.timezone.utc)
        )

        set_last_notification_error(session, message=None)

        assert get_last_notification_error(session) is None
