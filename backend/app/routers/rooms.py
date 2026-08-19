"""Rooms API — plan section 4.3."""

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models.orm import Plant, Room
from app.schemas import RoomCreate, RoomOut, RoomSummaryOut
from app.utils.errors import not_found

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


@router.post("", response_model=RoomOut, status_code=201)
def create_room(payload: RoomCreate, db: Session = Depends(get_db)) -> Room:
    room = Room(name=payload.name)
    db.add(room)
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Room name already exists") from exc
    db.refresh(room)
    return room


@router.post("/{room_id}", response_model=RoomOut)
def rename_room(room_id: int, payload: RoomCreate, db: Session = Depends(get_db)) -> Room:
    room = db.get(Room, room_id)
    if room is None:
        raise not_found("Room")
    room.name = payload.name
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Room name already exists") from exc
    db.refresh(room)
    return room


@router.delete("/{room_id}", status_code=204)
def delete_room(room_id: int, db: Session = Depends(get_db)) -> Response:
    """Removes an empty room (TODO.md: room stays around after its last plant
    is removed). Rejected with 409 if the room still has plants — the
    frontend only shows the remove-room control once plant_count is 0, so
    hitting this is only possible via a direct API call."""
    room = db.get(Room, room_id)
    if room is None:
        raise not_found("Room")

    plant_count = db.scalar(select(func.count(Plant.id)).where(Plant.room_id == room_id))
    if plant_count:
        raise HTTPException(status_code=409, detail="Room still has plants")

    db.delete(room)
    db.flush()
    return Response(status_code=204)


@router.get("", response_model=list[RoomSummaryOut])
def list_rooms(db: Session = Depends(get_db)) -> list[RoomSummaryOut]:
    now = dt.datetime.now(dt.timezone.utc)
    rooms = db.scalars(select(Room).order_by(Room.sort_order, Room.name)).all()

    counts = dict(
        db.execute(
            select(Plant.room_id, func.count(Plant.id)).group_by(Plant.room_id)
        ).all()
    )
    overdue_counts = dict(
        db.execute(
            select(Plant.room_id, func.count(Plant.id))
            .where(Plant.next_due_at.is_not(None), Plant.next_due_at < now)
            .group_by(Plant.room_id)
        ).all()
    )
    due_counts = dict(
        db.execute(
            select(Plant.room_id, func.count(Plant.id))
            .where(
                Plant.next_due_at.is_not(None),
                Plant.next_due_at >= now,
                Plant.next_due_at < now + dt.timedelta(days=1),
            )
            .group_by(Plant.room_id)
        ).all()
    )

    return [
        RoomSummaryOut(
            id=room.id,
            name=room.name,
            sort_order=room.sort_order,
            plant_count=counts.get(room.id, 0),
            due_count=due_counts.get(room.id, 0),
            overdue_count=overdue_counts.get(room.id, 0),
        )
        for room in rooms
    ]
