from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

_SUMMARY_DEGRADATION_LABELS = {
    "config_fallback": "\u914d\u7f6e\u5feb\u7167\u5df2\u6309\u517c\u5bb9\u8def\u5f84\u6807\u51c6\u5316",
    "input_fallback": "\u8f93\u5165\u6784\u5efa\u5df2\u6309\u517c\u5bb9\u8def\u5f84\u7ee7\u7eed\u751f\u6210",
    "freeze_window_degraded": "\u51bb\u7ed3\u7a97\u53e3\u7ea6\u675f\u5df2\u964d\u7ea7",
    "downtime_avoid_degraded": "\u505c\u673a\u907f\u8ba9\u7ea6\u675f\u5df2\u964d\u7ea7",
    "resource_pool_degraded": "\u8d44\u6e90\u6c60\u6784\u5efa\u5df2\u964d\u7ea7",
    "invalid_due_date": "\u4ea4\u671f\u6570\u636e\u5df2\u964d\u7ea7",
    "legacy_external_days_defaulted": "\u5386\u53f2\u5916\u534f\u5468\u671f\u5df2\u517c\u5bb9\u56de\u9000",
    "ortools_warmstart_failed": "\u9884\u70ed\u5df2\u964d\u7ea7",
    "template_missing": "\u7ec4\u5408\u5408\u540c\u6a21\u677f\u4e0a\u4e0b\u6587\u5df2\u964d\u7ea7",
    "external_group_missing": "\u7ec4\u5408\u5e76\u5916\u90e8\u7ec4\u4e0a\u4e0b\u6587\u5df2\u964d\u7ea7",
    "merge_context_degraded": "\u7ec4\u5408\u5e76\u8bed\u4e49\u5df2\u964d\u7ea7",
    "summary_merge_failed": "\u6458\u8981\u544a\u8b66\u5408\u5e76\u5df2\u964d\u7ea7",
}


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value or 0)
    except Exception:
        return int(default)


def _degradation_label_for(*, code: str, message: str) -> str:
    label = _SUMMARY_DEGRADATION_LABELS.get(code)
    if label:
        return label
    if message:
        return message
    return "\u6392\u4ea7\u6458\u8981\u5b58\u5728\u53ef\u89c1\u9000\u5316"


def format_degradation_detail(label: Any, count: Any) -> str:
    normalized_label = str(label or "").strip()
    if not normalized_label:
        return ""
    normalized_count = max(1, _safe_int(count, default=1))
    return f"{normalized_label}\uff08{normalized_count}\uff09" if normalized_count > 1 else normalized_label


def degradation_reason_key(*, code: Any, label: Any, count: Any) -> Tuple[str, str, int]:
    return (
        str(code or "").strip(),
        str(label or "").strip(),
        max(1, _safe_int(count, default=1)),
    )


def degradation_display_key(*, code: Any, label: Any, count: Any, message: Any) -> Tuple[Tuple[str, str, int], str]:
    return (
        degradation_reason_key(code=code, label=label, count=count),
        str(message or "").strip(),
    )


def _normalize_result_state(
    *,
    result_state: Optional[Dict[str, Any]],
    completion_status: str,
) -> Dict[str, Any]:
    raw_status = ""
    outcome_status = str(completion_status or "").strip().lower()
    is_simulated = False
    if isinstance(result_state, dict):
        raw_status = str(result_state.get("raw_status") or "").strip().lower()
        outcome_status = str(result_state.get("outcome_status") or outcome_status).strip().lower()
        is_simulated = bool(result_state.get("is_simulated")) or raw_status == "simulated"
    if outcome_status not in {"success", "partial", "failed"}:
        outcome_status = "success"
    return {
        "raw_status": raw_status,
        "outcome_status": outcome_status,
        "is_simulated": is_simulated,
    }


def _primary_degradation_message(*, result_state: Dict[str, Any]) -> str:
    status = str(result_state.get("outcome_status") or "success").strip().lower()
    if bool(result_state.get("is_simulated")):
        return {
            "success": "本次模拟排产已完成，但存在内部降级/兼容修补。",
            "partial": "本次模拟排产部分完成，且存在内部降级/兼容修补。",
            "failed": "本次模拟排产失败，且存在内部降级/兼容修补。",
        }[status]
    return {
        "success": "本次排产已成功，但存在内部降级/兼容修补。",
        "partial": "本次排产部分完成，且存在内部降级/兼容修补。",
        "failed": "本次排产失败，且存在内部降级/兼容修补。",
    }[status]


def _normalize_summary_degradation_events(selected_summary: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(selected_summary, dict):
        return []

    events = selected_summary.get("degradation_events")
    if not isinstance(events, list):
        degraded_causes = selected_summary.get("degraded_causes")
        if not isinstance(degraded_causes, list):
            return []
        events = [{"code": str(code or "").strip(), "message": "", "count": 1} for code in degraded_causes]

    items: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str]] = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        code = str(event.get("code") or "").strip()
        message = str(event.get("message") or "").strip()
        if not code and not message:
            continue
        dedupe_key = (code, message)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        items.append(
            {
                "code": code,
                "label": _degradation_label_for(code=code, message=message),
                "message": message,
                "count": max(1, _safe_int(event.get("count"), default=1)),
            }
        )
    return items


def build_summary_degradation_messages(selected_summary: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return _normalize_summary_degradation_events(selected_summary)


def build_primary_degradation(
    selected_summary: Optional[Dict[str, Any]],
    *,
    result_state: Optional[Dict[str, Any]] = None,
    completion_status: str = "",
) -> Optional[Dict[str, Any]]:
    items = _normalize_summary_degradation_events(selected_summary)
    if not items:
        return None

    normalized_result_state = _normalize_result_state(
        result_state=result_state,
        completion_status=completion_status,
    )
    primary_message = _primary_degradation_message(result_state=normalized_result_state)

    details: List[str] = []
    detail_keys: List[Tuple[str, str, int]] = []
    for item in items:
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        detail = format_degradation_detail(label, item.get("count"))
        if detail not in details:
            details.append(detail)
        reason_key = degradation_reason_key(code=item.get("code"), label=label, count=item.get("count"))
        if reason_key not in detail_keys:
            detail_keys.append(reason_key)

    return {
        "message": primary_message,
        "details": details,
        "detail_keys": detail_keys,
    }


__all__ = [
    "build_primary_degradation",
    "build_summary_degradation_messages",
    "degradation_display_key",
    "degradation_reason_key",
    "format_degradation_detail",
]
