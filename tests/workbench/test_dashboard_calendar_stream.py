"""Large current plans retain calendar facts without a dense resource/date grid."""

from collections import Counter
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.models.workbench_dashboard import DashboardAnalysisQuery
from core.services.capacity.plan_calendar_io import CalendarFacts, ProjectionLimit
from core.services.report.utilization_calendars import resource_calendars
from core.services.workbench.dashboard import calendar_capture
from core.services.workbench.dashboard.service import WorkbenchDashboardService
from core.services.workbench.facts.archived_calendar import ArchivedCalendar
from core.services.workbench.plan.calendar import project_plan_calendar
from core.services.workbench.plan.occupancy_constraints import TaskConstraints
from tests.workbench.dashboard_support import NOW
from tests.workbench.dashboard_support import dashboard_case as dashboard_case  # noqa: F401


@pytest.fixture(autouse=True)
def legacy_calendar_schema(dashboard_case):
    # This fixture installs current metadata directly on schema.sql's version-0
    # seed. A valid saved/current legacy calendar declares its real version.
    dashboard_case.conn.execute("UPDATE SchemaVersion SET version=33 WHERE id=1")
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
        calendar_factory = facts.calendar_factory
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


def test_one_streamed_operator_window_supplies_both_priorities(dashboard_case):
    _, sources = _capture(dashboard_case)
    calendar = sources.facts.raw["resource_pressure"]["calendar"]
    scope = sources.facts.pressure["time_scope"]
    factory = sources.facts.calendar_factory
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
        constraints.check(dict(row, priority=priority), start, end)
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
    constraints.check(row, at, at)
    assert "assignment_calendar_unavailable" in constraints.private()


_INVALID = ("unavailable", ["calendar_invalid"])


def _codes(item):
    return item["state"], [entry["code"] for entry in item["issues"]]


def _streamed(factory, scope, kind, key):
    ref = next(ref for (bound_kind, ref), saved_id in factory.bindings.items() if (bound_kind, saved_id) == (kind, key))
    return dict(factory.iter_resources([{"kind": kind, "ref": ref, "saved_id": key}],
                                       scope["range_start"], scope["range_end"]))[ref]


def _report_and_plan_calendars(case, operators):
    """报表占用率和计划日历两条入口各自用同一份当前库日历构造引擎；坏日历只能变成不可用，不能中途抛错。"""
    start, end = datetime(2026, 9, 9, 8), datetime(2026, 9, 9, 10)
    rows = [{"op_id": case.op, "machine_id": "DM1", "operator_id": key, "source": "internal",
             "start_time": start.isoformat(), "end_time": end.isoformat()} for key in operators]
    report = resource_calendars(case.conn, rows, start, end)
    identities = {"machine": {"DM1": SimpleNamespace(ref="ref-DM1")},
                  "operator": {key: SimpleNamespace(ref="ref-" + key) for key in operators}}
    dto, facts = project_plan_calendar(case.conn, entry=None, scope=SimpleNamespace(plan_ref="plan-ref"), rows=rows,
                                       resources=identities, plan_span=None, selected=(rows, start, end, {}, None))
    return dto["global"], report, facts["resources"]


def test_damaged_calendar_keeps_dashboard_unavailable_without_rebuilding_point_engine(dashboard_case):
    case = dashboard_case
    # 带尾随空格的日期落在读取范围内，共享日历引擎拒绝它；错误留在引擎里，读到全局日历的策略才报日历无效。
    case.conn.execute("INSERT INTO WorkCalendar(date,day_type,shift_hours,efficiency,allow_normal,allow_urgent) "
                      "VALUES ('2026-09-08 ','workday',8,1,'yes','yes')")
    case.conn.commit()
    _, sources = _capture(case)
    facts = sources.facts
    calendar = facts.raw["resource_pressure"]["calendar"]
    factory = facts.calendar_factory
    assert calendar["sources"] is not None and factory.engine is not None
    assert calendar["state"] == facts.pressure["state"] == "unavailable"
    assert "assignment_calendar_unavailable" in {item["code"] for item in facts.pressure["issues"]}
    scope = facts.pressure["time_scope"]
    assert _codes(_streamed(factory, scope, "machine", "DM1")) == _codes(_streamed(factory, scope, "operator", "DO1")) == _INVALID
    # 点时间检查沿用工厂那台带着日历错误的引擎，不另建一台。
    constraints = TaskConstraints(calendar, point_calendar=factory.engine)
    assert constraints.point_calendar is factory.engine
    # 保存表结构坏了时工厂交来显式 None，不能当成没给而重建一遍引擎。
    assert TaskConstraints(calendar, point_calendar=None).point_calendar is None
    row = dict(facts.task_rows[0], _point_work={"operation": {"setup_hours": 0.0, "unit_hours": 0.0},
                                               "batch": {"priority": "normal"}, "quantity": 2})
    at = datetime.fromisoformat(row["start_time"])
    constraints.check(row, at, at)
    assert constraints.private()["assignment_calendar_unavailable"] == [case.op]


