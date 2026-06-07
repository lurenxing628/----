"""回归测试：零件工序工时 Excel 导入的 append（只补空工时）模式——页面隐藏 replace 仅留 overwrite/append；预览把已维护工时行标记 SKIP、空工时行标记 UPDATE、external 工序与不存在工序标记 ERROR；含 error 行时 confirm 拒绝整批导入，仅 skip/update 时成功写入；确认 DB 中已维护行不被覆盖、空工时行被补齐、external 行保持不变。"""

import io
import re


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


def test_process_excel_part_operation_hours_append_fill_empty_only(app_client, db_path) -> None:
    from core.infrastructure.database import get_connection

    client = app_client

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

    # 2) 路线导入（生成 internal:5/10 + external:20）
    routes_rows = [{"图号": "A1001", "名称": "测试件", "工艺路线字符串": "5数车10数车20表面处理"}]
    buf = _make_xlsx_bytes(["图号", "名称", "工艺路线字符串"], routes_rows)
    r = client.post(
        "/process/excel/routes/preview",
        data={"mode": "overwrite", "file": (buf, "routes.xlsx")},
        content_type="multipart/form-data",
    )
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

    # 3) 初始化：seq=5 置为已维护工时，seq=10 保持 0（待 append 补齐）
    conn = get_connection(db_path)
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
    if "只补空工时" not in html_page:
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
    if "已存在，选择“只补空工时”时会跳过" not in html_mixed:
        raise RuntimeError("append 预览未标记已维护行为 SKIP")
    if "工时为空，选择“只补空工时”时会补齐" not in html_mixed:
        raise RuntimeError("append 预览未把空工时行标记为补齐 UPDATE")
    if "仅支持内部工序导入工时" not in html_mixed:
        raise RuntimeError("append 预览未识别 external 工序错误")
    if "工序不存在" not in html_mixed:
        raise RuntimeError("append 预览未识别不存在工序错误")
    raw_mixed = _extract_raw_rows_json(html_mixed)
    preview_baseline_mixed = _extract_hidden_input(html_mixed, "preview_baseline")
    if not preview_baseline_mixed:
        raise RuntimeError("part_operation_hours append preview mixed 缺少 preview_baseline")
    r = client.post(
        "/process/excel/part-operation-hours/confirm",
        data={
            "mode": "append",
            "filename": "part_op_hours_append_mixed.xlsx",
            "raw_rows_json": raw_mixed,
            "preview_baseline": preview_baseline_mixed,
        },
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
    preview_html = r.data.decode("utf-8", errors="ignore")
    raw_ok = _extract_raw_rows_json(preview_html)
    preview_baseline_ok = _extract_hidden_input(preview_html, "preview_baseline")
    if not preview_baseline_ok:
        raise RuntimeError("part_operation_hours append preview ok 缺少 preview_baseline")
    r = client.post(
        "/process/excel/part-operation-hours/confirm",
        data={
            "mode": "append",
            "filename": "part_op_hours_append_ok.xlsx",
            "raw_rows_json": raw_ok,
            "preview_baseline": preview_baseline_ok,
        },
        follow_redirects=True,
    )
    _assert_status("part_operation_hours append confirm ok", r, 200)

    # 7) 验证 DB：seq5 保持原值；seq10 被补齐；seq20 不变
    conn = get_connection(db_path)
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


def test_process_excel_part_operation_hours_import(app_client, db_path) -> None:
    """回归测试：零件工序工时 Excel 导入的 overwrite 模式——预览须识别 external 工序行报错（仅支持内部工序导入工时）、拒绝 NaN/Inf 非有限数字（必须是有限数字 / 导入被拒绝）且坏值经预览-确认后不修改 DB 工时；仅内部行（overwrite）confirm 成功后 internal 工序工时被更新（setup≈1.25/unit≈0.5）、external 工序工时仍保持 0。复用本模块共享 helper（_make_xlsx_bytes/_extract_raw_rows_json/_extract_hidden_input/_assert_status）。"""
    from core.infrastructure.database import get_connection

    client = app_client

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
    conn = get_connection(db_path)
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

    conn = get_connection(db_path)
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
