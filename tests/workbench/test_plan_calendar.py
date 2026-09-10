"""Real calendar intersections, bounded reads and explicit missing-data policies."""

import json
import sqlite3

import pytest

from core.infrastructure.errors import AppError
from core.models.workbench_command import input_fingerprint
from core.services.scheduler.calendar_engine import CalendarEngine
from core.services.workbench.plan_calendar import project_plan_calendar
from core.services.workbench.plan_calendar_intervals import instant
from tests.workbench.plan_calendar_support import codes, measured, plan_calendar_case, resource


def test_default_is_domain_policy_not_sample_capacity(calendar_case):
    calendar, _, facts, _ = calendar_case.project()
    assert calendar["state"] == "available"
    assert calendar["global"]["available_hours"] == 8
    assert calendar["global"]["windows"][0]["provenance"] == "domain_default"
    assert resource(calendar)["basis"] == "global_calendar_machine_availability"
    assert resource(calendar)["available_hours"] == 8
    assert facts["sources"]["global"] == []


def test_night_tail_intersection_and_next_day_shift_not_noon_sample(calendar_case):
    calendar_case.calendar("2026-09-08", "20:00", "06:00")
    calendar_case.calendar("2026-09-09", "08:00", "16:00")
    calendar, _, _, _ = calendar_case.project()
    assert resource(calendar)["available_hours"] == 14
    windows = resource(calendar)["windows"]
    assert [(row["start"], row["end"]) for row in windows] == [
        ("2026-09-09T00:00:00", "2026-09-09T06:00:00"),
        ("2026-09-09T08:00:00", "2026-09-09T16:00:00")]
    calendar, _, _, _ = calendar_case.project("2026-09-09T01:00:00", "2026-09-09T03:00:00")
    assert calendar["global"]["available_hours"] == 2


def test_machine_global_calendar_does_not_infer_assigned_person_capacity(calendar_case):
    calendar_case.shift([("22:00", "06:00", 0)])
    calendar_case.execute("UPDATE Schedule SET start_time='2026-09-09 22:00:00',end_time='2026-09-10 06:00:00'")
    calendar, occupancy, _, _ = calendar_case.project("2026-09-09T00:00:00", "2026-09-11T00:00:00")
    assert resource(calendar)["available_hours"] == 16
    assert resource(calendar)["windows"][0]["start"] == "2026-09-09T08:00:00"
    assert resource(calendar, "operator")["windows"][0]["end"] == "2026-09-09T06:00:00"
    assert resource(occupancy)["outside_available_hours"] == 8
    assert resource(occupancy, "operator")["outside_available_hours"] == 0
    assert "assignment_outside_calendar" not in codes(occupancy["issues"])


def test_personal_override_wins_over_inactive_rotation_and_global_holiday(calendar_case):
    calendar_case.calendar(hours=0, normal="no", urgent="no")
    calendar_case.shift([("22:00", "06:00", 0)], status="inactive")
    for day in ("2026-09-08", "2026-09-09"):
        calendar_case.calendar(day, "09:00", "12:00", operator="PRIVATE-O1", efficiency=0.8)
    calendar, _, _, _ = calendar_case.project()
    assert resource(calendar)["available_hours"] == 0
    person = resource(calendar, "operator")
    assert person["available_hours"] == 3 and person["effective_hours"] == 2.4
    assert person["windows"][0]["provenance"] == "personal_calendar"


def test_current_personal_window_owns_scope_even_if_previous_profile_is_broken(calendar_case):
    calendar_case.shift([("22:00", "06:00", 0)], status="inactive")
    calendar_case.calendar(start="09:00", end="12:00", operator="PRIVATE-O1")
    calendar, _, _, _ = calendar_case.project("2026-09-09T09:00:00", "2026-09-09T12:00:00")
    assert resource(calendar, "operator")["available_hours"] == 3
    calendar, _, _, _ = calendar_case.project("2026-09-09T08:00:00", "2026-09-09T12:00:00")
    assert resource(calendar, "operator")["available_hours"] is None


def test_rotating_rest_keeps_previous_night_tail(calendar_case):
    calendar_case.shift([("22:00", "06:00", 0), ("00:00", "00:00", 1)])
    calendar_case.execute("UPDATE Schedule SET start_time='2026-09-09 22:00:00',end_time='2026-09-10 06:00:00'")
    calendar, _, _, _ = calendar_case.project("2026-09-10T00:00:00", "2026-09-11T00:00:00")
    assert resource(calendar, "operator")["available_hours"] == 6


