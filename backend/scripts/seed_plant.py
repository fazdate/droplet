#!/usr/bin/env python3
"""Manual plant seeding CLI — plan phase 1 (usable before the AI identify flow exists).

Usage:
    python -m scripts.seed_plant --nickname "Basil" --room "Kitchen" \\
        --species "Sweet basil" --interval-days 4 --photo photos/basil.jpg
"""

import argparse
import datetime as dt

from app.config import Settings
from app.db import create_db_engine, init_db, session_scope
from app.services.plants import create_plant, find_or_create_room, find_or_create_species_manual


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manually seed a plant.")
    parser.add_argument("--nickname", required=True, help="What to call this plant, e.g. 'Basil'")
    parser.add_argument("--room", required=True, help="Room name, e.g. 'Kitchen'")
    parser.add_argument("--species", required=True, help="Free-text species/name, e.g. 'Sweet basil'")
    parser.add_argument("--interval-days", required=True, type=int, help="Water every N days")
    parser.add_argument("--photo", required=True, help="Path to the plant's photo, relative to PHOTOS_DIR")
    parser.add_argument(
        "--seasonal-profile",
        default="temperate",
        choices=["temperate", "tropical", "succulent", "mediterranean"],
        help="Seasonal cadence profile (default: temperate)",
    )
    return parser.parse_args(argv)


def seed_plant(settings: Settings, args: argparse.Namespace) -> int:
    engine = create_db_engine(f"sqlite:///{settings.db_path}")
    init_db(engine)

    with session_scope(engine) as session:
        room = find_or_create_room(session, args.room)
        species = find_or_create_species_manual(
            session,
            name=args.species,
            interval_days=args.interval_days,
            seasonal_profile=args.seasonal_profile,
        )
        session.flush()
        plant = create_plant(
            session,
            nickname=args.nickname,
            room=room,
            species=species,
            photo_path=args.photo,
            now=dt.datetime.now(dt.timezone.utc),
            nickname_is_custom=True,
        )
        session.flush()
        plant_id = plant.id

    print(f"Created plant #{plant_id} '{args.nickname}' in room '{args.room}'")
    return plant_id


def main() -> None:
    args = parse_args()
    settings = Settings()
    seed_plant(settings, args)


if __name__ == "__main__":
    main()
