"""One notifier tick, in the order claude.md lays out:

1. generate occurrences   2. find due reminders   3. claim
4. send                   5. record (inside deliver)
"""

import logging
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from due_brew import bills, clock, heartbeat, models
from due_brew.config import get_settings
from due_brew.emails.sender import EmailSender
from due_brew.notifier import dispatch
from due_brew.notifier.planner import OVERDUE_DAYS, OpenOccurrence, Recipient, Rule, plan

log = logging.getLogger(__name__)

MAX_DAYS_BEFORE = 30  # reminder rules accept 0-30


def open_occurrences(db: Session, today) -> list[OpenOccurrence]:
    """Unpaid occurrences of active bills close enough to today to owe an email."""
    occ = models.BillOccurrence
    rows = db.scalars(
        select(occ)
        .join(models.Bill)
        .where(
            models.Bill.active,
            occ.paid_at.is_(None),
            occ.due_date >= today - timedelta(days=OVERDUE_DAYS + 1),
            occ.due_date <= today + timedelta(days=MAX_DAYS_BEFORE + 1),
        )
    ).unique()
    return [
        OpenOccurrence(
            id=o.id,
            due_date=o.due_date,
            rules=tuple(Rule(r.id, r.days_before) for r in o.bill.reminder_rules),
            assignee_ids=tuple(u.id for u in o.bill.assignees),
        )
        for o in rows.all()
    ]


def run_tick(db: Session, sender: EmailSender, now: datetime | None = None) -> Counter:
    settings = get_settings()
    now = now or clock.now()
    tz = clock.local_tz()
    local_now = now.astimezone(tz)
    today = local_now.date()

    # 1. Generate occurrences through the horizon.
    bills.sync_all(db, today)

    # 2. Find what's owed.
    users = {u.id: u for u in db.scalars(select(models.User)).all()}
    recipients = {
        u.id: Recipient(u.id, u.notify_mode, u.digest_hour, u.email_enabled) for u in users.values()
    }
    owed = plan(now, tz, timedelta(hours=settings.catchup_hours), recipients, open_occurrences(db, today))
    dispatch.record_skipped(db, owed.skip, now)

    # 3. Claim: new individual emails, then crash leftovers and due retries.
    individual = [n for n in owed.send if users[n.user_id].notify_mode == "individual"]
    to_send = dispatch.claim_new(db, individual, now)
    to_send += dispatch.reclaim_stale(db, now)
    to_send += dispatch.reclaim_retries(db, now)
    for user in users.values():
        if user.notify_mode != "digest" or not user.email_enabled or local_now.hour < user.digest_hour:
            continue
        notices = [n for n in owed.send if n.user_id == user.id]
        digest_id = dispatch.claim_digest(db, user, notices, today, now)
        if digest_id:
            to_send.append(digest_id)

    # 4 + 5. Send each claimed row and record the outcome.
    outcomes = Counter(dispatch.deliver(db, sender, row_id, now, today) for row_id in to_send)

    heartbeat.beat(db)
    if to_send:
        log.info("tick: %s", dict(outcomes))
    return outcomes