def test_priority_and_efficiency_measures_are_separate(calendar_case):
    calendar_case.calendar(hours=8, efficiency=0.5, normal="no", urgent="yes")
    calendar, occupancy, _, _ = calendar_case.project()
    machine = resource(calendar)
    assert machine["available_hours"] == 8 and machine["effective_hours"] == 4
    assert machine["normal_available_hours"] == 0 and machine["normal_effective_hours"] == 0
    assert machine["urgent_available_hours"] == 8 and machine["urgent_effective_hours"] == 4
    assert machine["windows"][0]["allow_normal"] is False
    assert "assignment_outside_calendar" in codes(occupancy["issues"])
    calendar_case.execute("UPDATE Batches SET priority='critical'")
    assert "assignment_outside_calendar" not in codes(calendar_case.project()[1]["issues"])


def test_overlapping_shift_policies_use_engine_today_precedence(calendar_case):
    calendar_case.calendar("2026-09-08", "20:00", "10:00", efficiency=0.5)
    calendar_case.calendar("2026-09-09", "08:00", "16:00", efficiency=1, normal="no")
    calendar, _, _, _ = calendar_case.project()
    machine = resource(calendar)
    assert machine["available_hours"] == 16 and machine["effective_hours"] == 12
    assert machine["normal_available_hours"] == 8
    for at in ("2026-09-09T07:00:00", "2026-09-09T09:00:00"):
        policy = CalendarEngine(calendar_case.conn).policy_for_datetime(instant(at))
        row = next(row for row in machine["windows"] if row["start"] <= at < row["end"])
        assert row["policy_date"] == policy.date_str and row["efficiency"] == policy.efficiency


def test_downtime_is_union_clipped_to_real_calendar_not_all_plant(calendar_case):
    for start, end, status in (("07:00", "10:00", "active"), ("09:00", "11:00", "active"),
                               ("15:00", "18:00", "active"), ("11:00", "15:00", "cancelled")):
        calendar_case.downtime("2026-09-09 " + start, "2026-09-09 " + end, status=status)
    calendar_case.execute("INSERT INTO Machines(machine_id,name) VALUES ('OTHER-M','Elsewhere')")
    calendar_case.downtime("broken", "broken", machine="OTHER-M")
    calendar, occupancy, facts, _ = calendar_case.project()
    assert resource(calendar)["available_hours"] == 4
    assert resource(calendar)["downtime_scope_hours"] == 7
    assert resource(calendar)["downtime_available_hours"] == 4
    assert resource(calendar, "operator")["available_hours"] == 8
    assert resource(occupancy)["outside_available_hours"] == 4
    assert len(facts["sources"]["downtimes"]) == 3


@pytest.mark.parametrize("mutation,code", [
    ("UPDATE Machines SET status=NULL", "resource_status_unknown"),
    ("UPDATE WorkCalendar SET shift_hours=NULL", "calendar_invalid"),
    ("UPDATE WorkCalendar SET efficiency=NULL", "calendar_invalid"),
    ("UPDATE WorkCalendar SET shift_start='29:00'", "calendar_invalid"),
    ("UPDATE WorkCalendar SET allow_normal=NULL", "calendar_invalid"),
    ("UPDATE WorkCalendar SET day_type='unknown'", "calendar_invalid"),
    ("UPDATE WorkCalendar SET shift_hours=25", "calendar_window_limit"),
])
def test_bad_or_nullable_capacity_is_never_known_zero(calendar_case, mutation, code):
    calendar_case.calendar()
    calendar_case.execute(mutation)
    calendar, occupancy, facts, _ = calendar_case.project()
    assert resource(calendar)["state"] == "unavailable"
    assert resource(calendar)["available_hours"] is None
    assert code in codes(resource(calendar)["issues"])
    assert resource(occupancy)["arranged_hours"] == 8
    assert resource(occupancy)["available_hours"] is None
    assert input_fingerprint(facts)


def test_nonfinite_calendar_is_retained_as_explicit_invalid_snapshot(calendar_case):
    calendar_case.calendar(efficiency=float("inf"))
    calendar, _, facts, _ = calendar_case.project()
    assert resource(calendar)["state"] == "unavailable"
    assert facts["sources"]["global"][0]["efficiency"] == {"invalid_number": "inf"}
    assert input_fingerprint(facts)


def test_derived_capacity_overflow_is_unavailable_and_snapshot_remains_serializable(calendar_case):
    calendar_case.calendar(efficiency=1e308)
    calendar, _, facts, _ = calendar_case.project()
    assert resource(calendar)["state"] == "unavailable"
    assert input_fingerprint(facts)


def test_calendar_enum_normalization_matches_domain(calendar_case):
    calendar_case.calendar(normal=" YES ", urgent=" NO ")
    calendar_case.execute("UPDATE WorkCalendar SET day_type=' WORKDAY '")
    calendar, _, _, _ = calendar_case.project()
    assert resource(calendar)["normal_available_hours"] == 8
    assert resource(calendar)["urgent_available_hours"] == 0


