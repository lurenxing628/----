"""回归测试：SystemJobState 里 last_run_time 是坏时间戳、last_run_detail 是坏 JSON 时，/system/logs 与 /system/backup
页面不应崩溃，而应渲染中文兜底提示（"上次执行时间记录异常，系统会在下次执行后重新记录。"与"上次结果记录异常，详细内容请让维护人员查看日志。"）。"""

from __future__ import annotations

from core.infrastructure.database import get_connection


def _assert_status(resp, name: str, expect: int = 200) -> None:
    if resp.status_code != expect:
        body = resp.data.decode("utf-8", errors="ignore") if getattr(resp, "data", None) else ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect}，body={body[:500]}")


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
    finally:
        conn.close()

    resp = app_client.get("/system/logs")
    _assert_status(resp, "GET /system/logs")
    html = resp.data.decode("utf-8", errors="ignore")

    assert "上次执行时间记录异常，系统会在下次执行后重新记录。" in html, html
    assert "上次结果记录异常，详细内容请让维护人员查看日志。" in html, html

    resp = app_client.get("/system/backup")
    _assert_status(resp, "GET /system/backup")
    backup_html = resp.data.decode("utf-8", errors="ignore")

    assert "上次结果记录异常，详细内容请让维护人员查看日志。" in backup_html, backup_html
