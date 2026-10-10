from datetime import UTC, date, datetime

from due_brew import clock


def test_now_override_naive_is_local_time(env):
    env(NOW_OVERRIDE="2026-10-31T23:30:00", TZ="America/Chicago")

    # 23:30 CDT is 04:30 UTC the next day, but "today" stays local.
    assert clock.now() == datetime(2026, 11, 1, 4, 30, tzinfo=UTC)
    assert clock.today() == date(2026, 10, 31)


def test_now_override_ignored_in_production(env):
    env(APP_ENV="production", NOW_OVERRIDE="2001-01-01T00:00:00")

    assert clock.now().year >= 2026
