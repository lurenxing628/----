"""Temporary SQLite/backup directories only, including destructive single-delete tests."""

import io
import json
import zipfile
from contextlib import closing

import pytest

from core.services.system.system_config_service import SystemConfigService
from core.services.workbench.run_data_context import RunDataContext
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
    def context_ref():
        with closing(system_api.connect()) as conn:
            return RunDataContext(conn, str(system_api.journal_dir), str(system_api.backups)).ref()

    before_context = context_ref()
    response = system_api.file_action("create")
    assert response.status_code == 200, response.get_json()
    result = response.get_json()["data"]["operation"]
    assert result["code"] == "backup_verified"
    assert result["terminal"] is True and result["audit_persisted"] is True
    assert context_ref() == before_context
    row = system_api.selected()
    assert row["verification_state"] == "not_checked"
    assert "_signature" not in row and "path" not in row
    deleted = system_api.file_action("delete", row, "system-test-request-0002")
    assert deleted.status_code == 200, deleted.get_json()
    assert deleted.get_json()["data"]["operation"]["state"] == "succeeded"
    assert context_ref() == before_context
    replay = system_api.file_action("delete", row, "system-test-request-0002")
    assert replay.get_json()["data"]["operation"]["replayed"] is True
    assert list(system_api.backups.glob("*.db")) == []
    assert context_ref() == before_context
    assert all("data_context_before" not in row for row in system_api.journal().records())


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
    retained = system_api.get("/logs/export/csv", type="runtime", snapshot_ref=token)
    assert retained.status_code == 200 and retained.data == csv.data
    refreshed = system_api.read("/logs", type="runtime")
    fresh_export = system_api.get("/logs/export/csv", type="runtime", snapshot_ref=refreshed["meta"]["snapshot_ref"])
    assert fresh_export.status_code == 200 and "[ERROR] new" in fresh_export.data.decode("utf-8")


def test_read_request_logging_cannot_invalidate_its_own_log_window(system_api):
    from flask import request

    path = system_api.logs / "aps.log"
    path.write_text("".join(f"2026-09-09 10:00:{index:02d} [INFO] captured row {index}\n" for index in range(30)), encoding="utf-8")
    emitted = []

    @system_api.app.after_request
    def log_slow_request(response):
        if "/system/logs" in request.path:
            emitted.append(request.path)
            with path.open("a", encoding="utf-8") as stream:
                stream.write(f"2026-09-09 11:00:{len(emitted):02d} [WARNING] 慢请求: GET {request.path}\n")
        return response

    initial = system_api.read("/logs", type="runtime", page_size="10")
    token = initial["meta"]["snapshot_ref"]
    assert len(emitted) == 1 and initial["data"]["page"]["total"] == 30
    page = system_api.read("/logs", type="runtime", page_size="10", page="2", snapshot_ref=token)
    assert page["meta"]["snapshot_ref"] == token and page["data"]["page"]["total"] == 30
    assert page["data"]["sources"] == initial["data"]["sources"]
    assert {row["key"] for row in initial["data"]["rows"]}.isdisjoint(row["key"] for row in page["data"]["rows"])
    csv = system_api.get("/logs/export/csv", type="runtime", snapshot_ref=token)
    archive = system_api.get("/logs/export/zip", type="runtime", snapshot_ref=token)
    assert csv.status_code == archive.status_code == 200
    text = csv.data.decode("utf-8-sig")
    assert text.count("captured row ") == 30 and "慢请求" not in text
    with zipfile.ZipFile(io.BytesIO(archive.data)) as package:
        assert package.testzip() is None and package.read("logs.csv") == csv.data
        info = json.loads(package.read("diagnostic_info.json"))
        assert info["rows"] == 30 and info["sources"] == initial["data"]["sources"]
        assert info["as_of"] == initial["meta"]["as_of"]
    assert len(emitted) == 4
    fresh = system_api.read("/logs", type="runtime")
    assert fresh["data"]["page"]["total"] == 34
    assert fresh["meta"]["snapshot_ref"] != token


