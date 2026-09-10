"""CB-only fixture: real worker/adoption, isolated v26 SQLite, no production switch."""

import json
import secrets
import threading
from pathlib import Path

from flask import Blueprint, Flask, g, jsonify, request

from tests.workbench.test_run_candidate_adoption_support import assert_retained, snapshot
from tests.workbench.test_run_candidate_support import connect
from tests.workbench.test_run_candidate_widgets_support import compute
from tests.workbench.test_run_jobs_support import JobCase
from web.routes.workbench.materials import command_receipt
from web.routes.workbench.run_candidate_adoption import register_run_candidate_adoption_routes
from web.routes.workbench.run_candidates import register_run_candidate_routes


class AdoptionWidgetServer:
    def __init__(self, case, output):
        self.root = Path(output).resolve()
        self.seed = self.root / "adoption-seed.sqlite"
        case.operation(seq=2)
        case.plan(3, [case.op_id])
        case.conn.execute("UPDATE ScheduleHistory SET result_summary=? WHERE version=3", (b"\x00\xffold-summary",))
        case.plan(7, [case.op_id])
        case.conn.execute("INSERT INTO ScheduleVersionSeq(version) VALUES (40)")
        case.conn.execute("CREATE TABLE CBRetainedValues(id INTEGER PRIMARY KEY, value)")
        for index, value in enumerate((None, 7, 1.25, "old-text", b"\x00\x80\xff")):
            case.conn.execute("INSERT INTO CBRetainedValues VALUES (?,?)", (index, value))
        case.conn.execute("INSERT INTO OperationLogs(log_level,module,action,detail) VALUES ('INFO','old','old',?)", (b"\xffaudit",))
        case.conn.commit()
        with connect(self.seed) as conn:
            case.conn.backup(conn)
        self.app = Flask("cb-adoption-widgets")
        self.app.config["WORKBENCH_CANDIDATE_ADOPTION_ENABLED"] = True
        bp = Blueprint("workbench", __name__)
        register_run_candidate_adoption_routes(bp)
        register_run_candidate_routes(bp)
        bp.add_url_rule("/api/workbench/v1/commands/<request_key>", view_func=command_receipt, methods=["GET"])
        self.app.register_blueprint(bp)
        self.path = None
        self.journal, self.proofs, self.connections = [], [], []
        self.release, self.started = threading.Event(), threading.Event()
        self.register()

    def connect(self):
        self.path.resolve().relative_to(self.root)
        self.connections.append(str(self.path))
        return connect(self.path)

    def capture_proof(self):
        if self.path is None:
            return
        with self.connect() as conn:
            after = snapshot(conn)
            assert_retained(self.before, after)
            rows = list(conn.execute("SELECT version,result_summary FROM ScheduleHistory WHERE version>7"))
            receipts = list(conn.execute("SELECT request_key,outcome_json FROM WorkbenchCommandReceipts WHERE action='scheduling.candidate.adopt'"))
            assert len(rows) <= 1 and len(rows) == len(receipts)
            if rows:
                assert rows[0][0] == 41
                audit, result = json.loads(rows[0][1]), json.loads(receipts[0][1])["data"]
                assert result["official_plan"]["version"] == 41
                assert audit["reason"] and audit["declared_operator"]
                assert result["row_count"] == conn.execute("SELECT COUNT(*) FROM Schedule WHERE version=41").fetchone()[0]
            self.proofs.append({"database": str(self.path), "old_rows_and_storage_types_retained": True,
                                "new_versions": len(rows), "adoption_receipts": len(receipts),
                                "unchanged_without_adoption": bool(rows) or self.before == after})

    def reset(self, mode):
        self.capture_proof()
        self.path = self.root / ("adoption-" + secrets.token_hex(8) + ".sqlite")
        with connect(self.seed) as source, self.connect() as conn:
            source.backup(conn)
            case = JobCase(conn)
            if mode == "empty":
                conn.execute("DELETE FROM Schedule")
                conn.execute("DELETE FROM ScheduleHistory")
                conn.commit()
            if mode == "partial":
                case.batch("B2", ready_status="no")
                case.operation("B2")
                conn.commit()
            with self.app.app_context():
                run, refs = compute(case, case.settings("B1", "B2") if mode == "partial" else None)
            self.before = snapshot(conn)
        self.app.config["WORKBENCH_CANDIDATE_ADOPTION_ENABLED"] = mode != "disabled"
        self.release.clear()
        self.started.clear()
        self.mode = mode
        self.current = {"run_ref": run, "candidate_ref": refs[0], "other_ref": refs[1]}
        return self.current

    def register(self):
        @self.app.before_request
        def bind():
            if request.path.startswith("/api/"):
                g.db = self.connect()
                if request.path.endswith("/adopt") and self.mode == "paused":
                    self.started.set()
                    if not self.release.wait(timeout=40):
                        raise RuntimeError("Fixture release timed out")

        @self.app.after_request
        def record(response):
            if request.path.startswith("/api/"):
                row = {"database": str(self.path), "path": request.path, "method": request.method, "status": response.status_code}
                if request.path.endswith("/adopt"):
                    body = request.get_json()
                    row.update(request_key=body["request_key"], fields=sorted(body), input=body["input"])
                self.journal.append(row)
                if request.path.endswith("/adopt-preview"):
                    assert snapshot(g.db) == self.before, "Preview changed SQLite"
            return response

        @self.app.teardown_request
        def close(_error):
            conn = g.pop("db", None)
            if conn is not None:
                conn.close()

        @self.app.route("/fixture/reset", methods=["POST"])
        def reset():
            return jsonify(self.reset(request.get_json()["mode"]))

        @self.app.route("/fixture/control", methods=["POST"])
        def control():
            action = request.get_json()["action"]
            if action == "drift":
                with self.connect() as conn:
                    conn.execute("UPDATE Machines SET name='Changed after preview'")
                    conn.commit()
                    self.before = snapshot(conn)
            elif action == "expire":
                self.app.extensions.pop("aps_public_opaque_tokens", None)
            elif action == "release":
                self.release.set()
            elif action == "enable":
                self.app.config["WORKBENCH_CANDIDATE_ADOPTION_ENABLED"] = True
            else:
                raise ValueError("Unknown adoption fixture action")
            return jsonify({"ok": True})

        @self.app.route("/fixture/evidence")
        def evidence():
            with self.connect() as conn:
                receipts = conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts WHERE action='scheduling.candidate.adopt'").fetchone()[0]
            return jsonify({"journal": self.journal, "receipts": receipts, "started": self.started.is_set(), "case": self.current})

    def proof(self):
        self.capture_proof()
        return {"databases": self.proofs, "journal": self.journal,
                "all_connections_isolated": bool(self.connections) and all(Path(p).parent == self.root for p in self.connections),
                "adoption_core_mocked": False, "production_enabled": False}
