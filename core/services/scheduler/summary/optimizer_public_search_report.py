from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .optimizer_public_safety import (
    project_attempt_score,
    safe_attempt_text,
    safe_bool,
    safe_counter_dict,
    safe_non_negative_int,
    safe_public_text_list,
)

_PUBLIC_TEXT_KEYS = (
    "status",
    "stop_reason",
    "algorithm_profile",
    "best_origin",
    "objective_name",
    "distinct_fingerprint_scope",
    "distinct_fingerprint_description",
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
_PUBLIC_BOOL_KEYS = ("best_fingerprint_changed", "improved")
_DIAGNOSTIC_KEYS = (
    "initial_fingerprint",
    "best_fingerprint",
    "initial_candidate_fingerprint",
    "best_candidate_fingerprint",
    "fingerprint_events",
    "improvement_conditions",
    "neighborhood_moves",
    "acceptance_events",
    "vns_events",
    "attempts",
    "improvement_trace",
    "public_attempt_summary",
)

# candidate profile（roadmap item 4）public 白名单：只投安全摘要字段。
# 与 roadmap 4.8 一致：raw config / 内部调试细节只进 diagnostics，不进普通页面。
_PROFILE_PUBLIC_TEXT_KEYS = ("profile", "acceptance", "system_limit_reason", "message")
_PROFILE_PUBLIC_INT_KEYS = (
    "seed",
    "configured_time_budget_seconds",
    "effective_time_budget_seconds",
    "configured_max_iterations",
    "effective_max_iterations",
)
_PROFILE_PUBLIC_BOOL_KEYS = ("enabled", "system_limit_applied")
_PROFILE_PUBLIC_LIST_KEYS = ("candidate_strategy_families", "neighborhoods")
_PROFILE_DIAGNOSTIC_TEXT_KEYS = (
    "seed_source",
    "iteration_limit_source",
    "repair",
    "candidate_strategy_family",
    "dispatch_mode",
    "dispatch_rule",
    "validation_status",
)
_PROFILE_DIAGNOSTIC_INT_KEYS = ("schema_version", "restart_after_iterations")
_PROFILE_DIAGNOSTIC_BOOL_KEYS = ("ortools_warmstart_enabled", "strict_mode")
_NEIGHBORHOOD_COUNTER_KEYS = ("attempted", "effective", "noop", "fallback", "rejected")
_ACCEPTANCE_COUNTER_KEYS = ("attempted", "accepted", "rejected", "non_improving_accepted")
_VNS_TEXT_KEYS = ("current_neighborhood", "last_switch_reason")
_VNS_INT_KEYS = ("neighborhood_index", "shake_count", "no_improve_count", "noop_count", "fallback_count")


def _safe_candidate_construction(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out: Dict[str, Any] = {}
    for family in ("grasp", "iterated_greedy"):
        source = value.get(family)
        if not isinstance(source, dict):
            continue
        row: Dict[str, Any] = {}
        for key in (
            "configured_restarts",
            "effective_restarts",
            "configured_rcl_size",
            "effective_rcl_size",
            "configured_destruction_size",
            "effective_destruction_size",
        ):
            number = safe_non_negative_int(source.get(key))
            if number is not None:
                row[key] = number
        if row:
            out[family] = row
    return out


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


def _project_neighborhood_summary(value: Any) -> Dict[str, Dict[str, int]]:
    if not isinstance(value, dict):
        return {}
    out: Dict[str, Dict[str, int]] = {}
    for raw_name, raw_counts in value.items():
        name = safe_attempt_text(raw_name)
        if not name or not isinstance(raw_counts, dict):
            continue
        row: Dict[str, int] = {}
        for key in _NEIGHBORHOOD_COUNTER_KEYS:
            number = safe_non_negative_int(raw_counts.get(key))
            if number is not None:
                row[key] = number
        if row:
            out[name] = row
    return out


def _project_acceptance_summary(value: Any) -> Dict[str, Dict[str, int]]:
    if not isinstance(value, dict):
        return {}
    out: Dict[str, Dict[str, int]] = {}
    for raw_name, raw_counts in value.items():
        name = safe_attempt_text(raw_name)
        if not name or not isinstance(raw_counts, dict):
            continue
        row: Dict[str, int] = {}
        for key in _ACCEPTANCE_COUNTER_KEYS:
            number = safe_non_negative_int(raw_counts.get(key))
            if number is not None:
                row[key] = number
        if row:
            out[name] = row
    return out


def _project_vns_summary(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out: Dict[str, Any] = {}
    for key in _VNS_TEXT_KEYS:
        text = safe_attempt_text(value.get(key))
        if text:
            out[key] = text
    for key in _VNS_INT_KEYS:
        number = safe_non_negative_int(value.get(key))
        if number is not None:
            out[key] = number
    return out


def _project_candidate_profile(value: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """把 candidate profile 合同拆成 (profile_public, profile_diagnostics)。

    public 只投 roadmap 允许的安全摘要字段；邻域只公开白名单名称，配置来源和构造预算等
    内部调试细节只进 diagnostics。所有字段仍过 safe_* 兜底，杜绝内部标识泄漏。
    """
    if not isinstance(value, dict):
        return {}, {}
    return _project_profile_public(value), _project_profile_diagnostics(value)


def _project_profile_public(value: Dict[str, Any]) -> Dict[str, Any]:
    public: Dict[str, Any] = {}
    for key in _PROFILE_PUBLIC_TEXT_KEYS:
        text = safe_attempt_text(value.get(key))
        if text:
            public[key] = text
    for key in _PROFILE_PUBLIC_INT_KEYS:
        number = safe_non_negative_int(value.get(key))
        if number is not None:
            public[key] = number
    for key in _PROFILE_PUBLIC_BOOL_KEYS:
        if key in value:
            public[key] = safe_bool(value.get(key))
    for key in _PROFILE_PUBLIC_LIST_KEYS:
        values = safe_public_text_list(value.get(key))
        if values:
            public[key] = values
    return public


def _project_profile_diagnostics(value: Dict[str, Any]) -> Dict[str, Any]:
    diagnostics: Dict[str, Any] = {}
    for key in _PROFILE_DIAGNOSTIC_TEXT_KEYS:
        text = safe_attempt_text(value.get(key))
        if text:
            diagnostics[key] = text
    for key in _PROFILE_DIAGNOSTIC_INT_KEYS:
        number = safe_non_negative_int(value.get(key))
        if number is not None:
            diagnostics[key] = number
    for key in _PROFILE_DIAGNOSTIC_BOOL_KEYS:
        if key in value:
            diagnostics[key] = safe_bool(value.get(key))
    candidate_construction = _safe_candidate_construction(value.get("candidate_construction"))
    if candidate_construction:
        diagnostics["candidate_construction"] = candidate_construction
    return diagnostics


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

    neighborhood_summary = _project_neighborhood_summary(value.get("neighborhood_summary"))
    if neighborhood_summary:
        public["neighborhood_summary"] = neighborhood_summary

    acceptance_summary = _project_acceptance_summary(value.get("acceptance_summary"))
    if acceptance_summary:
        public["acceptance_summary"] = acceptance_summary

    vns_summary = _project_vns_summary(value.get("vns_summary"))
    if vns_summary:
        public["vns_summary"] = vns_summary

    diagnostics = {key: value[key] for key in _DIAGNOSTIC_KEYS if key in value and value[key]}

    profile_public, profile_diagnostics = _project_candidate_profile(value.get("candidate_profile"))
    if profile_public:
        public["profile_public"] = profile_public
    if profile_diagnostics:
        diagnostics["profile_diagnostics"] = profile_diagnostics

    return public, diagnostics


__all__ = ["project_search_report"]
