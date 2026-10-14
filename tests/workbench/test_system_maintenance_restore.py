"""Fault injection only in our fresh disposable test DB and backup directory."""


import json
import logging
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from werkzeug.test import EnvironBuilder

from core.infrastructure.backup import BackupManager
from core.models.content import same
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts.system_journal import SystemMaintenanceJournal, assert_system_maintenance_ready
from core.services.workbench.facts.system_reads import backup_signature
from core.services.workbench.system.files import SystemFileWorkspace
from tests.workbench.system_restore_entrypoint_legacy_support import (
    system_api as _system_api_fixture,  # noqa: F401
)


def enable_restore(api):
    from web.bootstrap.workbench_system_restore import WorkbenchSystemRestoreHost
    host = api.app.extensions["workbench_system_restore_host"]
    assert isinstance(host, WorkbenchSystemRestoreHost)
    assert api.app.extensions["workbench_system_restore_guard"] is host
    assert host.runtime.ready and host.status["operations_available"]
    host.verify()


def test_static_files_observe_stop_state_without_rereading_database_locks(system_api, monkeypatch):
    from web.bootstrap.workbench_run_runtime_lock import RunRuntimeLockProof

    calls, original = [], RunRuntimeLockProof.verify

    def verify(proof):
        calls.append(proof)
        return original(proof)

    monkeypatch.setattr(RunRuntimeLockProof, "verify", verify)
    response = system_api.client.get("/static/workbench/app/theme.js", buffered=True)
    assert response.status_code == 200 and not calls
    response.close()
    assert system_api.get("/restore-host").status_code == 200 and calls
    host = system_api.app.extensions["workbench_system_restore_host"]
    host._set_state("stopped", None)
    calls.clear()
    assert system_api.client.get("/static/workbench/app/theme.js", buffered=True).status_code == 503
    assert not calls


def test_due_backup_runs_after_response_on_owned_worker_and_shutdown_joins_it(system_api, monkeypatch):
    from core.services.system.system_config_service import SystemConfigService
    from core.services.system.system_maintenance_service import SystemMaintenanceService
    from web.bootstrap.workbench_run_lifecycle import stop_run_runtime

    conn = system_api.connect()
    try:
        SystemConfigService(conn).update_backup_settings("yes", 60, "no", 7, 1440)
    finally:
        conn.close()
    # Advance the deferred check interval in this controlled test, without waiting ten seconds.
    monkeypatch.setattr(SystemMaintenanceService, "CHECK_THROTTLE_SECONDS", 0)
    entered, release = threading.Event(), threading.Event()
    threads, original = [], BackupManager.backup

    def backup(manager, *args, **kwargs):
        threads.append(threading.get_ident())
        entered.set()
        assert release.wait(5)
        return original(manager, *args, **kwargs)

    monkeypatch.setattr(BackupManager, "backup", backup)
    runtime = system_api.app.extensions["workbench_run_runtime"]
    try:
        response = system_api.client.get("/", buffered=True)
        assert response.status_code == 302
        response.close()
        assert entered.wait(3)
        assert threads == [runtime._thread.ident] and threads[0] != threading.get_ident()
        with ThreadPoolExecutor(max_workers=1) as pool:
            stopped = pool.submit(stop_run_runtime, runtime)
            assert not stopped.done()
            assert Path(runtime.proof.db_lock_path).exists()
            release.set()
            stopped.result(5)
        assert runtime.status["closed"]
        assert list(system_api.backups.glob("*_auto.db"))
    finally:
        release.set()


def test_download_requests_schedule_maintenance_after_wsgi_lifecycle_finishes(system_api, monkeypatch):
    app = system_api.app
    runtime = app.extensions["workbench_run_runtime"]
    gate = app.extensions["workbench_request_lifecycle"]
    calls = []
    monkeypatch.setattr(runtime, "request_maintenance_check", lambda: calls.append(gate.status["active"]))
    statuses = []
    environ = EnvironBuilder(path="/api/workbench/v1/entities/batch/template").get_environ()
    response = app.wsgi_app(environ, lambda status, headers: statuses.append(status))
    try:
        assert statuses == ["200 OK"]
        first_chunk = next(iter(response))
        assert not calls and gate.status["active"] == 1
        assert (first_chunk + b"".join(response)).startswith(b"PK")
        assert calls == [0]
    finally:
        response.close()
    assert calls == [0]


