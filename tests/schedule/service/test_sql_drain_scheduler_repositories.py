"""合同测试：SQL 排水第四批——工作台之外的服务层下沉出来的仓储方法。

覆盖日历投影事实、断点日历证书、执行台账范围、工艺模板查询、批次复制、执行资源事实、
计划目录有界读取、操作日志清理与工艺工作流读取。仓储只返回事实：上限、缺失、不一致的
裁决都留在服务层，这里只锁 SQL 语义（排序、过滤、限额、原始值）。
"""

from __future__ import annotations

import sqlite3

import pytest

from core.errors import AppError
from core.models.schedule_plan_role import SOURCE_SCHEDULE
from data.repositories.calendar_checkpoint_repo import CalendarCheckpointRepository
from data.repositories.calendar_facts_repo import CalendarFactsRepository
from data.repositories.execution_ledger_scope_repo import ExecutionLedgerScopeRepository
from data.repositories.operation_log_repo import OperationLogRepository
from data.repositories.process_query_repo import ProcessQueryRepository
from data.repositories.schedule_adjustment_scenario_repo import ScheduleAdjustmentScenarioRepository
from data.repositories.schedule_batch_copy_repo import ScheduleBatchCopyRepository
from data.repositories.schedule_execution_facts_repo import ScheduleExecutionFactsRepository
from data.repositories.schedule_plan_detail_time_repo import SchedulePlanDetailTimeRepository
from data.repositories.workbench_plan_catalog_repo import WorkbenchPlanCatalogRepository
from data.repositories.workbench_process_workflow_repo import WorkbenchProcessWorkflowRepository
from tests.workbench.execution_ledger_support import ledger_case as ledger_case  # noqa: F401
from tests.workbench.process_query_support import seed_process
from tests.workbench.process_workflow_support import confirm_all, seed_workflow


def _seed_resources(conn) -> None:
    conn.executemany("INSERT INTO OpTypes(op_type_id,name,category) VALUES (?,?,?)",
                     [("T1", "车削", "internal"), ("T2", "铣削", "internal")])
    conn.executemany("INSERT INTO Machines(machine_id,name,op_type_id,status) VALUES (?,?,?,?)",
                     [("M1", "车床", "T1", "active"), ("M2", "铣床", "T2", "inactive")])
    conn.executemany("INSERT INTO Operators(operator_id,name,status) VALUES (?,?,?)",
                     [("O1", "甲", "active"), ("O2", "乙", "active")])
    conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
    conn.execute("INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES ('O1','T1')")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','零件')")
    conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B1','P1',5)")
    conn.executemany(
        "INSERT INTO BatchOperations(op_code,batch_id,seq,piece_id,op_type_id,op_type_name) VALUES (?,?,?,?,?,?)",
        [("B1-20", "B1", 20, None, "T2", "铣削"), ("B1-10b", "B1", 10, "b", "T1", "车削"),
         ("B1-10a", "B1", 10, "a", "T1", "车削")])
    conn.commit()


def _seed_calendar(conn) -> None:
    conn.execute("INSERT INTO WorkCalendar(date,day_type,shift_start,shift_end,remark) "
                 "VALUES ('2026-09-21','workday','08:00','17:00','备注不进证书')")
    conn.execute("INSERT INTO WorkCalendar(date,day_type) VALUES ('2026-09-20','rest')")
    conn.execute("INSERT INTO OperatorCalendar(operator_id,date,day_type,shift_start,shift_end) "
                 "VALUES ('O1','2026-09-21','workday','09:00','18:00')")
    conn.execute("INSERT INTO WorkbenchShiftProfiles(profile_id,name,anchor_date,cycle_days,status) "
                 "VALUES ('SP1','两班','2026-09-01',2,'active')")
    conn.executemany("INSERT INTO WorkbenchShiftPatternDays(profile_id,day_offset,is_rest,shift_start,shift_end) VALUES (?,?,?,?,?)",
                     [("SP1", 0, 0, "08:00", "16:00"), ("SP1", 1, 1, "", "")])
    conn.executemany("INSERT INTO WorkbenchOperatorProfiles(operator_id,shift_profile_id,skills_declared) VALUES (?,?,?)",
                     [("O1", "SP1", 1), ("O2", None, 0)])
    conn.commit()


