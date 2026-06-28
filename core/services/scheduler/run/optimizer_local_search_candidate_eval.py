from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.algorithms import ScheduleResult
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.greedy.algo_stats import merge_algo_stats, snapshot_algo_stats

from .optimizer_neighborhood_moves import NeighborhoodMove


def evaluate_local_search_candidate(
    *,
    scheduler: Any,
    strict_mode: bool,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    strategy: Any,
    params: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    order: List[str],
    seed_sr_list: List[ScheduleResult],
    dispatch_mode: str,
    dispatch_rule: str,
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    optimizer_algo_stats: Optional[Dict[str, Any]],
    schedule_fn: Callable[..., Any],
    readiness_gate_enabled: bool,
    graph_ready_context: Optional[Any],
    neighborhood_move: NeighborhoodMove,
) -> Dict[str, Any]:
    res, summ, used_strat, used_params = schedule_fn(
        scheduler,
        strict_mode=bool(strict_mode),
        operations=algo_ops_to_schedule,
        batches=batches,
        strategy=strategy,
        strategy_params=params,
        start_dt=start_dt,
        end_date=end_date,
        machine_downtimes=downtime_map,
        batch_order_override=order,
        seed_results=seed_sr_list,
        dispatch_mode=dispatch_mode,
        dispatch_rule=dispatch_rule,
        resource_pool=resource_pool,
        readiness_gate_enabled=bool(readiness_gate_enabled),
        graph_ready_context=graph_ready_context,
    )
    metrics = compute_metrics(res, batches)
    algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(scheduler))
    return {
        "algo_stats": algo_stats,
        "results": res,
        "summary": summ,
        "strategy": used_strat,
        "params": used_params,
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "order": order,
        "metrics": metrics,
        "score": (float(summ.failed_ops),) + objective_score(objective_name, metrics),
        "resource_pool": resource_pool or {},
        "seed_result_count": len(seed_sr_list or []),
        "locked_seed_range": [getattr(item, "op_id", None) for item in list(seed_sr_list or [])],
        "mutable_scope": _mutable_scope_payload(neighborhood_move, order),
        "neighborhood_move": neighborhood_move.to_report_dict(),
    }


def _mutable_scope_payload(neighborhood_move: NeighborhoodMove, order: List[str]) -> Dict[str, Any]:
    return {
        "scope": str(neighborhood_move.input_scope or "batch_order"),
        "batch_count": len(order or []),
        "neighborhood_name": str(neighborhood_move.neighborhood_name),
        "move_kind": str(neighborhood_move.move_kind),
        "changed_decision_count": int(neighborhood_move.changed_decision_count),
        "fallback_used": bool(neighborhood_move.fallback_used),
        "fallback_reason": str(neighborhood_move.fallback_reason or ""),
    }


__all__ = ["evaluate_local_search_candidate"]
