"""Calendar capacity uses production DATE conversion without losing source types."""

import importlib
import sqlite3
from contextlib import closing
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.infrastructure.database import get_connection
from core.infrastructure.errors import ValidationError
from core.models.workbench_command import input_fingerprint
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from core.models.workbench_plan_scope import PlanReadScope
from core.services.capacity.plan_calendar_engine import SnapshotCalendarEngine
from core.services.scheduler.calendar_engine import CalendarEngine
from core.services.workbench.plan_fact_serialization import plain_plan_facts
from core.services.workbench.plan_queries import WorkbenchPlanQueryService
from tests.workbench.plan_calendar_support import CalendarCase, codes, resource
from tests.workbench.plan_read_support import BASE, assert_error, assert_no_private_facts


@pytest.fixture
def runtime_calendar(app_client, db_env):
    assert app_client.application.config["DATABASE_PATH"] == db_env
    with closing(get_connection(db_env)) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        case = CalendarCase(conn)
        ref = WorkbenchPlanQueryService(conn).references.get_plan_ref(WorkbenchPlanLocator(1, "adopted"))
        yield SimpleNamespace(case=case, client=app_client, path=db_env, ref=ref)


def _workspace(api, start, end, **extra):
    response = api.client.get(BASE + "/" + api.ref + "/workspace",
                              query_string=dict(range_start=start, range_end=end, **extra))
    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json()
    assert body["ok"] and body["meta"]["source"] == "production"
    assert_no_private_facts(body)
    return body


def _project(api, start, end):
    body = _workspace(api, start, end)
    calendar, occupancy, facts, _ = api.case.project(start, end)
    assert body["data"]["projections"]["calendar"] == calendar
    assert body["data"]["projections"]["occupancy"] == occupancy
    for kind in ("machine", "operator"):
        assert resource(calendar, kind)["available_hours"] == resource(occupancy, kind)["available_hours"]
    for name in ("global", "personal"):
        assert all(type(row["date"]) is date for row in facts["sources"][name])
    return calendar, occupancy, facts


def _assert_domain_windows(case, calendar, kind):
    engine = CalendarEngine(case.conn)
    for row in resource(calendar, kind)["windows"]:
        policy = engine.policy_for_datetime(datetime.fromisoformat(row["start"]),
                                             operator_id="PRIVATE-O1" if kind == "operator" else None)
        assert policy.date_str == row["policy_date"]
        assert policy.efficiency == row["efficiency"]
        assert policy.is_priority_allowed("normal") == row["allow_normal"]
        assert policy.is_priority_allowed("urgent") == row["allow_urgent"]
        low, high = policy.work_window()
        assert low <= datetime.fromisoformat(row["start"]) < datetime.fromisoformat(row["end"]) <= high


def test_real_full_app_date_converter_keeps_explicit_7_5_hour_night(runtime_calendar):
    api = runtime_calendar
    api.case.calendar("2026-09-12", "22:30", "06:00", hours=7.5)
    api.case.execute("UPDATE Schedule SET start_time='2026-09-12 22:30:00',end_time='2026-09-13 06:00:00'")
    row = api.case.conn.execute("SELECT date FROM WorkCalendar").fetchone()
    assert type(row["date"]) is date
    start, end = "2026-09-12T22:30:00", "2026-09-13T06:00:00"
    body = _workspace(api, start, end)
    calendar = body["data"]["projections"]["calendar"]
    occupancy = body["data"]["projections"]["occupancy"]
    assert calendar["global"]["available_hours"] == 7.5
    assert calendar["global"]["windows"][0]["provenance"] == "work_calendar"
    for kind in ("machine", "operator"):
        assert resource(calendar, kind)["available_hours"] == 7.5
        assert resource(occupancy, kind)["available_hours"] == 7.5
        assert resource(occupancy, kind)["outside_available_hours"] == 0


