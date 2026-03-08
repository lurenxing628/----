from __future__ import annotations

import importlib
import io
import os
import sys
import tempfile
from typing import Any, Dict, List, Optional


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


def _sheet_rows(resp_bytes: bytes) -> List[Dict[str, Any]]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(resp_bytes))
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    headers = [str(x) if x is not None else "" for x in rows[0]]
    out: List[Dict[str, Any]] = []
    for row in rows[1:]:
        item: Dict[str, Any] = {}
        for i, key in enumerate(headers):
            value = row[i]
            if hasattr(value, "isoformat"):
                try:
                    value = value.isoformat()
                except Exception:
                    pass
            item[key] = value
        out.append(item)
    return out


def _find_row(rows: List[Dict[str, Any]], **conditions: Any) -> Optional[Dict[str, Any]]:
    for row in rows:
        if all(row.get(k) == v for k, v in conditions.items()):
            return row
    return None


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    root = tempfile.mkdtemp(prefix="aps_reg_calendar_export_norm_")
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
            ("2026-02-01", "Weekend", 0, 1.0, "是", "NO", "global legacy"),
        )
        conn.execute(
            """
            INSERT INTO OperatorCalendar (operator_id, date, day_type, shift_hours, efficiency, allow_normal, allow_urgent, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("OP100", "2026-02-02", "Weekend", 0, 1.0, "YES", "否", "personal legacy"),
        )
        conn.commit()
    finally:
        conn.close()

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    resp_global = client.get("/scheduler/excel/calendar/export")
    _assert_status(resp_global, "GET /scheduler/excel/calendar/export")
    global_rows = _sheet_rows(resp_global.data)
    global_row = _find_row(global_rows, 日期="2026-02-01")
    if global_row is None:
        raise RuntimeError(f"未找到全局日历导出行：{global_rows!r}")
    assert global_row["类型"] == "holiday", f"预期全局导出 类型=holiday，实际 {global_row['类型']!r}"
    assert global_row["允许普通件"] == "yes", f"预期全局导出 允许普通件=yes，实际 {global_row['允许普通件']!r}"
    assert global_row["允许急件"] == "no", f"预期全局导出 允许急件=no，实际 {global_row['允许急件']!r}"

    resp_operator = client.get("/personnel/excel/operator_calendar/export")
    _assert_status(resp_operator, "GET /personnel/excel/operator_calendar/export")
    operator_rows = _sheet_rows(resp_operator.data)
    operator_row = _find_row(operator_rows, 工号="OP100", 日期="2026-02-02")
    if operator_row is None:
        raise RuntimeError(f"未找到个人日历导出行：{operator_rows!r}")
    assert operator_row["类型"] == "holiday", f"预期个人导出 类型=holiday，实际 {operator_row['类型']!r}"
    assert operator_row["允许普通件"] == "yes", f"预期个人导出 允许普通件=yes，实际 {operator_row['允许普通件']!r}"
    assert operator_row["允许急件"] == "no", f"预期个人导出 允许急件=no，实际 {operator_row['允许急件']!r}"

    print("OK")


if __name__ == "__main__":
    main()
