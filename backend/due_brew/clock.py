"""The only place the app reads the current time.

Event times are UTC; "today" is the calendar date in TZ, so a bill due on the
1st is due on the 1st locally. NOW_OVERRIDE lets a test or a manual notifier
run pretend it is any moment, and is ignored in production.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from due_brew.config import get_settings


def local_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().tz)


def now() -> datetime:
    """Current time as an aware UTC datetime."""
    settings = get_settings()
    if settings.now_override and not settings.is_production:
        override = datetime.fromisoformat(settings.now_override)
        if override.tzinfo is None:
            override = override.replace(tzinfo=local_tz())
        return override.astimezone(UTC)
    return datetime.now(UTC)


def local_now() -> datetime:
    return now().astimezone(local_tz())


def today() -> date:
    return local_now().date()