# ---------------------------------------------------------------- 断点日历证书
def test_calendar_signature_rows_keep_query_order_and_raw_storage_values(schema_conn) -> None:
    _seed_resources(schema_conn)
    _seed_calendar(schema_conn)
    rows = CalendarCheckpointRepository(schema_conn).calendar_signature_rows()
    assert len(rows) == 5 and all(type(group) is tuple for group in rows)
    assert [tuple(map(str, row[:2])) for row in rows[0]] == [("2026-09-20", "rest"), ("2026-09-21", "workday")]
    assert rows[0][1][2:] == ("08:00", "17:00", 8.0, 1.0, "yes", "yes"), "remark 不进证书"
    assert [(row[0], str(row[1]), row[3], row[4]) for row in rows[1]] == [("O1", "2026-09-21", "09:00", "18:00")]
    assert rows[2] == (("O1", "SP1"), ("O2", None))
    assert [(row[0], str(row[1]), row[2], row[3]) for row in rows[3]] == [("SP1", "2026-09-01", 2, "active")]
    assert rows[4] == (("SP1", 0, 0, "08:00", "16:00"), ("SP1", 1, 1, "", ""))
    assert CalendarCheckpointRepository(sqlite3.connect(":memory:")).__class__ is CalendarCheckpointRepository


def test_calendar_signature_rows_surface_missing_tables_as_app_error(schema_conn) -> None:
    schema_conn.execute("DROP TABLE WorkbenchShiftPatternDays")
    with pytest.raises(AppError) as failure:
        CalendarCheckpointRepository(schema_conn).calendar_signature_rows()
    assert isinstance(failure.value.cause, sqlite3.OperationalError)


# ---------------------------------------------------------------- 日历投影事实
def test_calendar_facts_reads_are_keyed_ordered_and_limited(schema_conn) -> None:
    _seed_resources(schema_conn)
    _seed_calendar(schema_conn)
    repo = CalendarFactsRepository(schema_conn)
    assert [str(row["date"]) for row in repo.global_calendar("2026-09-21", "2026-09-30", limit=10)] == ["2026-09-21"]
    assert len(repo.global_calendar("2026-09-01", "2026-09-30", limit=1)) == 1
    personal = repo.personal_calendar(["O2", "O1"], "2026-09-01", "2026-09-30", limit=10)
    assert [(row["operator_id"], row["shift_start"]) for row in personal] == [("O1", "09:00")]
    profiles = repo.operator_profiles(["O1", "O2"], limit=10)
    assert [(row["operator_id"], row["shift_profile_id"], row["cycle_days"], row["status"]) for row in profiles] == [("O1", "SP1", 2, "active")]
    assert [(row["day_offset"], row["is_rest"]) for row in repo.shift_patterns(["SP1", "none"], limit=10)] == [(0, 0), (1, 1)]
    assert [(row["machine_id"], row["op_type_id"], row["status"]) for row in repo.machines(["M2", "M1"], limit=10)] == [("M1", "T1", "active"), ("M2", "T2", "inactive")]
    states = repo.machine_states(["M1"], limit=10)
    assert states == [{"machine_id": "M1", "name": "车床", "status": "active"}]
    assert [row["operator_id"] for row in repo.operators(["O2", "O1"], limit=10)] == ["O1", "O2"]
    assert len(repo.operators(["O2", "O1"], limit=1)) == 1
    ids = [row["id"] for row in schema_conn.execute("SELECT id FROM BatchOperations ORDER BY id")]
    assert [(row["id"], row["op_type_id"]) for row in repo.operations(list(reversed(ids)), limit=10)] == [(ids[0], "T2"), (ids[1], "T1"), (ids[2], "T1")]
    assert [(row["op_type_id"], row["category"]) for row in repo.work_types(["T2", "T1"], limit=10)] == [("T1", "internal"), ("T2", "internal")]
    assert [(row["operator_id"], row["machine_id"]) for row in repo.authorizations(["O1", "O2"], limit=10)] == [("O1", "M1")]
    assert [(row["operator_id"], row["profile_operator_id"], row["skills_declared"]) for row in repo.skill_profiles(["O1", "O2"], limit=10)] == [("O1", "O1", 1), ("O2", "O2", 0)]
    assert [(row["operator_id"], row["op_type_id"], row["category"]) for row in repo.skills(["O1", "O2"], limit=10)] == [("O1", "T1", "internal")]


