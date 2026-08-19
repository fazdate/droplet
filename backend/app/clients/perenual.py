"""Perenual API v2 client — free-tier care data lookup (plan section 2.3).

Free tier is limited (~100 req/day) and covers a subset of fields/species, so
every call here is best-effort: a blank API key or any HTTP failure yields an
empty/``None`` result rather than raising, letting the resolution chain in
``app.services.care_resolution`` fall through to the LLM and category defaults.

A short per-call timeout plus a simple in-memory circuit breaker (see
``_should_skip``/``_record_failure``/``_record_success``) keep a slow or down
Perenual from bottlenecking plant identification — ``resolve_care_data`` calls
``search_species`` then ``get_watering_interval_days`` back-to-back, so
without these a single identify request could stall for 2x the timeout on
every request. See TODO.md "Speed up plant identification further".
"""

import logging
import time
from dataclasses import dataclass

import httpx

LOG = logging.getLogger(__name__)

_BASE_URL = "https://perenual.com/api/v2"

# plan 2.3: "category default map (frequent = 4d, average = 7d, minimum = 14d, none = 30d)"
CATEGORY_DEFAULT_DAYS = {"frequent": 4, "average": 7, "minimum": 14, "none": 30}


@dataclass(frozen=True)
class PerenualCareDetails:
    interval_days: int | None
    # Perenual's own text fields (English-only — the API has no language
    # parameter), extracted from the same species/details response already
    # fetched for the watering interval so care_resolution.resolve_care_data
    # gets them "for free" instead of making a second request.
    light: str | None
    soil: str | None


class PerenualClient:
    def __init__(
        self,
        api_key: str,
        timeout: float = 3.0,
        http_client: httpx.AsyncClient | None = None,
        failure_threshold: int = 2,
        cooldown_seconds: float = 300.0,
    ) -> None:
        self._api_key = api_key
        self._timeout = timeout
        # Shared, injected client (see app.main) reuses TCP/TLS connections
        # across requests; falls back to a private client (e.g. in tests)
        # when none is supplied.
        self._client = http_client or httpx.AsyncClient()
        # Circuit breaker: after `failure_threshold` consecutive failures
        # (timeouts, connection errors, non-2xx responses), stop calling
        # Perenual for `cooldown_seconds` and go straight to the empty/None
        # fallback instead. A single successful call resets the counter.
        # `time.monotonic()` is used so this is immune to wall-clock changes.
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._consecutive_failures = 0
        self._skip_until: float | None = None

    def _should_skip(self) -> bool:
        return self._skip_until is not None and time.monotonic() < self._skip_until

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._skip_until = None

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._failure_threshold:
            self._skip_until = time.monotonic() + self._cooldown_seconds

    async def search_species(self, query: str) -> list[dict]:
        if not self._api_key:
            return []
        if self._should_skip():
            LOG.info("Skipping Perenual search for %r — recently failing", query)
            return []

        start = time.monotonic()
        try:
            response = await self._client.get(
                f"{_BASE_URL}/species-list",
                params={"key": self._api_key, "q": query},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            LOG.info("Perenual search failed for %r after %.2fs", query, time.monotonic() - start, exc_info=True)
            self._record_failure()
            return []
        self._record_success()
        LOG.info("Perenual search for %r took %.2fs", query, time.monotonic() - start)

        results = []
        for item in response.json().get("data", []):
            scientific = item.get("scientific_name")
            results.append(
                {
                    "id": item["id"],
                    "common_name": item.get("common_name"),
                    "scientific_name": scientific[0] if isinstance(scientific, list) and scientific else scientific,
                    "watering": item.get("watering"),
                }
            )
        return results

    async def get_care_details(self, species_id: int) -> PerenualCareDetails | None:
        if not self._api_key:
            return None
        if self._should_skip():
            LOG.info("Skipping Perenual details lookup for species %s — recently failing", species_id)
            return None

        start = time.monotonic()
        try:
            response = await self._client.get(
                f"{_BASE_URL}/species/details/{species_id}",
                params={"key": self._api_key},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            LOG.info(
                "Perenual details lookup failed for species %s after %.2fs", species_id, time.monotonic() - start, exc_info=True
            )
            self._record_failure()
            return None
        self._record_success()
        LOG.info("Perenual details lookup for species %s took %.2fs", species_id, time.monotonic() - start)

        data = response.json()
        benchmark = data.get("watering_general_benchmark")
        if benchmark and benchmark.get("value"):
            interval_days = self._parse_benchmark_days(benchmark["value"])
        else:
            interval_days = self._category_default_days(data.get("watering"))

        return PerenualCareDetails(
            interval_days=interval_days,
            light=self._join_text_list(data.get("sunlight")),
            soil=self._join_text_list(data.get("soil")),
        )

    @staticmethod
    def _join_text_list(value: object) -> str | None:
        """Perenual returns `sunlight`/`soil` as a list of short phrases
        (e.g. ["part shade", "part sun/part shade"]) — join into one
        display-friendly string, or None if the field is absent/empty."""
        if isinstance(value, list):
            items = [str(v).strip() for v in value if str(v).strip()]
            return ", ".join(items) if items else None
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    @staticmethod
    def _parse_benchmark_days(value: str) -> int | None:
        """`value` is typically "7-10" or "7"."""
        normalized = str(value).strip().strip("\"'")
        parts = [p.strip() for p in normalized.split("-") if p.strip()]
        numbers = [float(p) for p in parts if p.replace(".", "", 1).isdigit()]
        if not numbers:
            return None
        return round(sum(numbers) / len(numbers))

    @staticmethod
    def _category_default_days(value: object) -> int | None:
        if not isinstance(value, str):
            return None
        return CATEGORY_DEFAULT_DAYS.get(value.strip().lower())
