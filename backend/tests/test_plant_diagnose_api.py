"""Tests for POST /api/plants/{plant_id}/diagnose."""

import io
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.clients.ai import AiDiagnoseError, AiUnavailableError, AiVisionClient, DiagnoseIssue, DiagnoseResult
from app.main import create_app
from app.models.orm import Plant, Room, Species


def _seed_plant(engine: Engine, **overrides) -> int:
    with Session(engine) as session:
        room = Room(name="Kitchen")
        species = Species(
            scientific_name=overrides.pop("scientific_name", "Monstera deliciosa"),
            common_name=overrides.pop("common_name", "Swiss cheese plant"),
            watering_interval_days=7,
        )
        session.add_all([room, species])
        session.commit()
        plant = Plant(
            nickname=overrides.pop("nickname", "Monty"),
            species_id=species.id,
            room_id=room.id,
            photo_path="p.jpg",
            **overrides,
        )
        session.add(plant)
        session.commit()
        return plant.id


@pytest.fixture
def diagnose_ai_client() -> MagicMock:
    client = MagicMock(spec=AiVisionClient)
    client.diagnose_plant.return_value = DiagnoseResult(
        healthy=False,
        issues=[DiagnoseIssue(issue="Yellowing lower leaves", suggestion="Water less often.")],
    )
    return client


@pytest.fixture
def app_client(settings, engine, diagnose_ai_client) -> TestClient:
    app = create_app(settings=settings, engine=engine, diagnose_ai_client=diagnose_ai_client)
    return TestClient(app)


def _photo_files() -> dict:
    return {"photo": ("plant.jpg", io.BytesIO(b"fake-image-bytes"), "image/jpeg")}


def test_should_diagnose_plant_and_return_issues(
    app_client: TestClient, engine: Engine, diagnose_ai_client: MagicMock
) -> None:
    plant_id = _seed_plant(engine)

    response = app_client.post(f"/api/plants/{plant_id}/diagnose", files=_photo_files())

    assert response.status_code == 200
    assert response.json()["issues"] == [{"issue": "Yellowing lower leaves", "suggestion": "Water less often."}]


def test_should_pass_species_common_name_and_language_to_ai(
    app_client: TestClient, engine: Engine, diagnose_ai_client: MagicMock, settings
) -> None:
    plant_id = _seed_plant(engine, common_name="Swiss cheese plant")

    app_client.post(f"/api/plants/{plant_id}/diagnose", files=_photo_files())

    diagnose_ai_client.diagnose_plant.assert_called_once_with(
        image_bytes=b"fake-image-bytes",
        mime_type="image/jpeg",
        species_name="Swiss cheese plant",
        language=settings.language,
    )


def test_should_fall_back_to_scientific_name_when_no_common_name(
    app_client: TestClient, engine: Engine, diagnose_ai_client: MagicMock
) -> None:
    plant_id = _seed_plant(engine, common_name=None, scientific_name="Monstera deliciosa")

    app_client.post(f"/api/plants/{plant_id}/diagnose", files=_photo_files())

    assert diagnose_ai_client.diagnose_plant.call_args.kwargs["species_name"] == "Monstera deliciosa"


def test_should_return_404_for_unknown_plant(app_client: TestClient) -> None:
    response = app_client.post("/api/plants/999999/diagnose", files=_photo_files())

    assert response.status_code == 404


def test_should_return_503_when_ai_is_unavailable(
    app_client: TestClient, engine: Engine, diagnose_ai_client: MagicMock
) -> None:
    plant_id = _seed_plant(engine)
    diagnose_ai_client.diagnose_plant.side_effect = AiUnavailableError("cooling down")

    response = app_client.post(f"/api/plants/{plant_id}/diagnose", files=_photo_files())

    assert response.status_code == 503


def test_should_return_502_when_ai_response_is_unparseable(
    app_client: TestClient, engine: Engine, diagnose_ai_client: MagicMock
) -> None:
    plant_id = _seed_plant(engine)
    diagnose_ai_client.diagnose_plant.side_effect = AiDiagnoseError("nope")

    response = app_client.post(f"/api/plants/{plant_id}/diagnose", files=_photo_files())

    assert response.status_code == 502


def test_should_report_healthy_plant_with_no_issues(
    app_client: TestClient, engine: Engine, diagnose_ai_client: MagicMock
) -> None:
    plant_id = _seed_plant(engine)
    diagnose_ai_client.diagnose_plant.return_value = DiagnoseResult(healthy=True, issues=[])

    response = app_client.post(f"/api/plants/{plant_id}/diagnose", files=_photo_files())

    assert response.status_code == 200
    assert response.json()["issues"] == []
