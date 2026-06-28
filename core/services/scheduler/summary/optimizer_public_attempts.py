from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .optimizer_public_safety import (
    project_attempt_failed_ops,
    project_attempt_metrics,
    project_attempt_score,
    safe_attempt_text,
)

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
    score = project_attempt_score(attempt.get("score"))
    if score:
        public_attempt["score"] = score
    failed_ops = project_attempt_failed_ops(attempt.get("failed_ops"))
    if failed_ops is not None:
        public_attempt["failed_ops"] = failed_ops
    metrics = project_attempt_metrics(attempt.get("metrics"))
    if metrics:
        public_attempt["metrics"] = metrics
    source_label = _source_label(attempt)
    if source_label:
        public_attempt["source_label"] = source_label
    return public_attempt


def _source_label(attempt: Dict[str, Any]) -> str:
    raw_tag = str(attempt.get("tag") or "").strip().lower()
    if raw_tag.startswith("start:"):
        return "多起点方案"
    if raw_tag.startswith("ortools:"):
        return "深度优化起点"
    if raw_tag.startswith("grasp:"):
        return "GRASP（贪心随机自适应搜索）候选起点"
    if raw_tag.startswith("ig:"):
        return "迭代贪心候选起点"
    if raw_tag.startswith("local:"):
        return "局部搜索"
    return ""


__all__ = ["project_attempts"]