@pytest.mark.parametrize("scope_start,scope_end,expected", [
    ("2026-09-09T00:00:00", "2026-09-10T00:00:00", 13.5),
    ("2026-09-09T01:00:00", "2026-09-09T03:00:00", 2),
    ("2026-09-09T08:00:00", "2026-09-09T15:30:00", 7.5),
])
def test_real_night_tail_and_day_capacity_match_domain(runtime_calendar, scope_start, scope_end, expected):
    api = runtime_calendar
    api.case.calendar("2026-09-08", "22:30", "06:00", hours=7.5, efficiency=0.8)
    api.case.calendar("2026-09-09", "08:00", "15:30", hours=7.5, efficiency=0.8)
    api.case.execute("UPDATE Schedule SET start_time='2026-09-09 00:00:00',end_time='2026-09-09 16:00:00'")
    calendar, _, _ = _project(api, scope_start, scope_end)
    for kind in ("machine", "operator"):
        row = resource(calendar, kind)
        assert row["available_hours"] == expected
        assert row["effective_hours"] == pytest.approx(expected * 0.8)
        assert {window["provenance"] for window in row["windows"]} == {"work_calendar"}
        _assert_domain_windows(api.case, calendar, kind)


@pytest.mark.parametrize("priority,blocked", [("normal", True), ("urgent", False), ("critical", False)])
def test_real_explicit_urgent_permission_is_not_default_normal(runtime_calendar, priority, blocked):
    api = runtime_calendar
    api.case.calendar(hours=7.5, efficiency=0.8, normal="no", urgent="yes")
    api.case.execute("UPDATE Batches SET priority=?", (priority,))
    api.case.execute("UPDATE Schedule SET end_time='2026-09-09 15:30:00'")
    calendar, occupancy, _ = _project(api, "2026-09-09T00:00:00", "2026-09-10T00:00:00")
    assert calendar["global"]["normal_available_hours"] == 0
    assert calendar["global"]["urgent_available_hours"] == 7.5
    assert calendar["global"]["urgent_effective_hours"] == 6
    assert ("assignment_outside_calendar" in codes(occupancy["issues"])) is blocked
    for kind in ("machine", "operator"):
        assert resource(occupancy, kind)["outside_available_hours"] == 0
        _assert_domain_windows(api.case, calendar, kind)


def test_real_personal_override_beats_global_holiday_and_inactive_shift(runtime_calendar):
    api = runtime_calendar
    api.case.calendar(hours=0, normal="no", urgent="no")
    api.case.execute("UPDATE WorkCalendar SET day_type='holiday'")
    api.case.shift([("22:00", "06:00", 0)], status="inactive")
    for day in ("2026-09-08", "2026-09-09"):
        api.case.calendar(day, "09:00", "12:00", operator="PRIVATE-O1", efficiency=0.8)
    calendar, occupancy, _ = _project(api, "2026-09-09T00:00:00", "2026-09-10T00:00:00")
    assert resource(calendar)["available_hours"] == 0
    person = resource(calendar, "operator")
    assert person["available_hours"] == 3 and person["effective_hours"] == 2.4
    assert person["windows"][0]["provenance"] == "personal_calendar"
    assert resource(occupancy, "operator")["outside_available_hours"] == 5
    _assert_domain_windows(api.case, calendar, "operator")


@pytest.mark.parametrize("personal", [False, True])
def test_real_explicit_leave_stays_known_zero_without_reopening(runtime_calendar, personal):
    api = runtime_calendar
    api.case.calendar(hours=7.5)
    api.case.shift([("08:00", "18:00", 0)])
    table = "OperatorCalendar" if personal else "WorkCalendar"
    if personal:
        api.case.calendar(hours=0, operator="PRIVATE-O1", normal="no", urgent="no")
    else:
        api.case.execute("UPDATE WorkCalendar SET shift_hours=0,allow_normal='no',allow_urgent='no'")
    api.case.execute("UPDATE " + table + " SET day_type='holiday'")
    calendar, occupancy, _ = _project(api, "2026-09-09T00:00:00", "2026-09-10T00:00:00")
    assert resource(calendar)["available_hours"] == (7.5 if personal else 0)
    assert resource(calendar, "operator")["state"] == "available"
    assert resource(calendar, "operator")["available_hours"] == 0
    assert resource(occupancy, "operator")["outside_available_hours"] == 8


