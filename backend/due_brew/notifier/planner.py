"""Which reminder emails are owed right now? Pure logic, no database.

For each unpaid occurrence of an active bill, each of its reminder rules, and
each assignee with email on:

- the send date is due_date - days_before, and the email goes out at the
  user's digest_hour (local time) on that date;
- once that moment has passed it's due, for CATCHUP_HOURS; if the moment was
  on an earlier day than today, it's marked late;
- missed by more than CATCHUP_HOURS it's skipped (logged, never sent);
- a reminder for a bill that's already overdue is skipped too: the overdue
  email covers it, instead of a confusing "due 1 day ago" reminder.

An unpaid occurrence past its due date also owes each assignee one overdue
email, due from the day after at their hour, until OVERDUE_DAYS after the
due date.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

OVERDUE_DAYS = 7


@dataclass(frozen=True)
class Recipient:
    id: uuid.UUID
    notify_mode: str  # individual | digest
    digest_hour: int
    email_enabled: bool = True


@dataclass(frozen=True)
class Rule:
    id: uuid.UUID
    days_before: int


@dataclass(frozen=True)
class OpenOccurrence:
    """An unpaid occurrence of an active bill."""

    id: uuid.UUID
    due_date: date
    rules: tuple[Rule, ...]
    assignee_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class Notice:
    kind: str  # reminder | overdue
    occurrence_id: uuid.UUID
    rule_id: uuid.UUID | None
    user_id: uuid.UUID
    send_date: date
    late: bool


@dataclass
class Plan:
    send: list[Notice] = field(default_factory=list)
    skip: list[Notice] = field(default_factory=list)


def send_moment(send_date: date, hour: int, tz: ZoneInfo) -> datetime:
    return datetime.combine(send_date, time(hour), tzinfo=tz)


def is_overdue_window(due_date: date, today: date) -> bool:
    return 0 < (today - due_date).days <= OVERDUE_DAYS


def plan(
    now: datetime,
    tz: ZoneInfo,
    catchup: timedelta,
    recipients: dict[uuid.UUID, Recipient],
    occurrences: list[OpenOccurrence],
) -> Plan:
    today = now.astimezone(tz).date()
    result = Plan()

    for occ in occurrences:
        for user_id in occ.assignee_ids:
            user = recipients.get(user_id)
            if user is None or not user.email_enabled:
                continue

            for rule in occ.rules:
                send_date = occ.due_date - timedelta(days=rule.days_before)
                moment = send_moment(send_date, user.digest_hour, tz)
                if moment > now:
                    continue  # not yet
                notice = Notice("reminder", occ.id, rule.id, user_id, send_date, late=send_date < today)
                if now - moment > catchup or occ.due_date < today:
                    result.skip.append(notice)
                else:
                    result.send.append(notice)

            if is_overdue_window(occ.due_date, today):
                send_date = occ.due_date + timedelta(days=1)
                if send_moment(send_date, user.digest_hour, tz) <= now:
                    result.send.append(
                        Notice("overdue", occ.id, None, user_id, send_date, late=send_date < today)
                    )

    return result
