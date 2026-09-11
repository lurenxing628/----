"""回归测试：SystemJobState 里 last_run_time 是坏时间戳、last_run_detail 是坏 JSON 时，/system/logs 与 /system/backup
页面不应崩溃，而应渲染中文兜底提示（"上次执行时间记录异常，系统会在下次执行后重新记录。"与"上次结果记录异常，详细内容请让维护人员查看日志。"）。"""

from __future__ import annotations

import json

import pytest

from core.infrastructure.database import get_connection
from tests._support.legacy_http import assert_retired_response
from tests._support.sqlite_snapshot import table_rows


def test_system_maintenance_invalid_last_run_visible(app_client, db_path) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO SystemJobState (job_key, last_run_time, last_run_detail) VALUES (?, ?, ?)",
            ("auto_backup", "2026-03-13 08:00:00", "{bad-json"),
        )
        conn.execute(
            "INSERT OR REPLACE INTO SystemJobState (job_key, last_run_time, last_run_detail) VALUES (?, ?, ?)",
            ("auto_backup_cleanup", "2026-03-13 08:00:00", "{bad-json"),
        )
        conn.execute(
            "INSERT OR REPLACE INTO SystemJobState (job_key, last_run_time, last_run_detail) VALUES (?, ?, ?)",
            ("auto_log_cleanup", "坏时间戳", "{bad-json"),
        )
        conn.commit()
        before = table_rows(conn, "SystemJobState")
    finally:
        conn.close()

    assert_retired_response(app_client.get("/system/logs"))
    assert_retired_response(app_client.get("/system/backup"))
    resp = app_client.get("/api/workbench/v1/system/backups")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    payload = resp.get_json()
    assert payload["ok"] is True
    data = payload["data"]
    assert data["scope"] == "backup-files-and-maintenance-events"
    conn = get_connection(db_path)
    try:
        assert table_rows(conn, "SystemJobState") == before
    finally:
        conn.close()
    jobs = {row["event_ref"]: row for row in data["rows"] if row.get("event_source") == "latest_job_state_only"}
    assert jobs["auto_log_cleanup"]["time"] is None
    assert jobs["auto_log_cleanup"]["status"] == "unknown"
    for job_key in ("auto_backup", "auto_backup_cleanup", "auto_log_cleanup"):
        warnings = [issue["message"] for issue in data["sources"] if issue.get("job_key") == job_key]
        assert any("上次结果记录异常，详细内容请让维护人员查看日志。" in message for message in warnings), data["sources"]
    for row in jobs.values():
        assert row["file_capabilities"] == {"download": False, "restore": False, "delete": False}
        assert "{bad-json" not in row["body"] and "Traceback" not in row["body"]
    time_warnings = [issue["message"] for issue in data["sources"] if issue.get("job_key") == "auto_log_cleanup"]
    assert any("上次执行时间记录异常，系统会在下次执行后重新记录。" in message for message in time_warnings)


@pytest.mark.parametrize(
    "state",
    ("unconfigured", "missing", "valid", "bad-time", "zero-time", "bad-json", "non-dict", "json-null", "existing-audit"),
)
def test_workbench_job_diagnostics_preserve_records_and_audits(app_client, db_path, state):
    job_keys = ("auto_backup", "auto_backup_cleanup", "auto_log_cleanup")
    tables = ("SystemJobState", "OperationLogs", "WorkbenchCommandReceipts")
    conn = get_connection(db_path)
    try:
        conn.execute("DELETE FROM SystemJobState")
        conn.execute("INSERT INTO SystemJobState(job_key,last_run_time,last_run_detail) VALUES('unrelated_job','broken','{private-other')")
        if state != "unconfigured":
            for job in job_keys:
                detail = {"filename": "aps_backup_not_present_auto.db"} if job == "auto_backup" else {
                    "removed_count" if job == "auto_backup_cleanup" else "deleted_count": 2}
                time = "2026-04-01 08:00:00"
                raw = json.dumps(detail)
                if state == "missing":
                    time, raw = None, None
                if state in ("bad-time", "existing-audit"):
                    time = "broken-time"
                if state == "zero-time":
                    time = 0
                if state in ("bad-json", "existing-audit"):
                    raw = "{private-job"
                if state == "non-dict":
                    raw = "[]"
                if state == "json-null":
                    raw = "null"
                conn.execute("INSERT INTO SystemJobState(job_key,last_run_time,last_run_detail) VALUES(?,?,?)", (job, time, raw))
        if state == "existing-audit":
            for action in ("cleanup", "logs_cleanup"):
                conn.execute("INSERT INTO OperationLogs(log_time,log_level,module,action,detail) VALUES(?,?,?,?,?)",
                             ("2026-04-02 08:00:00", "INFO", "system", action, json.dumps({"audit_fact": action})))
        conn.commit()
        before = {table: table_rows(conn, table) for table in tables}
        audit_ids = {str(row[0]) for row in conn.execute("SELECT id FROM OperationLogs WHERE module='system' AND action IN ('cleanup','logs_cleanup')")}
    finally:
        conn.close()

    response = app_client.get("/api/workbench/v1/system/backups")
    assert response.status_code == 200
    data = response.get_json()["data"]
    diagnostics = [issue for issue in data["sources"] if issue["code"] in (
        "maintenance_last_time_invalid", "maintenance_last_detail_invalid")]
    time_jobs = {issue["job_key"] for issue in diagnostics if issue["code"] == "maintenance_last_time_invalid"}
    detail_jobs = {issue["job_key"] for issue in diagnostics if issue["code"] == "maintenance_last_detail_invalid"}
    assert time_jobs == (set(job_keys) if state in ("bad-time", "zero-time", "existing-audit") else set())
    assert detail_jobs == (set(job_keys) if state in ("bad-json", "non-dict", "json-null", "existing-audit") else set())
    public = json.dumps(data, ensure_ascii=False)
    assert "private-job" not in public and "private-other" not in public and "broken-time" not in public
    assert not any(row["record_kind"] == "backup_file" for row in data["rows"])
    assert not any(row.get("event_ref") == "auto_backup" for row in data["rows"])
    for row in data["rows"]:
        assert row["file_capabilities"] == {"download": False, "restore": False, "delete": False}
    latest = [row for row in data["rows"] if row.get("event_source") == "latest_job_state_only"]
    audited = [row for row in data["rows"] if row.get("event_source") == "operation_audit"]
    if state in ("unconfigured", "missing", "existing-audit"):
        assert latest == []
    else:
        assert {row["event_ref"] for row in latest} == {"auto_backup_cleanup", "auto_log_cleanup"}
        assert all(row["status"] == ("unknown" if detail_jobs else "succeeded") for row in latest)
        assert all((row["time"] is None) is bool(time_jobs) for row in latest)
        if not detail_jobs:
            for row in latest:
                detail = json.loads(row["body"])["detail"]
                assert detail == {"removed_count" if row["event_ref"] == "auto_backup_cleanup" else "deleted_count": 2}
    if state == "existing-audit":
        assert {row["event_ref"] for row in audited} == audit_ids and len(audited) == 2
        assert all(row["status"] == "succeeded" and row["time"] == "2026-04-02T08:00:00" for row in audited)
        for row in audited:
            detail = json.loads(row["body"])
            assert detail["detail"] == {"audit_fact": detail["action"]}
    conn = get_connection(db_path)
    try:
        assert {table: table_rows(conn, table) for table in tables} == before
    finally:
        conn.close()