def test_calendar_facts_downtimes_return_overlapping_and_bad_time_rows_only(schema_conn) -> None:
    _seed_resources(schema_conn)
    schema_conn.executemany("INSERT INTO MachineDowntimes(machine_id,start_time,end_time,status) VALUES (?,?,?,?)", [
        ("M1", "2026-09-21 08:00:00", "2026-09-21 10:00:00", "active"),
        ("M1", "2026-09-21 13:00:00", "2026-09-21 14:00:00", "active"),
        ("M1", "2026-09-21 08:30:00", "2026-09-21 09:30:00", "cancelled"),
        ("M1", "bad-start", "worse-end", None),
        ("M2", "2026-09-21 09:00:00", "2026-09-21 09:30:00", "active"),
    ])
    repo = CalendarFactsRepository(schema_conn)
    rows = repo.downtimes(["M1"], "2026-09-21 12:00:00", "2026-09-21 09:00:00", limit=10)
    assert [(row["machine_id"], row["start_time"], row["status"]) for row in rows] == [
        ("M1", "2026-09-21 08:00:00", "active"), ("M1", "bad-start", None)]
    assert len(repo.downtimes(["M1"], "2026-09-21 12:00:00", "2026-09-21 09:00:00", limit=1)) == 1
    assert repo.downtimes(["M2"], "2026-09-22 00:00:00", "2026-09-21 23:00:00", limit=10) == []


# ---------------------------------------------------------------- 执行台账范围
def _operation_ref(conn, op_id) -> str:
    return conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? AND active=1",
                        (str(op_id),)).fetchone()[0]


def test_execution_ledger_scope_reads(ledger_case) -> None:
    case = ledger_case
    repo = ExecutionLedgerScopeRepository(case.conn)
    assert repo.schema_version_value() == 24
    assert repo.has_execution_command_receipts() is False
    case.conn.execute(
        "INSERT INTO WorkbenchCommandReceipts(request_key,receipt_ref,action,context_ref,input_hash,outcome_json) VALUES (?,?,?,?,?,?)",
        ("execution-receipt-00000001", "a" * 32, "execution.record", "ctx", "b" * 64, "{}"))
    assert repo.has_execution_command_receipts() is True
    schedule_id = case.conn.execute("SELECT id FROM Schedule WHERE version=1").fetchone()[0]
    assert repo.scope_task_rows([]) == []
    assert repo.scope_task_rows([schedule_id, 987654]) == [
        (schedule_id, 1, case.op_id, "B1", _operation_ref(case.conn, case.op_id), case.task(1, case.op_id), case.plan_ref(1))]


def test_execution_ledger_reported_operation_without_schedule_row(ledger_case) -> None:
    case = ledger_case
    case.install()
    repo = ExecutionLedgerScopeRepository(case.conn)
    assert repo.reported_operation_without_schedule_row() is None
    case.conn.execute(
        "INSERT INTO WorkbenchProductionReports(report_ref,report_no,operation_ref,recorded_against_task_ref,"
        "recorded_against_plan_ref,source,recorded_at) VALUES (?,?,?,?,?,'manual','2026-09-10T12:00:00')",
        ("c" * 48, "R1", _operation_ref(case.conn, case.op_id), case.task(1, case.op_id), case.plan_ref(1)))
    case.conn.commit()
    assert repo.reported_operation_without_schedule_row() is None, "有活跃安排行时不算孤儿报工"
    case.conn.execute("DELETE FROM Schedule WHERE version=1")
    case.conn.commit()
    assert repo.reported_operation_without_schedule_row() == (str(case.op_id),)


# ---------------------------------------------------------------- 执行资源事实与明细时间探针
def test_schedule_execution_facts_latest_rows_and_event_identity_probe(ledger_case) -> None:
    case = ledger_case
    repo = ScheduleExecutionFactsRepository(case.conn)
    rows = repo.latest_plan_rows(1)
    assert [(row["version"], row["op_id"], row["batch_id"], row["source"]) for row in rows] == [(1, case.op_id, "B1", "internal")]
    assert set(rows[0]) == {"schedule_id", "version", "op_id", "batch_id", "source", "start_time", "end_time"}
    second = case.op(code="OP2", seq=2)
    case.plan(2, [second])
    assert [(row["version"], row["op_id"]) for row in repo.latest_plan_rows(2)] == [(1, case.op_id), (2, second)]
    assert [(row["version"], row["op_id"]) for row in repo.latest_plan_rows(1)] == [(1, case.op_id)]
    assert repo.latest_plan_rows(0) == []
    assert repo.has_event_without_plan_identity("schedule", "adopted") is False
    case.event(case.op_id, "start")
    assert repo.has_event_without_plan_identity("schedule", "adopted") is False
    # 事件记的版本与安排行版本对不上（模拟历史损坏，暂时关掉外键才能写出这种行）：事实层只报 True，裁决在服务层
    case.conn.execute("PRAGMA foreign_keys=OFF")
    case.conn.execute("UPDATE OperationExecutionEvents SET schedule_version=7")
    case.conn.commit()
    case.conn.execute("PRAGMA foreign_keys=ON")
    assert repo.has_event_without_plan_identity("schedule", "adopted") is True
    assert repo.has_event_without_plan_identity("schedule", "baseline_best") is False


