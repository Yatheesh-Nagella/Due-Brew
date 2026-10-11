from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from due_brew import models
from due_brew.api.main import app
from due_brew.identity import get_current_user

TODAY = "2026-10-10T12:00:00"  # a Saturday; OCCURRENCE_HORIZON_DAYS defaults to 60
MISSING = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def client(env, alice):
    """Alice's client with the clock pinned to TODAY. Built directly rather than
    via as_user, which itself depends on `client`."""
    env(NOW_OVERRIDE=TODAY)
    app.dependency_overrides[get_current_user] = lambda: alice
    return TestClient(app)


@pytest.fixture
def make_bill(client, alice):
    def _make(**overrides):
        body = {
            "name": "Rent",
            "amount": 1200,
            "recurrence": "monthly",
            "due_day": 1,
            "assignee_ids": [str(alice.id)],
            **overrides,
        }
        res = client.post("/api/bills", json=body)
        assert res.status_code == 201, res.text
        return res.json()

    return _make


def due_dates(db, bill_id):
    rows = db.scalars(
        select(models.BillOccurrence.due_date)
        .where(models.BillOccurrence.bill_id == bill_id)
        .order_by(models.BillOccurrence.due_date)
    )
    return [d.isoformat() for d in rows.all()]


def upcoming(client, days=30):
    return [
        (o["bill_name"], o["due_date"], o["state"])
        for o in client.get(f"/api/bills/upcoming?days={days}").json()
    ]


# --- create ---


def test_create_monthly_bill(make_bill, alice, db):
    bill = make_bill()

    assert bill["start_date"] == "2026-10-10"  # defaults to today
    assert bill["reminder_days"] == [3, 0]  # spec defaults
    assert [a["display_name"] for a in bill["assignees"]] == ["Alice"]
    assert bill["amount"] == 1200
    assert bill["next_occurrence"]["due_date"] == "2026-11-01"
    assert bill["next_occurrence"]["state"] == "upcoming"
    assert bill["paid_count"] == 0
    # Generated through the 60-day horizon (Dec 9).
    assert due_dates(db, bill["id"]) == ["2026-11-01", "2026-12-01"]


def test_both_housemates_and_custom_reminders(make_bill, alice, bob):
    bill = make_bill(assignee_ids=[str(alice.id), str(bob.id)], reminder_days=[0, 7, 7, 1])

    assert [a["display_name"] for a in bill["assignees"]] == ["Alice", "Bob"]
    assert bill["reminder_days"] == [7, 1, 0]


def test_no_reminders_is_allowed(make_bill):
    assert make_bill(reminder_days=[])["reminder_days"] == []


def test_start_date_in_the_past_backfills_one_week(make_bill, db):
    # Due on the 5th, saved on the 10th: Oct 5 shows as overdue, Sep 5 doesn't appear.
    bill = make_bill(due_day=5, start_date="2026-09-01")

    assert due_dates(db, bill["id"]) == ["2026-10-05", "2026-11-05", "2026-12-05"]
    assert bill["next_occurrence"]["state"] == "overdue"
    assert bill["next_occurrence"]["days_until"] == -5


def test_one_off_bill_is_due_on_its_start_date(make_bill, db):
    bill = make_bill(name="Plumber", recurrence="once", start_date="2026-10-20", due_day=3)

    assert bill["due_day"] == 20
    assert due_dates(db, bill["id"]) == ["2026-10-20"]


def test_quarterly_and_yearly(make_bill, db):
    water = make_bill(name="Water", recurrence="quarterly", due_day=15, start_date="2026-08-01")
    insurance = make_bill(name="Insurance", recurrence="yearly", due_day=30, due_month=11)

    assert due_dates(db, water["id"]) == ["2026-11-15"]
    assert due_dates(db, insurance["id"]) == ["2026-11-30"]


def test_month_end_due_day_through_the_api(make_bill, db, env):
    env(NOW_OVERRIDE="2027-01-30T12:00:00")  # horizon reaches Mar 31
    bill = make_bill(due_day=31, start_date="2027-01-01")

    assert due_dates(db, bill["id"]) == ["2027-01-31", "2027-02-28", "2027-03-31"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"recurrence": "yearly", "due_month": None},
        {"due_day": None},
        {"due_day": 32},
        {"due_month": 13, "recurrence": "yearly"},
        {"assignee_ids": []},
        {"assignee_ids": [MISSING]},
        {"reminder_days": [31]},
        {"reminder_days": [-1]},
        {"amount": -5},
        {"start_date": "2026-10-10", "end_date": "2026-10-09"},
        {"name": " "},
        {"recurrence": "weekly"},
    ],
)
def test_invalid_bills_rejected(client, alice, overrides):
    body = {
        "name": "Rent",
        "recurrence": "monthly",
        "due_day": 1,
        "assignee_ids": [str(alice.id)],
        **overrides,
    }

    assert client.post("/api/bills", json=body).status_code == 422