def test_real_rotating_shift_caps_hours_and_keeps_night_tail_on_rest_day(runtime_calendar):
    api = runtime_calendar
    for day in ("2026-09-09", "2026-09-10"):
        api.case.calendar(day, hours=7.5, efficiency=0.8, normal="no", urgent="yes")
    api.case.shift([("22:00", "06:00", 0), ("00:00", "00:00", 1)])
    api.case.execute("UPDATE Batches SET priority='urgent'")
    api.case.execute("UPDATE Schedule SET start_time='2026-09-09 22:00:00',end_time='2026-09-10 05:30:00'")
    calendar, occupancy, _ = _project(api, "2026-09-10T00:00:00", "2026-09-11T00:00:00")
    person = resource(calendar, "operator")
    assert person["available_hours"] == 5.5 and person["normal_available_hours"] == 0
    assert person["effective_hours"] == 4.4
    assert [(row["start"], row["end"], row["provenance"]) for row in person["windows"]] == [
        ("2026-09-10T00:00:00", "2026-09-10T05:30:00", "work_calendar_operator_shift")]
    assert resource(occupancy, "operator")["outside_available_hours"] == 0
    assert resource(occupancy)["outside_available_hours"] == 5.5
    _assert_domain_windows(api.case, calendar, "operator")


@pytest.mark.parametrize("table", ["WorkCalendar", "OperatorCalendar"])
@pytest.mark.parametrize("assignment", ["shift_hours=NULL", "efficiency=NULL", "shift_start='29:00'",
                                         "day_type='unknown'", "allow_normal=NULL"])
def test_real_damaged_explicit_row_is_unavailable_not_default_or_zero(runtime_calendar, table, assignment):
    api = runtime_calendar
    api.case.calendar(hours=7.5)
    if table == "OperatorCalendar":
        api.case.calendar(hours=6, operator="PRIVATE-O1")
    api.case.execute("UPDATE " + table + " SET " + assignment)
    calendar, occupancy, _ = _project(api, "2026-09-09T00:00:00", "2026-09-10T00:00:00")
    kind = "operator" if table == "OperatorCalendar" else "machine"
    assert resource(calendar, kind)["state"] == "unavailable"
    assert resource(calendar, kind)["available_hours"] is None
    assert resource(occupancy, kind)["available_hours"] is None
    assert resource(occupancy, kind)["arranged_hours"] == 8
    assert "calendar_invalid" in codes(resource(calendar, kind)["issues"])


@pytest.mark.parametrize("personal", [False, True])
@pytest.mark.parametrize("day,code,status", [("2026-09-09 ", "invalid_input", 422),
                                            ("2026-09-09T00:00:00", "storage_failure", 500)])
def test_real_converted_duplicate_or_invalid_date_fails_workspace(runtime_calendar, personal, day, code, status):
    api = runtime_calendar
    operator = "PRIVATE-O1" if personal else None
    api.case.calendar(hours=7.5, operator=operator)
    api.case.calendar(day, hours=7.5, operator=operator)
    if code == "invalid_input":
        table = "OperatorCalendar" if personal else "WorkCalendar"
        rows = api.case.conn.execute("SELECT date FROM " + table).fetchall()
        assert len(rows) == 2 and all(row[0] == date(2026, 9, 9) for row in rows)
    response = api.client.get(BASE + "/" + api.ref + "/workspace", query_string={
        "range_start": "2026-09-09T00:00:00", "range_end": "2026-09-11T00:00:00"})
    assert_error(response, code, status)
    assert "data" not in response.get_json()


@pytest.mark.parametrize("day,expected", [("2026-09-09", 8), ("2026-09-12", 0)])
def test_real_absent_days_keep_domain_defaults(runtime_calendar, day, expected):
    api = runtime_calendar
    api.case.execute("UPDATE Schedule SET start_time=?,end_time=?", (day + " 08:00:00", day + " 16:00:00"))
    calendar, _, facts = _project(api, day + "T00:00:00", day + "T23:59:59")
    assert facts["sources"]["global"] == facts["sources"]["personal"] == []
    assert calendar["global"]["available_hours"] == expected
    if expected:
        assert calendar["global"]["windows"][0]["provenance"] == "domain_default"


def _facts(day, *, personal=False):
    row = dict(date=day, day_type="workday", shift_start="22:30", shift_end="06:00",
               shift_hours=7.5, efficiency=0.8, allow_normal="yes", allow_urgent="no")
    if personal:
        row["operator_id"] = "PRIVATE-O1"
    return {"global": [] if personal else [row], "personal": [row] if personal else [],
            "profiles": [], "patterns": []}


