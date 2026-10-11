"""Claim, send, record: the part of a tick that must never send twice.

1. Claim. Every email owed is first a notification_log row. New ones are
   INSERTed with ON CONFLICT DO NOTHING, so the unique indexes decide who owns
   a send: a second tick (or a restart) finds the row taken. The claim is
   committed before anything is sent.
2. Recover. A row left `pending` for STALE_PENDING_MINUTES (a crash between
   claim and record) and a `failed` row whose backoff has passed are re-claimed
   with a single UPDATE ... WHERE ... RETURNING, which Postgres runs atomically,
   so two ticks can't both take the same row.
3. Send, then record sent/failed. Delivery is at-least-once: a crash after
   Gmail accepts the email but before the row says `sent` re-sends it once.

Digest users get one email per day under a `digest` row; the reminder/overdue
rows it covers point at it via digest_id and share its fate.
"""

import logging
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from due_brew import models
from due_brew.config import get_settings
from due_brew.emails import compose
from due_brew.emails.sender import EmailSender
from due_brew.notifier.planner import OVERDUE_DAYS, Notice

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
# Wait after the 1st, 2nd, 3rd and 4th failure; the 5th failure is final.
BACKOFF = [timedelta(minutes=m) for m in (5, 15, 45, 120)]

NL = models.NotificationLog


def _row_values(notice: Notice, now: datetime, status: str, digest_id: uuid.UUID | None = None) -> dict:
    return {
        "id": uuid.uuid4(),
        "kind": notice.kind,
        "occurrence_id": notice.occurrence_id,
        "rule_id": notice.rule_id,
        "user_id": notice.user_id,
        "status": status,
        "claimed_at": now if status == "pending" else None,
        "digest_id": digest_id,
    }


# --- claiming ---


def claim_new(db: Session, notices: list[Notice], now: datetime) -> list[uuid.UUID]:
    """Insert pending rows; returns only the ids this call actually inserted."""
    if not notices:
        return []
    rows = db.execute(
        insert(NL)
        .values([_row_values(n, now, "pending") for n in notices])
        .on_conflict_do_nothing()
        .returning(NL.id)
    )
    ids = list(rows.scalars())
    db.commit()
    return ids


def record_skipped(db: Session, notices: list[Notice], now: datetime) -> None:
    """Missed beyond catch-up: log as skipped (once) so the log explains the gap."""
    if not notices:
        return
    db.execute(insert(NL).values([_row_values(n, now, "skipped") for n in notices]).on_conflict_do_nothing())
    db.commit()


def reclaim_stale(db: Session, now: datetime) -> list[uuid.UUID]:
    """Take over rows a crashed tick claimed but never recorded."""
    cutoff = now - timedelta(minutes=get_settings().stale_pending_minutes)
    rows = db.execute(
        update(NL)
        .where(NL.status == "pending", NL.claimed_at < cutoff, NL.digest_id.is_(None), NL.kind != "test")
        .values(claimed_at=now)
        .returning(NL.id)
    )
    ids = list(rows.scalars())
    db.commit()
    return ids


def reclaim_retries(db: Session, now: datetime) -> list[uuid.UUID]:
    """Take failed rows whose backoff has passed (and that have attempts left)."""
    rows = db.execute(
        update(NL)
        .where(
            NL.status == "failed",
            NL.attempts < MAX_ATTEMPTS,
            NL.next_attempt_at <= now,
            NL.digest_id.is_(None),
            NL.kind != "test",
        )
        .values(status="pending", claimed_at=now)
        .returning(NL.id)
    )
    ids = list(rows.scalars())
    db.commit()
    return ids


def overdue_for(db: Session, user_id: uuid.UUID, today: date) -> list[models.BillOccurrence]:
    """Unpaid occurrences of active bills assigned to the user, 1-7 days overdue."""
    occ = models.BillOccurrence
    return list(
        db.scalars(
            select(occ)
            .join(models.Bill)
            .join(models.BillAssignee, models.BillAssignee.bill_id == models.Bill.id)
            .where(
                models.BillAssignee.user_id == user_id,
                models.Bill.active,
                occ.paid_at.is_(None),
                occ.due_date < today,
                occ.due_date >= today - timedelta(days=OVERDUE_DAYS),
            )
            .order_by(occ.due_date)
        )
        .unique()
        .all()
    )


def claim_digest(
    db: Session, user: models.User, notices: list[Notice], today: date, now: datetime
) -> uuid.UUID | None:
    """Claim today's digest for `user` and the items it will carry. None if there's
    nothing new to say, or another tick already has today's digest."""
    overdue = overdue_for(db, user.id, today)
    if not notices and not overdue:
        return None
    digest_id = db.scalar(
        insert(NL)
        .values(
            id=uuid.uuid4(),
            kind="digest",
            user_id=user.id,
            digest_date=today,
            status="pending",
            claimed_at=now,
        )
        .on_conflict_do_nothing()
        .returning(NL.id)
    )
    if digest_id is None:
        db.rollback()
        return None
    items = []
    if notices:
        items = db.execute(
            insert(NL)
            .values([_row_values(n, now, "pending", digest_id) for n in notices])
            .on_conflict_do_nothing()
            .returning(NL.id)
        ).all()
    if not items and not overdue:
        # Everything owed was already sent some other way (e.g. before a switch
        # from individual mode): no digest today after all.
        db.execute(delete(NL).where(NL.id == digest_id))
        db.commit()
        return None
    db.commit()
    return digest_id


