"""合同测试：SQL 排水第一批（写语句）新增的仓储方法——按 id 改工序、外协组解绑/删除/改周期、工艺工作流确认表写入、
运行作业对账补写。锁定每个方法的 SQL 语义与影响行数，服务层不再持 conn 直接写这些表。"""

from __future__ import annotations

from data.repositories.external_group_repo import ExternalGroupRepository
from data.repositories.part_operation_repo import PartOperationRepository
from data.repositories.part_repo import PartRepository
from data.repositories.workbench_process_workflow_repo import WORKFLOW_STAGES, WorkbenchProcessWorkflowRepository
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from tests.workbench.process_query_support import seed_process


def _op(conn, part_no, seq):
    return dict(conn.execute("SELECT * FROM PartOperations WHERE part_no=? AND seq=?", (part_no, seq)).fetchone())


def test_part_operation_write_methods_by_id(schema_conn) -> None:
    seed_process(schema_conn)
    repo = PartOperationRepository(schema_conn)
    op10, op20 = _op(schema_conn, "PROC-001", 10), _op(schema_conn, "PROC-001", 20)

    assert repo.clear_external_group("PROC-001", "PROC-G") == 1
    assert _op(schema_conn, "PROC-001", 20)["ext_group_id"] is None
    assert repo.clear_external_group("PROC-001", "PROC-G") == 0

    assert repo.mark_deleted_by_id(op10["id"]) == 1
    assert _op(schema_conn, "PROC-001", 10)["status"] == "deleted"
    assert repo.restore_with_op_type_name(op10["id"], "精车") == 1
    restored = _op(schema_conn, "PROC-001", 10)
    assert (restored["status"], restored["op_type_name"], restored["unit_hours"]) == ("active", "精车", 0.125)

    repo.insert_route_operation(part_no="PROC-001", seq=40, op_type_name="磨削", source="internal",
                                op_type_id="PROC-IN", supplier_id=None, ext_days=None)
    inserted = _op(schema_conn, "PROC-001", 40)
    assert (inserted["status"], inserted["setup_hours"], inserted["unit_hours"], inserted["op_type_id"]) == ("active", None, None, "PROC-IN")

    repo.update_sources_by_id([("external", "PROC-EX", "PROC-S", inserted["id"])])
    changed = _op(schema_conn, "PROC-001", 40)
    assert (changed["source"], changed["op_type_id"], changed["supplier_id"]) == ("external", "PROC-EX", "PROC-S")

    assert repo.update_fields_by_id(op20["id"], {"setup_hours": 1.5, "ext_days": 4.0}) == 1
    updated = _op(schema_conn, "PROC-001", 20)
    assert (updated["setup_hours"], updated["ext_days"]) == (1.5, 4.0)
    assert repo.update_fields_by_id(op20["id"], {}) == 0
    try:
        repo.update_fields_by_id(op20["id"], {"part_no": "X"})
    except ValueError as exc:
        assert "part_no" in str(exc)
    else:
        raise AssertionError("白名单外的列必须抛错")


def test_external_group_delete_for_part_and_set_total_days(schema_conn) -> None:
    seed_process(schema_conn)
    repo = ExternalGroupRepository(schema_conn)
    assert repo.set_total_days("PROC-G", 9.5) == 1
    assert schema_conn.execute("SELECT total_days FROM ExternalGroups WHERE group_id='PROC-G'").fetchone()[0] == 9.5
    assert repo.set_total_days("NOPE", 1) == 0
    assert repo.delete_for_part("PROC-002", "PROC-G") == 0, "part_no 不匹配不得误删"
    PartOperationRepository(schema_conn).clear_external_group("PROC-001", "PROC-G")
    assert repo.delete_for_part("PROC-001", "PROC-G") == 1
    assert schema_conn.execute("SELECT COUNT(*) FROM ExternalGroups WHERE group_id='PROC-G'").fetchone()[0] == 0


