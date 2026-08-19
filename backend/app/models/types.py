"""Custom SQLAlchemy column types."""

import datetime as dt

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    """Stores datetimes as naive UTC (SQLite has no native tz-aware type) and
    always returns tz-aware UTC ``datetime`` objects on read.

    All application code passes tz-aware datetimes (``dt.datetime.now(dt.timezone.utc)``),
    so this type is the single place that bridges that convention to SQLite's
    naive storage, avoiding aware/naive comparison bugs everywhere else.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: dt.datetime | None, dialect) -> dt.datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("UTCDateTime requires timezone-aware datetimes")
        return value.astimezone(dt.timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: dt.datetime | None, dialect) -> dt.datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=dt.timezone.utc)
