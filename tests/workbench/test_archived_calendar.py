"""Saved identity, calendar versions and known/unknown day coverage contracts."""

import json
from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace

import pytest

from core.infrastructure.schema_declaration import declared_tables, load_schema_sql
from core.models.content import content_text
from core.models.enums import (
    BATCH_OPERATION_STATUS_VALUES,
    BATCH_PRIORITY_VALUES,
    BATCH_STATUS_VALUES,
    FLAG_VALUES,
    MACHINE_DOWNTIME_STATUS_VALUES,
    MACHINE_STATUS_VALUES,
    MERGE_MODE_VALUES,
    OP_TYPE_CATEGORY_VALUES,
    OPERATOR_STATUS_VALUES,
    PLAN_SOURCE_KIND_VALUES,
    READY_STATUS_VALUES,
    SHIFT_CYCLE_DAYS_MAX,
    SHIFT_DAY_OFFSET_MAX,
    SHIFT_PROFILE_STATUS_VALUES,
    SKILL_LEVEL_VALUES,
    SOURCE_TYPE_VALUES,
    SUPPLIER_STATUS_VALUES,
    YESNO_VALUES,
)
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts.archived_calendar import ArchivedCalendar, archived_calendar_tables
from core.services.workbench.facts.candidate_facts import admit_generation_facts
from core.services.workbench.facts.production_capture import (
    CORRUPT_ARCHIVE,
    ProductionFactsCapture,
    validate_production_archive,
)
from core.services.workbench.plan.occupancy import _resource_occupancy
from core.shared.local_datetime import datetime_to_us
from core.shared.strict_parse import TIME_US_MAX
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401

MACHINE, OPERATOR = "a" * 48, "b" * 48
RESOURCES = [{"kind": "machine", "ref": MACHINE, "saved_id": "M1"},
             {"kind": "operator", "ref": OPERATOR, "saved_id": "O1"}]


def archive(version=50):
    """The calendar tables ``ArchivedCalendar`` reads, with named rows."""
    return {"SchemaVersion": [{"id": 1, "version": version}],
        "WorkbenchEntityRefs": [{"kind": kind, "ref": ref, "entity_key": key, "active": 1}
                                for kind, ref, key in (("machine", MACHINE, "M1"), ("operator", OPERATOR, "O1"))],
        "Machines": [{"machine_id": "M1", "name": "保存的设备", "status": "active"}],
        "Operators": [{"operator_id": "O1", "name": "保存的人员", "status": "active"}],
        "WorkCalendar": [], "OperatorCalendar": [], "MachineDowntimes": [],
        "WorkbenchOperatorProfiles": [], "WorkbenchShiftProfiles": [], "WorkbenchShiftPatternDays": [],
        "WorkbenchCalendarDefaults": []}


def downtime(start, end, status="active"):
    return {"machine_id": "M1", "start_us": datetime_to_us(datetime.fromisoformat(start)),
            "end_us": datetime_to_us(datetime.fromisoformat(end)), "status": status}


def day(key, start="08:00", end: object = "16:00", *, efficiency: object = 1,
        normal="yes", urgent="yes", operator=None):
    periods_json = (
        f'[{{"start":"{start}","end":"{end}","day_offset":0}}]'
        if isinstance(start, str) and isinstance(end, str)
        else None
    )
    row = {"date": key, "day_type": "workday", "efficiency": efficiency, "allow_normal": normal, "allow_urgent": urgent,
           "remark": None, "periods_json": periods_json}
    if operator is not None:
        row["operator_id"] = operator
    return row


def project(saved, start="2026-10-12T00:00:00", end="2026-10-13T00:00:00", resources=RESOURCES, **kwargs):
    return dict(ArchivedCalendar(saved, source_ref="saved-calendar-ref", **kwargs).iter_resources(resources, start, end))


def test_saved_calendar_defaults_and_domain_default_periods():
    modern = archive()
    new = project(modern)[MACHINE]
    assert new["available_hours"] == pytest.approx(22 / 3, abs=1e-6)
    assert len(new["windows"]) == 2
    resources = project(modern)
    assert resources[OPERATOR]["windows"] == resources[MACHINE]["windows"]
    assert resources[OPERATOR]["days"][0]["windows"] is resources[MACHINE]["days"][0]["windows"]
    assert resources[OPERATOR]["basis"] == "personal_or_operator_shift_calendar"
    assert all(row["provenance"] == "domain_default" for row in resources[OPERATOR]["windows"])
    assert resources[MACHINE]["days"][0]["downtime_scope_hours"] == 0.0
    assert resources[MACHINE]["days"][0]["downtime_available_hours"] == 0.0
    modern["WorkbenchCalendarDefaults"] = [{"singleton": 1, "periods_json":
        '[{"start":"09:00","end":"12:00","day_offset":0},{"start":"14:00","end":"18:00","day_offset":0}]'}]
    assert project(modern)[MACHINE]["available_hours"] == 7


