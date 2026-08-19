"""Tests for /api/identify, /api/species/lookup, /api/species/manual, and POST /api/plants."""

import datetime as dt
import io
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.clients.ai import AiVisionClient, SpeciesCandidate
from app.clients.perenual import PerenualClient
from app.config import Settings
from app.main import create_app
from app.models.orm import Plant, Room, Species


@pytest.fixture
def ai_client() -> MagicMock:
    client = MagicMock(spec=AiVisionClient)
    client.identify_species.return_value = [
        SpeciesCandidate(scientific_name="Monstera deliciosa", common_name="Swiss cheese plant", confidence=0.92),
        SpeciesCandidate(scientific_name="Epipremnum aureum", common_name="Pothos", confidence=0.05),
    ]
    client.describe_care.return_value = {"watering_interval_days": 7, "seasonal_profile": "tropical"}
    return client


@pytest.fixture
def perenual_client() -> MagicMock:
    client = MagicMock(spec=PerenualClient)
    client.search_species.return_value = []
    return client


@pytest.fixture
def app_client(settings, engine, ai_client, perenual_client, monkeypatch) -> TestClient:
    async def fake_fetch_reference_image_url(name: str, **_kwargs) -> str:
        return f"https://example.com/{name}.jpg"

    monkeypatch.setattr("app.routers.species.fetch_reference_image_url", fake_fetch_reference_image_url)
    app = create_app(settings=settings, engine=engine, ai_client=ai_client, perenual_client=perenual_client)
    return TestClient(app)


def test_should_identify_species_and_cache_them(app_client: TestClient, engine: Engine, ai_client: MagicMock) -> None:
    files = {"photo": ("plant.jpg", io.BytesIO(b"fake-image-bytes"), "image/jpeg")}

    response = app_client.post("/api/identify", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["photo_id"].endswith(".jpg")
    assert len(body["candidates"]) == 2
    top = body["candidates"][0]
    assert top["scientific_name"] == "Monstera deliciosa"
    assert top["confidence"] == 0.92
    assert top["reference_image_url"] == "https://example.com/Monstera deliciosa.jpg"
    assert top["species_id"] is not None

    with Session(engine) as session:
        assert session.query(Species).filter_by(scientific_name="Monstera deliciosa").count() == 1
    ai_client.identify_species.assert_called_once()


def test_should_rate_limit_identify_requests(app_client: TestClient, ai_client: MagicMock) -> None:
    files = {"photo": ("plant.jpg", io.BytesIO(b"fake-image-bytes"), "image/jpeg")}

    responses = [app_client.post("/api/identify", files=files) for _ in range(11)]

    assert [response.status_code for response in responses[:10]] == [200] * 10
    assert responses[10].status_code == 429
    assert ai_client.identify_species.call_count == 10


def test_should_pass_configured_language_to_ai_identify_species(
    app_client: TestClient, ai_client: MagicMock, settings: Settings
) -> None:
    files = {"photo": ("plant.jpg", io.BytesIO(b"fake-image-bytes"), "image/jpeg")}

    app_client.post("/api/identify", files=files)

    ai_client.identify_species.assert_called_once_with(
        image_bytes=b"fake-image-bytes", mime_type="image/jpeg", language=settings.language
    )


def test_should_reuse_cached_species_on_second_identify_call(
    app_client: TestClient, ai_client: MagicMock, engine: Engine
) -> None:
    app_client.post("/api/identify", files={"photo": ("plant.jpg", io.BytesIO(b"one"), "image/jpeg")})
    app_client.post("/api/identify", files={"photo": ("plant2.jpg", io.BytesIO(b"two"), "image/jpeg")})

    with Session(engine) as session:
        assert session.query(Species).filter_by(scientific_name="Monstera deliciosa").count() == 1
    assert ai_client.describe_care.call_count <= 2


def test_should_look_up_species_by_name(app_client: TestClient, engine: Engine) -> None:
    with Session(engine) as session:
        session.add(Species(scientific_name="Ficus lyrata", common_name="Fiddle leaf fig", watering_interval_days=7, source="perenual"))
        session.commit()

    response = app_client.get("/api/species/lookup", params={"q": "ficus"})

    assert response.status_code == 200
    assert any(c["scientific_name"] == "Ficus lyrata" for c in response.json()["candidates"])


def test_should_not_fall_back_to_model_name_resolution_when_language_is_english(
    app_client: TestClient, ai_client: MagicMock
) -> None:
    response = app_client.get("/api/species/lookup", params={"q": "nonexistent plant"})

    assert response.status_code == 200
    assert response.json()["candidates"] == []
    ai_client.resolve_species_by_name.assert_not_called()


def test_should_fall_back_to_model_name_resolution_for_hungarian_query_with_no_other_matches(
    app_client: TestClient, ai_client: MagicMock, settings: Settings, engine: Engine
) -> None:
    settings.language = "hu"
    ai_client.resolve_species_by_name.return_value = [
        SpeciesCandidate(scientific_name="Dypsis lutescens", common_name="Areka pálma", confidence=0.8),
    ]

    response = app_client.get("/api/species/lookup", params={"q": "areka pálma"})

    assert response.status_code == 200
    candidates = response.json()["candidates"]
    assert any(c["scientific_name"] == "Dypsis lutescens" and c["common_name"] == "Areka pálma" for c in candidates)
    ai_client.resolve_species_by_name.assert_called_once_with("areka pálma", language="hu")
    with Session(engine) as session:
        assert session.query(Species).filter_by(scientific_name="Dypsis lutescens").count() == 1


def test_should_create_manual_species(app_client: TestClient, engine: Engine) -> None:
    response = app_client.post(
        "/api/species/manual", json={"name": "My weird cactus", "interval_days": 20, "seasonal_profile": "succulent"}
    )

    assert response.status_code == 201
    species_id = response.json()["species_id"]
    with Session(engine) as session:
        species = session.get(Species, species_id)
        assert species.scientific_name == "My weird cactus"
        assert species.watering_interval_days == 20
        assert species.source == "manual"


def test_should_create_plant_from_identified_species(
    app_client: TestClient, engine: Engine, frozen_now: dt.datetime
) -> None:
    with Session(engine) as session:
        room = Room(name="Kitchen")
        session.add(room)
        session.commit()
        room_id = room.id

    identify = app_client.post("/api/identify", files={"photo": ("plant.jpg", io.BytesIO(b"fake"), "image/jpeg")}).json()
    species_id = identify["candidates"][0]["species_id"]
    photo_id = identify["photo_id"]

    response = app_client.post(
        "/api/plants",
        json={"photo_id": photo_id, "species_id": species_id, "room_id": room_id, "nickname": "Monty"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["nickname"] == "Monty"
    assert body["photo_path"] == photo_id
    assert body["species_id"] == species_id

    with Session(engine) as session:
        assert session.query(Plant).filter_by(nickname="Monty").count() == 1


def test_should_derive_nickname_when_omitted(app_client: TestClient, engine: Engine) -> None:
    with Session(engine) as session:
        room = Room(name="Kitchen")
        species = Species(scientific_name="Basil", common_name="Sweet basil", watering_interval_days=4, source="manual")
        session.add_all([room, species])
        session.commit()
        room_id, species_id = room.id, species.id

    response = app_client.post("/api/plants", json={"photo_id": "x.jpg", "species_id": species_id, "room_id": room_id})

    assert response.status_code == 201
    assert response.json()["nickname"] == "Sweet basil"
