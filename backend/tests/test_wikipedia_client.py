"""Tests for app.clients.wikipedia: reference image lookup via the Wikipedia
REST summary endpoint — plan section 2.2."""

import httpx
import pytest
import respx

from app.clients.wikipedia import fetch_reference_image_url


@respx.mock
async def test_should_return_thumbnail_url_when_page_has_one() -> None:
    respx.get("https://en.wikipedia.org/api/rest_v1/page/summary/Monstera_deliciosa").mock(
        return_value=httpx.Response(
            200,
            json={
                "title": "Monstera deliciosa",
                "thumbnail": {"source": "https://upload.wikimedia.org/monstera.jpg", "width": 320, "height": 240},
            },
        )
    )

    url = await fetch_reference_image_url("Monstera deliciosa")

    assert url == "https://upload.wikimedia.org/monstera.jpg"


@respx.mock
async def test_should_replace_spaces_with_underscores_in_page_title() -> None:
    route = respx.get("https://en.wikipedia.org/api/rest_v1/page/summary/Ficus_lyrata").mock(
        return_value=httpx.Response(200, json={"title": "Ficus lyrata"})
    )

    await fetch_reference_image_url("Ficus lyrata")

    assert route.called


@respx.mock
async def test_should_return_none_when_no_thumbnail_present() -> None:
    respx.get("https://en.wikipedia.org/api/rest_v1/page/summary/Unknown_plant").mock(
        return_value=httpx.Response(200, json={"title": "Unknown plant"})
    )

    assert await fetch_reference_image_url("Unknown plant") is None


@respx.mock
async def test_should_return_none_when_page_not_found() -> None:
    respx.get("https://en.wikipedia.org/api/rest_v1/page/summary/Nonexistent_species").mock(
        return_value=httpx.Response(404, json={"title": "Not found"})
    )

    assert await fetch_reference_image_url("Nonexistent species") is None


@respx.mock
async def test_should_return_none_on_server_error_without_raising() -> None:
    respx.get("https://en.wikipedia.org/api/rest_v1/page/summary/Monstera_deliciosa").mock(
        return_value=httpx.Response(500)
    )

    assert await fetch_reference_image_url("Monstera deliciosa") is None


@respx.mock
async def test_should_fall_back_to_base_species_name_when_cultivar_page_missing() -> None:
    """Cultivar/variety-specific names (e.g. from an AI identify result) rarely
    have their own Wikipedia page; the lookup should retry with the cultivar
    suffix stripped rather than giving up."""
    respx.get(
        "https://en.wikipedia.org/api/rest_v1/page/summary/Syngonium_podophyllum_'Neon_Robusta'"
    ).mock(return_value=httpx.Response(404))
    respx.get("https://en.wikipedia.org/api/rest_v1/page/summary/Syngonium_podophyllum").mock(
        return_value=httpx.Response(
            200,
            json={"title": "Syngonium podophyllum", "thumbnail": {"source": "https://upload.wikimedia.org/syngonium.jpg"}},
        )
    )

    url = await fetch_reference_image_url("Syngonium podophyllum 'Neon Robusta'")

    assert url == "https://upload.wikimedia.org/syngonium.jpg"


@respx.mock
async def test_should_return_none_when_both_cultivar_and_base_name_lookups_fail() -> None:
    respx.get(
        "https://en.wikipedia.org/api/rest_v1/page/summary/Syngonium_podophyllum_'Neon_Robusta'"
    ).mock(return_value=httpx.Response(404))
    respx.get("https://en.wikipedia.org/api/rest_v1/page/summary/Syngonium_podophyllum").mock(
        return_value=httpx.Response(404)
    )

    assert await fetch_reference_image_url("Syngonium podophyllum 'Neon Robusta'") is None
