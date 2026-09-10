"""Real process loss and SQLite COMMIT uncertainty never cause readmission."""

import sqlite3
import subprocess
import sys
import threading
from contextlib import closing
from pathlib import Path

from flask import Flask

from core.infrastructure.database import get_connection
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_run_job import new_run_ref
from core.services.workbench.run_jobs import WorkbenchRunService
from core.services.workbench.run_worker import WorkbenchRunWorker
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from tests.workbench import test_run_runtime_support as support
from tests.workbench.test_run_jobs_support import job_case as _job_case  # noqa: F401
from tests.workbench.test_run_runtime_support import (
    BASE,
    install,
    intent,
)
from tests.workbench.test_run_runtime_support import (
    owned_case as _owned_case,  # noqa: F401
)
from tests.workbench.test_run_runtime_support import (
    runtime_api as _runtime_api,
)
from web.bootstrap import workbench_run_runtime as host
from web.bootstrap.launcher_paths import db_scope_lock_path
from web.bootstrap.launcher_runtime_lock import release_runtime_lock


class LostCommit:
    """Fault only the ACK after the real disk connection has committed."""

    def __init__(self, conn, table, failures):
        self.conn, self.table, self.failures = conn, table, failures

    def __getattr__(self, name):
        return getattr(self.conn, name)

    def commit(self):
        lose = not self.failures and self.conn.execute("SELECT COUNT(*) FROM " + self.table).fetchone()[0]
        self.conn.commit()
        if lose:
            self.failures.append(threading.get_ident())
            raise sqlite3.OperationalError("BN COMMIT succeeded but ACK was lost")


def test_result_commit_ack_lost_keeps_original_terminal_result_without_recompute(runtime_api, monkeypatch, caplog):
    client, case, runtime = runtime_api
    value = intent(client, case)
    failures, computed = [], []
    actual_get = host.get_connection
    actual_compute = WorkbenchRunWorker._compute

    def connection(path):
        return LostCommit(actual_get(path), "WorkbenchRunReceipts", failures)

    def compute(worker, row):
        computed.append(row["run_ref"])
        return actual_compute(worker, row)

    monkeypatch.setattr(host, "get_connection", connection)
    monkeypatch.setattr(WorkbenchRunWorker, "_compute", compute)
    response = client.post(BASE + "/runs", json=value)
    assert response.status_code == 202
    ref = response.get_json()["run_ref"]
    assert runtime.wait_idle(timeout=20)
    result = client.get(BASE + "/runs/" + ref).get_json()["data"]
    assert result["state"] == "complete" and result["result_persisted"]
    assert computed == [ref] and len(failures) == 1
    assert ref in caplog.text and "ACK was lost" in caplog.text
    assert client.post(BASE + "/runs", json=value).get_json()["replayed"]
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunReceipts").fetchone()[0] == 1
    assert runtime.ready


def test_admission_ack_lost_remains_queryable_original_key_until_restart(runtime_api, monkeypatch):
    client, case, runtime = runtime_api
    value = intent(client, case)
    failures = []
    actual_get = support.get_connection
    monkeypatch.setattr(support, "get_connection", lambda path:
                        LostCommit(actual_get(path), "WorkbenchRunJobs", failures))
    response = client.post(BASE + "/runs", json=value)
    assert response.status_code == 500 and response.get_json()["committed"] == "unknown"
    lookup = client.get(BASE + "/requests/" + value["request_key"]).get_json()["data"]["run"]
    ref = lookup["run_ref"]
    assert lookup["state"] == "queued" and len(failures) == 1
    assert runtime.status["pending"] == []
    replay = client.post(BASE + "/runs", json=value)
    assert replay.status_code == 202 and replay.get_json()["replayed"]
    assert replay.get_json()["run_ref"] == ref
    assert runtime.shutdown()
    app = Flask("after-lost-admission-ack")
    app.config["DATABASE_PATH"] = str(case.path)
    restarted = host.install_workbench_run_runtime(app, runtime_lock=case.lock_payload)
    try:
        assert restarted.ready and restarted.recovery["recovered"] == [ref]
        assert WorkbenchRunService(case.conn).lookup(value["request_key"])["state"] == "interrupted"
        assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunJobs").fetchone()[0] == 1
    finally:
        assert restarted.shutdown()