@pytest.mark.parametrize("status", ["inactive", "maintain"])
def test_known_disabled_resource_has_real_zero_capacity(calendar_case, status):
    calendar_case.execute("UPDATE Machines SET status=?", (status,))
    calendar, occupancy, _, _ = calendar_case.project()
    assert resource(calendar)["state"] == "available" and resource(calendar)["available_hours"] == 0
    assert resource(occupancy)["capacity_insufficient"] is True
    assert resource(occupancy)["utilization"] is None


@pytest.mark.parametrize("start,end,status", [("bad", "2026-09-09 12:00:00", "active"),
                                              ("2026-09-09 12:00:00", "2026-09-09 10:00:00", "active"),
                                              ("2026-09-09 10:00:00", "2026-09-09 12:00:00", None)])
def test_invalid_downtime_is_unavailable_not_ignored(calendar_case, start, end, status):
    calendar_case.downtime(start, end, status=status)
    calendar, _, _, _ = calendar_case.project()
    assert "downtime_invalid" in codes(resource(calendar)["issues"])
    assert resource(calendar)["available_hours"] is None


@pytest.mark.parametrize("mutation", ["DELETE FROM WorkbenchShiftPatternDays", "UPDATE WorkbenchShiftProfiles SET anchor_date='bad'",
                                     "UPDATE WorkbenchShiftProfiles SET status='inactive'"])
def test_invalid_person_profile_retains_machine_facts(calendar_case, mutation):
    calendar_case.shift([("22:00", "06:00", 0)])
    calendar_case.execute(mutation)
    calendar, _, _, _ = calendar_case.project()
    assert calendar["state"] == "partial"
    assert resource(calendar)["available_hours"] == 8
    assert resource(calendar, "operator")["available_hours"] is None


@pytest.mark.parametrize("table", ["WorkCalendar", "WorkbenchOperatorProfiles", "MachineDowntimes", "OperatorSkill"])
def test_sql_or_schema_failure_is_not_unavailable_success(calendar_case, table):
    calendar_case.execute("DROP TABLE " + table)
    with pytest.raises(AppError):
        calendar_case.project()


def test_huge_sparse_range_explicitly_bounded_before_calendar_sql(calendar_case):
    calendar_case.task("9998-01-01 08:00:00", "9998-01-01 09:00:00")
    with calendar_case.selected(None, None) as args:
        with measured(calendar_case.conn) as stats:
            calendar, facts = project_plan_calendar(calendar_case.conn, **args)
        assert stats["sql"] == []
        assert "calendar_range_limit" in codes(calendar["issues"])
        assert calendar["resources"] is None and facts["sources"] is None
    calendar, _, _, _ = calendar_case.project("9998-01-01T08:00:00", "9998-01-01T09:00:00")
    assert calendar["state"] == "available"


def test_snapshot_contains_permission_and_raw_source_changes(calendar_case):
    first = calendar_case.project()[2]
    calendar_case.calendar(normal="no")
    second = calendar_case.project()[2]
    assert input_fingerprint(first) != input_fingerprint(second)
    assert "PRIVATE-M1" in json.dumps(second)


def test_no_internal_ids_or_private_labels_and_database_unchanged(calendar_case):
    before = list(calendar_case.conn.iterdump()), calendar_case.conn.total_changes
    calendar_case.conn.execute("PRAGMA query_only=ON")
    calendar_case.project()
    after = list(calendar_case.conn.iterdump()), calendar_case.conn.total_changes
    assert after == before
    assert not calendar_case.conn.in_transaction


def test_same_read_transaction_keeps_calendar_resource_and_downtime_snapshot(calendar_case, tmp_path):
    path = tmp_path / "calendar-snapshot.db"
    writer = sqlite3.connect(str(path))
    reader = sqlite3.connect(str(path))
    reader.row_factory = sqlite3.Row
    original = calendar_case.conn
    try:
        original.backup(writer)
        writer.execute("PRAGMA journal_mode=WAL")
        calendar_case.conn = reader
        with calendar_case.selected() as args:
            writer.execute("INSERT INTO WorkCalendar(date,shift_hours) VALUES ('2026-09-09',0)")
            writer.execute("INSERT INTO MachineDowntimes(machine_id,start_time,end_time) "
                           "VALUES ('PRIVATE-M1','2026-09-09 08:00:00','2026-09-09 16:00:00')")
            writer.commit()
            dto, facts = project_plan_calendar(reader, **args)
            assert resource(dto)["available_hours"] == 8
            assert facts["sources"]["downtimes"] == facts["sources"]["global"] == []
        dto, _, facts, _ = calendar_case.project()
        assert resource(dto)["available_hours"] == 0
        assert len(facts["sources"]["global"]) == len(facts["sources"]["downtimes"]) == 1
    finally:
        calendar_case.conn = original
        reader.close()
        writer.close()
