"""Tests for app.clients.perenual: Perenual API v2 care-data lookup — plan 2.3."""

import asyncio

import httpx
import pytest
import respx

from app.clients.perenual import PerenualClient


@pytest.fixture
def client() -> PerenualClient:
    return PerenualClient(api_key="demo-key")


@respx.mock
async def test_should_search_species_by_query(client: PerenualClient) -> None:
    respx.get("https://perenual.com/api/v2/species-list", params={"key": "demo-key", "q": "monstera"}).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"id": 42, "common_name": "Swiss cheese plant", "scientific_name": ["Monstera deliciosa"], "watering": "average"}
                ]
            },
        )
    )

    results = await client.search_species("monstera")

    assert results == [{"id": 42, "common_name": "Swiss cheese plant", "scientific_name": "Monstera deliciosa", "watering": "average"}]


@respx.mock
async def test_should_return_empty_list_when_no_matches(client: PerenualClient) -> None:
    respx.get("https://perenual.com/api/v2/species-list", params={"key": "demo-key", "q": "xyz"}).mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    assert await client.search_species("xyz") == []


@respx.mock
async def test_should_get_watering_interval_days_from_benchmark(client: PerenualClient) -> None:
    respx.get("https://perenual.com/api/v2/species/details/42", params={"key": "demo-key"}).mock(
        return_value=httpx.Response(
            200,
            json={"id": 42, "watering": "average", "watering_general_benchmark": {"value": "7-10", "unit": "days"}},
        )
    )

    details = await client.get_care_details(42)

    assert details.interval_days == 8  # round(mean(7, 10))


@respx.mock
async def test_should_parse_quoted_benchmark_days_from_details(client: PerenualClient) -> None:
    respx.get("https://perenual.com/api/v2/species/details/42", params={"key": "demo-key"}).mock(
        return_value=httpx.Response(
            200,
            json={"id": 42, "watering": "Average", "watering_general_benchmark": {"value": '"7-10"', "unit": "days"}},
        )
    )

    details = await client.get_care_details(42)

    assert details.interval_days == 8


@respx.mock
async def test_should_fall_back_to_category_default_when_no_benchmark(client: PerenualClient) -> None:
    respx.get("https://perenual.com/api/v2/species/details/7", params={"key": "demo-key"}).mock(
        return_value=httpx.Response(200, json={"id": 7, "watering": "frequent"})
    )

    details = await client.get_care_details(7)

    assert details.interval_days == 4


@respx.mock
async def test_should_fall_back_to_category_default_case_insensitively(client: PerenualClient) -> None:
    respx.get("https://perenual.com/api/v2/species/details/7", params={"key": "demo-key"}).mock(
        return_value=httpx.Response(200, json={"id": 7, "watering": "Average"})
    )

    details = await client.get_care_details(7)

    assert details.interval_days == 7


@respx.mock
async def test_should_extract_sunlight_and_soil_from_details_response(client: PerenualClient) -> None:
    respx.get("https://perenual.com/api/v2/species/details/42", params={"key": "demo-key"}).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 42,
                "watering": "average",
                "sunlight": ["part shade", "part sun/part shade"],
                "soil": ["loam", "well-drained"],
            },
        )
    )

    details = await client.get_care_details(42)

    assert details.light == "part shade, part sun/part shade"
    assert details.soil == "loam, well-drained"


@respx.mock
async def test_should_return_none_light_and_soil_when_details_response_lacks_them(client: PerenualClient) -> None:
    respx.get("https://perenual.com/api/v2/species/details/7", params={"key": "demo-key"}).mock(
        return_value=httpx.Response(200, json={"id": 7, "watering": "frequent"})
    )

    details = await client.get_care_details(7)

    assert details.light is None
    assert details.soil is None


@respx.mock
async def test_should_return_none_when_details_lookup_fails(client: PerenualClient) -> None:
    respx.get("https://perenual.com/api/v2/species/details/7", params={"key": "demo-key"}).mock(
        return_value=httpx.Response(500)
    )

    assert await client.get_care_details(7) is None


async def test_search_species_should_return_empty_when_api_key_blank() -> None:
    client = PerenualClient(api_key="")

    assert await client.search_species("monstera") == []


def test_default_timeout_should_be_short() -> None:
    # A blank/slow-but-not-quite-timing-out Perenual shouldn't be able to
    # bottleneck plant identification (TODO.md "Speed up plant identification
    # further") the way the old 10s default could.
    client = PerenualClient(api_key="demo-key")

    assert client._timeout == 3.0


@respx.mock
async def test_should_skip_calls_after_consecutive_failures() -> None:
    route = respx.get("https://perenual.com/api/v2/species-list", params={"key": "demo-key", "q": "x"}).mock(
        return_value=httpx.Response(500)
    )
    client = PerenualClient(api_key="demo-key", failure_threshold=2, cooldown_seconds=60)

    assert await client.search_species("x") == []
    assert await client.search_species("x") == []
    assert route.call_count == 2

    # Breaker is now tripped: a third call should be skipped without hitting the network.
    assert await client.search_species("x") == []
    assert route.call_count == 2


@respx.mock
async def test_should_skip_details_lookup_once_breaker_tripped_by_search() -> None:
    search_route = respx.get(
        "https://perenual.com/api/v2/species-list", params={"key": "demo-key", "q": "x"}
    ).mock(return_value=httpx.Response(500))
    details_route = respx.get("https://perenual.com/api/v2/species/details/1", params={"key": "demo-key"}).mock(
        return_value=httpx.Response(200, json={"id": 1, "watering": "average"})
    )
    # Consecutive failures are shared across both endpoints: once Perenual
    # looks unhealthy from a search failure, details lookups skip too.
    client = PerenualClient(api_key="demo-key", failure_threshold=1, cooldown_seconds=60)

    assert await client.search_species("x") == []
    assert search_route.call_count == 1

    assert await client.get_care_details(1) is None
    assert details_route.call_count == 0


@respx.mock
async def test_should_reset_breaker_after_cooldown_and_success() -> None:
    route = respx.get("https://perenual.com/api/v2/species-list", params={"key": "demo-key", "q": "x"}).mock(
        side_effect=[httpx.Response(500), httpx.Response(200, json={"data": []})]
    )
    client = PerenualClient(api_key="demo-key", failure_threshold=1, cooldown_seconds=0.01)

    assert await client.search_species("x") == []
    assert route.call_count == 1

    await asyncio.sleep(0.02)  # let the short cooldown expire

    assert await client.search_species("x") == []
    assert route.call_count == 2
    assert client._consecutive_failures == 0
    assert client._skip_until is None
