"""BP-only HTTP fixture: fresh current schema, real scheduler, then read-only SQLite."""

import hashlib
import json
import secrets
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path

from flask import Blueprint, Flask, g, jsonify, request

from core.infrastructure.migration_state import current_schema_contract_issues
from core.services.workbench.run_worker import WorkbenchRunWorker
from tests.workbench.test_run_candidate_support import connect, corrupt_update
from web.routes.workbench.run_candidate_baseline import register_run_candidate_baseline_routes
from web.routes.workbench.run_candidates import register_run_candidate_routes
from web.routes.workbench.run_history import register_run_history_routes


def digest(conn):
    return hashlib.sha256("\n".join(conn.iterdump()).encode("utf-8")).hexdigest()


def compute(case, settings=None):
    accepted = case.accept(key="run-" + secrets.token_hex(24), settings=settings)
    result = WorkbenchRunWorker(case.conn, clock=lambda: datetime(2026, 9, 10, 12, 1)).execute(accepted["run_ref"])
    return result["run_ref"], [row["candidate_ref"] for row in result["candidates"]]


def fixtures(case):
    case.operation(seq=2, unit_hours=0.001)
    case.operation(seq=3, unit_hours=2)
    case.conn.commit()
    run, refs = compute(case)
    result = {"complete": {"run_ref": run, "candidate_ref": refs[0], "refs": refs}}
    case.batch("B2", ready_status="no")
    case.operation("B2")
    case.conn.commit()
    run, refs = compute(case, case.settings("B1", "B2"))
    result["partial"] = {"run_ref": run, "candidate_ref": refs[0], "refs": refs}
    run, refs = compute(case)
    receipt = json.loads(case.conn.execute("SELECT result_json FROM WorkbenchRunReceipts WHERE run_ref=?", (run,)).fetchone()[0])
    for ref, status in zip(refs[:2], ("failed", "skipped")):
        corrupt_update(case.conn, "WorkbenchRunCandidateTasks", "DELETE FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (ref,))
        sequence = case.conn.execute("SELECT sequence FROM WorkbenchRunCandidates WHERE candidate_ref=?", (ref,)).fetchone()[0]
        artifact = {"status": status, "sequence": sequence, "label": "Recorded " + status}
        corrupt_update(case.conn, "WorkbenchRunCandidates", "UPDATE WorkbenchRunCandidates SET status=?,task_count=0,artifact_json=? WHERE candidate_ref=?",
                       (status, json.dumps(artifact), ref))
        next(item for item in receipt["candidates"] if item["candidate_ref"] == ref).update(status=status, task_count=0)
        result[status] = {"run_ref": run, "candidate_ref": ref}
    receipt["state"] = "partial"
    corrupt_update(case.conn, "WorkbenchRunJobs", "UPDATE WorkbenchRunJobs SET state='partial' WHERE run_ref=?", (run,))
    corrupt_update(case.conn, "WorkbenchRunReceipts", "UPDATE WorkbenchRunReceipts SET state='partial',result_json=? WHERE run_ref=?", (json.dumps(receipt), run))
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0.001")
    codes = ["B1"] + [f"CAP-{index:03d}" for index in range(1, 100)]
    for index, code in enumerate(codes):
        machine, operator = ("M1", "O1") if not index else (f"CM{index:03d}", f"CO{index:03d}")
        if index:
            case.batch(code)
            case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES (?,?,'T1')", (machine, machine))
            case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES (?,?)", (operator, operator))
            case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)", (operator, machine))
        for seq in range(4 if not index else 1, 51):
            case.operation(code, seq, machine_id=machine, operator_id=operator, unit_hours=0.001)
    case.conn.commit()
    case.config(time_budget_seconds=600)
    run, refs = compute(case, case.settings(*codes))
    result["capacity"] = {"run_ref": run, "candidate_ref": refs[0], "refs": refs}
    assert all(row[0] == 5000 for row in case.conn.execute("SELECT task_count FROM WorkbenchRunCandidates WHERE run_ref=?", (run,)))
    case.conn.execute("UPDATE Machines SET name='CURRENT RENAMED MACHINE' WHERE machine_id='M1'")
    case.conn.execute("UPDATE Parts SET part_name='CURRENT RENAMED PART'")
    case.conn.execute("UPDATE BatchOperations SET op_type_name='CURRENT RENAMED PROCESS'")
    case.conn.commit()
    return result


