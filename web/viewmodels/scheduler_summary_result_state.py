from __future__ import annotations

import math
from typing import Any, Dict, Optional

from .scheduler_summary_status import error_count_blocks_success_inference

_RESULT_STATUS_LABELS = {
    "success": "成功",
    "partial": "部分成功",
    "failed": "失败",
    "simulated": "模拟排产",
    "unknown": "有问题，需检查",
}
_COMPLETION_STATUS_VALUES = {"success", "partial", "failed", "unknown"}
# ok/fail 是历史库可能存在的输入别名（读取归一，不进展示字典）；
# ok2 已删——写入方零证据（git log -S 零命中 + ScheduleResultStatus 枚举仅 4 值，
# fusion-label-single-source 拍板）：旧库若真有 ok2 行走 unknown 诚实降级。
_LEGACY_RESULT_STATUS_ALIASES = {
    "ok": "success",
    "fail": "failed",
}
_SUMMARY_COUNT_PARSE_FAILED_CODE = "summary_count_parse_failed"


def result_status_display_labels() -> Dict[str, str]:
    """展示字典（4 合法值 + unknown）——排产 result_status 词表唯一字源。

    analysis_overview / guardrail_messages 从此派生，不再各自手写；
    输入别名（ok/fail）只进 resolve 归一，不进展示字典。
    """
    return dict(_RESULT_STATUS_LABELS)


def resolve_result_status(value: Any) -> str:
    """归一 result_status 输入：别名（ok/fail）映射为合法值，其余小写原样返回。"""
    return _normalize_result_status_value(value)


def _has_summary_count_parse_marker(summary: Dict[str, Any]) -> bool:
    if bool(summary.get("summary_count_parse_failed")):
        return True
    counters = summary.get("degradation_counters")
    if isinstance(counters, dict) and counters.get(_SUMMARY_COUNT_PARSE_FAILED_CODE):
        return True
    causes = summary.get("degraded_causes")
    if isinstance(causes, list) and _SUMMARY_COUNT_PARSE_FAILED_CODE in {str(item or "").strip() for item in causes}:
        return True
    events = summary.get("degradation_events")
    if isinstance(events, list):
        for event in events:
            if isinstance(event, dict) and str(event.get("code") or "").strip() == _SUMMARY_COUNT_PARSE_FAILED_CODE:
                return True
    return False


def counts_from_summary(summary: Dict[str, Any]) -> Dict[str, int]:
    counts = summary.get("counts")
    if not isinstance(counts, dict):
        counts = {}

    parse_failed = False

    def _to_int(value: Any) -> int:
        nonlocal parse_failed
        if value is None or value == "":
            return 0
        if isinstance(value, bool):
            parse_failed = True
            return 0
        if isinstance(value, float) and (not math.isfinite(value) or not value.is_integer()):
            parse_failed = True
            return 0
        try:
            text = str(value).strip()
            if not text:
                return 0
            if "." in text:
                fv = float(text)
                if not math.isfinite(fv) or not fv.is_integer():
                    parse_failed = True
                    return 0
                number = int(fv)
            else:
                number = int(text)
        except (TypeError, ValueError, OverflowError):
            parse_failed = True
            return 0
        if number < 0:
            parse_failed = True
            return 0
        return number

    return {
        "scheduled_ops": _to_int(counts.get("scheduled_ops", summary.get("scheduled_ops"))),
        "failed_ops": _to_int(counts.get("failed_ops", summary.get("failed_ops"))),
        "total_ops": _to_int(counts.get("op_count", counts.get("total_ops", summary.get("total_ops")))),
        "_parse_failed": int(parse_failed or _has_summary_count_parse_marker(summary)),
    }


def _normalize_result_status_value(value: Any) -> str:
    text = str(value or "").strip().lower()
    return _LEGACY_RESULT_STATUS_ALIASES.get(text, text)


def _known_completion_status(value: Any) -> str:
    text = _normalize_result_status_value(value)
    if text in _COMPLETION_STATUS_VALUES:
        return text
    return ""


def _completion_status_from_counts(*, status: str, scheduled_ops: int, failed_ops: int, total_ops: int) -> str:
    if scheduled_ops <= 0 and failed_ops <= 0 and total_ops <= 0:
        return "unknown"
    if failed_ops > 0 and scheduled_ops > 0:
        return "partial"
    if failed_ops > 0:
        return "failed"
    if total_ops > 0 and scheduled_ops < total_ops:
        return "partial"
    return "success"


def _has_summary_errors(summary: Dict[str, Any]) -> bool:
    if error_count_blocks_success_inference(summary.get("error_count")):
        return True

    for key in ("errors", "errors_sample", "public_error_details"):
        value = summary.get(key)
        if isinstance(value, (list, tuple)) and len(value) > 0:
            return True
        if isinstance(value, str) and value.strip():
            return True
    return False


def derive_completion_status(*, result_status: Any, summary: Optional[Dict[str, Any]]) -> str:
    summary_dict = summary if isinstance(summary, dict) else {}
    counts = counts_from_summary(summary_dict)
    if bool(counts.get("_parse_failed")):
        return "unknown"

    summary_status = _known_completion_status(summary_dict.get("completion_status"))
    if summary_status:
        return summary_status

    status = _normalize_result_status_value(result_status)
    known_status = _known_completion_status(status)

    if known_status:
        if known_status == "success" and _has_summary_errors(summary_dict):
            return "unknown"
        return known_status
    if _has_summary_errors(summary_dict):
        return "unknown"
    return _completion_status_from_counts(
        status=status,
        scheduled_ops=int(counts.get("scheduled_ops") or 0),
        failed_ops=int(counts.get("failed_ops") or 0),
        total_ops=int(counts.get("total_ops") or 0),
    )


def result_status_display_label(*, raw_status: Any, outcome_status: Any) -> str:
    raw = _normalize_result_status_value(raw_status)
    outcome = _normalize_result_status_value(outcome_status)
    raw_label = _RESULT_STATUS_LABELS.get(raw, raw or "")
    outcome_label = _RESULT_STATUS_LABELS.get(outcome, outcome or "")
    if raw == "simulated" and outcome_label:
        return f"{raw_label} / {outcome_label}"
    return outcome_label or raw_label or "-"


def build_result_state(*, result_status: Any, summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw_status = _normalize_result_status_value(result_status)
    outcome_status = derive_completion_status(result_status=result_status, summary=summary)
    return {
        "raw_status": raw_status,
        "outcome_status": outcome_status,
        "is_simulated": raw_status == "simulated",
        "display_label": result_status_display_label(raw_status=raw_status, outcome_status=outcome_status),
    }


__all__ = [
    "build_result_state",
    "counts_from_summary",
    "derive_completion_status",
    "result_status_display_label",
]
