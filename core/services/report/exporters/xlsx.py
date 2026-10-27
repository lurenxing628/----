from __future__ import annotations

import io
import tempfile
from functools import lru_cache
from typing import Any, BinaryIO, Dict, List, cast

from core.services.common.excel_templates import sanitize_export_cell
from core.services.report.utilization import utilization_availability_note, utilization_percent


@lru_cache(maxsize=None)
def _cell_styles():
    """表头加粗字体、表头对齐和正文对齐；样式按值登记进工作簿，所有单元格共用这三个对象。"""
    from openpyxl.styles import Alignment, Font

    return Font(bold=True), Alignment(horizontal="center", vertical="center"), Alignment(vertical="top", wrap_text=True)


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

    bold, header_alignment, body_alignment = _cell_styles()
    row_cells: List[Any] = []
    for value in values:
        cell = WriteOnlyCell(ws, value=sanitize_export_cell(value))
        if is_header:
            cell.font = bold
            cell.alignment = header_alignment
        else:
            cell.alignment = body_alignment
        row_cells.append(cell)
    ws.append(row_cells)


def _format_sheet(ws) -> None:
    bold, header_alignment, body_alignment = _cell_styles()
    ws.freeze_panes = "A2"
    for cell in ws[1]:
        cell.font = bold
        cell.alignment = header_alignment
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = body_alignment
    _auto_width(ws)


def _make_output_buffer(*, write_only: bool) -> BinaryIO:
    if write_only:
        return cast(BinaryIO, tempfile.SpooledTemporaryFile(max_size=4 * 1024 * 1024, mode="w+b"))
    return io.BytesIO()


_OVERDUE_HEADERS = ["类别", "批次号", "图号", "名称", "数量", "交期", "完工/截至时间", "超期(天)", "超期(小时)"]
_EXECUTION_REVIEW_HEADERS = [
    "批次",
    "工序",
    "计划开始",
    "实际开始",
    "开工偏差",
    "计划结束",
    "实际结束",
    "完工偏差",
    "计划资源",
    "实际资源",
    "现场反馈状态",
]


# 摘要区里必须按原文落格、不能被 Excel 当公式的编号行标签；workbench 导出器从这里取，保证单一来源。
SUMMARY_IDENTITY_LABELS = ("计划编号", "数据版本编号")


def append_summary_row(ws, values: List[Any], *, write_only: bool) -> None:
    if len(values) == 2 and values[0] in SUMMARY_IDENTITY_LABELS:
        from openpyxl.cell import WriteOnlyCell

        body_alignment = _cell_styles()[2]
        cells = [WriteOnlyCell(ws, value=sanitize_export_cell(values[0])),
                 WriteOnlyCell(ws, value=values[1])]
        cells[1].data_type = "s"
        for cell in cells:
            cell.alignment = body_alignment
        ws.append(cells)
    elif write_only:
        _append_write_only_row(ws, values)
    else:
        _append_row(ws, values)


def _append_summary_sheet(wb, summary_rows: List[List[Any]], *, write_only: bool) -> None:
    if write_only:
        ws = wb.create_sheet("查询摘要")
        _append_write_only_row(ws, ["项目", "内容"], is_header=True)
        for row in summary_rows:
            append_summary_row(ws, row, write_only=True)
        return

    ws = wb.worksheets[0]
    ws.title = "查询摘要"
    _append_row(ws, ["项目", "内容"])
    for row in summary_rows:
        append_summary_row(ws, row, write_only=False)
    ws.freeze_panes = "A2"
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 42
    bold, _header_alignment, body_alignment = _cell_styles()
    for row in ws.iter_rows():
        row[0].font = bold
        for cell in row:
            cell.alignment = body_alignment


def export_overdue_xlsx(
    items: List[Dict[str, Any]],
    *,
    summary_rows: List[List[Any]],
    write_only: bool = False,
) -> BinaryIO:
    import openpyxl

    wb = openpyxl.Workbook(write_only=write_only)
    try:
        _append_summary_sheet(wb, summary_rows, write_only=write_only)
        ws = wb.create_sheet("超期清单")
        if write_only:
            _append_write_only_row(ws, _OVERDUE_HEADERS, is_header=True)
        else:
            ws.title = "超期清单"
            _append_row(ws, _OVERDUE_HEADERS)
        append = _append_write_only_row if write_only else _append_row
        for item in items:
            append(ws, [item["bucket_label"], item["batch_id"], item["part_no"],
                        item["part_name"], item["quantity"], item["due_date"],
                        item["finish_time"] or item["as_of_time"],
                        item["delay_days"], item["delay_hours"]])
        if not write_only:
            _format_sheet(ws)

        buf = _make_output_buffer(write_only=write_only)
        wb.save(buf)
        buf.seek(0)
        return buf
    finally:
        wb.close()


def export_utilization_xlsx(
    machines: List[Dict[str, Any]],
    operators: List[Dict[str, Any]],
    *,
    summary_rows: List[List[Any]],
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
            sheet = wb.create_sheet(title)
            sheet.title = title
            header = labels + ["班表内占用(小时)", "任务数", "可用工时(小时)", "整窗占用率(%)",
                               "累计负荷(小时)", "重叠负荷(小时)", "班表外占用(小时)", "计算方式版本", "计算说明"]
            if write_only:
                _append_write_only_row(sheet, header, is_header=True)
            else:
                _append_row(sheet, header)
            for row in rows:
                values = [row[kind + "_id"], row[kind + "_name"], row["hours"],
                          row["task_count"], row["capacity_hours"], utilization_percent(row["utilization"]),
                          row["summed_load_hours"], row["overlap_hours"], row["outside_calendar_hours"],
                          row["metric_version"], utilization_availability_note(row)]
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
    summary_rows: List[List[Any]],
    write_only: bool = False,
) -> BinaryIO:
    import openpyxl

    wb = openpyxl.Workbook(write_only=write_only)
    try:
        _append_summary_sheet(wb, summary_rows, write_only=write_only)
        ws = wb.create_sheet("停机影响")
        header = ["设备编号", "设备名称", "停机时长(小时)", "停机次数", "与排程重叠(小时)", "重叠次数"]
        if write_only:
            _append_write_only_row(ws, header, is_header=True)
        else:
            ws.title = "停机影响"
            _append_row(ws, header)
        append = _append_write_only_row if write_only else _append_row
        for row in machines:
            append(ws, [row["machine_id"], row["machine_name"], row["downtime_hours"],
                        row["downtime_count"], row["schedule_overlap_hours"],
                        row["schedule_overlap_count"]])
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
    summary_rows: List[List[Any]],
    write_only: bool = False,
) -> BinaryIO:
    import openpyxl

    wb = openpyxl.Workbook(write_only=write_only)
    try:
        _append_summary_sheet(wb, summary_rows, write_only=write_only)
        ws = wb.create_sheet("计划和现场实际")
        if not write_only:
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
        row["batch_id_label"],
        row["operation_label"],
        row["planned_start_time_label"],
        row["actual_start_time_label"],
        row["start_deviation_label"],
        row["planned_end_time_label"],
        row["actual_end_time_label"],
        row["end_deviation_label"],
        row["planned_resource_label"],
        row["actual_resource_label"],
        row["feedback_status_label"],
    ]
