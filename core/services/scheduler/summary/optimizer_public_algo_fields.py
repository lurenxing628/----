from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .optimizer_public_safety import (
    project_attempt_score,
    project_degradation_event_list,
    project_public_metrics,
    safe_attempt_text,
    safe_counter_dict,
    safe_non_negative_int,
    safe_public_text_list,
)

_PUBLIC_CONFIG_SNAPSHOT_TEXT_KEYS = (
    "sort_strategy",
    "dispatch_mode",
    "dispatch_rule",
    "algo_mode",
    "objective",
    "auto_assign_enabled",
    "freeze_window_enabled",
)
_PUBLIC_CONFIG_SNAPSHOT_INT_KEYS = (
    "time_budget_seconds",
    "freeze_window_days",
)
_PUBLIC_DOWNTIME_BOOL_KEYS = (
    "loaded_ok",
    "degraded",
    "extend_attempted",
    "downtime_meta_parse_failed",
)
_PUBLIC_DOWNTIME_INT_KEYS = (
    "load_partial_fail_count",
    "extend_partial_fail_count",
)
_PUBLIC_FREEZE_TEXT_KEYS = (
    "enabled",
    "degradation_reason",
    "freeze_state",
    "freeze_application_status",
    "freeze_degradation_public_code",
    "freeze_disabled_reason",
)
_PUBLIC_FREEZE_INT_KEYS = (
    "days",
    "frozen_op_count",
    "frozen_batch_count",
)
_PUBLIC_FREEZE_BOOL_KEYS = (
    "degraded",
    "freeze_applied",
)
_PUBLIC_RESOURCE_POOL_TEXT_KEYS = (
    "enabled",
    "degradation_reason",
)
_PUBLIC_RESOURCE_POOL_BOOL_KEYS = (
    "attempted",
    "degraded",
)
_PUBLIC_WARNING_PIPELINE_INT_KEYS = (
    "algo_warning_count",
    "summary_warning_count",
)
_PUBLIC_WARNING_PIPELINE_BOOL_KEYS = (
    "summary_merge_attempted",
    "summary_merge_failed",
)
_PUBLIC_METRICS_STATE_TEXT_KEYS = (
    "error_type",
    "message",
)
_PUBLIC_INPUT_CONTRACT_KEYS = (
    "degraded",
    "degradation_events",
    "degradation_counters",
    "empty_reason",
)


def _copy_text_fields(source: Dict[str, Any], keys: Tuple[str, ...]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key in keys:
        text = safe_attempt_text(source.get(key))
        if text:
            out[key] = text
    return out


def _copy_int_fields(source: Dict[str, Any], keys: Tuple[str, ...]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key in keys:
        number = safe_non_negative_int(source.get(key))
        if number is not None:
            out[key] = number
    return out


def _copy_bool_fields(source: Dict[str, Any], keys: Tuple[str, ...]) -> Dict[str, Any]:
    return {key: bool(source.get(key)) for key in keys if key in source}


def project_config_snapshot(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out = _copy_text_fields(value, _PUBLIC_CONFIG_SNAPSHOT_TEXT_KEYS)
    out.update(_copy_int_fields(value, _PUBLIC_CONFIG_SNAPSHOT_INT_KEYS))
    return out


def project_downtime_avoid(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out = _copy_bool_fields(value, _PUBLIC_DOWNTIME_BOOL_KEYS)
    out.update(_copy_int_fields(value, _PUBLIC_DOWNTIME_INT_KEYS))
    reason = safe_attempt_text(value.get("degradation_reason"))
    if reason:
        out["degradation_reason"] = reason
    return out


def project_freeze_window(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out = _copy_text_fields(value, _PUBLIC_FREEZE_TEXT_KEYS)
    out.update(_copy_int_fields(value, _PUBLIC_FREEZE_INT_KEYS))
    out.update(_copy_bool_fields(value, _PUBLIC_FREEZE_BOOL_KEYS))
    codes = safe_public_text_list(value.get("freeze_degradation_codes"))
    if codes:
        out["freeze_degradation_codes"] = codes
    return out


def project_resource_pool(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out = _copy_text_fields(value, _PUBLIC_RESOURCE_POOL_TEXT_KEYS)
    out.update(_copy_bool_fields(value, _PUBLIC_RESOURCE_POOL_BOOL_KEYS))
    return out


def project_warning_pipeline(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out = _copy_int_fields(value, _PUBLIC_WARNING_PIPELINE_INT_KEYS)
    out.update(_copy_bool_fields(value, _PUBLIC_WARNING_PIPELINE_BOOL_KEYS))
    error_code = safe_attempt_text(value.get("summary_merge_error"))
    if error_code:
        out["summary_merge_error"] = error_code
    elif "summary_merge_error" in value:
        out["summary_merge_error"] = None
    return out


def project_metrics_state(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out: Dict[str, Any] = {}
    if "parse_failed" in value:
        out["parse_failed"] = bool(value.get("parse_failed"))
    out.update(_copy_text_fields(value, _PUBLIC_METRICS_STATE_TEXT_KEYS))
    return out


def project_input_contract(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    public_contract: Dict[str, Any] = {
        "degraded": bool(value.get("degraded")),
        "degradation_events": project_degradation_event_list(value.get("degradation_events")),
        "degradation_counters": safe_counter_dict(value.get("degradation_counters")),
    }
    empty_reason = str(value.get("empty_reason") or "").strip()
    if empty_reason:
        public_contract["empty_reason"] = empty_reason
    return {key: public_contract[key] for key in _PUBLIC_INPUT_CONTRACT_KEYS if key in public_contract}


def project_improvement_trace(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in value:
        projected = _project_improvement_trace_item(item)
        if projected:
            out.append(projected)
    return out


def _project_improvement_trace_item(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    row: Dict[str, Any] = {}
    elapsed_ms = safe_non_negative_int(item.get("elapsed_ms"))
    if elapsed_ms is not None:
        row["elapsed_ms"] = elapsed_ms
    score = project_attempt_score(item.get("score"))
    if score:
        row["score"] = score
    metrics = project_public_metrics(item.get("metrics"))
    if metrics:
        row["metrics"] = metrics
    return row


__all__ = [
    "project_config_snapshot",
    "project_downtime_avoid",
    "project_freeze_window",
    "project_improvement_trace",
    "project_input_contract",
    "project_metrics_state",
    "project_resource_pool",
    "project_warning_pipeline",
]
