"""Pure query values for archived history; no database or metric calculation."""

import re
from datetime import date

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_candidate import local_time

HISTORY_VERSION = "decision-history-v1"
DEFAULT_METRIC_KEYS = ("overdue_count", "total_tardiness_hours", "makespan_hours", "elapsed_seconds")
HISTORY_STATES = ("all", "queued", "running", "complete", "partial", "failed", "interrupted", "committed")
QUERY_FIELDS = ("timeline", "date_from", "date_to", "metric_keys", "comparison", "reference_run_ref",
                "selected_entry_ref", "range_start", "range_end", "resource_window_days", "state", "sort", "order",
                "page", "size", "condition_page", "condition_size", "snapshot_ref")
_ENTRY = re.compile(r"(?:run:[0-9a-f]{48}|adoption:[0-9a-f]{32})\Z")


def reject_history(message, code="invalid_input", status=422):
    raise WorkbenchCommandRejected(code, message, status)


def validate_history_entry_ref(value):
    if type(value) is not str or len(value) > 128 or _ENTRY.fullmatch(value) is None:
        reject_history("历史条目编号无效，请从历史清单重新选择。")
    return value


def _integer(value, name, default, *, allowed=None, maximum=1000000):
    value = default if value is None else value
    if type(value) is str and re.fullmatch(r"[1-9][0-9]{0,6}", value):
        value = int(value)
    if type(value) is not int or not 1 <= value <= maximum or allowed is not None and value not in allowed:
        reject_history(name + "无效，请重新选择。")
    return value


def _date_range(values):
    start, end = values.get("date_from"), values.get("date_to")
    if start is None and end is None:
        return None, None
    try:
        if any(type(value) is not str or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None for value in (start, end)):
            raise ValueError("Invalid date")
        if date.fromisoformat(start) > date.fromisoformat(end):
            raise ValueError("Reversed dates")
    except (ValueError, TypeError):
        reject_history("时间线起止日期须一起填写，开始日期须早于或等于结束日期。")
    return start, end


def _resource_range(values):
    start, end = values.get("range_start"), values.get("range_end")
    if start is None and end is None:
        return None, None
    try:
        start, end = local_time(start), local_time(end)
        if start >= end:
            raise ValueError("Reversed window")
    except (ValueError, TypeError):
        reject_history("资源共同窗口须同时填写有效工厂本地起止时间，结束时间须晚于开始时间。")
    return start.isoformat(), end.isoformat()


def _metric_keys(value):
    if value is None:
        return list(DEFAULT_METRIC_KEYS)
    values = value.split(",") if type(value) is str else value
    if (type(values) not in (list, tuple) or not 1 <= len(values) <= 100
            or any(type(key) is not str or re.fullmatch(r"[a-z][a-z0-9_]{0,79}", key) is None for key in values)
            or len(set(values)) != len(values)):
        reject_history("指标列表无效，请从指标目录重新选择。")
    return list(values)


def normalize_history_query(values=None):
    """Accept API strings or retained UI values, returning one typed query."""
    values = {} if values is None else values
    if type(values) is not dict or set(values) - set(QUERY_FIELDS):
        reject_history("历史筛选含不支持的字段，请重新选择。")
    timeline, comparison = values.get("timeline", "run"), values.get("comparison", "observed")
    state, sort, order = values.get("state", "all"), values.get("sort", "occurred_at"), values.get("order", "desc")
    if (timeline not in ("run", "official") or comparison not in ("observed", "same_conditions")
            or state not in HISTORY_STATES or sort != "occurred_at" or order not in ("asc", "desc")):
        reject_history("历史时间线、比较方式、状态或排序条件无效。")
    reference = values.get("reference_run_ref")
    if reference is not None and (type(reference) is not str or re.fullmatch(r"[0-9a-f]{48}", reference) is None):
        reject_history("基准运行编号无效，请从运行记录重新选择。")
    selected = values.get("selected_entry_ref")
    if selected is not None:
        validate_history_entry_ref(selected)
    snapshot = values.get("snapshot_ref")
    if snapshot is not None and (type(snapshot) is not str or not snapshot or len(snapshot) > 512):
        reject_history("历史读取编号无效，请刷新历史。")
    date_from, date_to = _date_range(values)
    range_start, range_end = _resource_range(values)
    return {"timeline": timeline, "date_from": date_from, "date_to": date_to,
            "metric_keys": _metric_keys(values.get("metric_keys")), "comparison": comparison,
            "reference_run_ref": reference, "selected_entry_ref": selected,
            "range_start": range_start, "range_end": range_end,
            "resource_window_days": _integer(values.get("resource_window_days"), "资源窗口天数", 7, maximum=366),
            "state": state, "sort": sort, "order": order,
            "page": _integer(values.get("page"), "历史页码", 1), "size": _integer(values.get("size"), "每页条数", 20, allowed=(20, 50)),
            "condition_page": _integer(values.get("condition_page"), "条件页码", 1),
            "condition_size": _integer(values.get("condition_size"), "每页条件数", 20, allowed=(20, 50)),
            "snapshot_ref": snapshot}


def history_snapshot_scope(query):
    """Pagination changes the view; the selected source and filters bind the read."""
    excluded = ("page", "size", "condition_page", "condition_size", "snapshot_ref")
    return {"source": "production", "kind": "decision-history", **{key: value for key, value in query.items() if key not in excluded}}