# --- edit ---


def test_changing_due_day_moves_unpaid_but_keeps_paid(client, make_bill, db):
    bill = make_bill(due_day=5, start_date="2026-09-01")
    oct5 = bill["next_occurrence"]["id"]
    client.post(f"/api/occurrences/{oct5}/paid")

    res = client.patch(f"/api/bills/{bill['id']}", json={"due_day": 20})

    assert res.status_code == 200
    assert due_dates(db, bill["id"]) == ["2026-10-05", "2026-10-20", "2026-11-20"]
    assert res.json()["next_occurrence"]["due_date"] == "2026-10-20"


def test_end_date_cut_off(client, make_bill, db):
    bill = make_bill()

    client.patch(f"/api/bills/{bill['id']}", json={"end_date": "2026-11-15"})

    assert due_dates(db, bill["id"]) == ["2026-11-01"]


def test_switching_to_yearly_needs_a_month(client, make_bill):
    bill = make_bill()

    assert client.patch(f"/api/bills/{bill['id']}", json={"recurrence": "yearly"}).status_code == 422
    ok = client.patch(f"/api/bills/{bill['id']}", json={"recurrence": "yearly", "due_month": 12})
    assert ok.json()["next_occurrence"]["due_date"] == "2026-12-01"


def test_edit_assignees_and_reminders(client, make_bill, bob):
    bill = make_bill()

    res = client.patch(
        f"/api/bills/{bill['id']}", json={"assignee_ids": [str(bob.id)], "reminder_days": [0, 5]}
    )

    assert [a["display_name"] for a in res.json()["assignees"]] == ["Bob"]
    assert res.json()["reminder_days"] == [5, 0]
    # Replacing with an overlapping set must not trip the unique constraint.
    again = client.patch(f"/api/bills/{bill['id']}", json={"reminder_days": [5, 3, 0]})
    assert again.json()["reminder_days"] == [5, 3, 0]


def test_patch_rejects_clearing_required_fields(client, make_bill):
    bill = make_bill()

    for field in ("name", "recurrence", "active"):
        assert client.patch(f"/api/bills/{bill['id']}", json={field: None}).status_code == 422


def test_deactivate_hides_bill_and_reactivate_restores(client, make_bill, db):
    bill = make_bill()

    off = client.patch(f"/api/bills/{bill['id']}", json={"active": False}).json()
    assert off["next_occurrence"] is None
    assert due_dates(db, bill["id"]) == []
    assert upcoming(client, days=60) == []

    on = client.patch(f"/api/bills/{bill['id']}", json={"active": True}).json()
    assert on["next_occurrence"]["due_date"] == "2026-11-01"


# --- delete ---


def test_delete_without_payments(client, make_bill, db):
    bill = make_bill()

    assert client.delete(f"/api/bills/{bill['id']}").status_code == 204
    assert db.scalar(select(func.count()).select_from(models.BillOccurrence)) == 0


def test_delete_with_paid_history_needs_confirmation(client, make_bill):
    bill = make_bill(due_day=5, start_date="2026-09-01")
    client.post(f"/api/occurrences/{bill['next_occurrence']['id']}/paid")

    refused = client.delete(f"/api/bills/{bill['id']}")
    assert refused.status_code == 409
    assert "Deactivate" in refused.json()["detail"]

    assert client.delete(f"/api/bills/{bill['id']}?confirm=true").status_code == 204
    assert client.get(f"/api/bills/{bill['id']}").status_code == 404


# --- occurrences ---


def test_mark_paid_and_undo(as_user, make_bill, alice, bob):
    bill = make_bill()
    occ_id = bill["next_occurrence"]["id"]

    paid = as_user(bob).post(f"/api/occurrences/{occ_id}/paid").json()
    assert paid["state"] == "paid"
    assert paid["paid_by_user"]["display_name"] == "Bob"
    assert paid["paid_at"] is not None

    # Paying again keeps the first record.
    again = as_user(alice).post(f"/api/occurrences/{occ_id}/paid").json()
    assert again["paid_by_user"]["display_name"] == "Bob"
    assert again["paid_at"] == paid["paid_at"]

    undone = as_user(alice).delete(f"/api/occurrences/{occ_id}/paid").json()
    assert (undone["state"], undone["paid_at"], undone["paid_by_user"]) == ("upcoming", None, None)


def test_paid_at_is_utc_now(client, make_bill):
    bill = make_bill()

    paid = client.post(f"/api/occurrences/{bill['next_occurrence']['id']}/paid").json()

    # NOW_OVERRIDE is 12:00 in America/Chicago (CDT, UTC-5).
    assert paid["paid_at"].startswith("2026-10-10T17:00:00")


