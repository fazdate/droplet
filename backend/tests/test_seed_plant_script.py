"""Tests for the manual plant seeding CLI (scripts/seed_plant.py)."""

from app.config import Settings
from app.db import create_db_engine, init_db
from app.models.orm import Plant, Room, Species
from scripts.seed_plant import parse_args, seed_plant
from sqlalchemy.orm import Session


def test_should_parse_required_arguments() -> None:
    args = parse_args(
        [
            "--nickname", "Basil",
            "--room", "Kitchen",
            "--species", "Sweet basil",
            "--interval-days", "4",
            "--photo", "photos/basil.jpg",
        ]
    )

    assert args.nickname == "Basil"
    assert args.room == "Kitchen"
    assert args.species == "Sweet basil"
    assert args.interval_days == 4
    assert args.photo == "photos/basil.jpg"
    assert args.seasonal_profile == "temperate"


def test_should_seed_plant_end_to_end(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AI_API_KEY", "x")
    monkeypatch.setenv("HA_BASE_URL", "http://ha.local")
    monkeypatch.setenv("HA_LONG_LIVED_TOKEN", "x")
    monkeypatch.setenv("HA_WEBHOOK_SECRET", "x")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "seed_test.sqlite3"))
    settings = Settings()

    args = parse_args(
        [
            "--nickname", "Basil",
            "--room", "Kitchen",
            "--species", "Sweet basil",
            "--interval-days", "4",
            "--photo", "photos/basil.jpg",
        ]
    )

    plant_id = seed_plant(settings, args)

    engine = create_db_engine(f"sqlite:///{settings.db_path}")
    init_db(engine)
    with Session(engine) as session:
        plant = session.get(Plant, plant_id)
        assert plant is not None
        assert plant.nickname == "Basil"
        assert plant.room.name == "Kitchen"
        assert plant.species.scientific_name == "Sweet basil"
        assert plant.species.watering_interval_days == 4
        assert session.query(Room).count() == 1
        assert session.query(Species).count() == 1