class CandidateWidgetServer:
    def __init__(self, case, output):
        output = Path(output).resolve()
        root = Path(__file__).resolve().parents[2]
        paths = {Path(__file__).resolve(), root / "schema.sql"}
        paths.update(Path(module.__file__).resolve() for module in list(sys.modules.values())
                     if getattr(module, "__file__", None) and str(module.__file__).endswith(".py"))
        for source in sorted(paths):
            if root not in source.parents:
                continue
            target = output / "sources" / source.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(source), str(target))
        with (output / "fixture-sql-trace.log").open("w", encoding="utf-8") as trace:
            case.conn.set_trace_callback(lambda sql: trace.write(sql + "\n"))
            try:
                self.cases = fixtures(case)
            except Exception:
                (output / "fixture-error.log").write_text(traceback.format_exc(), encoding="utf-8")
                for suffix in ("", "-journal", "-wal", "-shm"):
                    source = Path(str(case.path) + suffix)
                    if source.is_file():
                        shutil.copy2(str(source), str(output / ("failed-original.sqlite" + suffix)))
                (output / "failed-connection.sql").write_text("\n".join(case.conn.iterdump()), encoding="utf-8")
                raise
            finally:
                case.conn.set_trace_callback(None)
        self.path = output / "candidate-widgets.sqlite"
        with connect(self.path) as target:
            case.conn.backup(target)
            self.before = digest(target)
        self.app = Flask("bp-candidate-widgets")
        bp = Blueprint("bp_candidates", __name__)
        register_run_candidate_routes(bp)
        register_run_candidate_baseline_routes(bp)
        register_run_history_routes(bp)
        self.app.register_blueprint(bp)
        self.journal = []
        self.connections = []
        self.statements = []
        self.register()

    def register(self):
        @self.app.before_request
        def bind():
            if request.path.startswith("/api/"):
                self.connections.append(str(self.path))
                g.db = connect(self.path)
                g.db.execute("PRAGMA query_only=ON")
                g.db.set_trace_callback(self.statements.append)

        @self.app.after_request
        def record(response):
            if request.path.startswith("/api/"):
                self.journal.append({"method": request.method, "path": request.path, "status": response.status_code})
            return response

        @self.app.teardown_request
        def close(_error):
            conn = g.pop("db", None)
            if conn is not None:
                conn.close()

        @self.app.route("/fixture/cases")
        def cases():
            return jsonify(self.cases)

        @self.app.route("/fixture/restart", methods=["POST"])
        def restart():
            self.app.extensions.pop("aps_public_opaque_tokens", None)
            return jsonify({"ok": True})

    def verify_baseline_route(self):
        source = self.cases["complete"]
        with self.app.test_client() as client:
            response = client.get("/api/workbench/v1/scheduling/candidates/" + source["candidate_ref"] + "/baseline")
        (self.path.parent / "baseline-route.json").write_text(response.get_data(as_text=True), encoding="utf-8")
        assert response.status_code == 200, response.get_data(as_text=True)
        payload = response.get_json()
        assert payload["ok"] and payload["meta"]["source"] == "production"
        assert payload["data"]["candidate"]["candidate_ref"] == source["candidate_ref"]
        assert payload["data"]["candidate"]["run_ref"] == source["run_ref"]
        assert payload["data"]["rows_complete"] is True

    def proof(self):
        with connect(self.path) as conn:
            return {"database": str(self.path), "schema_version": conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0],
                    "schema_contract_issues": current_schema_contract_issues(conn),
                    "before_sha256": self.before, "after_sha256": digest(conn), "source_data_retained": self.before == digest(conn),
                    "all_connections_isolated": set(self.connections) == {str(self.path)},
                    "read_only_http": all(row["method"] == "GET" for row in self.journal), "journal": self.journal,
                    "sql_trace": self.statements,
                    "injected_fixtures": ["failed/skipped persisted manifest", "renamed current entities after capture"],
                    "fixture_clock": "admission 2026-09-10T12:00:00; worker 2026-09-10T12:01:00",
                    "real_engine": ["complete", "partial", "5000 tasks x four candidates"]}