def test_verified_restore_uses_protection_external_result_and_new_connection(system_api):
    conn = system_api.connect()
    conn.execute("INSERT INTO SystemConfig(config_key,config_value) VALUES('marker','before')")
    conn.commit()
    conn.close()
    system_api.backup()
    row = system_api.selected()
    conn = system_api.connect()
    conn.execute("UPDATE SystemConfig SET config_value='after' WHERE config_key='marker'")
    conn.commit()
    conn.close()
    enable_restore(system_api)
    response = system_api.file_action("restore", row)
    assert response.status_code == 200, response.get_json()
    result = response.get_json()["data"]["operation"]
    assert result["code"] == "verified" and result["state"] == "succeeded"
    assert result["source_verification"] == {"basis": "original_file_content_and_sqlite", "target": "verified",
                                            "protection": "captured", "sqlite_integrity": "passed"}
    assert not {"target_sha256", "protection_sha256", "database_after_sha256"}.intersection(result)
    assert result["protection_filename"].endswith("before_restore.db")
    states = [item["state"] for item in result["history"]]
    assert states.index("protecting") < states.index("restoring") < states.index("verifying")
    conn = system_api.connect()
    assert conn.execute("SELECT config_value FROM SystemConfig WHERE config_key='marker'").fetchone()[0] == "before"
    assert conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM OperationLogs WHERE action='workbench_restore'").fetchone()[0] == 1
    conn.close()
    replay = system_api.file_action("restore", row)
    assert replay.status_code == 503
    maintenance = system_api.app.test_client().get("/workbench?view=dashboard")
    assert maintenance.status_code == 503
    html = maintenance.get_data(as_text=True)
    assert 'href="/workbench?view=dashboard">重新检查启动状态</a>' in html
    assert "返回工作台" not in html
    looked_up = system_api.read("/results/system-test-request-0001")["data"]["operation"]
    assert looked_up["replayed"] is True
    assert looked_up["job_ref"] == result["job_ref"]
    assert_system_maintenance_ready(str(system_api.database), str(system_api.journal_dir))


def test_legacy_journal_lookup_and_new_intent_replay_preserve_original_files(tmp_path):
    database = tmp_path / "portable.db"
    directory = tmp_path / "portable.db.system-journal"
    directory.mkdir()
    old = {"version": 1, "database_scope": "a" * 64, "job_ref": "b" * 32,
           "request_key": "old-maintenance-request-01", "input_hash": "c" * 64, "record_hash": "d" * 64,
           "action": "create", "state": "succeeded", "code": "backup_verified", "message": "old saved result",
           "history": [{"state": "succeeded", "time": "2026-10-01T12:00:00"}], "updated_at": "2026-10-01T12:00:00",
           "target": {"filename": "aps_backup_saved.db", "sha256": "e" * 64}, "protection": None, "audit_persisted": True}
    original_path = directory / ("f" * 64 + ".json")
    original_path.write_text(json.dumps(old), encoding="utf-8")
    original = original_path.read_bytes()
    journal = SystemMaintenanceJournal(str(directory), str(database))
    assert journal.lookup(old["request_key"]) == old and journal.database_scope == old["database_scope"]
    public = journal.public(journal.lookup(old["request_key"]))
    assert public["job_ref"] == old["job_ref"] and public["target_sha256"] == old["target"]["sha256"]
    with pytest.raises(WorkbenchCommandRejected) as error:
        journal.begin(old["request_key"], "create", {})
    assert error.value.code == "original_intent_unavailable"
    assert original_path.read_bytes() == original
    external = SystemMaintenanceJournal(str(directory), str(tmp_path / "another.db"))
    assert external.lookup(old["request_key"]) == old
    with pytest.raises(WorkbenchCommandRejected) as error:
        external.assert_ready()
    assert error.value.code == "maintenance_origin_unavailable"

    row, replayed = journal.begin("new-maintenance-request-01", "create", {})
    assert replayed is False and row["version"] == 2 and row["intent"] == {"action": "create", "input": {}}
    assert row["database_scope"] == old["database_scope"]
    journal.record(row, "succeeded", code="backup_verified")
    new_path = directory / (row["job_ref"] + ".json")
    saved = new_path.read_bytes()
    replayed_row, replayed = journal.begin(row["request_key"], "create", {})
    assert replayed is True and same(replayed_row, row)
    assert new_path.read_bytes() == saved and original_path.read_bytes() == original
    assert len(list(directory.glob("*.json"))) == 2
    with pytest.raises(WorkbenchCommandRejected) as error:
        journal.begin(row["request_key"], "delete", {"backup_ref": "another-original-reference"})
    assert error.value.code == "request_key_conflict"


