"""Watering schedule logic — plan section 4.2/4.5.

Pure functions only: no DB, no I/O, fully unit-testable in isolation.
"""

import datetime as dt

_PEAK_MONTHS = {6, 7, 8}
_SHOULDER_MONTHS = {4, 5, 9, 10}
_DORMANCY_MONTHS = {11, 12, 1, 2, 3}

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


def compute_effective_interval(
    base_interval_days: int,
    month: int,
    profile: str,
    hemisphere: str,
    seasonal_adjust_enabled: bool,
) -> int:
    """`effective_interval = clamp(round(base_interval x season_factor(month)), 2, 60)`,
    or the raw base interval when the plant opted out of seasonal adjustment."""
    if not seasonal_adjust_enabled:
        factor = 1.0
    else:
        factor = season_factor(month=month, profile=profile, hemisphere=hemisphere)

    raw = round(base_interval_days * factor)
    return max(_MIN_INTERVAL_DAYS, min(_MAX_INTERVAL_DAYS, raw))


def compute_next_due_at(last_watered_at: dt.datetime, effective_interval_days: int) -> dt.datetime:
    return last_watered_at + dt.timedelta(days=effective_interval_days)
