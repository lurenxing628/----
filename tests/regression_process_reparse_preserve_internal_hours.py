"""回归测试：经 /process/parts/<part>/reparse 重解析工艺路线时，已有内部工序(seq=5)的换型/单件工时(setup_hours/unit_hours)原样保留，新增工序(seq=15)工时回落默认 0，工序归属仍判为 internal。"""

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


def _preview_confirm_excel(client, *, preview_url: str, confirm_url: str, headers, rows, filename: str) -> None:
    buf = _make_xlsx_bytes(headers, rows)
    r = client.post(
        preview_url,
        data={"mode": "overwrite", "file": (buf, filename)},
        content_type="multipart/form-data",
    )
    _assert_status(f"{filename} preview", r, 200)
    preview_html = r.data.decode("utf-8", errors="ignore")
    raw = _extract_raw_rows_json(preview_html)
    preview_baseline = _extract_hidden_input(preview_html, "preview_baseline")
    if not preview_baseline:
        raise RuntimeError(f"{filename} 预览页面缺少 preview_baseline")
    r = client.post(
        confirm_url,
        data={
            "mode": "overwrite",
            "filename": filename,
            "raw_rows_json": raw,
            "preview_baseline": preview_baseline,
        },
        follow_redirects=True,
    )
    _assert_status(f"{filename} confirm", r, 200)


def test_process_reparse_preserve_internal_hours(app_client, db_path) -> None:
    from core.infrastructure.database import get_connection

    client = app_client

    # 1) 导入工种（内部+外部）
    _preview_confirm_excel(
        client,
        preview_url="/process/excel/op-types/preview",
        confirm_url="/process/excel/op-types/confirm",
        headers=["工种ID", "工种名称", "归属"],
        rows=[
            {"工种ID": "OT_IN", "工种名称": "数车", "归属": "internal"},
            {"工种ID": "OT_EX", "工种名称": "表面处理", "归属": "external"},
        ],
        filename="op_types.xlsx",
    )

    # 2) 导入初始路线（5 internal, 10 external）
    _preview_confirm_excel(
        client,
        preview_url="/process/excel/routes/preview",
        confirm_url="/process/excel/routes/confirm",
        headers=["图号", "名称", "工艺路线字符串"],
        rows=[{"图号": "A1001", "名称": "测试件", "工艺路线字符串": "5数车10表面处理"}],
        filename="routes_v1.xlsx",
    )

    # 3) 导入 internal 工时
    _preview_confirm_excel(
        client,
        preview_url="/process/excel/part-operation-hours/preview",
        confirm_url="/process/excel/part-operation-hours/confirm",
        headers=["图号", "工序", "换型时间(h)", "单件工时(h)"],
        rows=[{"图号": "A1001", "工序": 5, "换型时间(h)": 1.25, "单件工时(h)": 0.5}],
        filename="hours_v1.xlsx",
    )

    conn = get_connection(db_path)
    try:
        row_before = conn.execute(
            "SELECT source, setup_hours, unit_hours FROM PartOperations WHERE part_no=? AND seq=?",
            ("A1001", 5),
        ).fetchone()
        if not row_before:
            raise RuntimeError("重解析前未找到 A1001-5")
        if (row_before["source"] or "").strip().lower() != "internal":
            raise RuntimeError("重解析前 seq=5 应为 internal")
        if abs(float(row_before["setup_hours"] or 0.0) - 1.25) > 1e-6 or abs(float(row_before["unit_hours"] or 0.0) - 0.5) > 1e-6:
            raise RuntimeError("重解析前工时基线不正确")
    finally:
        conn.close()

    # 4) 触发重解析：新增一个 internal 工序 15
    r = client.post(
        "/process/parts/A1001/reparse",
        data={"route_raw": "5数车10表面处理15数车"},
        follow_redirects=True,
    )
    _assert_status("reparse", r, 200)

    conn = get_connection(db_path)
    try:
        row_5 = conn.execute(
            "SELECT source, setup_hours, unit_hours FROM PartOperations WHERE part_no=? AND seq=?",
            ("A1001", 5),
        ).fetchone()
        row_15 = conn.execute(
            "SELECT source, setup_hours, unit_hours FROM PartOperations WHERE part_no=? AND seq=?",
            ("A1001", 15),
        ).fetchone()

        if not row_5:
            raise RuntimeError("重解析后未找到 A1001-5")
        if not row_15:
            raise RuntimeError("重解析后未找到 A1001-15")

        if (row_5["source"] or "").strip().lower() != "internal":
            raise RuntimeError("重解析后 seq=5 应为 internal")
        if abs(float(row_5["setup_hours"] or 0.0) - 1.25) > 1e-6 or abs(float(row_5["unit_hours"] or 0.0) - 0.5) > 1e-6:
            raise RuntimeError(
                f"重解析后 seq=5 工时未保留：setup={row_5['setup_hours']!r} unit={row_5['unit_hours']!r}"
            )

        if (row_15["source"] or "").strip().lower() != "internal":
            raise RuntimeError("重解析后 seq=15 应为 internal")
        if abs(float(row_15["setup_hours"] or 0.0)) > 1e-6 or abs(float(row_15["unit_hours"] or 0.0)) > 1e-6:
            raise RuntimeError(
                f"重解析后新工序 seq=15 工时应为默认0：setup={row_15['setup_hours']!r} unit={row_15['unit_hours']!r}"
            )
    finally:
        conn.close()

