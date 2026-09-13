"""Tests for app.services.schedule: interval resolution and next-due calculation."""

import datetime as dt
import math

import pytest

from app.services.schedule import (
    climate_factor_from_vpd,
    compute_effective_interval,
    compute_next_due_at,
    resolve_base_interval,
    saturation_vapor_pressure_kpa,
    smooth_reading,
    vapor_pressure_deficit_kpa,
)


def test_should_use_species_interval_when_no_plant_override() -> None:
    assert resolve_base_interval(species_interval_days=7, plant_override_days=None) == 7


def test_should_prefer_plant_override_over_species_interval() -> None:
    assert resolve_base_interval(species_interval_days=7, plant_override_days=10) == 10


@pytest.mark.parametrize(
    "month,factor",
    [
        (6, 0.85),
        (7, 0.85),
        (8, 0.85),
        (4, 1.0),
        (5, 1.0),
        (9, 1.0),
        (10, 1.0),
        (11, 1.4),
        (12, 1.4),
        (1, 1.4),
        (2, 1.4),
        (3, 1.4),
    ],
)
def test_should_return_northern_hemisphere_season_factor_for_temperate_profile(month: int, factor: float) -> None:
    from app.services.schedule import season_factor

    assert season_factor(month=month, profile="temperate", hemisphere="northern") == pytest.approx(factor)


def test_should_invert_season_for_southern_hemisphere() -> None:
    from app.services.schedule import season_factor

    # August is peak growing season in the north (0.85) -> dormant-equivalent in the south.
    assert season_factor(month=8, profile="temperate", hemisphere="southern") == pytest.approx(1.4)
    assert season_factor(month=1, profile="temperate", hemisphere="southern") == pytest.approx(0.85)


def test_should_scale_succulent_winter_factor_higher_than_temperate() -> None:
    from app.services.schedule import season_factor

    assert season_factor(month=1, profile="succulent", hemisphere="northern") == pytest.approx(2.5)


def test_should_barely_change_tropical_profile_in_winter() -> None:
    from app.services.schedule import season_factor

    assert season_factor(month=1, profile="tropical", hemisphere="northern") == pytest.approx(1.1)


def test_should_compute_effective_interval_rounded_and_clamped() -> None:
    effective = compute_effective_interval(
        base_interval_days=7, month=1, profile="temperate", hemisphere="northern", seasonal_adjust_enabled=True
    )
    assert effective == 10  # round(7 * 1.4) = 10


def test_should_ignore_seasonal_factor_when_disabled_per_plant() -> None:
    effective = compute_effective_interval(
        base_interval_days=7, month=1, profile="temperate", hemisphere="northern", seasonal_adjust_enabled=False
    )
    assert effective == 7


def test_should_clamp_effective_interval_between_2_and_60() -> None:
    tiny = compute_effective_interval(
        base_interval_days=1, month=6, profile="temperate", hemisphere="northern", seasonal_adjust_enabled=True
    )
    huge = compute_effective_interval(
        base_interval_days=50, month=1, profile="succulent", hemisphere="northern", seasonal_adjust_enabled=True
    )
    assert tiny == 2
    assert huge == 60


def test_should_compute_next_due_at_from_last_watered_plus_effective_interval() -> None:
    last_watered = dt.datetime(2026, 1, 10, 9, 0, tzinfo=dt.timezone.utc)

    next_due = compute_next_due_at(last_watered_at=last_watered, effective_interval_days=10)

    assert next_due == dt.datetime(2026, 1, 20, 9, 0, tzinfo=dt.timezone.utc)


# --- Climate-aware cadence (CLIMATE_CADENCE_PLAN.md) ---


def test_should_compute_reference_vpd_at_21c_50rh() -> None:
    svp = saturation_vapor_pressure_kpa(21.0)
    vpd = vapor_pressure_deficit_kpa(21.0, 50.0)

    assert svp == pytest.approx(2.4875, abs=0.001)
    assert vpd == pytest.approx(1.24, abs=0.005)


def test_should_return_factor_1_at_reference_conditions() -> None:
    vpd = vapor_pressure_deficit_kpa(21.0, 50.0)

    assert climate_factor_from_vpd(vpd) == pytest.approx(1.0, abs=0.01)


def test_should_clamp_climate_factor_at_lower_bound_for_hot_dry_room() -> None:
    vpd = vapor_pressure_deficit_kpa(26.0, 35.0)

    assert climate_factor_from_vpd(vpd) == pytest.approx(0.8, abs=0.01)