def test_night_tail_priority_overlay_and_downtime_use_exact_half_open_window():
    saved = archive()
    saved["WorkCalendar"] = [day("2026-10-12", "22:00", "06:00", efficiency=0.5),
                             day("2026-10-13", "05:00", "05:30", normal="no")]
    saved["MachineDowntimes"] = [
        downtime("2026-10-13T04:30:00", "2026-10-13T05:15:00"),
        downtime("2026-10-13T00:00:00", "2026-10-14T00:00:00", "cancelled"),
        downtime("2026-10-14T00:00:00", "2026-10-15T00:00:00")]
    result = project(saved, "2026-10-13T04:00:00", "2026-10-13T06:00:00")[MACHINE]
    assert result["available_hours"] == 1.25
    assert result["effective_hours"] == 0.75
    assert result["normal_available_hours"] == 1 and result["urgent_available_hours"] == 1.25
    assert [(row["start"], row["end"]) for row in result["windows"]] == [
        (datetime(2026, 10, 13, 4, 0), datetime(2026, 10, 13, 4, 30)),
        (datetime(2026, 10, 13, 5, 15), datetime(2026, 10, 13, 5, 30)),
        (datetime(2026, 10, 13, 5, 30), datetime(2026, 10, 13, 6, 0))]


def test_machine_downtime_history_is_read_once_per_row_and_cancelled_rows_are_not_downtime(monkeypatch):
    from core.services.workbench.facts import archived_calendar

    saved = archive()
    saved["MachineDowntimes"] = [downtime("2020-01-01T08:00:00", "2020-01-01T09:00:00") for _ in range(100)] + [
        downtime("2026-10-15T08:00:00", "2026-10-15T09:00:00", "cancelled")]
    read, original = [], archived_calendar.union

    def union(windows):
        windows = list(windows)
        read.append(windows)
        return original(windows)

    monkeypatch.setattr(archived_calendar, "union", union)
    result = project(saved, "2026-10-12T00:00:00", "2026-10-16T00:00:00", resources=RESOURCES[:1])[MACHINE]
    # 四天投影只建一次这台设备的停机索引，读入的是 100 条有效停机，已取消的不读。
    assert read == [[(datetime(2020, 1, 1, 8), datetime(2020, 1, 1, 9))] * 100]
    assert [row["state"] for row in result["days"]] == ["available"] * 4
    assert result["days"][-1]["downtime_scope_hours"] == 0.0


def test_microsecond_calendar_and_occupancy_preserve_device_and_person_hours():
    saved = archive()
    saved["WorkCalendar"] = [day("2026-10-12", efficiency=0.5)]
    start, pause, resume, end = ["2026-10-12T08:00:00." + str(value).zfill(6) for value in range(4)]
    saved["MachineDowntimes"] = [downtime(pause, resume)]
    calendars = project(saved, start, end)
    unit = 1e-6 / 3600.0
    low, first, last, high = (datetime.fromisoformat(value) for value in (start, pause, resume, end))
    operations = {"one": [(low, high)], "two": [(first, last)]}
    refs = {"machine": {"M1": SimpleNamespace(ref=MACHINE)}, "operator": {"O1": SimpleNamespace(ref=OPERATOR)}}
    for kind, key, ref, duration in (("machine", "M1", MACHINE, 2), ("operator", "O1", OPERATOR, 3)):
        calendar = calendars[ref]
        for mode in ("", "normal_", "urgent_"):
            for measure, factor in (("available_hours", 1), ("effective_hours", 0.5)):
                field = mode + measure
                assert calendar[field] == calendar["days"][0][field]
                assert calendar[field] == pytest.approx(duration * unit * factor, rel=1e-12, abs=0)
        resource, complete = _resource_occupancy(
            kind, key, operations, {**calendar, "label": kind}, refs, kind, include_segments=True
        )
        assert complete is True
        assert resource["available_hours"] == calendar["available_hours"]
        expected = {"arranged_hours": 4 * unit, "occupied_hours": 3 * unit, "overlap_hours": unit,
                    "excess_arranged_hours": unit, "available_occupied_hours": duration * unit,
                    "outside_available_hours": (3 - duration) * unit,
                    "capacity_shortfall_hours": unit if kind == "operator" else 0,
                    "available_overlap_hours": unit if kind == "operator" else 0}
        for field, value in expected.items():
            assert resource[field] == pytest.approx(value, rel=1e-12, abs=0)
        assert resource["has_overlap"] is (kind == "operator")
        assert len(resource["conflict_segments"]) == (1 if kind == "operator" else 0)
        assert resource["utilization"] == 1
        for field in ("downtime_scope_hours", "downtime_available_hours"):
            assert calendar["days"][0][field] == pytest.approx(unit if kind == "machine" else 0, rel=1e-12, abs=0)


