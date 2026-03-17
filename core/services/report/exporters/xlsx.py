from __future__ import annotations

import io
from typing import Any, Dict, List

import openpyxl
from openpyxl.styles import Alignment, Font

from core.services.common.excel_templates import _sanitize_export_cell


def _auto_width(ws) -> None:
    widths: Dict[int, int] = {}
    for row in ws.iter_rows():
        for cell in row:
            text = "" if cell.value is None else str(cell.value)
            widths[cell.column] = max(widths.get(cell.column, 0), len(text))
    for col_idx, content_width in widths.items():
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = min(max(content_width + 2, 12), 36)


def _append_row(ws, values: List[Any]) -> None:
    ws.append([_sanitize_export_cell(v) for v in values])


def _format_sheet(ws) -> None:
    ws.freeze_panes = "A2"
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    _auto_width(ws)


def export_overdue_xlsx(items: List[Dict[str, Any]]) -> io.BytesIO:
    wb = openpyxl.Workbook()
    try:
        ws = wb.active
        ws.title = "overdue"
        _append_row(ws, ["类别", "批次号", "图号", "名称", "数量", "交期", "完工/截至时间", "超期(小时)", "超期(天)"])
        for it in items:
            _append_row(
                ws,
                [
                    it.get("bucket_label"),
                    it.get("batch_id"),
                    it.get("part_no"),
                    it.get("part_name"),
                    it.get("quantity"),
                    it.get("due_date"),
                    it.get("finish_time") or it.get("as_of_time"),
                    it.get("delay_hours"),
                    it.get("delay_days"),
                ],
            )
        _format_sheet(ws)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf
    finally:
        try:
            wb.close()
        except Exception:
            pass


def export_utilization_xlsx(machines: List[Dict[str, Any]], operators: List[Dict[str, Any]]) -> io.BytesIO:
    wb = openpyxl.Workbook()
    try:
        ws1 = wb.active
        ws1.title = "machines"
        _append_row(ws1, ["设备编号", "设备名称", "负荷(小时)", "任务数", "可用工时(小时)", "利用率"])
        for r in machines:
            _append_row(
                ws1,
                [
                    r.get("machine_id"),
                    r.get("machine_name"),
                    r.get("hours"),
                    r.get("task_count"),
                    r.get("capacity_hours"),
                    r.get("utilization"),
                ],
            )
        _format_sheet(ws1)

        ws2 = wb.create_sheet("operators")
        _append_row(ws2, ["工号", "姓名", "负荷(小时)", "任务数", "可用工时(小时)", "利用率"])
        for r in operators:
            _append_row(
                ws2,
                [
                    r.get("operator_id"),
                    r.get("operator_name"),
                    r.get("hours"),
                    r.get("task_count"),
                    r.get("capacity_hours"),
                    r.get("utilization"),
                ],
            )
        _format_sheet(ws2)

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf
    finally:
        try:
            wb.close()
        except Exception:
            pass


def export_downtime_impact_xlsx(machines: List[Dict[str, Any]]) -> io.BytesIO:
    wb = openpyxl.Workbook()
    try:
        ws = wb.active
        ws.title = "downtime"
        _append_row(ws, ["设备编号", "设备名称", "停机时长(小时)", "停机次数", "与排程重叠(小时)", "重叠次数"])
        for r in machines:
            _append_row(
                ws,
                [
                    r.get("machine_id"),
                    r.get("machine_name"),
                    r.get("downtime_hours"),
                    r.get("downtime_count"),
                    r.get("schedule_overlap_hours"),
                    r.get("schedule_overlap_count"),
                ],
            )
        _format_sheet(ws)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf
    finally:
        try:
            wb.close()
        except Exception:
            pass

