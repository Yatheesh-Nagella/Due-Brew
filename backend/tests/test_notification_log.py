"""The unique indexes behind "never send the same reminder twice"."""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from due_brew import models


@pytest.fixture
def occurrence(db, alice):
    bill = models.Bill(
        name="Rent", recurrence="monthly", due_day=1, start_date=date(2026, 10, 1), assignees=[alice]
    )
    bill.reminder_rules = [models.ReminderRule(days_before=3), models.ReminderRule(days_before=0)]
    db.add(bill)
    db.flush()
    occ = models.BillOccurrence(bill_id=bill.id, due_date=date(2026, 11, 1))
    db.add(occ)
    db.commit()
    return occ


def add(db, **fields):
    db.add(models.NotificationLog(**fields))
    db.commit()


def test_one_reminder_per_occurrence_rule_and_user(db, occurrence, alice, bob):
    three, zero = occurrence.bill.reminder_rules
    add(db, kind="reminder", occurrence_id=occurrence.id, rule_id=three.id, user_id=alice.id)
    add(db, kind="reminder", occurrence_id=occurrence.id, rule_id=zero.id, user_id=alice.id)
    add(db, kind="reminder", occurrence_id=occurrence.id, rule_id=three.id, user_id=bob.id)

    with pytest.raises(IntegrityError):
        add(db, kind="reminder", occurrence_id=occurrence.id, rule_id=three.id, user_id=alice.id)


def test_one_overdue_email_per_occurrence_and_user(db, occurrence, alice):
    add(db, kind="overdue", occurrence_id=occurrence.id, user_id=alice.id)

    with pytest.raises(IntegrityError):
        add(db, kind="overdue", occurrence_id=occurrence.id, user_id=alice.id)


def test_one_digest_per_user_per_day(db, alice, bob):
    add(db, kind="digest", user_id=alice.id, digest_date=date(2026, 10, 10))
    add(db, kind="digest", user_id=alice.id, digest_date=date(2026, 10, 11))
    add(db, kind="digest", user_id=bob.id, digest_date=date(2026, 10, 10))

    with pytest.raises(IntegrityError):
        add(db, kind="digest", user_id=alice.id, digest_date=date(2026, 10, 10))


def test_test_emails_are_not_limited(db, alice):
    add(db, kind="test", user_id=alice.id)
    add(db, kind="test", user_id=alice.id)


def test_unknown_kind_or_status_rejected(db, alice):
    with pytest.raises(IntegrityError):
        add(db, kind="sms", user_id=alice.id)
    db.rollback()
    with pytest.raises(IntegrityError):
        add(db, kind="test", status="queued", user_id=alice.id)