@pytest.mark.parametrize("personal", [False, True])
@pytest.mark.parametrize("day", [None, "", " ", "2026-02-30", "2026-9-09", "2026-09-09 ",
                                 "20260909", "2026-W37-3", "2026-09-09T00:00:00", b"2026-09-09",
                                 20260909, True, datetime(2026, 9, 9)])
def test_index_rejects_invalid_or_lossy_dates_without_mutating_facts(personal, day):
    facts = _facts(day, personal=personal)
    before = deepcopy(facts)
    with pytest.raises(ValidationError, match="工作日历"):
        SnapshotCalendarEngine(facts)
    assert facts == before


@pytest.mark.parametrize("personal", [False, True])
@pytest.mark.parametrize("days", [(date(2026, 9, 9), "2026-09-09"),
                                  ("2026-09-09", date(2026, 9, 9)),
                                  ("2026-09-09", "2026-09-09")])
def test_duplicate_normalized_date_is_an_error_even_for_identical_rows(personal, days):
    name = "personal" if personal else "global"
    facts = _facts(days[0], personal=personal)
    facts[name].extend(_facts(days[1], personal=personal)[name])
    before = deepcopy(facts)
    with pytest.raises(ValidationError, match="同一天出现了两条记录"):
        SnapshotCalendarEngine(facts)
    assert facts == before


def test_same_date_across_people_or_global_is_not_a_duplicate():
    facts = _facts(date(2026, 9, 9))
    facts["personal"] = _facts("2026-09-09", personal=True)["personal"]
    facts["personal"].append(dict(facts["personal"][0], operator_id="PRIVATE-O2", date=date(2026, 9, 9)))
    before = deepcopy(facts)
    engine = SnapshotCalendarEngine(facts)
    for operator in (None, "PRIVATE-O1", "PRIVATE-O2"):
        assert engine._policy_for_date("2026-09-09", operator).shift_hours == 7.5
        assert engine.provenance("2026-09-09", operator) == ("personal_calendar" if operator else "work_calendar")
    assert facts == before


def test_typed_and_legacy_string_reads_project_identically_without_retyping_sources(runtime_calendar):
    api = runtime_calendar
    api.case.calendar("2026-09-08", "22:30", "06:00")
    api.case.calendar(hours=7.5, normal="no", efficiency=0.8)
    api.case.shift([("22:00", "06:00", 0), ("00:00", "00:00", 1)])
    api.case.calendar("2026-09-09", "10:00", "14:00", operator="PRIVATE-O1", efficiency=0.6)
    start, end = "2026-09-09T00:00:00", "2026-09-11T00:00:00"
    calendar, _, facts = _project(api, start, end)
    assert resource(calendar, "operator")["windows"]
    before = deepcopy(facts)
    encoded = plain_plan_facts(facts)
    assert encoded["sources"]["global"][0]["date"] == {"storage_type": "date", "iso": "2026-09-08"}
    assert facts == before and type(facts["sources"]["personal"][0]["date"]) is date
    scope = PlanReadScope(api.ref, start, end)
    typed = WorkbenchPlanQueryService(api.case.conn)
    with typed.read_snapshot():
        typed_data, typed_state = typed.workspace(scope)
    # Independent legacy connection for equivalence only; app connections keep converters.
    with closing(sqlite3.connect(api.path)) as conn:
        conn.row_factory = sqlite3.Row
        assert type(conn.execute("SELECT date FROM WorkCalendar").fetchone()[0]) is str
        legacy = WorkbenchPlanQueryService(conn)
        with legacy.read_snapshot():
            legacy_data, legacy_state = legacy.workspace(scope)
    assert typed_data == legacy_data
    assert typed_state != legacy_state
    string_facts = deepcopy(facts)
    for name in ("global", "personal"):
        for row in string_facts["sources"][name]:
            row["date"] = row["date"].isoformat()
    assert input_fingerprint(encoded) != input_fingerprint(plain_plan_facts(string_facts))


