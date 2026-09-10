"""CN-owned fixtures: real schema, worker, trial services and isolated SQLite only."""

import json
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

from flask import Blueprint, Flask, g, jsonify, request

from core.infrastructure.database import ensure_schema, get_connection
from core.infrastructure.workbench_trial_schema import TRIAL_TABLES
from core.services.scheduler.config.config_field_spec import default_snapshot_values
from core.services.workbench.run_worker import WorkbenchRunWorker
from core.services.workbench.trial import WorkbenchTrialService
from tests.workbench.test_run_jobs_support import JobCase
from web.routes.workbench.plan_reads import register_plan_read_routes
from web.routes.workbench.run_candidates import register_run_candidate_routes
from web.routes.workbench.run_history import register_run_history_routes
from web.routes.workbench.trial import register_trial_routes
from web.routes.workbench.write_context import issue_write_context, validate_write_context

TRIAL_WIDGET_SOURCES = (
    "resource-contract.js", "ResourceControls.jsx", "WorkbenchControlStyles.jsx",
    "PointContract.js", "PointGantt.jsx",
    "WorkbenchCaption.jsx", "WorkbenchPageContext.jsx", "TrialContract.js", "TrialAPI.js", "TrialSession.js", "TrialExport.js",
    "TrialControls.jsx", "TrialViewState.js", "TrialCatalog.jsx", "TrialGantt.jsx", "TrialDetails.jsx",
    "TrialResults.jsx", "TrialStyles.jsx", "TrialWorkspace.jsx",
)


def connect(path):
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def snapshot(conn):
    return {name: [tuple((type(v).__name__, v) for v in row) for row in conn.execute('SELECT rowid,* FROM "' + name + '" ORDER BY rowid')]
            for name, in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")}


def service(conn):
    return WorkbenchTrialService(conn, context_factory=issue_write_context, context_validator=validate_write_context,
                                 actor_provider=lambda: "CN fixture operator")


def seed(path, app):
    root = Path(__file__).resolve().parents[2]
    ensure_schema(str(path), schema_path=str(root / "schema.sql"), backup_dir=None)
    with connect(path) as conn, app.app_context():
        conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','精加工')")
        conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','回转壳体与定位组件')")
        for i in (1, 2, 3):
            conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES (?,?,'T1')", ("M" + str(i), "加工中心 " + str(i)))
            conn.execute("INSERT INTO Operators(operator_id,name) VALUES (?,?)", ("O" + str(i), "操作员 " + str(i)))
            conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)", ("O" + str(i), "M" + str(i)))
        for key, value in default_snapshot_values().items():
            conn.execute("INSERT OR REPLACE INTO ScheduleConfig(config_key,config_value) VALUES (?,?)", (key, str(value)))
        case = JobCase(conn)
        for code in ("B1", "B2"):
            case.batch(code)
        # The single piece-A must cover the entire batch, including saved bases.
        case.batch("B3", quantity=1)
        first = case.operation(unit_hours=1, op_type_name="壳体外圆精加工")
        # Three pieces at ten seconds each keep real adjacent tasks below 5px at full width.
        short = case.operation(seq=2, unit_hours=1 / 360, op_type_name="短时检验")
        adjacent = case.operation(seq=3, unit_hours=1 / 360, op_type_name="相邻短时复检")
        locked = case.operation("B2", machine_id="M2", operator_id="O2", op_type_name="固定基准件")
        piece = case.operation("B3", piece_id="piece-A", unit_hours=0.5, machine_id="M3", operator_id="O3", op_type_name="分件精加工")
        ids = [first, short, adjacent, locked, piece]
        case.config(algo_mode="greedy", graph_candidate_weight_count=3, time_budget_seconds=60,
                    ortools_enabled="no", freeze_window_enabled="no")
        for version in range(1, 13):
            case.plan(version, ids, start="2026-09-09T08:00:00", end="2026-09-09T11:00:00")
        for op_id, machine, operator, start, end in (
            (short, "M1", "O1", "11:00:00", "11:00:30"), (adjacent, "M1", "O1", "11:00:30", "11:01:00"),
            (locked, "M2", "O2", "08:00:00", "08:45:00"), (piece, "M3", "O3", "10:00:00", "10:30:00"),
        ):
            conn.execute("UPDATE Schedule SET machine_id=?,operator_id=?,start_time=?,end_time=? WHERE op_id=?",
                         (machine, operator, "2026-09-09T" + start, "2026-09-09T" + end, op_id))
        conn.execute("UPDATE Schedule SET lock_status='locked' WHERE op_id=?", (locked,))
        conn.execute("CREATE TABLE CNRetainedValues(id INTEGER PRIMARY KEY, value)")
        for i, value in enumerate((None, 12, 1.5, "中文原值", b"\x00\xffold")):
            conn.execute("INSERT INTO CNRetainedValues VALUES (?,?)", (i, value))
        conn.commit()
        accepted = case.accept(settings=case.settings("B1", "B2"))
        run = WorkbenchRunWorker(conn, clock=lambda: datetime(2026, 9, 10, 12, 0, 1)).execute(accepted["run_ref"])
        assert run["state"] in ("complete", "partial"), run
        candidate = next(row for row in run["candidates"] if row["status"] == "completed")
        value = {"base": {"plan_ref": case.plan_ref(12)}}
        refs = []
        for index in range(12):
            preview = service(conn).preview_create(value)
            draft = service(conn).create(value, preview["write_context"]["write_token"], f"CN-seed-create-{index:08d}")["data"]
            refs.append(draft["draft_ref"])
            if index < 2:
                service(conn).save(draft["draft_ref"], {"name": "已存场景 " + str(index + 1)}, draft["write_context"]["write_token"], f"CN-seed-save-{index:08d}")
        return {"plan_ref": case.plan_ref(12), "candidate_ref": candidate["candidate_ref"], "run_ref": accepted["run_ref"], "drafts": refs,
                "machines": {"M" + str(i): case.ref("machine", "M" + str(i)) for i in (1, 2, 3)},
                "operators": {"O" + str(i): case.ref("operator", "O" + str(i)) for i in (1, 2, 3)}}


