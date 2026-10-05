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


def validate_v2_formula(formula: str) -> None:
    if formula not in _FORMULA_FIELDS:
        raise ValidationError(f"GraphReady v2 不支持候选公式：{formula}", field="graph_ready_v2_formula",
                              details={"reason": "graph_ready_bad_v2_formula"})


def _formula_key(metric, formula, values):
    validate_v2_formula(formula)
    result = []
    for field in _FORMULA_FIELDS[formula]:
        name = field.lstrip("-")
        value = values[name] if name in values else _required_non_negative_metric(metric, name)
        result.append(-value if field.startswith("-") else value)
    return tuple(result)


def _v2_priority_key_for_metric(metric: Dict[str, Any], *, profile: GraphReadyWeightProfile) -> Tuple[float, ...]:
    formula = str(profile.formula_slug or "").strip()
    due_deadline = _required_non_negative_metric(metric, "due_deadline_hours_rank01")
    due_budget = _required_non_negative_metric(metric, "due_budget_hours_rank01")
    due_pressure = _required_non_negative_metric(metric, "due_pressure_rank01")
    slack_hours = _required_non_negative_metric(metric, "slack_hours_rank01")
    remaining = _required_non_negative_metric(metric, "remaining_due_burden_hours_rank01")
    saveability = _required_non_negative_metric(metric, "saveability_rank01")
    processing_rank = _required_non_negative_metric(metric, "processing_time_rank_rank01")
    sacrifice_penalty = _required_non_negative_metric(metric, "sacrifice_penalty_rank01")
    critical_ratio = _required_non_negative_metric(metric, "critical_ratio_rank01")
    bottleneck_due_gate = _required_non_negative_metric(metric, "bottleneck_due_gate_rank01")
    graph_bonus = _required_non_negative_metric(metric, "graph_bonus_rank01")
    jitter = _stable_jitter(metric)

    return _formula_key(metric, formula, dict(due_deadline=due_deadline, due_budget=due_budget,
        due_pressure=due_pressure, slack_hours=slack_hours, remaining=remaining, saveability=saveability,
        processing_rank=processing_rank, sacrifice_penalty=sacrifice_penalty, critical_ratio=critical_ratio,
        bottleneck_due_gate=bottleneck_due_gate, graph_bonus=graph_bonus, jitter=jitter))


def _objective_priority_key(metric, formula, due_deadline, slack_hours, processing_rank, jitter):
    if formula in {"weighted_spt", "weighted_atc", "type_group", "type_group_reverse"}:
        return _formula_key(metric, formula, dict(due_deadline=due_deadline, slack_hours=slack_hours,
                                                processing_rank=processing_rank, jitter=jitter))
    return None


def _required_finite_metric(metric: Dict[str, Any], field: str) -> float:
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


def _required_non_negative_metric(metric: Dict[str, Any], field: str) -> float:
    number = _required_finite_metric(metric, field)
    if number < 0.0:
        raise ValidationError(
            f"GraphReady v2 图指标 {field} 必须是非负数。",
            field="graph_ready_v2_features",
            details={"reason": "graph_ready_bad_v2_feature"},
        )
    return number


def _required_positive_metric(metric: Dict[str, Any], field: str) -> float:
    number = _required_non_negative_metric(metric, field)
    if number <= 0.0:
        raise ValidationError(
            f"GraphReady v2 图指标 {field} 必须大于 0。",
            field="graph_ready_v2_features",
            details={"reason": "graph_ready_bad_v2_feature"},
        )
    return number


def _stable_jitter(metric: Dict[str, Any]) -> float:
    return _required_non_negative_metric(metric, "graph_ready_v2_jitter")


__all__ = ["_objective_priority_key", "_required_finite_metric", "_required_non_negative_metric",
           "_required_positive_metric", "_stable_jitter", "_v2_priority_key_for_metric"]
