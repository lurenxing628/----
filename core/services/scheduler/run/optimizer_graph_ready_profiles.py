from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import zip_longest
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import ValidationError
from core.models.objective import normalize_objective_name

from .optimizer_graph_ready_feature_basis import BATCH_WORKLOAD_BASIS, SUCCESSOR_WORKLOAD_BASIS

GRAPH_READY_PHASE = "graph_ready_candidate_search"
GRAPH_READY_BASE_ORIGIN = "graph_ready_base"
GRAPH_READY_WEIGHT_GRID_ORIGIN = "graph_ready_weight_grid"
GRAPH_READY_LOCAL_SEARCH_ORIGIN = "graph_ready_local_search"
GRAPH_READY_V2_GENERATED_ORIGIN = "graph_ready_v2_generated"
GRAPH_READY_V2_REPAIRED_ORIGIN = "graph_ready_v2_repaired"

GRAPH_READY_REQUIRED_CONTEXT_FIELDS = (
    "schedulable_op_ids",
    "fixed_op_ids",
    "predecessor_op_ids_by_op_id",
    "successor_op_ids_by_op_id",
    "sort_key_by_op_id",
    "graph_priority_key_by_op_id",
)

GRAPH_READY_SELECTION_TIEBREAKER = (
    "failed_ops",
    "objective_score",
    "best_fingerprint_changed",
    "runtime_ms",
    "candidate_origin",
)

GRAPH_READY_DEFAULT_WEIGHT_PROFILES: Tuple[Dict[str, Any], ...] = (
    {"slug": "balanced", "critical_path": 2.0, "successor_count": 1.0, "downstream_work_hours": 1.0, "bottleneck_machine": 1.0},
    {"slug": "critical_path_first", "critical_path": 4.0, "successor_count": 1.0, "downstream_work_hours": 1.0, "bottleneck_machine": 0.5},
    {"slug": "successor_fanout_first", "critical_path": 1.0, "successor_count": 3.0, "downstream_work_hours": 1.0, "bottleneck_machine": 0.5},
    {"slug": "downstream_work_first", "critical_path": 1.0, "successor_count": 1.0, "downstream_work_hours": 3.0, "bottleneck_machine": 0.5},
    {"slug": "bottleneck_relief", "critical_path": 1.0, "successor_count": 0.5, "downstream_work_hours": 1.0, "bottleneck_machine": 3.0},
    {"slug": "critical_bottleneck", "critical_path": 3.0, "successor_count": 0.5, "downstream_work_hours": 1.0, "bottleneck_machine": 2.0},
    {"slug": "fanout_downstream", "critical_path": 0.5, "successor_count": 2.0, "downstream_work_hours": 2.0, "bottleneck_machine": 0.5},
    {"slug": "bottleneck_downstream", "critical_path": 0.5, "successor_count": 1.0, "downstream_work_hours": 2.0, "bottleneck_machine": 2.0},
    {"slug": "graph_neutral", "critical_path": 0.0, "successor_count": 0.0, "downstream_work_hours": 0.0, "bottleneck_machine": 0.0},
)


@dataclass(frozen=True)
class GraphReadyWeightProfile:
    slug: str
    profile_order: int
    raw_weights: Dict[str, float]
    effective_weights: Dict[str, float]
    candidate_origin: str
    candidate_policy: str
    formula_slug: str = "v1_weighted_graph"
    formula_version: str = "graph_ready_v1"
    jitter_seed: int = 0
    objective_name: str = "min_overdue"
    feature_basis: str = SUCCESSOR_WORKLOAD_BASIS


def graph_ready_weight_profile_summary(max_weight_profiles: int = 9) -> Dict[str, Any]:
    profiles, truncated, reason = default_weight_profiles(max_weight_profiles=max_weight_profiles)
    return {
        "schema_version": 1,
        "phase": GRAPH_READY_PHASE,
        "candidate_policy": "weight_grid",
        "max_weight_profiles": int(max_weight_profiles),
        "configured_weight_profile_count": len(GRAPH_READY_DEFAULT_WEIGHT_PROFILES),
        "effective_weight_profile_count": len(profiles),
        "weight_profile_slugs": [profile.slug for profile in profiles],
        "truncated": bool(truncated),
        "truncation_reason": reason,
        "selection_tiebreaker": list(GRAPH_READY_SELECTION_TIEBREAKER),
    }


