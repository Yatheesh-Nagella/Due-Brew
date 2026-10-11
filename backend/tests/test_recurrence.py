from datetime import date

import pytest

from due_brew.recurrence import Schedule, due_dates

D = date
JAN_1 = D(2026, 1, 1)


def monthly(day, start=JAN_1, end=None):
    return Schedule("monthly", day, None, start, end)


def test_monthly():
    assert due_dates(monthly(1), D(2026, 1, 1), D(2026, 4, 30)) == [
        D(2026, 1, 1),
        D(2026, 2, 1),
        D(2026, 3, 1),
        D(2026, 4, 1),
    ]


@pytest.mark.parametrize(
    ("day", "expected_feb"),
    [(28, D(2026, 2, 28)), (29, D(2026, 2, 28)), (30, D(2026, 2, 28)), (31, D(2026, 2, 28))],
)
def test_due_day_past_month_end_falls_on_last_day(day, expected_feb):
    dates = due_dates(monthly(day), D(2026, 1, 1), D(2026, 4, 30))

    assert dates == [D(2026, 1, day), expected_feb, D(2026, 3, day), D(2026, 4, min(day, 30))]


def test_31st_in_every_short_month():
    dates = due_dates(monthly(31), D(2026, 1, 1), D(2026, 12, 31))

    assert [d.day for d in dates] == [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def test_leap_year_february():
    assert due_dates(monthly(30), D(2028, 2, 1), D(2028, 2, 29)) == [D(2028, 2, 29)]
    assert due_dates(monthly(29), D(2027, 2, 1), D(2027, 2, 28)) == [D(2027, 2, 28)]


def test_yearly_feb_29_only_on_leap_years():
    schedule = Schedule("yearly", 29, 2, D(2027, 1, 1))

    assert due_dates(schedule, D(2027, 1, 1), D(2029, 12, 31)) == [
        D(2027, 2, 28),
        D(2028, 2, 29),
        D(2029, 2, 28),
    ]


def test_yearly():
    schedule = Schedule("yearly", 15, 4, D(2026, 1, 1))

    assert due_dates(schedule, D(2026, 1, 1), D(2028, 12, 31)) == [
        D(2026, 4, 15),
        D(2027, 4, 15),
        D(2028, 4, 15),
    ]


def test_yearly_requires_due_month():
    with pytest.raises(ValueError):
        due_dates(Schedule("yearly", 1, None, D(2026, 1, 1)), D(2026, 1, 1), D(2026, 12, 31))


def test_quarterly_counts_from_start_month():
    schedule = Schedule("quarterly", 10, None, D(2026, 2, 1))

    assert due_dates(schedule, D(2026, 1, 1), D(2027, 3, 31)) == [
        D(2026, 2, 10),
        D(2026, 5, 10),
        D(2026, 8, 10),
        D(2026, 11, 10),
        D(2027, 2, 10),
    ]


def test_quarterly_month_end_clamp():
    schedule = Schedule("quarterly", 31, None, D(2026, 2, 1))

    assert due_dates(schedule, D(2026, 1, 1), D(2026, 12, 31)) == [
        D(2026, 2, 28),
        D(2026, 5, 31),
        D(2026, 8, 31),
        D(2026, 11, 30),
    ]


def test_once():
    schedule = Schedule("once", 20, None, D(2026, 10, 20))

    assert due_dates(schedule, D(2026, 10, 1), D(2026, 12, 31)) == [D(2026, 10, 20)]
    assert due_dates(schedule, D(2026, 10, 21), D(2026, 12, 31)) == []


def test_nothing_before_start_date():
    # Starts mid-month after the due day: the first one is next month.
    assert due_dates(monthly(1, start=D(2026, 10, 15)), D(2026, 10, 1), D(2026, 12, 31)) == [
        D(2026, 11, 1),
        D(2026, 12, 1),
    ]


def test_start_date_on_due_day_is_included():
    schedule = monthly(15, start=D(2026, 10, 15))

    assert due_dates(schedule, D(2026, 10, 1), D(2026, 10, 31)) == [D(2026, 10, 15)]


def test_end_date_cut_off_is_inclusive():
    schedule = monthly(1, end=D(2026, 3, 1))

    assert due_dates(schedule, D(2026, 1, 1), D(2026, 12, 31)) == [
        D(2026, 1, 1),
        D(2026, 2, 1),
        D(2026, 3, 1),
    ]


def test_end_date_before_window_gives_nothing():
    assert due_dates(monthly(1, end=D(2025, 12, 31)), D(2026, 1, 1), D(2026, 12, 31)) == []


def test_window_crossing_year_boundary():
    assert due_dates(monthly(5), D(2026, 11, 20), D(2027, 2, 1)) == [
        D(2026, 12, 5),
        D(2027, 1, 5),
    ]


def test_window_is_inclusive_both_ends():
    assert due_dates(monthly(10), D(2026, 3, 10), D(2026, 4, 10)) == [D(2026, 3, 10), D(2026, 4, 10)]
