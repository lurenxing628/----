"""当前工作台保留批次外协快照、冻结种子和已完工的实际安排。"""

from datetime import datetime

import pytest

from core.algorithm_contracts.types import ScheduleResult
from core.infrastructure.transaction import TransactionManager
from core.services.scheduler.run.schedule_input_contracts import ScheduleRunInput
from core.services.scheduler.run.schedule_orchestrator import ScheduleOrchestrationOutcome
from core.services.scheduler.template_lineage import TemplateLineageWriter
from core.services.workbench.batch.facts import BatchFacts
from tests.workbench.run_compute_support import compute_run, unchanged
from tests.workbench.run_compute_support import run_case as _run_case  # noqa: F401


def _external_plan(case, with_execution):
    conn = case.conn
    conn.executescript("""
        INSERT INTO OpTypes(op_type_id,name,category) VALUES ('EXT','External','external');
        INSERT INTO Suppliers(supplier_id,name) VALUES ('S1','Supplier');
        INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES ('S1','EXT');
        INSERT INTO Parts(part_no,part_name,route_parsed) VALUES ('P_EXT','External Part','yes');
        INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id)
        VALUES ('G1','P_EXT',10,20,'separate',2,'S1');
    """)
    for seq in (10, 20, 30):
        conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days,ext_group_id) "
                     "VALUES ('P_EXT',?,'EXT','External','external','S1',1,?)", (seq, "G1" if seq < 30 else None))
    conn.commit()
    with TransactionManager(conn).transaction():
        conn.execute("INSERT INTO Batches(batch_id,part_no,quantity,due_date,ready_status) "
                     "VALUES ('EXT','P_EXT',1,'2026-09-25','yes')")
        writer = TemplateLineageWriter(conn)
        facts = BatchFacts(conn).load()
        rows = [row for row in facts["PartOperations"] if row["part_no"] == "P_EXT" and row["status"] == "active"]
        for template in writer.prepare_templates(rows, facts=facts):
            writer.copy_prepared_template("EXT", template)
    ids = [row[0] for row in conn.execute("SELECT id FROM BatchOperations WHERE batch_id='EXT' ORDER BY seq")]
    case.plan(1, ids + ([case.op_id] if with_execution else []))
    for index, op_id in enumerate(ids):
        conn.execute("UPDATE Schedule SET machine_id=NULL,operator_id=NULL,start_time=?,end_time=? WHERE op_id=?",
            (f"2026-09-{9 + index:02d} 00:00:00", f"2026-09-{10 + index:02d} 00:00:00", op_id))
    conn.commit()
    if with_execution:
        case.command("create", case.task(1, case.op_id), case.values(3, effective_processing_hours=2))
    conn.execute("UPDATE ExternalGroups SET merge_mode='merged' WHERE group_id='G1'")
    conn.commit()
    return ids


@pytest.mark.parametrize("with_execution", [False, True])
def test_template_change_keeps_frozen_batch_cycles_and_execution_facts(run_case, with_execution):
    case = run_case
    ids = _external_plan(case, with_execution)
    original = [tuple(row) for row in case.conn.execute("SELECT * FROM Schedule ORDER BY id")]
    settings = case.settings(*(["EXT", "B1"] if with_execution else ["EXT"]),
        hold_window={"start": "2026-09-09T00:00", "end": "2026-09-09T01:00"})
    result = unchanged(case, lambda: compute_run(case.conn, settings, case.projections("EXT", "B1") if with_execution else case.projections("EXT")))
    prepared = result.schedule_input
    assert isinstance(prepared, ScheduleRunInput)
    assert prepared.frozen_op_ids == {ids[0]}
    assert prepared.execution_completed_op_ids == ({case.op_id} if with_execution else set())
    assert ids[0] not in {op.id for op in prepared.algo_ops_to_schedule}
    for payload in result.candidate_payloads.values():
        rows = {row.op_id: row for row in payload.schedule_rows}
        assert (rows[ids[0]].start_time, rows[ids[0]].end_time) == (datetime(2026, 9, 9), datetime(2026, 9, 10))
        assert (rows[ids[1]].start_time, rows[ids[1]].end_time) == (datetime(2026, 9, 10), datetime(2026, 9, 11))
        assert rows[ids[2]].start_time == datetime(2026, 9, 11)
        if with_execution:
            assert (rows[case.op_id].start_time, rows[case.op_id].end_time) == (datetime(2026, 9, 9, 8), datetime(2026, 9, 9, 10))
            assert (rows[case.op_id].machine_id, rows[case.op_id].operator_id) == ("M1", "O1")
    orchestration = result.orchestration
    assert isinstance(orchestration, ScheduleOrchestrationOutcome)
    adopted_results = orchestration.candidate_comparison.selection.selected_plan.results
    assert all(type(row) is ScheduleResult for row in adopted_results)
    assert not any(key.startswith("_external_group") for row in adopted_results for key in vars(row))
    assert [tuple(row) for row in case.conn.execute("SELECT * FROM Schedule ORDER BY id")] == original


