"""PATCH /me, GET /notifications, POST /notifications/test."""

from datetime import date
from decimal import Decimal

import pytest

from due_brew import clock, models
from due_brew.database import SessionLocal
from due_brew.emails import sender as sender_module
from due_brew.emails.sender import FakeSender
from due_brew.notifier.tick import run_tick


@pytest.fixture
def fake(monkeypatch):
    fake = FakeSender()
    monkeypatch.setattr(sender_module, "get_sender", lambda: fake)
    return fake


# --- PATCH /me ---


def test_update_own_preferences(as_user, alice, bob, db):
    res = as_user(alice).patch(
        "/api/me",
        json={
            "email": " new@example.com ",
            "notify_mode": "digest",
            "digest_hour": 19,
            "email_enabled": False,
        },
    )

    assert res.status_code == 200
    me = res.json()
    assert (me["email"], me["notify_mode"], me["digest_hour"], me["email_enabled"]) == (
        "new@example.com",
        "digest",
        19,
        False,
    )
    # Bob is untouched; you can only change yourself.
    db.refresh(bob)
    assert bob.notify_mode == "individual"


def test_partial_update_keeps_other_fields(as_user, alice, db):
    # (Read back from the database: the test identity override hands every
    # request the same in-memory User, unlike get_current_user.)
    email = alice.email
    as_user(alice).patch("/api/me", json={"digest_hour": 6})

    db.refresh(alice)
    assert (alice.digest_hour, alice.notify_mode, alice.email) == (6, "individual", email)


@pytest.mark.parametrize(
    "body",
    [
        {"digest_hour": 24},
        {"digest_hour": -1},
        {"notify_mode": "sms"},
        {"email": "not-an-email"},
        {"email": None},
        {"notify_mode": None},
    ],
)
def test_invalid_preferences_rejected(as_user, alice, body):
    assert as_user(alice).patch("/api/me", json=body).status_code == 422


# --- POST /notifications/test ---


def test_send_test_email(as_user, alice, fake):
    res = as_user(alice).post("/api/notifications/test")

    assert res.status_code == 200
    assert res.json()["status"] == "sent" and res.json()["kind"] == "test"
    assert [(e.to, e.subject) for e in fake.sent] == [(alice.email, "[due-brew] Test email")]


def test_test_email_failure_is_reported_and_logged(as_user, alice, fake):
    fake.failing = True

    res = as_user(alice).post("/api/notifications/test")

    assert res.status_code == 502
    assert "SMTP unavailable" in res.json()["detail"]
    [row] = as_user(alice).get("/api/notifications").json()
    assert (row["kind"], row["status"], row["last_error"]) == ("test", "failed", "SMTP unavailable")


# --- GET /notifications ---


def test_log_newest_first_with_bill_details(as_user, alice, db, env, fake):
    bill = models.Bill(
        name="Rent",
        amount=Decimal(1200),
        recurrence="monthly",
        due_day=1,
        start_date=date(2026, 10, 1),
        assignees=[alice],
    )
    bill.reminder_rules = [models.ReminderRule(days_before=3)]
    db.add(bill)
    db.commit()
    env(NOW_OVERRIDE="2026-10-29T08:05")
    with SessionLocal() as session:
        run_tick(session, fake, clock.now())
    as_user(alice).post("/api/notifications/test")

    rows = as_user(alice).get("/api/notifications").json()

    assert [r["kind"] for r in rows] == ["test", "reminder"]
    reminder = rows[1]
    assert reminder["bill_name"] == "Rent" and reminder["due_date"] == "2026-11-01"
    assert reminder["to"] == alice.email and reminder["user"]["display_name"] == alice.display_name
    assert reminder["subject"] == "[due-brew] Rent due in 3 days ($1,200 on Nov 1)"
    assert reminder["status"] == "sent" and reminder["attempts"] == 1


def test_digest_shows_as_one_row_with_its_item_count(as_user, alice, db, env, fake):
    alice.notify_mode = "digest"
    for name, day in (("Rent", 13), ("Internet", 12)):
        bill = models.Bill(
            name=name, recurrence="monthly", due_day=day, start_date=date(2026, 10, 1), assignees=[alice]
        )
        bill.reminder_rules = [models.ReminderRule(days_before=day - 10)]
        db.add(bill)
    db.commit()
    env(NOW_OVERRIDE="2026-10-10T09:00")
    with SessionLocal() as session:
        run_tick(session, fake, clock.now())

    rows = as_user(alice).get("/api/notifications").json()

    assert [(r["kind"], r["items"], r["status"]) for r in rows] == [("digest", 2, "sent")]


def test_limit(as_user, alice, fake):
    for _ in range(3):
        as_user(alice).post("/api/notifications/test")

    assert len(as_user(alice).get("/api/notifications?limit=2").json()) == 2
    assert as_user(alice).get("/api/notifications?limit=0").status_code == 422
