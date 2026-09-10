"""DH: disposable real factory, real SQLite and original launcher-lock payload."""

import os
import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest

from core.infrastructure.backup import BackupManager
from core.infrastructure.database import get_connection
from core.services.workbench.system_journal import SystemMaintenanceJournal, assert_system_maintenance_ready
from tests.workbench.request_lifecycle_support import http_json, http_server  # noqa: F401
from web.bootstrap import factory
from web.bootstrap.launcher_paths import db_scope_lock_path
from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
from web.bootstrap.workbench_run_runtime import install_workbench_run_runtime
from web.bootstrap.workbench_system_restore import install_workbench_system_restore_host

BASE = "/api/workbench/v1/system"
KEY = "dh-restore-host-request-000001"


class RestoreHostCase:
    def __init__(self, app, runtime, host, journal_dir, payload):
        self.app, self.runtime, self.host = app, runtime, host
        self.path = app.config["DATABASE_PATH"]
        self.backups = Path(app.config["BACKUP_DIR"])
        self.journal = SystemMaintenanceJournal(str(journal_dir), self.path)
        self.gate = host.gate
        self.lock_paths = [Path(payload["path"]), Path(db_scope_lock_path(self.path))]
        self.lock_bytes = [path.read_bytes() for path in self.lock_paths]
        self.client = app.test_client()

    def marker(self, value=None, path=None):
        with closing(get_connection(path or self.path)) as conn:
            if value is not None:
                conn.execute("INSERT OR REPLACE INTO SystemConfig(config_key,config_value) VALUES ('DH',?)", (value,))
                conn.commit()
            return conn.execute("SELECT config_value FROM SystemConfig WHERE config_key='DH'").fetchone()[0]

    def intent(self):
        self.marker("selected")
        self.source = BackupManager(self.path, str(self.backups)).backup(suffix="dh_source")
        self.marker("current")
        response = self.client.get(BASE + "/backups", buffered=True)
        assert response.status_code == 200, response.get_json()
        row = next(row for row in response.get_json()["data"]["rows"] if row["filename"] == Path(self.source).name)
        return {"request_key": KEY, "write_token": row["write_context"]["write_token"],
                "input": {"backup_ref": row["backup_ref"]}}

    def assert_locks_held(self):
        assert [path.read_bytes() for path in self.lock_paths] == self.lock_bytes


@pytest.fixture(name="restore_host")
def restore_host(db_env, tmp_path, monkeypatch):
    connect = sqlite3.connect
    def isolated(database, *args, **kwargs):
        raw = os.fspath(database)
        if raw != ":memory:":
            path = unquote(urlparse(raw).path) if raw.startswith("file:") else raw
            Path(path).resolve().relative_to(tmp_path.resolve())
        return connect(database, *args, **kwargs)
    monkeypatch.setattr(sqlite3, "connect", isolated)
    monkeypatch.setenv("APS_ENV", "production")
    journal_dir = tmp_path / "restore-journal"
    journal_dir.mkdir()
    scope = str(tmp_path / "dh-launcher")
    payload = acquire_runtime_lock(scope, db_path=db_env)
    runtime, gate = None, None
    try:
        # Explicit host integration under test; native factory/entrypoint hooks
        # are owned by the main agent and are NOT claimed by this fixture.
        assert_system_maintenance_ready(db_env, str(journal_dir))
        app = factory.create_app_core(ui_mode="default", enable_secret_key=False,
                                     enable_security_headers=False, enable_session_cookie_hardening=False)
        app.config.update(TESTING=True, WORKBENCH_SYSTEM_JOURNAL_DIR=str(journal_dir))
        gate = app.extensions["workbench_request_lifecycle"]
        runtime = install_workbench_run_runtime(app, runtime_lock=payload)
        assert runtime.ready, runtime.status
        host = install_workbench_system_restore_host(app, runtime=runtime)
        yield RestoreHostCase(app, runtime, host, journal_dir, payload)
    finally:
        if runtime is not None:
            assert runtime.shutdown(timeout=20), runtime.status
        if gate is not None:
            gate.shutdown(timeout=20)
        release_runtime_lock(scope, db_path=db_env)


def seed_worker(case):
    from core.services.scheduler.config.config_field_spec import default_snapshot_values
    from tests.workbench.run_jobs_support import JobCase
    with closing(get_connection(case.path)) as conn:
        conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
        conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Lathe','T1')")
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
        conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
        conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','Part')")
        for key, value in default_snapshot_values().items():
            conn.execute("INSERT OR REPLACE INTO ScheduleConfig(config_key,config_value) VALUES (?,?)", (key, str(value)))
        job = JobCase(conn)
        job.batch("B1")
        job.op_id = job.operation()
        job.config(algo_mode="greedy", graph_candidate_weight_count=3, time_budget_seconds=60,
                   ortools_enabled="no", freeze_window_enabled="no")
        with case.app.app_context():
            accepted = job.accept(key="dh-host-worker-request-000001")
        return accepted