def test_actual_process_crash_after_claim_is_recovered_by_new_actual_lock(owned_case):
    case = owned_case
    case.accept()
    # The child must acquire the real lock itself, never bypass same-PID refusal.
    release_runtime_lock(case.runtime_dir, db_path=str(case.path))
    script = """
import os, sys
from flask import Flask
from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock
from web.bootstrap.workbench_run_runtime import install_workbench_run_runtime
from core.infrastructure.database import get_connection
from core.services.workbench.run_worker import WorkbenchRunWorker
from tests.workbench.test_run_jobs_support import JobCase

path, runtime_dir = sys.argv[1:]
claim = acquire_runtime_lock(runtime_dir, db_path=path)
app = Flask('bn-crash-child'); app.config['DATABASE_PATH'] = path
conn = get_connection(path)
case = JobCase(conn)
with app.app_context():
    runtime = install_workbench_run_runtime(app, runtime_lock=claim)
    assert runtime.ready, runtime.status
    accepted = case.accept('runtime-child-request-00000001')
    def crash(self, row):
        os._exit(23)
    WorkbenchRunWorker._compute = crash
    runtime(accepted['run_ref'])
    runtime.wait_idle(timeout=20)
os._exit(90)
"""
    completed = subprocess.run([sys.executable, "-c", script, str(case.path), case.runtime_dir],
                               capture_output=True, text=True, timeout=35)
    assert completed.returncode == 23, completed.stderr
    with closing(get_connection(str(case.path))) as conn:
        row = WorkbenchRunService(conn).lookup("runtime-child-request-00000001")
        assert row["state"] == "running"
        crashed_ref = row["run_ref"]
        unknown = WorkbenchRunService(conn).recover_unfinished_runs()
        assert unknown["pending"] == [crashed_ref]
        assert WorkbenchRunService(conn).get(crashed_ref)["stage"] == "awaiting_reconciliation"
    from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock
    case.lock_payload = acquire_runtime_lock(case.runtime_dir, db_path=str(case.path))
    runtime = install(case)
    assert runtime.recovery["recovered"] == [crashed_ref]
    assert WorkbenchRunService(case.conn).get(crashed_ref)["state"] == "interrupted"
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidates").fetchone()[0] == 0


def test_lock_evidence_becomes_unknown_during_recovery_keeps_awaiting(owned_case, monkeypatch):
    case = owned_case
    ref = case.accept()["run_ref"]
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        WorkbenchRunRepository(case.conn).claim(ref, new_run_ref(), "2000-01-01T00:00:00")
    path = Path(db_scope_lock_path(str(case.path)))
    moved = path.with_suffix(".held")
    recover = WorkbenchRunService.recover_unfinished_runs

    def lose_lock(service, *, executor_is_active=None):
        path.rename(moved)
        return recover(service, executor_is_active=executor_is_active)

    monkeypatch.setattr(WorkbenchRunService, "recover_unfinished_runs", lose_lock)
    try:
        runtime = host.install_workbench_run_runtime(case.app, runtime_lock=case.lock_payload)
        assert not runtime.ready and runtime.recovery["pending"] == [ref]
        assert "workbench_run_dispatcher" not in case.app.extensions
        state = WorkbenchRunService(case.conn).get(ref)
        assert state["state"] == "running" and state["stage"] == "awaiting_reconciliation"
    finally:
        moved.rename(path)


def test_no_schema_repair_when_a_required_run_object_is_missing(owned_case):
    case = owned_case
    case.conn.execute("DROP INDEX idx_wb_run_state")
    case.conn.commit()
    before = list(case.conn.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name"))
    runtime = host.install_workbench_run_runtime(case.app, runtime_lock=case.lock_payload)
    assert not runtime.ready
    assert list(case.conn.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name")) == before
