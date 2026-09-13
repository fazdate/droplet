"""Home Assistant REST API client — used to push actionable notifications
(plan section 2.4/4.8) and, since CLIMATE_CADENCE_PLAN.md, to read room
temperature/humidity sensor states for the climate-aware watering cadence.
All other HA interaction (automations forwarding button presses) lives on the
HA side and calls back into our /api/ha/action webhook.
"""

from dataclasses import dataclass

import httpx

_UNAVAILABLE_STATES = {"unknown", "unavailable", "none", ""}
_TEMP_BOUNDS_C = (-30.0, 60.0)
_RH_BOUNDS_PCT = (5.0, 100.0)
_SENSOR_READ_TIMEOUT = 5.0


@dataclass(frozen=True)
class SensorInfo:
    entity_id: str
    friendly_name: str
    device_class: str
    unit: str | None
    state: str


class HomeAssistantClient:
    def __init__(self, base_url: str, token: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def _call_notify(self, target: str, payload: dict) -> None:
        url = f"{self._base_url}/api/services/notify/{target}"
        response = httpx.post(url, json=payload, headers=self._headers(), timeout=self._timeout)
        response.raise_for_status()

    def notify(
        self,
        *,
        targets: list[str],
        title: str,
        message: str,
        tag: str,
        actions: list[dict],
        click_action: str,
    ) -> None:
        payload = {
            "title": title,
            "message": message,
            "data": {"tag": tag, "actions": actions, "clickAction": click_action},
        }
        for target in targets:
            self._call_notify(target, payload)

    def clear_notification(self, *, targets: list[str], tag: str) -> None:
        payload = {"message": "clear_notification", "data": {"tag": tag}}
        for target in targets:
            self._call_notify(target, payload)

    def get_sensor_state(self, entity_id: str, *, kind: str) -> float | None:
        """Reads and validates one HA sensor's current numeric state.

        `kind` is "temperature" or "humidity" and determines unit handling and
        post-conversion bounds. Returns None — never a clamped value — for any
        bad *sample* (unavailable/unknown state, non-numeric, missing or
        unrecognized unit, or an out-of-bounds reading): the caller
        (app.services.climate) treats that as "skip this poll, keep the
        previous smoothed value" rather than corrupting the average. HTTP
        errors (HA unreachable, 404/500) are not sample problems and are left
        to propagate so the caller's per-entity try/except can log them.
        """
        response = httpx.get(
            f"{self._base_url}/api/states/{entity_id}", headers=self._headers(), timeout=_SENSOR_READ_TIMEOUT
        )
        response.raise_for_status()
        payload = response.json()

        state = payload.get("state")
        if state in _UNAVAILABLE_STATES:
            return None
        try:
            value = float(state)
        except (TypeError, ValueError):
            return None

        unit = (payload.get("attributes") or {}).get("unit_of_measurement")
        if kind == "temperature":
            if unit in ("°C", "C"):
                pass
            elif unit in ("°F", "F"):
                value = (value - 32) * 5 / 9
            else:
                # A missing/unrecognized unit rejects the sample — never
                # assume Celsius, since a °F room read as °C silently
                # inverts the climate factor.
                return None
            low, high = _TEMP_BOUNDS_C
        elif kind == "humidity":
            if unit not in (None, "", "%"):
                return None
            low, high = _RH_BOUNDS_PCT
        else:
            raise ValueError(f"Unknown sensor kind: {kind!r}")

        if not (low <= value <= high):
            return None
        return value

    def list_climate_sensors(self) -> list[SensorInfo]:
        """Lists all temperature/humidity sensors known to HA, for the room
        settings dropdown — filtered server-side so the frontend never has to
        know about HA's `device_class` attribute."""
        response = httpx.get(f"{self._base_url}/api/states", headers=self._headers(), timeout=_SENSOR_READ_TIMEOUT)
        response.raise_for_status()

        sensors: list[SensorInfo] = []
        for entry in response.json():
            attributes = entry.get("attributes") or {}
            device_class = attributes.get("device_class")
            if device_class not in ("temperature", "humidity"):
                continue
            sensors.append(
                SensorInfo(
                    entity_id=entry["entity_id"],
                    friendly_name=attributes.get("friendly_name") or entry["entity_id"],
                    device_class=device_class,
                    unit=attributes.get("unit_of_measurement"),
                    state=entry.get("state", ""),
                )
            )
        return sensors
