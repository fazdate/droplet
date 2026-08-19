"""Scheduler job: the 30-min tick that decides who to notify — plan section 4.8.

Wired to APScheduler in app.scheduler; kept here as a plain function so it can
be unit tested without a real scheduler or HTTP calls.
"""

import datetime as dt
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.languages import DEFAULT_LANGUAGE
from app.i18n import translate
from app.models.orm import Plant
from app.services.notifications import NotificationJob, group_into_notification_jobs, should_notify_plant
from app.services.settings_store import get_away_until


class NotifierProtocol(Protocol):
    def notify(
        self, *, targets: list[str], title: str, message: str, tag: str, actions: list[dict], click_action: str
    ) -> None: ...


def _build_actions(job: NotificationJob, language: str = DEFAULT_LANGUAGE) -> list[dict]:
    if len(job.plant_ids) == 1:
        plant_id = job.plant_ids[0]
        return [
            {"action": f"WATERED_{plant_id}", "title": translate("action_watered", language)},
            {"action": f"SNOOZE_1D_{plant_id}", "title": translate("action_snooze_1d", language)},
            {"action": "AWAY_3D", "title": translate("action_away_3d", language)},
        ]
    return [
        {"action": f"WATERED_ROOM_{job.room_id}", "title": translate("action_water_all", language)},
        {"action": "AWAY_3D", "title": translate("action_away_3d", language)},
    ]


def run_notification_tick(
    session: Session,
    *,
    ha_client: NotifierProtocol,
    now: dt.datetime,
    notify_targets: list[str],
    quiet_hours_start: int,
    quiet_hours_end: int,
    click_action: str,
    timezone_name: str = "UTC",
    language: str = DEFAULT_LANGUAGE,
) -> list[NotificationJob]:
    if not notify_targets:
        return []

    away_until = get_away_until(session)
    plants = session.scalars(select(Plant).where(Plant.next_due_at.is_not(None))).all()

    notifiable = [
        plant
        for plant in plants
        if should_notify_plant(
            next_due_at=plant.next_due_at,
            snoozed_until=plant.snoozed_until,
            last_notified_at=plant.last_notified_at,
            now=now,
            away_until=away_until,
            quiet_hours_start=quiet_hours_start,
            quiet_hours_end=quiet_hours_end,
            timezone_name=timezone_name,
        )
    ]

    plant_dicts = [
        {"id": p.id, "room_id": p.room_id, "room_name": p.room.name, "nickname": p.nickname} for p in notifiable
    ]
    jobs = group_into_notification_jobs(plant_dicts, language=language)

    plants_by_id = {p.id: p for p in notifiable}
    for job in jobs:
        ha_client.notify(
            targets=notify_targets,
            title=job.title,
            message=job.message,
            tag=job.tag,
            actions=_build_actions(job, language=language),
            click_action=click_action,
        )
        for plant_id in job.plant_ids:
            plants_by_id[plant_id].last_notified_at = now

    session.commit()
    return jobs
