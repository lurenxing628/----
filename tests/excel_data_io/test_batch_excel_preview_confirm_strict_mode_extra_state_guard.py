"""回归测试：批次 Excel 预览(/scheduler/excel/batches/preview)与确认(/confirm)的 strict_mode 漂移护栏——预览页须保留 strict_mode/auto_generate_ops/preview_baseline 隐藏字段，确认时 strict_mode 由 yes 改成 no 应被拦截，提示「请重新上传 Excel 并检查」且不写入 Batches。"""

import io

from tests._support.legacy_http import assert_no_confirmation, assert_retired_response, confirmation_inputs


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


def _assert_status(name: str, resp, expect_code: int = 200) -> None:
    if resp.status_code != expect_code:
        body = ""
        try:
            body = resp.data.decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect_code}；body={body[:500]}")


def test_batch_excel_preview_confirm_strict_mode_extra_state_guard(app_client, db_path) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(db_path)
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

    client = app_client

    page_resp = client.get("/scheduler/excel/batches")
    assert_retired_response(page_resp)
    previews = {}
    for requested, expected in ((None, "no"), ("yes", "yes")):
        data = {
            "mode": "overwrite", "auto_generate_ops": "1",
            "file": (_make_xlsx_bytes(
                ["批次号", "图号", "数量", "交期", "优先级", "齐套", "齐套日期", "备注"],
                [{"批次号": "B_STRICT_GUARD", "图号": "P_BATCH", "数量": 2, "交期": "2026-04-10",
                  "优先级": "normal", "齐套": "yes", "齐套日期": None, "备注": "strict-mode-preview"}]), "batches.xlsx"),
        }
        if requested is not None:
            data["strict_mode"] = requested
        preview_resp = client.post("/scheduler/excel/batches/preview", data=data, content_type="multipart/form-data")
        _assert_status("POST /scheduler/excel/batches/preview", preview_resp, 200)
        fields = confirmation_inputs(preview_resp.get_data(as_text=True), "/scheduler/excel/batches/confirm")
        assert fields["strict_mode"] == expected
        previews[expected] = fields
    fields = previews["yes"]
    if fields["strict_mode"] != "yes":
        raise RuntimeError("批次 Excel 预览页未保留 strict_mode hidden field")
    if fields["auto_generate_ops"] != "1":
        raise RuntimeError("批次 Excel 预览页未保留 auto_generate_ops hidden field")

    raw_rows_json = fields["raw_rows_json"]
    preview_baseline = fields["preview_baseline"]
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
    assert_no_confirmation(confirm_html)
    if "请重新上传 Excel 并检查" not in confirm_html:
        raise RuntimeError("strict_mode 漂移后确认导入未提示“请重新上传 Excel 并检查”")

    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT COUNT(1) AS cnt FROM Batches WHERE batch_id=?", ("B_STRICT_GUARD",)).fetchone()
        if row is None or int(row["cnt"] or 0) != 0:
            raise RuntimeError(f"strict_mode 漂移被拦截后不应写入批次：{dict(row) if row else None!r}")
    finally:
        conn.close()
