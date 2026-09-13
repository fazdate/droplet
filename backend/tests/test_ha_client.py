"""Tests for app.clients.ha: Home Assistant REST notify client (mocked with respx)."""

import httpx
import pytest
import respx

from app.clients.ha import HomeAssistantClient, SensorInfo


@pytest.fixture
def client() -> HomeAssistantClient:
    return HomeAssistantClient(base_url="http://ha.local:8123", token="secret-token")


@respx.mock
def test_should_post_actionable_notification_to_each_target(client: HomeAssistantClient) -> None:
    route1 = respx.post("http://ha.local:8123/api/services/notify/mobile_app_phone1").mock(
        return_value=httpx.Response(200, json=[])
    )
    route2 = respx.post("http://ha.local:8123/api/services/notify/mobile_app_phone2").mock(
        return_value=httpx.Response(200, json=[])
    )

    client.notify(
        targets=["mobile_app_phone1", "mobile_app_phone2"],
        title="Kitchen: 3 plants need water",
        message="Kitchen has 3 plants overdue for watering.",
        tag="room-10",
        actions=[{"action": "WATERED_ROOM_10", "title": "Watered"}],
        click_action="http://localhost:8080/",
    )

    assert route1.called
    assert route2.called
    sent = route1.calls.last.request
    assert sent.headers["authorization"] == "Bearer secret-token"
    body = respx.calls.last.request.content
    import json as _json

    payload = _json.loads(body)
    assert payload["title"] == "Kitchen: 3 plants need water"
    assert payload["message"] == "Kitchen has 3 plants overdue for watering."
    assert payload["data"]["tag"] == "room-10"
    assert payload["data"]["actions"] == [{"action": "WATERED_ROOM_10", "title": "Watered"}]
    assert payload["data"]["clickAction"] == "http://localhost:8080/"


@respx.mock
def test_should_clear_notification_with_same_tag_on_both_targets(client: HomeAssistantClient) -> None:
    route = respx.post("http://ha.local:8123/api/services/notify/mobile_app_phone1").mock(
        return_value=httpx.Response(200, json=[])
    )

    client.clear_notification(targets=["mobile_app_phone1"], tag="plant-5")

    assert route.called
    import json as _json

    payload = _json.loads(route.calls.last.request.content)
    assert payload["message"] == "clear_notification"
    assert payload["data"]["tag"] == "plant-5"


@respx.mock
def test_should_raise_on_ha_error_response(client: HomeAssistantClient) -> None:
    respx.post("http://ha.local:8123/api/services/notify/mobile_app_phone1").mock(
        return_value=httpx.Response(401, json={"message": "unauthorized"})
    )

    with pytest.raises(httpx.HTTPStatusError):
        client.notify(
            targets=["mobile_app_phone1"],
            title="x",
            message="y",
            tag="z",
            actions=[],
            click_action="http://x",
        )


def _states_response(state: str, unit: str | None) -> httpx.Response:
    attributes = {} if unit is None else {"unit_of_measurement": unit}
    return httpx.Response(200, json={"entity_id": "sensor.x", "state": state, "attributes": attributes})


@respx.mock
def test_should_read_celsius_temperature_unchanged(client: HomeAssistantClient) -> None:
    respx.get("http://ha.local:8123/api/states/sensor.living_room_temp").mock(
        return_value=_states_response("21.5", "°C")
    )

    assert client.get_sensor_state("sensor.living_room_temp", kind="temperature") == pytest.approx(21.5)


@respx.mock
def test_should_convert_fahrenheit_temperature_to_celsius(client: HomeAssistantClient) -> None:
    respx.get("http://ha.local:8123/api/states/sensor.living_room_temp").mock(
        return_value=_states_response("70", "°F")
    )

    assert client.get_sensor_state("sensor.living_room_temp", kind="temperature") == pytest.approx(21.111, abs=0.01)


@respx.mock
def test_should_reject_temperature_with_missing_unit(client: HomeAssistantClient) -> None:
    respx.get("http://ha.local:8123/api/states/sensor.x").mock(return_value=_states_response("21.5", None))

    assert client.get_sensor_state("sensor.x", kind="temperature") is None


