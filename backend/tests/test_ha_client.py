"""Tests for app.clients.ha: Home Assistant REST notify client (mocked with respx)."""

import httpx
import pytest
import respx

from app.clients.ha import HomeAssistantClient


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
