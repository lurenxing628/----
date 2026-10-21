from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.errors import ValidationError
from core.services.scheduler.run.optimizer.graph_ready_profiles import (
    GraphReadyWeightProfile,
    resolve_v2_profiles_and_summary,
    resolve_weight_grid_profiles_and_summary,
)


def resolve_graph_ready_profiles_and_metrics(
    *,
    max_weight_profiles: int,
    candidate_construction: Optional[Dict[str, Any]],
    version: int,
    objective_name: str = "min_overdue",
    shared_search: bool = True,
) -> Tuple[List[GraphReadyWeightProfile], Dict[str, Any]]:
    optimization = _graph_ready_optimization(candidate_construction)
    policy = str(optimization.get("candidate_policy") or "weight_grid").strip().lower()
    if policy == "weight_grid":
        return resolve_weight_grid_profiles_and_summary(
            max_weight_profiles=max_weight_profiles, objective_name=objective_name,
        )
    if policy == "objective_aware_portfolio":
        max_candidate_profiles = _positive_profile_limit(
            optimization.get("max_candidate_profiles", 60),
            field="max_candidate_profiles",
        )
        return resolve_v2_profiles_and_summary(
            max_candidate_profiles=max_candidate_profiles,
            seed=int(version),
            objective_name=objective_name,
            shared_search=shared_search,
        )
    raise ValidationError(
        f"GraphReady 候选策略不支持：{policy}",
        field="graph_ready_candidate_policy",
        details={"reason": "graph_ready_bad_candidate_policy"},
    )


def _graph_ready_optimization(candidate_construction: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(candidate_construction, dict):
        return {}
    value = candidate_construction.get("graph_ready_optimization")
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError(
            "GraphReady 候选配置必须是映射。",
            field="graph_ready_candidate_policy",
            details={"reason": "graph_ready_bad_candidate_policy"},
        )
    return dict(value)


def _positive_profile_limit(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        _raise_bad_limit(field)
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(
            f"{field} 必须是正整数。",
            field="graph_ready_candidate_policy",
            details={"reason": "graph_ready_bad_candidate_policy"},
        ) from exc
    if number <= 0:
        _raise_bad_limit(field)
    return number


def _raise_bad_limit(field: str) -> None:
    raise ValidationError(
        f"{field} 必须是正整数。",
        field="graph_ready_candidate_policy",
        details={"reason": "graph_ready_bad_candidate_policy"},
    )


__all__ = ["resolve_graph_ready_profiles_and_metrics"]
