"""Tests for app.services.climate: HA polling into the smoothed per-room VPD
and the resulting cadence factor lookup — CLIMATE_CADENCE_PLAN.md."""

import datetime as dt

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.models.orm import Base, Room
from app.services.climate import climate_factor_for_room, poll_room_climate, room_climate_factors
from app.services.schedule import vapor_pressure_deficit_kpa

NOW = dt.datetime(2026, 1, 15, 12, 0, tzinfo=dt.timezone.utc)


class FakeHaClient:
    """Stub matching HomeAssistantClient.get_sensor_state's signature, driven
    by a simple {entity_id: value_or_exception} map so tests don't need respx
    for a client that isn't making real HTTP calls."""

    def __init__(self, readings: dict[str, float | None | Exception]) -> None:
        self._readings = readings

    def get_sensor_state(self, entity_id: str, *, kind: str) -> float | None:
        value = self._readings.get(entity_id)
        if isinstance(value, Exception):
            raise value
        return value


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _configured_room(**overrides) -> Room:
    defaults = dict(
        name="Balcony",
        temperature_entity_id="sensor.balcony_temp",
        humidity_entity_id="sensor.balcony_humidity",
    )
    defaults.update(overrides)
    return Room(**defaults)


def test_climate_factor_for_room_should_be_1_when_unconfigured() -> None:
    room = Room(name="Kitchen")

    assert climate_factor_for_room(room, NOW) == 1.0


def test_climate_factor_for_room_should_be_1_when_never_polled() -> None:
    room = _configured_room()

    assert climate_factor_for_room(room, NOW) == 1.0


def test_climate_factor_for_room_should_be_1_when_stale_beyond_6_hours() -> None:
    room = _configured_room(
        climate_vpd_kpa=2.0, climate_updated_at=NOW - dt.timedelta(hours=6, minutes=1)
    )

    assert climate_factor_for_room(room, NOW) == 1.0


def test_climate_factor_for_room_should_use_smoothed_vpd_when_fresh() -> None:
    reference_vpd = vapor_pressure_deficit_kpa(21.0, 50.0)
    room = _configured_room(climate_vpd_kpa=reference_vpd, climate_updated_at=NOW - dt.timedelta(hours=1))

    assert climate_factor_for_room(room, NOW) == pytest.approx(1.0, abs=0.01)


def test_poll_room_climate_should_skip_rooms_without_both_entities() -> None:
    with _session() as session:
        room = Room(name="Kitchen")
        session.add(room)
        session.commit()

        poll_room_climate(session, ha_client=FakeHaClient({}), now=NOW)

        session.refresh(room)
        assert room.climate_vpd_kpa is None


def test_poll_room_climate_should_store_smoothed_vpd_and_display_values() -> None:
    with _session() as session:
        room = _configured_room()
        session.add(room)
        session.commit()

        ha_client = FakeHaClient({"sensor.balcony_temp": 21.0, "sensor.balcony_humidity": 50.0})
        poll_room_climate(session, ha_client=ha_client, now=NOW)

        session.refresh(room)
        assert room.climate_vpd_kpa == pytest.approx(vapor_pressure_deficit_kpa(21.0, 50.0))
        assert room.climate_temp_c == 21.0
        assert room.climate_humidity == 50.0
        assert room.climate_updated_at == NOW


def test_poll_room_climate_should_accept_sub_zero_balcony_reading() -> None:
    with _session() as session:
        room = _configured_room()
        session.add(room)
        session.commit()

        ha_client = FakeHaClient({"sensor.balcony_temp": -8.0, "sensor.balcony_humidity": 80.0})
        poll_room_climate(session, ha_client=ha_client, now=NOW)

        session.refresh(room)
        assert room.climate_vpd_kpa == pytest.approx(vapor_pressure_deficit_kpa(-8.0, 80.0))


def test_poll_room_climate_should_preserve_prior_vpd_when_one_sensor_unavailable() -> None:
    with _session() as session:
        prior_vpd = vapor_pressure_deficit_kpa(21.0, 50.0)
        room = _configured_room(climate_vpd_kpa=prior_vpd, climate_updated_at=NOW - dt.timedelta(minutes=30))
        session.add(room)
        session.commit()

        ha_client = FakeHaClient({"sensor.balcony_temp": 21.0, "sensor.balcony_humidity": None})
        poll_room_climate(session, ha_client=ha_client, now=NOW)

        session.refresh(room)
        assert room.climate_vpd_kpa == pytest.approx(prior_vpd)
        assert room.climate_updated_at == NOW - dt.timedelta(minutes=30)


def test_poll_room_climate_should_preserve_prior_vpd_on_sensor_read_error() -> None:
    with _session() as session:
        prior_vpd = vapor_pressure_deficit_kpa(21.0, 50.0)
        room = _configured_room(climate_vpd_kpa=prior_vpd, climate_updated_at=NOW - dt.timedelta(minutes=30))
        session.add(room)
        session.commit()

        ha_client = FakeHaClient(
            {"sensor.balcony_temp": RuntimeError("boom"), "sensor.balcony_humidity": 50.0}
        )
        poll_room_climate(session, ha_client=ha_client, now=NOW)

        session.refresh(room)
        assert room.climate_vpd_kpa == pytest.approx(prior_vpd)


def test_poll_room_climate_should_converge_on_mean_vpd_over_several_days_of_swing() -> None:
    """The case that motivated the design: alternating morning/afternoon
    samples should converge close to the mean of per-sample VPD, not the VPD
    of the mean readings (see the diurnal-swing regression test in
    test_schedule_service.py). With a 24h EWMA time constant, convergence
    from a cold start takes on the order of several tau, not a single day —
    5 days of alternation is enough to land within a couple percent."""
    with _session() as session:
        room = _configured_room()
        session.add(room)
        session.commit()

        morning = {"sensor.balcony_temp": 8.0, "sensor.balcony_humidity": 80.0}
        afternoon = {"sensor.balcony_temp": 24.0, "sensor.balcony_humidity": 40.0}

        now = NOW
        for i in range(48 * 5):  # 5 days of half-hour samples
            readings = morning if i % 2 == 0 else afternoon
            poll_room_climate(session, ha_client=FakeHaClient(readings), now=now)
            now += dt.timedelta(minutes=30)

        session.refresh(room)
        expected_mean_vpd = (
            vapor_pressure_deficit_kpa(8.0, 80.0) + vapor_pressure_deficit_kpa(24.0, 40.0)
        ) / 2
        assert room.climate_vpd_kpa == pytest.approx(expected_mean_vpd, rel=0.05)


def test_room_climate_factors_should_issue_a_single_query() -> None:
    with _session() as session:
        session.add_all(
            [
                _configured_room(name="A", climate_vpd_kpa=1.24, climate_updated_at=NOW),
                _configured_room(name="B"),
                Room(name="C"),
            ]
        )
        session.commit()

        query_count = 0

        def _count(*args, **kwargs) -> None:
            nonlocal query_count
            query_count += 1

        event.listen(session.bind, "before_cursor_execute", _count)
        try:
            factors = room_climate_factors(session, now=NOW)
        finally:
            event.remove(session.bind, "before_cursor_execute", _count)

        assert query_count == 1
        assert len(factors) == 3