# --- sending ---


def _line(occ: models.BillOccurrence, today: date, late: bool = False) -> compose.BillLine:
    return compose.BillLine(
        bill_name=occ.bill.name,
        amount=occ.effective_amount,
        due_date=occ.due_date,
        assignees=[u.display_name for u in occ.bill.assignees],
        days_until=(occ.due_date - today).days,
        late=late,
    )


def _still_owed(occ: models.BillOccurrence | None) -> str | None:
    """Why an email should no longer go out, or None if it should."""
    if occ is None:
        return "bill deleted"
    if occ.paid_at is not None:
        return "paid before it was sent"
    if not occ.bill.active:
        return "bill deactivated"
    return None


def _single_email(db: Session, row: models.NotificationLog, today: date):
    """The email for a reminder/overdue row, or a reason to skip it."""
    occ = row.occurrence
    reason = _still_owed(occ)
    if reason:
        return None, reason
    base_url = get_settings().app_base_url
    if row.kind == "overdue":
        line = _line(occ, today)
        return compose.overdue_email(row.user.email, row.user.display_name, line, base_url), None
    rule = db.get(models.ReminderRule, row.rule_id) if row.rule_id else None
    if rule is None:
        return None, "reminder removed from the bill"
    send_date = occ.due_date - timedelta(days=rule.days_before)
    line = _line(occ, today, late=send_date < today)
    return compose.reminder_email(row.user.email, row.user.display_name, line, base_url), None


def _digest_email(db: Session, row: models.NotificationLog, today: date):
    items = db.scalars(select(NL).where(NL.digest_id == row.id)).unique().all()
    overdue = {o.id: o for o in overdue_for(db, row.user_id, today)}
    due: dict[uuid.UUID, compose.BillLine] = {}
    for item in items:
        occ = item.occurrence
        if _still_owed(occ) or occ.id in overdue or occ.due_date < today:
            continue
        rule = db.get(models.ReminderRule, item.rule_id) if item.rule_id else None
        late = rule is not None and occ.due_date - timedelta(days=rule.days_before) < today
        due.setdefault(occ.id, _line(occ, today, late))
    if not due and not overdue:
        return None, "nothing left to remind about"
    due_lines = sorted(due.values(), key=lambda line: (line.due_date, line.bill_name))
    overdue_lines = [_line(o, today) for o in overdue.values()]
    email = compose.digest_email(
        row.user.email, row.user.display_name, due_lines, overdue_lines, get_settings().app_base_url
    )
    return email, None


def _record(db: Session, row: models.NotificationLog, now: datetime, **values) -> None:
    db.execute(update(NL).where(NL.id == row.id).values(**values))
    if row.kind == "digest":
        # The rows a digest carries share its outcome.
        item_values = {k: v for k, v in values.items() if k in ("status", "sent_at", "last_error")}
        db.execute(update(NL).where(NL.digest_id == row.id).values(**item_values))
    db.commit()


def deliver(db: Session, sender: EmailSender, row_id: uuid.UUID, now: datetime, today: date) -> str:
    """Send one claimed row (a single email or a digest) and record the outcome."""
    row = db.get(NL, row_id)
    if row is None:
        return "gone"
    if row.kind == "digest":
        email, skip_reason = _digest_email(db, row, today)
    else:
        email, skip_reason = _single_email(db, row, today)

    if email is None:
        _record(db, row, now, status="skipped", last_error=skip_reason, next_attempt_at=None)
        return "skipped"
    if not row.user.email_enabled:
        _record(db, row, now, status="skipped", last_error="email turned off", next_attempt_at=None)
        return "skipped"

    attempts = row.attempts + 1
    try:
        sender.send(email)
    except Exception as exc:  # any delivery failure is retried, never fatal to the tick
        give_up = attempts >= MAX_ATTEMPTS
        log.warning("send failed (attempt %d) for %s: %s", attempts, row.kind, exc)
        _record(
            db,
            row,
            now,
            status="failed",
            attempts=attempts,
            subject=email.subject,
            last_error=str(exc)[:500] or exc.__class__.__name__,
            next_attempt_at=None if give_up else now + BACKOFF[attempts - 1],
        )
        return "failed"

    _record(
        db,
        row,
        now,
        status="sent",
        attempts=attempts,
        subject=email.subject,
        sent_at=now,
        last_error=None,
        next_attempt_at=None,
    )
    return "sent"
