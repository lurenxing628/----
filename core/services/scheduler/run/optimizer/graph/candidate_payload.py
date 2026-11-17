"""Serialization and formal scoring of a decoded graph candidate."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.algorithm_contracts.sort_strategies import WeightedParams
from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary
from core.algorithms.evaluation import ScheduleMetrics, objective_score
from core.models.enums import SortStrategy
from core.services.scheduler.run.optimizer.graph_ready_profiles import (
    GraphReadyWeightProfile,
)


def public_graph_ready_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """The part of a candidate's graph-ready profile payload a published plan records."""
    return {key: profile[key] for key in (
        "schema_version", "candidate_origin", "weight_profile_slug", "candidate_policy", "max_weight_profiles")}


def build_graph_ready_candidate_payload(
    *, res: List[ScheduleResult], decoded_order: Tuple[str, ...], summ: ScheduleSummary, used_strat: SortStrategy,
    params: Optional[WeightedParams], metrics: ScheduleMetrics, profile: GraphReadyWeightProfile,
    order: Sequence[str], dispatch_rule: str, objective_name: str, algo_stats: Dict[str, Any], runtime_ms: int,
    profile_dict: Dict[str, Any], repair_decision: Optional[Any] = None,
) -> Dict[str, Any]:
    """A graph candidate decodes with the run's own pair ranks: it carries no rank override."""
    result_order = _result_batch_order(decoded_order, decision_order=order)
    return {
        "results": res,
        "summary": summ,
        "strategy": used_strat,
        "params": params,
        "graph_ready_profile": profile_dict,
        "dispatch_mode": "sgs",
        "dispatch_rule": dispatch_rule,
        "repair_decision": None if repair_decision is None else {
            "batch_order": list(repair_decision.batch_order), "operation_order": list(repair_decision.operation_order),
            "resource_overrides": [list(item) for item in repair_decision.resource_overrides],
        },
        "order": result_order,
        "decoded_batch_order": decoded_order,
        "metrics": metrics,
        "score": (float(summ.failed_ops),) + objective_score(objective_name, metrics),
        "algo_stats": algo_stats,
        "resource_pair_rank": {},
        "candidate_origin": profile.candidate_origin,
        "runtime_ms": int(runtime_ms),
    }


def _result_batch_order(decoded_order: Tuple[str, ...], *, decision_order: Sequence[str]) -> List[str]:
    out = list(decoded_order)
    seen = set(out)
    for batch_id in decision_order:
        if batch_id not in seen:
            seen.add(batch_id)
            out.append(batch_id)
    return out
