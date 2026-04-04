import importlib
import io
import os
import re
import sys
import tempfile
from html import unescape
from unittest.mock import patch


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _make_xlsx_bytes(headers, rows):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    if ws is None:
        raise RuntimeError("openpyxl Workbook.active 不应为空")
    ws.title = "日历导入"
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h) for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    buf.seek(0)
    return buf


def _extract_raw_rows_json(html: str) -> str:
    match = re.search(r'<textarea name="raw_rows_json"[^>]*>(.*?)</textarea>', html, re.S)
    if not match:
        raise RuntimeError("未能从页面提取 raw_rows_json")
    return unescape(match.group(1)).strip()


def _extract_hidden_input(html: str, name: str) -> str:
    for match in re.finditer(r"<input[^>]+>", html, re.I):
        tag = match.group(0)
        if re.search(rf'name="{re.escape(name)}"', tag):
            value_match = re.search(r'value="([^"]*)"', tag)
            return unescape(value_match.group(1)).strip() if value_match else ""
    return ""


def _assert_status(name: str, resp, expect_code: int = 200) -> None:
    if resp.status_code != expect_code:
        body = ""
        try:
            body = resp.data.decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect_code}；body={body[:500]}")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_calendar_executor_")
    test_db = os.path.join(tmpdir, "aps_test.db")
    test_logs = os.path.join(tmpdir, "logs")
    test_backups = os.path.join(tmpdir, "backups")
    test_templates = os.path.join(tmpdir, "templates_excel")
    os.makedirs(test_logs, exist_ok=True)
    os.makedirs(test_backups, exist_ok=True)
    os.makedirs(test_templates, exist_ok=True)

    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = test_db
    os.environ["APS_LOG_DIR"] = test_logs
    os.environ["APS_BACKUP_DIR"] = test_backups
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = test_templates

    from core.infrastructure.database import ensure_schema, get_connection

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"), backup_dir=None)

    from core.services.scheduler.config_service import ConfigService

    conn = get_connection(test_db)
    try:
        ConfigService(conn).set_holiday_default_efficiency(0.6)
    finally:
        conn.close()

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    preview_resp = client.post(
        "/scheduler/excel/calendar/preview",
        data={
            "mode": "overwrite",
            "file": (
                _make_xlsx_bytes(
                    ["日期", "类型", "可用工时", "效率", "允许普通件", "允许急件", "说明"],
                    [
                        {
                            "日期": "2026-04-01",
                            "类型": "workday",
                            "可用工时": 8,
                            "效率": 1.0,
                            "允许普通件": "yes",
                            "允许急件": "yes",
                            "说明": "executor-route",
                        }
                    ],
                ),
                "calendar.xlsx",
            ),
        },
        content_type="multipart/form-data",
    )
    _assert_status("POST /scheduler/excel/calendar/preview", preview_resp, 200)
    preview_html = preview_resp.data.decode("utf-8", errors="ignore")
    raw_rows_json = _extract_raw_rows_json(preview_html)
    preview_baseline = _extract_hidden_input(preview_html, "preview_baseline")
    if not preview_baseline:
        raise RuntimeError("工作日历预览页缺少 preview_baseline")

    route_mod = importlib.import_module("web.routes.scheduler_excel_calendar")
    from core.services.common.excel_import_executor import ImportExecutionStats

    captured = {}

    def _fake_execute(conn, **kwargs):
        captured["conn"] = conn
        captured["kwargs"] = kwargs
        return ImportExecutionStats(new_count=0, update_count=0, skip_count=1, error_count=0, errors_sample=[])

    with patch.object(route_mod, "execute_preview_rows_transactional", side_effect=_fake_execute) as executor_mock:
        confirm_resp = client.post(
            "/scheduler/excel/calendar/confirm",
            data={
                "mode": "overwrite",
                "filename": "calendar.xlsx",
                "raw_rows_json": raw_rows_json,
                "preview_baseline": preview_baseline,
            },
            follow_redirects=True,
        )
        _assert_status("POST /scheduler/excel/calendar/confirm", confirm_resp, 200)
        if executor_mock.call_count != 1:
            raise RuntimeError(f"工作日历确认导入未通过通用执行器，实际调用次数：{executor_mock.call_count}")

    kwargs = captured.get("kwargs") or {}
    preview_rows = list(kwargs.get("preview_rows") or [])
    if len(preview_rows) != 1:
        raise RuntimeError(f"工作日历确认导入传入执行器的预览行数量异常：{len(preview_rows)}")

    pr = preview_rows[0]
    if getattr(kwargs.get("mode"), "value", None) != "overwrite":
        raise RuntimeError(f"工作日历确认导入传入执行器的 mode 异常：{kwargs.get('mode')!r}")
    if getattr(pr, "source_row_num", None) != 2 or getattr(pr, "row_num", None) != 2:
        raise RuntimeError(
            f"工作日历确认导入传入执行器的源行号异常：row_num={getattr(pr, 'row_num', None)!r} source_row_num={getattr(pr, 'source_row_num', None)!r}"
        )
    if "__source_row_num" in (getattr(pr, "data", None) or {}) or "__source_sheet_name" in (getattr(pr, "data", None) or {}):
        raise RuntimeError(f"执行器收到的预览行不应再包含保留元数据键：{pr.data!r}")

    confirm_html = confirm_resp.data.decode("utf-8", errors="ignore")
    expected_message = "导入完成：新增 0，更新 0，跳过 1，错误 0。"
    if expected_message not in confirm_html:
        raise RuntimeError(f"工作日历确认导入未使用执行器统计结果提示页面：未找到 {expected_message!r}")

    conn = get_connection(test_db)
    try:
        row = conn.execute("SELECT COUNT(1) AS cnt FROM WorkCalendar").fetchone()
        if row is None or int(row["cnt"] or 0) != 0:
            raise RuntimeError(f"打桩执行器未写库时，工作日历不应落库：{dict(row) if row else None!r}")
    finally:
        conn.close()

    print("OK")


if __name__ == "__main__":
    main()
