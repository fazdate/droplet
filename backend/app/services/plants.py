"""Plant/room/species creation helpers — used by the manual seed script (phase 1),
the AI identify flow, and the manual escape-hatch add-plant form (phase 3)."""

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orm import Plant, Room, Species


def find_or_create_room(session: Session, name: str) -> Room:
    room = session.scalars(select(Room).where(Room.name == name)).first()
    if room is not None:
        return room
    room = Room(name=name)
    session.add(room)
    session.flush()
    return room


def find_or_create_species_manual(
    session: Session,
    *,
    name: str,
    interval_days: int,
    common_name: str | None = None,
    seasonal_profile: str = "temperate",
) -> Species:
    """Manual species are matched by scientific_name (here: whatever free-text
    name the user typed) among source='manual' rows, so the second identical
    manual entry is reused rather than duplicated."""
    species = session.scalars(
        select(Species).where(Species.scientific_name == name, Species.source == "manual")
    ).first()
    if species is not None:
        return species

    species = Species(
        scientific_name=name,
        common_name=common_name,
        watering_interval_days=interval_days,
        seasonal_profile=seasonal_profile,
        source="manual",
    )
    session.add(species)
    session.flush()
    return species


def create_plant(
    session: Session,
    *,
    nickname: str,
    room: Room,
    species: Species,
    photo_path: str,
    now: dt.datetime,
    nickname_is_custom: bool = False,
) -> Plant:
    """A freshly added plant has no watering history yet; it is marked due
    immediately so it surfaces on the daily list right away."""
    plant = Plant(
        nickname=nickname,
        nickname_is_custom=nickname_is_custom,
        room_id=room.id,
        species_id=species.id,
        photo_path=photo_path,
        last_watered_at=None,
        next_due_at=now,
    )
    session.add(plant)
    session.flush()
    return plant