def test_schedule_plan_detail_time_probe_flags_empty_or_inverted_ranges(ledger_case) -> None:
    case = ledger_case
    repo = SchedulePlanDetailTimeRepository(case.conn)
    scope = dict(source_table=SOURCE_SCHEDULE, candidate_id=None, scenario_id=None)
    assert repo.has_invalid_detail_times(version=1, **scope) is False
    case.conn.execute("UPDATE Schedule SET end_time=start_time WHERE version=1")
    case.conn.commit()
    assert repo.has_invalid_detail_times(version=1, **scope) is True
    case.conn.execute("UPDATE Schedule SET end_time='' WHERE version=1")
    case.conn.commit()
    assert repo.has_invalid_detail_times(version=1, **scope) is True
    assert repo.has_invalid_detail_times(version=2, **scope) is False


# ---------------------------------------------------------------- 计划目录有界读取
def test_plan_catalog_bounded_reads(ledger_case) -> None:
    case = ledger_case
    repo = WorkbenchPlanCatalogRepository(case.conn)
    scope = dict(version=1, source_table=SOURCE_SCHEDULE, candidate_id=None)
    schedule_id = case.conn.execute("SELECT id FROM Schedule WHERE version=1").fetchone()[0]
    assert repo.list_plan_row_ids_bounded(limit=5, **scope) == [{"id": schedule_id}]
    assert repo.list_plan_row_ids_bounded(limit=0, **scope) == []
    rows = repo.list_plan_rows_bounded(limit=5, **scope)
    assert [(row["id"], row["op_id"], row["version"]) for row in rows] == [(schedule_id, case.op_id, 1)]
    detail = repo.list_detail_rows_bounded(limit=5, **scope)
    assert len(detail) == 1 and detail[0]["op_id"] == case.op_id and detail[0]["batch_id"] == "B1"
    inside = repo.list_detail_rows_bounded(limit=5, range_start="2026-09-09 09:00:00", range_end="2026-09-09 09:30:00", **scope)
    assert [row["op_id"] for row in inside] == [case.op_id]
    outside = repo.list_detail_rows_bounded(limit=5, range_start="2026-09-10 00:00:00", range_end="2026-09-10 01:00:00", **scope)
    assert outside == []
    assert repo.list_detail_rows_bounded(limit=0, **scope) == []
    assert repo.list_plan_row_ids_bounded(version=9, source_table=SOURCE_SCHEDULE, candidate_id=None, limit=5) == []


# ---------------------------------------------------------------- 批次复制、模拟方案目录、操作日志
def test_batch_copy_source_operation_ids_follow_seq_then_piece(schema_conn) -> None:
    _seed_resources(schema_conn)
    ids = {row["op_code"]: row["id"] for row in schema_conn.execute("SELECT op_code,id FROM BatchOperations")}
    assert ScheduleBatchCopyRepository(schema_conn).source_operation_ids("B1") == [ids["B1-10a"], ids["B1-10b"], ids["B1-20"]]
    assert ScheduleBatchCopyRepository(schema_conn).source_operation_ids("missing") == []


def test_scenario_catalog_rows_order_by_base_version_then_created_at(schema_conn) -> None:
    schema_conn.executemany(
        "INSERT INTO ScheduleAdjustmentScenario(scenario_id,source_draft_id,base_version,base_plan_role,base_source_table,"
        "validation_status,created_at) VALUES (?,?,?,?,?,?,?)",
        [("S-old", "D-old", 1, "adopted", "schedule", "valid", "2026-09-01 00:00:00"),
         ("S-new", "D-new", 2, "adopted", "schedule", "valid", "2026-09-01 00:00:00"),
         ("S-late", "D-late", 1, "adopted", "schedule", "warning", "2026-09-02 00:00:00")])
    rows = ScheduleAdjustmentScenarioRepository(schema_conn).list_catalog_rows()
    assert [row["scenario_id"] for row in rows] == ["S-new", "S-late", "S-old"]
    assert rows[0]["status"] == "active" and rows[2]["validation_status"] == "valid"