def graph_ready_v2_profile_summary(max_candidate_profiles: int = 60, *, seed: int = 0, objective_name: str = "min_overdue") -> Dict[str, Any]:
    profiles, truncated, reason = graph_ready_v2_profiles(max_candidate_profiles=max_candidate_profiles, seed=seed, objective_name=objective_name)
    return {
        "schema_version": 1,
        "phase": GRAPH_READY_PHASE,
        "candidate_policy": "objective_aware_portfolio",
        "max_candidate_profiles": int(max_candidate_profiles),
        "configured_candidate_profile_count": len(_graph_ready_v2_profile_specs(objective_name=objective_name)),
        "objective_name": normalize_objective_name(objective_name),
        "objective_candidate_version": "baseline_and_successor_portfolio_v1",
        "effective_candidate_profile_count": len(profiles),
        "weight_profile_slugs": [profile.slug for profile in profiles],
        "formula_versions": sorted({profile.formula_version for profile in profiles}),
        "normalization_version": "rank_percentile_v1",
        "ordering_policy": "baseline_micro_edd_then_feature_round_robin",
        "feature_bases": sorted({profile.feature_basis for profile in profiles if profile.formula_version.startswith("graph_ready_v2")}),
        "truncated": bool(truncated),
        "truncation_reason": reason,
        "selection_tiebreaker": list(GRAPH_READY_SELECTION_TIEBREAKER),
    }


def default_weight_profiles(*, max_weight_profiles: int) -> Tuple[List[GraphReadyWeightProfile], bool, Optional[str]]:
    limit = _positive_limit(max_weight_profiles)
    profiles = [_build_profile(index, raw) for index, raw in enumerate(GRAPH_READY_DEFAULT_WEIGHT_PROFILES[:limit])]
    truncated = len(GRAPH_READY_DEFAULT_WEIGHT_PROFILES) > len(profiles)
    return profiles, truncated, ("max_weight_profiles" if truncated else None)


def graph_ready_v2_profiles(*, max_candidate_profiles: int, seed: int = 0, objective_name: str = "min_overdue") -> Tuple[List[GraphReadyWeightProfile], bool, Optional[str]]:
    limit = _positive_limit(max_candidate_profiles)
    specs = _graph_ready_v2_profile_specs(seed=seed, objective_name=objective_name)
    profiles = [_build_profile(index, raw) for index, raw in enumerate(specs[:limit])]
    truncated = len(specs) > len(profiles)
    return profiles, truncated, ("max_candidate_profiles" if truncated else None)


def profile_payload(profile: GraphReadyWeightProfile, *, version: Optional[int]) -> Dict[str, Any]:
    payload = {
        "schema_version": 1,
        "graph_analysis_mode": "on",
        "dispatch_mode": "sgs",
        "candidate_origin": profile.candidate_origin,
        "weight_profile_slug": profile.slug,
        "priority_weights": dict(profile.raw_weights),
        "raw_weights": dict(profile.raw_weights),
        "effective_weights": dict(profile.effective_weights),
        "candidate_policy": profile.candidate_policy,
        "formula_slug": profile.formula_slug,
        "formula_version": profile.formula_version,
        "objective_name": profile.objective_name,
        "feature_basis": profile.feature_basis,
        "max_weight_profiles": len(GRAPH_READY_DEFAULT_WEIGHT_PROFILES),
        "profile_order": int(profile.profile_order),
        "selection_tiebreaker": list(GRAPH_READY_SELECTION_TIEBREAKER),
    }
    if version is not None:
        payload["seed"] = int(version)
    return payload


def finite_number(value: Any, *, field: str, reason: str = "graph_ready_bad_node_metrics") -> float:
    if isinstance(value, bool):
        raise ValidationError(f"图指标 {field} 必须是有限数字。", field="graph_ready_context", details={"reason": reason})
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"图指标 {field} 必须是有限数字。", field="graph_ready_context", details={"reason": reason}) from exc
    if not math.isfinite(number):
        raise ValidationError(f"图指标 {field} 必须是有限数字。", field="graph_ready_context", details={"reason": reason})
    return number


def _build_profile(index: int, raw: Dict[str, Any]) -> GraphReadyWeightProfile:
    raw_weights = {field: _finite_non_negative_weight(raw.get(field), field=field) for field in _weight_fields()}
    slug = str(raw.get("slug") or "").strip()
    if not slug:
        raise ValidationError("图权重配置缺少 slug。", field="graph_ready_weight")
    return GraphReadyWeightProfile(
        slug=slug,
        profile_order=index,
        raw_weights=raw_weights,
        effective_weights=dict(raw_weights),
        candidate_origin=str(raw.get("candidate_origin") or (GRAPH_READY_BASE_ORIGIN if index == 0 else GRAPH_READY_WEIGHT_GRID_ORIGIN)),
        candidate_policy=str(raw.get("candidate_policy") or ("fixed_weights" if index == 0 else "weight_grid")),
        formula_slug=str(raw.get("formula_slug") or "v1_weighted_graph"),
        formula_version=str(raw.get("formula_version") or "graph_ready_v1"),
        jitter_seed=int(raw.get("jitter_seed") or 0),
        objective_name=normalize_objective_name(raw.get("objective_name")),
        feature_basis=str(raw.get("feature_basis") or SUCCESSOR_WORKLOAD_BASIS),
    )