def test_real_typed_calendar_snapshot_is_stable_and_hidden_change_stales_pin(runtime_calendar):
    api = runtime_calendar
    api.case.calendar(hours=7.5)
    api.case.execute("UPDATE WorkCalendar SET remark=?", (b"private-before",))
    start, end = "2026-09-09T00:00:00", "2026-09-10T00:00:00"
    before = list(api.case.conn.iterdump())
    first = _workspace(api, start, end)
    repeated = _workspace(api, start, end, snapshot_ref=first["meta"]["snapshot_ref"])
    assert repeated["data"] == first["data"]
    assert repeated["meta"]["snapshot_ref"] == first["meta"]["snapshot_ref"]
    assert list(api.case.conn.iterdump()) == before
    api.case.execute("UPDATE WorkCalendar SET remark=?", (b"private-after",))
    second = _workspace(api, start, end)
    assert second["data"] == first["data"]
    assert second["meta"]["snapshot_ref"] != first["meta"]["snapshot_ref"]
    response = api.client.get(BASE + "/" + api.ref + "/workspace", query_string={
        "range_start": start, "range_end": end, "snapshot_ref": first["meta"]["snapshot_ref"]})
    assert_error(response, "snapshot_stale")


def test_real_converter_calendar_read_snapshot_does_not_mix_new_capacity(runtime_calendar):
    api = runtime_calendar
    api.case.calendar(hours=7.5)
    scope = PlanReadScope(api.ref, "2026-09-09T00:00:00", "2026-09-10T00:00:00")
    service = WorkbenchPlanQueryService(api.case.conn)
    with service.read_snapshot():
        first_data, first_state = service.workspace(scope)
        with closing(get_connection(api.path)) as writer:
            with writer:
                writer.execute("UPDATE WorkCalendar SET shift_hours=3")
        assert service.workspace(scope) == (first_data, first_state)
    with service.read_snapshot():
        next_data, next_state = service.workspace(scope)
    for name in ("calendar", "occupancy"):
        assert resource(first_data["projections"][name])["available_hours"] == 7.5
        assert resource(next_data["projections"][name])["available_hours"] == 3
    assert next_state != first_state


def test_existing_full_app_root_fixture_night_and_personal_override(app_client, db_env, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parent))
    root_fixture = importlib.import_module("migration_pages_live_server")
    assert app_client.application.config["DATABASE_PATH"] == db_env
    root_fixture.seed(app_client.application)
    with closing(get_connection(db_env)) as conn:
        assert type(conn.execute("SELECT date FROM WorkCalendar").fetchone()[0]) is date
        assert type(conn.execute("SELECT date FROM OperatorCalendar").fetchone()[0]) is date
        ref = WorkbenchPlanQueryService(conn).references.get_plan_ref(WorkbenchPlanLocator(3, "adopted"))
        api = SimpleNamespace(client=app_client, ref=ref)
        body = _workspace(api, "2026-09-07T23:00:00", "2026-09-08T06:30:00")
        for name in ("calendar", "occupancy"):
            for kind in ("machine", "operator"):
                assert resource(body["data"]["projections"][name], kind)["available_hours"] == 7.5
        first = conn.execute("SELECT op_id FROM Schedule WHERE version=3 ORDER BY id LIMIT 1").fetchone()[0]
        with conn:
            conn.execute("UPDATE Schedule SET operator_id='RT-O',machine_id='RT-M',"
                         "start_time='2026-09-09 23:15:00',end_time='2026-09-10 07:45:00' WHERE version=3 AND op_id=?", (first,))
        before = list(conn.iterdump())
        body = _workspace(api, "2026-09-09T23:15:00", "2026-09-10T07:45:00")
        calendar = body["data"]["projections"]["calendar"]
        for name in ("calendar", "occupancy"):
            assert resource(body["data"]["projections"][name])["available_hours"] == 7.25
            assert resource(body["data"]["projections"][name], "operator")["available_hours"] == 8.5
        person = resource(calendar, "operator")
        assert person["effective_hours"] == 5.3125
        assert person["normal_available_hours"] == 8.5 and person["urgent_available_hours"] == 0
        assert person["windows"][0]["provenance"] == "personal_calendar"
        policy = CalendarEngine(conn).policy_for_datetime(datetime(2026, 9, 9, 23, 15), "RT-O")
        assert (policy.shift_hours, policy.efficiency) == (8.5, 0.625)
        assert policy.work_window() == (datetime(2026, 9, 9, 23, 15), datetime(2026, 9, 10, 7, 45))
        assert policy.is_priority_allowed("normal") and not policy.is_priority_allowed("urgent")
        assert list(conn.iterdump()) == before
