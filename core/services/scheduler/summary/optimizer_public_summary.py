from __future__ import annotations

from typing import Any, Dict, List, Tuple

from core.models.scheduler_degradation_messages import public_degradation_events

_PUBLIC_INPUT_CONTRACT_KEYS = (
    "degraded",
    "degradation_events",
    "degradation_counters",
    "empty_reason",
)
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


def _safe_counter_dict(value: Any) -> Dict[str, int]:
    if not isinstance(value, dict):
        return {}

    out: Dict[str, int] = {}
    for key, raw in value.items():
        normalized_key = str(key or "").strip()
        if not normalized_key:
            continue
        try:
            count = int(raw or 0)
        except Exception:
            continue
        if count:
            out[normalized_key] = count
    return out


def _project_input_contract(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    public_contract: Dict[str, Any] = {
        "degraded": bool(value.get("degraded")),
        "degradation_events": _project_degradation_event_list(value.get("degradation_events")),
        "degradation_counters": _safe_counter_dict(value.get("degradation_counters")),
    }

    empty_reason = str(value.get("empty_reason") or "").strip()
    if empty_reason:
        public_contract["empty_reason"] = empty_reason

    return {key: public_contract[key] for key in _PUBLIC_INPUT_CONTRACT_KEYS if key in public_contract}


def project_public_algo_summary(algo: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    public_algo = dict(algo or {})
    public_attempts, diagnostic_attempts = _project_attempts(public_algo.get("attempts"))
    if isinstance(public_algo.get("attempts"), list):
        public_algo["attempts"] = public_attempts
    if "input_contract" in public_algo:
        public_algo["input_contract"] = _project_input_contract(public_algo.get("input_contract"))
    if "merge_context_events" in public_algo:
        public_algo["merge_context_events"] = _project_degradation_event_list(
            public_algo.get("merge_context_events")
        )

    diagnostics: Dict[str, Any] = {}
    if diagnostic_attempts:
        diagnostics["optimizer"] = {"attempts": diagnostic_attempts}
    return public_algo, diagnostics
