from __future__ import annotations

from typing import Any, Dict, List, Tuple

from core.services.scheduler.contracts.optimizer_public_safety import (
    COMPARISON_METRIC_KEYS,
    project_attempt_metrics,
    public_int,
    safe_attempt_text,
    safe_non_negative_int,
)
from core.shared.strict_parse import is_exact_finite_number

DIAGNOSTIC_ATTEMPT_KEYS = {
    "tag",
    "source",
    "origin",
    "used_params",
    "algo_stats",
}
REJECTED_DIAGNOSTIC_ATTEMPT_KEYS = DIAGNOSTIC_ATTEMPT_KEYS | {
    "strategy",
    "dispatch_mode",
    "dispatch_rule",
}
_COMPLETION_KEYS = ("expected_operation_count", "missing_operation_count", "unexpected_result_count", "complete_batch_count", "incomplete_batch_count")
_SOURCE_LABELS = (
    ("graph_ready_base", "按基础规则试排"), ("graph_ready_weight_grid", "按不同优先侧重试排"),
    ("graph_ready_local_search", "局部调整排法"), ("graph_ready_v2_generated", "按规则生成排法"),
    ("graph_ready_v2_repaired", "局部调整排法"), ("graph_ready_v2_iterated_greedy", "继续调整工序顺序"),
    ("multi_start", "多起点方案"), ("ortools_warmstart", "深度优化起点"),
    ("grasp", "GRASP（贪心随机自适应搜索）候选起点"), ("ig", "迭代贪心候选起点"), ("local_search", "局部搜索"),
)
_TAG_ORIGINS = (("start:", "multi_start"), ("ortools:", "ortools_warmstart"), ("grasp:", "grasp"), ("ig:", "ig"), ("local:", "local_search"))


def _finite(value: Any) -> Any:
    return value if is_exact_finite_number(value) else None


def project_attempt_evaluation(score: Any, primary: Any, completion: Dict[str, Any]) -> Tuple[List[Any], Any]:
    """Preserve score positions and distinguish unknown ordering values from business values."""
    values = [_finite(item) for item in score] if isinstance(score, (list, tuple)) else []
    if completion.get("objective_scope") == "unknown" or completion.get("objective_score_policy") == "unknown_all_components":
        return ([values[0]] + [None] * (len(values) - 1) if values else []), None
    return values, _finite(primary)


def _project_comparison(value: Any) -> Any:
    if not isinstance(value, dict):
        return None
    scope = safe_attempt_text(value.get("reference_scope")) or None
    reference_score = value.get("reference_score")
    score, _primary = project_attempt_evaluation(reference_score, None, {"objective_scope": scope})
    metrics, completion, deltas = (value.get(key) for key in ("reference_metrics", "reference_completion", "metric_deltas"))
    return {**{key: safe_attempt_text(value.get(key)) or None for key in ("kind", "state", "objective_name", "objective_scope", "reference_scope")},
        "reference_score": score if isinstance(reference_score, (list, tuple)) else None,
        "reference_metrics": {key: _finite(metrics.get(key)) for key in COMPARISON_METRIC_KEYS} if isinstance(metrics, dict) else None,
        "reference_completion": {key: safe_non_negative_int(completion.get(key)) for key in _COMPLETION_KEYS} if isinstance(completion, dict) else None,
        "metric_deltas": {key: _finite(deltas.get(key)) for key in COMPARISON_METRIC_KEYS} if isinstance(deltas, dict) else None}


def _source_origin(attempt: Dict[str, Any]) -> str:
    origin = safe_attempt_text(attempt.get("candidate_origin"))
    if origin:
        return origin
    source = safe_attempt_text(attempt.get("source"))
    if source in {kind for kind, _label in _SOURCE_LABELS}:
        return source
    tag = str(attempt.get("tag") or "").strip().lower()
    return next((kind for prefix, kind in _TAG_ORIGINS if tag.startswith(prefix)), "")


def project_attempts(attempts: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not isinstance(attempts, list):
        return [], []

    public_attempts: List[Dict[str, Any]] = []
    diagnostic_attempts: List[Dict[str, Any]] = []
    for attempt in attempts:
        if not isinstance(attempt, dict):
            continue
        if _is_candidate_rejected_attempt(attempt):
            diagnostic_keys = REJECTED_DIAGNOSTIC_ATTEMPT_KEYS
        else:
            public_attempts.append(_project_public_attempt(attempt))
            diagnostic_keys = DIAGNOSTIC_ATTEMPT_KEYS
        diagnostics = {key: attempt[key] for key in diagnostic_keys if key in attempt}
        if diagnostics:
            diagnostic_attempts.append(diagnostics)
    return public_attempts, diagnostic_attempts


def _is_candidate_rejected_attempt(attempt: Dict[str, Any]) -> bool:
    return attempt.get("source") == "candidate_rejected"


def _project_public_attempt(attempt: Dict[str, Any]) -> Dict[str, Any]:
    public_attempt: Dict[str, Any] = {}
    for key in ("strategy", "dispatch_mode", "dispatch_rule", "candidate_status"):
        text = safe_attempt_text(attempt.get(key))
        if text:
            public_attempt[key] = text
    raw_metrics = attempt.get("metrics")
    raw_completion = raw_metrics.get("completion") if isinstance(raw_metrics, dict) else None
    score, _primary = project_attempt_evaluation(attempt.get("score"), None, raw_completion if isinstance(raw_completion, dict) else {})
    if score:
        public_attempt["score"] = score
    failed_ops = public_int(attempt.get("failed_ops"))
    if failed_ops is not None:
        public_attempt["failed_ops"] = failed_ops
    metrics = project_attempt_metrics(attempt.get("metrics"))
    if metrics:
        public_attempt["metrics"] = metrics
    origin = _source_origin(attempt)
    source_label = _source_label(attempt, origin=origin)
    if source_label:
        public_attempt["source_label"] = source_label
    if origin:
        public_attempt["candidate_origin"] = origin
    profile = safe_attempt_text(attempt.get("weight_profile_slug"))
    if profile:
        public_attempt["weight_profile_slug"] = profile
    for key in ("elapsed_ms", "event_index"):
        if key in attempt:
            value = safe_non_negative_int(attempt[key]) if key == "event_index" else _finite(attempt[key])
            public_attempt[key] = value if value is None or value >= 0 else None
    for key in ("accepted", "verified", "strict_improved"):
        if key in attempt:
            public_attempt[key] = attempt[key] if type(attempt[key]) is bool else None
    if "comparison" in attempt:
        public_attempt["comparison"] = _project_comparison(attempt["comparison"])
    return public_attempt


def _source_label(attempt: Dict[str, Any], *, origin: str) -> str:
    label = next((label for key, label in _SOURCE_LABELS if key == origin), "")
    if label:
        return label
    raw_tag = str(attempt.get("tag") or "").strip().lower()
    if raw_tag.startswith("graph_ready:"):
        return "GraphReady 候选"
    # Public attempts have no raw tag when the ordinary summary is projected again.
    return safe_attempt_text(attempt.get("source_label"))


__all__ = ["project_attempts", "project_attempt_evaluation", "COMPARISON_METRIC_KEYS"]
