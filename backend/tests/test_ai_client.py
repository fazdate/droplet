"""Tests for app.clients.ai: provider-neutral plant-identification client."""

import asyncio
import json

import httpx
import pytest
import respx

from app.clients.ai import (
    AiCareDataError,
    AiDiagnoseError,
    AiUnavailableError,
    AiVisionClient,
    AiVisionError,
)


@pytest.fixture
def openai_client() -> AiVisionClient:
    return AiVisionClient(
        api_style="openai",
        base_url="https://api.example.com/v1",
        api_key="openai-secret",
        model="gpt-4.1-mini",
        api_version="unused",
    )


@pytest.fixture
def azure_client() -> AiVisionClient:
    return AiVisionClient(
        api_style="azure-openai",
        base_url="https://azure.example.com",
        api_key="azure-secret",
        model="vision-deployment",
        api_version="2024-10-21",
    )


def _chat_response(content: str) -> dict:
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
    }


@respx.mock
async def test_should_call_openai_style_endpoint_with_bearer_token(openai_client: AiVisionClient) -> None:
    route = respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json=_chat_response(
                json.dumps({"candidates": [{"scientific_name": "Monstera deliciosa", "common_name": "Swiss cheese plant", "confidence": 0.9}]})
            ),
        )
    )

    await openai_client.identify_species(image_bytes=b"fake-jpeg-bytes", mime_type="image/jpeg")

    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer openai-secret"
    assert "api-version" not in request.url.params
    body = json.loads(request.content)
    assert body["model"] == "gpt-4.1-mini"
    image_part = next(p for p in body["messages"][-1]["content"] if p["type"] == "image_url")
    assert image_part["image_url"]["url"].startswith("data:image/jpeg;base64,")


@respx.mock
async def test_should_call_azure_style_endpoint_with_api_version(azure_client: AiVisionClient) -> None:
    route = respx.post("https://azure.example.com/openai/deployments/vision-deployment/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json=_chat_response(
                json.dumps({"candidates": [{"scientific_name": "Monstera deliciosa", "common_name": "Swiss cheese plant", "confidence": 0.9}]})
            ),
        )
    )

    await azure_client.identify_species(image_bytes=b"x", mime_type="image/jpeg")

    request = route.calls.last.request
    assert request.headers["api-key"] == "azure-secret"
    assert request.url.params["api-version"] == "2024-10-21"
    body = json.loads(request.content)
    assert "model" not in body


@respx.mock
async def test_should_request_common_name_in_english_by_default(openai_client: AiVisionClient) -> None:
    route = respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json=_chat_response(
                json.dumps({"candidates": [{"scientific_name": "Monstera deliciosa", "common_name": "Swiss cheese plant", "confidence": 0.9}]})
            ),
        )
    )

    await openai_client.identify_species(image_bytes=b"x", mime_type="image/jpeg")

    body = json.loads(route.calls.last.request.content)
    assert "English" in body["messages"][0]["content"]


@respx.mock
async def test_should_request_common_name_in_hungarian_when_language_is_hu(openai_client: AiVisionClient) -> None:
    route = respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json=_chat_response(
                json.dumps({"candidates": [{"scientific_name": "Monstera deliciosa", "common_name": "Fűrészlevelű fikusz", "confidence": 0.9}]})
            ),
        )
    )

    await openai_client.identify_species(image_bytes=b"x", mime_type="image/jpeg", language="hu")

    body = json.loads(route.calls.last.request.content)
    assert "Hungarian" in body["messages"][0]["content"]


@respx.mock
async def test_should_resolve_species_from_typed_name_in_configured_language(openai_client: AiVisionClient) -> None:
    route = respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json=_chat_response(
                json.dumps(
                    {"candidates": [{"scientific_name": "Dypsis lutescens", "common_name": "Areka pálma", "confidence": 0.8}]}
                )
            ),
        )
    )

    candidates = await openai_client.resolve_species_by_name("areka pálma", language="hu")

    assert candidates[0].scientific_name == "Dypsis lutescens"
    assert candidates[0].common_name == "Areka pálma"
    body = json.loads(route.calls.last.request.content)
    assert "Hungarian" in body["messages"][0]["content"]
    assert body["messages"][-1]["content"] == "Plant name: areka pálma"