@respx.mock
def test_should_reject_temperature_with_unrecognized_unit(client: HomeAssistantClient) -> None:
    respx.get("http://ha.local:8123/api/states/sensor.x").mock(return_value=_states_response("21.5", "K"))

    assert client.get_sensor_state("sensor.x", kind="temperature") is None


@respx.mock
def test_should_read_humidity_percent(client: HomeAssistantClient) -> None:
    respx.get("http://ha.local:8123/api/states/sensor.x").mock(return_value=_states_response("55", "%"))

    assert client.get_sensor_state("sensor.x", kind="humidity") == pytest.approx(55.0)


@respx.mock
def test_should_read_humidity_with_absent_unit_as_percent(client: HomeAssistantClient) -> None:
    respx.get("http://ha.local:8123/api/states/sensor.x").mock(return_value=_states_response("55", None))

    assert client.get_sensor_state("sensor.x", kind="humidity") == pytest.approx(55.0)


@pytest.mark.parametrize("state", ["unavailable", "unknown", "none", ""])
@respx.mock
def test_should_reject_unavailable_states(client: HomeAssistantClient, state: str) -> None:
    respx.get("http://ha.local:8123/api/states/sensor.x").mock(return_value=_states_response(state, "°C"))

    assert client.get_sensor_state("sensor.x", kind="temperature") is None


@respx.mock
def test_should_reject_non_numeric_state(client: HomeAssistantClient) -> None:
    respx.get("http://ha.local:8123/api/states/sensor.x").mock(return_value=_states_response("not-a-number", "°C"))

    assert client.get_sensor_state("sensor.x", kind="temperature") is None


@respx.mock
def test_should_reject_out_of_bounds_temperature(client: HomeAssistantClient) -> None:
    respx.get("http://ha.local:8123/api/states/sensor.x").mock(return_value=_states_response("500", "°C"))

    assert client.get_sensor_state("sensor.x", kind="temperature") is None


@respx.mock
def test_should_accept_sub_zero_temperature_for_a_balcony_sensor(client: HomeAssistantClient) -> None:
    respx.get("http://ha.local:8123/api/states/sensor.x").mock(return_value=_states_response("-8", "°C"))

    assert client.get_sensor_state("sensor.x", kind="temperature") == pytest.approx(-8.0)


@respx.mock
def test_should_reject_out_of_bounds_humidity(client: HomeAssistantClient) -> None:
    respx.get("http://ha.local:8123/api/states/sensor.x").mock(return_value=_states_response("2", "%"))

    assert client.get_sensor_state("sensor.x", kind="humidity") is None


@respx.mock
def test_get_sensor_state_should_raise_on_404(client: HomeAssistantClient) -> None:
    respx.get("http://ha.local:8123/api/states/sensor.missing").mock(return_value=httpx.Response(404))

    with pytest.raises(httpx.HTTPStatusError):
        client.get_sensor_state("sensor.missing", kind="temperature")


@respx.mock
def test_get_sensor_state_should_raise_on_500(client: HomeAssistantClient) -> None:
    respx.get("http://ha.local:8123/api/states/sensor.x").mock(return_value=httpx.Response(500))

    with pytest.raises(httpx.HTTPStatusError):
        client.get_sensor_state("sensor.x", kind="temperature")


@respx.mock
def test_should_filter_climate_sensors_by_device_class(client: HomeAssistantClient) -> None:
    respx.get("http://ha.local:8123/api/states").mock(
        return_value=httpx.Response(
            200,
            json=[
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
                    "entity_id": "sensor.living_room_battery",
                    "state": "80",
                    "attributes": {"device_class": "battery", "unit_of_measurement": "%"},
                },
                {"entity_id": "light.living_room", "state": "on", "attributes": {}},
            ],
        )
    )

    sensors = client.list_climate_sensors()

    assert sensors == [
        SensorInfo(
            entity_id="sensor.living_room_temp",
            friendly_name="Living Room Temperature",
            device_class="temperature",
            unit="°C",
            state="21.5",
        ),
        SensorInfo(
            entity_id="sensor.living_room_humidity",
            friendly_name="Living Room Humidity",
            device_class="humidity",
            unit="%",
            state="50",
        ),
    ]
