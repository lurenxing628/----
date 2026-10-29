from __future__ import annotations

from typing import Any, Dict, List

from core.shared.strict_parse import finite_float, is_int, is_number

COMPARISON_METRIC_KEYS = (
    "failed_ops",
    "overdue_count",
    "weighted_tardiness_hours",
    "total_tardiness_hours",
    "makespan_hours",
    "changeover_count",
)
PUBLIC_ATTEMPT_METRIC_KEYS = {key for key in COMPARISON_METRIC_KEYS if key != "failed_ops"}
_COMPLETION_COUNT_KEYS = (
    "expected_operation_count", "missing_operation_count", "unexpected_result_count",
    "complete_batch_count", "incomplete_batch_count", "partial_batch_count", "failure_detail_count",
)
_COMPLETION_ALLOWED_LABELS = {
    "contract": ("expected_operations_complete_only_v1",),
    "objective_score_policy": ("original", "unknown_all_components", "completed_batches_only"),
    "objective_scope": ("all_batches", "completed_batches_only", "unknown"),
    "due_metrics_scope": ("completed_batches_only",),
    "resource_metrics_scope": ("scheduled_results_only",),
}


def safe_metric_key(value: Any) -> str:
    if value is None or isinstance(value, (bool, dict, list, tuple, set)):
        return ""
    return str(value).strip().replace("\r", " ").replace("\n", " ")


def public_int(value: Any) -> Any:
    return value if is_int(value) else None


def safe_non_negative_int(value: Any) -> Any:
    if is_int(value):
        return value if value >= 0 else None
    if isinstance(value, str) and value.strip().isdecimal():
        return int(value.strip())
    return None


def safe_attempt_text(value: Any) -> str:
    if value is None or isinstance(value, (bool, dict, list, tuple, set)):
        return ""
    return str(value).strip().replace("\r", " ").replace("\n", " ")


def safe_public_text_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        text = safe_attempt_text(item)
        if text and text not in out:
            out.append(text)
    return out


def project_attempt_score(value: Any) -> List[Any]:
    return [item for item in value if is_number(item)] if isinstance(value, (list, tuple)) else []


def project_attempt_metrics(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out = {key: value[key] for key in PUBLIC_ATTEMPT_METRIC_KEYS if is_number(value.get(key))}
    _add_metric_completion(out, value)
    return out


def project_public_metrics(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out = {k: v for raw_k, v in value.items() if (k := safe_attempt_text(raw_k)) and is_number(v)}
    _add_metric_completion(out, value)
    return out


def _add_metric_completion(out: Dict[str, Any], metrics: Dict[str, Any]) -> None:
    raw = metrics.get("completion")
    if not isinstance(raw, dict):
        return
    completion: Dict[str, Any] = {}
    if isinstance(raw.get("objective_defined"), bool):
        completion["objective_defined"] = raw["objective_defined"]
    for key in _COMPLETION_COUNT_KEYS:
        count = public_int(raw.get(key))
        if count is not None and count >= 0:
            completion[key] = count
    for key, labels in _COMPLETION_ALLOWED_LABELS.items():
        if raw.get(key) in labels:
            completion[key] = raw[key]
    raw_weight = raw.get("incomplete_work_weight")
    weight = finite_float(raw_weight) if is_number(raw_weight) else None
    if weight is not None and weight >= 0:
        completion["incomplete_work_weight"] = weight
    if completion:
        out["completion"] = completion


def public_counter_dict(counts: Dict[str, int]) -> Dict[str, int]:
    """Public view of an internal counter bucket (written only by increment_counter / merge_algo_stats)."""
    return {key: count for key, count in counts.items() if count and safe_attempt_text(key)}


__all__ = [
    "COMPARISON_METRIC_KEYS",
    "PUBLIC_ATTEMPT_METRIC_KEYS",
    "project_attempt_metrics",
    "project_attempt_score",
    "project_public_metrics",
    "safe_attempt_text",
    "public_counter_dict",
    "public_int",
    "safe_metric_key",
    "safe_non_negative_int",
    "safe_public_text_list",
]
