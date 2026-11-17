from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Tuple

from core.algorithms.evaluation import objective_score

from .shared_decode import decode_and_metrics

if TYPE_CHECKING:
    from .local_search_state import StrategyState
    from .shared_decode import SharedDecodeSession


def evaluate_local_search_candidate(
    *,
    inherited: StrategyState,
    order: List[str],
    dispatch_mode: str,
    dispatch_rule: str,
    objective_name: str,
    decode_session: SharedDecodeSession,
    resource_pair_rank: Mapping[Tuple[str, str], int],
) -> Dict[str, Any]:
    """Decode a move with the ``inherited`` candidate's strategy and weights and its own dispatch and pair-rank
    overrides, graph scoring off; the candidate records exactly those parameters and no graph-ready profile."""
    decoded = decode_and_metrics(
        decode_session=decode_session,
        objective_name=objective_name,
        strategy=inherited.strategy,
        strategy_params=inherited.params,
        batch_order_override=order,
        dispatch_mode=dispatch_mode,
        dispatch_rule=dispatch_rule,
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
        "params": inherited.params,
        "graph_ready_profile": None,
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "repair_decision": None,
        "order": order,
        "decoded_batch_order": decoded.decoded_batch_order,
        "metrics": metrics,
        "score": (float(summary.failed_ops),) + objective_score(objective_name, metrics),
        "resource_pair_rank": resource_pair_rank,
    }
    candidate["archive_ref"] = decoded.archive_ref()
    candidate["decode_receipt"] = decoded.receipt
    source_runtime = decoded.receipt["source_runtime_ms"]
    if source_runtime is not None:
        candidate["runtime_ms"] = source_runtime
    return candidate


__all__ = ["evaluate_local_search_candidate"]
