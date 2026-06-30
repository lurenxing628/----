from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithms import ScheduleResult
from core.infrastructure.errors import ValidationError

from .optimizer_graph_ready_profiles import (
    GraphReadyWeightProfile,
    default_weight_profiles,
    graph_ready_v2_profile_summary,
    graph_ready_v2_profiles,
    graph_ready_weight_profile_summary,
)
from .optimizer_graph_ready_v2_features import enrich_graph_ready_v2_metrics


def resolve_graph_ready_profiles_and_metrics(
    metrics_by_op_id: Dict[int, Dict[str, Any]],
    *,
    max_weight_profiles: int,
    profiles_override: Optional[List[GraphReadyWeightProfile]],
    profile_summary_override: Optional[Dict[str, Any]],
    candidate_construction: Optional[Dict[str, Any]],
    version: int,
    scheduler: Any,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    start_dt: datetime,
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_sr_list: List[ScheduleResult],
    resource_pool: Optional[Dict[str, Any]],
    strict_mode: bool,
) -> Tuple[List[GraphReadyWeightProfile], Dict[str, Any], Dict[int, Dict[str, Any]]]:
    profiles, profile_summary = _resolve_profiles(
        max_weight_profiles=max_weight_profiles,
        profiles_override=profiles_override,
        profile_summary_override=profile_summary_override,
        candidate_construction=candidate_construction,
        version=version,
    )
    # 空交期由 v2 特征层做 per-op 占位降级；非空坏交期始终 fail-loud，不能伪装成无交期。
    # 其它坏特征一律 fail-loud，不存在"v2 整池跳过"中间态。
    # _metrics_for_profiles 抛出的 ValidationError 直接上抛,由 run_graph_ready_candidates 主链按 strict/feature-error 统一处理。
    metrics = _metrics_for_profiles(
        metrics_by_op_id,
        profiles=profiles,
        scheduler=scheduler,
        algo_ops_to_schedule=algo_ops_to_schedule,
        batches=batches,
        start_dt=start_dt,
        downtime_map=downtime_map,
        seed_sr_list=seed_sr_list,
        resource_pool=resource_pool,
        strict_mode=bool(strict_mode),
    )
    return profiles, profile_summary, metrics


def _resolve_profiles(
    *,
    max_weight_profiles: int,
    profiles_override: Optional[List[GraphReadyWeightProfile]],
    profile_summary_override: Optional[Dict[str, Any]],
    candidate_construction: Optional[Dict[str, Any]],
    version: int,
) -> Tuple[List[GraphReadyWeightProfile], Dict[str, Any]]:
    if profiles_override is not None:
        profiles = list(profiles_override)
        summary = profile_summary_override or _profile_summary_for_profiles(
            profiles,
            max_weight_profiles=max_weight_profiles,
            version=version,
        )
        return profiles, summary

    optimization = _graph_ready_optimization(candidate_construction)
    policy = str(optimization.get("candidate_policy") or "weight_grid").strip().lower()
    if policy == "weight_grid":
        profiles, _truncated, _reason = default_weight_profiles(max_weight_profiles=max_weight_profiles)
        return profiles, graph_ready_weight_profile_summary(max_weight_profiles=max_weight_profiles)
    if policy == "objective_aware_portfolio":
        max_candidate_profiles = _positive_profile_limit(
            optimization.get("max_candidate_profiles", 60),
            field="max_candidate_profiles",
        )
        profiles, _truncated, _reason = graph_ready_v2_profiles(
            max_candidate_profiles=max_candidate_profiles,
            seed=int(version),
        )
        return profiles, graph_ready_v2_profile_summary(
            max_candidate_profiles=max_candidate_profiles,
            seed=int(version),
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


def _profile_summary_for_profiles(
    profiles: List[GraphReadyWeightProfile],
    *,
    max_weight_profiles: int,
    version: int,
) -> Dict[str, Any]:
    if any(_uses_v2_profile(profile) for profile in profiles):
        return graph_ready_v2_profile_summary(max_candidate_profiles=max(len(profiles), 1), seed=int(version))
    return graph_ready_weight_profile_summary(max_weight_profiles=max_weight_profiles)


def _metrics_for_profiles(
    metrics_by_op_id: Dict[int, Dict[str, Any]],
    *,
    profiles: List[GraphReadyWeightProfile],
    scheduler: Any,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    start_dt: datetime,
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_sr_list: List[ScheduleResult],
    resource_pool: Optional[Dict[str, Any]],
    strict_mode: bool,
) -> Dict[int, Dict[str, Any]]:
    if not any(_uses_v2_profile(profile) for profile in profiles):
        return metrics_by_op_id
    return enrich_graph_ready_v2_metrics(
        metrics_by_op_id,
        operations=algo_ops_to_schedule,
        batches=batches,
        start_dt=start_dt,
        calendar_service=getattr(scheduler, "calendar", None),
        downtime_map=downtime_map,
        seed_results=seed_sr_list,
        resource_pool=resource_pool,
        strict_mode=bool(strict_mode),
    )


def _uses_v2_profile(profile: GraphReadyWeightProfile) -> bool:
    return str(profile.formula_version or "").startswith("graph_ready_v2")


__all__ = ["resolve_graph_ready_profiles_and_metrics"]
