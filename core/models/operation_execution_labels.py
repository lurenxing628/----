from __future__ import annotations

from typing import Any

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


__all__ = [
    "HANDLING_STATUS_LABELS",
    "REASON_LABELS",
    "SEVERITY_LABELS",
    "exception_reason_label",
    "handling_status_label",
    "severity_label",
    "suggest_reschedule_label",
]
