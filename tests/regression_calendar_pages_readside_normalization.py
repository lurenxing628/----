from __future__ import annotations

import importlib
import os
import re
import sys
import tempfile


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _assert_status(resp, name: str, expect: int = 200) -> None:
    if resp.status_code != expect:
        body = resp.data.decode("utf-8", errors="ignore") if getattr(resp, "data", None) else ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect}，body={body[:500]}")


def _assert_calendar_row(
    html: str,
    date_value: str,
    day_type_zh: str,
    shift_hours_re: str,
    allow_normal_zh: str,
    allow_urgent_zh: str,
) -> None:
    pattern = (
        rf"<td>{re.escape(date_value)}</td>"
        rf"\s*<td>{re.escape(day_type_zh)}</td>"
        rf".*?<td>{shift_hours_re}</td>"
        rf".*?<td>{re.escape(allow_normal_zh)}</td>"
        rf"\s*<td>{re.escape(allow_urgent_zh)}</td>"
    )
    if re.search(pattern, html, re.S) is None:
        raise RuntimeError(
            f"未找到归一化后的日历行：date={date_value}, day_type_zh={day_type_zh}, shift_hours_re={shift_hours_re}, "
            f"allow_normal_zh={allow_normal_zh}, allow_urgent_zh={allow_urgent_zh}"
        )


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    root = tempfile.mkdtemp(prefix="aps_reg_calendar_page_norm_")
    test_db = os.path.join(root, "aps_test.db")
    test_logs = os.path.join(root, "logs")
    test_backups = os.path.join(root, "backups")
    test_templates = os.path.join(root, "templates_excel")
    os.makedirs(test_logs, exist_ok=True)
    os.makedirs(test_backups, exist_ok=True)
    os.makedirs(test_templates, exist_ok=True)

    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = test_db
    os.environ["APS_LOG_DIR"] = test_logs
    os.environ["APS_BACKUP_DIR"] = test_backups
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = test_templates

    from core.infrastructure.database import ensure_schema, get_connection

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))

    conn = get_connection(test_db)
    try:
        conn.execute("INSERT INTO Operators (operator_id, name) VALUES (?, ?)", ("OP100", "测试员甲"))
        conn.execute(
            """
            INSERT INTO WorkCalendar (date, day_type, shift_hours, efficiency, allow_normal, allow_urgent, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("2026-02-01", "Weekend", 0, 1.0, "Yes", "NO", "global legacy"),
        )
        conn.execute(
            """
            INSERT INTO OperatorCalendar (operator_id, date, day_type, shift_hours, efficiency, allow_normal, allow_urgent, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("OP100", "2026-02-02", "Weekend", 0, 1.0, "是", "否", "personal legacy"),
        )
        conn.commit()
    finally:
        conn.close()

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    resp_scheduler = client.get("/scheduler/calendar")
    _assert_status(resp_scheduler, "GET /scheduler/calendar")
    html_scheduler = resp_scheduler.data.decode("utf-8", errors="ignore")
    _assert_calendar_row(html_scheduler, "2026-02-01", "假期", r"0(?:\.0+)?", "是", "否")

    resp_personnel = client.get("/personnel/OP100/calendar")
    _assert_status(resp_personnel, "GET /personnel/OP100/calendar")
    html_personnel = resp_personnel.data.decode("utf-8", errors="ignore")
    _assert_calendar_row(html_personnel, "2026-02-02", "假期", r"0(?:\.0+)?", "是", "否")

    print("OK")


if __name__ == "__main__":
    main()