def test_next_occurrence_skips_paid(client, make_bill):
    bill = make_bill()
    client.post(f"/api/occurrences/{bill['next_occurrence']['id']}/paid")

    refreshed = client.get(f"/api/bills/{bill['id']}").json()
    assert refreshed["next_occurrence"]["due_date"] == "2026-12-01"
    assert refreshed["paid_count"] == 1


def test_variable_bill_amount_on_occurrence(client, make_bill):
    bill = make_bill(name="Electric", amount=None)
    occ = bill["next_occurrence"]
    assert (occ["amount"], occ["variable"]) == (None, True)

    set_amount = client.patch(f"/api/occurrences/{occ['id']}", json={"amount": 87.45}).json()
    assert set_amount["amount"] == 87.45

    cleared = client.patch(f"/api/occurrences/{occ['id']}", json={"amount": None}).json()
    assert cleared["amount"] is None


def test_override_survives_bill_amount_change(client, make_bill):
    bill = make_bill()
    nov, dec = client.get("/api/bills/upcoming?days=60").json()
    client.patch(f"/api/occurrences/{nov['id']}", json={"amount": 1150})

    client.patch(f"/api/bills/{bill['id']}", json={"amount": 1250})

    amounts = [o["amount"] for o in client.get("/api/bills/upcoming?days=60").json()]
    assert amounts == [1150, 1250]
    assert dec["amount"] == 1200  # what it was before the edit


def test_negative_occurrence_amount_rejected(client, make_bill):
    occ = make_bill()["next_occurrence"]

    assert client.patch(f"/api/occurrences/{occ['id']}", json={"amount": -1}).status_code == 422


def test_missing_occurrence_404(client):
    assert client.post(f"/api/occurrences/{MISSING}/paid").status_code == 404
    assert client.delete(f"/api/occurrences/{MISSING}/paid").status_code == 404
    assert client.patch(f"/api/occurrences/{MISSING}", json={"amount": 1}).status_code == 404


# --- upcoming ---


def test_upcoming_window_overdue_and_paid(client, make_bill):
    make_bill(name="Rent", due_day=1)  # Nov 1: 22 days out
    internet = make_bill(name="Internet", due_day=8, start_date="2026-09-01")  # Oct 8: overdue
    make_bill(name="Gym", due_day=10)  # today
    phone = make_bill(name="Phone", due_day=12)  # Oct 12, will be paid
    client.post(f"/api/occurrences/{phone['next_occurrence']['id']}/paid")

    assert upcoming(client, days=7) == [
        ("Internet", "2026-10-08", "overdue"),
        ("Gym", "2026-10-10", "due_today"),
        ("Phone", "2026-10-12", "paid"),
    ]
    assert ("Rent", "2026-11-01", "upcoming") in upcoming(client, days=30)

    # A paid overdue occurrence drops off.
    client.post(f"/api/occurrences/{internet['next_occurrence']['id']}/paid")
    assert ("Internet", "2026-10-08", "overdue") not in upcoming(client, days=7)


def test_overdue_stays_until_paid(client, make_bill, env):
    make_bill(name="Internet", due_day=8, start_date="2026-09-01")

    env(NOW_OVERRIDE="2026-11-01T12:00:00")  # weeks later, still unpaid

    assert ("Internet", "2026-10-08", "overdue") in upcoming(client)


def test_horizon_rolls_forward_as_days_pass(client, make_bill, db, env):
    bill = make_bill()
    assert due_dates(db, bill["id"]) == ["2026-11-01", "2026-12-01"]

    env(NOW_OVERRIDE="2026-11-15T12:00:00")
    client.get("/api/bills")

    assert due_dates(db, bill["id"])[-1] == "2027-01-01"


def test_syncing_twice_changes_nothing(client, make_bill, db):
    bill = make_bill()
    before = due_dates(db, bill["id"])

    client.get("/api/bills")
    client.get("/api/bills/upcoming")

    assert due_dates(db, bill["id"]) == before


def test_list_bills_active_first(client, make_bill):
    make_bill(name="b-old", active=False)
    make_bill(name="Zoo")
    make_bill(name="apple")

    assert [b["name"] for b in client.get("/api/bills").json()] == ["apple", "Zoo", "b-old"]


def test_due_dates_are_plain_dates_in_local_tz(client, make_bill, env):
    # 23:30 on Oct 31 in Chicago is already Nov 1 in UTC; the bill is not due yet.
    env(NOW_OVERRIDE="2026-10-31T23:30:00")
    bill = make_bill(start_date="2026-10-01")

    assert bill["next_occurrence"]["due_date"] == date(2026, 11, 1).isoformat()
    assert bill["next_occurrence"]["days_until"] == 1