@respx.mock
async def test_should_apply_curated_override_for_known_mistranslation(openai_client: AiVisionClient) -> None:
    respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json=_chat_response(
                json.dumps(
                    {"candidates": [{"scientific_name": "Syngonium podophyllum", "common_name": "Nyílgyökér", "confidence": 0.9}]}
                )
            ),
        )
    )

    candidates = await openai_client.identify_species(image_bytes=b"x", mime_type="image/jpeg", language="hu")

    assert candidates[0].common_name == "Nyíllevél"


@respx.mock
async def test_should_extract_json_when_model_wraps_it_in_prose_or_markdown_fences(openai_client: AiVisionClient) -> None:
    wrapped = 'Sure, here you go:\n```json\n{"candidates": [{"scientific_name": "Ficus lyrata", "common_name": "Fiddle leaf fig", "confidence": 0.8}]}\n```'
    respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_chat_response(wrapped))
    )

    candidates = await openai_client.identify_species(image_bytes=b"x", mime_type="image/jpeg")

    assert candidates[0].scientific_name == "Ficus lyrata"


@respx.mock
async def test_should_raise_ai_vision_error_on_unparseable_content(openai_client: AiVisionClient) -> None:
    respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_chat_response("not json at all"))
    )

    with pytest.raises(AiVisionError):
        await openai_client.identify_species(image_bytes=b"x", mime_type="image/jpeg")


@respx.mock
async def test_should_raise_on_http_error(openai_client: AiVisionClient) -> None:
    respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(401, json={"error": "unauthorized"})
    )

    with pytest.raises(httpx.HTTPStatusError):
        await openai_client.identify_species(image_bytes=b"x", mime_type="image/jpeg")


def test_default_timeout_should_be_short() -> None:
    client = AiVisionClient(
        api_style="openai",
        base_url="https://api.example.com/v1",
        api_key="k",
        model="gpt-4.1-mini",
        api_version="unused",
    )

    assert client._timeout == 15.0


@respx.mock
async def test_should_skip_calls_after_consecutive_failures() -> None:
    route = respx.post("https://api.example.com/v1/chat/completions").mock(return_value=httpx.Response(500))
    client = AiVisionClient(
        api_style="openai",
        base_url="https://api.example.com/v1",
        api_key="k",
        model="gpt-4.1-mini",
        api_version="unused",
        failure_threshold=2,
        cooldown_seconds=60,
    )

    for _ in range(2):
        with pytest.raises(httpx.HTTPStatusError):
            await client.identify_species(image_bytes=b"x", mime_type="image/jpeg")
    assert route.call_count == 2

    with pytest.raises(AiUnavailableError):
        await client.identify_species(image_bytes=b"x", mime_type="image/jpeg")
    assert route.call_count == 2


@respx.mock
async def test_breaker_should_be_shared_across_identify_and_describe_care() -> None:
    route = respx.post("https://api.example.com/v1/chat/completions").mock(return_value=httpx.Response(500))
    client = AiVisionClient(
        api_style="openai",
        base_url="https://api.example.com/v1",
        api_key="k",
        model="gpt-4.1-mini",
        api_version="unused",
        failure_threshold=1,
        cooldown_seconds=60,
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.identify_species(image_bytes=b"x", mime_type="image/jpeg")
    assert route.call_count == 1

    with pytest.raises(AiUnavailableError):
        await client.describe_care("Some plant")
    assert route.call_count == 1


@respx.mock
async def test_should_reset_breaker_after_cooldown_and_success(openai_client: AiVisionClient) -> None:
    route = respx.post("https://api.example.com/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(
                200,
                json=_chat_response(
                    json.dumps({"candidates": [{"scientific_name": "Monstera deliciosa", "common_name": "x", "confidence": 0.9}]})
                ),
            ),
        ]
    )
    openai_client._failure_threshold = 1
    openai_client._cooldown_seconds = 0.01

    with pytest.raises(httpx.HTTPStatusError):
        await openai_client.identify_species(image_bytes=b"x", mime_type="image/jpeg")
    assert route.call_count == 1

    await asyncio.sleep(0.02)

    await openai_client.identify_species(image_bytes=b"x", mime_type="image/jpeg")
    assert route.call_count == 2
    assert openai_client._consecutive_failures == 0
    assert openai_client._skip_until is None


