"""当前工作台保留批次外协快照、冻结种子和已完工的实际安排。"""

from datetime import datetime

import pytest

from core.algorithm_contracts.types import ScheduleResult
from core.services.batch.service import BatchService
from core.services.workbench.run.compute import compute_candidate_run
from tests.workbench.run_compute_support import run_case as _run_case  # noqa: F401
from tests.workbench.run_compute_support import unchanged


def _external_plan(case, with_execution):
    conn = case.conn
    conn.executescript("""
        INSERT INTO OpTypes(op_type_id,name,category) VALUES ('EXT','External','external');
        INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('S1','Supplier','EXT');
        INSERT INTO Parts(part_no,part_name,route_parsed) VALUES ('P_EXT','External Part','yes');
        INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id)
        VALUES ('G1','P_EXT',10,20,'separate',2,'S1');
    """)
    for seq in (10, 20, 30):
        conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days,ext_group_id) "
                     "VALUES ('P_EXT',?,'EXT','External','external','S1',1,?)", (seq, "G1" if seq < 30 else None))
    conn.commit()
    BatchService(conn).create_batch_from_template(batch_id="EXT", part_no="P_EXT", quantity=1,
        due_date="2026-09-25", ready_status="yes")
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
    result = unchanged(case, lambda: compute_candidate_run(case.conn, settings, case.projections("EXT", "B1") if with_execution else case.projections("EXT")))
    prepared = result.schedule_input
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
    assert all(type(row) is ScheduleResult for row in result.orchestration.results)
    assert not any(key.startswith("_external_group") for row in result.orchestration.results for key in vars(row))
    assert [tuple(row) for row in case.conn.execute("SELECT * FROM Schedule ORDER BY id")] == original
