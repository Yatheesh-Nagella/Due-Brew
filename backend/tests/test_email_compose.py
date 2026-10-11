from datetime import date
from decimal import Decimal

import pytest

from due_brew.emails.compose import BillLine, check_email, digest_email, money, overdue_email, reminder_email

URL = "https://raspberrypi.example.ts.net/due-brew"


def line(**overrides):
    fields = {
        "bill_name": "Rent",
        "amount": Decimal("1200"),
        "due_date": date(2026, 11, 1),
        "assignees": ["Alice", "Bob"],
        "days_until": 3,
        **overrides,
    }
    return BillLine(**fields)


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (Decimal("1200"), "$1,200"),
        (Decimal("87.5"), "$87.50"),
        (Decimal("0"), "$0"),
        (None, "amount not set"),
    ],
)
def test_money(value, text):
    assert money(value) == text


@pytest.mark.parametrize(
    ("days", "subject"),
    [
        (3, "[due-brew] Rent due in 3 days ($1,200 on Nov 1)"),
        (1, "[due-brew] Rent due tomorrow ($1,200 on Nov 1)"),
        (0, "[due-brew] Rent due today ($1,200 on Nov 1)"),
    ],
)
def test_reminder_subject_matches_spec(days, subject):
    assert reminder_email("a@example.com", "Alice", line(days_until=days), URL).subject == subject


def test_reminder_without_amount():
    email = reminder_email("a@example.com", "Alice", line(amount=None), URL)

    assert email.subject == "[due-brew] Rent due in 3 days (amount not set, Nov 1)"
    assert "amount not set" in email.text and "amount not set" in email.html


def test_late_reminder_is_marked():
    email = reminder_email("a@example.com", "Alice", line(days_until=1, late=True), URL)

    assert email.subject == "[due-brew] (late) Rent due tomorrow ($1,200 on Nov 1)"
    assert "late" in email.text


def test_reminder_body_has_everything_the_spec_asks_for():
    email = reminder_email("alice@example.com", "Alice", line(), URL)

    for body in (email.text, email.html):
        assert "Rent" in body
        assert "$1,200" in body
        assert "Sunday, November 1" in body
        assert "Alice &amp; Bob" in body or "Alice & Bob" in body
        assert f"{URL}/bills" in body
    assert email.to == "alice@example.com"


def test_html_is_escaped_text_is_not():
    email = reminder_email("a@example.com", "Alice", line(bill_name="<b>Tom & Jerry</b>"), URL)

    assert "&lt;b&gt;Tom &amp; Jerry&lt;/b&gt;" in email.html
    assert "<b>Tom & Jerry</b>" in email.text


def test_overdue_subject():
    email = overdue_email("a@example.com", "Alice", line(days_until=-2), URL)

    assert email.subject == "[due-brew] Rent is overdue ($1,200, was due Nov 1)"
    assert "2 days ago" in email.text


@pytest.mark.parametrize(
    ("due", "overdue", "subject"), [(1, 0, "1 bill needs"), (1, 1, "2 bills need"), (0, 3, "3 bills need")]
)
def test_digest_subject_counts(due, overdue, subject):
    email = digest_email("a@example.com", "Alice", [line()] * due, [line(days_until=-1)] * overdue, URL)

    assert email.subject == f"[due-brew] {subject} attention today"


def test_digest_lists_overdue_then_coming_up():
    email = digest_email(
        "a@example.com",
        "Alice",
        [line(bill_name="Internet", amount=None, days_until=0)],
        [line(bill_name="Electric", days_until=-2)],
        URL,
    )

    text = email.text
    assert text.index("OVERDUE") < text.index("Electric") < text.index("COMING UP") < text.index("Internet")
    assert "amount not set" in text
    assert "Electric" in email.html and "Internet" in email.html


def test_check_email():
    email = check_email("alice@example.com", "Alice", URL)

    assert email.subject == "[due-brew] Test email"
    assert f"{URL}/settings" in email.text
