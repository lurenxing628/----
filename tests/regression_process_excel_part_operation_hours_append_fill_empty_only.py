import io
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


def _make_xlsx_bytes(headers, rows):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h) for h in headers])
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
    tmpdir = tempfile.mkdtemp(prefix="aps_regression_part_op_hours_append_")
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

    import importlib

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    # 1) 工种导入（internal + external）
    op_types_rows = [
        {"工种ID": "OT_IN", "工种名称": "数车", "归属": "internal"},
        {"工种ID": "OT_EX", "工种名称": "表面处理", "归属": "external"},
    ]
    buf = _make_xlsx_bytes(["工种ID", "工种名称", "归属"], op_types_rows)
    r = client.post(
        "/process/excel/op-types/preview",
        data={"mode": "overwrite", "file": (buf, "op_types.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status("op_types preview", r, 200)
    raw = _extract_raw_rows_json(r.data.decode("utf-8", errors="ignore"))
    r = client.post(
        "/process/excel/op-types/confirm",
        data={"mode": "overwrite", "filename": "op_types.xlsx", "raw_rows_json": raw},
        follow_redirects=True,
    )
    _assert_status("op_types confirm", r, 200)

    # 2) 路线导入（生成 internal:5/10 + external:20）
    routes_rows = [{"图号": "A1001", "名称": "测试件", "工艺路线字符串": "5数车10数车20表面处理"}]
    buf = _make_xlsx_bytes(["图号", "名称", "工艺路线字符串"], routes_rows)
    r = client.post(
        "/process/excel/routes/preview",
        data={"mode": "overwrite", "file": (buf, "routes.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status("routes preview", r, 200)
    raw = _extract_raw_rows_json(r.data.decode("utf-8", errors="ignore"))
    r = client.post(
        "/process/excel/routes/confirm",
        data={"mode": "overwrite", "filename": "routes.xlsx", "raw_rows_json": raw},
        follow_redirects=True,
    )
    _assert_status("routes confirm", r, 200)

    # 3) 初始化：seq=5 置为已维护工时，seq=10 保持 0（待 append 补齐）
    conn = get_connection(test_db)
    try:
        conn.execute(
            "UPDATE PartOperations SET setup_hours=?, unit_hours=? WHERE part_no=? AND seq=?",
            (1.0, 0.5, "A1001", 5),
        )
        conn.commit()
    finally:
        conn.close()

    # 4) 页面模式应隐藏 replace，仅保留 overwrite/append
    r = client.get("/process/excel/part-operation-hours")
    _assert_status("part_operation_hours page", r, 200)
    html_page = r.data.decode("utf-8", errors="ignore")
    if 'value="replace"' in html_page:
        raise RuntimeError("零件工序工时页面不应展示 replace 模式")
    if "追加（仅补齐空工时）" not in html_page:
        raise RuntimeError("零件工序工时页面未展示 append 补齐语义")

    # 5) append 预览（含 skip/update/error 混合）
    append_rows_mixed = [
        {"图号": "A1001", "工序": 5, "换型时间(h)": 2.0, "单件工时(h)": 1.0},   # 已维护 -> SKIP
        {"图号": "A1001", "工序": 10, "换型时间(h)": 0.8, "单件工时(h)": 0.4},  # 空工时 -> UPDATE
        {"图号": "A1001", "工序": 20, "换型时间(h)": 0.2, "单件工时(h)": 0.1},  # external -> ERROR
        {"图号": "A1001", "工序": 99, "换型时间(h)": 0.2, "单件工时(h)": 0.1},  # 不存在 -> ERROR
    ]
    buf = _make_xlsx_bytes(["图号", "工序", "换型时间(h)", "单件工时(h)"], append_rows_mixed)
    r = client.post(
        "/process/excel/part-operation-hours/preview",
        data={"mode": "append", "file": (buf, "part_op_hours_append_mixed.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status("part_operation_hours append preview mixed", r, 200)
    html_mixed = r.data.decode("utf-8", errors="ignore")
    if "已存在，按“追加”模式将跳过" not in html_mixed:
        raise RuntimeError("append 预览未标记已维护行为 SKIP")
    if "工时为空，按“追加”模式将补齐" not in html_mixed:
        raise RuntimeError("append 预览未把空工时行标记为补齐 UPDATE")
    if "仅支持内部工序导入工时" not in html_mixed:
        raise RuntimeError("append 预览未识别 external 工序错误")
    if "工序不存在" not in html_mixed:
        raise RuntimeError("append 预览未识别不存在工序错误")
    raw_mixed = _extract_raw_rows_json(html_mixed)
    r = client.post(
        "/process/excel/part-operation-hours/confirm",
        data={"mode": "append", "filename": "part_op_hours_append_mixed.xlsx", "raw_rows_json": raw_mixed},
        follow_redirects=True,
    )
    _assert_status("part_operation_hours append confirm mixed", r, 200)
    html_mixed_confirm = r.data.decode("utf-8", errors="ignore")
    if "导入被拒绝" not in html_mixed_confirm:
        raise RuntimeError("append confirm（含错误行）应拒绝导入")

    # 6) append 预览+确认（仅 skip/update，无 error）应成功写入空工时行
    append_rows_ok = [
        {"图号": "A1001", "工序": 5, "换型时间(h)": 9.9, "单件工时(h)": 9.9},   # 已维护 -> SKIP
        {"图号": "A1001", "工序": 10, "换型时间(h)": 0.8, "单件工时(h)": 0.4},  # 空工时 -> UPDATE
    ]
    buf = _make_xlsx_bytes(["图号", "工序", "换型时间(h)", "单件工时(h)"], append_rows_ok)
    r = client.post(
        "/process/excel/part-operation-hours/preview",
        data={"mode": "append", "file": (buf, "part_op_hours_append_ok.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status("part_operation_hours append preview ok", r, 200)
    raw_ok = _extract_raw_rows_json(r.data.decode("utf-8", errors="ignore"))
    r = client.post(
        "/process/excel/part-operation-hours/confirm",
        data={"mode": "append", "filename": "part_op_hours_append_ok.xlsx", "raw_rows_json": raw_ok},
        follow_redirects=True,
    )
    _assert_status("part_operation_hours append confirm ok", r, 200)

    # 7) 验证 DB：seq5 保持原值；seq10 被补齐；seq20 不变
    conn = get_connection(test_db)
    try:
        row5 = conn.execute(
            "SELECT setup_hours, unit_hours FROM PartOperations WHERE part_no=? AND seq=?",
            ("A1001", 5),
        ).fetchone()
        row10 = conn.execute(
            "SELECT setup_hours, unit_hours FROM PartOperations WHERE part_no=? AND seq=?",
            ("A1001", 10),
        ).fetchone()
        row20 = conn.execute(
            "SELECT source, setup_hours, unit_hours FROM PartOperations WHERE part_no=? AND seq=?",
            ("A1001", 20),
        ).fetchone()

        if not row5 or not row10 or not row20:
            raise RuntimeError("导入后未找到预期 PartOperations 记录")

        if abs(float(row5["setup_hours"] or 0.0) - 1.0) > 1e-6 or abs(float(row5["unit_hours"] or 0.0) - 0.5) > 1e-6:
            raise RuntimeError(
                f"append 不应覆盖已维护工时（seq=5）：setup={row5['setup_hours']!r}, unit={row5['unit_hours']!r}"
            )
        if abs(float(row10["setup_hours"] or 0.0) - 0.8) > 1e-6 or abs(float(row10["unit_hours"] or 0.0) - 0.4) > 1e-6:
            raise RuntimeError(
                f"append 应补齐空工时（seq=10）：setup={row10['setup_hours']!r}, unit={row10['unit_hours']!r}"
            )
        if str(row20["source"] or "").strip().lower() != "external":
            raise RuntimeError("seq=20 应为 external")
        if abs(float(row20["setup_hours"] or 0.0)) > 1e-6 or abs(float(row20["unit_hours"] or 0.0)) > 1e-6:
            raise RuntimeError("append 不应更新 external 工序工时")
    finally:
        conn.close()

    print("OK")


if __name__ == "__main__":
    main()
