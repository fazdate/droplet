"""Tests for app.services.schedule: interval resolution and next-due calculation."""

import datetime as dt

import pytest

from app.services.schedule import compute_effective_interval, compute_next_due_at, resolve_base_interval


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