def test_should_clamp_climate_factor_at_upper_bound_for_cool_humid_room() -> None:
    vpd = vapor_pressure_deficit_kpa(18.0, 70.0)

    assert climate_factor_from_vpd(vpd) == pytest.approx(1.25, abs=0.01)


@pytest.mark.parametrize(
    "temp_c,rh,expected_days",
    [
        (26.0, 35.0, 6),
        (21.0, 50.0, 7),
        (18.0, 70.0, 9),
    ],
)
def test_should_reproduce_worked_examples_at_base_7_days(temp_c: float, rh: float, expected_days: int) -> None:
    vpd = vapor_pressure_deficit_kpa(temp_c, rh)
    climate_factor = climate_factor_from_vpd(vpd)

    effective = compute_effective_interval(
        base_interval_days=7,
        month=5,  # shoulder month -> season_factor == 1.0, isolates the climate term
        profile="temperate",
        hemisphere="northern",
        seasonal_adjust_enabled=True,
        climate_factor=climate_factor,
    )

    assert effective == expected_days


def test_should_ignore_climate_factor_when_seasonal_adjust_disabled() -> None:
    effective = compute_effective_interval(
        base_interval_days=7,
        month=1,
        profile="temperate",
        hemisphere="northern",
        seasonal_adjust_enabled=False,
        climate_factor=0.8,
    )

    assert effective == 7


def test_should_default_climate_factor_to_1_and_reproduce_prior_behavior() -> None:
    effective = compute_effective_interval(
        base_interval_days=7, month=1, profile="temperate", hemisphere="northern", seasonal_adjust_enabled=True
    )

    assert effective == 10  # unchanged from the pre-climate test above


def test_should_cap_combined_season_and_climate_factor_at_2_5() -> None:
    # succulent dormancy (2.5) x a very humid climate factor (>1.25 pre-clamp
    # would already be capped at 1.25) would double-count winter beyond what
    # the calendar alone allows at its most conservative.
    effective = compute_effective_interval(
        base_interval_days=10,
        month=1,
        profile="succulent",
        hemisphere="northern",
        seasonal_adjust_enabled=True,
        climate_factor=1.25,
    )

    assert effective == 25  # round(10 * min(2.5*1.25, 2.5)) = round(10*2.5)


def test_should_still_clamp_final_interval_between_2_and_60_with_climate_factor() -> None:
    huge = compute_effective_interval(
        base_interval_days=50,
        month=1,
        profile="succulent",
        hemisphere="northern",
        seasonal_adjust_enabled=True,
        climate_factor=1.25,
    )

    assert huge == 60


def test_smooth_reading_should_return_sample_when_no_previous_value() -> None:
    assert smooth_reading(previous=None, sample=1.5, elapsed_seconds=1800, tau_seconds=86400) == 1.5


def test_smooth_reading_should_move_halfway_after_one_half_life() -> None:
    tau = 86400.0
    half_life_seconds = tau * math.log(2)

    result = smooth_reading(previous=1.0, sample=2.0, elapsed_seconds=half_life_seconds, tau_seconds=tau)

    assert result == pytest.approx(1.5, abs=0.001)


def test_smooth_reading_should_not_move_with_zero_elapsed_time() -> None:
    assert smooth_reading(previous=1.0, sample=2.0, elapsed_seconds=0, tau_seconds=86400) == pytest.approx(1.0)


def test_diurnal_swing_regression_should_average_vpd_not_temp_and_humidity() -> None:
    """This is the case that motivated the climate design (CLIMATE_CADENCE_PLAN.md):
    a swinging balcony sensor must be aggregated as the mean of per-sample VPD,
    never as VPD-of-the-mean-readings, or drying demand is understated ~38%."""
    morning_vpd = vapor_pressure_deficit_kpa(8.0, 80.0)
    afternoon_vpd = vapor_pressure_deficit_kpa(24.0, 40.0)
    mean_of_per_sample_vpd = (morning_vpd + afternoon_vpd) / 2

    assert mean_of_per_sample_vpd == pytest.approx(1.00, abs=0.02)
    assert climate_factor_from_vpd(mean_of_per_sample_vpd) == pytest.approx(1.11, abs=0.01)

    # Explicitly NOT the result of averaging the raw readings first.
    mean_temp = (8.0 + 24.0) / 2
    mean_rh = (80.0 + 40.0) / 2
    vpd_of_mean_readings = vapor_pressure_deficit_kpa(mean_temp, mean_rh)
    assert vpd_of_mean_readings == pytest.approx(0.73, abs=0.02)
    assert climate_factor_from_vpd(vpd_of_mean_readings) == pytest.approx(1.25, abs=0.01)
