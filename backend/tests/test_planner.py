import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from due_brew.notifier.planner import OpenOccurrence, Recipient, Rule, plan

TZ = ZoneInfo("America/Chicago")
CATCHUP = timedelta(hours=48)
ALICE = Recipient(uuid.uuid4(), "individual", digest_hour=8)
BOB = Recipient(uuid.uuid4(), "individual", digest_hour=20)
THREE = Rule(uuid.uuid4(), 3)
ZERO = Rule(uuid.uuid4(), 0)


def at(y, m, d, hour=12, minute=0):
    return datetime(y, m, d, hour, minute, tzinfo=TZ)


def occ(due=date(2026, 11, 1), rules=(THREE, ZERO), assignees=(ALICE,)):
    return OpenOccurrence(uuid.uuid4(), due, rules, tuple(a.id for a in assignees))


def run(now, *occurrences, users=(ALICE, BOB)):
    result = plan(now, TZ, CATCHUP, {u.id: u for u in users}, list(occurrences))
    send = [(n.kind, n.send_date.isoformat(), n.late) for n in result.send]
    skip = [(n.kind, n.send_date.isoformat()) for n in result.skip]
    return send, skip


def test_three_days_before_at_the_users_hour():
    rent = occ()

    assert run(at(2026, 10, 29, 7, 59), rent) == ([], [])
    assert run(at(2026, 10, 29, 8, 0), rent) == ([("reminder", "2026-10-29", False)], [])


def test_on_due_date():
    send, _ = run(at(2026, 11, 1, 9), occ(rules=(ZERO,)))

    assert send == [("reminder", "2026-11-01", False)]


def test_each_user_at_their_own_hour():
    rent = occ(rules=(ZERO,), assignees=(ALICE, BOB))

    morning = plan(at(2026, 11, 1, 9), TZ, CATCHUP, {ALICE.id: ALICE, BOB.id: BOB}, [rent])
    evening = plan(at(2026, 11, 1, 20), TZ, CATCHUP, {ALICE.id: ALICE, BOB.id: BOB}, [rent])

    assert [n.user_id for n in morning.send] == [ALICE.id]
    assert {n.user_id for n in evening.send} == {ALICE.id, BOB.id}


def test_both_rules_due_once_both_moments_passed():
    send, _ = run(at(2026, 11, 1, 9), occ())

    # The 3-day one (Oct 29) is outside the 48h catch-up by Nov 1 09:00 -> skipped.
    assert send == [("reminder", "2026-11-01", False)]


def test_catch_up_within_48_hours_is_marked_late():
    # Pi was off Oct 29-30; back on Oct 30 at noon: 28h after the 3-day reminder.
    send, skip = run(at(2026, 10, 30, 12), occ())

    assert send == [("reminder", "2026-10-29", True)]
    assert skip == []


def test_missed_by_more_than_48_hours_is_skipped():
    # Back on Oct 31 at 09:00: 49h after Oct 29 08:00.
    send, skip = run(at(2026, 10, 31, 9), occ())

    assert send == []
    assert skip == [("reminder", "2026-10-29")]


def test_exactly_48_hours_still_sends():
    send, _ = run(at(2026, 10, 31, 8), occ())

    assert send == [("reminder", "2026-10-29", True)]


def test_reminder_for_an_overdue_bill_is_skipped_not_sent_late():
    # Due-date reminder missed (Pi off on Nov 1); on Nov 2 the overdue email covers it.
    send, skip = run(at(2026, 11, 2, 9), occ(rules=(ZERO,)))

    assert send == [("overdue", "2026-11-02", False)]
    assert skip == [("reminder", "2026-11-01")]


def test_overdue_email_window():
    rent = occ(rules=())

    assert run(at(2026, 11, 1, 23), rent)[0] == []  # due today: not overdue yet
    assert run(at(2026, 11, 2, 7), rent)[0] == []  # before Alice's hour
    assert run(at(2026, 11, 2, 8), rent)[0] == [("overdue", "2026-11-02", False)]
    assert run(at(2026, 11, 8, 8), rent)[0] == [("overdue", "2026-11-02", True)]  # day 7: still (late)
    assert run(at(2026, 11, 9, 8), rent)[0] == []  # day 8: done


def test_only_assignees_with_email_enabled():
    off = Recipient(uuid.uuid4(), "individual", 8, email_enabled=False)

    send, skip = run(at(2026, 11, 1, 9), occ(rules=(ZERO,), assignees=(off,)), users=(off,))

    assert (send, skip) == ([], [])


def test_unassigned_users_get_nothing():
    rent = occ(rules=(ZERO,), assignees=(ALICE,))

    result = plan(at(2026, 11, 1, 21), TZ, CATCHUP, {ALICE.id: ALICE, BOB.id: BOB}, [rent])

    assert [n.user_id for n in result.send] == [ALICE.id]


def test_no_rules_means_no_reminders():
    assert run(at(2026, 11, 1, 9), occ(rules=())) == ([], [])


def test_local_hour_not_utc():
    # 08:00 in Chicago is 13:00 UTC; at 12:00 UTC it's still 07:00 locally.
    utc_noon = datetime(2026, 11, 1, 12, tzinfo=ZoneInfo("UTC"))

    assert run(utc_noon, occ(rules=(ZERO,)))[0] == []


def test_dst_change_day_still_fires():
    # Nov 1 2026 is the fall-back DST change in the US.
    send, _ = run(at(2026, 11, 1, 8, 30), occ(rules=(ZERO,)))

    assert send == [("reminder", "2026-11-01", False)]
