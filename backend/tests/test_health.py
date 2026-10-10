from datetime import timedelta

from due_brew import clock, heartbeat
from due_brew.notifier import tick


def test_health_needs_no_identity(client, env):
    env(APP_ENV="production")

    res = client.get("/api/health")

    assert res.status_code == 200
    assert res.json() == {"status": "ok", "db": "ok", "notifier_heartbeat_age_seconds": None}


def test_health_reports_heartbeat_age(client, db, env):
    env(NOW_OVERRIDE="2026-10-03T09:00:00")
    tick()
    env(NOW_OVERRIDE="2026-10-03T09:05:00")

    assert client.get("/api/health").json()["notifier_heartbeat_age_seconds"] == 300


def test_heartbeat_is_a_single_row_that_moves_forward(db, env):
    env(NOW_OVERRIDE="2026-10-03T09:00:00")
    heartbeat.beat(db)
    first = heartbeat.last_beat(db)
    env(NOW_OVERRIDE="2026-10-03T09:10:00")
    heartbeat.beat(db)

    assert heartbeat.last_beat(db) - first == timedelta(minutes=10)
    assert heartbeat.last_beat(db) == clock.now()