def test_saved_personal_override_and_rotating_rest_keep_operator_capacity():
    saved = archive()
    tables = saved
    tables["WorkbenchCalendarDefaults"] = [{"singleton": 1, "periods_json":
        '[{"start":"08:00","end":"16:00","day_offset":0}]'}]
    tables["WorkbenchOperatorProfiles"] = [{"operator_id": "O1", "shift_profile_id": "NIGHT"}]
    tables["WorkbenchShiftProfiles"] = [{"profile_id": "NIGHT", "anchor_date": "2026-10-12", "cycle_days": 2, "status": "active"}]
    tables["WorkbenchShiftPatternDays"] = [
        {"profile_id": "NIGHT", "day_offset": 0, "is_rest": 0,
         "periods_json": '[{"start":"22:00","end":"06:00","day_offset":0}]'},
        {"profile_id": "NIGHT", "day_offset": 1, "is_rest": 1,
         "periods_json": "[]"}]
    tail = project(saved, "2026-10-13T00:00:00", "2026-10-13T06:00:00")[OPERATOR]
    assert tail["available_hours"] == 6 and tail["windows"][0]["provenance"] == "domain_default_operator_shift"
    rest = project(saved, "2026-10-13T08:00:00", "2026-10-13T16:00:00")[OPERATOR]
    assert rest["state"] == "available" and rest["windows"] == [] and rest["available_hours"] == 0
    tables["OperatorCalendar"] = [day("2026-10-13", "09:00", "12:00", efficiency=0.25, normal="no", operator="O1")]
    tables["WorkbenchShiftProfiles"][0]["status"] = "inactive"
    personal = project(saved, "2026-10-13T09:00:00", "2026-10-13T12:00:00")[OPERATOR]
    assert personal["state"] == "available" and personal["available_hours"] == 3
    assert personal["effective_hours"] == 0.75 and personal["normal_available_hours"] == 0
    assert personal["windows"][0]["provenance"] == "personal_calendar"
    tables["WorkbenchOperatorProfiles"] = []
    tables["OperatorCalendar"] = [day("2026-10-12", "22:00", "06:00", operator="O1")]
    personal_tail = project(saved, "2026-10-13T00:00:00", "2026-10-13T06:00:00")[OPERATOR]
    assert personal_tail["available_hours"] == 6
    assert personal_tail["windows"][0]["provenance"] == "personal_calendar"


def test_broken_policy_days_keep_other_days_known_and_defaults_are_lazy():
    saved = archive()
    saved["WorkCalendar"] = [day("2026-10-13", end=None)]
    result = project(saved, "2026-10-12T00:00:00", "2026-10-16T00:00:00")[MACHINE]
    assert result["state"] == "partial" and result["available_hours"] is None and result["windows"] is None
    assert [row["state"] for row in result["days"]] == ["available", "unavailable", "unavailable", "available"]
    assert (result["known_days"], result["unknown_days"]) == (2, 2)
    assert result["known_windows"]


def test_declared_bounded_coverage_is_not_extended_with_implicit_defaults():
    saved = archive()
    result = project(saved, "2026-10-12T00:00:00", "2026-10-15T00:00:00",
                     coverage={"start": "2026-10-12T00:00:00", "end": "2026-10-14T00:00:00"})[MACHINE]
    assert [row["state"] for row in result["days"]] == ["available", "available", "unavailable"]
    assert result["days"][-1]["end"] == datetime(2026, 10, 15, 0, 0)
    assert result["days"][-1]["issues"][0]["missing_fact"] == "calendar_coverage"
    with pytest.raises(WorkbenchCommandRejected) as exc:
        project(saved, "2020-01-01T00:00:00", "2031-01-01T00:00:00")
    assert exc.value.status == 422


