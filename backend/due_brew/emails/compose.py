"""Turn bills into emails: subjects (per claude.md) and Jinja2 text + HTML bodies.

[due-brew] Rent due in 3 days ($1,200 on Nov 1)
[due-brew] (late) Rent due tomorrow (amount not set, Nov 1)
[due-brew] Rent is overdue ($1,200, was due Nov 1)
[due-brew] 2 bills need attention today
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from due_brew.emails.sender import Email

PREFIX = "[due-brew]"

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html"]),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


@dataclass(frozen=True)
class BillLine:
    """One bill occurrence as an email shows it."""

    bill_name: str
    amount: Decimal | None
    due_date: date
    assignees: list[str]
    days_until: int
    late: bool = False


def money(amount: Decimal | None) -> str:
    if amount is None:
        return "amount not set"
    if amount == amount.to_integral_value():
        return f"${amount:,.0f}"
    return f"${amount:,.2f}"


def short_date(d: date) -> str:
    return f"{d:%b} {d.day}"


def long_date(d: date) -> str:
    return f"{d:%A, %B} {d.day}"


def when(days_until: int) -> str:
    if days_until == 0:
        return "today"
    if days_until == 1:
        return "tomorrow"
    if days_until > 1:
        return f"in {days_until} days"
    return f"{-days_until} day{'' if days_until == -1 else 's'} ago"


def _line_context(line: BillLine) -> dict:
    return {
        "name": line.bill_name,
        "amount": money(line.amount),
        "amount_missing": line.amount is None,
        "due": long_date(line.due_date),
        "when": when(line.days_until),
        "assignees": " & ".join(line.assignees),
        "late": line.late,
    }


def _render(template: str, to: str, subject: str, **context) -> Email:
    context["subject"] = subject
    return Email(
        to=to,
        subject=subject,
        text=_env.get_template(f"{template}.txt").render(**context),
        html=_env.get_template(f"{template}.html").render(**context),
    )


def reminder_email(to: str, recipient_name: str, line: BillLine, base_url: str) -> Email:
    late = "(late) " if line.late else ""
    if line.amount is None:
        detail = f"amount not set, {short_date(line.due_date)}"
    else:
        detail = f"{money(line.amount)} on {short_date(line.due_date)}"
    subject = f"{PREFIX} {late}{line.bill_name} due {when(line.days_until)} ({detail})"
    return _render(
        "reminder",
        to,
        subject,
        recipient=recipient_name,
        bill=_line_context(line),
        bills_url=f"{base_url}/bills",
    )


def overdue_email(to: str, recipient_name: str, line: BillLine, base_url: str) -> Email:
    subject = (
        f"{PREFIX} {line.bill_name} is overdue ({money(line.amount)}, was due {short_date(line.due_date)})"
    )
    return _render(
        "overdue",
        to,
        subject,
        recipient=recipient_name,
        bill=_line_context(line),
        bills_url=f"{base_url}/bills",
    )


def digest_email(
    to: str, recipient_name: str, due: list[BillLine], overdue: list[BillLine], base_url: str
) -> Email:
    count = len(due) + len(overdue)
    subject = f"{PREFIX} {count} bill{'s need' if count != 1 else ' needs'} attention today"
    return _render(
        "digest",
        to,
        subject,
        recipient=recipient_name,
        due=[_line_context(line) for line in due],
        overdue=[_line_context(line) for line in overdue],
        bills_url=f"{base_url}/bills",
    )


def check_email(to: str, recipient_name: str, base_url: str) -> Email:
    """The "send test email" button's email (not a pytest test)."""
    return _render(
        "test", to, f"{PREFIX} Test email", recipient=recipient_name, settings_url=f"{base_url}/settings"
    )