def test_restore_preflight_detects_changed_original_bytes_with_same_file_metadata(tmp_path):
    database, backup_dir, journal_dir = tmp_path / "current.db", tmp_path / "backups", tmp_path / "journal"
    backup_dir.mkdir()
    journal_dir.mkdir()
    selected = backup_dir / "aps_backup_selected.db"
    for path, value in ((database, "current!"), (selected, "selected")):
        with sqlite3.connect(str(path)) as conn:
            conn.execute("CREATE TABLE marker (value TEXT)")
            conn.execute("INSERT INTO marker VALUES (?)", (value,))
    workspace = SystemFileWorkspace(database_path=str(database), backup_dir=str(backup_dir), journal_dir=str(journal_dir),
                                    logger=logging.getLogger("system-source-content-tests"))
    signature = backup_signature(str(selected))
    row, replayed, path = workspace.prepare_restore(
        request_key="source-content-request-01", intent={"backup_ref": "retained-original-reference"},
        guard=lambda: {"filename": selected.name, "signature": signature},
    )
    assert not replayed and row["source_verification"]["target"] == "captured"
    with sqlite3.connect(str(selected)) as conn:
        conn.execute("UPDATE marker SET value = ?", ("changed!",))
    os.utime(str(selected), ns=(selected.stat().st_atime_ns, signature["mtime_ns"]))
    assert same(backup_signature(str(selected)), signature)

    def restore(manager, source_path):
        return SimpleNamespace(result=manager.restore(source_path), category="error")

    result = workspace.finish_restore(row, path, restore_runner=restore, audit=lambda _result: False, confirm_host=lambda: None)
    assert result["state"] == "rolled_back" and result["code"] == "restore_failed_rolled_back"
    with sqlite3.connect(str(database)) as conn:
        assert conn.execute("SELECT value FROM marker").fetchone() == ("current!",)
    saved = workspace.journal.lookup(row["request_key"])
    assert set(saved["target"]) == {"filename", "signature"} and set(saved["protection"]) == {"filename", "signature"}


def test_runtime_identity_is_independent_of_shutdown_and_application_secrets(tmp_path, monkeypatch):
    from flask import Flask

    from web.runtime_host import runtime_identity

    app = Flask("system-runtime-identity")
    app.config.update(DATABASE_PATH=str(tmp_path / "runtime.db"), APS_RUNTIME_OWNER="source-content-test")
    first = runtime_identity(app)
    monkeypatch.setitem(app.config, "APS_RUNTIME_SHUTDOWN_TOKEN", "shutdown-secret-for-contract")
    monkeypatch.setitem(app.config, "SECRET_KEY", "application-secret-for-contract")
    assert runtime_identity(app) == first
    assert first["db_path"] == os.path.normcase(os.path.abspath(str(tmp_path / "runtime.db")))
    assert first["owner"] == "source-content-test" and len(first["instance_id"]) == 32 and first["started_at"]
    assert not {"db_path_hash", "shutdown_token", "SECRET_KEY"}.intersection(first)
    other = Flask("another-system-runtime-identity")
    other.config.update(app.config)
    assert runtime_identity(other)["instance_id"] != first["instance_id"]
    if os.name != "nt":
        alias = tmp_path / "runtime-alias"
        alias.symlink_to(tmp_path, target_is_directory=True)
        app.config["DATABASE_PATH"] = str(alias / "runtime.db")
        assert runtime_identity(app)["db_path"] == str(alias / "runtime.db")
        assert runtime_identity(app)["instance_id"] == first["instance_id"]


@pytest.mark.parametrize("rollback_fails", [True])
def test_verify_failure_and_rollback_failure_are_distinct(system_api, monkeypatch, rollback_fails):
    system_api.backup()
    enable_restore(system_api)
    def verification(*args, **kwargs):
        raise RuntimeError("injected verify failure")
    monkeypatch.setattr("web.routes.workbench.system_actions.ensure_schema", verification)
    copy = BackupManager._copy_db_file
    def failing_copy(self, source_path, **kwargs):
        if rollback_fails and "before_restore" in source_path:
            raise OSError("injected rollback failure")
        return copy(self, source_path, **kwargs)
    monkeypatch.setattr(BackupManager, "_copy_db_file", failing_copy)
    result = system_api.file_action("restore").get_json()["data"]["operation"]
    assert result["code"] == ("verify_failed_rollback_failed" if rollback_fails else "verify_failed_rolled_back")
    assert result["state"] == ("rollback_failed" if rollback_fails else "rolled_back")
    if rollback_fails:
        with pytest.raises(ValueError, match="还没有确认结果"):
            assert_system_maintenance_ready(str(system_api.database), str(system_api.journal_dir))
        assert system_api.get("/backups").status_code == 503
        assert system_api.read("/restore-host")["data"]["host"]["operations_available"] is False