def test_saved_archive_and_its_stored_copy_never_read_live_calendars(candidate_case):
    case = candidate_case
    saved = ProductionFactsCapture(case.conn).scoped_archive(())
    stored = json.loads(content_text(saved))
    resources = [{"kind": kind, "ref": case.ref(kind, key), "saved_id": key}
                 for kind, key in (("machine", "M1"), ("operator", "O1"))]
    case.conn.execute("UPDATE Machines SET status='inactive' WHERE machine_id='M1'")
    case.conn.execute("UPDATE WorkbenchCalendarDefaults SET periods_json=?",
                      ('[{"start":"09:00","end":"12:00","day_offset":0}]',))
    case.conn.commit()
    case.conn.execute("BEGIN")
    current_snapshot = archived_calendar_tables(ProductionFactsCapture(case.conn).scoped_archive(()))
    saved_tables, stored_tables = archived_calendar_tables(saved), archived_calendar_tables(stored)
    statements = []
    case.conn.set_trace_callback(statements.append)
    try:
        run = dict(ArchivedCalendar(saved_tables).iter_resources(resources, "2026-10-12T08:00:00", "2026-10-12T16:00:00"))
        reread = dict(ArchivedCalendar(stored_tables).iter_resources(
            resources, "2026-10-12T08:00:00", "2026-10-12T16:00:00"))
        current = dict(ArchivedCalendar(current_snapshot, metadata_basis="current_transaction_snapshot").iter_resources(
            resources, "2026-10-12T08:00:00", "2026-10-12T16:00:00"))
    finally:
        case.conn.set_trace_callback(None)
        case.conn.rollback()
    assert statements == []
    assert run == reread
    assert all(row["available_hours"] == 8 for row in run.values())
    assert all(row["source"]["metadata_basis"] == "saved_archive" for row in run.values())
    assert current[resources[0]["ref"]]["available_hours"] == 0
    assert current[resources[1]["ref"]]["available_hours"] == 3
    assert all(row["source"]["metadata_basis"] == "current_transaction_snapshot" for row in current.values())


def test_saved_archive_admits_every_downtime_instant_at_its_storage_boundary(candidate_case):
    case = candidate_case
    low, high = datetime_to_us(datetime(2026, 10, 12, 8)), datetime_to_us(datetime(2026, 10, 12, 9))
    case.conn.executemany(
        "INSERT INTO MachineDowntimes(machine_id,start_time,end_time,start_us,end_us,reason_code,status) "
        "VALUES ('M1','2026-10-12 08:00:00','2026-10-12 09:00:00',?,?,'maintenance',?)",
        [(low, high, "active"), (low, high, "cancelled")])
    case.conn.commit()
    stored = json.loads(content_text(ProductionFactsCapture(case.conn).scoped_archive(())))
    validate_production_archive(stored)
    admit_generation_facts({"facts": stored, "execution": []})
    columns = stored["columns"]["MachineDowntimes"]
    rows = {row[columns.index("status")]: index for index, row in enumerate(stored["tables"]["MachineDowntimes"])}
    # 表的 CHECK 不随 JSON 副本走：有效或已取消停机的任一端不是存储微秒，整份归档都按损坏拒收。
    for status, column in (("active", "start_us"), ("cancelled", "end_us")):
        for value in ("2026-10-12 08:00:00", 1.5, True, None, TIME_US_MAX + 1):
            broken = deepcopy(stored)
            broken["tables"]["MachineDowntimes"][rows[status]][columns.index(column)] = value
            with pytest.raises(ValueError, match=CORRUPT_ARCHIVE):
                validate_production_archive(broken)
            with pytest.raises(WorkbenchCommandRejected) as rejected:
                admit_generation_facts({"facts": broken, "execution": []})
            assert (rejected.value.code, rejected.value.status) == ("candidate_artifact_invalid", 500)
    # 起止都是存储微秒但结束不晚于开始，同样违反表的 CHECK(start_us < end_us)。
    broken = deepcopy(stored)
    broken["tables"]["MachineDowntimes"][rows["active"]][columns.index("end_us")] = low
    with pytest.raises(ValueError, match=CORRUPT_ARCHIVE):
        validate_production_archive(broken)


