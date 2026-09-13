"""Tests for GET /api/ha/sensors — the room settings modal's sensor dropdown
discovery endpoint (CLIMATE_CADENCE_PLAN.md)."""

import httpx
import respx
from fastapi.testclient import TestClient


def _states_payload() -> list[dict]:
    return [
        {
            "entity_id": "sensor.living_room_temp",
            "state": "21.5",
            "attributes": {
                "device_class": "temperature",
                "friendly_name": "Living Room Temperature",
                "unit_of_measurement": "°C",
            },
        },
        {
            "entity_id": "sensor.living_room_humidity",
            "state": "50",
            "attributes": {
                "device_class": "humidity",
                "friendly_name": "Living Room Humidity",
                "unit_of_measurement": "%",
            },
        },
        {
            "entity_id": "light.living_room",
            "state": "on",
            "attributes": {},
        },
    ]


@respx.mock
def test_should_list_sensors_split_by_device_class(client: TestClient) -> None:
    respx.get("http://ha.local/api/states").mock(return_value=httpx.Response(200, json=_states_payload()))

    response = client.get("/api/ha/sensors")

    assert response.status_code == 200
    body = response.json()
    assert len(body["temperature"]) == 1
    assert body["temperature"][0]["entity_id"] == "sensor.living_room_temp"
    assert len(body["humidity"]) == 1
    assert body["humidity"][0]["entity_id"] == "sensor.living_room_humidity"


@respx.mock
def test_should_return_503_when_ha_is_unreachable(client: TestClient) -> None:
    respx.get("http://ha.local/api/states").mock(side_effect=httpx.ConnectError("connection refused"))

    response = client.get("/api/ha/sensors")

    assert response.status_code == 503


@respx.mock
def test_should_return_503_on_ha_error_response(client: TestClient) -> None:
    respx.get("http://ha.local/api/states").mock(return_value=httpx.Response(401))

    response = client.get("/api/ha/sensors")

    assert response.status_code == 503
