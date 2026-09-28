"""Explicit single-machine downtime input; no business-code based mutation."""

import re
from datetime import datetime

from core.models.workbench_command import WorkbenchCommandRejected

REASONS = {"maintenance": "计划维护", "breakdown": "故障停机", "power": "停电/能耗", "tooling": "换刀/工装", "other": "其他"}


def _time(value, field):
    if type(value) is not str or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}(:[0-9]{2})?", value) is None:
        raise WorkbenchCommandRejected("invalid_input", "停机起止须填写年月日和时分。", 422)
    try:
        return datetime.fromisoformat(value).isoformat(sep=" ", timespec="seconds")
    except ValueError as exc:
        raise WorkbenchCommandRejected("invalid_input", "停机日期或时刻不存在，请核对。", 422) from exc


def normalize_downtime(action, value):
    allowed = {"start_time", "end_time", "reason_code", "reason_detail"} if action != "cancel" else set()
    if action != "create":
        allowed.add("downtime_ref")
    if action not in ("create", "update", "cancel") or type(value) is not dict or set(value) - allowed:
        raise WorkbenchCommandRejected("invalid_input", "停机资料格式不正确，请刷新后重新填写。", 422)
    result = {}
    if action != "create":
        ref = value.get("downtime_ref")
        if type(ref) is not str or re.fullmatch(r"[0-9a-f]{48}", ref) is None:
            raise WorkbenchCommandRejected("invalid_input", "请选择有效的停机记录。", 422)
        result["downtime_ref"] = ref
    if action == "cancel":
        return result
    return {**result, **_window_fields(value)}


def _window_fields(value):
    result = {}
    result.update({key: _time(value.get(key), key) for key in ("start_time", "end_time")})
    if result["end_time"] <= result["start_time"]:
        raise WorkbenchCommandRejected("invalid_input", "停机结束必须晚于开始。", 422)
    reason, detail = value.get("reason_code"), value.get("reason_detail")
    if type(reason) is not str or reason not in REASONS or detail is not None and type(detail) is not str:
        raise WorkbenchCommandRejected("invalid_input", "请选择停机原因，并使用文字填写说明。", 422)
    result.update(reason_code=reason, reason_detail=(detail.strip() or None) if detail is not None else None)
    return result