@pytest.mark.parametrize("source", ["missing", None, "", " internal", "Internal", "legacy"])
def test_seed_contract_rejects_missing_or_irregular_source(source):
    """种子来源与工序来源同一值域：缺失或不规范一律按无效种子停止排产，不再静默当作自制。"""
    from core.errors import ValidationError
    from core.services.scheduler.run.schedule_seed_contracts import coerce_seed_results

    seed = {"op_id": 1, "op_code": "OP1", "batch_id": "B1", "seq": 1, "machine_id": "M1", "operator_id": "O1",
            "start_time": datetime(2026, 9, 9, 8), "end_time": datetime(2026, 9, 9, 9)}
    if source != "missing":
        seed["source"] = source
    with pytest.raises(ValidationError) as exc_info:
        coerce_seed_results([seed], optimizer_algo_stats={"fallback_counts": {}})
    details = exc_info.value.details or {}
    assert details["reason"] == "invalid_seed_results"
    assert details["invalid_seed_samples"][0]["error"] == "第 1 条已有排产记录的工序来源不正确。"


@pytest.mark.parametrize(("field", "label"), [("op_id", "工序编号"), ("seq", "工序号")])
@pytest.mark.parametrize("value", ["missing", None, "", 0, -1, True, 1.5, "1a"])
def test_seed_contract_rejects_missing_or_non_positive_identity(field, label, value):
    """种子的工序编号和工序号由生产者按本次工序写入正整数：缺失也整次拒绝，不再静默当作 0。"""
    from core.errors import ValidationError
    from core.services.scheduler.run.schedule_seed_contracts import coerce_seed_results

    seed = {"op_id": 1, "op_code": "OP1", "batch_id": "B1", "seq": 1, "machine_id": "M1", "operator_id": "O1",
            "start_time": datetime(2026, 9, 9, 8), "end_time": datetime(2026, 9, 9, 9), "source": "internal"}
    if value == "missing":
        del seed[field]
    else:
        seed[field] = value
    with pytest.raises(ValidationError) as exc_info:
        coerce_seed_results([seed], optimizer_algo_stats={"fallback_counts": {}})
    details = exc_info.value.details or {}
    assert details["reason"] == "invalid_seed_results"
    assert details["invalid_seed_samples"][0]["error"] == "第 1 条已有排产记录的" + label + "必须是正整数。"


_MISSING_TIME = "第 1 条已有排产记录缺少开始时间或结束时间。"
_INVALID_TIME = "第 1 条已有排产记录的开始时间和结束时间必须是有效时间。"
_UNORDERED_TIME = "第 1 条已有排产记录的开始时间必须早于结束时间。"


@pytest.mark.parametrize(("start_time", "end_time", "error"), [
    (None, datetime(2026, 9, 9, 9), _MISSING_TIME),
    (datetime(2026, 9, 9, 8), None, _MISSING_TIME),
    ("2026-09-09 08:00:00", datetime(2026, 9, 9, 9), _INVALID_TIME),
    (datetime(2026, 9, 9, 9), datetime(2026, 9, 9, 8), _UNORDERED_TIME),
    (datetime(2026, 9, 9, 9), datetime(2026, 9, 9, 9), _UNORDERED_TIME),
])
def test_seed_contract_rejects_missing_irregular_or_unordered_time_window(start_time, end_time, error):
    """种子起止时间只在入口校验一次：缺失、非时间、倒序、无见证的零时长都整次拒绝，下游不再二次丢弃。"""
    from core.errors import ValidationError
    from core.services.scheduler.run.schedule_seed_contracts import coerce_seed_results

    seed = {"op_id": 1, "op_code": "OP1", "batch_id": "B1", "seq": 1, "machine_id": "M1", "operator_id": "O1",
            "start_time": start_time, "end_time": end_time, "source": "internal"}
    with pytest.raises(ValidationError) as exc_info:
        coerce_seed_results([seed], optimizer_algo_stats={"fallback_counts": {}})
    details = exc_info.value.details or {}
    assert details["reason"] == "invalid_seed_results"
    assert details["invalid_seed_samples"][0]["error"] == error
