"""Actual auto assignment, overnight calendar, external lead time and fixed seeds."""

import json
from datetime import datetime

import pytest

from core.services.workbench.resource.downtimes import WorkbenchDowntimeService
from core.services.workbench.run.preflight import PreflightService
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.piece_adoption_support import split
from tests.workbench.run_candidate_adoption_support import (
    INTENT,
    KEY,
    assert_retained,
    candidate,
    preview,
    service,
    snapshot,
)
from tests.workbench.run_candidate_adoption_support import candidate_case as _case  # noqa: F401
from tests.workbench.run_candidate_support import compute, corrupt_update
from tests.workbench.run_jobs_support import service as run_service


@pytest.mark.parametrize("mode", ["auto_assign", "multiday", "external", "locked"])
def test_real_resource_calendar_and_protected_seed_contracts(candidate_case, mode):
    case = candidate_case
    if mode == "auto_assign":
        case.conn.execute("UPDATE BatchOperations SET machine_id=NULL,operator_id=NULL")
    elif mode == "multiday":
        case.conn.execute("UPDATE BatchOperations SET unit_hours=5")
    elif mode == "external":
        case.conn.execute("UPDATE OpTypes SET category='both' WHERE op_type_id='T1'")
        case.conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('S1','Supplier','T1')")
        case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
                          "VALUES ('P1',1,'T1','Turning','external','S1',2)")
        case.conn.execute("UPDATE BatchOperations SET source='external',supplier_id='S1',ext_days=2,machine_id=NULL,operator_id=NULL")
    elif mode == "locked":
        case.operation(seq=2)
        case.plan(1, [case.op_id], end="2026-09-09T08:45:00")
        case.conn.execute("UPDATE Schedule SET lock_status='locked'")
    case.conn.commit()
    ref = candidate(case)
    token = preview(case, ref)
    before = snapshot(case.conn)
    result = service(case.conn).adopt(ref, token, KEY, INTENT)
    version = result["data"]["official_plan"]["version"]
    row = case.conn.execute("SELECT * FROM Schedule WHERE version=? AND op_id=?", (version, case.op_id)).fetchone()
    if mode == "external":
        assert row["machine_id"] is None and row["operator_id"] is None
    elif mode == "auto_assign":
        assert (row["machine_id"], row["operator_id"]) == ("M1", "O1")
        assert case.conn.execute("SELECT machine_id FROM BatchOperations WHERE id=?", (case.op_id,)).fetchone()[0] is None
    elif mode == "locked":
        assert row["lock_status"] == "locked" and row["start_time"] == "2026-09-09 08:00:00"
    assert_retained(before, snapshot(case.conn))


