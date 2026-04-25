from __future__ import annotations

from typing import Any, Dict, List, Tuple

_PUBLIC_ATTEMPT_KEYS = {
    "strategy",
    "dispatch_mode",
    "dispatch_rule",
    "score",
    "failed_ops",
    "metrics",
}

_DIAGNOSTIC_ATTEMPT_KEYS = {
    "tag",
    "source",
    "origin",
    "used_params",
    "algo_stats",
}


def _source_label(attempt: Dict[str, Any]) -> str:
    raw_tag = str(attempt.get("tag") or "").strip().lower()
    if raw_tag.startswith("start:"):
        return "多起点方案"
    if raw_tag.startswith("ortools:"):
        return "OR-Tools 起点"
    if raw_tag.startswith("local:"):
        return "局部搜索"
    return ""


def _project_attempts(attempts: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not isinstance(attempts, list):
        return [], []

    public_attempts: List[Dict[str, Any]] = []
    diagnostic_attempts: List[Dict[str, Any]] = []
    for attempt in attempts:
        if not isinstance(attempt, dict):
            continue
        public_attempt = {key: attempt[key] for key in _PUBLIC_ATTEMPT_KEYS if key in attempt}
        source_label = _source_label(attempt)
        if source_label:
            public_attempt["source_label"] = source_label
        public_attempts.append(public_attempt)
        diagnostics = {key: attempt[key] for key in _DIAGNOSTIC_ATTEMPT_KEYS if key in attempt}
        if diagnostics:
            diagnostic_attempts.append(diagnostics)
    return public_attempts, diagnostic_attempts


def project_public_algo_summary(algo: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    public_algo = dict(algo or {})
    public_attempts, diagnostic_attempts = _project_attempts(public_algo.get("attempts"))
    if isinstance(public_algo.get("attempts"), list):
        public_algo["attempts"] = public_attempts

    diagnostics: Dict[str, Any] = {}
    if diagnostic_attempts:
        diagnostics["optimizer"] = {"attempts": diagnostic_attempts}
    return public_algo, diagnostics
