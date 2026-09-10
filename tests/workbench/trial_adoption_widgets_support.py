"""CX isolated fixture: real CQ routes, SQLite and HTTP lifecycle, explicitly enabled."""

import json
import secrets
import threading
from pathlib import Path

from flask import Blueprint, Flask, g, jsonify, request

from core.infrastructure.database import get_connection
from core.infrastructure.workbench_trial_schema import TRIAL_TABLES
from core.services.scheduler import schedule_service
from tests.workbench.test_run_jobs_support import JobCase
from tests.workbench.trial_adoption_support import assert_dashboard_task_appends
from tests.workbench.trial_adoption_support import service as adoption_service
from tests.workbench.trial_support import CommitFailureConnection, change, connect, create, snapshot
from tests.workbench.trial_support import service as trial_service
from web.bootstrap.workbench_request_lifecycle import (
    close_workbench_request_connection,
    install_workbench_request_lifecycle,
    track_workbench_request_connection,
)
from web.routes.workbench.plan_reads import register_plan_read_routes
from web.routes.workbench.trial import register_trial_routes
from web.routes.workbench.trial_adoption import register_trial_adoption_routes


def seed(case, path):
    second = case.operation(seq=2, op_type_name="后序精加工")
    for version in (3, 7):
        case.plan(version, [case.op_id, second], end="2026-09-09T11:00:00")
        case.conn.execute("UPDATE Schedule SET start_time='2026-09-09T11:00:00',end_time='2026-09-09T11:45:00' WHERE version=? AND op_id=?", (version, second))
    case.conn.execute("INSERT INTO ScheduleVersionSeq(version) VALUES (40)")
    case.conn.execute("UPDATE ScheduleHistory SET result_summary=? WHERE version=3", (b"\x00\xffold-summary",))
    case.conn.execute("CREATE TABLE CXRetainedValues(id INTEGER PRIMARY KEY,value)")
    for i, value in enumerate((None, 12, 1.5, "中文原值", b"\x00\xffold")):
        case.conn.execute("INSERT INTO CXRetainedValues VALUES (?,?)", (i, value))
    case.conn.commit()
    case.command("create", case.task(7, case.op_id), case.values(quantity=3, actual_end="2026-09-09T11:00:00"))
    source = {"base": {"plan_ref": case.plan_ref(7)}, "scope": {"query": "not-visible", "range_start": "2026-09-10T08:00:00", "range_end": "2026-09-10T09:00:00"}}
    scenarios = []
    for index in range(3):
        draft = create(case, source, key="cx-seed-create-000" + str(index))
        draft = change(case, draft, task=1, operator="O1" if index == 2 else "O2", key="cx-seed-change-000" + str(index))["data"]
        saved = trial_service(case.conn).save(draft["draft_ref"], {"name": "场景完整采用核对 " + str(index + 1)},
            draft["write_context"]["write_token"], "cx-seed-save-000" + str(index))["data"]
        scenarios.append(saved)
    checked = adoption_service(case.conn).preview(scenarios[0]["scenario_ref"])
    assert checked["validation"]["can_adopt"], checked
    assert not adoption_service(case.conn).preview(scenarios[2]["scenario_ref"])["validation"]["can_adopt"]
    with connect(path) as target:
        case.conn.backup(target)
    return scenarios


