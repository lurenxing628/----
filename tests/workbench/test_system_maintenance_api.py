"""Temporary SQLite/backup directories only, including destructive single-delete tests."""

import io
import json
import zipfile

import pytest

from core.services.system.system_config_service import SystemConfigService
from tests.workbench.system_maintenance_support import system_api as _system_api_fixture  # noqa: F401


def test_config_read_does_not_persist_defaults(system_api):
    data = system_api.read("/config")["data"]
    assert len(data["defaulted_fields"]) == 8
    conn = system_api.connect()
    assert conn.execute("SELECT COUNT(*) FROM SystemConfig").fetchone()[0] == 0
    conn.close()


def test_config_atomic_save_audit_replay_and_stale_guard(system_api):
    before = system_api.read("/config")["data"]
    values = {**before["values"], "auto_backup_interval_minutes": 37}
    token = before["write_context"]["write_token"]
    response = system_api.post("/config/save", values, token)
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    assert result["result"] == "committed"
    assert result["data"]["audit_persisted"] is True
    replay = system_api.post("/config/save", values, "expired-token")
    assert replay.get_json()["receipt_ref"] == result["receipt_ref"]
    assert replay.get_json()["replayed"] is True
    stale = system_api.post("/config/save", {**values, "auto_backup_interval_minutes": 39}, token, "system-test-request-0002")
    assert stale.status_code == 409
    conflict = system_api.post("/config/save", before["values"], token)
    assert conflict.status_code == 409
    receipt = system_api.read("/results/system-test-request-0001")["data"]
    assert receipt["kind"] == "config"
    conn = system_api.connect()
    assert conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 1
    record = conn.execute("SELECT detail FROM OperationLogs WHERE action='workbench_config_save'").fetchone()[0]
    assert json.loads(record)["before"] == before["stored_values"]
    assert json.loads(record)["after"]["auto_backup_interval_minutes"] == "37"
    conn.close()


@pytest.mark.parametrize("field,value", [("auto_backup_enabled", "maybe"), ("auto_backup_interval_minutes", True),
    ("auto_backup_keep_days", 0), ("auto_backup_keep_days", 366), ("auto_log_cleanup_interval_minutes", 1441),
    ("auto_backup_interval_minutes", ""), ("auto_backup_interval_minutes", 1.5)])
def test_bad_config_rejected_without_writes(system_api, field, value):
    data = system_api.read("/config")["data"]
    result = system_api.post("/config/save", {**data["values"], field: value}, data["write_context"]["write_token"])
    assert result.status_code == 422
    assert system_api.read("/config")["data"]["values"] == data["values"]


def test_second_group_failure_rolls_back_first_group_and_receipt(system_api, monkeypatch):
    data = system_api.read("/config")["data"]
    def fail(*args, **kwargs):
        raise RuntimeError("injected second group failure")
    monkeypatch.setattr(SystemConfigService, "update_logs_settings", fail)
    response = system_api.post("/config/save", data["values"], data["write_context"]["write_token"])
    assert response.status_code == 500
    conn = system_api.connect()
    assert conn.execute("SELECT COUNT(*) FROM SystemConfig").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 0
    conn.close()
    assert system_api.read("/results/system-test-request-0001")["data"]["kind"] == "not_recorded"


def test_real_backup_create_single_delete_replay_and_no_fake_verification(system_api):
    response = system_api.file_action("create")
    assert response.status_code == 200, response.get_json()
    result = response.get_json()["data"]["operation"]
    assert result["code"] == "backup_verified"
    assert result["terminal"] is True and result["audit_persisted"] is True
    row = system_api.selected()
    assert row["verification_state"] == "not_checked"
    assert "_signature" not in row and "path" not in row
    deleted = system_api.file_action("delete", row, "system-test-request-0002")
    assert deleted.status_code == 200, deleted.get_json()
    assert deleted.get_json()["data"]["operation"]["state"] == "succeeded"
    replay = system_api.file_action("delete", row, "system-test-request-0002")
    assert replay.get_json()["data"]["operation"]["replayed"] is True
    assert list(system_api.backups.glob("*.db")) == []


def test_restore_is_disabled_without_host_global_guard(system_api):
    system_api.backup()
    response = system_api.file_action("restore")
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "maintenance_unavailable"
    assert system_api.journal().lookup("system-test-request-0001") is None
    assert system_api.read("/backups")["data"]["capabilities"]["restore"] is False