def test_started_work_needing_reconciliation_is_not_admitted_by_upstream(candidate_case):
    case = candidate_case
    case.operation(seq=2)
    case.plan(1, [case.op_id])
    case.event(case.op_id, "start")
    before = snapshot(case.conn)
    data, _ = PreflightService(case.conn).evaluate(case.settings())
    assert "execution_review_required" in {item["code"] for item in data["blockers"]}
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("unit,efficiency", [(0.001, 1.0), (0.25, 0.95)])
def test_piece_real_computation_and_adoption_preserve_fractional_seconds(candidate_case, unit, efficiency):
    case = candidate_case
    split(case, common=False, unit=unit, quantity=1)
    case.conn.execute("INSERT INTO WorkCalendar(date,day_type,shift_hours,shift_start,efficiency,allow_normal,allow_urgent) "
                      "VALUES ('2026-09-09','workday',8,'08:00',?,'yes','yes')", (efficiency,))
    case.conn.commit()
    ref = candidate(case)
    expected = {row["op_id"]: (datetime.fromisoformat(row["start_time"]), datetime.fromisoformat(row["end_time"]))
                for row in (json.loads(item[0]) for item in case.conn.execute(
                    "SELECT payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (ref,)))}
    assert any(end.microsecond for _, end in expected.values())
    result = service(case.conn).adopt(ref, preview(case, ref), KEY, INTENT)
    stored = {row[0]: (datetime.fromisoformat(row[1]), datetime.fromisoformat(row[2]))
              for row in case.conn.execute("SELECT op_id,start_time,end_time FROM Schedule WHERE version=?",
                                           (result["data"]["official_plan"]["version"],))}
    assert stored == expected


def locked_plan(case):
    """正式计划里留一道冻结期内锁定的安排；返回按序号排产、取首个候选的函数。"""
    def run(number, settings=None):
        accepted = case.accept(key="locked-calendar-run-" + str(number).zfill(5), settings=settings)
        computed = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
        return computed["candidates"][0]["candidate_ref"]

    def adopt(number, ref):
        return service(case.conn).adopt(ref, preview(case, ref), "locked-calendar-adopt-" + str(number).zfill(5), INTENT)

    adopt(1, run(1))
    case.operation(seq=2)
    case.conn.commit()
    case.config(freeze_window_enabled="yes", freeze_window_days=3)
    adopt(2, run(2))
    case.config(freeze_window_enabled="no")
    # 不重排时段只管那一次排产，采用后按未锁定落库；这里模拟正式计划里继承下来的锁定。
    assert case.conn.execute("SELECT lock_status FROM Schedule WHERE version=2 AND op_id=?", (case.op_id,)).fetchone()[0] == "unlocked"
    case.conn.execute("UPDATE Schedule SET lock_status='locked' WHERE version=2 AND op_id=?", (case.op_id,))
    case.conn.commit()
    return run


def add_locked_downtime(case):
    downtime = WorkbenchDowntimeService(case.conn)
    machine_ref = case.ref("machine", "M1")
    state = downtime.snapshot(machine_ref)
    case.conn.execute("BEGIN IMMEDIATE")
    downtime.apply(machine_ref, "create", {"start_time": "2026-09-09 08:00", "end_time": "2026-09-09 09:00",
                                            "reason_code": "maintenance", "reason_detail": None}, state)
    case.conn.commit()


@pytest.mark.parametrize("run_start", ["2026-09-09", "2026-09-10"])
def test_window_boundary_cannot_hide_downtime_of_legitimately_locked_work(candidate_case, run_start):
    case = candidate_case
    run = locked_plan(case)
    add_locked_downtime(case)
    assert case.conn.execute("SELECT count(*) FROM OperationExecutionEvents").fetchone()[0] == 0
    assert case.conn.execute("SELECT count(*) FROM WorkbenchExecutionLegacyFacts").fetchone()[0] == 0
    # 锁定安排排产时原样保留、不会避开停机，采用时却按停机复核：排产检查先指出冲突（窗口从次日开始也一样），
    # 不再算出一批都采用不了的候选。
    settings = case.settings(start_date=run_start)
    before = snapshot(case.conn)
    checked, _ = PreflightService(case.conn).evaluate(settings)
    conflict = next(row for row in checked["blockers"] if row["code"] == "locked_downtime_conflict")
    assert conflict["operation_ref"] == next(row["operation_ref"] for row in checked["tasks"] if row["sequence"] == 1)
    assert "设备 M1" in conflict["message"] and "2026-09-09 08:00:00 至 2026-09-09 09:00:00" in conflict["message"]
    assert snapshot(case.conn) == before
    reasons = run_service(case.conn).preview(case.preflight(settings))["write_context"]["blocked_reasons"]
    assert "locked_downtime_conflict" in {row["code"] for row in reasons}
    case.conn.execute("UPDATE Schedule SET lock_status='unlocked' WHERE op_id=?", (case.op_id,))
    case.conn.commit()
    ref = run(3, settings)
    assert service(case.conn).preview(ref)["validation"]["can_adopt"] is True


@pytest.mark.parametrize("gap", ["preflight_missed", "after_run"])
def test_adoption_still_rejects_locked_work_overlapping_downtime(candidate_case, monkeypatch, gap):
    from core.models.workbench_command import WorkbenchCommandRejected
    from core.services.workbench.run import preflight

    case = candidate_case
    run = locked_plan(case)
    if gap == "preflight_missed":
        # 排产检查万一没拦住，采用时仍按锁定安排的设备停机复核，不能采用。
        monkeypatch.setattr(preflight, "held_arrangement_reasons", lambda *args: ([], [], {}))
        add_locked_downtime(case)
        ref = run(3)
        before = snapshot(case.conn)
        checked = service(case.conn).preview(ref)
        assert checked["validation"]["can_adopt"] is False
        assert checked["validation"]["issues"][0]["code"] == "candidate_calendar_duration_conflict"
        assert snapshot(case.conn) == before
    else:
        # 排产算完之后才登记的停机：采用时发现排产所用事实已变，同样不采用。
        ref = run(3)
        add_locked_downtime(case)
        with pytest.raises(WorkbenchCommandRejected) as stale:
            service(case.conn).preview(ref)
        assert stale.value.code == "snapshot_stale"


def first_candidate(case, key, settings):
    accepted = case.accept(key=key, settings=settings)
    return WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])["candidates"][0]["candidate_ref"]


def held_plan(case, hold):
    """B1 的原安排在正式计划里锁定，或落在不重排时段里（交付设置「锁定近期排程」3 天推算）；另加一批用别的设备人员、照常要排的 B2。"""
    case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M2','Second lathe','T1')")
    case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O2','Second operator')")
    case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O2','M2')")
    case.conn.commit()
    _run, refs = compute(case)
    service(case.conn).adopt(refs[0], preview(case, refs[0]), "held-plan-adopt-000001", INTENT)
    if hold == "locked":
        case.conn.execute("UPDATE Schedule SET lock_status='locked' WHERE op_id=?", (case.op_id,))
    else:
        case.config(freeze_window_enabled="yes", freeze_window_days=3)
    case.batch("B2")
    case.operation(batch="B2", seq=1, machine_id="M2", operator_id="O2")
    case.conn.commit()


def material_arrives_later(case):
    """B1 登记物料需求：原安排之后（仍在排产日期范围内）的 2026-09-10 才到齐。"""
    from core.infrastructure.transaction import TransactionManager
    from core.services.workbench.batch.materials import WorkbenchBatchMaterialService

    case.conn.execute("INSERT INTO Materials(material_id,name,unit) VALUES ('STEEL','钢材','件')")
    case.conn.commit()
    operation_ref = case.conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? "
                                      "AND active=1", (str(case.op_id),)).fetchone()[0]
    with TransactionManager(case.conn).transaction():
        WorkbenchBatchMaterialService(case.conn).apply(case.ref("batch", "B1"), {"removed_keys": [], "rows": [{
            "row_key": None, "material_ref": case.ref("material", "STEEL"), "required_quantity": 3, "available_quantity": 0,
            "operation_ref": operation_ref, "arrivals": [{"arrival_date": "2026-09-10", "quantity": 3}]}]})


