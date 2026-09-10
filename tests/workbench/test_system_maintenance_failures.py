"""Persistence and telemetry faults exercise only our disposable fixture files."""

import json

import pytest

from core.infrastructure.logging import OperationLogger
from core.services.workbench.system_exports import logs_csv
from core.services.workbench.system_journal import SystemMaintenanceJournal, assert_system_maintenance_ready
from core.services.workbench.system_redaction import public_system_text
from tests.workbench.system_maintenance_support import system_api as _system_api_fixture  # noqa: F401


def test_audit_failure_does_not_invent_backup_failure(system_api, monkeypatch):
    monkeypatch.setattr("web.routes.workbench.system_actions._audit_file", lambda result: False)
    response = system_api.file_action("create")
    operation = response.get_json()["data"]["operation"]
    assert operation["state"] == "succeeded"
    assert operation["audit_persisted"] is False
    assert len(list(system_api.backups.glob("*.db"))) == 1


def test_config_audit_failure_rolls_back_both_groups(system_api, monkeypatch):
    data = system_api.read("/config")["data"]
    def fail(*args, **kwargs):
        raise OSError("injected audit failure")
    monkeypatch.setattr(OperationLogger, "info", fail)
    response = system_api.post("/config/save", data["values"], data["write_context"]["write_token"])
    assert response.status_code == 500
    conn = system_api.connect()
    try:
        for table in ("SystemConfig", "WorkbenchCommandReceipts", "OperationLogs"):
            assert conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0
    finally:
        conn.close()


def test_intent_fsync_failure_prevents_file_work(system_api, monkeypatch):
    def fail(*args):
        raise OSError("injected fsync failure")
    monkeypatch.setattr("core.services.workbench.system_journal.os.fsync", fail)
    response = system_api.file_action("create")
    assert response.status_code == 500
    assert list(system_api.backups.glob("*.db")) == []
    assert system_api.journal().lookup("system-test-request-0001") is None


def test_result_write_failure_keeps_unknown_and_does_not_repeat_backup(system_api, monkeypatch):
    original = SystemMaintenanceJournal.record
    def fail(self, row, state, **values):
        if state == "succeeded":
            raise OSError("injected terminal record failure")
        return original(self, row, state, **values)
    monkeypatch.setattr(SystemMaintenanceJournal, "record", fail)
    response = system_api.file_action("create")
    assert response.status_code == 500
    assert response.get_json()["committed"] == "unknown"
    assert response.get_json()["error"]["result_target"].endswith("/system/results/system-test-request-0001")
    files = list(system_api.backups.glob("*.db"))
    assert len(files) == 1
    replay = system_api.file_action("create").get_json()["data"]["operation"]
    assert replay["terminal"] is False
    assert list(system_api.backups.glob("*.db")) == files
    with pytest.raises(ValueError):
        assert_system_maintenance_ready(str(system_api.database), str(system_api.journal_dir))


def test_checksum_changed_terminal_is_not_trusted(system_api):
    assert system_api.file_action("create").status_code == 200
    path = next(system_api.journal_dir.glob("*.json"))
    row = json.loads(path.read_text())
    row["code"] = "different"
    path.write_text(json.dumps(row))
    with pytest.raises(RuntimeError, match="不完整"):
        system_api.journal().pending()


def test_log_read_failure_is_visible_and_not_zero(system_api, monkeypatch):
    (system_api.logs / "aps.log").write_text("2026-09-09 12:00:00 [INFO] text\n")
    def fail(*args, **kwargs):
        raise PermissionError("sensitive/path/not/public")
    monkeypatch.setattr("core.services.workbench.system_reads.read_log_entries_tail", fail)
    sources = system_api.read("/logs")["data"]["sources"]
    failed = next(item for item in sources if item["source"] == "aps.log")
    assert failed["state"] == "error" and failed["count"] is None
    assert "sensitive" not in json.dumps(sources)


def test_request_keys_cannot_collide_between_file_and_config(system_api):
    assert system_api.file_action("create").status_code == 200
    config = system_api.read("/config")["data"]
    collision = system_api.post("/config/save", config["values"], config["write_context"]["write_token"])
    assert collision.status_code == 409
    saved = system_api.post("/config/save", config["values"], config["write_context"]["write_token"], "system-test-request-0002")
    assert saved.status_code == 200
    assert system_api.file_action("create", key="system-test-request-0002").status_code == 409


@pytest.mark.parametrize("text", ["Authorization: Bearer CANARY", '{"api_key":"CANARY"}', "password=CANARY", "C:\\CANARY\\a.db", "/data/CANARY/a.db",
    "-----BEGIN PRIVATE KEY-----\nCANARY\n-----END PRIVATE KEY-----"])
def test_sensitive_text_never_reaches_diagnostic(text):
    assert "CANARY" not in public_system_text(text)


def test_csv_formula_is_literal():
    csv = logs_csv([{"file": "aps.log", "time": None, "type": "runtime", "level": "INFO", "status": "recorded", "summary": "=HYPERLINK(1)", "body": "  +1"}]).decode("utf-8-sig")
    assert "'=HYPERLINK(1)" in csv and "'  +1" in csv
