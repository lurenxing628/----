"""Real HTTP restore terminal and rollback proofs, without a bool guard."""

import sqlite3
import threading
from contextlib import closing

import pytest

from core.infrastructure.backup import BackupManager, RestoreResult
from core.infrastructure.database import get_connection
from core.services.system.backup_restore import RestoreBackupOutcome
from core.services.workbench.facts.run_data_context import RunDataContext
from core.services.workbench.facts.system_journal import assert_system_maintenance_ready, file_fingerprint
from core.services.workbench.system.restore import restore_outcome
from tests.workbench.system_restore_host_support import BASE, KEY, http_json, http_server
from tests.workbench.system_restore_host_support import restore_host as _restore_host  # noqa: F401
from web.bootstrap import factory


def test_ready_host_requests_do_not_scan_journal_history(restore_host, monkeypatch):
    from werkzeug.test import Client
    from werkzeug.wrappers import Response

    from web.bootstrap.launcher_shutdown import RuntimeHostStopTransport

    case = restore_host
    reads, original = [], case.host.journal.records

    def records():
        reads.append(True)
        return original()

    monkeypatch.setattr(case.host.journal, "records", records)
    assert case.client.get("/static/missing.css", buffered=True).status_code == 404
    assert reads == []
    client = Client(RuntimeHostStopTransport(case.app), Response)
    assert client.get("/system/health", buffered=True).status_code == 200
    assert case.client.get(BASE + "/config", buffered=True).status_code == 200
    assert reads == []
    case.host._set_state("recovery_required", "unconfirmed-request")
    assert case.client.get("/static/missing.css", buffered=True).status_code == 503


def test_managed_workbench_access_drives_due_tasks_before_read_snapshot(restore_host, monkeypatch):
    from core.services.system.system_maintenance_service import SystemMaintenanceService

    case = restore_host
    calls = []
    def maintenance(conn, **kwargs):
        calls.append((conn.in_transaction, kwargs["db_path"]))
    monkeypatch.setattr(SystemMaintenanceService, "run_if_due", maintenance)
    assert case.client.get(BASE + "/config", buffered=True).status_code == 200
    assert calls == [(False, case.path)]
    assert case.client.get("/system/health", buffered=True).status_code == 200
    assert case.client.get("/static/missing.css", buffered=True).status_code == 404
    assert calls == [(False, case.path)]


def test_unexpected_maintenance_driver_failure_stops_request_and_closes_connection(restore_host, monkeypatch):
    from core.services.system.system_maintenance_service import SystemMaintenanceService

    case = restore_host
    case.app.config["PROPAGATE_EXCEPTIONS"] = False
    attempted, routed = [], []
    @case.app.get("/system-driver-probe")
    def probe():
        routed.append(True)
        return {"ok": True}
    def failed(conn, **kwargs):
        attempted.append(conn)
        raise RuntimeError("unexpected maintenance driver failure")
    monkeypatch.setattr(SystemMaintenanceService, "run_if_due", failed)
    assert case.client.get("/system-driver-probe", buffered=True).status_code == 500
    assert len(attempted) == 1 and routed == []
    with pytest.raises(sqlite3.ProgrammingError):
        attempted[0].execute("SELECT 1")
    assert case.host.status["state"] == "ready" and case.runtime.ready


def test_busy_automatic_admission_rejects_request_without_stopping_owner(restore_host, monkeypatch):
    from contextlib import contextmanager

    from core.infrastructure.backup import maintenance_window
    from core.services.system.system_maintenance_service import SystemMaintenanceService

    case = restore_host
    with closing(get_connection(case.path)) as conn:
        conn.execute("INSERT INTO SystemConfig(config_key,config_value) VALUES ('auto_backup_enabled','yes')")
        conn.commit()
    admitted, release = threading.Event(), threading.Event()
    actual_admission = case.host.automatic_maintenance
    files_before = list(case.backups.glob("*.db"))
    def competitor():
        with maintenance_window(case.path, action="competing_automatic_task"):
            admitted.set()
            assert release.wait(10)
    @contextmanager
    def racing_admission():
        competitor_thread = threading.Thread(target=competitor)
        competitor_thread.start()
        try:
            assert admitted.wait(5)
            with actual_admission():
                yield
        finally:
            release.set()
            competitor_thread.join(timeout=5)
            assert not competitor_thread.is_alive()
    monkeypatch.setattr(case.host, "automatic_maintenance", racing_admission)
    SystemMaintenanceService.reset_throttle_for_tests()
    try:
        assert case.client.get(BASE + "/config", buffered=True).status_code == 503
        assert case.host.status["state"] == "ready" and case.runtime.ready
        assert list(case.backups.glob("*.db")) == files_before
    finally:
        release.set()
        SystemMaintenanceService.reset_throttle_for_tests()


def test_history_read_during_live_maintenance_does_not_stop_owner(restore_host):
    from core.infrastructure.backup import MaintenanceWindowError, maintenance_window

    case = restore_host
    entered, release = threading.Event(), threading.Event()
    def hold_window():
        with maintenance_window(case.path, action="live_create"):
            entered.set()
            assert release.wait(10)
    worker = threading.Thread(target=hold_window)
    worker.start()
    try:
        assert entered.wait(5)
        with pytest.raises(MaintenanceWindowError):
            case.host.capture_maintenance_records()
        assert case.host.status["state"] == "ready" and case.runtime.ready
    finally:
        release.set()
        worker.join(timeout=5)
    assert not worker.is_alive()
    assert case.host.capture_maintenance_records() == []
    assert case.host.status["operations_available"]


