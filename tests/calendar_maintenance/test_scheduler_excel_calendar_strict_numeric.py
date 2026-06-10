"""回归测试：工作日历 Excel preview 路由严格拒绝 bool / NaN / Inf 数值。

验证 scheduler_excel_calendar.py 的 validate_row 闭包通过 parse_finite_float
正确拒绝布尔值（True/False）和非有限浮点数（NaN/Inf）作为"可用工时"/"效率"。
"""

import io
import re


def _make_xlsx_bytes(headers, rows):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "日历导入"
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h) for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    buf.seek(0)
    return buf


def test_scheduler_excel_calendar_strict_numeric(app_client, db_path) -> None:
    from core.infrastructure.database import get_connection
    from core.services.scheduler.config.config_service import ConfigService

    conn = get_connection(db_path)
    try:
        ConfigService(conn).set_holiday_default_efficiency(0.6)
    finally:
        conn.close()

    headers = ["日期", "类型", "可用工时", "效率", "允许普通件", "允许急件", "说明"]
    base = {"类型": "workday", "允许普通件": "yes", "允许急件": "yes", "说明": ""}

    rows = [
        {**base, "日期": "2026-05-01", "可用工时": True, "效率": 1.0},        # bool -> 拒绝
        {**base, "日期": "2026-05-02", "可用工时": 8, "效率": "NaN"},           # 字符串 NaN -> float("nan") -> isfinite 拒绝
        {**base, "日期": "2026-05-03", "可用工时": "Infinity", "效率": 1.0},    # 字符串 Inf -> float("inf") -> isfinite 拒绝
        {**base, "日期": "2026-05-04", "可用工时": 8, "效率": 1.0},             # 正常行
    ]

    preview_resp = app_client.post(
        "/scheduler/excel/calendar/preview",
        data={
            "mode": "overwrite",
            "file": (_make_xlsx_bytes(headers, rows), "calendar.xlsx"),
        },
        content_type="multipart/form-data",
    )
    assert preview_resp.status_code == 200, (
        f"preview 返回 {preview_resp.status_code}，期望 200"
    )

    html = preview_resp.data.decode("utf-8", errors="ignore")

    # 验证错误信息包含 "必须是数字" 或 "必须是有限数字"
    assert "必须是数字" in html, "布尔值应触发 '必须是数字' 错误"
    assert "必须是有限数字" in html, "NaN/Inf 应触发 '必须是有限数字' 错误"