_REST = "'holiday','08:00','16:00',0,1.0,'no','no','[]')"
_CALENDAR_COLUMNS = "date,day_type,shift_start,shift_end,shift_hours,efficiency,allow_normal,allow_urgent,periods_json)"
HELD_CHANGES = {
    "machine_inactive": (["UPDATE Machines SET status='inactive' WHERE machine_id='M1'"],
                         "locked_resource_invalid", "设备已停用", "candidate_resource_invalid"),
    "authorization_removed": (["DELETE FROM OperatorMachine WHERE operator_id='O1' AND machine_id='M1'"],
                              "locked_resource_invalid", "没有这台设备的操作授权", "candidate_resource_invalid"),
    "material_late": (material_arrives_later, "locked_material_late", "本序物料要到 2026-09-10 才到齐", "candidate_before_material"),
    "ready_date": (["UPDATE Batches SET ready_date='2026-09-10' WHERE batch_id='B1'"],
                   "locked_before_ready_date", "齐套日期是 2026-09-10", "candidate_before_ready_date"),
    "operator_leave": (["INSERT INTO OperatorCalendar(operator_id," + _CALENDAR_COLUMNS + " VALUES ('O1','2026-09-09'," + _REST],
                       "locked_calendar_conflict", "休息或请假", "candidate_calendar_duration_conflict"),
    "factory_holiday": (["INSERT INTO WorkCalendar(" + _CALENDAR_COLUMNS + " VALUES ('2026-09-09'," + _REST],
                        "locked_calendar_conflict", "休息或请假", "candidate_calendar_duration_conflict"),
    "downtime": (["INSERT INTO MachineDowntimes(machine_id,start_time,end_time,status) "
                  "VALUES ('M1','2026-09-09 08:00:00','2026-09-09 12:00:00','active')"],
                 "locked_downtime_conflict", "2026-09-09 08:00:00 至 2026-09-09 12:00:00 有停机", "candidate_calendar_duration_conflict"),
    "now_external": (["UPDATE OpTypes SET category='both' WHERE op_type_id='T1'",
                      "INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('S1','供应商','T1')",
                      "INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
                      "VALUES ('P1',1,'T1','Turning','external','S1',2)",
                      "UPDATE BatchOperations SET source='external',supplier_id='S1',ext_days=2,machine_id=NULL,operator_id=NULL "
                      "WHERE batch_id='B1'"],
                     "locked_external_resource_conflict", "现在是外协", "candidate_external_resource_conflict"),
}


