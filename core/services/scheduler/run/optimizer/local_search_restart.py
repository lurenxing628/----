"""Restart after a stall: shake the incumbent order and decode it once so current stays aligned."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .local_search_candidate_eval import evaluate_local_search_candidate
from .local_search_round import stamp_decode_runtime
from .local_search_state import LocalSearchState, StrategyState, resolve_current_strategy_state
from .shared_budget import SharedSearchSkip

if TYPE_CHECKING:
    from .search_report import OptimizationSearchReportState
    from .shared_decode import SharedDecodeSession

ShakenOrderEvaluator = Callable[[List[str], StrategyState], Dict[str, Any]]


@dataclass(frozen=True)
class RestartOutcome:
    strategy_state: StrategyState
    decode_attempted: bool
    stop_reason: Optional[str] = None
    rejected_mode: Optional[str] = None


def _shake_order(order: List[str], rnd: Any) -> List[str]:
    cur_order = list(order)
    shake = rnd.randint(3, 8)
    for _ in range(shake):
        if len(cur_order) < 2:
            break
        if rnd.random() < 0.6:
            i, j = rnd.sample(range(len(cur_order)), 2)
            cur_order[i], cur_order[j] = cur_order[j], cur_order[i]
        else:
            i = rnd.randrange(len(cur_order))
            j = rnd.randrange(len(cur_order))
            item = cur_order.pop(i)
            cur_order.insert(j, item)
    return cur_order


def evaluate_restart_candidate(
    *,
    shaken_order: List[str],
    local_state: LocalSearchState,
    inherited: StrategyState,
    objective_name: str,
    search_report_state: OptimizationSearchReportState,
    decode_session: SharedDecodeSession,
) -> Dict[str, Any]:
    """Decode the shaken order once so current's order/score/results come from one evaluation.

    Evaluation failures propagate; common-session budget skips propagate to the caller with
    their request receipt.
    """
    candidate = evaluate_local_search_candidate(
        inherited=inherited,
        order=shaken_order,
        dispatch_mode=inherited.dispatch_mode,
        dispatch_rule=inherited.dispatch_rule,
        # A restart shakes the incumbent: it keeps best's pair-rank overrides, as it keeps best's strategy.
        resource_pair_rank=local_state.best["resource_pair_rank"],
        objective_name=objective_name,
        decode_session=decode_session,
    )
    stamp_decode_runtime(candidate)
    search_report_state.mark_candidate_evaluated(candidate, origin="local_search_restart")
    return candidate


def restart_after_stall(
    *,
    local_state: LocalSearchState,
    rnd: Any,
    evaluate_shaken_order: ShakenOrderEvaluator,
    decode_session: SharedDecodeSession,
) -> RestartOutcome:
    """Shake the incumbent and move current onto the decoded shaken order.

    The shaken order is decoded for real so acceptance compares against its true score and
    the neighborhoods target its real results (A01). The common session owns decision reuse
    and records any skipped request.
    """
    shaken_order = _shake_order(local_state.best.get("order") or local_state.current_order, rnd)
    best_state = resolve_current_strategy_state(local_state.best)
    stop_reason: Optional[str] = None
    rejected_mode: Optional[str] = None
    calls_before = decode_session.actual_decoder_calls
    try:
        candidate = evaluate_shaken_order(shaken_order, best_state)
    except SharedSearchSkip as exc:
        if exc.reason in ("estimated_decode_cost", "time_budget"):
            stop_reason = exc.reason
            if stop_reason == "estimated_decode_cost":
                rejected_mode = best_state.dispatch_mode
    else:
        local_state.accept_current(candidate)
    decode_attempted = decode_session.actual_decoder_calls > calls_before
    return RestartOutcome(
        strategy_state=resolve_current_strategy_state(local_state.current),
        decode_attempted=decode_attempted,
        stop_reason=stop_reason,
        rejected_mode=rejected_mode,
    )


__all__ = ["RestartOutcome", "ShakenOrderEvaluator", "evaluate_restart_candidate", "restart_after_stall"]
