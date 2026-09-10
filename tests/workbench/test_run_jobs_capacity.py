"""5000 actual positive-duration tasks, full durable candidates, reopen and original preservation."""

import json
import time

from core.services.workbench.run_jobs_facts import capture_run_facts
from core.services.workbench.run_worker import WorkbenchRunWorker
from tests.workbench.run_jobs_support import connection, service  # noqa: F401
from tests.workbench.run_jobs_support import job_case as _job_case


def test_5000_real_tasks_persist_all_four_candidates(job_case):
    case = job_case
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
    assert case.conn.execute("SELECT COUNT(*) FROM BatchOperations").fetchone()[0] == 5000
    before = capture_run_facts(case.conn)
    started = time.monotonic()
    accepted = case.accept(settings=case.settings(*codes))
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert result["state"] == "complete" and result["result_persisted"]
    assert len(result["candidates"]) == 4 and all(row["task_count"] == 5000 for row in result["candidates"])
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks").fetchone()[0] == 20000
    assert capture_run_facts(case.conn) == before
    for row in case.conn.execute("SELECT artifact_json FROM WorkbenchRunCandidates"):
        artifact = json.loads(row[0])
        assert len(artifact["results"]) == len(artifact["validated_payload"]["schedule_rows"]) == 5000
    with connection(case.path) as restarted:
        assert service(restarted).get(accepted["run_ref"]) == result
    assert time.monotonic() - started < 240