def test_damaged_global_calendar_date_reports_calendar_invalid_instead_of_raising(dashboard_case):
    case = dashboard_case
    case.conn.execute("INSERT INTO WorkCalendar(date,day_type,shift_hours,efficiency,allow_normal,allow_urgent) "
                      "VALUES ('2026-09-08 ','workday',8,1,'yes','yes')")
    case.conn.commit()
    global_calendar, report, plan = _report_and_plan_calendars(case, ["DO1"])
    assert _codes(global_calendar) == _INVALID
    for kind, key in (("machine", "DM1"), ("operator", "DO1")):
        assert _codes(report[kind, key]) == _codes(plan[kind][key]) == _INVALID


def test_damaged_personal_calendar_invalidates_personnel_but_keeps_global_and_machine(dashboard_case):
    case = dashboard_case
    case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('DO2','Second operator')")
    case.conn.execute("INSERT INTO OperatorCalendar(operator_id,date,day_type,shift_hours,efficiency,allow_normal,allow_urgent) "
                      "VALUES ('DO1','2026-09-08 ','workday',8,1,'yes','yes')")
    case.conn.commit()
    global_calendar, report, plan = _report_and_plan_calendars(case, ["DO1", "DO2"])
    assert global_calendar["state"] == "available"
    assert report["machine", "DM1"]["state"] == plan["machine"]["DM1"]["state"] == "available"
    # 个人日历表坏了就确认不了 DO2 没有个人日历，不能拿全局日历顶替。
    for key in ("DO1", "DO2"):
        assert _codes(report["operator", key]) == _codes(plan["operator"][key]) == _INVALID
    # 看板归档日历工厂同一口径：空的个人日历索引不能让人员借用全局日历的结果。
    _, sources = _capture(case)
    factory, scope = sources.facts.calendar_factory, sources.facts.pressure["time_scope"]
    assert _streamed(factory, scope, "machine", "DM1")["state"] == "available"
    assert _codes(_streamed(factory, scope, "operator", "DO1")) == _INVALID
    assert sources.facts.raw["resource_pressure"]["calendar"]["state"] == "partial"


def test_saved_damaged_personal_calendar_outranks_missing_shift_tables():
    machine, operator = "m" * 48, "o" * 48
    personal = {"operator_id": "O1", "date": "2026-10-12 ", "day_type": "workday", "shift_start": "08:00",
                "shift_end": "16:00", "shift_hours": 8, "efficiency": 1, "allow_normal": "yes", "allow_urgent": "yes",
                "remark": None, "periods_json": None}
    # 保存资料缺了人员班表登记（WorkbenchOperatorProfiles 不在表里）；个人日历表本身也坏了。
    saved = {"tables": {"SchemaVersion": [{"id": 1, "version": 35}],
        "WorkbenchEntityRefs": [{"kind": "machine", "ref": machine, "entity_key": "M1", "active": 1},
                                {"kind": "operator", "ref": operator, "entity_key": "O1", "active": 1}],
        "Machines": [{"machine_id": "M1", "name": "保存的设备", "status": "active"}],
        "Operators": [{"operator_id": "O1", "name": "保存的人员", "status": "active"}],
        "WorkCalendar": [], "OperatorCalendar": [personal], "MachineDowntimes": [], "WorkbenchShiftProfiles": [],
        "WorkbenchShiftPatternDays": [], "WorkbenchShiftDayPeriods": [], "WorkbenchCalendarDefaults": []}}
    projected = dict(ArchivedCalendar(saved).iter_resources(
        [{"kind": "machine", "ref": machine, "saved_id": "M1"}, {"kind": "operator", "ref": operator, "saved_id": "O1"}],
        "2026-10-12T00:00:00", "2026-10-13T00:00:00"))
    assert projected[machine]["state"] == "available"
    # 查不清这天有没有个人日历时，先报个人日历无效，而不是缺了班表资料。
    assert _codes(projected[operator]) == _INVALID
    assert all("missing_fact" not in item for item in projected[operator]["issues"])
