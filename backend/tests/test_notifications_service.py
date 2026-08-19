"""Tests for app.services.notifications: escalation/quiet-hours decision logic
and room-batching — plan section 4.8."""

import datetime as dt

import pytest

from app.services.notifications import is_quiet_hours, should_notify_plant


def _dt(*, day: int, hour: int, minute: int = 0, month: int = 8) -> dt.datetime:
    return dt.datetime(2026, month, day, hour, minute, tzinfo=dt.timezone.utc)


class TestIsQuietHours:
    def test_should_be_quiet_within_simple_range(self) -> None:
        assert is_quiet_hours(_dt(day=1, hour=23), quiet_hours_start=22, quiet_hours_end=8) is True

    def test_should_be_quiet_after_midnight_before_end(self) -> None:
        assert is_quiet_hours(_dt(day=1, hour=3), quiet_hours_start=22, quiet_hours_end=8) is True

    def test_should_not_be_quiet_during_the_day(self) -> None:
        assert is_quiet_hours(_dt(day=1, hour=14), quiet_hours_start=22, quiet_hours_end=8) is False

    def test_should_not_be_quiet_exactly_at_end_hour(self) -> None:
        assert is_quiet_hours(_dt(day=1, hour=8), quiet_hours_start=22, quiet_hours_end=8) is False

    def test_should_be_quiet_exactly_at_start_hour(self) -> None:
        assert is_quiet_hours(_dt(day=1, hour=22), quiet_hours_start=22, quiet_hours_end=8) is True

    def test_should_convert_utc_to_local_timezone_before_comparing(self) -> None:
        # 20:00 UTC == 22:00 CEST (Europe/Budapest, UTC+2 in August) -> quiet start.
        assert (
            is_quiet_hours(
                _dt(day=1, hour=20), quiet_hours_start=22, quiet_hours_end=8, timezone_name="Europe/Budapest"
            )
            is True
        )

    def test_should_not_be_quiet_in_local_morning_even_if_utc_hour_is_still_before_end(self) -> None:
        # 08:15 UTC == 10:15 CEST -> well past the local 08:00 end of quiet hours,
        # even though the raw UTC hour (8) would still look "quiet" without conversion.
        assert (
            is_quiet_hours(
                _dt(day=1, hour=8, minute=15),
                quiet_hours_start=22,
                quiet_hours_end=8,
                timezone_name="Europe/Budapest",
            )
            is False
        )


class TestShouldNotifyPlant:
    def _decide(self, **overrides) -> bool:
        defaults = dict(
            next_due_at=_dt(day=10, hour=9),
            snoozed_until=None,
            last_notified_at=None,
            now=_dt(day=10, hour=9),
            away_until=None,
            quiet_hours_start=22,
            quiet_hours_end=8,
        )
        defaults.update(overrides)
        return should_notify_plant(**defaults)

    def test_should_not_notify_when_not_yet_due(self) -> None:
        assert self._decide(now=_dt(day=9, hour=9)) is False

    def test_should_notify_on_first_check_after_due(self) -> None:
        assert self._decide(now=_dt(day=10, hour=9, minute=30)) is True

    def test_should_not_renotify_same_day_after_due_notification_sent(self) -> None:
        assert self._decide(now=_dt(day=10, hour=15), last_notified_at=_dt(day=10, hour=9)) is False

    def test_should_not_renotify_after_midnight_while_still_under_a_day_late(self) -> None:
        # Regression: due late on day 10 (e.g. afternoon), notified once that
        # day; checking again after local midnight on day 11 — while still
        # under 24h late overall — must not re-send the "due" reminder just
        # because the calendar date rolled over.
        assert (
            self._decide(
                next_due_at=_dt(day=10, hour=20),
                now=_dt(day=11, hour=10),
                last_notified_at=_dt(day=10, hour=20, minute=5),
            )
            is False
        )

    def test_should_not_notify_while_snoozed(self) -> None:
        assert self._decide(snoozed_until=_dt(day=11, hour=0), now=_dt(day=10, hour=12)) is False

    def test_should_notify_after_snooze_expires(self) -> None:
        assert self._decide(snoozed_until=_dt(day=10, hour=10), now=_dt(day=10, hour=11)) is True

    def test_should_not_notify_while_away(self) -> None:
        assert self._decide(away_until=_dt(day=15, hour=0), now=_dt(day=12, hour=9)) is False

    def test_should_not_notify_during_quiet_hours(self) -> None:
        assert self._decide(now=_dt(day=10, hour=23)) is False

    def test_should_notify_once_a_day_late_after_9am(self) -> None:
        # due day-10; a full day late means day-11 09:00 onward
        assert (
            self._decide(now=_dt(day=11, hour=9, minute=30), last_notified_at=_dt(day=10, hour=9)) is True
        )

    def test_should_not_renotify_within_same_am_slot(self) -> None:
        assert (
            self._decide(now=_dt(day=11, hour=9, minute=45), last_notified_at=_dt(day=11, hour=9)) is False
        )

    def test_should_notify_again_at_6pm_slot_same_late_day(self) -> None:
        assert (
            self._decide(now=_dt(day=11, hour=18, minute=0), last_notified_at=_dt(day=11, hour=9)) is True
        )

    def test_should_not_notify_a_third_time_same_day_after_pm_slot(self) -> None:
        assert (
            self._decide(now=_dt(day=11, hour=20), last_notified_at=_dt(day=11, hour=18)) is False
        )

    def test_should_notify_again_next_morning_am_slot(self) -> None:
        assert (
            self._decide(now=_dt(day=12, hour=9, minute=30), last_notified_at=_dt(day=11, hour=18)) is True
        )

    def test_should_return_false_when_next_due_at_is_none(self) -> None:
        assert self._decide(next_due_at=None) is False

    def test_should_respect_local_quiet_hours_via_timezone_name(self) -> None:
        # 20:00 UTC == 22:00 CEST, which is quiet in Europe/Budapest even
        # though 20:00 is not quiet under the default UTC interpretation.
        assert self._decide(now=_dt(day=10, hour=20), timezone_name="Europe/Budapest") is False
