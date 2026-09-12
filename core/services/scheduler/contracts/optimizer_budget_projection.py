"""Bounded diagnostic projection of assigned optimizer time budgets."""

import math
from typing import Any, Dict

from .optimizer_public_safety import safe_attempt_text, safe_non_negative_int

_TEXT_KEYS = ("policy", "clock", "phase_policy")
_MILLISECOND_KEYS = (
    "assigned_time_budget_ms", "preparation_runtime_ms", "optimizer_time_budget_ms",
    "outer_remaining_time_ms", "multi_start_budget_ms", "warmstart_cutoff_ms",
    "heuristic_cutoff_ms", "deadline_overrun_ms", "outer_deadline_overrun_ms",
)
_FEEDBACK_INTEGER_KEYS = (
    "observed_completed_count", "observed_improvement_count", "candidate_sequence",
    "equal_slice_ms", "minimum_untried_share_ms", "reserved_for_other_candidates_ms",
)
_FEEDBACK_REASONS = {
    "last_candidate_uses_remaining", "no_finite_remaining_budget", "no_measured_comparable_improvement",
    "unrepresentable_improvement_rate", "observed_no_improvement_reserve_untried", "observed_strict_improvement_bonus",
}


def project_optimizer_budget(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out: Dict[str, Any] = {}
    for key in _TEXT_KEYS:
        text = safe_attempt_text(value.get(key))
        if text:
            out[key] = text
    for key in _MILLISECOND_KEYS:
        number = safe_non_negative_int(value.get(key))
        if number is not None:
            out[key] = number
    feedback = _project_allocation_feedback(value.get("allocation_feedback"))
    if feedback:
        out["allocation_feedback"] = feedback
    return out


def _project_allocation_feedback(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out: Dict[str, Any] = {}
    if value.get("policy") == "observed_strict_improvement_per_second_v1":
        out["policy"] = value["policy"]
    reason = value.get("reason")
    if type(reason) is str and reason in _FEEDBACK_REASONS:
        out["reason"] = reason
    for key in _FEEDBACK_INTEGER_KEYS:
        number = safe_non_negative_int(value.get(key))
        if number is not None:
            out[key] = number
    for key in ("feedback_applied", "strict_improvement"):
        if type(value.get(key)) is bool:
            out[key] = value[key]
    for key in ("allocation_factor", "elapsed_seconds", "improvements_per_second"):
        number = _finite_non_negative_number(value.get(key))
        if number is not None:
            out[key] = number
    return out


def _finite_non_negative_number(value: Any) -> Any:
    if type(value) not in (int, float):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) and number >= 0 else None