def test_stale_backup_and_user_paths_never_delete(system_api):
    path = system_api.backup()
    row = system_api.selected()
    with open(path, "ab") as stream:
        stream.write(b"changed")
    assert system_api.file_action("delete", row).status_code == 409
    result = system_api.post("/backups/delete", {"filename": path}, row["write_context"]["write_token"])
    assert result.status_code == 400
    assert system_api.journal().lookup("system-test-request-0001") is None


@pytest.mark.parametrize("module,action,expected", [
    ("scheduler", "schedule", "排产管理 · 排产"),
    (" system ", " backup ", "系统管理 · 备份"),
    ("raw_mod", "raw_act", "其他模块（raw_mod） · 其他操作（raw_act）"),
    ("", "", "- · -"),
])
def test_operation_log_summary_uses_shared_labels_without_rewriting_audit(system_api, module, action, expected):
    conn = system_api.connect()
    try:
        detail = '{"message":"日志标签回归原记录"}'
        conn.execute("INSERT INTO OperationLogs(log_time,log_level,module,action,detail) VALUES (?,?,?,?,?)",
                     ("2026-09-11 08:00:00", "INFO", module, action, detail))
        conn.commit()
        before = tuple(conn.iterdump())
        row, = system_api.read("/logs", type="operation", file="OperationLogs")["data"]["rows"]
        assert row["summary"] == expected
        assert "日志标签回归原记录" in row["body"]
        assert tuple(conn.execute("SELECT module,action,detail FROM OperationLogs").fetchone()) == (module, action, detail)
        assert tuple(conn.iterdump()) == before
    finally:
        conn.close()


def test_windows_filter_pagination_export_and_diagnostic_redaction(system_api):
    entries = [f"2026-09-09 10:00:{index % 60:02d} [INFO] row {index}\n" for index in range(220)]
    entries[-1] = "2026-09-09 11:00:00 [ERROR] failure\nAuthorization: Bearer secret-test-sentinel\n/Users/private/db/main.db\n"
    (system_api.logs / "aps.log").write_text("".join(entries), encoding="utf-8")
    (system_api.logs / "aps_secret_key.txt").write_text("SECRET-FILE-SENTINEL", encoding="utf-8")
    conn = system_api.connect()
    conn.executemany("INSERT INTO OperationLogs(log_level,module,action,detail) VALUES ('INFO','test','event',?)", [("row " + str(index),) for index in range(510)])
    conn.commit()
    conn.close()
    payload = system_api.read("/logs", type="runtime", page_size="10")
    assert payload["data"]["page"]["total"] == 200
    assert len(payload["data"]["rows"]) == 10
    assert all(row["status"] == "recorded" for row in payload["data"]["rows"])
    sources = {item["source"]: item for item in payload["data"]["sources"]}
    assert sources["aps.log"]["truncated"] is True
    assert sources["OperationLogs"]["truncated"] is True
    assert sources["aps_error.log"]["state"] == "missing"
    token = payload["meta"]["snapshot_ref"]
    csv = system_api.get("/logs/export/csv", type="runtime", snapshot_ref=token)
    assert csv.status_code == 200
    assert csv.data.startswith(b"\xef\xbb\xbf")
    assert "row 21" in csv.data.decode("utf-8")
    archive = system_api.get("/logs/export/zip", type="runtime", snapshot_ref=token)
    assert archive.status_code == 200, archive.get_json()
    with zipfile.ZipFile(io.BytesIO(archive.data)) as package:
        assert "aps_secret_key.txt" not in package.namelist()
        assert "aps_error.log_READ_FAILED.txt" in package.namelist()
        raw = "\n".join(package.read(name).decode("utf-8") for name in package.namelist())
        assert "secret-test-sentinel" not in raw and "SECRET-FILE-SENTINEL" not in raw
        assert "/Users/private" not in raw
    assert all(path.suffix != ".zip" for path in system_api.root.rglob("*"))
    with (system_api.logs / "aps.log").open("a", encoding="utf-8") as stream:
        stream.write("2026-09-09 12:00:00 [ERROR] new\n")
    assert system_api.get("/logs/export/csv", type="runtime", snapshot_ref=token).status_code == 409


@pytest.mark.parametrize("query", [{"start": "2026-02-30"}, {"start": "2026-09-10", "end": "2026-09-09"},
    {"file": "../aps_secret_key.txt"}, {"page_size": "200"}, {"status": "succeeded"}, {"unknown": "x"}])
def test_invalid_log_query_is_not_silently_changed(system_api, query):
    assert system_api.get("/logs", **query).status_code in (400, 422)