def test_saved_archive_admits_every_external_cycle_at_its_storage_boundary(candidate_case):
    # 归档里的本序外协周期与整组周期会被试调当自然日累加，JSON 副本不带表的 CHECK，在归档准入处按同一值域拒收。
    case = candidate_case
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('EXT','Heat treatment','external')")
    case.conn.execute("INSERT INTO Suppliers(supplier_id,name,default_days) VALUES ('S1','Supplier',2)")
    case.conn.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id) "
                      "VALUES ('EG','P1',2,2,'merged',1.5,'S1')")
    case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days,ext_group_id) "
                      "VALUES ('P1',2,'EXT','Heat treatment','external','S1',2,'EG')")
    case.operation(seq=2, op_type_id="EXT", op_type_name="Heat treatment", source="external", supplier_id="S1",
                   machine_id=None, operator_id=None, ext_days=2)
    case.conn.commit()
    stored = json.loads(content_text(ProductionFactsCapture(case.conn).scoped_archive([case.ref("batch", "B1")])))
    validate_production_archive(stored)
    for table, column in (("BatchOperations", "ext_days"), ("BatchExternalContexts", "total_days")):
        columns = stored["columns"][table]
        index = next(i for i, row in enumerate(stored["tables"][table]) if row[columns.index(column)] is not None)
        for value in (None, 36500):  # 没设周期与 100 年上限本身都收
            kept = deepcopy(stored)
            kept["tables"][table][index][columns.index(column)] = value
            validate_production_archive(kept)
        for value in (0, -1, 36500.5, float("inf"), float("nan"), True, "2"):
            broken = deepcopy(stored)
            broken["tables"][table][index][columns.index(column)] = value
            with pytest.raises(ValueError, match=CORRUPT_ARCHIVE):
                validate_production_archive(broken)
            with pytest.raises(WorkbenchCommandRejected) as rejected:
                admit_generation_facts({"facts": broken, "execution": []})
            assert (rejected.value.code, rejected.value.status) == ("candidate_artifact_invalid", 500)


def _saved_archive_with_every_checked_table(case):
    """A real scoped archive whose every checked and keyed table holds at least one row."""
    low, high = datetime_to_us(datetime(2026, 10, 12, 8)), datetime_to_us(datetime(2026, 10, 12, 16))
    periods = '[{"start":"08:00","end":"16:00","day_offset":0}]'
    case.conn.execute("INSERT INTO MachineDowntimes(machine_id,start_time,end_time,start_us,end_us,reason_code,status) "
                      "VALUES ('M1','2026-10-12 08:00:00','2026-10-12 16:00:00',?,?,'maintenance','active')", (low, high))
    case.conn.execute("INSERT INTO Suppliers(supplier_id,name,default_days) VALUES ('S1','Supplier',2)")
    case.conn.execute("INSERT INTO WorkCalendar(date,day_type,efficiency,allow_normal,allow_urgent,periods_json) "
                      "VALUES ('2026-10-12','workday',1,'yes','yes',?)", (periods,))
    case.conn.execute("INSERT INTO OperatorCalendar(operator_id,date,day_type,efficiency,allow_normal,allow_urgent,"
                      "periods_json) VALUES ('O1','2026-10-12','workday',1,'yes','yes',?)", (periods,))
    case.conn.execute("INSERT INTO WorkbenchShiftProfiles(profile_id,name,anchor_date,cycle_days) "
                      "VALUES ('SP','Day shift','2026-10-12',1)")
    case.conn.execute("INSERT INTO WorkbenchShiftPatternDays(profile_id,day_offset,is_rest,periods_json) VALUES ('SP',0,0,?)",
                      (periods,))
    case.conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,shift_profile_id,skills_declared) VALUES ('O1','SP',0)")
    case.conn.execute("INSERT INTO Materials(material_id,name) VALUES ('MAT','Steel')")
    case.conn.execute("INSERT INTO BatchMaterials(id,batch_id,material_id,required_qty) VALUES (1,'B1','MAT',1)")
    case.conn.execute("INSERT INTO BatchMaterialArrivals(requirement_id,arrival_date,quantity) VALUES (1,'2026-10-12',1)")
    case.conn.execute("INSERT INTO BatchMaterialReviews(requirement_id,batch_quantity) VALUES (1,1)")
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('EXT','Heat treatment','external')")
    case.conn.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id) "
                      "VALUES ('EG','P1',2,2,'merged',1.5,'S1')")
    case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days,"
                      "ext_group_id) VALUES ('P1',2,'EXT','Heat treatment','external','S1',2,'EG')")
    case.operation(seq=2, op_type_id="EXT", op_type_name="Heat treatment", source="external", supplier_id="S1",
                   machine_id=None, operator_id=None, ext_days=2)
    case.conn.commit()
    stored = json.loads(content_text(ProductionFactsCapture(case.conn).scoped_archive([case.ref("batch", "B1")])))
    return stored


