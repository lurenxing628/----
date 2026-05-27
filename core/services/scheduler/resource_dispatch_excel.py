from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List, Sequence, cast

from openpyxl import Workbook
from openpyxl.cell.cell import Cell
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from core.models.resource_dispatch_public_labels import lock_status_public_label, source_public_label
from core.services.common.excel_templates import _sanitize_export_cell


def _auto_width(ws: Worksheet) -> None:
    for column in ws.columns:
        max_length = 0
        column_letter = None
        for cell in column:
            if column_letter is None:
                column_index = cell.column
                if isinstance(column_index, int):
                    column_letter = get_column_letter(column_index)
                elif isinstance(column_index, str) and column_index:
                    column_letter = column_index
            text = "" if cell.value is None else str(cell.value)
            if len(text) > max_length:
                max_length = len(text)
        if column_letter is not None:
            ws.column_dimensions[column_letter].width = min(max(max_length + 2, 12), 36)


def _append_row(ws: Worksheet, values: Sequence[Any]) -> None:
    ws.append([_sanitize_export_cell(v) for v in values])


def _write_table(ws: Worksheet, headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
    _append_row(ws, list(headers))
    ws.freeze_panes = "A2"
    for cell_obj in ws[1]:
        cell = cast(Cell, cell_obj)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row in rows:
        _append_row(ws, list(row))
    for row in ws.iter_rows(min_row=2):
        for cell_obj in row:
            cell = cast(Cell, cell_obj)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    _auto_width(ws)


def _detail_headers() -> List[str]:
    return [
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
        "现场状态",
        "最近异常原因",
        "严重程度",
        "预计影响时间",
        "影响设备",
        "影响人员",
        "处理状态",
        "是否建议重排",
        "情况说明",
    ]


def _first_present(row: Dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _yes_no_label(value: Any) -> str:
    return "是" if value else "否"


def _source_label(row: Dict[str, Any]) -> str:
    return str(_first_present(row, "source_label") or source_public_label(row.get("source")))


def _lock_status_label(row: Dict[str, Any]) -> str:
    return str(_first_present(row, "lock_status_label") or lock_status_public_label(row.get("lock_status")))


def _build_detail_row(row: Dict[str, Any]) -> List[Any]:
    seq = row.get("seq")
    return [
        _first_present(row, "op_code"),
        _first_present(row, "batch_id"),
        _first_present(row, "part_no"),
        seq if seq is not None else "",
        _first_present(row, "op_type_name"),
        _first_present(row, "start_time"),
        _first_present(row, "end_time"),
        _first_present(row, "duration_minutes", default=0),
        _first_present(row, "current_resource_label", "scope_label"),
        _first_present(row, "counterpart_resource_label"),
        _first_present(row, "current_team_name", "current_team_id"),
        _first_present(row, "counterpart_team_name", "counterpart_team_id"),
        _first_present(row, "team_relation_label"),
        _source_label(row),
        _lock_status_label(row),
        _yes_no_label(row.get("is_cross_day")),
        _yes_no_label(row.get("is_overdue")),
        _first_present(row, "execution_status_label", default="待开工"),
        _first_present(row, "latest_exception_reason_label", default="暂无异常"),
        _first_present(row, "latest_exception_severity_label", default=""),
        _first_present(row, "latest_exception_impact_minutes_label", default=""),
        _first_present(row, "latest_exception_affected_machine_label", default=""),
        _first_present(row, "latest_exception_affected_operator_label", default=""),
        _first_present(row, "latest_exception_handling_status_label", default=""),
        _first_present(row, "latest_exception_suggest_reschedule_label", default=""),
        _first_present(row, "latest_exception_remark", default=""),
    ]


def _detail_table_rows(detail_rows: Sequence[Dict[str, Any]]) -> List[List[Any]]:
    return [_build_detail_row(row) for row in detail_rows]


def _calendar_table_rows(calendar_rows: Sequence[Dict[str, Any]]) -> List[List[Any]]:
    table: List[List[Any]] = []
    for row in calendar_rows:
        line = [row.get("scope_label") or ""]
        cells = row.get("cells") or []
        for cell in cells:
            line.append(cell.get("text") or "")
        table.append(line)
    return table


def _empty_reason_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text == "all_rows_filtered_by_invalid_time":
        return "排班开始或结束时间写法不对，已全部过滤。"
    return text


def _degradation_message_text(summary: Dict[str, Any]) -> str:
    events = summary.get("degradation_events") or []
    messages: List[str] = []
    for item in events:
        if not isinstance(item, dict):
            continue
        message = str(item.get("message") or "").strip()
        if not message:
            continue
        try:
            count = int(item.get("count") or 0)
        except Exception:
            count = 0
        text = f"{message}（{count}）" if count > 1 else message
        if text not in messages:
            messages.append(text)
    return "；".join(messages)


def _summary_filter_value(filters: Dict[str, Any], key: str) -> Any:
    return filters.get(key) or ""


def _summary_plan_label(filters: Dict[str, Any]) -> Any:
    return (
        filters.get("plan_view_label")
        or filters.get("scenario_display_name")
        or filters.get("scenario_name")
        or filters.get("effective_plan_role_label")
        or filters.get("plan_role_label")
        or ""
    )


def _summary_plan_identity_value(payload: Dict[str, Any]) -> str:
    plan_identity = payload.get("plan_identity")
    if not isinstance(plan_identity, dict):
        return ""
    parts = [
        str(plan_identity.get("kind_label") or "").strip(),
        str(plan_identity.get("dispatch_feedback_label") or "").strip(),
    ]
    return "；".join(part for part in parts if part)


def _summary_plan_guardrail_value(payload: Dict[str, Any]) -> str:
    plan_identity = payload.get("plan_identity")
    if not isinstance(plan_identity, dict):
        return ""
    return str(plan_identity.get("guardrail_text") or "").strip()


def _summary_scenario_note(filters: Dict[str, Any]) -> str:
    if filters.get("is_scenario_preview"):
        return "这是模拟方案预览，正式计划还没有改变。"
    return ""


def _summary_pairs(payload: Dict[str, Any]) -> List[List[Any]]:
    filters = payload.get("filters") or {}
    summary = payload.get("summary") or {}
    counters = summary.get("degradation_counters") or {}
    overdue_markers_message = payload.get("overdue_markers_message") or ""
    return [
        ["视角", _summary_filter_value(filters, "scope_type_label")],
        ["查询对象", _summary_filter_value(filters, "scope_label")],
        ["班组轴", _summary_filter_value(filters, "team_axis_label")],
        ["区间类型", _summary_filter_value(filters, "period_preset_label")],
        ["开始日期", _summary_filter_value(filters, "start_date")],
        ["结束日期", _summary_filter_value(filters, "end_date")],
        ["排产版本", _summary_filter_value(filters, "version")],
        ["查看方案", _summary_plan_label(filters)],
        ["计划身份", _summary_plan_identity_value(payload)],
        ["派工反馈说明", _summary_plan_guardrail_value(payload)],
        ["模拟方案说明", _summary_scenario_note(filters)],
        ["任务数量", summary.get("total_tasks") or 0],
        ["总工时（小时）", summary.get("total_hours") or 0],
        ["跨天任务", summary.get("cross_day_count") or 0],
        ["超期批次任务", summary.get("overdue_count") or 0],
        ["外协未分配", summary.get("external_count") or 0],
        ["跨班组", summary.get("cross_team_count") or 0],
        ["数据不完整", _yes_no_label(summary.get("degraded"))],
        ["空结果说明", _yes_no_label(bool(summary.get("empty_reason")))],
        ["空结果原因", _empty_reason_text(summary.get("empty_reason"))],
        ["开始或结束时间写法不对，已过滤的记录数", int(counters.get("bad_time_row_skipped") or 0)],
        ["处理提示", _degradation_message_text(summary)],
        ["超期标记说明", overdue_markers_message],
    ]


def _write_summary_sheet(wb: Workbook, payload: Dict[str, Any]) -> None:
    ws_summary = cast(Worksheet, wb.create_sheet("查询摘要"))
    for key, value in _summary_pairs(payload):
        _append_row(ws_summary, [key, value])
    ws_summary.freeze_panes = "A2"
    for row in ws_summary.iter_rows():
        row[0].font = Font(bold=True)
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    _auto_width(ws_summary)


def _write_calendar_sheet(wb: Workbook, title: str, headers: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    ws = cast(Worksheet, wb.create_sheet(title))
    _write_table(ws, ["查询对象"] + list(headers), _calendar_table_rows(rows))


def _write_detail_sheet(wb: Workbook, title: str, rows: Sequence[Dict[str, Any]]) -> None:
    ws = cast(Worksheet, wb.create_sheet(title))
    _write_table(ws, _detail_headers(), _detail_table_rows(rows))


def _write_team_scope_sheets(wb: Workbook, payload: Dict[str, Any]) -> None:
    _write_detail_sheet(wb, "班组人员任务明细", list(payload.get("operator_rows") or []))
    _write_detail_sheet(wb, "班组设备任务明细", list(payload.get("machine_rows") or []))
    _write_calendar_sheet(
        wb,
        "班组人员日历",
        list(payload.get("operator_calendar_headers") or []),
        list(payload.get("operator_calendar_rows") or []),
    )
    _write_calendar_sheet(
        wb,
        "班组设备日历",
        list(payload.get("machine_calendar_headers") or []),
        list(payload.get("machine_calendar_rows") or []),
    )
    cross_team_rows = list(payload.get("cross_team_rows") or [])
    if cross_team_rows:
        _write_detail_sheet(wb, "跨班组", cross_team_rows)


def _write_resource_scope_sheets(wb: Workbook, payload: Dict[str, Any]) -> None:
    _write_detail_sheet(wb, "任务明细", list(payload.get("detail_rows") or []))
    _write_calendar_sheet(
        wb,
        "日历排班",
        list(payload.get("calendar_headers") or []),
        list(payload.get("calendar_rows") or []),
    )


def build_resource_dispatch_workbook(payload: Dict[str, Any]) -> BytesIO:
    wb = Workbook()
    default_ws = wb.active
    if default_ws is None:
        raise ValueError("Workbook 缺少活动工作表")

    wb.remove(default_ws)

    filters = payload.get("filters") or {}
    _write_summary_sheet(wb, payload)

    if str(filters.get("scope_type") or "") == "team":
        _write_team_scope_sheets(wb, payload)
    else:
        _write_resource_scope_sheets(wb, payload)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
