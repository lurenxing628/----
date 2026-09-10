"""Real factory, real launcher files and callbacks; only the socket server is replaced."""

import atexit
import os
from dataclasses import replace
from pathlib import Path

import pytest
from flask import Flask

from core.infrastructure.database import get_connection
from core.services.scheduler.config.config_field_spec import default_snapshot_values
from tests.workbench.run_jobs_support import JobCase
from web.bootstrap import entrypoint, factory
from web.bootstrap.launcher_paths import db_scope_lock_path


@pytest.fixture(name="job_case")
def entrypoint_case(db_path):
    # db_path runs the production empty-database bootstrap before any business seed.
    conn = get_connection(db_path)
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
    conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Lathe','T1')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
    conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','Part')")
    for key, value in default_snapshot_values().items():
        conn.execute("INSERT INTO ScheduleConfig(config_key,config_value) VALUES (?,?)", (key, str(value)))
    case = JobCase(conn)
    case.path = Path(db_path)
    case.batch("B1")
    case.op_id = case.operation()
    case.config(algo_mode="greedy", graph_candidate_weight_count=3, time_budget_seconds=60,
                ortools_enabled="no", freeze_window_enabled="no")
    case.app = Flask(__name__)
    try:
        with case.app.app_context():
            yield case
    finally:
        conn.close()


class EntryHarness:
    def __init__(self, case, tmp_path, monkeypatch, serve):
        self.case = case
        self.root = tmp_path / "entrypoint"
        self.root.mkdir()
        self.handlers = []
        self.events = []
        self.app = None
        self.runtime = None
        for key, value in {
            "APS_ENV": "production", "APS_DB_PATH": str(case.path), "APS_LOG_DIR": str(self.root / "logs"),
            "APS_BACKUP_DIR": str(self.root / "backups"), "APS_EXCEL_TEMPLATE_DIR": str(self.root / "templates"),
            "SECRET_KEY": "isolated-entrypoint-regression-only",
        }.items():
            monkeypatch.setenv(key, value)
        monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
        monkeypatch.setattr(atexit, "register", self.register)
        monkeypatch.setattr(factory, "_EXIT_BACKUP_REGISTERED", False)
        self.deps = replace(entrypoint._default_deps("default"), create_app=self.create,
                            serve_runtime_app=serve, pick_port=lambda host, _port, **_kwargs: (host, 59995))

    def register(self, callback, *args, **kwargs):
        self.handlers.append((callback, args, kwargs))
        return callback

    def create(self):
        assert Path(db_scope_lock_path(str(self.case.path))).exists()
        self.events.append("create-under-db-lock")
        self.app = entrypoint.create_app_with_mode("default")
        self.app.config["TESTING"] = True
        with get_connection(str(self.case.path)) as conn:
            for key in ("auto_backup_enabled", "auto_backup_cleanup_enabled", "auto_log_cleanup_enabled"):
                conn.execute("INSERT OR REPLACE INTO SystemConfig(config_key,config_value) VALUES (?, 'no')", (key,))
        return self.app

    def run(self):
        return entrypoint.app_main(anchor_file=str(self.root / "app.py"), argv=[], deps=self.deps)

    def exit(self):
        for callback, args, kwargs in reversed(self.handlers):
            callback(*args, **kwargs)
        self.handlers.clear()

    def cleanup(self):
        runtime = self.app and self.app.extensions.get("workbench_run_runtime")
        if runtime is not None:
            runtime.shutdown(wait=True)
        self.deps.release_runtime_lock(str(self.root), os.getpid(), str(self.case.path))


def accept_via_http(client, case, key="entrypoint-run-request-0001"):
    checked = client.post("/api/workbench/v1/scheduling/preflight", json=case.settings())
    assert checked.status_code == 200, checked.get_json()
    input_ref = checked.get_json()["data"]["input_ref"]
    preview = client.post("/api/workbench/v1/scheduling/runs/preview", json={"input_ref": input_ref})
    assert preview.status_code == 200, preview.get_json()
    context = preview.get_json()["data"]["write_context"]
    assert context["capabilities"]["scheduling.run"] is True
    body = {"input_ref": input_ref, "write_token": context["write_token"], "request_key": key}
    accepted = client.post("/api/workbench/v1/scheduling/runs", json=body)
    assert accepted.status_code == 202, accepted.get_json()
    return accepted.get_json(), body
