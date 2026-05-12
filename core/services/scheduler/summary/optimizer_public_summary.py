from __future__ import annotations

from typing import Any, Dict, List, Tuple

from core.models.scheduler_degradation_messages import public_degradation_events

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
_REJECTED_DIAGNOSTIC_ATTEMPT_KEYS = _DIAGNOSTIC_ATTEMPT_KEYS | {
    "strategy",
    "dispatch_mode",
    "dispatch_rule",
}


def _is_candidate_rejected_attempt(attempt: Dict[str, Any]) -> bool:
    return attempt.get("source") == "candidate_rejected"


def _source_label(attempt: Dict[str, Any]) -> str:
    raw_tag = str(attempt.get("tag") or "").strip().lower()
    if raw_tag.startswith("start:"):
        return "多起点方案"
    if raw_tag.startswith("ortools:"):
        return "深度优化起点"
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
        if not _is_candidate_rejected_attempt(attempt):
            public_attempt = {key: attempt[key] for key in _PUBLIC_ATTEMPT_KEYS if key in attempt}
            source_label = _source_label(attempt)
            if source_label:
                public_attempt["source_label"] = source_label
            public_attempts.append(public_attempt)
            diagnostic_keys = _DIAGNOSTIC_ATTEMPT_KEYS
        else:
            diagnostic_keys = _REJECTED_DIAGNOSTIC_ATTEMPT_KEYS
        diagnostics = {key: attempt[key] for key in diagnostic_keys if key in attempt}
        if diagnostics:
            diagnostic_attempts.append(diagnostics)
    return public_attempts, diagnostic_attempts


def _project_degradation_event_list(events: Any) -> List[Dict[str, Any]]:
    if not isinstance(events, list):
        return []
    return public_degradation_events(events)


def _project_input_contract(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    public_contract = dict(value)
    if "degradation_events" in public_contract:
        public_contract["degradation_events"] = _project_degradation_event_list(
            public_contract.get("degradation_events")
        )
    return public_contract


def project_public_algo_summary(algo: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    public_algo = dict(algo or {})
    public_attempts, diagnostic_attempts = _project_attempts(public_algo.get("attempts"))
    if isinstance(public_algo.get("attempts"), list):
        public_algo["attempts"] = public_attempts
    if isinstance(public_algo.get("input_contract"), dict):
        public_algo["input_contract"] = _project_input_contract(public_algo.get("input_contract"))
    if "merge_context_events" in public_algo:
        public_algo["merge_context_events"] = _project_degradation_event_list(
            public_algo.get("merge_context_events")
        )

    diagnostics: Dict[str, Any] = {}
    if diagnostic_attempts:
        diagnostics["optimizer"] = {"attempts": diagnostic_attempts}
    return public_algo, diagnostics
