from __future__ import annotations

import io
import tempfile
from typing import Any, BinaryIO, Dict, List, Optional, cast

from core.services.common.excel_templates import sanitize_export_cell


def _auto_width(ws) -> None:
    from openpyxl.utils import get_column_letter

    widths: Dict[int, int] = {}
    for row in ws.iter_rows():
        for cell in row:
            text = "" if cell.value is None else str(cell.value)
            widths[cell.column] = max(widths.get(cell.column, 0), len(text))
    for col_idx, content_width in widths.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max(content_width + 2, 12), 36)


def _append_row(ws, values: List[Any]) -> None:
    ws.append([sanitize_export_cell(v) for v in values])


def _append_write_only_row(ws, values: List[Any], *, is_header: bool = False) -> None:
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Alignment, Font

    row_cells: List[Any] = []
    for value in values:
        cell = WriteOnlyCell(ws, value=sanitize_export_cell(value))
        if is_header:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center", vertical="center")
        else:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        row_cells.append(cell)
    ws.append(row_cells)


def _format_sheet(ws) -> None:
    from openpyxl.styles import Alignment, Font

    ws.freeze_panes = "A2"
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    _auto_width(ws)


def _make_output_buffer(*, write_only: bool) -> BinaryIO:
    if write_only:
        return cast(BinaryIO, tempfile.SpooledTemporaryFile(max_size=4 * 1024 * 1024, mode="w+b"))
    return io.BytesIO()


def _utilization_percent(value: Optional[float]) -> Optional[float]:
    return round(value * 100.0, 2) if value is not None else None


_OVERDUE_HEADERS = ["类别", "批次号", "图号", "名称", "数量", "交期", "完工/截至时间", "超期(天)", "超期(小时)"]
_DIAGNOSIS_HEADERS = ["本次诊断编号", "生成依据摘要", "核对信息", "证据来源", "证据缺口", "生成时间", "筛选条件"]
_EXECUTION_REVIEW_HEADERS = [
    "批次",
    "工序",
    "计划开始",
    "实际开始",
    "开工偏差",
    "计划结束",
    "实际结束",
    "完工偏差",
    "暂停时长",
    "异常原因",
    "严重程度",
    "预计影响时间",
    "影响设备",
    "影响人员",
    "处理状态",
    "是否建议重新排程",
    "计划资源",
    "实际资源",
    "现场反馈状态",
]


# 摘要区里必须按原文落格、不能被 Excel 当公式的编号行标签；workbench 导出器从这里取，保证单一来源。
SUMMARY_IDENTITY_LABELS = ("计划编号", "数据版本编号")


def _append_summary_row(ws, values: List[Any], *, write_only: bool) -> None:
    if len(values) == 2 and values[0] in SUMMARY_IDENTITY_LABELS:
        from openpyxl.cell import WriteOnlyCell
        from openpyxl.styles import Alignment

        cells = [WriteOnlyCell(ws, value=sanitize_export_cell(values[0])),
                 WriteOnlyCell(ws, value=values[1])]
        cells[1].data_type = "s"
        for cell in cells:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        ws.append(cells)
    elif write_only:
        _append_write_only_row(ws, values)
    else:
        _append_row(ws, values)


def _append_summary_sheet(wb, summary_rows: Optional[List[List[Any]]], *, write_only: bool) -> None:
    from openpyxl.styles import Alignment, Font

    rows = summary_rows
    if not rows:
        return
    if write_only:
        ws = wb.create_sheet("查询摘要")
        _append_write_only_row(ws, ["项目", "内容"], is_header=True)
        for row in rows:
            _append_summary_row(ws, row, write_only=True)
        return

    ws = wb.worksheets[0]
    ws.title = "查询摘要"
    _append_row(ws, ["项目", "内容"])
    for row in rows:
        _append_summary_row(ws, row, write_only=False)
    ws.freeze_panes = "A2"
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 42
    for row in ws.iter_rows():
        row[0].font = Font(bold=True)
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)


def export_overdue_xlsx(
    items: List[Dict[str, Any]],
    *,
    summary_rows: Optional[List[List[Any]]] = None,
    write_only: bool = False,
) -> BinaryIO:
    import openpyxl

    wb = openpyxl.Workbook(write_only=write_only)
    try:
        _append_summary_sheet(wb, summary_rows, write_only=write_only)
        ws = wb.create_sheet("超期清单") if (write_only or summary_rows) else wb.worksheets[0]
        if write_only:
            _append_write_only_row(ws, _OVERDUE_HEADERS, is_header=True)
        else:
            ws.title = "超期清单"
            _append_row(ws, _OVERDUE_HEADERS)
        append = _append_write_only_row if write_only else _append_row
        for item in items:
            append(ws, [item.get("bucket_label"), item.get("batch_id"), item.get("part_no"),
                        item.get("part_name"), item.get("quantity"), item.get("due_date"),
                        item.get("finish_time") or item.get("as_of_time"),
                        item.get("delay_days"), item.get("delay_hours")])
        if not write_only:
            _format_sheet(ws)
        _append_diagnosis_sheet(wb, write_only=write_only)

        buf = _make_output_buffer(write_only=write_only)
        wb.save(buf)
        buf.seek(0)
        return buf
    finally:
        wb.close()


