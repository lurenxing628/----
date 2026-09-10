"""5000 actual operations, full persisted candidates and an actual adoption transaction."""

import time

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


def test_5000_real_operations_adopt_without_truncation(candidate_case):
    case = candidate_case
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0.01")
    batches = ["B1"] + [f"BX-{index:03d}" for index in range(1, 100)]
    for index, batch in enumerate(batches):
        machine, operator = ("M1", "O1") if index == 0 else (f"BXM{index:03d}", f"BXO{index:03d}")
        if index:
            case.batch(batch)
            case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES (?,?,'T1')", (machine, machine))
            case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES (?,?)", (operator, operator))
            case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)", (operator, machine))
        for seq in range(2 if index == 0 else 1, 51):
            case.operation(batch, seq, unit_hours=0.01, machine_id=machine, operator_id=operator)
    case.conn.commit()
    case.config(time_budget_seconds=600)
    started = time.monotonic()
    ref = candidate(case, case.settings(*batches))
    compute_seconds = time.monotonic() - started
    before = snapshot(case.conn)
    started = time.monotonic()
    token = preview(case, ref)
    preview_seconds = time.monotonic() - started
    assert snapshot(case.conn) == before
    started = time.monotonic()
    result = service(case.conn).adopt(ref, token, KEY, INTENT)
    adopt_seconds = time.monotonic() - started
    version = result["data"]["official_plan"]["version"]
    assert result["data"]["row_count"] == 5000
    count, unique = case.conn.execute("SELECT COUNT(*),COUNT(DISTINCT op_id) FROM Schedule WHERE version=?", (version,)).fetchone()
    assert count == unique == 5000
    plan_ref = result["data"]["official_plan"]["plan_ref"]
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchTaskRefs WHERE plan_ref=?", (plan_ref,)).fetchone()[0] == 5000
    assert_retained(before, snapshot(case.conn))
    assert compute_seconds < 180 and preview_seconds < 60 and adopt_seconds < 60
    print(f"BX 5000 timings compute={compute_seconds:.3f}s preview={preview_seconds:.3f}s adopt={adopt_seconds:.3f}s")
