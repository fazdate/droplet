"""Tests for grouping notifiable plants into per-plant or per-room notification jobs."""

import datetime as dt

from app.services.notifications import NotificationJob, group_into_notification_jobs


def _plant(id: int, room_id: int, room_name: str, nickname: str) -> dict:
    return {"id": id, "room_id": room_id, "room_name": room_name, "nickname": nickname}


def test_should_produce_one_job_per_plant_when_room_has_single_notifiable_plant() -> None:
    plants = [_plant(1, 10, "Kitchen", "Basil")]

    jobs = group_into_notification_jobs(plants)

    assert jobs == [
        NotificationJob(
            tag="plant-1",
            title="Basil needs water",
            message="Basil is overdue for watering.",
            plant_ids=[1],
            room_id=10,
        )
    ]


def test_should_batch_multiple_notifiable_plants_in_same_room() -> None:
    plants = [
        _plant(1, 10, "Kitchen", "Basil"),
        _plant(2, 10, "Kitchen", "Mint"),
        _plant(3, 10, "Kitchen", "Thyme"),
    ]

    jobs = group_into_notification_jobs(plants)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.tag == "room-10"
    assert job.title == "Kitchen: 3 plants need water"
    assert job.plant_ids == [1, 2, 3]
    assert job.room_id == 10


def test_should_produce_separate_jobs_for_separate_rooms() -> None:
    plants = [
        _plant(1, 10, "Kitchen", "Basil"),
        _plant(2, 20, "Bedroom", "Fern"),
    ]

    jobs = group_into_notification_jobs(plants)

    assert {job.tag for job in jobs} == {"plant-1", "plant-2"}


def test_should_return_empty_list_when_no_plants() -> None:
    assert group_into_notification_jobs([]) == []
