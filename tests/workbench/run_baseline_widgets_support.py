"""BZ-only source probe: real admission captures, engine and isolated read-only HTTP."""

import hashlib
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from flask import Blueprint, Flask, g, jsonify, request

from core.infrastructure.migration_state import current_schema_contract_issues
from core.services.workbench.run_candidate_facts import _columns
from tests.workbench.test_run_candidate_baseline_support import original_plan
from tests.workbench.test_run_candidate_support import connect, corrupt_update
from tests.workbench.test_run_candidate_widgets_support import compute, digest
from tests.workbench.test_run_jobs_support import JobCase
from web.routes.workbench.run_candidate_baseline import register_run_candidate_baseline_routes
from web.routes.workbench.run_candidates import register_run_candidate_routes


def record(case, settings=None):
    run, refs = compute(case, settings)
    return {"run_ref": run, "candidate_ref": refs[0], "refs": refs}


def historical_segment(case, run_ref, operation):
    """Historical-shape injection, matching BU's test; never alter the live schema."""
    raw = case.conn.execute("SELECT facts_json,baseline_json FROM WorkbenchRunJobs WHERE run_ref=?", (run_ref,)).fetchone()
    facts, baseline = json.loads(raw[0]), json.loads(raw[1])

    def columns(table):
        sql = next(r[3] for r in facts["schema"] if r[0:2] == ["table", table])
        return _columns(sql, table)

    old = next(r for r in baseline["rows"] if r["op_id"] == operation)
    new = dict(old, id=max(r["id"] for r in baseline["rows"]) + 1, start_time="2026-09-12T09:00:00", end_time="2026-09-12T11:00:00")
    baseline["rows"].append(new)
    facts["tables"]["Schedule"].append([new[k] for k in columns("Schedule")])
    names = columns("WorkbenchPlanSourceRefs")
    source = list(next(r for r in facts["tables"]["WorkbenchPlanSourceRefs"] if r[names.index("kind")] == "schedule_row" and r[names.index("source_key")] == str(old["id"])))
    old_ref, new_ref = source[names.index("ref")], secrets.token_hex(24)
    source[names.index("ref")] = new_ref
    source[names.index("source_key")] = str(new["id"])
    facts["tables"]["WorkbenchPlanSourceRefs"].append(source)
    names = columns("WorkbenchTaskRefs")
    task = list(next(r for r in facts["tables"]["WorkbenchTaskRefs"] if r[names.index("row_ref")] == old_ref))
    task[names.index("ref")] = secrets.token_hex(24)
    task[names.index("row_ref")] = new_ref
    facts["tables"]["WorkbenchTaskRefs"].append(task)
    encoded = json.dumps(facts, ensure_ascii=False)
    corrupt_update(case.conn, "WorkbenchRunJobs", "UPDATE WorkbenchRunJobs SET facts_json=?,facts_hash=?,baseline_json=? WHERE run_ref=?",
                   (encoded, hashlib.sha256(encoded.encode("utf-8")).hexdigest(), json.dumps(baseline), run_ref))


def small_cases(case):
    short = case.operation(seq=2, unit_hours=0.001)
    multi = case.operation(seq=3)
    case.operation(seq=4)
    case.conn.commit()
    result = {"no_baseline": record(case)}
    # Zero quantity is a valid point; unreadiness must be the real exclusion.
    case.batch("UNREADY", quantity=3, ready_status="no")
    unready = case.operation("UNREADY")
    case.batch("OUTSIDE")
    outside = case.operation("OUTSIDE")
    case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M2','Admission old lathe','T1')")
    case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O2','Admission old operator')")
    case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O2','M2')")
    original_plan(case, [case.op_id, short, multi, unready, outside], start="2026-09-12T08:00:00", end="2026-09-12T10:00:00")
    case.conn.execute("UPDATE Schedule SET machine_id='M2',operator_id='O2' WHERE op_id=?", (case.op_id,))
    case.conn.commit()
    result["mixed"] = record(case, case.settings("B1", "UNREADY"))
    case.command("create", case.task(7, case.op_id), case.values(3, effective_processing_hours=0))
    result["execution"] = record(case, case.settings("B1", "UNREADY"))
    historical_segment(case, result["mixed"]["run_ref"], multi)
    case.conn.execute("UPDATE Machines SET name='CURRENT RENAMED MACHINE'")
    case.conn.execute("UPDATE Operators SET name='CURRENT RENAMED OPERATOR'")
    case.conn.execute("UPDATE Parts SET part_name='CURRENT RENAMED PART'")
    case.conn.commit()
    return result