@respx.mock
async def test_should_describe_care_for_species_name(openai_client: AiVisionClient) -> None:
    respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json=_chat_response(
                json.dumps(
                    {
                        "watering_interval_days": 7,
                        "light": "bright indirect",
                        "soil": "well-draining potting mix",
                        "notes": "Likes humidity.",
                        "seasonal_profile": "tropical",
                    }
                )
            ),
        )
    )

    care = await openai_client.describe_care("Monstera deliciosa")

    assert care["watering_interval_days"] == 7
    assert care["seasonal_profile"] == "tropical"


@respx.mock
async def test_should_request_care_text_in_configured_language(openai_client: AiVisionClient) -> None:
    route = respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json=_chat_response(
                json.dumps(
                    {
                        "watering_interval_days": 7,
                        "light": "fényes, közvetett fény",
                        "soil": "jól áteresztő talaj",
                        "notes": "Szereti a párát.",
                        "seasonal_profile": "tropical",
                    }
                )
            ),
        )
    )

    care = await openai_client.describe_care("Monstera deliciosa", language="hu")

    assert care["light"] == "fényes, közvetett fény"
    sent_body = json.loads(route.calls.last.request.content)
    assert "Hungarian" in sent_body["messages"][0]["content"]


@respx.mock
async def test_should_raise_ai_care_data_error_when_unparseable(openai_client: AiVisionClient) -> None:
    respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_chat_response("nope"))
    )

    with pytest.raises(AiCareDataError):
        await openai_client.describe_care("Some plant")


@respx.mock
async def test_should_diagnose_plant_issues_from_photo(openai_client: AiVisionClient) -> None:
    route = respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json=_chat_response(
                json.dumps(
                    {
                        "healthy": False,
                        "issues": [
                            {
                                "issue": "Yellowing lower leaves",
                                "suggestion": "Let the soil dry out more between waterings.",
                            }
                        ],
                    }
                )
            ),
        )
    )

    result = await openai_client.diagnose_plant(
        image_bytes=b"fake-jpeg-bytes", mime_type="image/jpeg", species_name="Monstera deliciosa"
    )

    assert result.healthy is False
    assert len(result.issues) == 1
    assert result.issues[0].issue == "Yellowing lower leaves"
    assert result.issues[0].suggestion == "Let the soil dry out more between waterings."

    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer openai-secret"
    body = json.loads(request.content)
    assert "Monstera deliciosa" in body["messages"][0]["content"]


@respx.mock
async def test_should_report_healthy_plant_with_no_issues(openai_client: AiVisionClient) -> None:
    respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_chat_response(json.dumps({"healthy": True, "issues": []})))
    )

    result = await openai_client.diagnose_plant(image_bytes=b"x", mime_type="image/jpeg")

    assert result.healthy is True
    assert result.issues == []


@respx.mock
async def test_should_request_diagnosis_text_in_configured_language(openai_client: AiVisionClient) -> None:
    route = respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json=_chat_response(
                json.dumps(
                    {
                        "healthy": False,
                        "issues": [{"issue": "Sárguló levelek", "suggestion": "Locsold ritkábban."}],
                    }
                )
            ),
        )
    )

    result = await openai_client.diagnose_plant(image_bytes=b"x", mime_type="image/jpeg", language="hu")

    assert result.issues[0].issue == "Sárguló levelek"
    body = json.loads(route.calls.last.request.content)
    assert "Hungarian" in body["messages"][0]["content"]


@respx.mock
async def test_should_default_species_name_when_unknown(openai_client: AiVisionClient) -> None:
    route = respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_chat_response(json.dumps({"healthy": True, "issues": []})))
    )

    await openai_client.diagnose_plant(image_bytes=b"x", mime_type="image/jpeg")

    body = json.loads(route.calls.last.request.content)
    assert "unknown species" in body["messages"][0]["content"]


@respx.mock
async def test_should_raise_ai_diagnose_error_when_unparseable(openai_client: AiVisionClient) -> None:
    respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_chat_response("not json"))
    )

    with pytest.raises(AiDiagnoseError):
        await openai_client.diagnose_plant(image_bytes=b"x", mime_type="image/jpeg")