@pytest.mark.parametrize("change", ("scope", "unknown_token", "missing_window", "expired_window", "changed_window", "expired_token"))
def test_retained_log_window_does_not_bypass_scope_expiry_or_content_guards(system_api, change):
    from dataclasses import replace

    from web.routes.workbench.system_log_snapshots import _EXTENSION

    (system_api.logs / "aps.log").write_text("2026-09-09 10:00:00 [INFO] original\n", encoding="utf-8")
    original = system_api.read("/logs", type="runtime")
    token = original["meta"]["snapshot_ref"]
    query = {"type": "runtime", "snapshot_ref": token}
    if change == "scope":
        query["file"] = "aps.log"
    elif change == "unknown_token":
        query["snapshot_ref"] = "not-the-read-window"
    else:
        with system_api.app.app_context():
            windows = system_api.app.extensions[_EXTENSION]
            if change == "missing_window":
                windows.clear()
            elif change == "expired_window":
                windows[token] = replace(windows[token], expires_at=0)
            elif change == "changed_window":
                data = json.loads(windows[token].document)
                data["rows"][0]["summary"] = "replaced after approval"
                windows[token] = replace(windows[token], document=json.dumps(data))
            else:
                from web import public_token_registry
                for scope in public_token_registry._registry().values():
                    for entry in scope["tokens"].values():
                        entry["expires_at"] = 0
    response = system_api.get("/logs/export/csv", **query)
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"
    assert "Content-Disposition" not in response.headers


@pytest.mark.parametrize("maintenance", ("restore", "create"))
def test_log_snapshot_binds_database_restore_generation(system_api, maintenance):
    initial = system_api.read("/logs")
    token = initial["meta"]["snapshot_ref"]
    journal = system_api.journal()
    row, _ = journal.begin("log-snapshot-generation-0001", maintenance, {})
    journal.record(row, "succeeded", code="verified")
    response = system_api.get("/logs/export/csv", snapshot_ref=token)
    assert response.status_code == (409 if maintenance == "restore" else 200)
    if maintenance == "restore":
        assert response.get_json()["error"]["code"] == "snapshot_stale"
        fresh = system_api.read("/logs")
        assert system_api.get("/logs/export/csv", snapshot_ref=fresh["meta"]["snapshot_ref"]).status_code == 200


@pytest.mark.parametrize("bound", ("entries", "bytes"))
def test_log_snapshot_cache_is_bounded_without_truncating_exports(system_api, monkeypatch, bound):
    from web.routes.workbench import system_log_snapshots as snapshots

    (system_api.logs / "aps.log").write_text("2026-09-09 10:00:00 [INFO] original\n", encoding="utf-8")
    first = system_api.read("/logs")
    token = first["meta"]["snapshot_ref"]
    with system_api.app.app_context():
        size = system_api.app.extensions[snapshots._EXTENSION][token].size_bytes
    monkeypatch.setattr(snapshots, "_MAX_WINDOWS", 1 if bound == "entries" else 32)
    monkeypatch.setattr(snapshots, "_MAX_BYTES", size + 1 if bound == "bytes" else 64 * 1024 * 1024)
    second = system_api.read("/logs", query="original")
    with system_api.app.app_context():
        windows = system_api.app.extensions[snapshots._EXTENSION]
        assert len(windows) == 1 and sum(item.size_bytes for item in windows.values()) <= snapshots._MAX_BYTES
    assert system_api.get("/logs/export/csv", snapshot_ref=token).status_code == 409
    exported = system_api.get("/logs/export/csv", query="original", snapshot_ref=second["meta"]["snapshot_ref"])
    assert exported.status_code == 200 and b"original" in exported.data


def test_oversized_log_snapshot_reports_failure_without_partial_export(system_api, monkeypatch):
    from web.routes.workbench import system_log_snapshots as snapshots

    monkeypatch.setattr(snapshots, "_MAX_BYTES", 1)
    response = system_api.get("/logs")
    assert response.status_code == 503 and response.get_json()["error"]["code"] == "snapshot_capacity_exceeded"


@pytest.mark.parametrize("query", [{"start": "2026-02-30"}, {"start": "2026-09-10", "end": "2026-09-09"},
    {"file": "../aps_secret_key.txt"}, {"page_size": "200"}, {"status": "succeeded"}, {"unknown": "x"}])
def test_invalid_log_query_is_not_silently_changed(system_api, query):
    assert system_api.get("/logs", **query).status_code in (400, 422)