def capacity_case(case):
    codes = ["B1"] + [f"BZ-{i:03d}" for i in range(1, 100)]
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0.001")
    for index, code in enumerate(codes):
        machine, operator = ("M1", "O1") if not index else (f"BZ-M{index:03d}", f"BZ-O{index:03d}")
        if index:
            case.batch(code)
            case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES (?,?,'T1')", (machine, machine))
            case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES (?,?)", (operator, operator))
            case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)", (operator, machine))
        for sequence in range(2 if not index else 1, 51):
            case.operation(code, sequence, machine_id=machine, operator_id=operator, unit_hours=0.001)
    case.conn.execute("INSERT INTO ScheduleHistory(version,strategy,schedule_time,result_status,result_summary) VALUES (7,'bz-capacity','2026-09-09T08:00:00','success','{}')")
    start = datetime(2026, 9, 12, 8)
    operations = list(case.conn.execute("SELECT id,machine_id,operator_id,seq FROM BatchOperations ORDER BY id"))
    case.conn.executemany("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time) VALUES (7,?,?,?,?,?)", [
        (r[0], r[1], r[2], (start + timedelta(seconds=(r[3] - 1) * 30)).isoformat(),
         (start + timedelta(seconds=r[3] * 30)).isoformat()) for r in operations])
    case.conn.commit()
    case.config(time_budget_seconds=600)
    result = record(case, case.settings(*codes))
    assert len(result["refs"]) == 4
    assert all(row[0] == 5000 for row in case.conn.execute("SELECT task_count FROM WorkbenchRunCandidates"))
    return result


class BaselineWidgetServer:
    def __init__(self, case, output):
        output = Path(output)
        small, large = output / "baseline-small.sqlite", output / "baseline-5000.sqlite"
        with connect(large) as conn:
            case.conn.backup(conn)
            large_case = JobCase(conn)
            large_case.op_id = case.op_id
            capacity = capacity_case(large_case)
        self.cases = small_cases(case)
        self.cases["capacity"] = capacity
        with connect(small) as conn:
            case.conn.backup(conn)
        self.paths = {ref: large if key == "capacity" else small for key, row in self.cases.items() for ref in row["refs"]}
        self.before = {}
        for path in set(self.paths.values()):
            with connect(path) as conn:
                self.before[path] = digest(conn)
        self.app = Flask("bz-baseline-widgets")
        bp = Blueprint("bz_baseline", __name__)
        register_run_candidate_routes(bp)
        register_run_candidate_baseline_routes(bp)
        self.app.register_blueprint(bp)
        self.journal, self.connections = [], []
        self.register(small)

    def register(self, default_path):
        @self.app.before_request
        def bind():
            if request.path.startswith("/api/"):
                ref = (request.view_args or {}).get("candidate_ref")
                path = self.paths.get(ref, default_path)
                self.connections.append(path)
                g.db = connect(path)
                g.db.execute("PRAGMA query_only=ON")

        @self.app.after_request
        def record_response(response):
            if request.path.startswith("/api/"):
                self.journal.append({"method": request.method, "path": request.path, "query": dict(request.args), "status": response.status_code})
            return response

        @self.app.teardown_request
        def close(_error):
            conn = g.pop("db", None)
            if conn is not None:
                conn.close()

        @self.app.route("/fixture/cases")
        def cases():
            return jsonify(self.cases)

    def proof(self):
        databases = []
        for path, before in self.before.items():
            with connect(path) as conn:
                databases.append({"path": str(path), "before_sha256": before, "after_sha256": digest(conn),
                                  "schema_contract_issues": current_schema_contract_issues(conn),
                                  "schema_version": conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0]})
        return {"databases": databases, "source_data_retained": all(r["before_sha256"] == r["after_sha256"] for r in databases),
                "all_connections_isolated": bool(self.connections) and set(self.connections) <= set(self.before),
                "read_only_http": all(r["method"] == "GET" for r in self.journal), "journal": self.journal,
                "fixture_facts": ["real worker four candidates per run", "5000 baseline and 4 x 5000 candidate rows",
                                  "explicit historical multi-segment archive injection (current admission rejects duplicates)",
                                  "real completed production report", "renamed current metadata after admission"]}
