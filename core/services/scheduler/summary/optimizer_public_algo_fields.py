from __future__ import annotations

from typing import Any, Dict, List, Tuple

from core.services.scheduler.contracts.optimizer_public_safety import (
    project_public_metrics,
    safe_attempt_text,
    safe_non_negative_int,
)

from .optimizer_public_attempts import project_attempt_evaluation

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
_PUBLIC_DOWNTIME_BOOL_KEYS = ("extend_attempted",)
_PUBLIC_FREEZE_TEXT_KEYS = (
    "enabled",
    "freeze_state",
    "freeze_application_status",
    "freeze_disabled_reason",
)
_PUBLIC_FREEZE_INT_KEYS = (
    "days",
    "frozen_op_count",
    "frozen_batch_count",
)
_PUBLIC_FREEZE_BOOL_KEYS = ("freeze_applied",)
_PUBLIC_RESOURCE_POOL_TEXT_KEYS = ("enabled",)
_PUBLIC_RESOURCE_POOL_BOOL_KEYS = ("attempted",)


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
    return _copy_bool_fields(value, _PUBLIC_DOWNTIME_BOOL_KEYS)


def project_freeze_window(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out = _copy_text_fields(value, _PUBLIC_FREEZE_TEXT_KEYS)
    out.update(_copy_int_fields(value, _PUBLIC_FREEZE_INT_KEYS))
    out.update(_copy_bool_fields(value, _PUBLIC_FREEZE_BOOL_KEYS))
    return out


def project_resource_pool(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out = _copy_text_fields(value, _PUBLIC_RESOURCE_POOL_TEXT_KEYS)
    out.update(_copy_bool_fields(value, _PUBLIC_RESOURCE_POOL_BOOL_KEYS))
    return out


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
    metrics = project_public_metrics(item.get("metrics"))
    score, _primary = project_attempt_evaluation(item.get("score"), None, metrics.get("completion") or {})
    if score:
        row["score"] = score
    if metrics:
        row["metrics"] = metrics
    return row


__all__ = [
    "project_config_snapshot",
    "project_downtime_avoid",
    "project_freeze_window",
    "project_improvement_trace",
    "project_resource_pool",
]
