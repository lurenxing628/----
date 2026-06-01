from __future__ import annotations

from typing import Any

from core.models.operation_execution_event import (
    EXECUTION_ACTION_REPORT_EXCEPTION,
    EXECUTION_EVENT_EXCEPTION,
    EXECUTION_EVENT_FINISH,
    EXECUTION_EVENT_PAUSE,
    EXECUTION_EVENT_RESUME,
    EXECUTION_EVENT_START,
    EXECUTION_STATUS_COMPLETED,
    EXECUTION_STATUS_EXCEPTION,
    EXECUTION_STATUS_NOT_STARTED,
    EXECUTION_STATUS_PAUSED,
    EXECUTION_STATUS_PROCESSING,
)

EXECUTION_ACTION_FILL_ACTUAL = "fill_actual"
EXECUTION_ACTION_VIEW_RECORDS = "view_records"

STATUS_LABELS = {
    EXECUTION_STATUS_NOT_STARTED: "待开工",
    EXECUTION_STATUS_PROCESSING: "生产中",
    EXECUTION_STATUS_PAUSED: "已暂停",
    EXECUTION_STATUS_EXCEPTION: "异常中",
    EXECUTION_STATUS_COMPLETED: "已完工",
}

ACTION_LABELS = {
    EXECUTION_EVENT_START: "开工",
    EXECUTION_EVENT_PAUSE: "暂停",
    EXECUTION_EVENT_RESUME: "继续生产",
    EXECUTION_EVENT_FINISH: "完工",
    EXECUTION_EVENT_EXCEPTION: "报异常",
    EXECUTION_ACTION_REPORT_EXCEPTION: "报异常",
    EXECUTION_ACTION_FILL_ACTUAL: "填写实际情况",
    EXECUTION_ACTION_VIEW_RECORDS: "查看现场记录",
}

REASON_LABELS = {
    "equipment": "设备问题",
    "person": "人员问题",
    "material": "物料问题",
    "quality": "质量问题",
    "process": "工艺问题",
    "external": "外协问题",
    "other": "其他",
}

SEVERITY_LABELS = {
    "low": "轻微",
    "medium": "一般",
    "high": "严重",
    "critical": "紧急",
}

HANDLING_STATUS_LABELS = {
    "new": "刚上报",
    "checking": "处理中",
    "waiting": "等待条件",
    "handled": "已处理",
}

def _normalize_remark_token(value: Any) -> str:
    return str(value or "").strip().casefold()


# 这一行记录“自己的”结构化字段名。一条说明只有在等于本记录的某个结构化枚举码时，
# 才说明它是写入链路把内部值错灌进了说明字段；否则即便它恰好等于别的记录用得到的
# 英文码，也应当原样保留，避免误杀用户真填的内容。
_INTERNAL_REMARK_EVENT_FIELDS = (
    "event_type",
    "reported_status",
    "reason_code",
    "severity",
    "handling_status",
)


def execution_status_label(value: Any) -> str:
    text = str(value or "").strip()
    return STATUS_LABELS.get(text, "状态未识别")


def execution_action_label(value: Any) -> str:
    text = str(value or "").strip()
    return ACTION_LABELS.get(text, "操作未识别")


def event_type_to_action(value: Any) -> str:
    text = str(value or "").strip()
    if text == EXECUTION_EVENT_EXCEPTION:
        return EXECUTION_ACTION_REPORT_EXCEPTION
    return text


def action_to_event_type(value: Any) -> str:
    text = str(value or "").strip()
    if text == EXECUTION_ACTION_REPORT_EXCEPTION:
        return EXECUTION_EVENT_EXCEPTION
    return text


def exception_reason_label(value: Any) -> str:
    text = str(value or "").strip()
    return REASON_LABELS.get(text, "原因未识别") if text else "未填写原因"


def severity_label(value: Any) -> str:
    text = str(value or "").strip()
    return SEVERITY_LABELS.get(text, "严重程度未识别") if text else "未填写严重程度"


def handling_status_label(value: Any) -> str:
    text = str(value or "").strip()
    return HANDLING_STATUS_LABELS.get(text, "处理状态未识别") if text else HANDLING_STATUS_LABELS["new"]


def suggest_reschedule_label(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in ("1", "yes", "true"):
        return "建议重新排程"
    if text in ("0", "no", "false", ""):
        return "暂不建议重新排程"
    return "暂不清楚是否需要重新排程"


def public_execution_remark(value: Any, *, internal_tokens: Any = None) -> str:
    """把“情况说明”里被错灌进来的内部枚举码清掉，保留用户真填的文字。

    ``internal_tokens`` 传入本条记录自己的结构化码集合（event_type / reported_status /
    reason_code / severity / handling_status）。说明只有在等于其中之一时才判为泄漏并清空，
    这样不会误伤恰好等于其它记录所用英文码的合法说明。判定用 casefold 归一，避免大小写绕过。
    """
    text = str(value or "").strip()
    if not text:
        return ""
    tokens = {
        _normalize_remark_token(token)
        for token in (internal_tokens or ())
        if str(token or "").strip()
    }
    if _normalize_remark_token(text) in tokens:
        return ""
    return text


def internal_remark_tokens_from_event(event: Any) -> frozenset:
    """从一条执行事件里取出它“自己的”结构化枚举码，供 public_execution_remark 判定泄漏。"""
    return frozenset(
        str(getattr(event, field, "") or "").strip()
        for field in _INTERNAL_REMARK_EVENT_FIELDS
        if str(getattr(event, field, "") or "").strip()
    )


__all__ = [
    "ACTION_LABELS",
    "EXECUTION_ACTION_FILL_ACTUAL",
    "EXECUTION_ACTION_VIEW_RECORDS",
    "HANDLING_STATUS_LABELS",
    "REASON_LABELS",
    "SEVERITY_LABELS",
    "STATUS_LABELS",
    "action_to_event_type",
    "exception_reason_label",
    "event_type_to_action",
    "execution_action_label",
    "execution_status_label",
    "handling_status_label",
    "internal_remark_tokens_from_event",
    "public_execution_remark",
    "severity_label",
    "suggest_reschedule_label",
]