def test_saved_archive_admits_every_consumed_checked_cell_at_its_storage_boundary(candidate_case):
    # 读者把这些格子当表的 CHECK 值域直接用：停机状态坏了会被当成没停机，算出 8 小时可用产能；
    # 设备、人员、供应商状态与普通/急件许可坏了，产能与可排结论跟着静默改变；技能等级坏了查业务序时裸 KeyError；
    # 有效标志坏了永久编号被当成失效，合并方式坏了改用本序周期，轮换日偏移坏了建日历引擎就出错；
    # 核对时的批次数量写成 1.0 会被当成与批次数量 1 相等，按已核对放行。
    # JSON 副本不带 CHECK，坏一格整份归档在准入处按损坏拒收；同一值域里的每个合法值照收。
    stored = _saved_archive_with_every_checked_table(candidate_case)
    validate_production_archive(stored)
    enum, flag, bit = ("unexpected", None, 1), ("Y", None, True), ("1", None, True, 2, 1.0)
    cells = {
        ("WorkbenchEntityRefs", "active"): (FLAG_VALUES, bit),
        ("WorkbenchPlanSourceRefs", "kind"): (PLAN_SOURCE_KIND_VALUES, ("batch", None, 1)),
        ("WorkbenchPlanSourceRefs", "active"): (FLAG_VALUES, bit),
        ("WorkbenchOperatorProfiles", "skills_declared"): (FLAG_VALUES, bit),
        ("WorkbenchShiftProfiles", "cycle_days"): ((1, SHIFT_CYCLE_DAYS_MAX), (0, SHIFT_CYCLE_DAYS_MAX + 1, "1", True, None)),
        ("WorkbenchShiftPatternDays", "day_offset"): ((0, SHIFT_DAY_OFFSET_MAX), (-1, SHIFT_DAY_OFFSET_MAX + 1, 0.0, [0])),
        ("WorkbenchShiftPatternDays", "is_rest"): (FLAG_VALUES, bit),
        ("BatchExternalContexts", "merge_mode"): (MERGE_MODE_VALUES + (None,), ("Merged", 1)),
        ("BatchMaterialArrivals", "quantity"): ((0.25, 2**53 - 1), (0, -1, "1", None, 2**53, float("inf"))),
        ("BatchMaterialReviews", "batch_quantity"): ((1, 2**53 - 1), (None, 0, -1, 2**53, 1.0, "1", True)),
        ("MachineDowntimes", "status"): (MACHINE_DOWNTIME_STATUS_VALUES, enum),
        ("Machines", "status"): (MACHINE_STATUS_VALUES, enum),
        ("Operators", "status"): (OPERATOR_STATUS_VALUES, enum),
        ("OperatorMachine", "skill_level"): (SKILL_LEVEL_VALUES, enum),
        ("OperatorMachine", "is_primary"): (YESNO_VALUES, flag),
        ("OpTypes", "category"): (OP_TYPE_CATEGORY_VALUES, enum),
        ("Suppliers", "status"): (SUPPLIER_STATUS_VALUES, enum),
        ("Suppliers", "default_days"): ((0.5, 36500), (0, None, "2")),
        ("WorkCalendar", "allow_normal"): (YESNO_VALUES, flag),
        ("WorkCalendar", "allow_urgent"): (YESNO_VALUES, flag),
        ("OperatorCalendar", "allow_normal"): (YESNO_VALUES, flag),
        ("OperatorCalendar", "allow_urgent"): (YESNO_VALUES, flag),
        ("WorkbenchShiftProfiles", "status"): (SHIFT_PROFILE_STATUS_VALUES, enum),
        ("Batches", "quantity"): ((1, 2**53 - 1), (0, -1, 2**53, 1.0, "1", True, None)),
        ("Batches", "priority"): (BATCH_PRIORITY_VALUES, enum),
        ("Batches", "ready_status"): (READY_STATUS_VALUES, enum),
        ("Batches", "status"): (BATCH_STATUS_VALUES, enum),
        ("BatchOperations", "source"): (SOURCE_TYPE_VALUES, enum),
        ("BatchOperations", "status"): (BATCH_OPERATION_STATUS_VALUES, enum),
        ("BatchMaterials", "ready_status"): (READY_STATUS_VALUES, enum),
    }
    for (table, column), (legal, corrupt) in cells.items():
        index = stored["columns"][table].index(column)
        assert stored["tables"][table], table
        for value in legal:
            kept = deepcopy(stored)
            kept["tables"][table][0][index] = value
            validate_production_archive(kept)
        for value in corrupt:
            broken = deepcopy(stored)
            broken["tables"][table][0][index] = value
            with pytest.raises(ValueError, match=CORRUPT_ARCHIVE):
                validate_production_archive(broken)
            with pytest.raises(WorkbenchCommandRejected) as rejected:
                admit_generation_facts({"facts": broken, "execution": []})
            assert (rejected.value.code, rejected.value.status) == ("candidate_artifact_invalid", 500)


