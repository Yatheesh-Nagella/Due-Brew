"""When is a bill due? Pure date arithmetic, no database.

Rules (claude.md, Data model):
- monthly:   every month on due_day
- quarterly: every third month on due_day, counting from start_date's month
- yearly:    every year on due_month / due_day
- once:      exactly on start_date
- a due_day past the month's end (31 in February) falls on the month's last day
- nothing before start_date or after end_date
"""

import calendar
from dataclasses import dataclass
from datetime import date

RECURRENCES = ("monthly", "quarterly", "yearly", "once")
MONTH_STEP = {"monthly": 1, "quarterly": 3, "yearly": 12}


@dataclass(frozen=True)
class Schedule:
    recurrence: str
    due_day: int
    due_month: int | None
    start_date: date
    end_date: date | None = None


def clamp_day(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def _anchor_month(schedule: Schedule) -> int:
    if schedule.recurrence == "yearly":
        if schedule.due_month is None:
            raise ValueError("a yearly bill needs due_month")
        return schedule.due_month
    return schedule.start_date.month


def due_dates(schedule: Schedule, window_start: date, window_end: date) -> list[date]:
    """Every due date of `schedule` that falls within [window_start, window_end]."""
    lo = max(window_start, schedule.start_date)
    hi = min(window_end, schedule.end_date) if schedule.end_date else window_end
    if lo > hi:
        return []

    if schedule.recurrence == "once":
        return [schedule.start_date] if lo <= schedule.start_date <= hi else []
    if schedule.recurrence not in MONTH_STEP:
        raise ValueError(f"unknown recurrence {schedule.recurrence!r}")

    step = MONTH_STEP[schedule.recurrence]
    anchor = _anchor_month(schedule)
    dates = []
    # Walk month by month (as a running month index) from lo's month to hi's.
    for index in range(lo.year * 12 + lo.month - 1, hi.year * 12 + hi.month):
        year, month = divmod(index, 12)
        month += 1
        if (month - anchor) % step:
            continue
        due = clamp_day(year, month, schedule.due_day)
        if lo <= due <= hi:
            dates.append(due)
    return dates
