"""5000 real positive-duration operations; no mock optimizer or truncated payload."""

import time

from core.services.workbench.run_compute import compute_candidate_run
from tests.workbench.run_compute_support import run_case as _run_case  # noqa: F401
from tests.workbench.run_compute_support import unchanged


def test_5000_operations_produce_complete_candidates_with_no_database_changes(run_case):
    case = run_case
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0.001")
    codes = ["B1"] + [f"CAP-{index:03d}" for index in range(1, 100)]
    for code in codes[1:]:
        case.batch(code)
    for index, code in enumerate(codes):
        machine, operator = ("M1", "O1") if index == 0 else (f"CM{index:03d}", f"CO{index:03d}")
        if index:
            case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES (?,?,'T1')", (machine, machine))
            case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES (?,?)", (operator, operator))
            case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)", (operator, machine))
        for seq in range(2 if index == 0 else 1, 51):
            case.operation(code, seq, unit_hours=0.001, machine_id=machine, operator_id=operator)
    case.conn.commit()
    case.config(time_budget_seconds=600)
    op_ids = {row[0] for row in case.conn.execute("SELECT id FROM BatchOperations")}
    assert len(op_ids) == 5000
    projections = case.projections()
    started = time.monotonic()
    result = unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(*codes), projections))
    elapsed = time.monotonic() - started
    assert result.state == "complete"
    assert result.result_persisted is False
    assert len(result.dispositions) == 5000
    assert len(result.schedule_input.normalized_batch_ids) == 100
    assert len(result.candidate_payloads) == 4
    for payload in result.candidate_payloads.values():
        assert payload.scheduled_op_ids == op_ids
        assert len(payload.schedule_rows) == 5000
        assert all(row.end_time > row.start_time for row in payload.schedule_rows)
    assert elapsed < 180
