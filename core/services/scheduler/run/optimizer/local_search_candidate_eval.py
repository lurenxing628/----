from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from core.algorithms.evaluation import objective_score

from .shared_decode import decode_and_metrics

if TYPE_CHECKING:
    from .shared_decode import SharedDecodeSession


def evaluate_local_search_candidate(
    *,
    strict_mode: bool,
    strategy: Any,
    params: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    order: List[str],
    dispatch_mode: str,
    dispatch_rule: str,
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    optimizer_algo_stats: Optional[Dict[str, Any]],
    readiness_gate_enabled: bool,
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
        graph_enabled=False,
        graph_score_enabled=False,
        graph_priority_key_by_op_id=None,
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
    }
    candidate["resource_pair_rank"] = resource_pair_rank or {}
    candidate["_shared_entry_id"] = decoded.entry_id
    candidate["_archive_observation"] = decoded.archive_observation
    if decoded.receipt is not None:
        candidate["decode_receipt"] = decoded.receipt
        source_runtime = decoded.receipt.get("source_runtime_ms")
        if source_runtime is not None:
            candidate["runtime_ms"] = source_runtime
    return candidate


__all__ = ["evaluate_local_search_candidate"]
