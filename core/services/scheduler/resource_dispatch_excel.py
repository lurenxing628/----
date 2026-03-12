from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List, Sequence

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font


def _auto_width(ws) -> None:
    for column in ws.columns:
        max_length = 0
        column_letter = None
        for cell in column:
            if column_letter is None:
                column_letter = cell.column_letter
            text = "" if cell.value is None else str(cell.value)
            if len(text) > max_length:
                max_length = len(text)
        if column_letter is not None:
            ws.column_dimensions[column_letter].width = min(max(max_length + 2, 12), 36)


def _write_table(ws, headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
    ws.append(list(headers))
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row in rows:
        ws.append(list(row))
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    _auto_width(ws)


def _detail_headers() -> List[str]:
    return [
        "排程ID",
        "工序ID",
        "工序编码",
        "批次号",
        "图号",
        "工序",
        "工序名称",
        "开始时间",
        "结束时间",
        "时长(分钟)",
        "查询对象",
        "对应资源",
        "查询对象班组",
        "对应资源班组",
        "班组关系",
        "来源",
        "锁定状态",
        "是否跨天",
        "是否超期",
    ]


def _detail_table_rows(detail_rows: Sequence[Dict[str, Any]]) -> List[List[Any]]:
    table: List[List[Any]] = []
    for row in detail_rows:
        table.append(
            [
                row.get("schedule_id") or "",
                row.get("op_id") or "",
                row.get("op_code") or "",
                row.get("batch_id") or "",
                row.get("part_no") or "",
                row.get("seq") if row.get("seq") is not None else "",
                row.get("op_type_name") or "",
                row.get("start_time") or "",
                row.get("end_time") or "",
                row.get("duration_minutes") or 0,
                row.get("current_resource_label") or row.get("scope_label") or "",
                row.get("counterpart_resource_label") or "",
                row.get("current_team_name") or row.get("current_team_id") or "",
                row.get("counterpart_team_name") or row.get("counterpart_team_id") or "",
                row.get("team_relation_label") or "",
                row.get("source") or "",
                row.get("lock_status") or "",
                "是" if row.get("is_cross_day") else "否",
                "是" if row.get("is_overdue") else "否",
            ]
        )
    return table


def _calendar_table_rows(calendar_rows: Sequence[Dict[str, Any]]) -> List[List[Any]]:
    table: List[List[Any]] = []
    for row in calendar_rows:
        line = [row.get("scope_label") or ""]
        cells = row.get("cells") or []
        for cell in cells:
            line.append(cell.get("text") or "")
        table.append(line)
    return table


def build_resource_dispatch_workbook(payload: Dict[str, Any]) -> BytesIO:
    wb = Workbook()
    default_ws = wb.active
    wb.remove(default_ws)

    filters = payload.get("filters") or {}
    summary = payload.get("summary") or {}
    detail_rows: List[Dict[str, Any]] = list(payload.get("detail_rows") or [])
    calendar_headers: List[str] = list(payload.get("calendar_headers") or [])
    calendar_rows: List[Dict[str, Any]] = list(payload.get("calendar_rows") or [])

    ws_summary = wb.create_sheet("查询摘要")
    summary_pairs = [
        ("视角", filters.get("scope_type_label") or ""),
        ("查询对象", filters.get("scope_label") or ""),
        ("班组轴", filters.get("team_axis_label") or ""),
        ("区间类型", filters.get("period_preset_label") or ""),
        ("开始日期", filters.get("start_date") or ""),
        ("结束日期", filters.get("end_date") or ""),
        ("排产版本", filters.get("version") or ""),
        ("任务数量", summary.get("total_tasks") or 0),
        ("总工时（小时）", summary.get("total_hours") or 0),
        ("跨天任务", summary.get("cross_day_count") or 0),
        ("超期批次任务", summary.get("overdue_count") or 0),
        ("外协/未分配", summary.get("external_count") or 0),
        ("跨班组借调", summary.get("cross_team_count") or 0),
    ]
    for key, value in summary_pairs:
        ws_summary.append([key, value])
    for row in ws_summary.iter_rows():
        row[0].font = Font(bold=True)
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    _auto_width(ws_summary)

    if str(filters.get("scope_type") or "") == "team":
        operator_rows: List[Dict[str, Any]] = list(payload.get("operator_rows") or [])
        machine_rows: List[Dict[str, Any]] = list(payload.get("machine_rows") or [])
        cross_team_rows: List[Dict[str, Any]] = list(payload.get("cross_team_rows") or [])
        operator_calendar_headers: List[str] = list(payload.get("operator_calendar_headers") or [])
        operator_calendar_rows: List[Dict[str, Any]] = list(payload.get("operator_calendar_rows") or [])
        machine_calendar_headers: List[str] = list(payload.get("machine_calendar_headers") or [])
        machine_calendar_rows: List[Dict[str, Any]] = list(payload.get("machine_calendar_rows") or [])

        ws_operator_detail = wb.create_sheet("班组人员任务明细")
        _write_table(ws_operator_detail, _detail_headers(), _detail_table_rows(operator_rows))

        ws_machine_detail = wb.create_sheet("班组设备任务明细")
        _write_table(ws_machine_detail, _detail_headers(), _detail_table_rows(machine_rows))

        ws_operator_calendar = wb.create_sheet("班组人员日历")
        _write_table(
            ws_operator_calendar,
            ["查询对象"] + operator_calendar_headers,
            _calendar_table_rows(operator_calendar_rows),
        )

        ws_machine_calendar = wb.create_sheet("班组设备日历")
        _write_table(
            ws_machine_calendar,
            ["查询对象"] + machine_calendar_headers,
            _calendar_table_rows(machine_calendar_rows),
        )

        if cross_team_rows:
            ws_cross = wb.create_sheet("跨班组借调")
            _write_table(ws_cross, _detail_headers(), _detail_table_rows(cross_team_rows))
    else:
        ws_detail = wb.create_sheet("任务明细")
        _write_table(ws_detail, _detail_headers(), _detail_table_rows(detail_rows))

        ws_calendar = wb.create_sheet("日历排班")
        _write_table(ws_calendar, ["查询对象"] + calendar_headers, _calendar_table_rows(calendar_rows))

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
