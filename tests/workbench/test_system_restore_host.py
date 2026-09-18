"""Real HTTP restore terminal and rollback proofs, without a bool guard."""

import sqlite3
from contextlib import closing

import pytest

from core.infrastructure.backup import BackupManager, RestoreResult
from core.infrastructure.database import get_connection
from core.services.system.backup_restore import RestoreBackupOutcome
from core.services.workbench.run_data_context import RunDataContext
from core.services.workbench.system_journal import assert_system_maintenance_ready, file_fingerprint
from core.services.workbench.system_restore import restore_outcome
from tests.workbench.system_restore_host_support import BASE, KEY, http_json, http_server
from tests.workbench.system_restore_host_support import restore_host as _restore_host  # noqa: F401
from web.bootstrap import factory


def test_real_http_verified_restore_requires_process_restart_and_external_receipt(restore_host, monkeypatch):
    case = restore_host
    with closing(get_connection(case.path)) as conn:
        before_context = RunDataContext(conn, case.journal.directory, str(case.backups)).ref()
    body = case.intent()
    config = case.client.get(BASE + "/config", buffered=True).get_json()["data"]
    saved = case.client.post(BASE + "/config/save", json={"request_key": "dh-config-before-restore-000001",
        "write_token": config["write_context"]["write_token"], "input": config["values"]}, buffered=True)
    assert saved.status_code == 200, saved.get_json()
    source_hash = file_fingerprint(case.source)
    opened = []
    original = factory.get_connection
    def tracked(path):
        conn = original(path)
        opened.append(conn)
        return conn
    monkeypatch.setattr(factory, "get_connection", tracked)
    with http_server(case.app) as port:
        status, payload = http_json(port, BASE + "/backups/restore", body)
        assert status == 200, payload
        result = payload["data"]["operation"]
        assert (result["state"], result["code"]) == ("succeeded", "verified")
        assert result["target_sha256"] == source_hash
        assert result["protection_sha256"] == file_fingerprint(str(case.backups / result["protection_filename"]))
        assert result["database_after_sha256"] == file_fingerprint(case.path)
        assert result["database_origin"] == "selected_backup"
        assert result["restart_required"] and result["references_require_reload"]
        assert result["result_source"] == "external_maintenance_journal"
        assert payload["data"]["host"]["state"] == "restart_required"
        assert case.marker() == "selected"
        assert case.marker(path=str(case.backups / result["protection_filename"])) == "current"
        count = len(opened)
        for path in ("/workbench", "/static/missing.css", "/scheduler/", "/system/runtime/shutdown", BASE + "/backups/restore"):
            assert http_json(port, path, body)[0] == 503
        for path in (BASE + "/results/" + KEY, BASE + "/jobs/" + result["job_ref"]):
            status, replay = http_json(port, path, method="GET")
            assert status == 200 and replay["data"]["operation"]["job_ref"] == result["job_ref"]
            assert replay["data"]["operation"]["replayed"]
        assert len(opened) == count
        status, missing = http_json(port, BASE + "/results/dh-config-before-restore-000001", method="GET")
        assert status == 200 and missing["data"]["kind"] == "not_recorded"
        assert "不能就此认定没有执行" in missing["data"]["message"]
        with closing(get_connection(str(case.backups / result["protection_filename"]))) as conn:
            assert conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 1
    assert not case.runtime.ready and case.runtime.status["closed"]
    assert case.app.config["WORKBENCH_CANDIDATE_ADOPTION_ENABLED"] is False
    assert "workbench_run_dispatcher" not in case.app.extensions
    case.assert_locks_held()
    for conn in opened:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            conn.execute("SELECT 1")
    with closing(get_connection(case.path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM OperationLogs WHERE action='workbench_restore'").fetchone()[0] == 1
        context = RunDataContext(conn, case.journal.directory, str(case.backups))
        assert context.ref() != before_context
        assert context.resolve_missing("restore-context-lost-run-000001", before_context) == "context_replaced"
    record = case.journal.lookup(KEY)
    assert record["data_context_before"] == before_context
    assert_system_maintenance_ready(case.path, case.journal.directory)


@pytest.mark.parametrize("rollback_fails", [False, True])
def test_http_verify_failure_rolls_back_or_stays_unconfirmed(restore_host, monkeypatch, rollback_fails):
    case, original = restore_host, BackupManager._copy_db_file
    body = case.intent()
    def verify(*args, **kwargs):
        raise RuntimeError("DH injected verification failure")
    def copy(manager, source_path, **kwargs):
        if rollback_fails and "before_restore" in source_path:
            raise OSError("DH rollback failure")
        return original(manager, source_path, **kwargs)
    monkeypatch.setattr("web.routes.workbench.system_actions.ensure_schema", verify)
    monkeypatch.setattr(BackupManager, "_copy_db_file", copy)
    with http_server(case.app) as port:
        status, payload = http_json(port, BASE + "/backups/restore", body)
        assert status == 200, payload
        result = payload["data"]["operation"]
        assert result["state"] == ("rollback_failed" if rollback_fails else "rolled_back")
        assert result["terminal"] is (not rollback_fails)
        assert result["database_origin"] == ("unconfirmed" if rollback_fails else "protection_backup")
        assert case.marker() == ("selected" if rollback_fails else "current")
        assert http_json(port, "/workbench", method="GET")[0] == 503
    case.assert_locks_held()
    if rollback_fails:
        with pytest.raises(ValueError, match="还没有确认结果"):
            assert_system_maintenance_ready(case.path, case.journal.directory)
    else:
        assert_system_maintenance_ready(case.path, case.journal.directory)


def test_bool_guard_is_not_real_integration(restore_host):
    case = restore_host
    body = case.intent()
    case.app.extensions.pop("workbench_system_restore_host")
    case.app.extensions["workbench_system_restore_guard"] = lambda: True
    response = case.client.post(BASE + "/backups/restore", json=body, buffered=True)
    assert response.status_code == 503 and case.journal.lookup(KEY) is None
    assert case.marker() == "current" and case.runtime.ready


@pytest.mark.parametrize("code", ["new_rolled_back", "new_rollback_failed", "new_success", "copied_pending_verify"])
def test_unknown_restore_terminal_never_authorizes_success(code):
    result = RestoreResult(ok=True, code=code, message="unknown")
    manager = type("Manager", (), {"restore_result": result, "rollback_result": None})()
    assert restore_outcome(manager, RestoreBackupOutcome("", "success", result))[0] == "recovery_required"


def test_known_success_code_with_failed_result_is_unconfirmed():
    result = RestoreResult(ok=False, code="verified", message="inconsistent")
    manager = type("Manager", (), {"restore_result": result, "rollback_result": None})()
    assert restore_outcome(manager, RestoreBackupOutcome("", "success", result))[0] == "recovery_required"


def test_failed_protection_keeps_original_database_but_requires_restart(restore_host, monkeypatch):
    case = restore_host
    body = case.intent()
    original = BackupManager.backup
    def fail(manager, suffix=None):
        if suffix and "before_restore" in suffix:
            raise OSError("DH protection failure")
        return original(manager, suffix)
    monkeypatch.setattr(BackupManager, "backup", fail)
    response = case.client.post(BASE + "/backups/restore", json=body, buffered=True)
    result = response.get_json()["data"]["operation"]
    assert (result["state"], result["code"]) == ("failed", "before_restore_backup_failed")
    assert case.marker() == "current" and not case.runtime.ready
    assert result["database_origin"] == "unchanged" and result["protection_filename"] is None


@pytest.mark.parametrize("ok,category", [(True, "error"), (False, "success")])
def test_inconsistent_rollback_flags_are_not_confirmed(ok, category):
    result = RestoreResult(ok=ok, code="verify_failed_rolled_back", message="inconsistent")
    manager = type("Manager", (), {"restore_result": result, "rollback_result": None})()
    assert restore_outcome(manager, RestoreBackupOutcome("", category, result))[0] == "recovery_required"
