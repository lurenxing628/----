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
    return HANDLING_STATUS_LABELS.get(text, "处理状态未识别") if text else "未填写处理状态"


def suggest_reschedule_label(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in ("yes", "true", "1"):
        return "建议重新排程"
    if text in ("no", "false", "0"):
        return "暂不建议重新排程"
    return "暂不清楚是否需要重新排程"


__all__ = [
    "ACTION_LABELS",
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
    "severity_label",
    "suggest_reschedule_label",
]
