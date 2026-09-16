"""BK-only live HTTP fixture. Every SQLite file is below the disposable output root."""

import secrets
import threading
from contextlib import closing
from pathlib import Path

from flask import Blueprint, Flask, g, jsonify, request

from core.services.workbench.run_data_context import RunDataContext
from core.services.workbench.run_jobs import WorkbenchRunService
from core.services.workbench.run_jobs_facts import capture_run_facts
from core.services.workbench.run_worker import WorkbenchRunWorker
from core.services.workbench.system_journal import SystemMaintenanceJournal, file_fingerprint
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from tests.workbench.run_jobs_support import JobCase, connection
from web.routes.workbench.preflight import register_preflight_routes
from web.routes.workbench.run_candidates import register_run_candidate_routes
from web.routes.workbench.scheduling_jobs import register_scheduling_job_routes


class WidgetServer:
    def __init__(self, case, output):
        self.root = Path(output).resolve()
        self.seed = self.root / "seed.sqlite"
        with connection(self.seed) as target:
            case.conn.backup(target)
        self.app = Flask(__name__)
        self.path = None
        self.journal = []
        self.calls = []
        self.worker = None
        self.release = threading.Event()
        self.started = threading.Event()
        self.worker_errors = []
        self.databases = []
        self.proofs = []
        bp = Blueprint("bk_run_widgets", __name__)
        register_preflight_routes(bp)
        register_scheduling_job_routes(bp)
        register_run_candidate_routes(bp)
        self.app.register_blueprint(bp)
        self.register()

    def connect(self, path=None):
        value = Path(path or self.path).resolve()
        value.relative_to(self.root)
        return connection(value)

    def join(self):
        if self.worker:
            self.release.set()
            self.worker.join(timeout=240)
            if self.worker.is_alive():
                raise RuntimeError("Isolated run worker did not finish")
            self.worker = None

    def proof(self):
        if self.path:
            with self.connect() as conn:
                self.proofs.append({"database": str(self.path), "business_facts_unchanged": capture_run_facts(conn) == self.before,
                    "runs": conn.execute("SELECT COUNT(*) FROM WorkbenchRunJobs").fetchone()[0],
                    "candidate_tasks": conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks").fetchone()[0]})

    def reset(self, mode):
        self.join()
        self.proof()
        self.path = self.root / ("run-" + secrets.token_hex(8) + ".sqlite")
        self.databases.append(str(self.path))
        with connection(self.seed) as source, self.connect() as conn:
            source.backup(conn)
            case = JobCase(conn)
            codes = ["B1"]
            if mode == "partial":
                case.batch("B2", ready_status="no")
                case.operation("B2")
                codes.append("B2")
            if mode == "point":
                conn.execute("UPDATE BatchOperations SET unit_hours=0,setup_hours=0")
            if mode == "failed":
                # Positive work lost at datetime precision must fail; exact zero is a valid point.
                conn.execute("UPDATE BatchOperations SET unit_hours=1e-12,setup_hours=0")
            if mode == "capacity":
                conn.execute("UPDATE BatchOperations SET unit_hours=0.001")
                for index in range(100):
                    code = "B1" if index == 0 else f"CAP-{index:03d}"
                    machine, operator = ("M1", "O1") if index == 0 else (f"CM{index:03d}", f"CO{index:03d}")
                    if index:
                        codes.append(code)
                        case.batch(code)
                        conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES (?,?,'T1')", (machine, machine))
                        conn.execute("INSERT INTO Operators(operator_id,name) VALUES (?,?)", (operator, operator))
                        conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)", (operator, machine))
                    for seq in range(2 if index == 0 else 1, 51):
                        case.operation(code, seq, unit_hours=0.001, machine_id=machine, operator_id=operator)
                case.config(time_budget_seconds=600)
            conn.commit()
            self.settings = case.settings(*codes)
            self.before = capture_run_facts(conn)
        self.calls = []
        self.app.extensions["workbench_run_dispatcher"] = self.calls.append
        self.app.config["WORKBENCH_RUN_JOBS_ENABLED"] = True
        self.app.config["BACKUP_DIR"] = str(self.root / "restore-backups")
        self.app.extensions.pop("aps_public_opaque_tokens", None)
        return self.settings

    def restore_scope(self):
        """Fixture-only controlled replacement, using a real registered protection copy."""
        self.join()
        backups = Path(self.app.config["BACKUP_DIR"])
        backups.mkdir(exist_ok=True)
        path = backups / ("aps_backup_" + secrets.token_hex(8) + "_before_restore.db")
        with closing(self.connect()) as conn:
            context = RunDataContext(conn)
            before = context.ref()
            journal = SystemMaintenanceJournal(str(self.path) + ".system-journal", str(self.path))
            row, _ = journal.begin("restore-fixture-" + secrets.token_hex(12), "restore", {})
            with closing(connection(path)) as protection:
                conn.backup(protection)
            with closing(connection(self.seed)) as source:
                source.backup(conn)
            journal.record(row, "succeeded", code="verified", data_context_before=before,
                protection={"filename": path.name, "sha256": file_fingerprint(str(path))})
        self.app.extensions.pop("aps_public_opaque_tokens", None)

    def start(self, run_ref):
        self.join()
        self.release.clear()
        self.started.clear()
        owner, path = self, self.path

        class PausedWorker(WorkbenchRunWorker):
            def _compute(self, row):
                owner.started.set()
                if not owner.release.wait(timeout=120):
                    raise RuntimeError("Fixture worker release was not received")
                return super()._compute(row)

        def execute():
            with owner.app.app_context(), owner.connect(path) as conn:
                try:
                    PausedWorker(conn).execute(run_ref)
                except Exception as error:
                    owner.worker_errors.append(type(error).__name__)
        self.worker = threading.Thread(target=execute)
        self.worker.start()
        if not self.started.wait(timeout=20):
            raise RuntimeError("Fixture worker did not claim the run")

    def register(self):
        @self.app.before_request
        def bind():
            if request.path.startswith("/api/"):
                g.db = self.connect()

        @self.app.after_request
        def record(response):
            if request.path.startswith("/api/"):
                entry = {"path": request.path, "method": request.method, "status": response.status_code}
                if request.path.endswith("/runs") and request.is_json:
                    value = request.get_json()
                    entry.update(request_key=value["request_key"], input_ref=value["input_ref"], fields=sorted(value))
                data = response.get_json()
                if data and data.get("ok"):
                    entry["snapshot_ref"] = data.get("meta", {}).get("snapshot_ref")
                self.journal.append(entry)
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
            value = request.get_json()
            action = value["action"]
            if action == "disable":
                self.app.extensions.pop("workbench_run_dispatcher", None)
            elif action == "missing_schema":
                with self.connect() as conn:
                    conn.execute("DROP INDEX idx_wb_run_state")
                # Deliberate schema fault is part of the test fixture's new baseline.
                with self.connect() as conn:
                    self.before = capture_run_facts(conn)
            elif action == "start":
                self.start(value["run_ref"])
            elif action == "release":
                self.release.set()
            elif action == "restart":
                self.join()
                self.app.extensions.pop("aps_public_opaque_tokens", None)
            elif action == "restore_scope":
                self.restore_scope()
            elif action == "reconcile_unknown":
                with self.connect() as conn:
                    WorkbenchRunRepository(conn).claim(value["run_ref"], "e" * 48, "2026-09-10T12:00:00")
                with self.connect() as conn:
                    WorkbenchRunService(conn).recover_unfinished_runs()
            elif action == "interrupt":
                with self.connect() as conn:
                    WorkbenchRunService(conn).recover_unfinished_runs(executor_is_active=lambda _ref: False)
            else:
                raise ValueError("Unknown fixture control")
            return jsonify({"ok": True, "calls": self.calls})

        @self.app.route("/fixture/evidence")
        def evidence():
            return jsonify({"calls": self.calls, "journal": self.journal})
