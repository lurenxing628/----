"""Fresh-process pending journals, uncertain disk ACKs and pinned source hashes."""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.infrastructure.backup import BackupManager, RestoreResult
from core.services.workbench.system_journal import (
    SystemMaintenanceJournal,
    assert_system_maintenance_ready,
    file_fingerprint,
)
from tests.workbench.test_system_restore_host_support import BASE, KEY, http_json, http_server
from tests.workbench.test_system_restore_host_support import restore_host as _restore_host  # noqa: F401


@pytest.mark.parametrize("after_disk_write", [False, True])
def test_uncertain_terminal_journal_ack_never_replays_restore(restore_host, monkeypatch, after_disk_write):
    case = restore_host
    body = case.intent()
    original = SystemMaintenanceJournal.record
    def fail(journal, row, state, **values):
        if state in ("succeeded", "recovery_required"):
            if after_disk_write and state == "succeeded":
                original(journal, row, state, **values)
            raise OSError("DH terminal journal ACK lost")
        return original(journal, row, state, **values)
    monkeypatch.setattr(SystemMaintenanceJournal, "record", fail)
    with http_server(case.app) as port:
        status, result = http_json(port, BASE + "/backups/restore", body)
        assert status == 500 and result["committed"] == "unknown", result
        assert result["error"]["request_key"] == KEY
        status, recovered = http_json(port, BASE + "/results/" + KEY, method="GET")
        assert status == 200
        assert recovered["data"]["operation"]["state"] == ("succeeded" if after_disk_write else "verifying")
        assert recovered["data"]["host"]["state"] == "recovery_required"
        before = file_fingerprint(case.path)
        assert http_json(port, BASE + "/backups/restore", body)[0] == 503
        assert file_fingerprint(case.path) == before
    assert len(list(case.backups.glob("*before_restore.db"))) == 1
    assert case.marker() == "selected"
    case.assert_locks_held()


