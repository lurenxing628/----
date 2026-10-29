"""Large current plans retain calendar facts without a dense resource/date grid."""

from collections import Counter
from datetime import datetime, timedelta

import pytest

from core.models.workbench_dashboard import DashboardAnalysisQuery
from core.services.capacity.plan_calendar_io import CalendarFacts, ProjectionLimit
from core.services.workbench.dashboard import calendar_capture
from core.services.workbench.dashboard.service import WorkbenchDashboardService
from core.services.workbench.plan.occupancy_constraints import TaskConstraints
from tests.workbench.dashboard_support import NOW
from tests.workbench.dashboard_support import dashboard_case as dashboard_case  # noqa: F401


@pytest.fixture(autouse=True)
def factory_shift(dashboard_case):
    # These plans are read against an explicitly saved 08:00-16:00 factory shift.
    dashboard_case.conn.execute("INSERT INTO WorkbenchCalendarDefaults(singleton,periods_json) VALUES (1,?)",
                                ('[{"start":"08:00","end":"16:00","day_offset":0}]',))
    dashboard_case.conn.commit()


def _capture(case):
    reader = WorkbenchDashboardService(case.conn, clock=lambda: NOW)
    with reader.read_snapshot():
        sources = reader.load()
    return reader, sources


def _large_plan(case):
    low = datetime(2026, 1, 5, 8)
    high = (low + timedelta(days=100)).replace(hour=16)
    case.conn.execute("UPDATE Schedule SET start_time=?,end_time=?", (low.isoformat(), high.isoformat()))
    for index in range(2, 202):
        machine, operator = "DM" + str(index), "DO" + str(index)
        case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES (?,?,'DT1')", (machine, machine))
        case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES (?,?)", (operator, operator))
        case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)", (operator, machine))
        operation = case.conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,unit_hours,setup_hours) "
            "VALUES (?,'DB1',?,'DT1','Turning','internal',0.5,0)", ("DOP" + str(index), index)).lastrowid
        case.conn.execute("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time) VALUES (1,?,?,?,?,?)",
                          (operation, machine, operator, low.isoformat(), high.isoformat()))
    case.conn.commit()


def test_over_40000_resource_dates_keep_complete_sources_and_current_resource_capacity(dashboard_case, monkeypatch):
    case = dashboard_case
    _large_plan(case)
    calls, original = Counter(), calendar_capture.calendar_from_sources

    def factory(*args, **kwargs):
        result = original(*args, **kwargs)
        assert result is not None
        stream = result.iter_resources

        def tracked(resources, start, end):
            for resource in resources:
                calls[resource["kind"], resource["saved_id"]] += 1
            yield from stream(resources, start, end)

        monkeypatch.setattr(result, "iter_resources", tracked)
        return result

    monkeypatch.setattr(calendar_capture, "calendar_from_sources", factory)
    reader, sources = _capture(case)
    facts = sources.facts
    private = facts.raw["resource_pressure"]
    calendar = private["calendar"]
    assert facts.pressure["resource_count"] == 402
    assert calendar["state"] == facts.pressure["state"] == "available"
    assert calendar["sources"] is not None and calendar["fact_count"] < 50000
    assert len(calendar["sources"]["machines"]) == len(calendar["sources"]["operators"]) == 201
    assert not private["constraints"] and "resources" not in facts.pressure
    assert len(calls) == 402 and set(calls.values()) == {1}
    assert calendar["resources"] is None and private["occupancy"] is None
    # Analysis remains usable after the source snapshot closes. No current
    # SQL read is needed to recover capacity from this complete capture.
    case.conn.set_authorizer(lambda *_: 1)
    try:
        analysis = reader.analysis(sources, DashboardAnalysisQuery("pressure", size=100))
        assert facts.pressure_metrics is not None
        calendar_factory = facts.pressure_metrics.factory
        assert calendar_factory is not None
        resource = analysis["resources"][0]
        kind, ref = resource["kind"], resource["resource_ref"]
        projected = dict(calendar_factory.iter_resources([{"kind": kind, "ref": ref,
            "saved_id": calendar_factory.bindings[kind, ref]}], analysis["time_scope"]["range_start"], analysis["time_scope"]["range_end"]))[ref]
    finally:
        case.conn.set_authorizer(None)
    assert analysis["pagination"]["total"] == 402
    assert all(row["window_metrics"]["available_hours"] is not None for row in analysis["resources"])
    assert resource["window_metrics"]["available_hours"] == projected["available_hours"]


def test_streamed_constraints_keep_qualification_type_calendar_and_downtime_issues(dashboard_case):
    case = dashboard_case
    case.conn.execute("UPDATE Schedule SET start_time='2026-09-09T07:00:00'")
    case.conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,skills_declared) VALUES ('DO1',1)")
    case.conn.execute("DELETE FROM OperatorMachine WHERE operator_id='DO1'")
    case.conn.execute("UPDATE OpTypes SET category='external' WHERE op_type_id='DT1'")
    case.conn.commit()
    _, sources = _capture(case)
    facts = sources.facts
    codes = {item["code"] for item in facts.pressure["issues"]}
    assert {"assignment_outside_calendar", "assignment_machine_downtime", "assignment_not_authorized",
            "assignment_work_type_mismatch"} <= codes
    assert all(ids == [case.op] for ids in facts.raw["resource_pressure"]["constraints"].values())
    # Authorization and explicit skill qualification remain separate domain
    # checks, using the same captured source contract as the previous consumer.
    case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('DO1','DM1')")
    case.conn.execute("UPDATE OpTypes SET category='internal' WHERE op_type_id='DT1'")
    case.conn.commit()
    _, sources = _capture(case)
    assert "assignment_not_qualified" in {item["code"] for item in sources.facts.pressure["issues"]}


