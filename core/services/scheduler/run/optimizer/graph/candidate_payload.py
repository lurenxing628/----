"""Serialization and formal scoring of a decoded graph candidate."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from core.algorithm_contracts.sort_strategies import SortStrategy
from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary
from core.algorithms.evaluation import ScheduleMetrics, objective_score
from core.services.scheduler.run.optimizer.graph_ready_profiles import (
    GraphReadyWeightProfile,
)

from .reporting import public_params


def build_graph_ready_candidate_payload(
    *, res: List[ScheduleResult], summ: ScheduleSummary, used_strat: SortStrategy,
    used_params: Dict[str, Any], metrics: ScheduleMetrics, profile: GraphReadyWeightProfile,
    order: List[str], dispatch_rule: str, objective_name: str, algo_stats: Dict[str, Any],
    resource_pool: Optional[Dict[str, Any]], runtime_ms: int,
    profile_dict: Dict[str, Any], repair_decision: Optional[Any] = None,
) -> Dict[str, Any]:
    decoded_order = decoded_batch_order(res)
    result_order = _result_batch_order(decoded_order, decision_order=order)
    payload = {
        "results": res,
        "summary": summ,
        "strategy": used_strat,
        "params": public_params(used_params),
        "dispatch_mode": "sgs",
        "dispatch_rule": str(dispatch_rule or ""),
        "order": result_order,
        "decoded_batch_order": decoded_order,
        "metrics": metrics,
        "score": (float(summ.failed_ops),) + objective_score(objective_name, metrics),
        "algo_stats": algo_stats,
        "resource_pool": resource_pool or {},
        "candidate_origin": profile.candidate_origin,
        "runtime_ms": int(runtime_ms),
        "graph_ready_profile": profile_dict,
    }
    if repair_decision is not None:
        payload["repair_decision"] = {
            "batch_order": list(repair_decision.batch_order), "operation_order": list(repair_decision.operation_order),
            "resource_overrides": [list(item) for item in repair_decision.resource_overrides],
        }
    return payload


def decoded_batch_order(results: List[ScheduleResult]) -> List[str]:
    order: List[str] = []
    seen = set()
    for result in sorted(
        results,
        key=lambda item: (
            item.start_time or datetime.max,
            item.end_time or datetime.max,
            int(item.seq or 0),
            int(item.op_id or 0),
        ),
    ):
        batch_id = str(result.batch_id or "").strip()
        if not batch_id or batch_id in seen:
            continue
        seen.add(batch_id)
        order.append(batch_id)
    return order


def _result_batch_order(decoded_batch_order: List[str], *, decision_order: List[str]) -> List[str]:
    out = list(decoded_batch_order)
    seen = set(out)
    for batch_id in decision_order:
        text = str(batch_id or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out