def _append_diagnosis_sheet(wb, *, write_only: bool) -> None:
    ws = wb.create_sheet("诊断依据")
    if write_only:
        _append_write_only_row(ws, _DIAGNOSIS_HEADERS, is_header=True)
        return

    _append_row(ws, _DIAGNOSIS_HEADERS)
    _format_sheet(ws)


def export_utilization_xlsx(
    machines: List[Dict[str, Any]],
    operators: List[Dict[str, Any]],
    *,
    summary_rows: Optional[List[List[Any]]] = None,
    write_only: bool = False,
) -> BinaryIO:
    import openpyxl

    wb = openpyxl.Workbook(write_only=write_only)
    try:
        _append_summary_sheet(wb, summary_rows, write_only=write_only)
        for kind, title, labels, rows in (
            ("machine", "设备负荷", ["设备编号", "设备名称"], machines),
            ("operator", "人员负荷", ["工号", "姓名"], operators),
        ):
            sheet = wb.create_sheet(title) if write_only or summary_rows or kind == "operator" else wb.worksheets[0]
            sheet.title = title
            header = labels + ["班表内占用(小时)", "任务数", "可用工时(小时)", "整窗占用率(%)",
                               "累计负荷(小时)", "重叠负荷(小时)", "班表外占用(小时)", "计算方式版本", "计算说明"]
            if write_only:
                _append_write_only_row(sheet, header, is_header=True)
            else:
                _append_row(sheet, header)
            for row in rows:
                note = "此范围无可用工时" if row.get("reason") == "zero_available_capacity" else (
                    "；".join(issue["message"] for issue in row.get("calendar_issues", [])) or "日历资料不完整"
                    if row.get("reason") == "calendar_unavailable" else "")
                values = [row.get(kind + "_id"), row.get(kind + "_name"), row.get("hours"),
                          row.get("task_count"), row.get("capacity_hours"), _utilization_percent(row.get("utilization")),
                          row.get("summed_load_hours"), row.get("overlap_hours"), row.get("outside_calendar_hours"),
                          row.get("metric_version"), note]
                if write_only:
                    _append_write_only_row(sheet, values)
                else:
                    _append_row(sheet, values)
            if not write_only:
                _format_sheet(sheet)
        buf = _make_output_buffer(write_only=write_only)
        wb.save(buf)
        buf.seek(0)
        return buf
    finally:
        wb.close()


def export_downtime_impact_xlsx(
    machines: List[Dict[str, Any]],
    *,
    summary_rows: Optional[List[List[Any]]] = None,
    write_only: bool = False,
) -> BinaryIO:
    import openpyxl

    wb = openpyxl.Workbook(write_only=write_only)
    try:
        _append_summary_sheet(wb, summary_rows, write_only=write_only)
        ws = wb.create_sheet("停机影响") if (write_only or summary_rows) else wb.worksheets[0]
        header = ["设备编号", "设备名称", "停机时长(小时)", "停机次数", "与排程重叠(小时)", "重叠次数"]
        if write_only:
            _append_write_only_row(ws, header, is_header=True)
        else:
            ws.title = "停机影响"
            _append_row(ws, header)
        append = _append_write_only_row if write_only else _append_row
        for row in machines:
            append(ws, [row.get("machine_id"), row.get("machine_name"), row.get("downtime_hours"),
                        row.get("downtime_count"), row.get("schedule_overlap_hours"),
                        row.get("schedule_overlap_count")])
        if not write_only:
            _format_sheet(ws)

        buf = _make_output_buffer(write_only=write_only)
        wb.save(buf)
        buf.seek(0)
        return buf
    finally:
        wb.close()


def export_execution_review_xlsx(
    rows: List[Dict[str, Any]],
    *,
    summary_rows: Optional[List[List[Any]]] = None,
    write_only: bool = False,
) -> BinaryIO:
    import openpyxl

    wb = openpyxl.Workbook(write_only=write_only)
    try:
        _append_summary_sheet(wb, summary_rows, write_only=write_only)
        ws = wb.create_sheet("计划和现场实际") if (write_only or summary_rows) else wb.worksheets[0]
        if not write_only:
            ws.title = "计划和现场实际"
            _append_row(ws, _EXECUTION_REVIEW_HEADERS)
            for row in rows:
                _append_row(ws, _execution_review_values(row))
            _format_sheet(ws)
        else:
            _append_write_only_row(ws, _EXECUTION_REVIEW_HEADERS, is_header=True)
            for row in rows:
                _append_write_only_row(ws, _execution_review_values(row))

        buf = _make_output_buffer(write_only=write_only)
        wb.save(buf)
        buf.seek(0)
        return buf
    finally:
        wb.close()


def _execution_review_values(row: Dict[str, Any]) -> List[Any]:
    return [
        row.get("batch_id_label"),
        row.get("operation_label"),
        row.get("planned_start_time_label"),
        row.get("actual_start_time_label"),
        row.get("start_deviation_label"),
        row.get("planned_end_time_label"),
        row.get("actual_end_time_label"),
        row.get("end_deviation_label"),
        row.get("pause_duration_label"),
        row.get("exception_reason_label"),
        row.get("exception_severity_label"),
        row.get("exception_impact_minutes_label"),
        row.get("exception_affected_machine_label"),
        row.get("exception_affected_operator_label"),
        row.get("exception_handling_status_label"),
        row.get("exception_suggest_reschedule_label"),
        row.get("planned_resource_label"),
        row.get("actual_resource_label"),
        row.get("feedback_status_label"),
    ]