@pytest.mark.parametrize("due", [False, True])
def test_automatic_tasks_read_journal_only_once_when_any_task_is_due(restore_host, monkeypatch, due):
    from datetime import datetime, timedelta

    from core.services.system.system_maintenance_service import SystemMaintenanceService
    from data.repositories.system_job_state_repo import SystemJobStateRepository

    case = restore_host
    with closing(get_connection(case.path)) as conn:
        for key in ("auto_backup_enabled", "auto_backup_cleanup_enabled", "auto_log_cleanup_enabled"):
            conn.execute("INSERT INTO SystemConfig(config_key,config_value) VALUES(?, 'yes')", (key,))
        if not due:
            repo = SystemJobStateRepository(conn)
            for key in ("auto_backup", "auto_backup_cleanup", "auto_log_cleanup"):
                repo.set_last_run(key, last_run_time=(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"), last_run_detail="{}")
        conn.commit()
    scans, records = [], case.host.journal.records
    def tracked(**kwargs):
        scans.append(True)
        return records(**kwargs)
    monkeypatch.setattr(case.host.journal, "records", tracked)
    files_before = list(case.backups.glob("*.db"))
    SystemMaintenanceService.reset_throttle_for_tests()
    try:
        assert case.client.get(BASE + "/config", buffered=True).status_code == 200
        assert scans == ([True] if due else [])
        assert len(list(case.backups.glob("*.db"))) == len(files_before) + int(due)
        assert case.host.status["operations_available"]
    finally:
        SystemMaintenanceService.reset_throttle_for_tests()


def test_busy_restore_preparation_keeps_owner_ready_even_with_original_terminal_record(restore_host):
    from types import SimpleNamespace

    from core.infrastructure.backup import MaintenanceWindowError

    case = restore_host
    row, _ = case.journal.begin(KEY, "restore", {})
    case.journal.record(row, "failed", code="backup_integrity_failed", database_origin="unchanged")
    def busy(**kwargs):
        raise MaintenanceWindowError("maintenance_active", "competing maintenance")
    with pytest.raises(MaintenanceWindowError):
        case.host._prepare(SimpleNamespace(prepare_restore=busy), KEY, {}, lambda: None)
    assert case.host.status["state"] == "ready" and case.runtime.ready


def test_uncertain_create_ack_closes_managed_owner_without_repeating_file_work(restore_host, monkeypatch):
    from core.services.workbench.facts.system_journal import SystemMaintenanceJournal

    case = restore_host
    data = case.client.get(BASE + "/backups", buffered=True).get_json()["data"]
    original = SystemMaintenanceJournal.record
    def fail_ack(self, row, state, **values):
        original(self, row, state, **values)
        if row["action"] == "create" and state == "succeeded":
            raise OSError("create terminal ACK unconfirmed")
    monkeypatch.setattr(SystemMaintenanceJournal, "record", fail_ack)
    response = case.client.post(BASE + "/backups/create", json={"request_key": KEY, "input": {},
        "write_token": data["create_context"]["write_token"]}, buffered=True)
    assert response.status_code == 500
    assert case.host.status["state"] == "recovery_required" and not case.runtime.ready
    assert case.client.get(BASE + "/results/" + KEY, buffered=True).status_code == 200
    assert case.client.post(BASE + "/backups/create", json={}, buffered=True).status_code == 503


@pytest.mark.parametrize("damage", ["pending", "unreadable"])
def test_restore_admission_with_unknown_history_stops_owner_before_file_work(restore_host, damage):
    case = restore_host
    body = case.intent()
    body["request_key"] = "system-" + "8" * 48
    row, _ = case.journal.begin(KEY, "restore", {})
    if damage == "unreadable":
        from pathlib import Path
        Path(case.journal.directory, "corrupt.json").write_text("{", encoding="utf-8")
    response = case.client.post(BASE + "/backups/restore", json=body, buffered=True)
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == ("maintenance_active" if damage == "pending" else "maintenance_unconfirmed")
    assert case.host.status["state"] == "recovery_required" and not case.runtime.ready
    assert case.journal.lookup(body["request_key"]) is None
    assert case.marker() == "current" and not list(case.backups.glob("*before_restore.db"))
    result = case.client.get(BASE + "/results/" + KEY, buffered=True)
    assert result.status_code == 200 and result.get_json()["data"]["operation"]["job_ref"] == row["job_ref"]


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
    def backup_fingerprint_only(path):
        if str(path) == str(case.path):
            raise OSError("terminal diagnostic database read failed")
        return file_fingerprint(path)
    monkeypatch.setattr("core.services.workbench.system.files.file_fingerprint", backup_fingerprint_only)
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
        assert result["database_after_sha256"] is None
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
    assert restore_outcome(RestoreBackupOutcome("", "success", result))[0] == "recovery_required"


def test_known_success_code_with_failed_result_is_unconfirmed():
    result = RestoreResult(ok=False, code="verified", message="inconsistent")
    assert restore_outcome(RestoreBackupOutcome("", "success", result))[0] == "recovery_required"


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
    assert restore_outcome(RestoreBackupOutcome("", category, result))[0] == "recovery_required"