@pytest.mark.parametrize("failure", ["calendar_range_limit", "calendar_fact_limit"])
def test_capture_retains_real_calendar_date_and_source_fact_limits(dashboard_case, monkeypatch, failure):
    case = dashboard_case
    if failure == "calendar_range_limit":
        case.conn.execute("UPDATE Schedule SET start_time='2010-01-04T08:00:00',end_time='2026-09-09T10:00:00'")
        case.conn.commit()
    else:
        def over_budget(*args, **kwargs):
            raise ProjectionLimit("calendar_fact_limit")

        monkeypatch.setattr(CalendarFacts, "resources", over_budget)
    _, sources = _capture(case)
    calendar = sources.facts.raw["resource_pressure"]["calendar"]
    assert calendar["sources"] is None and calendar["reason"] == failure
    assert sources.facts.pressure["state"] == "unavailable"
    assert {item["code"] for item in sources.facts.pressure["issues"]} == {"assignment_calendar_unavailable"}


def test_unstreamed_pressure_builds_one_index_and_repeats_identity_gaps(dashboard_case, monkeypatch):
    case = dashboard_case
    case.conn.execute("UPDATE Schedule SET machine_id=NULL")
    case.conn.commit()
    index_type, indexes = calendar_capture.ResourceTaskIndex, []

    def resource_task_index(*args, **kwargs):
        indexes.append(index_type(*args, **kwargs))
        return indexes[-1]

    def over_budget(*args, **kwargs):
        raise ProjectionLimit("calendar_fact_limit")

    monkeypatch.setattr(CalendarFacts, "resources", over_budget)
    monkeypatch.setattr(calendar_capture, "ResourceTaskIndex", resource_task_index)
    reader, sources = _capture(case)
    assert sources.facts.raw["resource_pressure"]["calendar"]["reason"] == "calendar_fact_limit"
    assert sources.facts.pressure_metrics is not None
    assert indexes == [] and sources.facts.pressure_metrics.summaries == {}
    first = reader.analysis(sources, DashboardAnalysisQuery("pressure", size=100))
    # Analysis projects the uncaptured cohort once; a later read reuses those
    # summaries and still reports the same missing machine identity.
    assert first["resource_common"]["machine"]["unknown_workload_count"] == 1
    assert reader.analysis(sources, DashboardAnalysisQuery("pressure", size=100)) == first
    assert len(indexes) == 1 and indexes[0] is sources.facts.pressure_metrics.index


def test_one_streamed_operator_window_supplies_both_priorities(dashboard_case):
    _, sources = _capture(dashboard_case)
    calendar = sources.facts.raw["resource_pressure"]["calendar"]
    scope = sources.facts.pressure["time_scope"]
    assert sources.facts.pressure_metrics is not None
    factory = sources.facts.pressure_metrics.factory
    assert factory is not None
    ref = next(ref for (kind, ref) in factory.bindings if kind == "operator")
    calls = []

    def lookup(kind, key):
        calls.append((kind, key))
        return dict(factory.iter_resources([{"kind": kind, "ref": ref, "saved_id": key}],
            scope["range_start"], scope["range_end"]))[ref]

    constraints = TaskConstraints(calendar, calendar_lookup=lookup)
    row = sources.facts.task_rows[0]
    start, end = (datetime.fromisoformat(row[key]) for key in ("start_time", "end_time"))
    for priority in ("normal", "urgent", "critical", "normal"):
        constraints.check(dict(row, priority=priority), start, end, row_start=start, row_end=end)
    assert calls == [("operator", "DO1")]
    assert constraints.private() == {"assignment_machine_downtime": [dashboard_case.op]}


@pytest.mark.parametrize("profile_status,is_rest", [("inactive", 0), ("active", 1)])
def test_point_event_calendar_catches_shift_validation_and_business_errors(dashboard_case, profile_status, is_rest):
    case = dashboard_case
    case.conn.execute(
        "INSERT INTO WorkbenchShiftProfiles(profile_id,name,cycle_days,anchor_date,status) "
        "VALUES ('SP-POINT','Point Shift',1,'2026-09-01',?)",
        (profile_status,),
    )
    case.conn.execute(
        "INSERT INTO WorkbenchShiftPatternDays(profile_id,day_offset,is_rest,shift_start,shift_end) "
        "VALUES ('SP-POINT',0,?,'08:00','16:00')",
        (is_rest,),
    )
    case.conn.execute(
        "INSERT INTO WorkbenchOperatorProfiles(operator_id,shift_profile_id) VALUES ('DO1','SP-POINT')"
    )
    case.conn.commit()
    _, sources = _capture(case)
    calendar = sources.facts.raw["resource_pressure"]["calendar"]
    constraints = TaskConstraints(calendar)
    row = dict(
        sources.facts.task_rows[0],
        _point_work={
            "operation": {"setup_hours": 0.0, "unit_hours": 0.0},
            "batch": {"priority": "normal"},
            "quantity": 2,
        },
    )
    at = datetime.fromisoformat(row["start_time"])
    constraints.check(row, at, at, row_start=at, row_end=at)
    assert "assignment_calendar_unavailable" in constraints.private()
