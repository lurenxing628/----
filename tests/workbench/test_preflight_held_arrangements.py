"""排产检查核对不重排时段里要原样保留的原安排：资格、齐套、到料或日历对不上时，报一条工序级阻断。"""

from datetime import date

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_batch_material import normalize_material_changes
from core.services.workbench.batch.facts import BatchFacts
from core.services.workbench.batch.materials import WorkbenchBatchMaterialService
from core.services.workbench.batch.scope import BatchFactScope
from core.services.workbench.run.preflight import PreflightService
from tests.workbench.execution_ledger_support import publish_official_plan
from tests.workbench.run_compute_support import run_case as run_case  # noqa: F401

HOLD = {"start": "2026-09-09T00:00", "end": "2026-09-10T00:00"}
UNPROVEN = ("，但按现在的工作日历或外协周期算不出这道工序的完工时间。排产会原样保留这个安排，排出的方案都不能采用。"
            "请核对相关的工作日历、个人日历、班次或外协周期，或到排产检查把不重排时段改短或不设。")


def _held_blockers(case, *batch_ids):
    data, _ = PreflightService(case.conn).evaluate(case.settings(*batch_ids, hold_window=HOLD), material_day=date.today().isoformat())
    return [row for row in data["blockers"] if row["code"] != "all_tasks_held"], data


def _operation_ref(data, sequence):
    return next(task["operation_ref"] for task in data["tasks"] if (task["batch_id"], task["sequence"]) == ("B1", sequence))


def test_held_arrangement_whose_operator_never_works_is_one_calendar_unproven_blocker(run_case):
    case = run_case
    publish_official_plan(case.conn, 1, [{"op_id": case.op_id, "machine_id": "M1", "operator_id": "O1",
                                          "start_time": "2026-09-09T08:00:00", "end_time": "2026-09-09T08:45:00"}])
    case.conn.commit()
    assert _held_blockers(case)[0] == []
    # 人员换到只有休息日的班次：往后 10 年都没有允许这个优先级的班段。
    case.conn.execute("INSERT INTO WorkbenchShiftProfiles(profile_id,name,anchor_date,cycle_days) "
                      "VALUES ('REST','Rest','2026-09-01',1)")
    case.conn.execute("INSERT INTO WorkbenchShiftPatternDays(profile_id,day_offset,is_rest,periods_json) "
                      "VALUES ('REST',0,1,'[]')")
    case.conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,shift_profile_id) VALUES ('O1','REST')")
    case.conn.commit()
    blockers, data = _held_blockers(case)
    assert [(row["code"], row["operation_ref"], row["batch_id"]) for row in blockers] == [
        ("locked_calendar_unproven", _operation_ref(data, 1), "B1")]
    assert blockers[0]["message"] == ("这道工序在正式计划里排在 2026-09-09 08:00:00 至 2026-09-09 08:45:00，"
                                      "因不重排时段（2026-09-09 00:00 至 2026-09-10 00:00）保持原安排" + UNPROVEN)



def test_held_arrangement_beyond_the_exact_hours_range_is_calendar_unproven_for_whole_and_piece_batches(run_case):
    """标准工时按排产同一公式算，总量超过 2^53-1 小时（单项仍在准入上限内）时，整批与分件批次都报“日历核对不了”。"""
    case = run_case
    case.batch("B2", quantity=1)
    piece_op = case.operation("B2", piece_id="B2-1")
    publish_official_plan(case.conn, 1, [
        {"op_id": case.op_id, "machine_id": "M1", "operator_id": "O1",
         "start_time": "2026-09-09T08:00:00", "end_time": "2026-09-09T08:45:00"},
        {"op_id": piece_op, "machine_id": "M1", "operator_id": "O1",
         "start_time": "2026-09-09T09:00:00", "end_time": "2026-09-09T09:15:00"}])
    case.conn.commit()
    assert _held_blockers(case, "B1", "B2")[0] == []
    # 整批 9e15 h × 3 件；分件 9e15 h + 9e15 h × 1 件。
    case.conn.execute("UPDATE BatchOperations SET unit_hours=9e15 WHERE id=?", (case.op_id,))
    case.conn.execute("UPDATE BatchOperations SET setup_hours=9e15, unit_hours=9e15 WHERE id=?", (piece_op,))
    case.conn.commit()
    blockers, _ = _held_blockers(case, "B1", "B2")
    assert sorted((row["code"], row["batch_id"]) for row in blockers) == [
        ("locked_calendar_unproven", "B1"), ("locked_calendar_unproven", "B2")]


