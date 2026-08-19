"""APScheduler wiring for the 30-min notification tick — plan section 4.8.

Kept separate from app.main so create_app() (used by the whole test suite)
never starts a background thread; only app.asgi (the real uvicorn entrypoint)
calls build_scheduler().
"""

import datetime as dt
import logging
from collections.abc import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import sessionmaker

from app.clients.ha import HomeAssistantClient
from app.config import Settings
from app.services.scheduler_job import run_notification_tick
from app.services.settings_store import set_last_notification_error

LOG = logging.getLogger(__name__)


def make_tick_callable(
    *, session_factory: sessionmaker, ha_client: HomeAssistantClient, settings: Settings
) -> Callable[[], None]:
    def tick() -> None:
        session = session_factory()
        try:
            run_notification_tick(
                session,
                ha_client=ha_client,
                now=dt.datetime.now(dt.timezone.utc),
                notify_targets=settings.notify_targets,
                quiet_hours_start=settings.quiet_hours_start,
                quiet_hours_end=settings.quiet_hours_end,
                click_action=settings.app_public_url,
                timezone_name=settings.timezone,
                language=settings.language,
            )
        except Exception as exc:
            LOG.exception("Notification tick failed")
            # Surface the failure (plan section 6 hardening) instead of only
            # logging it — a revoked/expired HA token would otherwise stop
            # reminders with no user-facing signal. Best-effort: if even this
            # fails, we've already logged the original error above.
            try:
                session.rollback()
                set_last_notification_error(session, message=str(exc), at=dt.datetime.now(dt.timezone.utc))
                session.commit()
            except Exception:
                LOG.exception("Failed to record notification tick failure")
        else:
            try:
                set_last_notification_error(session, message=None)
                session.commit()
            except Exception:
                LOG.exception("Failed to clear notification tick failure")
        finally:
            session.close()

    return tick


def build_scheduler(*, session_factory: sessionmaker, settings: Settings) -> BackgroundScheduler:
    ha_client = HomeAssistantClient(base_url=settings.ha_base_url, token=settings.ha_long_lived_token)
    tick = make_tick_callable(session_factory=session_factory, ha_client=ha_client, settings=settings)

    scheduler = BackgroundScheduler()
    scheduler.add_job(tick, "interval", minutes=30, id="notification_tick")
    return scheduler
