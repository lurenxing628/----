import io
import os
import re
import sys
import tempfile
from html import unescape


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
    ws.title = "Sheet1"
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
    raise RuntimeError(f"未能从页面提取隐藏字段：{name}")


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

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_batch_strict_mode_guard_")
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

    conn = get_connection(test_db)
    try:
        conn.execute(
            "INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)",
            ("OT_EXT", "表处理", "external"),
        )
        conn.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark) VALUES (?, ?, ?, ?, ?)",
            ("P_BATCH", "批次件", "10表处理", "no", None),
        )
        conn.commit()
    finally:
        conn.close()

    import importlib

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    page_resp = client.get("/scheduler/excel/batches")
    _assert_status("GET /scheduler/excel/batches", page_resp, 200)
    page_html = page_resp.data.decode("utf-8", errors="ignore")
    if 'name="strict_mode"' not in page_html:
        raise RuntimeError("批次 Excel 页面未渲染 strict_mode 控件")
    if _extract_hidden_input(page_html, "strict_mode") != "no":
        raise RuntimeError("批次 Excel 页面 strict_mode 默认 hidden 值异常")

    preview_resp = client.post(
        "/scheduler/excel/batches/preview",
        data={
            "mode": "overwrite",
            "auto_generate_ops": "1",
            "strict_mode": "yes",
            "file": (
                _make_xlsx_bytes(
                    ["批次号", "图号", "数量", "交期", "优先级", "齐套", "齐套日期", "备注"],
                    [
                        {
                            "批次号": "B_STRICT_GUARD",
                            "图号": "P_BATCH",
                            "数量": 2,
                            "交期": "2026-04-10",
                            "优先级": "normal",
                            "齐套": "yes",
                            "齐套日期": None,
                            "备注": "strict-mode-preview",
                        }
                    ],
                ),
                "batches.xlsx",
            ),
        },
        content_type="multipart/form-data",
    )
    _assert_status("POST /scheduler/excel/batches/preview", preview_resp, 200)
    preview_html = preview_resp.data.decode("utf-8", errors="ignore")

    if _extract_hidden_input(preview_html, "strict_mode") != "yes":
        raise RuntimeError("批次 Excel 预览页未保留 strict_mode hidden field")
    if _extract_hidden_input(preview_html, "auto_generate_ops") != "1":
        raise RuntimeError("批次 Excel 预览页未保留 auto_generate_ops hidden field")

    raw_rows_json = _extract_raw_rows_json(preview_html)
    preview_baseline = _extract_hidden_input(preview_html, "preview_baseline")
    if not preview_baseline:
        raise RuntimeError("批次 Excel 预览页缺少 preview_baseline")

    confirm_resp = client.post(
        "/scheduler/excel/batches/confirm",
        data={
            "mode": "overwrite",
            "filename": "batches.xlsx",
            "raw_rows_json": raw_rows_json,
            "preview_baseline": preview_baseline,
            "auto_generate_ops": "1",
            "strict_mode": "no",
        },
        follow_redirects=True,
    )
    _assert_status("POST /scheduler/excel/batches/confirm", confirm_resp, 200)
    confirm_html = confirm_resp.data.decode("utf-8", errors="ignore")
    if "需重新预览" not in confirm_html:
        raise RuntimeError("strict_mode 漂移后确认导入未提示“需重新预览”")

    conn = get_connection(test_db)
    try:
        row = conn.execute("SELECT COUNT(1) AS cnt FROM Batches WHERE batch_id=?", ("B_STRICT_GUARD",)).fetchone()
        if row is None or int(row["cnt"] or 0) != 0:
            raise RuntimeError(f"strict_mode 漂移被拦截后不应写入批次：{dict(row) if row else None!r}")
    finally:
        conn.close()

    print("OK")


if __name__ == "__main__":
    main()
