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
    assert ws is not None

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
    tmpdir = tempfile.mkdtemp(prefix="aps_regression_part_op_hours_import_")
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

    # 1) 工种导入（内部 + 外部）
    op_types_rows = [
        {"工种ID": "OT_IN", "工种名称": "数车", "归属": "internal"},
        {"工种ID": "OT_EX", "工种名称": "表面处理", "归属": "external"},
    ]
    buf = _make_xlsx_bytes(["工种ID", "工种名称", "归属"], op_types_rows)
    r = client.post("/process/excel/op-types/preview", data={"mode": "overwrite", "file": (buf, "op_types.xlsx")}, content_type="multipart/form-data")
    _assert_status("op_types preview", r, 200)
    preview_html = r.data.decode("utf-8", errors="ignore")
    raw = _extract_raw_rows_json(preview_html)
    preview_baseline = _extract_hidden_input(preview_html, "preview_baseline")
    if not preview_baseline:
        raise RuntimeError("op_types preview 缺少 preview_baseline")
    r = client.post(
        "/process/excel/op-types/confirm",
        data={"mode": "overwrite", "filename": "op_types.xlsx", "raw_rows_json": raw, "preview_baseline": preview_baseline},
        follow_redirects=True,
    )
    _assert_status("op_types confirm", r, 200)

    # 2) 路线导入（生成 PartOperations：5 internal / 10 external）
    routes_rows = [{"图号": "A1001", "名称": "测试件", "工艺路线字符串": "5数车10表面处理"}]
    buf = _make_xlsx_bytes(["图号", "名称", "工艺路线字符串"], routes_rows)
    r = client.post("/process/excel/routes/preview", data={"mode": "overwrite", "file": (buf, "routes.xlsx")}, content_type="multipart/form-data")
    _assert_status("routes preview", r, 200)
    preview_html = r.data.decode("utf-8", errors="ignore")
    raw = _extract_raw_rows_json(preview_html)
    preview_baseline = _extract_hidden_input(preview_html, "preview_baseline")
    if not preview_baseline:
        raise RuntimeError("routes preview 缺少 preview_baseline")
    r = client.post(
        "/process/excel/routes/confirm",
        data={"mode": "overwrite", "filename": "routes.xlsx", "raw_rows_json": raw, "preview_baseline": preview_baseline},
        follow_redirects=True,
    )
    _assert_status("routes confirm", r, 200)

    # 3) 先验证：包含 external 行时预览应给 ERROR
    hours_rows_with_external = [
        {"图号": "A1001", "工序": 5, "换型时间(h)": 1.25, "单件工时(h)": 0.5},
        {"图号": "A1001", "工序": 10, "换型时间(h)": 0.2, "单件工时(h)": 0.1},
    ]
    buf = _make_xlsx_bytes(["图号", "工序", "换型时间(h)", "单件工时(h)"], hours_rows_with_external)
    r = client.post(
        "/process/excel/part-operation-hours/preview",
        data={"mode": "overwrite", "file": (buf, "part_op_hours_bad.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status("part_operation_hours preview bad", r, 200)
    html_bad = r.data.decode("utf-8", errors="ignore")
    if "仅支持内部工序导入工时" not in html_bad:
        raise RuntimeError("预览未识别外部工序行（期望提示：仅支持内部工序导入工时）")

    # 3.1) 非有限数字（NaN）应被拒绝
    hours_rows_nan = [{"图号": "A1001", "工序": 5, "换型时间(h)": "NaN", "单件工时(h)": 0.5}]
    buf = _make_xlsx_bytes(["图号", "工序", "换型时间(h)", "单件工时(h)"], hours_rows_nan)
    r = client.post(
        "/process/excel/part-operation-hours/preview",
        data={"mode": "overwrite", "file": (buf, "part_op_hours_nan.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status("part_operation_hours preview nan", r, 200)
    html_nan = r.data.decode("utf-8", errors="ignore")
    if "必须是有限数字" not in html_nan:
        raise RuntimeError("预览未识别 NaN（期望提示：必须是有限数字）")
    raw_nan = _extract_raw_rows_json(html_nan)
    preview_baseline_nan = _extract_hidden_input(html_nan, "preview_baseline")
    if not preview_baseline_nan:
        raise RuntimeError("part_operation_hours preview nan 缺少 preview_baseline")
    r = client.post(
        "/process/excel/part-operation-hours/confirm",
        data={
            "mode": "overwrite",
            "filename": "part_op_hours_nan.xlsx",
            "raw_rows_json": raw_nan,
            "preview_baseline": preview_baseline_nan,
        },
        follow_redirects=True,
    )
    _assert_status("part_operation_hours confirm nan", r, 200)
    html_nan_confirm = r.data.decode("utf-8", errors="ignore")
    if "导入被拒绝" not in html_nan_confirm:
        raise RuntimeError("confirm 阶段未拒绝 NaN 数据")

    # 3.2) 非有限数字（Inf）应被拒绝
    hours_rows_inf = [{"图号": "A1001", "工序": 5, "换型时间(h)": 0.5, "单件工时(h)": "Inf"}]
    buf = _make_xlsx_bytes(["图号", "工序", "换型时间(h)", "单件工时(h)"], hours_rows_inf)
    r = client.post(
        "/process/excel/part-operation-hours/preview",
        data={"mode": "overwrite", "file": (buf, "part_op_hours_inf.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status("part_operation_hours preview inf", r, 200)
    html_inf = r.data.decode("utf-8", errors="ignore")
    if "必须是有限数字" not in html_inf:
        raise RuntimeError("预览未识别 Inf（期望提示：必须是有限数字）")
    raw_inf = _extract_raw_rows_json(html_inf)
    preview_baseline_inf = _extract_hidden_input(html_inf, "preview_baseline")
    if not preview_baseline_inf:
        raise RuntimeError("part_operation_hours preview inf 缺少 preview_baseline")
    r = client.post(
        "/process/excel/part-operation-hours/confirm",
        data={
            "mode": "overwrite",
            "filename": "part_op_hours_inf.xlsx",
            "raw_rows_json": raw_inf,
            "preview_baseline": preview_baseline_inf,
        },
        follow_redirects=True,
    )
    _assert_status("part_operation_hours confirm inf", r, 200)
    html_inf_confirm = r.data.decode("utf-8", errors="ignore")
    if "导入被拒绝" not in html_inf_confirm:
        raise RuntimeError("confirm 阶段未拒绝 Inf 数据")

    # 非有限值导入后，数据库不应被更新
    conn = get_connection(test_db)
    try:
        row_before = conn.execute(
            "SELECT setup_hours, unit_hours FROM PartOperations WHERE part_no=? AND seq=?",
            ("A1001", 5),
        ).fetchone()
        if not row_before:
            raise RuntimeError("未找到 A1001-5 工序记录")
        if abs(float(row_before["setup_hours"] or 0.0)) > 1e-6 or abs(float(row_before["unit_hours"] or 0.0)) > 1e-6:
            raise RuntimeError("NaN/Inf 预览-确认后不应修改工时")
    finally:
        conn.close()

    # 4) 仅内部行：预览 + 确认应成功，并更新 PartOperations 工时
    hours_rows_ok = [{"图号": "A1001", "工序": 5, "换型时间(h)": 1.25, "单件工时(h)": 0.5}]
    buf = _make_xlsx_bytes(["图号", "工序", "换型时间(h)", "单件工时(h)"], hours_rows_ok)
    r = client.post(
        "/process/excel/part-operation-hours/preview",
        data={"mode": "overwrite", "file": (buf, "part_op_hours_ok.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status("part_operation_hours preview ok", r, 200)
    preview_html = r.data.decode("utf-8", errors="ignore")
    raw = _extract_raw_rows_json(preview_html)
    preview_baseline = _extract_hidden_input(preview_html, "preview_baseline")
    if not preview_baseline:
        raise RuntimeError("part_operation_hours preview ok 缺少 preview_baseline")
    r = client.post(
        "/process/excel/part-operation-hours/confirm",
        data={
            "mode": "overwrite",
            "filename": "part_op_hours_ok.xlsx",
            "raw_rows_json": raw,
            "preview_baseline": preview_baseline,
        },
        follow_redirects=True,
    )
    _assert_status("part_operation_hours confirm", r, 200)

    conn = get_connection(test_db)
    try:
        row_in = conn.execute(
            "SELECT source, setup_hours, unit_hours FROM PartOperations WHERE part_no=? AND seq=?",
            ("A1001", 5),
        ).fetchone()
        row_ex = conn.execute(
            "SELECT source, setup_hours, unit_hours FROM PartOperations WHERE part_no=? AND seq=?",
            ("A1001", 10),
        ).fetchone()
        if not row_in or not row_ex:
            raise RuntimeError("导入后未找到预期工序记录")
        if (row_in["source"] or "").strip().lower() != "internal":
            raise RuntimeError("seq=5 应为 internal")
        if abs(float(row_in["setup_hours"] or 0.0) - 1.25) > 1e-6 or abs(float(row_in["unit_hours"] or 0.0) - 0.5) > 1e-6:
            raise RuntimeError(
                f"内部工序工时更新失败：setup={row_in['setup_hours']!r} unit={row_in['unit_hours']!r}"
            )
        if (row_ex["source"] or "").strip().lower() != "external":
            raise RuntimeError("seq=10 应为 external")
        if abs(float(row_ex["setup_hours"] or 0.0)) > 1e-6 or abs(float(row_ex["unit_hours"] or 0.0)) > 1e-6:
            raise RuntimeError(
                f"外部工序不应被导入工时更新：setup={row_ex['setup_hours']!r} unit={row_ex['unit_hours']!r}"
            )
    finally:
        conn.close()

    print("OK")


if __name__ == "__main__":
    main()