def test_part_update_keeps_route_semantics(schema_conn) -> None:
    seed_process(schema_conn)
    PartRepository(schema_conn).update("PROC-002", {"route_raw": "10车削", "route_parsed": "yes"})
    row = schema_conn.execute("SELECT route_raw, route_parsed, updated_at FROM Parts WHERE part_no='PROC-002'").fetchone()
    assert (row["route_raw"], row["route_parsed"]) == ("10车削", "yes")
    assert row["updated_at"] is not None


def test_workflow_repository_writes(schema_conn) -> None:
    seed_process(schema_conn)
    part_ref = schema_conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='part' AND entity_key='PROC-001'").fetchone()[0]
    op_ref = schema_conn.execute(
        "SELECT r.ref FROM WorkbenchEntityRefs r JOIN PartOperations o ON r.entity_key=CAST(o.id AS TEXT) "
        "WHERE r.kind='template_operation' AND o.part_no='PROC-001' AND o.seq=10"
    ).fetchone()[0]
    repo = WorkbenchProcessWorkflowRepository(schema_conn)
    repo.insert_workflow(part_ref)
    assert schema_conn.execute("SELECT COUNT(*) FROM WorkbenchProcessWorkflow WHERE part_ref=?", (part_ref,)).fetchone()[0] == 1

    sig1, sig2 = "1" * 64, "2" * 64
    repo.insert_confirmation(part_ref=part_ref, operation_ref=op_ref, stage="source", signature=sig1,
                             confirmed_at="2026-09-20T00:00:00Z", confirmed_by="张三")
    assert repo.update_confirmation(part_ref=part_ref, operation_ref=op_ref, stage="source", signature=sig2,
                                    confirmed_at="2026-09-20T00:00:01Z", confirmed_by=None) == 1
    row = schema_conn.execute("SELECT signature, confirmed_by FROM WorkbenchProcessOperationConfirmations "
                              "WHERE part_ref=? AND operation_ref=?", (part_ref, op_ref)).fetchone()
    assert (row["signature"], row["confirmed_by"]) == (sig2, None)

    # 本序仍是 active 工序，不在删除范围内
    assert repo.delete_confirmations_outside_active_route(part_ref, "PROC-001") == 0
    PartOperationRepository(schema_conn).mark_deleted_by_id(
        schema_conn.execute("SELECT id FROM PartOperations WHERE part_no='PROC-001' AND seq=10").fetchone()[0])
    assert repo.delete_confirmations_outside_active_route(part_ref, "PROC-001") == 1

    for index, stage in enumerate(WORKFLOW_STAGES):
        assert repo.set_stage_confirmation(part_ref=part_ref, stage=stage, signature=str(index) * 64,
                                           confirmed_at="2026-09-20T00:00:02Z", confirmed_by="李四") == 1
    row = schema_conn.execute("SELECT route_signature, hours_confirmed_by FROM WorkbenchProcessWorkflow WHERE part_ref=?",
                              (part_ref,)).fetchone()
    assert (row["route_signature"], row["hours_confirmed_by"]) == ("0" * 64, "李四")
    try:
        repo.set_stage_confirmation(part_ref=part_ref, stage="bogus", signature="x", confirmed_at="t", confirmed_by=None)
    except ValueError:
        pass
    else:
        raise AssertionError("阶段名不在白名单必须抛错")


def test_run_repository_record_reconciled_finish(schema_conn) -> None:
    run_ref = "a" * 48
    schema_conn.execute(
        "INSERT INTO WorkbenchRunJobs(run_ref,request_key,input_ref,normalized_input_json,facts_hash,facts_json,"
        "execution_json,baseline_json,accepted_at,state,stage,executor_ref,started_at) "
        "VALUES (?,'req-1','in-1','{}','h','{}','{}','{}','t0','running','computing','exec-1','t0')",
        (run_ref,),
    )
    WorkbenchRunRepository(schema_conn).record_reconciled_finish(run_ref, "complete", "t1", "null")
    row = schema_conn.execute("SELECT state, stage, finished_at, error_json FROM WorkbenchRunJobs WHERE run_ref=?", (run_ref,)).fetchone()
    assert tuple(row) == ("complete", "finished", "t1", "null")