@pytest.mark.parametrize("hold", ["locked", "frozen"])
@pytest.mark.parametrize("change", sorted(HELD_CHANGES))
def test_held_arrangement_no_longer_valid_is_named_before_run_and_still_refused_at_adoption(
        candidate_case, monkeypatch, hold, change):
    """锁定或不重排时段保留的原安排，排产原样留下、采用却按现在的资料逐条复核：
    设备人员停用或取消授权、物料或齐套日期改晚、请假或改休息、停机、改成外协，排产检查先按同一口径指出这道工序和出路；
    锁定的提示工作台里不能解锁、请维护人员解除；时段里的提示到排产检查把不重排时段改短或不设。"""
    from core.services.workbench.run import preflight

    case = candidate_case
    held_plan(case, hold)
    statements, blocker_code, detail, adoption_code = HELD_CHANGES[change]
    if callable(statements):
        statements(case)
    else:
        for sql in statements:
            case.conn.execute(sql)
    case.conn.commit()
    settings = case.settings("B1", "B2")
    before = snapshot(case.conn)
    checked, _ = PreflightService(case.conn).evaluate(settings)
    assert snapshot(case.conn) == before
    blocker = next(row for row in checked["blockers"] if row["code"] == blocker_code)
    assert blocker["operation_ref"] == next(row["operation_ref"] for row in checked["tasks"] if row["batch_id"] == "B1")
    assert detail in blocker["message"]
    if hold == "locked":
        assert "工作台里不能解锁" in blocker["message"] and "不重排时段" not in blocker["message"]
    else:
        assert "因不重排时段（2026-09-09 00:00 至 2026-09-12 00:00）保持原安排" in blocker["message"] and "解锁" not in blocker["message"]
        assert "到排产检查把不重排时段改短或不设" in blocker["message"]
    # 排产检查万一没拦住，采用复核照旧兜底，拒绝原因与检查指出的是同一处。
    monkeypatch.setattr(preflight, "held_arrangement_reasons", lambda *args: ([], [], {}))
    issues = service(case.conn).preview(first_candidate(case, "held-plan-run-000002", settings))["validation"]["issues"]
    assert [row["code"] for row in issues] == [adoption_code]


