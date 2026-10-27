from __future__ import annotations

from typing import Any, Dict, List, Tuple

from core.services.scheduler.contracts.optimizer_public_safety import (
    project_public_metrics,
    safe_non_negative_int,
)

from .optimizer_public_attempts import project_attempt_evaluation

_PUBLIC_CONFIG_SNAPSHOT_KEYS = (
    "sort_strategy",
    "dispatch_mode",
    "dispatch_rule",
    "algo_mode",
    "objective",
    "auto_assign_enabled",
    "freeze_window_enabled",
    "time_budget_seconds",
    "freeze_window_days",
)
_PUBLIC_DOWNTIME_KEYS = ("extend_attempted",)
_PUBLIC_FREEZE_KEYS = (
    "enabled",
    "freeze_state",
    "freeze_application_status",
    "freeze_disabled_reason",
    "days",
    "frozen_op_count",
    "frozen_batch_count",
    "freeze_applied",
)
_PUBLIC_RESOURCE_POOL_KEYS = ("enabled", "attempted")


def _project_fields(source: Any, keys: Tuple[str, ...]) -> Dict[str, Any]:
    if not isinstance(source, dict):
        return {}
    return {key: source[key] for key in keys if source.get(key) is not None and source[key] != ""}


def project_config_snapshot(value: Any) -> Dict[str, Any]:
    return _project_fields(value, _PUBLIC_CONFIG_SNAPSHOT_KEYS)


def project_downtime_avoid(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {key: bool(value[key]) for key in _PUBLIC_DOWNTIME_KEYS if key in value}


def project_freeze_window(value: Any) -> Dict[str, Any]:
    return _project_fields(value, _PUBLIC_FREEZE_KEYS)


def project_resource_pool(value: Any) -> Dict[str, Any]:
    return _project_fields(value, _PUBLIC_RESOURCE_POOL_KEYS)


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
