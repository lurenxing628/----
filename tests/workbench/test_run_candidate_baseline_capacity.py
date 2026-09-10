"""5000 actual baseline rows and 4 x 5000 engine rows, with bounded SQL/output."""

import time
from datetime import datetime, timedelta

from tests.workbench.run_candidate_baseline_support import api
from tests.workbench.run_candidate_support import BASE, compute, public, retained
from tests.workbench.run_candidate_support import candidate_case as _candidate_case


def test_real_5000_baseline_rows_and_four_candidates_bounded_complete_read(candidate_case):
    case = candidate_case
    codes = ["B1"] + [f"BU-{index:03d}" for index in range(1, 100)]
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0.001")
    for index, code in enumerate(codes):
        machine, operator = ("M1", "O1") if not index else (f"BU-M{index:03d}", f"BU-O{index:03d}")
        if index:
            case.batch(code)
            case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES (?,?,'T1')", (machine, machine))
            case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES (?,?)", (operator, operator))
            case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)", (operator, machine))
        for sequence in range(2 if not index else 1, 51):
            case.operation(code, sequence, machine_id=machine, operator_id=operator, unit_hours=0.001)
    case.conn.execute("INSERT INTO ScheduleHistory(version,strategy,schedule_time,result_status,result_summary) VALUES (7,'bu-capacity','2026-09-09T08:00:00','success','{}')")
    start = datetime(2026, 9, 12, 8)
    operations = list(case.conn.execute("SELECT id,machine_id,operator_id,seq FROM BatchOperations ORDER BY id"))
    case.conn.executemany("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time) VALUES (7,?,?,?,?,?)", [
        (row[0], row[1], row[2], (start + timedelta(seconds=(row[3] - 1) * 30)).isoformat(),
         (start + timedelta(seconds=row[3] * 30)).isoformat()) for row in operations])
    case.conn.commit()
    case.config(time_budget_seconds=600)
    started = time.monotonic()
    _, refs = compute(case, case.settings(*codes))
    generation_seconds = time.monotonic() - started
    assert len(refs) == 4
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks").fetchone()[0] == 20000
    client, statements = api(case)
    measurements = []
    with retained(case.conn):
        for ref in refs:
            statements.clear()
            started = time.monotonic()
            response = client.get(BASE + "/candidates/" + ref + "/baseline")
            seconds = time.monotonic() - started
            assert response.status_code == 200, response.get_data(as_text=True)[:1000]
            payload = response.get_json()
            public(payload)
            data = payload["data"]
            assert data["rows_complete"] and data["operation_count"] == data["full_operation_count"] == 5000
            assert len(data["comparisons"]) == data["baseline"]["captured_task_count"] == 5000
            assert data["counts"] == {"matched": 5000}
            assert len({row["operation_ref"] for row in data["comparisons"]}) == 5000
            assert len({row["row_ref"] for row in data["comparisons"]}) == 5000
            count = len([sql for sql in statements if sql.startswith("SELECT")])
            assert count <= 14 and len(response.data) <= 32 * 1024 * 1024
            measurements.append({"seconds": seconds, "selects": count, "response_bytes": len(response.data)})
    print({"generation_seconds": generation_seconds, "baseline_reads": measurements})
