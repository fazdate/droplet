"""Watering schedule logic — plan section 4.2/4.5.

Pure functions only: no DB, no I/O, fully unit-testable in isolation.
"""

import datetime as dt
import math

_PEAK_MONTHS = {6, 7, 8}
_SHOULDER_MONTHS = {4, 5, 9, 10}
_DORMANCY_MONTHS = {11, 12, 1, 2, 3}

# Climate-aware cadence (CLIMATE_CADENCE_PLAN.md) — VPD (vapor pressure
# deficit) is what actually drives evapotranspiration, not raw temp/humidity.
_VPD_REFERENCE_KPA = 1.24  # 21 °C / 50 %RH via Tetens — typical indoor room
_CLIMATE_EXPONENT = 0.5
_CLIMATE_FACTOR_MIN, _CLIMATE_FACTOR_MAX = 0.8, 1.25
_COMBINED_FACTOR_MIN, _COMBINED_FACTOR_MAX = 0.6, 2.5

# Per-species-profile factor for each season category. "temperate" values come
# straight from plan 4.5; the others are the classification buckets the
# LLM/Perenual enrichment step assigns a species to.
_PROFILE_FACTORS: dict[str, dict[str, float]] = {
    "temperate": {"peak": 0.85, "shoulder": 1.0, "dormancy": 1.4},
    "tropical": {"peak": 0.95, "shoulder": 1.0, "dormancy": 1.1},
    "succulent": {"peak": 0.7, "shoulder": 1.0, "dormancy": 2.5},
    "mediterranean": {"peak": 0.8, "shoulder": 1.0, "dormancy": 1.3},
}

_MIN_INTERVAL_DAYS = 2
_MAX_INTERVAL_DAYS = 60


def resolve_base_interval(species_interval_days: int, plant_override_days: int | None) -> int:
    """Per-plant override always wins; species recommendation is the fallback
    and is never mutated by the override (see plan 7.7)."""
    return plant_override_days if plant_override_days is not None else species_interval_days


def _season_category(month: int) -> str:
    if month in _PEAK_MONTHS:
        return "peak"
    if month in _SHOULDER_MONTHS:
        return "shoulder"
    return "dormancy"


def season_factor(month: int, profile: str, hemisphere: str) -> float:
    """Calendar-based seasonal multiplier for a species profile.

    Southern hemisphere is modelled by shifting the calendar by 6 months
    relative to the northern-hemisphere season table (so August there behaves
    like February in the north).
    """
    effective_month = month
    if hemisphere == "southern":
        effective_month = ((month - 1 + 6) % 12) + 1

    category = _season_category(effective_month)
    factors = _PROFILE_FACTORS.get(profile, _PROFILE_FACTORS["temperate"])
    return factors[category]


def saturation_vapor_pressure_kpa(temp_c: float) -> float:
    """Tetens' formula for saturation vapor pressure over water."""
    return 0.6108 * math.exp(17.27 * temp_c / (temp_c + 237.3))


def vapor_pressure_deficit_kpa(temp_c: float, relative_humidity: float) -> float:
    return saturation_vapor_pressure_kpa(temp_c) * (1 - relative_humidity / 100)


def climate_factor_from_vpd(vpd_kpa: float) -> float:
    """Higher VPD -> faster drying -> shorter interval -> factor < 1.

    Takes VPD rather than temperature/humidity directly because the caller is
    expected to pass the *smoothed mean of per-sample VPD* (see
    app.services.climate) rather than aggregate raw readings — VPD is
    exponential in temperature, so averaging temperature/humidity first and
    computing VPD from the means understates drying demand (Jensen's
    inequality). The 0.5 exponent damps the response since a room sensor is
    only a weak proxy for actual soil drying.
    """
    raw = (_VPD_REFERENCE_KPA / vpd_kpa) ** _CLIMATE_EXPONENT
    return max(_CLIMATE_FACTOR_MIN, min(_CLIMATE_FACTOR_MAX, raw))


def smooth_reading(previous: float | None, sample: float, elapsed_seconds: float, tau_seconds: float) -> float:
    """Time-aware EWMA so a missed poll doesn't distort the average, a restart
    doesn't reset it, and a momentary spike can't skew the cadence."""
    if previous is None:
        return sample
    alpha = 1 - math.exp(-elapsed_seconds / tau_seconds)
    return previous + alpha * (sample - previous)


def compute_effective_interval(
    base_interval_days: int,
    month: int,
    profile: str,
    hemisphere: str,
    seasonal_adjust_enabled: bool,
    climate_factor: float = 1.0,
) -> int:
    """`effective_interval = clamp(round(base_interval x season_factor(month) x climate_factor), 2, 60)`,
    or the raw base interval when the plant opted out of seasonal adjustment
    (which also serves as the per-plant climate opt-out — see
    CLIMATE_CADENCE_PLAN.md)."""
    if not seasonal_adjust_enabled:
        factor = 1.0
    else:
        season = season_factor(month=month, profile=profile, hemisphere=hemisphere)
        combined = season * climate_factor
        # _PROFILE_FACTORS dormancy already encodes "cooler, slower growth", so
        # multiplying it by a cool-humid climate factor would double-count the
        # same winter; capping here means climate can never push a plant past
        # what the calendar alone already allows at its most conservative.
        factor = max(_COMBINED_FACTOR_MIN, min(_COMBINED_FACTOR_MAX, combined))

    raw = round(base_interval_days * factor)
    return max(_MIN_INTERVAL_DAYS, min(_MAX_INTERVAL_DAYS, raw))


def compute_next_due_at(last_watered_at: dt.datetime, effective_interval_days: int) -> dt.datetime:
    return last_watered_at + dt.timedelta(days=effective_interval_days)
