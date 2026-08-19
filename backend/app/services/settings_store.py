"""DB-backed key/value settings — plan section 4.2 (`settings(key, value)` table).

``away_until`` and ``last_notification_error*`` live here; quiet hours/notify
targets/hemisphere are env-based (app.config.Settings) since they rarely
change and don't need a UI.
"""

import datetime as dt

from sqlalchemy.orm import Session

from app.models.orm import Setting

_AWAY_UNTIL_KEY = "away_until"
_LAST_NOTIFICATION_ERROR_KEY = "last_notification_error"
_LAST_NOTIFICATION_ERROR_AT_KEY = "last_notification_error_at"


def _set_or_clear(session: Session, key: str, value: str | None) -> None:
    row = session.get(Setting, key)
    if value is None:
        if row is not None:
            session.delete(row)
    elif row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value = value


def get_away_until(session: Session) -> dt.datetime | None:
    row = session.get(Setting, _AWAY_UNTIL_KEY)
    if row is None:
        return None
    return dt.datetime.fromisoformat(row.value)


def set_away_until(session: Session, until: dt.datetime | None) -> None:
    _set_or_clear(session, _AWAY_UNTIL_KEY, until.isoformat() if until is not None else None)
    session.flush()


def get_last_notification_error(session: Session) -> dict[str, str] | None:
    """Return the most recent notification-tick failure, or None if the last tick succeeded.

    Surfaced via /api/health (plan section 6 hardening: HA notify-call failure
    visibility) so a stale HA long-lived token doesn't fail silently.
    """
    message_row = session.get(Setting, _LAST_NOTIFICATION_ERROR_KEY)
    if message_row is None:
        return None
    at_row = session.get(Setting, _LAST_NOTIFICATION_ERROR_AT_KEY)
    return {"message": message_row.value, "at": at_row.value if at_row is not None else None}


def set_last_notification_error(session: Session, *, message: str | None, at: dt.datetime | None = None) -> None:
    """Record a notification-tick failure, or clear it (pass message=None) after a success."""
    _set_or_clear(session, _LAST_NOTIFICATION_ERROR_KEY, message)
    _set_or_clear(session, _LAST_NOTIFICATION_ERROR_AT_KEY, at.isoformat() if at is not None else None)
    session.flush()
