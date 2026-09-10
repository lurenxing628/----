"""5000 real tasks x four persisted candidates; bounded queries and full exports."""

import time

from tests.workbench.run_candidate_support import BASE, api, compute, connect, read, retained
from tests.workbench.run_candidate_support import candidate_case as _candidate_case
from tests.workbench.test_run_candidate_exports import decode


def test_real_5000_by_four_no_n_plus_one_full_csv_xlsx_and_preservation(candidate_case):
    case = candidate_case
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0.001")
    codes = ["B1"] + [f"CAP-{index:03d}" for index in range(1, 100)]
    for code in codes[1:]:
        case.batch(code)
    for index, code in enumerate(codes):
        machine, operator = ("M1", "O1") if not index else (f"CM{index:03d}", f"CO{index:03d}")
        if index:
            case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES (?,?,'T1')", (machine, machine))
            case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES (?,?)", (operator, operator))
            case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)", (operator, machine))
        for sequence in range(2 if not index else 1, 51):
            case.operation(code, sequence, machine_id=machine, operator_id=operator, unit_hours=0.001)
    case.conn.commit()
    case.config(time_budget_seconds=600)
    started = time.monotonic()
    run_ref, refs = compute(case, case.settings(*codes))
    generation_seconds = time.monotonic() - started
    assert len(refs) == 4
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks").fetchone()[0] == 20000
    client, statements = api(case)
    timings = {}
    with retained(case.conn):
        started = time.monotonic()
        catalog = read(client, "/runs/" + run_ref + "/candidates", size=1)
        assert catalog["data"]["page"]["total"] == 4
        assert len([sql for sql in statements if sql.startswith("SELECT")]) <= 9
        timings["catalog"] = time.monotonic() - started
        for ref in refs:
            statements.clear()
            started = time.monotonic()
            result = read(client, "/candidates/" + ref)
            assert result["data"]["task_count"] == len(result["data"]["tasks"]) == 5000
            assert len({task["row_ref"] for task in result["data"]["tasks"]}) == 5000
            assert len([sql for sql in statements if sql.startswith("SELECT")]) <= 14
            timings["workspace"] = max(timings.get("workspace", 0), time.monotonic() - started)
        for fmt in ("csv", "xlsx"):
            statements.clear()
            started = time.monotonic()
            response = client.get(BASE + "/candidates/" + refs[-1] + "/export", query_string={"format": fmt, "snapshot_ref": result["meta"]["snapshot_ref"]})
            assert response.status_code == 200 and response.headers["X-Workbench-Row-Count"] == "5000"
            headers, rows = decode(response, fmt)
            assert [row[headers.index("行引用")] for row in rows] == [task["row_ref"] for task in result["data"]["tasks"]]
            assert len([sql for sql in statements if sql.startswith("SELECT")]) <= 14
            timings[fmt] = time.monotonic() - started
        with connect(case.path) as reopened:
            count = reopened.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks").fetchone()[0]
            assert count == 20000
    print({"generation_seconds": generation_seconds, "read_and_decode_seconds": timings})
