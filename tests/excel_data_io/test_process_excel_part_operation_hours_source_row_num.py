"""回归测试：/process/excel/part-operation-hours 预览与确认全链路——预览命中「必须是有限数字」校验、raw_rows_json 以 aps-preview-json-b64 编码且保留原始 Excel 行号(__source_row_num=3)/工作表名/行标识，确认阶段拒绝错误数据并把错误示例按原始行号「第3行」显示，不回退到压缩行号「第2行」。"""

import io
import json
from base64 import urlsafe_b64decode
from typing import Any, cast

from tests._support.legacy_http import assert_no_confirmation, capture_legacy_preview, rejected_preview_payload
from tests._support.sqlite_snapshot import table_rows


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


def _decode_preview_rows_payload(raw_rows_json: str) -> str:
    prefix = "aps-preview-json-b64:"
    if not raw_rows_json.startswith(prefix):
        raise RuntimeError("raw_rows_json 必须使用 aps-preview-json-b64 编码，不能退回明文 JSON")
    return urlsafe_b64decode(raw_rows_json[len(prefix) :].encode("ascii")).decode("utf-8")


def _assert_status(name: str, resp, expect_code: int = 200):
    if resp.status_code != expect_code:
        body = None
        try:
            body = resp.data.decode("utf-8", errors="ignore")
        except Exception:
            body = None
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect_code}；body={body[:500] if body else None}")


def test_process_excel_part_operation_hours_source_row_num(app_client, db_path) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(db_path)
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
        before = table_rows(conn, "PartOperations")
    finally:
        conn.close()

    client = app_client

    headers = ["图号", "工序", "换型时间(h)", "单件工时(h)"]
    rows = [
        {},
        {"图号": "A1001", "工序": 5, "换型时间(h)": "NaN", "单件工时(h)": 0.5},
    ]
    buf = _make_xlsx_bytes(headers, rows)

    with capture_legacy_preview(client.application) as captured:
        resp = client.post(
            "/process/excel/part-operation-hours/preview",
            data={"mode": "overwrite", "file": (buf, "part_op_hours_source_row.xlsx")},
            content_type="multipart/form-data",
        )
    _assert_status("part_operation_hours preview", resp, 200)
    preview_html = resp.data.decode("utf-8", errors="ignore")
    if "必须是有限数字" not in preview_html:
        raise RuntimeError("预览阶段未命中有限数字校验")

    blocked_fields = rejected_preview_payload(captured, preview_html)
    raw_rows_json = blocked_fields["raw_rows_json"]
    preview_baseline = blocked_fields["preview_baseline"]
    if not preview_baseline:
        raise RuntimeError("预览页面缺少 preview_baseline")

    preview_rows = json.loads(_decode_preview_rows_payload(raw_rows_json))
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
    assert_no_confirmation(confirm_html)
    if "导入被拒绝" not in confirm_html:
        raise RuntimeError("确认阶段未拒绝错误数据")
    if "错误示例：第3行：" not in confirm_html:
        raise RuntimeError("确认阶段错误示例未优先显示原始 Excel 行号 3")
    if "错误示例：第2行：" in confirm_html:
        raise RuntimeError("确认阶段错误示例错误回退到了压缩行号 2")
    conn = get_connection(db_path)
    try:
        assert table_rows(conn, "PartOperations") == before
    finally:
        conn.close()
