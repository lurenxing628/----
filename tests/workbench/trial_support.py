"""CD-only real temporary SQLite, calendar, ledger, engine and API fixtures."""

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest
from flask import Blueprint, Flask, g

from core.infrastructure.database import ensure_schema
from core.infrastructure.workbench_trial_schema import TRIAL_TABLES, install_workbench_trial_schema
from core.models.workbench_trial_codec import fingerprint
from core.services.scheduler.config.config_field_spec import default_snapshot_values
from core.services.workbench.run_worker import WorkbenchRunWorker
from core.services.workbench.trial import WorkbenchTrialService
from tests.workbench.run_jobs_support import JobCase
from web.routes.workbench.trial import register_trial_routes
from web.routes.workbench.write_context import issue_write_context, validate_write_context

NOW = datetime(2026, 9, 10, 12)
BASE = "/api/workbench/v1/trial"


def connect(path, factory=sqlite3.Connection):
    conn = sqlite3.connect(str(path), timeout=20, factory=factory)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def service(conn):
    return WorkbenchTrialService(conn, context_factory=issue_write_context,
        context_validator=validate_write_context, clock=lambda: NOW, actor_provider=lambda: "trial-local-user")


@pytest.fixture
def trial_case(tmp_path):
    path = tmp_path / "trial.sqlite"
    ensure_schema(str(path), schema_path=str(Path(__file__).resolve().parents[2] / "schema.sql"), backup_dir=None)
    conn = connect(path)
    conn.execute("BEGIN IMMEDIATE")
    install_workbench_trial_schema(conn)
    conn.commit()
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','Original part')")
    for i in (1, 2, 3):
        conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES (?,?, 'T1')", ("M" + str(i), "Lathe " + str(i)))
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES (?,?)", ("O" + str(i), "Operator " + str(i)))
        conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)", ("O" + str(i), "M" + str(i)))
    for key, value in default_snapshot_values().items():
        conn.execute("INSERT OR REPLACE INTO ScheduleConfig(config_key,config_value) VALUES (?,?)", (key, str(value)))
    case = JobCase(conn)
    case.path = path
    case.batch("B1")
    case.op_id = case.operation(setup_hours=0, unit_hours=1)
    case.config(algo_mode="greedy", graph_candidate_weight_count=3, time_budget_seconds=60,
                ortools_enabled="no", freeze_window_enabled="no")
    case.app = Flask("trial-tests")
    with case.app.app_context():
        yield case
    conn.close()


def official(case, *, ids=None, start="2026-09-09T08:00:00", end="2026-09-09T11:00:00"):
    case.plan(1, ids or [case.op_id], start=start, end=end)
    return {"base": {"plan_ref": case.plan_ref(1)}}


def candidate(case):
    accepted = case.accept()
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert result["state"] == "complete", result
    return {"base": {"candidate_ref": result["candidates"][0]["candidate_ref"]}}


def create(case, value=None, key="trial-create-00000001"):
    intent = value or official(case)
    svc = service(case.conn)
    preview = svc.preview_create(intent)
    result = svc.create(intent, preview["write_context"]["write_token"], key)
    assert result["ok"] is True
    return result["data"]


def change(case, draft, *, start="2026-09-09T13:00:00", machine="M2", operator="O2", task=0, key="trial-change-00000001"):
    value = {"task_ref": draft["tasks"][task]["task_ref"], "machine_ref": case.ref("machine", machine) if machine else None,
             "operator_ref": case.ref("operator", operator) if operator else None, "start": start}
    return service(case.conn).change(draft["draft_ref"], value, draft["write_context"]["write_token"], key)


def snapshot(conn):
    return {name: [tuple((type(value).__name__, value) for value in row) for row in conn.execute('SELECT rowid,* FROM "' + name + '" ORDER BY rowid')]
            for name, in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")}


def assert_legacy_retained(before, after):
    for name in before:
        if name not in set(TRIAL_TABLES) | {"WorkbenchCommandReceipts"}:
            assert fingerprint(before[name]) == fingerprint(after[name]), name


def api(case, factory=sqlite3.Connection):
    bp = Blueprint("trial_tests", __name__)
    register_trial_routes(bp)
    case.app.register_blueprint(bp)

    @case.app.before_request
    def bind():
        g.db = connect(case.path, factory)

    @case.app.teardown_request
    def close(error):
        g.db.close()

    return case.app.test_client()


class CommitFailureConnection(sqlite3.Connection):
    fail_commit = False
    acknowledge_only = False

    def commit(self):
        if self.fail_commit:
            self.fail_commit = False
            if self.acknowledge_only:
                super().commit()
            raise sqlite3.OperationalError("injected trial commit acknowledgement failure")
        return super().commit()
