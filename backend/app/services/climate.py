"""Climate polling and per-room cadence factor lookup — CLIMATE_CADENCE_PLAN.md.

The impure boundary that keeps app.services.schedule free of DB/HTTP I/O:
this module reads Home Assistant sensors, maintains the smoothed per-room VPD
on the Room row, and exposes the resulting climate factor to the cadence
recompute job / presenters.
"""

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.ha import HomeAssistantClient
from app.models.orm import Room
from app.services.schedule import climate_factor_from_vpd, smooth_reading, vapor_pressure_deficit_kpa

LOG = logging.getLogger(__name__)

_EWMA_TAU_SECONDS = 24 * 3600
# 12x the 30-min poll period — short relative to the 24h averaging window, so
# a room whose sensor dies drops out well before its stored average goes
# meaningfully stale.
_STALE_AFTER = dt.timedelta(hours=6)


def poll_room_climate(session: Session, *, ha_client: HomeAssistantClient, now: dt.datetime) -> None:
    """Reads both sensors for every room that has them configured, and folds
    a valid pair into the room's smoothed VPD.

    Both sensors must yield a valid sample for the VPD to be usable — a
    rejected sample (bad reading, or a per-entity HTTP failure) is skipped
    entirely, leaving the previous smoothed VPD untouched, so one
    `unavailable` doesn't erase 24h of accumulated data. No circuit breaker:
    this is a 30-minute background job over a handful of rooms, not a request
    path, so a per-entity try/except plus this module logger is the right size.
    """
    rooms = session.scalars(
        select(Room).where(Room.temperature_entity_id.is_not(None), Room.humidity_entity_id.is_not(None))
    ).all()

    for room in rooms:
        try:
            temp_c = ha_client.get_sensor_state(room.temperature_entity_id, kind="temperature")
            humidity = ha_client.get_sensor_state(room.humidity_entity_id, kind="humidity")
        except Exception:
            LOG.exception("Failed to read climate sensors for room %s", room.id)
            continue

        if temp_c is None or humidity is None:
            LOG.warning("Rejected climate sample for room %s (temp=%r, humidity=%r)", room.id, temp_c, humidity)
            continue

        sample_vpd = vapor_pressure_deficit_kpa(temp_c, humidity)
        elapsed_seconds = (
            (now - room.climate_updated_at).total_seconds() if room.climate_updated_at is not None else 0.0
        )
        room.climate_vpd_kpa = smooth_reading(
            previous=room.climate_vpd_kpa,
            sample=sample_vpd,
            elapsed_seconds=max(elapsed_seconds, 0.0),
            tau_seconds=_EWMA_TAU_SECONDS,
        )
        room.climate_temp_c = temp_c
        room.climate_humidity = humidity
        room.climate_updated_at = now

    session.flush()


def climate_factor_for_room(room: Room, now: dt.datetime) -> float:
    """Returns 1.0 (today's exact calendar-only math), never raises, when the
    room has no sensors configured, has never been polled successfully, or
    its reading has gone stale — the degradation path back to no-climate
    behavior."""
    if room.temperature_entity_id is None or room.humidity_entity_id is None:
        return 1.0
    if room.climate_updated_at is None or room.climate_vpd_kpa is None:
        return 1.0
    if now - room.climate_updated_at > _STALE_AFTER:
        return 1.0
    return climate_factor_from_vpd(room.climate_vpd_kpa)


def room_climate_factors(session: Session, *, now: dt.datetime) -> dict[int, float]:
    """One `select(Room)` for the whole batch, avoiding an N+1 in
    cadence_recompute's per-plant loop (`plant.room` is lazy)."""
    rooms = session.scalars(select(Room)).all()
    return {room.id: climate_factor_for_room(room, now) for room in rooms}
