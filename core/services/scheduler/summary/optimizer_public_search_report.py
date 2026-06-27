from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .optimizer_public_safety import (
    project_attempt_score,
    safe_attempt_text,
    safe_bool,
    safe_counter_dict,
    safe_non_negative_int,
)

_PUBLIC_TEXT_KEYS = (
    "status",
    "stop_reason",
    "algorithm_profile",
    "best_origin",
    "objective_name",
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
    "rejected_candidates",
)
_PUBLIC_BOOL_KEYS = ("best_fingerprint_changed", "improved")
_DIAGNOSTIC_KEYS = (
    "initial_fingerprint",
    "best_fingerprint",
    "attempts",
    "improvement_trace",
    "public_attempt_summary",
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
    return {key: safe_bool(source.get(key)) for key in _PUBLIC_BOOL_KEYS if key in source}


def _project_skipped_phases(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        phase = safe_attempt_text(item.get("phase"))
        reason = safe_attempt_text(item.get("reason"))
        if not phase and not reason:
            continue
        row: Dict[str, Any] = {}
        if phase:
            row["phase"] = phase
        if reason:
            row["reason"] = reason
        out.append(row)
    return out


def _project_attempt_summary(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        row: Dict[str, Any] = {}
        for key in ("origin", "status", "strategy", "dispatch_mode", "dispatch_rule"):
            text = safe_attempt_text(item.get(key))
            if text:
                row[key] = text
        score = project_attempt_score(item.get("score"))
        if score:
            row["score"] = score
        failed_ops = safe_non_negative_int(item.get("failed_ops"))
        if failed_ops is not None:
            row["failed_ops"] = failed_ops
        if row:
            out.append(row)
    return out


def project_search_report(value: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if not isinstance(value, dict):
        return {}, {}

    public = _copy_text_fields(value)
    public.update(_copy_int_fields(value))
    public.update(_copy_bool_fields(value))

    score = project_attempt_score(value.get("best_score"))
    if score:
        public["best_score"] = score

    rejection_summary = safe_counter_dict(value.get("rejection_summary"))
    if rejection_summary:
        public["rejection_summary"] = rejection_summary

    skipped_phases = _project_skipped_phases(value.get("skipped_phases"))
    if skipped_phases:
        public["skipped_phases"] = skipped_phases

    attempt_summary = _project_attempt_summary(value.get("public_attempt_summary"))
    if attempt_summary:
        public["public_attempt_summary"] = attempt_summary

    diagnostics = {key: value[key] for key in _DIAGNOSTIC_KEYS if key in value and value[key]}
    return public, diagnostics


__all__ = ["project_search_report"]
