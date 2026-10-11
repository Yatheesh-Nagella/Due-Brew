"""The notifier end to end against real Postgres: NOW_OVERRIDE + FakeSender.

Covers everything claude.md asks the notifier tests to prove.
"""

import threading
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, update

from due_brew import bills, clock, models
from due_brew.database import SessionLocal
from due_brew.emails.sender import FakeSender
from due_brew.notifier import dispatch
from due_brew.notifier.planner import Notice
from due_brew.notifier.tick import run_tick

NL = models.NotificationLog


@pytest.fixture
def sender():
    return FakeSender()


@pytest.fixture
def tick(env, sender):
    """tick("2026-10-29T08:05") runs one notifier tick at that local time."""

    def _tick(at, using=None):
        env(NOW_OVERRIDE=at)
        with SessionLocal() as session:
            return run_tick(session, using or sender, clock.now())

    return _tick


@pytest.fixture
def make_bill(db, env):
    def _make(name="Rent", assignees=(), due_day=1, days=(3, 0), amount="1200", start=date(2026, 10, 1)):
        bill = models.Bill(
            name=name,
            amount=Decimal(amount) if amount is not None else None,
            recurrence="monthly",
            due_day=due_day,
            start_date=start,
            assignees=list(assignees),
        )
        bill.reminder_rules = [models.ReminderRule(days_before=d) for d in days]
        db.add(bill)
        db.commit()
        return bill

    return _make


def occurrence(db, bill, due):
    """Make sure the occurrence exists (a tick would too) and return it."""
    bills.sync_occurrences(db, bill, due - timedelta(days=1))
    db.commit()
    return db.scalar(
        select(models.BillOccurrence).where(
            models.BillOccurrence.bill_id == bill.id, models.BillOccurrence.due_date == due
        )
    )


def log_rows(db, **filters):
    db.expire_all()
    query = select(NL).order_by(NL.created_at)
    for key, value in filters.items():
        query = query.where(getattr(NL, key) == value)
    return db.scalars(query).unique().all()


# --- right day, right hour ---


def test_reminder_fires_on_the_right_day_and_hour(tick, sender, make_bill, alice):
    make_bill(assignees=[alice])

    tick("2026-10-29T07:55")
    assert sender.sent == []

    tick("2026-10-29T08:05")
    assert sender.subjects() == ["[due-brew] Rent due in 3 days ($1,200 on Nov 1)"]
    assert sender.sent[0].to == alice.email

    tick("2026-11-01T08:05")
    assert sender.subjects()[-1] == "[due-brew] Rent due today ($1,200 on Nov 1)"


def test_every_assignee_gets_one(tick, sender, make_bill, alice, bob):
    make_bill(assignees=[alice, bob], days=(0,))

    tick("2026-11-01T09:00")  # Alice's and Bob's default hour is 8

    assert sorted(e.to for e in sender.sent) == sorted([alice.email, bob.email])


def test_two_ticks_in_a_row_send_nothing_twice(tick, sender, make_bill, alice, db):
    make_bill(assignees=[alice])

    tick("2026-10-29T08:05")
    tick("2026-10-29T08:10")
    tick("2026-10-29T13:00")

    assert len(sender.sent) == 1
    [row] = log_rows(db, kind="reminder", status="sent")
    assert row.attempts == 1 and row.subject.startswith("[due-brew] Rent due in 3 days")


def test_paid_occurrence_gets_no_reminders(tick, sender, make_bill, alice, db):
    bill = make_bill(assignees=[alice])
    occ = occurrence(db, bill, date(2026, 11, 1))
    occ.paid_at, occ.paid_by = clock.now(), alice.id
    db.commit()

    tick("2026-10-29T08:05")
    tick("2026-11-01T08:05")
    tick("2026-11-03T08:05")

    assert sender.sent == []


def test_deactivated_bill_and_email_off(tick, sender, make_bill, alice, bob, db):
    bill = make_bill(assignees=[alice])
    bill.active = False
    make_bill(name="Gym", assignees=[bob])
    bob.email_enabled = False
    db.commit()

    tick("2026-10-29T08:05")

    assert sender.sent == []


# --- crash recovery ---


def crash_after_claim(db, alice, bill, at, env):
    """Claim a reminder the way a tick does, then 'crash' before sending."""
    env(NOW_OVERRIDE=at)
    occ = occurrence(db, bill, date(2026, 11, 1))
    rule = next(r for r in bill.reminder_rules if r.days_before == 3)
    notice = Notice("reminder", occ.id, rule.id, alice.id, date(2026, 10, 29), late=False)
    return dispatch.claim_new(db, [notice], clock.now())


