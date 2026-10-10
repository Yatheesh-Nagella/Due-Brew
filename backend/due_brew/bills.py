"""Bill occurrences: keeping one row per due date in step with each bill's schedule.

Used by the API on bill save and before showing bills (M2), and by the
notifier each tick (M3). Safe to run any number of times.
"""

from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from due_brew import models
from due_brew.config import get_settings
from due_brew.recurrence import Schedule, due_dates

# A bill saved a few days after its due date still shows up as overdue, but a
# bill whose start date is months back doesn't flood the list with old dues.
BACKFILL_DAYS = 7


def schedule_of(bill: models.Bill) -> Schedule:
    return Schedule(bill.recurrence, bill.due_day, bill.due_month, bill.start_date, bill.end_date)


def sync_occurrences(db: Session, bill: models.Bill, today: date) -> None:
    """Make the bill's occurrences match its schedule from (today - BACKFILL_DAYS)
    through the horizon. Adds missing rows; removes unpaid rows in that range the
    schedule no longer has (edited due day, end date, deactivated). Paid rows and
    older overdue rows are never touched. Caller commits."""
    window_start = today - timedelta(days=BACKFILL_DAYS)
    window_end = today + timedelta(days=get_settings().occurrence_horizon_days)
    wanted = due_dates(schedule_of(bill), window_start, window_end) if bill.active else []

    if wanted:
        db.execute(
            insert(models.BillOccurrence)
            .values([{"bill_id": bill.id, "due_date": d} for d in wanted])
            .on_conflict_do_nothing(index_elements=["bill_id", "due_date"])
        )
    db.execute(
        delete(models.BillOccurrence).where(
            models.BillOccurrence.bill_id == bill.id,
            models.BillOccurrence.paid_at.is_(None),
            models.BillOccurrence.due_date >= window_start,
            models.BillOccurrence.due_date.not_in(wanted),
        )
    )


def sync_all(db: Session, today: date) -> None:
    for bill in db.scalars(select(models.Bill)).all():
        sync_occurrences(db, bill, today)
    db.commit()
