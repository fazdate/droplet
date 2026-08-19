"""SQLAlchemy ORM models — plan section 4.2.

Package-local rule: this module is the innermost layer of the data package;
routers/services depend on it, never the other way around.
"""

import datetime as dt

from sqlalchemy import ForeignKey, Integer, String, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.models.types import UTCDateTime


class Base(DeclarativeBase):
    pass


class Room(Base):
    __tablename__ = "room"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    plants: Mapped[list["Plant"]] = relationship(back_populates="room")


class Species(Base):
    __tablename__ = "species"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scientific_name: Mapped[str] = mapped_column(String, nullable=False)
    common_name: Mapped[str | None] = mapped_column(String, nullable=True)
    reference_image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    reference_image_path: Mapped[str | None] = mapped_column(String, nullable=True)
    watering_interval_days: Mapped[int] = mapped_column(Integer, nullable=False)
    # tropical | succulent | mediterranean | temperate — drives the seasonal factor table.
    seasonal_profile: Mapped[str] = mapped_column(String, nullable=False, default="temperate")
    light: Mapped[str | None] = mapped_column(String, nullable=True)
    soil: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    # perenual | llm | default | manual
    source: Mapped[str] = mapped_column(String, nullable=False, default="manual")
    # Language `light`/`soil`/`notes` are written in (e.g. "en"/"hu"), or None
    # if none of them have ever been resolved. Lets app.services.species_resolution
    # detect a stale-language cache (deployment language changed after this row
    # was created) and re-resolve just the free text on the next re-identify —
    # see the refresh_common_name handling in get_or_create_species.
    care_language: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=lambda: dt.datetime.now(dt.timezone.utc)
    )

    plants: Mapped[list["Plant"]] = relationship(back_populates="species")


class Plant(Base):
    __tablename__ = "plant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nickname: Mapped[str] = mapped_column(String, nullable=False)
    # True once the user has explicitly set a personal nickname (at creation
    # or via the later rename control) — as opposed to the auto-derived
    # species name label every plant starts with. Drives the "Add
    # nickname" vs "Update nickname" wording in the "⋮" detail menu.
    nickname_is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    species_id: Mapped[int] = mapped_column(ForeignKey("species.id"), nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey("room.id"), nullable=False)
    photo_path: Mapped[str] = mapped_column(String, nullable=False)
    watering_interval_days_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seasonal_adjust_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_watered_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    next_due_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    snoozed_until: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # Tracks the last time a reminder was actually sent for this plant so the
    # scheduler (30-min tick) can implement "once on due date, then twice a day
    # once 1 full day late" escalation without spamming every tick. Not part of
    # the plan's original schema sketch but required to implement plan 4.8.
    last_notified_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=lambda: dt.datetime.now(dt.timezone.utc)
    )

    species: Mapped["Species"] = relationship(back_populates="plants")
    room: Mapped["Room"] = relationship(back_populates="plants")
    watering_events: Mapped[list["WateringEvent"]] = relationship(
        back_populates="plant", cascade="all, delete-orphan"
    )


class WateringEvent(Base):
    __tablename__ = "watering_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plant.id"), nullable=False)
    watered_at: Mapped[dt.datetime] = mapped_column(UTCDateTime(), nullable=False)
    # app_single | app_room | notification | manual
    source: Mapped[str] = mapped_column(String, nullable=False)

    plant: Mapped["Plant"] = relationship(back_populates="watering_events")


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)