def _distinct_elsewhere(row, columns, key, others):
    """A copy of ``row`` sharing only ``key``: every other declared key column gets a value no row has."""
    copy = list(row)
    for column in {column for other in others for column in other} - set(key):
        index = columns.index(column)
        value = copy[index]
        copy[index] = value + 10**9 if type(value) is int else value + "-copy" if type(value) is str else value
    return copy


def test_saved_archive_admits_every_declared_unique_key_at_its_storage_boundary(candidate_case):
    # JSON 副本丢了表的 PRIMARY KEY 与 UNIQUE，读者按键建索引时重复行会被静默取最后一行。
    # 每张归档表按声明（schema_declaration.declared_tables）核每个无条件唯一列组：只共用这一组的副本整份拒收；
    # 列组里有 NULL 时与 SQLite 一样不算重复。
    stored = _saved_archive_with_every_checked_table(candidate_case)
    declared = declared_tables(load_schema_sql())
    checked = []
    for table, rows in stored["tables"].items():
        if not rows:
            continue
        columns, keys = stored["columns"][table], declared[table].unique_keys
        for key in keys:
            copy = _distinct_elsewhere(rows[0], columns, key, keys)
            duplicated = deepcopy(stored)
            duplicated["tables"][table].append(copy)
            if any(copy[columns.index(column)] is None for column in key):
                validate_production_archive(duplicated)
                checked.append((table, key, "null"))
                continue
            with pytest.raises(ValueError, match=CORRUPT_ARCHIVE):
                validate_production_archive(duplicated)
            with pytest.raises(WorkbenchCommandRejected) as rejected:
                admit_generation_facts({"facts": duplicated, "execution": []})
            assert (rejected.value.code, rejected.value.status) == ("candidate_artifact_invalid", 500)
            checked.append((table, key, "duplicate"))
    assert ("WorkbenchShiftPatternDays", ("profile_id", "day_offset"), "duplicate") in checked
    assert ("WorkbenchPlanSourceRefs", ("ref",), "duplicate") in checked
    assert ("BatchOperations", ("batch_id", "seq", "piece_id"), "null") in checked
    # 部分唯一索引（有效永久编号的 (kind, entity_key) 这类）不在声明的无条件列组里，由各自的读者核对。
    assert ("kind", "entity_key") not in declared["WorkbenchEntityRefs"].unique_keys


