"""Pydantic request/response schemas for the API."""

import datetime as dt

from pydantic import BaseModel, ConfigDict, model_validator


class RoomCreate(BaseModel):
    name: str


class RoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int


class RoomSummaryOut(BaseModel):
    id: int
    name: str
    sort_order: int
    plant_count: int
    due_count: int
    overdue_count: int


class PlantOut(BaseModel):
    id: int
    nickname: str
    # Whether `nickname` is a user-set personal name vs. the auto-derived
    # species name default — drives "Add nickname" vs "Update
    # nickname" wording in the client's rename control.
    nickname_is_custom: bool
    room_id: int
    room_name: str
    species_id: int
    species_common_name: str | None
    photo_path: str
    next_due_at: dt.datetime | None
    last_watered_at: dt.datetime | None
    is_overdue: bool
    watering_interval_days_override: int | None
    seasonal_adjust_enabled: bool
    # What the cadence would be with the override removed (species interval,
    # seasonally adjusted for the current month) — drives the "Reset to
    # recommended: N days" button label in the cadence editor (plan 4.6).
    recommended_interval_days: int
    # perenual | llm | default | manual — where the species-level
    # recommendation came from (plan 4.2/4.6).
    care_source: str
    # Sunlight needs / soil-and-potting-mix guidance / other free-form care
    # tips (plan TODO: "Provide some care instructions for the plant"), or
    # None if care_source == "manual" or the lookup never found any.
    light: str | None
    soil: str | None
    notes: str | None


class WaterResult(BaseModel):
    undo_token: str
    plant_ids: list[int]


class UndoRequest(BaseModel):
    token: str


class UndoResult(BaseModel):
    restored_plant_ids: list[int]


class SnoozeRequest(BaseModel):
    days: int | None = None
    minutes: int | None = None

    @model_validator(mode="after")
    def validate_duration(self):
        if self.days is None and self.minutes is None:
            raise ValueError("Either days or minutes must be set")
        if self.days is not None and self.minutes is not None:
            raise ValueError("Use either days or minutes, not both")
        if self.days is not None and self.days <= 0:
            raise ValueError("days must be > 0")
        if self.minutes is not None and self.minutes <= 0:
            raise ValueError("minutes must be > 0")
        return self


class AwayRequest(BaseModel):
    days: int | None = None
    # Accepted as ISO-8601 text and parsed manually in the router (see notes there);
    # kept as str to avoid a pydantic/FastAPI request-body schema caching issue
    # observed with `dt.datetime | None` fields in this dependency combination.
    until: str | None = None


class HaActionRequest(BaseModel):
    action: str
    tag: str | None = None


class IdentifyCandidateOut(BaseModel):
    species_id: int
    scientific_name: str
    common_name: str | None
    confidence: float | None
    reference_image_url: str | None


class IdentifyResponse(BaseModel):
    photo_id: str
    candidates: list[IdentifyCandidateOut]


class SpeciesLookupResponse(BaseModel):
    candidates: list[IdentifyCandidateOut]


class DiagnoseIssueOut(BaseModel):
    issue: str
    suggestion: str


class DiagnoseResponse(BaseModel):
    healthy: bool
    issues: list[DiagnoseIssueOut]


class SpeciesManualCreate(BaseModel):
    name: str
    interval_days: int
    seasonal_profile: str = "temperate"


class PlantCreate(BaseModel):
    photo_id: str
    species_id: int
    room_id: int
    nickname: str | None = None
    interval_override: int | None = None


class PlantUpdate(BaseModel):
    nickname: str | None = None
    room_id: int | None = None
    interval_override: int | None = None
    seasonal_adjust_enabled: bool | None = None
