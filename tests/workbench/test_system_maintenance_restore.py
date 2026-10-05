"""Fault injection only in our fresh disposable test DB and backup directory."""


import pytest

from core.infrastructure.backup import BackupManager
from core.services.workbench.facts.system_journal import assert_system_maintenance_ready
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
