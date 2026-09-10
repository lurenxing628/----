"""Real CalendarService consumes registered shifts, not labels or personal-row rewrites."""

from datetime import datetime

import pytest

from core.errors import AppError, ValidationError
from core.services.scheduler.calendar_service import CalendarService


def _shift(conn, days, *, anchor="2026-09-09", status="active"):
    conn.execute("INSERT INTO Operators(operator_id,name,status) VALUES ('O-SHIFT','Shift','active')")
    conn.execute("INSERT INTO WorkbenchShiftProfiles(profile_id,name,anchor_date,cycle_days,status) VALUES ('SHIFT','Pattern',?,?,?)",
                 (anchor, len(days), status))
    for offset, (start, end, rest) in enumerate(days):
        conn.execute("INSERT INTO WorkbenchShiftPatternDays(profile_id,day_offset,shift_start,shift_end,is_rest) VALUES ('SHIFT',?,?,?,?)",
                     (offset, start, end, int(rest)))
    conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,shift_profile_id) VALUES ('O-SHIFT','SHIFT')")
    conn.commit()


def test_unassigned_legacy_person_uses_unchanged_calendar(schema_conn):
    schema_conn.execute("INSERT INTO Operators(operator_id,name,status) VALUES ('OLD','Legacy','inactive')")
    schema_conn.commit()
    service = CalendarService(schema_conn)
    at = datetime(2026, 9, 9, 9)
    before = list(schema_conn.iterdump())
    assert service.policy_for_datetime(at, operator_id="OLD") == service.policy_for_datetime(at)
    assert list(schema_conn.iterdump()) == before


def test_fixed_night_shift_moves_clock_preserves_capacity_and_has_cross_midnight_membership(schema_conn):
    _shift(schema_conn, [("22:00", "06:00", False)])
    service = CalendarService(schema_conn)
    before = list(schema_conn.iterdump())
    start = service.adjust_to_working_time(datetime(2026, 9, 9, 9), operator_id="O-SHIFT")
    assert start == datetime(2026, 9, 9, 22)
    finish = service.add_working_hours(start, 8, operator_id="O-SHIFT")
    assert finish == datetime(2026, 9, 10, 6)
    policy = service.policy_for_datetime(datetime(2026, 9, 10, 2), operator_id="O-SHIFT")
    assert policy.date_str == "2026-09-09" and policy.work_window() == (start, finish)
    assert list(schema_conn.iterdump()) == before


def test_rotating_rest_day_does_not_hide_previous_night_tail(schema_conn):
    _shift(schema_conn, [("22:00", "06:00", False), ("00:00", "00:00", True)])
    service = CalendarService(schema_conn)
    assert service.policy_for_datetime(datetime(2026, 9, 10, 2), operator_id="O-SHIFT").date_str == "2026-09-09"
    assert service.policy_for_datetime(datetime(2026, 9, 10, 8), operator_id="O-SHIFT").shift_hours == 0


def test_profile_cannot_reopen_global_rest_or_add_capacity_or_relax_priority(schema_conn):
    _shift(schema_conn, [("20:00", "08:00", False)])
    service = CalendarService(schema_conn)
    service.upsert("2026-09-09", day_type="workday", shift_hours=4, efficiency=0.5,
                   allow_normal="no", allow_urgent="yes", remark="explicit")
    policy = service.policy_for_datetime(datetime(2026, 9, 9, 21), operator_id="O-SHIFT")
    assert policy.shift_hours == 4 and policy.efficiency == 0.5
    assert policy.allow_normal == "no" and policy.allow_urgent == "yes"
    assert policy.work_window() == (datetime(2026, 9, 9, 20), datetime(2026, 9, 10, 0))
    weekend = service.policy_for_datetime(datetime(2026, 9, 12, 22), operator_id="O-SHIFT")
    assert weekend.shift_hours == 0 and weekend.allow_urgent == "no"


def test_explicit_personal_calendar_wins_even_over_inactive_profile(schema_conn):
    _shift(schema_conn, [("22:00", "06:00", False)], status="inactive")
    service = CalendarService(schema_conn)
    service.upsert_operator_calendar("O-SHIFT", "2026-09-09", day_type="workday", shift_start="09:00", shift_end="12:00",
                                    efficiency=0.8, allow_normal="yes", allow_urgent="no", remark="personal")
    before = list(schema_conn.iterdump())
    policy = service.policy_for_datetime(datetime(2026, 9, 9, 10), operator_id="O-SHIFT")
    assert policy.work_window() == (datetime(2026, 9, 9, 9), datetime(2026, 9, 9, 12))
    assert policy.efficiency == 0.8 and policy.allow_urgent == "no"
    assert list(schema_conn.iterdump()) == before


@pytest.mark.parametrize("mutation", (
    "UPDATE WorkbenchShiftProfiles SET status='inactive'",
    "UPDATE WorkbenchShiftProfiles SET anchor_date='not-a-date'",
    "DELETE FROM WorkbenchShiftPatternDays",
    "UPDATE WorkbenchShiftPatternDays SET shift_start='29:00'",
    "UPDATE WorkbenchShiftProfiles SET cycle_days=2",
))
def test_invalid_assigned_profile_never_falls_back_to_default(schema_conn, mutation):
    _shift(schema_conn, [("22:00", "06:00", False)])
    schema_conn.execute(mutation)
    schema_conn.commit()
    with pytest.raises(ValidationError):
        CalendarService(schema_conn).policy_for_datetime(datetime(2026, 9, 9, 23), operator_id="O-SHIFT")


def test_missing_shift_schema_is_not_treated_as_no_assignment(schema_conn):
    schema_conn.execute("DROP TABLE WorkbenchOperatorProfiles")
    schema_conn.commit()
    with pytest.raises(AppError):
        CalendarService(schema_conn).policy_for_datetime(datetime(2026, 9, 9, 10), operator_id="O-SHIFT")
