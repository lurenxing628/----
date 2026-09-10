"""BT isolated HTTP fixture: BQ ledger seeds plus one real scheduler result."""

import hashlib
from datetime import datetime
from pathlib import Path

from flask import Blueprint, Flask, g, jsonify, request

from core.infrastructure.migration_state import current_schema_contract_issues
from core.services.workbench.run_worker import WorkbenchRunWorker
from tests.workbench.run_history_support import connect, seed
from tests.workbench.run_jobs_support import JobCase
from web.routes.workbench.run_candidate_baseline import register_run_candidate_baseline_routes
from web.routes.workbench.run_candidates import register_run_candidate_routes
from web.routes.workbench.run_history import register_run_history_routes


def digest(conn):
    return hashlib.sha256("\n".join(conn.iterdump()).encode("utf-8")).hexdigest()


class HistoryWidgetServer:
    def __init__(self, case, output):
        self.root = Path(output).resolve()
        self.empty_seed = self.root / "bt-history-empty.sqlite"
        with connect(self.empty_seed) as conn:
            case.conn.backup(conn)
        accepted = case.accept()
        result = WorkbenchRunWorker(case.conn, clock=lambda: datetime(2026, 9, 10, 12, 1)).execute(accepted["run_ref"])
        assert result["state"] == "complete" and len(result["candidates"]) == 4
        self.cases = {"real": {"run_ref": result["run_ref"], "candidate_ref": result["candidates"][0]["candidate_ref"]}}
        for index in range(24):
            state = ("queued", "running", "complete", "partial", "failed", "interrupted")[index % 6]
            ref = seed(case, state, accepted=f"2026-09-{index + 1:02d}T09:00:00", counts=(1, 1))
            self.cases.setdefault(state, {"run_ref": ref})
        self.cases["awaiting"] = {"run_ref": seed(case, "running", stage="awaiting_reconciliation", accepted="2026-09-25T09:00:00")}
        self.cases["missing"] = {"run_ref": seed(case, settings={}, accepted="2026-09-26T09:00:00")}
        self.seed_path = self.root / "bt-history-seed.sqlite"
        with connect(self.seed_path) as conn:
            case.conn.backup(conn)
        self.path = None
        self.journal, self.connections, self.proofs, self.statements = [], [], [], []
        self.app = Flask("bt-run-history-widgets")
        bp = Blueprint("bt_history", __name__)
        register_run_history_routes(bp)
        register_run_candidate_routes(bp)
        register_run_candidate_baseline_routes(bp)
        self.app.register_blueprint(bp)
        self.reset()
        self.register()

    def checkpoint(self):
        if self.path is not None:
            with connect(self.path) as conn:
                after = digest(conn)
            self.proofs.append({"database": str(self.path), "before_sha256": self.before,
                                "after_sha256": after, "source_data_retained": self.before == after})

    def reset(self, empty=False):
        self.checkpoint()
        self.path = self.root / (f"bt-history-{len(self.proofs)}.sqlite")
        with connect(self.empty_seed if empty else self.seed_path) as source, connect(self.path) as target:
            source.backup(target)
            self.before = digest(target)
        self.app.extensions.pop("aps_public_opaque_tokens", None)

    def register(self):
        @self.app.before_request
        def bind():
            if request.path.startswith("/api/"):
                self.path.relative_to(self.root)
                self.connections.append(str(self.path))
                g.db = connect(self.path)
                g.db.execute("PRAGMA query_only=ON")
                g.db.set_trace_callback(self.statements.append)

        @self.app.after_request
        def record(response):
            if request.path.startswith("/api/"):
                value = response.get_json(silent=True)
                self.journal.append({"method": request.method, "path": request.path, "query": dict(request.args),
                    "status": response.status_code, "snapshot_ref": value.get("meta", {}).get("snapshot_ref") if value else None})
            return response

        @self.app.teardown_request
        def close(_error):
            conn = g.pop("db", None)
            if conn is not None:
                conn.close()

        @self.app.route("/fixture/cases")
        def cases():
            return jsonify(self.cases)

        @self.app.route("/fixture/control", methods=["POST"])
        def control():
            action = request.get_json()["action"]
            if action == "reset":
                self.reset()
            elif action == "empty":
                self.reset(empty=True)
            elif action == "restart":
                self.app.extensions.pop("aps_public_opaque_tokens", None)
            elif action == "append":
                self.checkpoint()
                with connect(self.path) as conn:
                    seed(JobCase(conn), accepted="2026-09-27T09:00:00")
                    self.before = digest(conn)
            else:
                raise ValueError("Unknown fixture action")
            return jsonify({"ok": True})

    def proof(self):
        self.checkpoint()
        with connect(self.path) as conn:
            version = conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0]
            issues = current_schema_contract_issues(conn)
        return {"schema_version": version, "root": str(self.root), "phases": self.proofs,
            "schema_contract_issues": issues,
            "source_data_retained": all(row["source_data_retained"] for row in self.proofs),
            "read_only_http": bool(self.journal) and all(row["method"] == "GET" for row in self.journal),
            "read_only_sql": bool(self.statements) and all(not sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER")) for sql in self.statements),
            "all_connections_isolated": bool(self.connections) and all(Path(p).parent == self.root for p in self.connections),
            "journal": self.journal, "sql_trace": self.statements, "real_engine": self.cases["real"],
            "injected_fixtures": ["24 synthetic consistent state ledgers", "awaiting reconciliation", "missing admission scope", "explicit directory append between reads"],
            "downloads": "not applicable: history has no export capability"}
