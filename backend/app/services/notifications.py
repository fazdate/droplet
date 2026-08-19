"""Notification escalation/quiet-hours decision logic — plan section 4.8.

Pure functions only; the scheduler/router layer wires these to the DB and the
Home Assistant client.
"""

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass

from app.languages import DEFAULT_LANGUAGE
from zoneinfo import ZoneInfo

from app.i18n import translate

_AM_SLOT_START_HOUR = 9
_PM_SLOT_START_HOUR = 18


def _to_local(when: dt.datetime, timezone_name: str) -> dt.datetime:
    """Converts a tz-aware (UTC) datetime to the household's local timezone so
    quiet-hours/escalation-slot hour-of-day and date comparisons match what
    the owner actually experiences, not the server's UTC clock."""
    return when.astimezone(ZoneInfo(timezone_name))


def is_quiet_hours(
    now: dt.datetime, quiet_hours_start: int, quiet_hours_end: int, timezone_name: str = "UTC"
) -> bool:
    """Quiet hours may wrap past midnight (e.g. 22 -> 8)."""
    hour = _to_local(now, timezone_name).hour
    if quiet_hours_start <= quiet_hours_end:
        return quiet_hours_start <= hour < quiet_hours_end
    return hour >= quiet_hours_start or hour < quiet_hours_end


def _escalation_slot(now: dt.datetime, next_due_at: dt.datetime, timezone_name: str = "UTC") -> tuple[dt.date, str]:
    """Identifies which "reminder slot" `now` falls into, relative to `next_due_at`:
    - "due": the (single) reminder on the due date, before 1 full day late.
    - "am"/"pm": the twice-daily slots (09:00, 18:00) once 1+ day late.
    Two datetimes in the same slot should not both trigger a send.
    """
    local_now = _to_local(now, timezone_name)
    if now - next_due_at < dt.timedelta(days=1):
        # Anchored to the due date itself (not now.date()) so this stays a
        # single stable slot for the whole "not yet 1 full day late" window,
        # even if a periodic check happens to run after local midnight.
        return (_to_local(next_due_at, timezone_name).date(), "due")
    if local_now.hour < _AM_SLOT_START_HOUR:
        return (local_now.date() - dt.timedelta(days=1), "pm")
    if local_now.hour < _PM_SLOT_START_HOUR:
        return (local_now.date(), "am")
    return (local_now.date(), "pm")


def should_notify_plant(
    *,
    next_due_at: dt.datetime | None,
    snoozed_until: dt.datetime | None,
    last_notified_at: dt.datetime | None,
    now: dt.datetime,
    away_until: dt.datetime | None,
    quiet_hours_start: int,
    quiet_hours_end: int,
    timezone_name: str = "UTC",
) -> bool:
    if next_due_at is None or now < next_due_at:
        return False
    if snoozed_until is not None and now < snoozed_until:
        return False
    if away_until is not None and now < away_until:
        return False
    if is_quiet_hours(now, quiet_hours_start, quiet_hours_end, timezone_name):
        return False
    if last_notified_at is None:
        return True
    return _escalation_slot(now, next_due_at, timezone_name) != _escalation_slot(
        last_notified_at, next_due_at, timezone_name
    )


@dataclass(frozen=True)
class NotificationJob:
    """One HA notify.* call worth of data: either a single-plant reminder or a
    room-batched reminder, per plan 4.8 ("send a per-plant notification only
    when a single plant is overdue")."""

    tag: str
    title: str
    message: str
    plant_ids: list[int]
    room_id: int


def group_into_notification_jobs(notifiable_plants: list[dict], language: str = DEFAULT_LANGUAGE) -> list[NotificationJob]:
    """`notifiable_plants` items need keys: id, room_id, room_name, nickname."""
    by_room: dict[int, list[dict]] = defaultdict(list)
    for plant in notifiable_plants:
        by_room[plant["room_id"]].append(plant)

    jobs: list[NotificationJob] = []
    for room_id, plants in by_room.items():
        room_name = plants[0]["room_name"]
        if len(plants) == 1:
            plant = plants[0]
            jobs.append(
                NotificationJob(
                    tag=f"plant-{plant['id']}",
                    title=translate("plant_title", language, nickname=plant["nickname"]),
                    message=translate("plant_message", language, nickname=plant["nickname"]),
                    plant_ids=[plant["id"]],
                    room_id=room_id,
                )
            )
        else:
            jobs.append(
                NotificationJob(
                    tag=f"room-{room_id}",
                    title=translate("room_title", language, room_name=room_name, count=len(plants)),
                    message=translate("room_message", language, room_name=room_name, count=len(plants)),
                    plant_ids=[p["id"] for p in plants],
                    room_id=room_id,
                )
            )
    return jobs