def test_streaming_releases_person_groups_and_derived_facts_keeps_shared_shift(monkeypatch):
    saved = archive()
    tables = saved
    second_ref = "c" * 48
    tables["WorkbenchEntityRefs"].append({"kind": "operator", "ref": second_ref, "entity_key": "O2", "active": 1})
    tables["Operators"].append({"operator_id": "O2", "name": "乙", "status": "active"})
    tables["WorkbenchOperatorProfiles"] = [{"operator_id": who, "shift_profile_id": "S"} for who in ("O1", "O2")]
    tables["WorkbenchShiftProfiles"] = [{"profile_id": "S", "anchor_date": "2026-10-12", "cycle_days": 1, "status": "active"}]
    tables["WorkbenchShiftPatternDays"] = [{"profile_id": "S", "day_offset": 0, "is_rest": 0,
                                           "periods_json": '[{"start":"09:00","end":"17:00","day_offset":0}]'}]
    factory = ArchivedCalendar(saved)
    engine = factory.engine
    global_key = "2026-10-12"
    global_policy = engine._policy_for_date(global_key)
    shifts = type(engine.operator_shift_calendar)
    reads, build_pattern = [], shifts._pattern
    monkeypatch.setattr(shifts, "_pattern", lambda self, *args: (reads.append(args[:2]), build_pattern(self, *args))[1])
    stream = factory.iter_resources([RESOURCES[1], {"kind": "operator", "ref": second_ref, "saved_id": "O2"}],
                                    "2026-10-12T08:00:00", "2026-10-14T17:00:00")
    _, first = next(stream)
    assert first["state"] == "available" and "O1" in engine._policy_operator_keys
    engine.working_hours_between(datetime.fromisoformat("2026-10-12T08:00:00"),
                                 datetime.fromisoformat("2026-10-13T17:00:00"), priority="normal", operator_id="O1")
    _, second = next(stream)
    assert second["available_hours"] == first["available_hours"]
    assert "O1" not in engine._policy_operator_keys and "O1" not in engine._segment_cache
    assert "O1" not in engine.operator_shift_calendar._profiles
    assert all(key[0] != "O1" for key in engine._policy_cache)
    assert all(key[0] != "O1" for key in engine._working_hours_prefix)
    assert "O2" not in engine._policy_operator_keys and len(factory._shift_days) == 3
    assert engine._public_calendar_rows and len(reads) == 1
    assert engine.operator_shift_calendar._patterns
    assert list(stream) == []
    assert not engine._policy_operator_keys
    assert not engine._policy_cache
    assert engine._public_policy_cache[global_key] is global_policy
    assert engine._policy_for_date("2026-10-12", "O1").hours == pytest.approx(22 / 3)


def test_unavailable_global_and_shift_days_are_projected_once_across_operators(monkeypatch):
    from core.services.workbench.facts import archived_calendar

    second_ref = "c" * 48
    operators = [RESOURCES[1], {"kind": "operator", "ref": second_ref, "saved_id": "O2"}]

    def two_operator_archive():
        saved = archive()
        saved["WorkbenchEntityRefs"].append(
            {"kind": "operator", "ref": second_ref, "entity_key": "O2", "active": 1}
        )
        saved["Operators"].append({"operator_id": "O2", "name": "乙", "status": "active"})
        return saved

    calls = []
    real_projection = archived_calendar.policy_projection

    def counted_projection(engine, first_day, last_day, start, end, operator_id=None):
        calls.append((start, end, operator_id))
        return real_projection(engine, first_day, last_day, start, end, operator_id)

    monkeypatch.setattr(archived_calendar, "policy_projection", counted_projection)

    broken_global = two_operator_archive()
    broken_global["WorkCalendar"] = [day("2026-10-12", end=None)]
    broken_res = project(broken_global, "2026-10-12T00:00:00", "2026-10-13T00:00:00", resources=operators)
    assert len(calls) == 1
    assert broken_res[OPERATOR]["state"] == "unavailable"
    assert broken_res[OPERATOR]["basis"] == "personal_or_operator_shift_calendar"
    assert broken_res[OPERATOR]["issues"] == [{"code": "calendar_invalid", "message": broken_res[OPERATOR]["issues"][0]["message"], "policy_date": "2026-10-12"}]
    assert broken_res[second_ref]["basis"] == broken_res[OPERATOR]["basis"]
    assert broken_res[second_ref]["issues"] == broken_res[OPERATOR]["issues"]

    calls.clear()
    broken_shift = two_operator_archive()
    broken_shift["WorkbenchOperatorProfiles"] = [
        {"operator_id": who, "shift_profile_id": "S"} for who in ("O1", "O2")
    ]
    broken_shift["WorkbenchShiftProfiles"] = [
        {"profile_id": "S", "anchor_date": "2026-10-12", "cycle_days": 1, "status": "inactive"}
    ]
    broken_shift["WorkbenchShiftPatternDays"] = [
        {"profile_id": "S", "day_offset": 0, "is_rest": 0,
         "periods_json": '[{"start":"09:00","end":"17:00","day_offset":0}]'}
    ]
    shift_res = project(broken_shift, "2026-10-12T00:00:00", "2026-10-13T00:00:00", resources=operators)
    assert [who for _, _, who in calls] == ["O1"]
    assert shift_res[OPERATOR]["state"] == "unavailable"
    assert shift_res[OPERATOR]["basis"] == "personal_or_operator_shift_calendar"
    assert shift_res[OPERATOR]["issues"][0]["code"] == "calendar_invalid"
    assert shift_res[second_ref]["basis"] == shift_res[OPERATOR]["basis"]
    assert shift_res[second_ref]["issues"] == shift_res[OPERATOR]["issues"]