def large_plan(conn):
    case = JobCase(conn)
    case.batch("CN-LARGE", quantity=1)
    ids = [case.operation("CN-LARGE", seq=i, unit_hours=1 / 3600, op_type_name="连续短工序 " + str(i)) for i in range(1, 1001)]
    case.plan(13, ids, start="2026-09-09T08:00:00", end="2026-09-09T09:00:00")
    start = datetime(2026, 9, 9, 8)
    conn.executemany("UPDATE Schedule SET start_time=?,end_time=? WHERE version=13 AND op_id=?", [
        ((start + timedelta(seconds=i)).isoformat(), (start + timedelta(seconds=i + 1)).isoformat(), op_id) for i, op_id in enumerate(ids)])
    conn.commit()
    return {"plan_ref": case.plan_ref(13)}


class TrialWidgetServer:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.app = Flask("cn-trial-widgets")
        self.seed = self.root / "trial-seed.sqlite"
        self.refs = seed(self.seed, self.app)
        self.path = None
        self.connections, self.journal, self.proofs, self.fixture_changes = [], [], [], []
        self.started, self.release = threading.Event(), threading.Event()
        self.paused = False
        bp = Blueprint("workbench", __name__)
        register_trial_routes(bp)
        register_plan_read_routes(bp)
        register_run_history_routes(bp)
        register_run_candidate_routes(bp)
        self.app.register_blueprint(bp)
        self.register()
        self.reset()

    def connect(self):
        self.path.resolve().relative_to(self.root)
        self.connections.append(str(self.path))
        return connect(self.path)

    def request_connection(self):
        self.path.resolve().relative_to(self.root)
        self.connections.append(str(self.path))
        return get_connection(str(self.path))

    def reset(self, large=False):
        if self.path:
            self.prove()
        self.path = self.root / ("trial-" + secrets.token_hex(8) + ".sqlite")
        with connect(self.seed) as source, self.connect() as conn:
            source.backup(conn)
            self.current = {**self.refs, **(large_plan(conn) if large else {})}
            self.before = snapshot(conn)
        self.paused = False
        self.started.clear()
        self.release.clear()
        return self.current

    def prove(self):
        with self.connect() as conn:
            after = snapshot(conn)
            for table in self.before:
                if table not in set(TRIAL_TABLES) | {"WorkbenchCommandReceipts"}:
                    assert self.before[table] == after[table], table
            for row in conn.execute("SELECT request_key,outcome_json FROM WorkbenchCommandReceipts WHERE action LIKE 'trial.%'"):
                data = json.loads(row[1])["data"]
                if "tasks" in data:
                    assert data["task_count"] == len(data["tasks"])
                    table, key = ("WorkbenchTrialScenarioRows", "scenario_ref") if "scenario_ref" in data else ("WorkbenchTrialRows", "draft_ref")
                    assert conn.execute("SELECT COUNT(*) FROM " + table + " WHERE " + key + "=?", (data[key],)).fetchone()[0] == data["task_count"]
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        self.proofs.append({"database": str(self.path), "legacy_rows_and_types_retained": True, "receipt_task_counts_match_sqlite": True})

    def evidence(self):
        with self.connect() as conn:
            drafts = [dict(r) for r in conn.execute("SELECT draft_ref,status,revision,row_count FROM WorkbenchTrialDrafts")]
            scenarios = [dict(r) for r in conn.execute("SELECT scenario_ref,draft_ref,name FROM WorkbenchTrialScenarios")]
            rows = [{"task_ref": r[0], "draft_ref": r[1], "current": json.loads(r[2]), "original_json": r[3]} for r in conn.execute(
                "SELECT task_ref,draft_ref,current_json,original_json FROM WorkbenchTrialRows")]
            receipts = [dict(r) for r in conn.execute("SELECT request_key,action,receipt_ref FROM WorkbenchCommandReceipts WHERE request_key LIKE 'trial-%'")]
        return {"drafts": drafts, "scenarios": scenarios, "rows": rows, "receipts": receipts, "journal": self.journal, "started": self.started.is_set(), "refs": self.current}

    def register(self):
        @self.app.before_request
        def bind():
            if request.path.startswith("/api/"):
                g.db = self.request_connection()
                if self.paused and request.method == "POST" and request.path.endswith("/change"):
                    self.started.set()
                    if not self.release.wait(timeout=40):
                        raise RuntimeError("CN fixture release timeout")

        @self.app.after_request
        def record(response):
            if request.path.startswith("/api/"):
                row = {"database": str(self.path), "method": request.method, "path": request.path, "query": dict(request.args), "status": response.status_code}
                body = request.get_json(silent=True)
                if body and "request_key" in body:
                    row.update(request_key=body["request_key"], input=body["input"])
                self.journal.append(row)
            return response

        @self.app.teardown_request
        def close(_error):
            conn = g.pop("db", None)
            if conn is not None:
                conn.close()

        @self.app.route("/fixture/reset", methods=["POST"])
        def reset():
            return jsonify(self.reset(large=(request.get_json(silent=True) or {}).get("large", False)))

        @self.app.route("/fixture/evidence")
        def evidence():
            return jsonify(self.evidence())

        @self.app.route("/fixture/control", methods=["POST"])
        def control():
            action = request.get_json()["action"]
            if action == "expire":
                self.app.extensions.pop("aps_public_opaque_tokens", None)
            elif action == "pause":
                self.paused = True
            elif action == "release":
                self.paused = False
                self.release.set()
            elif action == "drift":
                self.prove()
                with self.connect() as conn:
                    before = snapshot(conn)
                    conn.execute("UPDATE Machines SET name='Changed fixture machine' WHERE machine_id='M1'")
                    conn.commit()
                    after = snapshot(conn)
                    changed = [name for name in before if before[name] != after[name]]
                    assert set(changed) == {"Machines", "WorkbenchEntityRefs"}
                    self.fixture_changes.append({"database": str(self.path), "action": "explicit_machine_drift", "tables": changed})
                    self.before.update({name: after[name] for name in changed})
            else:
                raise ValueError("Unknown fixture action")
            return jsonify({"ok": True})

    def proof(self):
        self.prove()
        return {"databases": self.proofs, "journal": self.journal, "explicit_fixture_changes": self.fixture_changes, "business_results_mocked": False,
                "request_connection": "core.infrastructure.database.get_connection",
                "all_connections_isolated": bool(self.connections) and all(Path(p).parent == self.root for p in self.connections)}


def serve_preview():
    """Explicit local-only preview runner; every launch allocates a fresh fixture root."""
    import os
    import subprocess
    import tempfile

    from werkzeug.serving import make_server

    from tests.workbench.test_live_browser import runtime_tools

    root = Path(tempfile.mkdtemp(prefix="aps-cn-trial-preview-"))
    backend = TrialWidgetServer(root)
    server = make_server("127.0.0.1", 0, backend.app, threaded=True)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    node, _browser, modules = runtime_tools()
    process = subprocess.Popen([node, str(Path(__file__).with_name("trial_widgets_probe.cjs")), str(root),
                                "http://127.0.0.1:" + str(server.server_port), json.dumps(TRIAL_WIDGET_SOURCES)],
                               env=dict(os.environ, NODE_PATH=modules, TRIAL_WIDGET_PREVIEW="1"))
    try:
        process.wait()
    finally:
        backend.release.set()
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        server.shutdown()
        thread.join(timeout=10)
        server.server_close()


if __name__ == "__main__":
    serve_preview()