def test_held_point_arrangement_stays_while_hours_are_zero_and_conflicts_once_the_operation_has_hours(run_case):
    """零工时保留安排与采用同口径：工时为零时这一刻本身成立就原样保留；工序改出工时后报零工时冲突。"""
    case = run_case
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0 WHERE id=?", (case.op_id,))
    publish_official_plan(case.conn, 1, [{"op_id": case.op_id, "machine_id": "M1", "operator_id": "O1",
                                          "start_time": "2026-09-09T08:00:00", "end_time": "2026-09-09T08:00:00"}])
    case.conn.commit()
    assert _held_blockers(case)[0] == []
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0.25 WHERE id=?", (case.op_id,))
    case.conn.commit()
    blockers, data = _held_blockers(case)
    assert [(row["code"], row["operation_ref"]) for row in blockers] == [("locked_point_conflict", _operation_ref(data, 1))]
    assert "原安排是开工即完工的零工时安排，但这道工序现在有工时，不再是零工时工序。" in blockers[0]["message"]


HELD = ("这道工序在正式计划里排在 2026-09-09 08:00:00 至 2026-09-09 08:45:00，"
        "因不重排时段（2026-09-09 00:00 至 2026-09-10 00:00）保持原安排")
KEEP = "排产会原样保留这个安排，排出的方案都不能采用。"
SHORTEN = "，或到排产检查把不重排时段改短或不设。"


def _publish_held(case, machine_id="M1", operator_id="O1"):
    publish_official_plan(case.conn, 1, [{"op_id": case.op_id, "machine_id": machine_id, "operator_id": operator_id,
                                          "start_time": "2026-09-09T08:00:00", "end_time": "2026-09-09T08:45:00"}])
    case.conn.commit()


def test_held_arrangement_on_an_unauthorized_operator_names_the_missing_authorization(run_case):
    """保留安排用的是计划行自己的设备人员：工序资料里的人员有授权，计划行上的人员没有，照样报资源阻断。"""
    case = run_case
    case.conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('M2','Mill')")
    case.conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('M2','T1')")
    case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O2','Second')")
    _publish_held(case, "M2", "O2")
    blockers, data = _held_blockers(case)
    assert [(row["code"], row["operation_ref"]) for row in blockers] == [("locked_resource_invalid", _operation_ref(data, 1))]
    assert blockers[0]["message"] == (HELD + "，用的是设备 M2、人员 O2，但人员没有这台设备的操作授权。" + KEEP
                                      + "请到资料总览核对设备、人员和工种" + SHORTEN)


def test_held_arrangement_before_the_batch_ready_date_is_one_ready_date_blocker(run_case):
    case = run_case
    _publish_held(case)
    case.conn.execute("UPDATE Batches SET ready_date='2026-09-10' WHERE batch_id='B1'")
    case.conn.commit()
    blockers, data = _held_blockers(case)
    assert [(row["code"], row["operation_ref"]) for row in blockers] == [("locked_before_ready_date", _operation_ref(data, 1))]
    assert blockers[0]["message"] == (HELD + "，但这批的齐套日期是 2026-09-10，比原安排晚。" + KEEP
                                      + "请到批次管理核对齐套日期" + SHORTEN)


def test_held_arrangement_before_its_material_arrives_names_the_arrival_day(run_case):
    case = run_case
    _publish_held(case)
    case.conn.execute("INSERT INTO Materials(material_id,name,unit) VALUES ('STEEL','钢材','件')")
    case.conn.commit()
    operation_ref = case.conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? "
                                      "AND active=1", (str(case.op_id),)).fetchone()[0]
    with TransactionManager(case.conn).transaction():
        batch_ref = case.ref("batch", "B1")
        scope = BatchFactScope(BatchFacts(case.conn, material_day=date.today().isoformat()), command=True, mode="single_instance", target_ref=batch_ref)
        WorkbenchBatchMaterialService(case.conn).apply_normalized(scope, batch_ref, normalize_material_changes({
            "removed_keys": [], "rows": [{"row_key": None, "material_ref": case.ref("material", "STEEL"),
                                          "required_quantity": 3, "available_quantity": 0, "operation_ref": operation_ref,
                                          "arrivals": [{"arrival_date": "2026-09-10", "quantity": 3}]}]}))
    blockers, data = _held_blockers(case)
    assert [(row["code"], row["operation_ref"]) for row in blockers] == [("locked_material_late", _operation_ref(data, 1))]
    assert blockers[0]["message"] == (HELD + "，但本序物料要到 2026-09-10 才到齐。" + KEEP
                                      + "请到批次管理核对物料到料" + SHORTEN)
