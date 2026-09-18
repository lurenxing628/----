"""GraphReady v2 priority keys: rank-normalized feature tuples per candidate formula."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from core.infrastructure.errors import ValidationError

from .optimizer_graph_ready_profiles import GraphReadyWeightProfile, finite_number


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

    objective_key = _objective_priority_key(metric, formula, due_deadline, slack_hours, processing_rank, jitter)
    if objective_key is not None:
        return objective_key
    if formula == "edd":
        return (due_deadline, sacrifice_penalty, processing_rank, jitter)
    if formula == "spt":
        return (processing_rank, due_budget, sacrifice_penalty, jitter)
    if formula == "min_slack":
        return (slack_hours, sacrifice_penalty, processing_rank, jitter)
    if formula == "critical_ratio":
        return (critical_ratio, sacrifice_penalty, processing_rank, jitter)
    if formula == "atc_like":
        return (-due_pressure, sacrifice_penalty, -saveability, processing_rank, jitter)
    if formula == "saveability":
        return (-saveability, sacrifice_penalty, -due_pressure, remaining, processing_rank, jitter)
    if formula == "sacrifice_long":
        return (sacrifice_penalty, remaining, -saveability, due_budget, processing_rank, jitter)
    if formula == "graph_due_hybrid":
        return (-graph_bonus, -due_pressure, sacrifice_penalty, processing_rank, jitter)
    if formula == "bottleneck_due_gated":
        return (-bottleneck_due_gate, sacrifice_penalty, -due_pressure, processing_rank, jitter)
    if formula == "micro_perturbation":
        # 小扰动只在两个主交期目标(牺牲度、交期压力)都相同的候选间用 jitter 打破平局(压过次要的工时排名),
        # 不跨交期分数差异重排,符合"只在分数接近的 ready 候选之间做";同分时不同 seed 产生不同候选以提供多样性。
        return (sacrifice_penalty, -due_pressure, jitter, processing_rank)
    raise ValidationError(
        f"GraphReady v2 不支持候选公式：{formula}",
        field="graph_ready_v2_formula",
        details={"reason": "graph_ready_bad_v2_formula"},
    )


def _objective_priority_key(metric, formula, due_deadline, slack_hours, processing_rank, jitter):
    if formula == "weighted_spt":
        return (_required_non_negative_metric(metric, "weighted_processing_hours_rank01"), due_deadline, slack_hours, jitter)
    if formula == "weighted_atc":
        return (-_required_non_negative_metric(metric, "weighted_due_pressure_rank01"),
                _required_non_negative_metric(metric, "weighted_processing_hours_rank01"), slack_hours, jitter)
    if formula in {"type_group", "type_group_reverse"}:
        family = _required_non_negative_metric(metric, "changeover_family_rank_rank01")
        return (family if formula == "type_group" else -family, due_deadline, processing_rank, jitter)
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