def test_fresh_process_pending_startup_blocks_database_access_and_exposes_only_journal(restore_host, monkeypatch):
    case = restore_host
    body = case.intent()
    original = SystemMaintenanceJournal.record
    def fail(journal, row, state, **values):
        if state in ("succeeded", "recovery_required"):
            raise OSError("DH power-loss terminal write simulation")
        return original(journal, row, state, **values)
    monkeypatch.setattr(SystemMaintenanceJournal, "record", fail)
    response = case.client.post(BASE + "/backups/restore", json=body, buffered=True)
    assert response.status_code == 500
    before = {path.name: file_fingerprint(str(path)) for path in [Path(case.path)] + list(case.backups.glob("*.db"))}
    script = r'''
import json, logging, sqlite3, sys
from werkzeug.test import Client
from werkzeug.wrappers import Response
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.system_journal import assert_system_maintenance_ready
from core.services.workbench.system_files import SystemFileWorkspace
from web.bootstrap.workbench_system_restore import make_workbench_system_restore_recovery_app
database, journal, backups, key, intent = sys.argv[1:]
def forbidden(*args, **kwargs):
    raise AssertionError("pending startup must never open SQLite or resolve old tokens")
sqlite3.connect = forbidden
try:
    assert_system_maintenance_ready(database, journal)
except WorkbenchCommandRejected as exc:
    assert exc.code == "maintenance_active"
else:
    raise AssertionError("startup unexpectedly enabled")
service = SystemFileWorkspace(database_path=database, backup_dir=backups, journal_dir=journal, logger=logging.getLogger("DH"))
row, replayed, path = service.prepare_restore(request_key=key, intent=json.loads(intent), guard=forbidden)
assert replayed is True and path is None and row["state"] == "verifying"
client = Client(make_workbench_system_restore_recovery_app(database, journal), Response)
result = client.get("/api/workbench/v1/system/results/" + key)
assert result.status_code == 200 and result.json["data"]["operation"]["state"] == "verifying"
assert client.post("/api/workbench/v1/system/backups/restore", json={}).status_code == 503
assert client.get("/workbench").status_code == 503
assert client.get("/static/test.css").status_code == 503
print(json.dumps({"state": row["state"], "replayed": replayed, "database_opened": False}))
'''
    result = subprocess.run([sys.executable, "-c", script, case.path, case.journal.directory,
                             str(case.backups), KEY, json.dumps(body["input"])],
                            cwd=str(Path(__file__).resolve().parents[2]), capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["database_opened"] is False
    assert {path.name: file_fingerprint(str(path)) for path in [Path(case.path)] + list(case.backups.glob("*.db"))} == before


def test_changed_source_after_durable_acceptance_is_not_restored(restore_host, monkeypatch):
    case = restore_host
    body = case.intent()
    original = BackupManager.backup
    def changed_source(manager, suffix=None):
        path = original(manager, suffix)
        if suffix and "before_restore" in suffix:
            case.marker("changed-source", path=case.source)
        return path
    monkeypatch.setattr(BackupManager, "backup", changed_source)
    result = case.client.post(BASE + "/backups/restore", json=body, buffered=True).get_json()["data"]["operation"]
    assert result["state"] == "rolled_back"
    assert case.marker() == "current"
    assert case.marker(path=case.source) == "changed-source"
    assert result["target_sha256"] != file_fingerprint(case.source)
    assert_system_maintenance_ready(case.path, case.journal.directory)


def test_changed_protection_cannot_authorize_rollback(restore_host, monkeypatch):
    case = restore_host
    body = case.intent()
    def verify(*args, **kwargs):
        protection = next(case.backups.glob("*before_restore.db"))
        case.marker("wrong-protection", path=str(protection))
        raise RuntimeError("DH verification failed with modified protection")
    monkeypatch.setattr("web.routes.workbench.system_actions.ensure_schema", verify)
    result = case.client.post(BASE + "/backups/restore", json=body, buffered=True).get_json()["data"]["operation"]
    assert result["state"] == "rollback_failed" and not result["terminal"]
    assert case.marker() == "selected"
    assert result["protection_sha256"] != file_fingerprint(str(case.backups / result["protection_filename"]))
    with pytest.raises(ValueError, match="未核实"):
        assert_system_maintenance_ready(case.path, case.journal.directory)


def test_unknown_runner_result_remains_pending_across_restart(restore_host, monkeypatch):
    case = restore_host
    body = case.intent()
    def unknown(manager, path):
        return SimpleNamespace(result=RestoreResult(True, "unknown_rolled_back", "unknown"), category="success")
    monkeypatch.setattr("web.routes.workbench.system_actions._restore_runner", unknown)
    result = case.client.post(BASE + "/backups/restore", json=body, buffered=True).get_json()["data"]["operation"]
    assert result["state"] == "recovery_required" and result["terminal"] is False
    with pytest.raises(ValueError, match="未核实"):
        assert_system_maintenance_ready(case.path, case.journal.directory)
    assert case.marker() == "current"


def test_hash_valid_unknown_terminal_record_still_blocks_startup(restore_host):
    journal = restore_host.journal
    row, _ = journal.begin(KEY, "restore", {})
    journal.record(row, "succeeded", code="new_unknown_success")
    with pytest.raises(RuntimeError, match="终态"):
        journal.assert_ready()


def test_no_original_scheduler_lock_means_no_database_copy(restore_host):
    from core.services.scheduler import schedule_service
    case = restore_host
    body = case.intent()
    with schedule_service._RUN_SCHEDULE_LOCK:
        response = case.client.post(BASE + "/backups/restore", json=body, buffered=True)
    result = response.get_json()["data"]["operation"]
    assert result["state"] == "recovery_required"
    assert not list(case.backups.glob("*before_restore.db"))
    assert case.marker() == "current" and not case.runtime.ready


def test_failure_after_intent_ack_closes_admission_before_any_copy(restore_host, monkeypatch):
    case = restore_host
    body = case.intent()
    original = SystemMaintenanceJournal.record
    def fail(journal, row, state, **values):
        if state == "checking":
            raise OSError("DH accepted intent but checking ACK failed")
        return original(journal, row, state, **values)
    monkeypatch.setattr(SystemMaintenanceJournal, "record", fail)
    response = case.client.post(BASE + "/backups/restore", json=body, buffered=True)
    assert response.status_code == 500
    assert case.journal.lookup(KEY)["state"] == "accepted"
    assert case.host.status["state"] == "recovery_required"
    assert not case.runtime.ready and case.client.get("/workbench", buffered=True).status_code == 503
    assert case.marker() == "current" and not list(case.backups.glob("*before_restore.db"))


def test_confirmed_restore_replays_only_after_fresh_process_runtime_ownership(restore_host):
    from web.bootstrap.launcher_runtime_lock import release_runtime_lock
    case = restore_host
    body = case.intent()
    response = case.client.post(BASE + "/backups/restore", json=body, buffered=True)
    operation = response.get_json()["data"]["operation"]
    assert operation["state"] == "succeeded"
    assert case.gate.shutdown(timeout=5) and case.runtime.shutdown(timeout=5)
    scope = str(case.lock_paths[0].parent)
    release_runtime_lock(scope, db_path=case.path)
    script = r'''
import atexit, json, os, sqlite3, sys
from pathlib import Path
from urllib.parse import unquote, urlparse
from core.infrastructure.backup import BackupManager
from core.services.workbench.system_journal import assert_system_maintenance_ready
from web.bootstrap import factory
from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
from web.bootstrap.workbench_run_runtime import install_workbench_run_runtime
from web.bootstrap.workbench_system_restore import install_workbench_system_restore_host
database, journal, scope, body = sys.argv[1:]
connect = sqlite3.connect
def isolated(path, *args, **kwargs):
    raw = os.fspath(path)
    if raw != ":memory:":
        actual = unquote(urlparse(raw).path) if raw.startswith("file:") else raw
        Path(actual).resolve().relative_to(Path(database).resolve().parent)
    return connect(path, *args, **kwargs)
sqlite3.connect = isolated
def forbidden(*args, **kwargs):
    raise AssertionError("old restore must never be copied again")
BackupManager.restore = forbidden
payload = acquire_runtime_lock(scope, db_path=database)
runtime = gate = None
try:
    assert_system_maintenance_ready(database, journal)
    app = factory.create_app_core(ui_mode="default", enable_secret_key=False,
        enable_security_headers=False, enable_session_cookie_hardening=False)
    app.config["WORKBENCH_SYSTEM_JOURNAL_DIR"] = journal
    gate = app.extensions["workbench_request_lifecycle"]
    runtime = install_workbench_run_runtime(app, runtime_lock=payload)
    host = install_workbench_system_restore_host(app, runtime=runtime)
    response = app.test_client().post("/api/workbench/v1/system/backups/restore", json=json.loads(body), buffered=True)
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert data["operation"]["replayed"] is True
    assert data["operation"]["result_source"] == "external_maintenance_journal"
    assert data["host"]["state"] == "ready" and data["host"]["restart_required"] is False
    assert runtime.ready and gate.status["state"] == "accepting"
    print(json.dumps({"job_ref": data["operation"]["job_ref"], "runtime_ready": runtime.ready}))
finally:
    if gate is not None:
        assert gate.shutdown(timeout=5)
    if runtime is not None:
        assert runtime.shutdown(timeout=5)
    atexit.unregister(factory._run_exit_backup)
    release_runtime_lock(scope, db_path=database)
'''
    completed = subprocess.run([sys.executable, "-c", script, case.path, case.journal.directory,
                                scope, json.dumps(body)], cwd=str(Path(__file__).resolve().parents[2]),
                               capture_output=True, text=True, timeout=25)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout) == {"job_ref": operation["job_ref"], "runtime_ready": True}
    assert len(list(case.backups.glob("*before_restore.db"))) == 1
