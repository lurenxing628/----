from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.models.scheduler_degradation_messages import (
    is_public_freeze_degradation_message,
    public_degradation_event_message,
)

_SUMMARY_DEGRADATION_LABELS = {
    "config_fallback": "系统已先按默认值处理的排产设置",
    "input_fallback": "系统已先按默认值处理的排产数据",
    "freeze_window_degraded": "冻结窗口资料不完整",
    "downtime_avoid_degraded": "停机时间资料不完整",
    "resource_pool_degraded": "资源池资料不完整",
    "invalid_due_date": "交期数据无法使用",
    "legacy_external_days_defaulted": "部分外协周期先按 1 天计算",
    "ortools_warmstart_failed": "优化起点不可用",
    "template_missing": "组合合同模板资料不完整",
    "external_group_missing": "组合并外协组资料不完整",
    "merge_context_degraded": "组合并资料不完整",
    "summary_merge_failed": "部分排产提示没有整理完整，请到排产历史或日志查看详情",
    "optimizer_metrics_invalid": "优化指标记录异常",
    "fallback_count_parse_failed": "排产降级统计记录异常",
    "summary_count_parse_failed": "排产摘要数量记录异常",
    "graph_enhancement_degraded": "工序图增强已退回普通排法",
    "dispatch_failure_details": "工序失败和跳过明细",
}


def _positive_count_state(value: Any) -> Tuple[int, bool]:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return 1, False
    if isinstance(value, bool):
        return 1, True
    try:
        if isinstance(value, int):
            parsed = value
        else:
            text = str(value).strip()
            sign = text[0] if text and text[0] in ("+", "-") else ""
            digits = text[1:] if sign else text
            if not digits.isdigit():
                return 1, True
            parsed = int(text)
    except (TypeError, ValueError, OverflowError):
        return 1, True
    return (parsed, False) if parsed >= 1 else (1, True)


def _degradation_label_for(*, code: str, message: str) -> str:
    label = _SUMMARY_DEGRADATION_LABELS.get(code)
    if label:
        return label
    return "排产摘要里有需要注意的提示"


def _public_message_for_event(*, code: str, message: str) -> str:
    normalized_message = str(message or "").strip()
    if code == "freeze_window_degraded" and is_public_freeze_degradation_message(normalized_message):
        return normalized_message
    return public_degradation_event_message(code) if code else ""


def format_degradation_detail(label: Any, count: Any, *, count_parse_failed: bool = False) -> str:
    normalized_label = str(label or "").strip()
    if not normalized_label:
        return ""
    normalized_count, failed = _positive_count_state(count)
    if count_parse_failed or failed:
        return f"{normalized_label}（数量记录异常）"
    return f"{normalized_label}\uff08{normalized_count}\uff09" if normalized_count > 1 else normalized_label


def degradation_reason_key(*, code: Any, label: Any, count: Any) -> Tuple[str, str, int]:
    normalized_count, failed = _positive_count_state(count)
    return (
        str(code or "").strip(),
        str(label or "").strip(),
        0 if failed else normalized_count,
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
    if outcome_status not in {"success", "partial", "failed", "unknown"}:
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
            "success": "本次模拟排产已完成，但有些数据或设置需要复核，系统先按能确认的内容继续。",
            "partial": "本次模拟排产部分完成，并且有些数据或设置需要复核，系统先按能确认的内容继续。",
            "failed": "本次模拟排产失败，并且有些数据或设置需要复核，系统先按能确认的内容继续。",
            "unknown": "本次模拟排产结果有问题，需要检查，有些数据或设置需要复核，系统先按能确认的内容继续。",
        }[status]
    return {
        "success": "本次排产已成功，但有些数据或设置需要复核，系统先按能确认的内容继续。",
        "partial": "本次排产部分完成，并且有些数据或设置需要复核，系统先按能确认的内容继续。",
        "failed": "本次排产失败，并且有些数据或设置需要复核，系统先按能确认的内容继续。",
        "unknown": "本次排产结果有问题，需要检查，有些数据或设置需要复核，系统先按能确认的内容继续。",
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
    items_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        code = str(event.get("code") or "").strip()
        raw_message = str(event.get("message") or "").strip()
        message = _public_message_for_event(code=code, message=raw_message)
        if not code and not message:
            continue
        dedupe_key = (code, message)
        count, count_parse_failed = _positive_count_state(event.get("count"))
        existing = items_by_key.get(dedupe_key)
        if existing is not None:
            if count_parse_failed:
                existing["count_parse_failed"] = True
            else:
                existing["count"] = int(existing.get("count") or 0) + count
            continue
        items_by_key[dedupe_key] = {
            "code": code,
            "label": _degradation_label_for(code=code, message=message),
            "message": message,
            "count": count,
            "count_parse_failed": count_parse_failed,
        }
        items.append(items_by_key[dedupe_key])
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
        detail = format_degradation_detail(
            label,
            item.get("count"),
            count_parse_failed=bool(item.get("count_parse_failed")),
        )
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