def test_stale_pending_claim_is_resent_once(tick, sender, make_bill, alice, db, env):
    bill = make_bill(assignees=[alice], days=(3,))
    [claimed] = crash_after_claim(db, alice, bill, "2026-10-29T08:05", env)

    tick("2026-10-29T08:10")  # 5 minutes: maybe still being sent elsewhere; leave it
    assert sender.sent == []

    tick("2026-10-29T08:16")  # 11 minutes > STALE_PENDING_MINUTES (10): take over
    tick("2026-10-29T08:30")
    assert len(sender.sent) == 1
    [row] = log_rows(db, id=claimed)
    assert (row.status, row.attempts) == ("sent", 1)


def test_two_concurrent_ticks_cannot_both_reclaim(make_bill, alice, db, env):
    bill = make_bill(assignees=[alice], days=(3,))
    crash_after_claim(db, alice, bill, "2026-10-29T08:05", env)
    env(NOW_OVERRIDE="2026-10-29T08:30")
    now = clock.now()

    barrier = threading.Barrier(8)
    results = []

    def contender():
        with SessionLocal() as session:
            barrier.wait()
            results.append(dispatch.reclaim_stale(session, now))

    threads = [threading.Thread(target=contender) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(len(r) for r in results) == [0] * 7 + [1]


def test_concurrent_claims_of_new_rows_insert_once(make_bill, alice, db, env):
    bill = make_bill(assignees=[alice], days=(3,))
    env(NOW_OVERRIDE="2026-10-29T08:05")
    occ = occurrence(db, bill, date(2026, 11, 1))
    notice = Notice("reminder", occ.id, bill.reminder_rules[0].id, alice.id, date(2026, 10, 29), False)
    barrier = threading.Barrier(6)
    results = []

    def contender():
        with SessionLocal() as session:
            barrier.wait()
            results.append(dispatch.claim_new(session, [notice], clock.now()))

    threads = [threading.Thread(target=contender) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(len(r) for r in results) == [0] * 5 + [1]


# --- catch-up ---


def test_catch_up_within_48_hours_is_sent_late(tick, sender, make_bill, alice):
    make_bill(assignees=[alice], days=(3,))

    tick("2026-10-30T12:00")  # Pi was off at Oct 29 08:00; 28h later

    assert sender.subjects() == ["[due-brew] (late) Rent due in 2 days ($1,200 on Nov 1)"]


def test_older_than_48_hours_is_skipped_and_logged(tick, sender, make_bill, alice, db):
    make_bill(assignees=[alice], days=(3,))

    tick("2026-10-31T09:00")  # 49h late
    tick("2026-10-31T10:00")

    assert sender.sent == []
    [row] = log_rows(db, kind="reminder")
    assert row.status == "skipped"


# --- overdue ---


def test_individual_mode_gets_one_overdue_email(tick, sender, make_bill, alice):
    make_bill(assignees=[alice], days=())

    tick("2026-11-02T08:05")
    tick("2026-11-03T08:05")
    tick("2026-11-05T08:05")

    assert sender.subjects() == ["[due-brew] Rent is overdue ($1,200, was due Nov 1)"]


# --- retries ---


def test_failed_send_is_retried_with_backoff(tick, sender, make_bill, alice, db):
    make_bill(assignees=[alice], days=(3,))
    sender.failing, sender.fail_times = True, 1

    tick("2026-10-29T08:00")
    [row] = log_rows(db, kind="reminder")
    assert (row.status, row.attempts) == ("failed", 1)
    assert row.last_error == "SMTP unavailable"

    tick("2026-10-29T08:04")  # backoff after the 1st failure is 5 minutes
    assert sender.sent == []

    tick("2026-10-29T08:05")
    [row] = log_rows(db, kind="reminder")
    assert (row.status, row.attempts, row.last_error) == ("sent", 2, None)
    assert len(sender.sent) == 1


def test_gives_up_after_five_failures(tick, sender, make_bill, alice, db):
    make_bill(assignees=[alice], days=(3,))
    sender.failing = True

    # 08:00 fail #1, +5m #2, +15m #3, +45m #4, +120m #5; then nothing more.
    for at in ("08:00", "08:05", "08:20", "09:05", "11:05", "15:00", "23:00"):
        tick(f"2026-10-29T{at}")

    [row] = log_rows(db, kind="reminder")
    assert (row.status, row.attempts, row.next_attempt_at) == ("failed", 5, None)


def test_retry_skips_once_paid(tick, sender, make_bill, alice, db):
    bill = make_bill(assignees=[alice], days=(3,))
    sender.failing = True
    tick("2026-10-29T08:00")
    occ = occurrence(db, bill, date(2026, 11, 1))
    occ.paid_at = clock.now()
    db.commit()
    sender.failing = False

    tick("2026-10-29T08:10")

    [row] = log_rows(db, kind="reminder")
    assert (row.status, row.last_error) == ("skipped", "paid before it was sent")
    assert sender.sent == []


# --- digest ---


@pytest.fixture
def digest_alice(alice, db):
    alice.notify_mode = "digest"
    db.commit()
    return alice


def test_digest_groups_the_day_into_one_email(tick, sender, make_bill, digest_alice, db):
    make_bill(name="Rent", assignees=[digest_alice], due_day=13, days=(3,))
    make_bill(name="Internet", assignees=[digest_alice], due_day=10, days=(0,), amount=None)
    make_bill(name="Electric", assignees=[digest_alice], due_day=8, days=(), amount="87.45")  # overdue

    tick("2026-10-10T07:59")
    assert sender.sent == []

    tick("2026-10-10T08:01")
    tick("2026-10-10T12:00")

    assert sender.subjects() == ["[due-brew] 3 bills need attention today"]
    text = sender.sent[0].text
    assert "Electric" in text and "Internet: amount not set, due today" in text and "Rent: $1,200" in text
    [digest] = log_rows(db, kind="digest")
    assert digest.status == "sent" and digest.digest_date == date(2026, 10, 10)
    items = log_rows(db, digest_id=digest.id)
    assert {i.kind for i in items} == {"reminder", "overdue"} and {i.status for i in items} == {"sent"}


def test_digest_repeats_overdue_daily_for_a_week(tick, sender, make_bill, digest_alice):
    make_bill(name="Electric", assignees=[digest_alice], due_day=8, days=(), start=date(2026, 10, 1))

    for day in range(9, 18):  # Oct 9 .. Oct 17
        tick(f"2026-10-{day:02d}T09:00")

    # Overdue Oct 9..15 (1-7 days after Oct 8): one digest each day, then none.
    assert sender.subjects() == ["[due-brew] 1 bill needs attention today"] * 7


def test_no_digest_on_a_quiet_day(tick, sender, make_bill, digest_alice):
    make_bill(assignees=[digest_alice], days=(3,))

    tick("2026-10-20T09:00")

    assert sender.sent == []


def test_switching_to_digest_does_not_repeat_todays_emails(tick, sender, make_bill, alice, db):
    make_bill(assignees=[alice], days=(3,))
    tick("2026-10-29T08:05")  # individual email sent
    alice.notify_mode = "digest"
    db.commit()

    tick("2026-10-29T09:00")

    assert len(sender.sent) == 1
    assert log_rows(db, kind="digest") == []


def test_failed_digest_is_retried_as_one_email(tick, sender, make_bill, digest_alice, db):
    make_bill(name="Rent", assignees=[digest_alice], due_day=13, days=(3,))
    sender.failing, sender.fail_times = True, 1

    tick("2026-10-10T08:00")
    tick("2026-10-10T08:06")

    assert sender.subjects() == ["[due-brew] 1 bill needs attention today"]
    [digest] = log_rows(db, kind="digest")
    assert (digest.status, digest.attempts) == ("sent", 2)
    assert {i.status for i in log_rows(db, digest_id=digest.id)} == {"sent"}


# --- heartbeat ---


def test_each_tick_writes_the_heartbeat(tick, db):
    tick("2026-10-29T08:05")

    beat = db.scalar(select(models.NotifierHeartbeat.beat_at))
    assert beat == clock.now()


def test_stale_reclaim_ignores_rows_inside_digests_and_test_emails(db, alice, env):
    env(NOW_OVERRIDE="2026-10-29T09:00")
    old = clock.now() - timedelta(hours=1)
    db.add(NL(kind="test", user_id=alice.id, status="pending", claimed_at=old))
    db.commit()
    db.execute(update(NL).values(claimed_at=old))
    db.commit()

    assert dispatch.reclaim_stale(db, clock.now()) == []
