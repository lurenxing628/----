import io
import json
import os
import re
import sys
import tempfile
from typing import Any, cast


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
        raise RuntimeError("openpyxl 工作簿缺少活动工作表")
    cast(Any, ws).title = "Sheet1"
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h) for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _extract_raw_rows_json(html: str) -> str:
    m = re.search(r'<textarea name="raw_rows_json"[^>]*>(.*?)</textarea>', html, re.S)
    if not m:
        raise RuntimeError("未能从预览页面提取 raw_rows_json")
    raw = m.group(1)
    raw = raw.replace("&quot;", '"').replace("&#34;", '"').replace("&amp;", "&")
    return raw.strip()


def _extract_hidden_input(html: str, name: str) -> str:
    for m in re.finditer(r"<input[^>]+>", html, re.I):
        tag = m.group(0)
        if re.search(rf'name="{re.escape(name)}"', tag):
            vm = re.search(r'value="([^"]*)"', tag)
            value = vm.group(1) if vm else ""
            return value.replace("&quot;", '"').replace("&#34;", '"').replace("&amp;", "&").strip()
    return ""


def _assert_status(name: str, resp, expect_code: int = 200):
    if resp.status_code != expect_code:
        body = None
        try:
            body = resp.data.decode("utf-8", errors="ignore")
        except Exception:
            body = None
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect_code}；body={body[:500] if body else None}")


def main() -> None:
    repo_root = find_repo_root()
    tmpdir = tempfile.mkdtemp(prefix="aps_regression_part_op_hours_source_row_")
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

    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))

    conn = get_connection(test_db)
    try:
        conn.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark) VALUES (?, ?, ?, ?, ?)",
            ("A1001", "测试件", None, "no", None),
        )
        conn.execute(
            """
            INSERT INTO PartOperations
            (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("A1001", 5, None, "数车", "internal", None, None, None, 0.0, 0.0, "active"),
        )
        conn.commit()
    finally:
        conn.close()

    import importlib

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    headers = ["图号", "工序", "换型时间(h)", "单件工时(h)"]
    rows = [
        {},
        {"图号": "A1001", "工序": 5, "换型时间(h)": "NaN", "单件工时(h)": 0.5},
    ]
    buf = _make_xlsx_bytes(headers, rows)

    resp = client.post(
        "/process/excel/part-operation-hours/preview",
        data={"mode": "overwrite", "file": (buf, "part_op_hours_source_row.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status("part_operation_hours preview", resp, 200)
    preview_html = resp.data.decode("utf-8", errors="ignore")
    if "必须是有限数字" not in preview_html:
        raise RuntimeError("预览阶段未命中有限数字校验")

    raw_rows_json = _extract_raw_rows_json(preview_html)
    preview_baseline = _extract_hidden_input(preview_html, "preview_baseline")
    if not preview_baseline:
        raise RuntimeError("预览页面缺少 preview_baseline")

    preview_rows = json.loads(raw_rows_json)
    if len(preview_rows) != 1:
        raise RuntimeError(f"预览 raw_rows_json 行数异常：{preview_rows!r}")
    row = preview_rows[0]
    if row.get("__source_row_num") != 3:
        raise RuntimeError(f"零件工序工时 raw_rows_json 未保留原始行号 3：{row!r}")
    if row.get("__source_sheet_name") != "Sheet1":
        raise RuntimeError(f"零件工序工时 raw_rows_json 未保留工作表名称：{row!r}")
    if row.get("__row_id__") != "A1001|5":
        raise RuntimeError(f"零件工序工时 raw_rows_json 行标识异常：{row!r}")

    resp = client.post(
        "/process/excel/part-operation-hours/confirm",
        data={
            "mode": "overwrite",
            "filename": "part_op_hours_source_row.xlsx",
            "raw_rows_json": raw_rows_json,
            "preview_baseline": preview_baseline,
        },
        follow_redirects=True,
    )
    _assert_status("part_operation_hours confirm", resp, 200)
    confirm_html = resp.data.decode("utf-8", errors="ignore")
    if "导入被拒绝" not in confirm_html:
        raise RuntimeError("确认阶段未拒绝错误数据")
    if "错误示例：第3行：" not in confirm_html:
        raise RuntimeError("确认阶段错误示例未优先显示原始 Excel 行号 3")
    if "错误示例：第2行：" in confirm_html:
        raise RuntimeError("确认阶段错误示例错误回退到了压缩行号 2")

    print("OK")


if __name__ == "__main__":
    main()