class TrialAdoptionWidgetServer:
    def __init__(self, case, output):
        self.root = Path(output).resolve()
        self.seed = self.root / "cx-seed.sqlite"
        self.scenarios = seed(case, self.seed)
        self.path = None
        self.journal, self.proofs, self.connections, self.gates = [], [], [], []
        self.changes = []
        self.release, self.started = threading.Event(), threading.Event()
        self.run_locked = False
        self.app = Flask("cx-trial-adoption-control")
        self.register_controls()
        original = self.app.wsgi_app

        def dispatch(environ, start_response):
            target = self.business if environ["PATH_INFO"].startswith("/api/") else original
            return target(environ, start_response)

        self.app.wsgi_app = dispatch
        self.reset("normal")

    def connect(self, factory=None):
        self.path.resolve().relative_to(self.root)
        self.connections.append(str(self.path))
        return connect(self.path, factory) if factory else get_connection(str(self.path))

    def reset(self, mode):
        self.capture_proof()
        self.release.set()
        if self.run_locked:
            schedule_service._RUN_SCHEDULE_LOCK.release()
            self.run_locked = False
        self.path = self.root / ("cx-" + secrets.token_hex(8) + ".sqlite")
        with connect(self.seed) as source, self.connect() as conn:
            source.backup(conn)
            self.before = snapshot(conn)
        self.mode = mode
        self.release.clear()
        self.started.clear()
        self.install_business()
        selected = self.scenarios[2 if mode == "invalid" else 0]
        self.current = {"scenario_ref": selected["scenario_ref"], "draft_ref": selected["draft_ref"],
                        "other_ref": self.scenarios[1]["scenario_ref"], "baseline_ref": selected["baseline"]["plan_ref"]}
        return self.current

    def install_business(self):
        app = Flask("cx-trial-adoption-business")
        app.config.update(DATABASE_PATH=str(self.path), WORKBENCH_CANDIDATE_ADOPTION_ENABLED=self.mode != "disabled")
        self.gate = install_workbench_request_lifecycle(app)
        self.gates.append(self.gate)
        bp = Blueprint("workbench", __name__)
        register_trial_adoption_routes(bp)
        register_trial_routes(bp)
        register_plan_read_routes(bp)
        app.register_blueprint(bp)

        @app.before_request
        def bind():
            adopt = request.path.endswith("/adopt")
            g.db = self.connect(CommitFailureConnection if adopt and self.mode in ("ack", "rollback") else None)
            track_workbench_request_connection(g.db)
            if adopt and self.mode in ("ack", "rollback"):
                g.db.fail_commit, g.db.acknowledge_only = True, self.mode == "ack"
            if adopt and self.mode == "paused":
                self.started.set()
                if not self.release.wait(40):
                    raise RuntimeError("CX fixture release timeout")

        @app.after_request
        def record(response):
            row = {"database": str(self.path), "method": request.method, "path": request.path, "query": dict(request.args), "status": response.status_code}
            body = request.get_json(silent=True)
            if body is not None:
                row["body_keys"] = sorted(body)
                if "request_key" in body:
                    row.update(request_key=body["request_key"], input=body["input"])
            payload = response.get_json(silent=True)
            if payload and payload.get("ok") is False:
                row.update(committed=payload.get("committed"), error=payload.get("error"))
            if "/adoption-commands/" in request.path and payload and payload.get("ok"):
                row["lookup_state"] = payload["data"]["state"]
            self.journal.append(row)
            return response

        @app.teardown_request
        def close(_error):
            conn = g.pop("db", None)
            if conn is not None:
                close_workbench_request_connection(conn)

        self.business = app

    def capture_proof(self):
        if self.path is None:
            return
        with self.connect() as conn:
            after = snapshot(conn)
            self.assert_preserved_data(conn, after)
            receipts = [json.loads(r[0]) for r in conn.execute("SELECT outcome_json FROM WorkbenchCommandReceipts WHERE action='trial.scenario.adopt'")]
            for receipt in receipts:
                data = receipt["data"]
                saved = trial_service(conn).scenario(data["scenario_ref"])
                assert saved["draft_ref"] == data["draft_ref"]
                rows = list(conn.execute("SELECT s.*,r.ref AS operation_ref FROM Schedule s JOIN WorkbenchPlanSourceRefs r ON r.kind='operation' AND r.source_key=CAST(s.op_id AS TEXT) AND r.active=1 WHERE s.version=?", (data["official_plan"]["version"],)))
                assert len(rows) == data["row_count"] == saved["task_count"]
                for task in saved["tasks"]:
                    row = next(r for r in rows if r["operation_ref"] == task["operation_ref"])
                    assert row["start_time"].replace(" ", "T") == task["start"] and row["end_time"].replace(" ", "T") == task["end"]
                    for kind in ("machine", "operator"):
                        actual = conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind=? AND entity_key=? AND active=1", (kind, row[kind + "_id"])).fetchone()[0]
                        assert actual == task[kind + "_ref"]
            versions = conn.execute("SELECT COUNT(*) FROM ScheduleHistory WHERE version>7").fetchone()[0]
            assert versions == len(receipts)
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok" and not conn.execute("PRAGMA foreign_key_check").fetchall()
            self.proofs.append({"database": str(self.path), "old_rows_and_types_retained": True, "old_scenarios_exactly_retained": True,
                                "old_execution_exactly_retained": True, "saved_arrangements_match_new_official": True, "new_versions": versions,
                                "receipt_count": len(receipts), "unchanged_without_adoption": bool(receipts) or self.before == after})

    def assert_preserved_data(self, conn, after):
        append = set(TRIAL_TABLES) | {"Schedule", "ScheduleHistory", "ScheduleVersionSeq", "OperationLogs", "WorkbenchCommandReceipts", "WorkbenchPlanSourceRefs", "WorkbenchTaskRefs"}
        assert set(self.before) == set(after)
        for table, rows in self.before.items():
            if table == "WorkbenchDashboardItems":
                assert_dashboard_task_appends(self.before, after)
            elif table in append:
                found = {r[0]: r for r in after[table]}
                assert all(found.get(r[0]) == r for r in rows), table
            elif table not in {"sqlite_sequence", "WorkbenchPlanIdentityClock"}:
                assert after[table] == rows, table
        for saved in self.scenarios:
            assert trial_service(conn).scenario(saved["scenario_ref"]) == saved

    def evidence(self):
        with self.connect() as conn:
            receipts = [dict(r) for r in conn.execute("SELECT request_key,receipt_ref,outcome_json FROM WorkbenchCommandReceipts WHERE action='trial.scenario.adopt'")]
        return {"journal": self.journal, "receipts": receipts, "started": self.started.is_set(), "refs": self.current, "lifecycle": self.gate.status}

    def advance(self):
        with self.business.app_context(), self.connect() as conn:
            case = JobCase(conn)
            version = conn.execute("SELECT MAX(version) FROM ScheduleHistory").fetchone()[0]
            draft = create(case, {"base": {"plan_ref": case.plan_ref(version)}}, key="cx-next-create-0001")
            saved = trial_service(conn).save(draft["draft_ref"], {"name": "后续真实正式版本"}, draft["write_context"]["write_token"], "cx-next-save-0001")["data"]
            svc = adoption_service(conn)
            result = svc.adopt(saved["scenario_ref"], svc.preview(saved["scenario_ref"])["write_context"]["write_token"], "cx-next-adopt-0001",
                               {"confirm": True, "reason": "Explicit subsequent official", "declared_operator": "CX fixture"})
        return result

    def control(self, action):
        if action == "expire":
            self.business.extensions.pop("aps_public_opaque_tokens", None)
        elif action == "release":
            self.release.set()
        elif action == "enable":
            self.business.config["WORKBENCH_CANDIDATE_ADOPTION_ENABLED"] = True
        elif action in ("run-busy", "run-idle"):
            if action == "run-busy":
                assert not self.run_locked and schedule_service._RUN_SCHEDULE_LOCK.acquire(blocking=False)
                self.run_locked = True
            elif self.run_locked:
                schedule_service._RUN_SCHEDULE_LOCK.release()
                self.run_locked = False
        elif action == "drain":
            thread = threading.Thread(target=lambda: self.gate.shutdown(wait=False))
            thread.start()
            thread.join(5)
            assert not thread.is_alive() and self.gate.status["state"] == "stopping"
        elif action == "advance":
            return self.advance()
        elif action == "drift":
            self.capture_proof()
            with self.connect() as conn:
                conn.execute("UPDATE Machines SET name='CX explicit drift' WHERE machine_id='M2'")
                conn.commit()
                after = snapshot(conn)
                changed = [t for t in self.before if after[t] != self.before[t]]
                assert set(changed) == {"Machines", "WorkbenchEntityRefs"}
                self.before.update({t: after[t] for t in changed})
                self.changes.append({"database": str(self.path), "tables": changed})
        else:
            raise ValueError("Unknown CX fixture control")
        return {"ok": True}

    def register_controls(self):
        @self.app.route("/fixture/reset", methods=["POST"])
        def reset():
            return jsonify(self.reset(request.get_json()["mode"]))

        @self.app.route("/fixture/evidence")
        def evidence():
            return jsonify(self.evidence())

        @self.app.route("/fixture/control", methods=["POST"])
        def control():
            return jsonify(self.control(request.get_json()["action"]))

    def proof(self):
        self.capture_proof()
        return {"databases": self.proofs, "journal": self.journal, "fixture_changes": self.changes,
                "all_connections_isolated": bool(self.connections) and all(Path(p).parent == self.root for p in self.connections),
                "business_results_mocked": False, "fixture_explicitly_enabled": True, "production_preview_touched": False}

    def close(self):
        self.release.set()
        if self.run_locked:
            schedule_service._RUN_SCHEDULE_LOCK.release()
            self.run_locked = False
        for gate in self.gates:
            assert gate.shutdown(wait=True, timeout=10)
