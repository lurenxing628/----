from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from core.algorithms import ScheduleResult
from core.algorithms.evaluation import objective_score

from .neighborhood_moves import NeighborhoodMove
from .shared_decode import decode_and_metrics

if TYPE_CHECKING:
    from .shared_decode import SharedDecodeSession


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
    decode_session: SharedDecodeSession,
    resource_pair_rank: Optional[Dict[Tuple[str, str], int]] = None,
) -> Dict[str, Any]:
    decoded = decode_and_metrics(
        decode_session=decode_session,
        objective_name=objective_name,
        optimizer_algo_stats=optimizer_algo_stats,
        strict_mode=bool(strict_mode),
        strategy=strategy,
        strategy_params=params,
        start_dt=start_dt,
        end_date=end_date,
        batch_order_override=order,
        dispatch_mode=dispatch_mode,
        dispatch_rule=dispatch_rule,
        readiness_gate_enabled=bool(readiness_gate_enabled),
        graph_enabled=graph_ready_context is not None,
        graph_score_enabled=bool(graph_ready_context and graph_ready_context.get("score_enabled")),
        graph_priority_key_by_op_id=(graph_ready_context or {}).get("graph_priority_key_by_op_id"),
        resource_pair_rank=resource_pair_rank,
    )
    metrics, summary = decoded.metrics, decoded.summary
    candidate = {
        "algo_stats": decoded.algo_stats,
        "results": decoded.results,
        "summary": summary,
        "strategy": decoded.used_strategy,
        "params": decoded.used_params,
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "order": order,
        "metrics": metrics,
        "score": (float(summary.failed_ops),) + objective_score(objective_name, metrics),
        "resource_pool": resource_pool or {},
        "seed_result_count": len(seed_sr_list or []),
        "mutable_scope": _mutable_scope_payload(neighborhood_move, order),
        "neighborhood_move": neighborhood_move.to_report_dict(),
    }
    candidate["resource_pair_rank"] = resource_pair_rank or {}
    candidate["_shared_entry_id"] = decoded.entry_id
    candidate["_archive_observation"] = decoded.archive_observation
    if decoded.receipt is not None:
        candidate["decode_receipt"] = dict(decoded.receipt)
        source_runtime = decoded.receipt.get("source_runtime_ms")
        if source_runtime is not None:
            candidate["runtime_ms"] = source_runtime
    return candidate


def _mutable_scope_payload(neighborhood_move: NeighborhoodMove, order: List[str]) -> Dict[str, Any]:
    return {
        "scope": str(neighborhood_move.input_scope or "batch_order"),
        "batch_count": len(order or []),
        "neighborhood_name": str(neighborhood_move.neighborhood_name),
        "move_kind": str(neighborhood_move.move_kind),
        "dispatch_mode": str(neighborhood_move.dispatch_mode or ""),
        "dispatch_rule": str(neighborhood_move.dispatch_rule or ""),
        "changed_decision_count": int(neighborhood_move.changed_decision_count),
        "fallback_used": bool(neighborhood_move.fallback_used),
        "fallback_reason": str(neighborhood_move.fallback_reason or ""),
    }


__all__ = ["evaluate_local_search_candidate"]
