"""Fault injection only in our fresh disposable test DB and backup directory."""

import json
import threading

import pytest

from core.infrastructure.backup import BackupManager, maintenance_window
from core.services.workbench.system_journal import assert_system_maintenance_ready
from tests.workbench.test_system_restore_entrypoint_legacy_support import (
    system_api as _system_api_fixture,  # noqa: F401
)


def enable_restore(api):
    from web.bootstrap.workbench_system_restore import WorkbenchSystemRestoreHost
    host = api.app.extensions["workbench_system_restore_host"]
    assert isinstance(host, WorkbenchSystemRestoreHost)
    assert api.app.extensions["workbench_system_restore_guard"] is host
    assert host.runtime.ready and host.status["operations_available"]
    host.verify()


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
    looked_up = system_api.read("/results/system-test-request-0001")["data"]["operation"]
    assert looked_up["replayed"] is True
    assert looked_up["job_ref"] == result["job_ref"]
    assert_system_maintenance_ready(str(system_api.database), str(system_api.journal_dir))


def test_protection_failure_never_modifies_database(system_api, monkeypatch):
    system_api.backup()
    before = system_api.database.read_bytes()
    enable_restore(system_api)
    original = BackupManager.backup
    def fail(self, suffix=None):
        if suffix and suffix.endswith("before_restore"):
            raise OSError("injected protection disk error")
        return original(self, suffix)
    monkeypatch.setattr(BackupManager, "backup", fail)
    result = system_api.file_action("restore").get_json()["data"]["operation"]
    assert result["code"] == "before_restore_backup_failed" and result["state"] == "failed"
    assert system_api.database.read_bytes() == before
    assert result["protection_filename"] is None
    assert not list(system_api.backups.glob("*before_restore.db"))


@pytest.mark.parametrize("rollback_fails", [False, True])
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
        with pytest.raises(ValueError, match="未核实"):
            assert_system_maintenance_ready(str(system_api.database), str(system_api.journal_dir))
        assert system_api.get("/backups").status_code == 503
        assert system_api.read("/restore-host")["data"]["host"]["operations_available"] is False


def test_corrupt_backup_never_becomes_success(system_api):
    (system_api.backups / "aps_backup_bad.db").write_bytes(b"not a sqlite database")
    before = system_api.database.read_bytes()
    enable_restore(system_api)
    result = system_api.file_action("restore").get_json()["data"]["operation"]
    assert result["state"] == "failed" and result["code"] == "backup_integrity_failed"
    assert result["protection_filename"]
    assert system_api.database.read_bytes() == before


@pytest.mark.parametrize("rollback_fails", [False, True])
def test_copy_failure_retains_actual_rollback_outcome(system_api, monkeypatch, rollback_fails):
    system_api.backup()
    enable_restore(system_api)
    original = BackupManager._copy_db_file
    def fail(self, source_path, **kwargs):
        if "before_restore" not in source_path or rollback_fails:
            raise OSError("injected database copy failure")
        return original(self, source_path, **kwargs)
    monkeypatch.setattr(BackupManager, "_copy_db_file", fail)
    result = system_api.file_action("restore").get_json()["data"]["operation"]
    assert result["code"] == ("restore_failed_rollback_failed" if rollback_fails else "restore_failed_rolled_back")
    assert result["state"] == ("rollback_failed" if rollback_fails else "rolled_back")


def test_busy_does_not_accept_or_run_operation(system_api):
    entered, release = threading.Event(), threading.Event()
    token = system_api.read("/backups")["data"]["create_context"]["write_token"]
    def holder():
        with maintenance_window(str(system_api.database), action="test-only-busy"):
            entered.set()
            release.wait(10)
    thread = threading.Thread(target=holder)
    thread.start()
    try:
        assert entered.wait(5)
        response = system_api.post("/backups/create", {}, token)
        assert response.status_code == 503
        assert response.get_json()["error"]["code"] == "service_unavailable"
        assert system_api.journal().lookup("system-test-request-0001") is None
    finally:
        release.set()
        thread.join(10)


def test_interrupted_record_blocks_new_actions_and_is_never_replayed(system_api):
    journal = system_api.journal()
    row, _ = journal.begin("system-test-request-0001", "create", {})
    journal.record(row, "checking")
    response = system_api.get("/results/system-test-request-0001")
    assert response.get_json()["data"]["operation"]["state"] == "checking"
    assert list(system_api.backups.iterdir()) == []
    other = system_api.post("/backups/create", {}, "old-token", key="system-test-request-0002")
    assert other.status_code == 503
    assert len(list(system_api.journal_dir.glob("*.json"))) == 1


def test_damaged_journal_fails_closed(system_api):
    (system_api.journal_dir / "damaged.json").write_text('{"state":')
    with pytest.raises(json.JSONDecodeError):
        assert_system_maintenance_ready(str(system_api.database), str(system_api.journal_dir))
    assert system_api.get("/backups").status_code == 503
    assert system_api.read("/restore-host")["data"]["host"]["operations_available"] is False
