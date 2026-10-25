"""GraphReady v2 priority keys: rank-normalized feature tuples per candidate formula."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from core.errors import ValidationError
from core.services.scheduler.run.optimizer.graph_ready_profiles import (
    GraphReadyWeightProfile,
    finite_number,
)

_FORMULA_FIELDS = {
    "edd": ("due_deadline", "sacrifice_penalty", "processing_rank", "jitter"),
    "spt": ("processing_rank", "due_budget", "sacrifice_penalty", "jitter"),
    "min_slack": ("slack_hours", "sacrifice_penalty", "processing_rank", "jitter"),
    "critical_ratio": ("critical_ratio", "sacrifice_penalty", "processing_rank", "jitter"),
    "atc_like": ("-due_pressure", "sacrifice_penalty", "-saveability", "processing_rank", "jitter"),
    "saveability": ("-saveability", "sacrifice_penalty", "-due_pressure", "remaining", "processing_rank", "jitter"),
    "sacrifice_long": ("sacrifice_penalty", "remaining", "-saveability", "due_budget", "processing_rank", "jitter"),
    "graph_due_hybrid": ("-graph_bonus", "-due_pressure", "sacrifice_penalty", "processing_rank", "jitter"),
    "bottleneck_due_gated": ("-bottleneck_due_gate", "sacrifice_penalty", "-due_pressure", "processing_rank", "jitter"),
    "micro_perturbation": ("sacrifice_penalty", "-due_pressure", "jitter", "processing_rank"),
    "weighted_spt": ("weighted_processing_hours_rank01", "due_deadline", "slack_hours", "jitter"),
    "weighted_atc": ("-weighted_due_pressure_rank01", "weighted_processing_hours_rank01", "slack_hours", "jitter"),
    "type_group": ("changeover_family_rank_rank01", "due_deadline", "processing_rank", "jitter"),
    "type_group_reverse": ("-changeover_family_rank_rank01", "due_deadline", "processing_rank", "jitter"),
}


_INF = float("inf")
_FIELD_TO_METRIC_KEY = {
    "due_deadline": "due_deadline_hours_rank01",
    "due_budget": "due_budget_hours_rank01",
    "due_pressure": "due_pressure_rank01",
    "slack_hours": "slack_hours_rank01",
    "remaining": "remaining_due_burden_hours_rank01",
    "saveability": "saveability_rank01",
    "processing_rank": "processing_time_rank_rank01",
    "sacrifice_penalty": "sacrifice_penalty_rank01",
    "critical_ratio": "critical_ratio_rank01",
    "bottleneck_due_gate": "bottleneck_due_gate_rank01",
    "graph_bonus": "graph_bonus_rank01",
    "jitter": "graph_ready_v2_jitter",
}
_FORMULA_SPECS: Dict[str, Tuple[Tuple[bool, str], ...]] = {
    formula: tuple(
        (field.startswith("-"), _FIELD_TO_METRIC_KEY[name] if name in _FIELD_TO_METRIC_KEY else name)
        for field in fields
        for name in (field.lstrip("-"),)
    )
    for formula, fields in _FORMULA_FIELDS.items()
}


def validate_v2_formula(formula: str) -> None:
    if formula not in _FORMULA_FIELDS:
        raise ValidationError(f"GraphReady v2 不支持候选公式：{formula}", field="graph_ready_v2_formula",
                              details={"reason": "graph_ready_bad_v2_formula"})


def v2_formula_specs(formula: str) -> Tuple[Tuple[bool, str], ...]:
    validate_v2_formula(formula)
    return _FORMULA_SPECS[formula]


def v2_priority_key_for_metric(
    metric: Dict[str, Any],
    *,
    profile: GraphReadyWeightProfile,
    specs: Optional[Tuple[Tuple[bool, str], ...]] = None,
) -> Tuple[float, ...]:
    if specs is None:
        specs = v2_formula_specs(str(profile.formula_slug or "").strip())
    result = []
    for neg, key in specs:
        val = metric.get(key)
        if type(val) is not float or not (0.0 <= val < _INF):
            val = required_non_negative_metric(required_finite_metric(metric, key), key)
        result.append(-val if neg else val)
    return tuple(result)


def required_finite_metric(metric: Dict[str, Any], field: str) -> float:
    if field not in metric:
        raise ValidationError(
            f"GraphReady v2 图指标缺少 {field}。",
            field="graph_ready_v2_features",
            details={"reason": "graph_ready_missing_v2_feature"},
        )
    try:
        return float(finite_number(metric.get(field), field=field, reason="graph_ready_bad_v2_feature"))
    except ValidationError as exc:
        raise ValidationError(exc.message, field="graph_ready_v2_features", details=exc.details) from exc


def required_non_negative_metric(value: float, field: str) -> float:
    if value < 0.0:
        raise ValidationError(
            f"GraphReady v2 图指标 {field} 必须是非负数。",
            field="graph_ready_v2_features",
            details={"reason": "graph_ready_bad_v2_feature"},
        )
    return value


def required_positive_metric(metric: Dict[str, Any], field: str) -> float:
    number = required_non_negative_metric(required_finite_metric(metric, field), field)
    if number <= 0.0:
        raise ValidationError(
            f"GraphReady v2 图指标 {field} 必须大于 0。",
            field="graph_ready_v2_features",
            details={"reason": "graph_ready_bad_v2_feature"},
        )
    return number


__all__ = [
    "required_finite_metric",
    "required_non_negative_metric",
    "required_positive_metric",
    "v2_formula_specs",
    "v2_priority_key_for_metric",
    "validate_v2_formula",
]