def test_frozen_batch_whose_earlier_operation_is_unreported_is_rescheduled_with_a_notice(candidate_case):
    """日常滚动重排：前道原安排在排产起日之前、还没报工，后道原安排落在不重排时段里。
    整批前后顺序保不住，这批这次不冻结、照常重排并事先提醒，不再整次失败；文案不再说“未使用冻结窗口”却直接失败。"""
    case = candidate_case
    case.conn.execute("UPDATE BatchOperations SET unit_hours=?", (8 / 3,))
    second = case.operation(seq=2, unit_hours=8 / 3)
    case.conn.commit()
    _run, refs = compute(case, case.settings(start_date="2026-09-08"))
    service(case.conn).adopt(refs[0], preview(case, refs[0]), "held-prefix-adopt-0001", INTENT)
    assert [row[0][:10] for row in case.conn.execute("SELECT start_time FROM Schedule ORDER BY op_id")] == ["2026-09-08", "2026-09-09"]
    case.config(freeze_window_enabled="yes", freeze_window_days=1)
    settings = case.settings(start_date="2026-09-09")
    checked, _ = PreflightService(case.conn).evaluate(settings)
    assert checked["blockers"] == []
    notice = next(row for row in checked["warnings"] if row["code"] == "freeze_window_skipped")
    assert notice["batch_id"] == "B1" and "这次这批不保留原安排" in notice["message"]
    ref = first_candidate(case, "held-prefix-run-000002", settings)
    tasks = [json.loads(row[0]) for row in case.conn.execute(
        "SELECT payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (ref,))]
    assert {row["op_id"] for row in tasks} == {case.op_id, second} and not any(row["locked"] for row in tasks)
    assert service(case.conn).preview(ref)["validation"]["can_adopt"] is True


def test_unreadable_frozen_window_is_a_preflight_blocker_not_a_silent_skip(candidate_case):
    """窗口里读到的原安排本身坏了（结束早于开始）仍按严格口径拒绝：排产检查先拦下，请维护人员核对，不当作“不冻结”放过去。"""
    case = candidate_case
    _run, refs = compute(case)
    service(case.conn).adopt(refs[0], preview(case, refs[0]), "held-broken-adopt-0001", INTENT)
    case.config(freeze_window_enabled="yes", freeze_window_days=3)
    corrupt_update(case.conn, "Schedule", "UPDATE Schedule SET end_time='2026-09-09 07:00:00' WHERE op_id=?", (case.op_id,))
    checked, _ = PreflightService(case.conn).evaluate(case.settings())
    blocker = next(row for row in checked["blockers"] if row["code"] == "freeze_window_unavailable")
    assert "联系维护人员" in blocker["message"] and "未使用" not in blocker["message"]


@pytest.mark.parametrize("column", ["shift_start", "shift_hours", "efficiency"])
def test_legacy_blank_calendar_column_is_read_like_the_engine_and_adoptable(candidate_case, column):
    """旧库升级加列没回填：排产当天的日历行班次开始、工时或效率空着，日历引擎和日历页都按默认值解释
    （08:00 开始、按起止算工时、效率 1）。排产不再以“读不出来”整次失败，排出的方案能采用。"""
    case = candidate_case
    row = dict(date="2026-09-09", day_type="workday", shift_start="08:00", shift_end="16:00", shift_hours=8, efficiency=1.0,
               allow_normal="yes", allow_urgent="yes")
    row[column] = None
    case.conn.execute("INSERT INTO WorkCalendar(date,day_type,shift_start,shift_end,shift_hours,efficiency,allow_normal,allow_urgent) "
                      "VALUES (:date,:day_type,:shift_start,:shift_end,:shift_hours,:efficiency,:allow_normal,:allow_urgent)", row)
    case.conn.commit()
    ref = first_candidate(case, "legacy-calendar-run-" + column, case.settings())
    tasks = [json.loads(item[0]) for item in case.conn.execute(
        "SELECT payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (ref,))]
    assert [(item["start_time"], item["end_time"]) for item in tasks] == [("2026-09-09T08:00:00", "2026-09-09T08:45:00")]
    assert service(case.conn).preview(ref)["validation"]["can_adopt"] is True


_EXTERNAL_B1 = ["UPDATE OpTypes SET category='both' WHERE op_type_id='T1'",
                "INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('S1','供应商','T1')",
                "INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
                "VALUES ('P1',1,'T1','Turning','external','S1',2)",
                "UPDATE BatchOperations SET source='external',supplier_id='S1',ext_days=2,machine_id=NULL,operator_id=NULL "
                "WHERE batch_id='B1'"]
HELD_DURATIONS = {
    # 原安排 2 天外协，之后把周期改成 3 天。
    "external_days": (_EXTERNAL_B1, "UPDATE BatchOperations SET ext_days=3 WHERE batch_id='B1'",
                      "现在的周期是 3 天", "candidate_external_duration_conflict"),
    # 分件批次按每件数量算工时：单件工时从 0.25 改成 0.5，原安排的完工时间对不上。
    "piece_hours": (lambda case: split(case, common=False, unit=0.25, quantity=1),
                    "UPDATE BatchOperations SET unit_hours=0.5 WHERE batch_id='B1'", "开工、完工时间和这段安排对不上", None),
}


@pytest.mark.parametrize("hold", ["locked", "frozen"])
@pytest.mark.parametrize("kind", sorted(HELD_DURATIONS))
def test_held_external_cycle_and_piece_hours_are_checked_before_run_like_adoption(candidate_case, monkeypatch, hold, kind):
    """保留的外协安排按现在的外协周期、分件批次按每件数量复核：排产检查先指出，采用照旧拒绝同一处。"""
    from core.models.workbench_piece_adoption import PieceAdoptionBlocked
    from core.services.workbench.run import preflight

    case = candidate_case
    setup, change, detail, adoption_code = HELD_DURATIONS[kind]
    if callable(setup):
        setup(case)
    else:
        for sql in setup:
            case.conn.execute(sql)
    case.conn.commit()
    held_plan(case, hold)
    case.conn.execute(change)
    case.conn.commit()
    settings = case.settings("B1", "B2")
    checked, _ = PreflightService(case.conn).evaluate(settings)
    assert any(detail in row["message"] for row in checked["blockers"]), checked["blockers"]
    monkeypatch.setattr(preflight, "held_arrangement_reasons", lambda *args: ([], [], {}))
    if adoption_code is None:
        # 分件运行在计算收尾就按分件采用口径逐条复核，同一处在那里被拒。
        with pytest.raises(PieceAdoptionBlocked, match="工序时长"):
            service(case.conn).preview(first_candidate(case, "held-duration-run-0002", settings))
        return
    ref = first_candidate(case, "held-duration-run-0002", settings)
    assert [row["code"] for row in service(case.conn).preview(ref)["validation"]["issues"]] == [adoption_code]


@pytest.mark.parametrize("hold", ["locked", "frozen"])
@pytest.mark.parametrize("change,detail,compute_message", [
    ("INSERT INTO WorkCalendar(" + _CALENDAR_COLUMNS + " VALUES ('2026-09-09'," + _REST,
     "最早要到 2026-09-10 08:00:00", "零工时工序的时间不符合实际班表"),
    ("UPDATE BatchOperations SET unit_hours=0.25 WHERE batch_id='B1'", "现在有工时，不再是零工时工序", "不是零工时工序"),
])
def test_held_zero_duration_arrangement_is_checked_before_run(candidate_case, monkeypatch, hold, change, detail, compute_message):
    """保留的零工时安排（开工即完工）改休息或改成有工时后不成立，排产计算会整次失败；排产检查先指出这道工序。"""
    from core.models.workbench_run_compute import CandidateRunInputError
    from core.services.workbench.run import preflight
    from tests.workbench.ea_zero_duration_support import adoption_service

    case = candidate_case
    case.conn.execute("UPDATE BatchOperations SET setup_hours=0,unit_hours=0 WHERE batch_id='B1'")
    case.conn.commit()
    _run, refs = compute(case)
    adopter = adoption_service(case.conn)
    adopter.adopt(refs[0], adopter.preview(refs[0])["write_context"]["write_token"], "held-point-adopt-0001", INTENT)
    if hold == "locked":
        case.conn.execute("UPDATE Schedule SET lock_status='locked' WHERE op_id=?", (case.op_id,))
    else:
        case.config(freeze_window_enabled="yes", freeze_window_days=3)
    case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M2','Second lathe','T1')")
    case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O2','Second operator')")
    case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O2','M2')")
    case.batch("B2")
    case.operation(batch="B2", seq=1, machine_id="M2", operator_id="O2")
    case.conn.execute(change)
    case.conn.commit()
    settings = case.settings("B1", "B2")
    checked, _ = PreflightService(case.conn).evaluate(settings)
    blocker = next(row for row in checked["blockers"] if row["code"] == "locked_point_conflict")
    assert detail in blocker["message"] and "零工时安排" in blocker["message"]
    monkeypatch.setattr(preflight, "held_arrangement_reasons", lambda *args: ([], [], {}))
    with pytest.raises(CandidateRunInputError, match=compute_message):
        first_candidate(case, "held-point-run-000002", settings)


@pytest.mark.parametrize("hold", ["locked", "frozen"])
def test_every_selected_operation_held_is_a_preflight_blocker(candidate_case, hold):
    """选中的工序全都原样保留时，排产计算没有可排的工序会直接停下；排产检查先说清楚，计算的提示也不再夹英文。"""
    from core.models.workbench_run_compute import CandidateRunInputError
    from core.services.workbench.run import preflight

    case = candidate_case
    _run, refs = compute(case)
    service(case.conn).adopt(refs[0], preview(case, refs[0]), "held-all-adopt-000001", INTENT)
    if hold == "locked":
        case.conn.execute("UPDATE Schedule SET lock_status='locked' WHERE op_id=?", (case.op_id,))
    else:
        case.config(freeze_window_enabled="yes", freeze_window_days=3)
    case.conn.commit()
    checked, _ = PreflightService(case.conn).evaluate(case.settings())
    blocker = next(row for row in checked["blockers"] if row["code"] == "all_tasks_held")
    assert ("解除不需要的锁定" in blocker["message"]) is (hold == "locked")
    original = preflight.held_arrangement_reasons
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(preflight, "held_arrangement_reasons",
                      lambda *args: ([row for row in original(*args)[0] if row["code"] != "all_tasks_held"], [], {}))
        with pytest.raises(CandidateRunInputError) as raised:
            first_candidate(case, "held-all-run-0000002", case.settings())
    assert "本次未执行排产计算" in str(raised.value) and "computation" not in str(raised.value)
