from __future__ import annotations

from typing import Any, Dict, Tuple

from .optimizer_public_safety import (
    project_attempt_score,
    safe_attempt_text,
    safe_non_negative_int,
)

_PUBLIC_TEXT_KEYS = (
    "status",
    "stop_reason",
    "algorithm_profile",
    "best_origin",
    "objective_name",
    "distinct_fingerprint_scope",
    "distinct_fingerprint_description",
    "distinct_output_scope",
    "distinct_output_description",
    "message",
)
_PUBLIC_INT_KEYS = (
    "schema_version",
    "seed",
    "time_budget_seconds",
    "runtime_ms",
    "iterations",
    "evaluated_candidates",
    "distinct_candidates",
    "accepted_candidates",
    "accepted_distinct_candidates",
    "current_accepted_candidates",
    "best_improved_candidates",
    "rejected_candidates",
)
_PUBLIC_BOOL_KEYS = ("best_fingerprint_changed", "best_output_changed", "improved")
_DIAGNOSTIC_KEYS = (
    "initial_fingerprint",
    "best_fingerprint",
    "initial_candidate_fingerprint",
    "best_candidate_fingerprint",
    "fingerprint_events",
    "initial_candidate_id",
    "best_candidate_id",
    "initial_candidate_identity",
    "best_candidate_identity",
    "candidate_events",
    "improvement_conditions",
    "neighborhood_moves",
    "acceptance_events",
    "vns_events",
    "attempts",
    "improvement_trace",
)


def _copy_text_fields(source: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key in _PUBLIC_TEXT_KEYS:
        text = safe_attempt_text(source.get(key))
        if text:
            out[key] = text
    return out


def _copy_int_fields(source: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key in _PUBLIC_INT_KEYS:
        number = safe_non_negative_int(source.get(key))
        if number is not None:
            out[key] = number
    return out


def _copy_bool_fields(source: Dict[str, Any]) -> Dict[str, Any]:
    return {key: bool(source.get(key)) for key in _PUBLIC_BOOL_KEYS if key in source}


def project_search_report(value: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if not isinstance(value, dict):
        return {}, {}

    public = _copy_text_fields(value)
    public.update(_copy_int_fields(value))
    public.update(_copy_bool_fields(value))

    score = project_attempt_score(value.get("best_score"))
    if score:
        public["best_score"] = score

    diagnostics = {key: value[key] for key in _DIAGNOSTIC_KEYS if key in value and value[key]}
    return public, diagnostics


__all__ = ["project_search_report"]