def test_operation_log_counts_and_oldest_first_deletion(schema_conn) -> None:
    repo = OperationLogRepository(schema_conn)
    assert repo.count_all() == 0
    schema_conn.executemany("INSERT INTO OperationLogs(log_time,log_level,module,action) VALUES (?,?,?,?)", [
        ("2026-09-02 00:00:00", "INFO", "m", "second"), ("2026-09-01 00:00:00", "INFO", "m", "first"),
        ("2026-09-03 00:00:00", "INFO", "m", "third")])
    assert repo.count_all() == 3
    assert repo.count_before("2026-09-03 00:00:00") == 2
    assert repo.delete_oldest_before("2026-09-03 00:00:00", 1) == 1
    assert [row[0] for row in schema_conn.execute("SELECT action FROM OperationLogs ORDER BY log_time")] == ["second", "third"]
    assert repo.delete_oldest_before("2026-09-03 00:00:00", 5) == 1
    assert repo.delete_oldest_before("2026-09-03 00:00:00", 5) == 0
    assert repo.count_all() == 1


# ---------------------------------------------------------------- 工艺模板查询
def test_process_query_repository_template_and_batch_facts(schema_conn) -> None:
    seed_process(schema_conn)
    repo = ProcessQueryRepository(schema_conn)
    assert repo.batch_references_part("PROC-001") is True
    assert repo.batch_references_part("PROC-002") is False
    row = repo.template_operation_ref("PROC-001", 10)
    assert row is not None and set(row) == {"ref"} and len(row["ref"]) == 48
    assert repo.template_operation_ref("PROC-004", 10) is None, "已删除模板工序没有活跃引用行"
    assert repo.template_operation_ref("PROC-001", 99) is None
    rows = repo.template_operations_by_refs([row["ref"], "f" * 48])
    assert [(item["part_no"], item["seq"], item["ref"]) for item in rows] == [("PROC-001", 10, row["ref"])]
    assert rows[0]["revision"] >= 1 and rows[0]["op_type_name"] == "车削"
    assert repo.template_operations_by_refs([]) == []
    legacy = repo.legacy_template_operations()
    assert [(item["part_no"], item["seq"], item["unit_hours"]) for item in legacy] == [
        ("PROC-001", 10, 0.125), ("PROC-001", 20, 0.0), ("PROC-001", 30, 0.0), ("PROC-003", 10, None)]
    assert all(len(item["ref"]) == 48 for item in legacy)


# ---------------------------------------------------------------- 工艺工作流读取
def test_process_workflow_reads_cover_parts_operations_groups_suppliers_and_confirmations(schema_conn) -> None:
    seed_workflow(schema_conn)
    repo = WorkbenchProcessWorkflowRepository(schema_conn)
    parts = repo.parts_with_refs()
    assert [(part["part_no"], part["remark"]) for part in parts] == [("P1", "retained")]
    part = repo.part_with_ref("P1")[0]
    assert part["part_name"] == "part" and len(part["ref"]) == 48
    assert repo.part_with_ref("missing") == []
    assert repo.stored_workflow(part["ref"]) == [] and repo.stored_workflows() == []
    ops = repo.active_operations("P1")
    assert [(op["seq"], op["type_name"], op["category"], op["source"]) for op in ops] == [
        (1, "turning", "internal", "internal"), (2, "turning", "internal", "internal"), (3, "coating", "external", "external")]
    assert {"ref", "type_ref", "default_merge_mode"} <= set(ops[0])
    assert [op["seq"] for op in repo.active_operations()] == [1, 2, 3]
    assert repo.active_operations("missing") == []
    groups = repo.active_external_groups("P1")
    assert [(group["group_id"], group["remark"]) for group in groups] == [("P1-G", "retained-hidden-rule")] and "ref" in groups[0]
    assert [group["group_id"] for group in repo.active_external_groups()] == ["P1-G"]
    facts = repo.supplier_facts()
    assert [(fact["supplier_id"], fact["op_type_id"], fact["status"], fact["inactive_reason"]) for fact in facts] == [("S", "TE", "active", None)]
    assert all(set(row) == {"supplier_id", "op_type_id"} for row in repo.supplier_op_types())
    assert repo.confirmations("P1") == [] and repo.confirmations() == []
    confirm_all(schema_conn, "P1")
    stored = repo.stored_workflow(part["ref"])
    assert len(stored) == 1 and len(stored[0]["route_signature"]) == 64
    assert [row["part_ref"] for row in repo.stored_workflows()] == [part["ref"]]
    confirmations = repo.confirmations("P1")
    assert {row["stage"] for row in confirmations} == {"source", "hours"}
    assert all(row["part_ref"] == part["ref"] and len(row["signature"]) == 64 for row in confirmations)
    assert len(repo.confirmations()) == len(confirmations)
    assert repo.confirmations("missing") == []