def _positive_limit(value: Any) -> int:
    if isinstance(value, bool):
        raise ValidationError("max_weight_profiles 必须是正整数。", field="max_weight_profiles")
    limit = int(value or 0)
    if limit <= 0:
        raise ValidationError("max_weight_profiles 必须是正整数。", field="max_weight_profiles")
    return limit


def _finite_non_negative_weight(value: Any, *, field: str) -> float:
    number = finite_number(value, field=field, reason="graph_ready_bad_weight")
    if number < 0:
        raise ValidationError(f"图权重 {field} 必须是非负数。", field="graph_ready_weight")
    return float(number)


def _weight_fields() -> Tuple[str, str, str, str]:
    return ("critical_path", "successor_count", "downstream_work_hours", "bottleneck_machine")


def _graph_ready_v2_profile_specs(*, seed: int = 0, objective_name: str = "min_overdue") -> Tuple[Dict[str, Any], ...]:
    v1 = tuple(dict(item) for item in GRAPH_READY_DEFAULT_WEIGHT_PROFILES)
    baseline = tuple(dict(item, feature_basis=BATCH_WORKLOAD_BASIS) for item in _v2_ordering_specs(seed))
    objective_name = normalize_objective_name(objective_name)
    successor = _successor_profile_specs(seed, objective_name)
    # Preserve two established, distinct baseline parents before adding features.
    # Remaining baseline and enhanced candidates compete within the same limits.
    portfolio = [v1[0], baseline[0], baseline[1]]
    for group in zip_longest(successor, v1[1:], baseline[2:]):
        portfolio.extend(item for item in group if item is not None)
    return tuple(dict(item, objective_name=objective_name) for item in portfolio)


def _v2_ordering_specs(seed: int) -> Tuple[Dict[str, Any], ...]:
    return (
        _v2_spec("v2_seeded_micro_perturbation", "micro_perturbation", jitter_seed=int(seed)),
        _v2_spec("v2_edd", "edd"),
        _v2_spec("v2_spt", "spt"),
        _v2_spec("v2_min_slack", "min_slack"),
        _v2_spec("v2_critical_ratio", "critical_ratio"),
        _v2_spec("v2_atc_like", "atc_like"),
        _v2_spec("v2_saveability", "saveability"),
        _v2_spec("v2_sacrifice_long", "sacrifice_long"),
        _v2_spec("v2_graph_due_hybrid", "graph_due_hybrid", critical_path=1.0, successor_count=0.5, downstream_work_hours=0.5),
        _v2_spec("v2_bottleneck_due_gated", "bottleneck_due_gated", bottleneck_machine=1.0),
    )


def _successor_profile_specs(seed: int, objective_name: str) -> Tuple[Dict[str, Any], ...]:
    v2_specs = _v2_ordering_specs(seed)
    if objective_name == "min_tardiness":
        preferred = ("spt", "min_slack", "edd", "atc_like")
        v2_specs = tuple(item for name in preferred for item in v2_specs if item["formula_slug"] == name) + tuple(
            item for item in v2_specs if item["formula_slug"] not in preferred
        )
    elif objective_name == "min_weighted_tardiness":
        v2_specs = (_v2_spec("v2_weighted_spt", "weighted_spt"), _v2_spec("v2_weighted_atc", "weighted_atc")) + v2_specs
    elif objective_name == "min_changeover":
        v2_specs = (_v2_spec("v2_type_group", "type_group"), _v2_spec("v2_type_group_reverse", "type_group_reverse")) + v2_specs
    return tuple(dict(item, slug="v2_successor_" + item["slug"][3:],
                      formula_version="graph_ready_v2_operation_successor_v1", feature_basis=SUCCESSOR_WORKLOAD_BASIS)
                 for item in v2_specs)


def _v2_spec(
    slug: str,
    formula_slug: str,
    *,
    critical_path: float = 0.0,
    successor_count: float = 0.0,
    downstream_work_hours: float = 0.0,
    bottleneck_machine: float = 0.0,
    jitter_seed: int = 0,
) -> Dict[str, Any]:
    return {
        "slug": slug,
        "critical_path": critical_path,
        "successor_count": successor_count,
        "downstream_work_hours": downstream_work_hours,
        "bottleneck_machine": bottleneck_machine,
        "candidate_origin": GRAPH_READY_V2_GENERATED_ORIGIN,
        "candidate_policy": "objective_aware_portfolio",
        "formula_slug": formula_slug,
        "formula_version": "graph_ready_v2_objective_features_v2",
        "jitter_seed": int(jitter_seed),
    }
