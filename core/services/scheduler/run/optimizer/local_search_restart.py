"""Restart after a stall: shake the incumbent order and decode it once so current stays aligned."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .attempt_records import evaluate_optional_local_candidate
from .local_search_candidate_eval import evaluate_local_search_candidate
from .local_search_round import stamp_decode_runtime
from .local_search_state import LocalSearchState, resolve_current_strategy_state
from .shared_budget import SharedSearchSkip

if TYPE_CHECKING:
    from .search_report import OptimizationSearchReportState
    from .shared_decode import SharedDecodeSession

RESTART_SHAKE = "restart_shake"


ShakenOrderEvaluator = Callable[
    [List[str], Any, Dict[str, Any], str, str],
    Optional[Dict[str, Any]],
]


@dataclass(frozen=True)
class RestartOutcome:
    strategy: Any
    params: Dict[str, Any]
    dispatch_mode: str
    dispatch_rule: str
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


def _evaluate_restart_candidate(
    *,
    shaken_order: List[str],
    local_state: LocalSearchState,
    strategy: Any,
    params: Dict[str, Any],
    dispatch_mode: str,
    dispatch_rule: str,
    strict_mode: bool,
    start_dt: datetime,
    end_date: Optional[date],
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    optimizer_algo_stats: Optional[Dict[str, Any]],
    readiness_gate_enabled: bool,
    attempts: List[Dict[str, Any]],
    search_report_state: OptimizationSearchReportState,
    decode_session: SharedDecodeSession,
) -> Optional[Dict[str, Any]]:
    """Decode the shaken order once so current's order/score/results come from one evaluation.

    Failures reuse the local candidate failure path: strict mode raises, otherwise a rejected
    attempt is recorded and ``None`` returned. Common-session budget skips propagate to the
    caller with their request receipt.
    """
    best_resource_pool = local_state.best.get("resource_pool")
    candidate_resource_pool = (
        best_resource_pool if isinstance(best_resource_pool, dict) else {}
    ) or resource_pool
    evaluate = partial(
        evaluate_local_search_candidate,
        strict_mode=bool(strict_mode),
        strategy=strategy,
        params=params,
        start_dt=start_dt,
        end_date=end_date,
        order=shaken_order,
        dispatch_mode=dispatch_mode,
        dispatch_rule=dispatch_rule,
        resource_pool=candidate_resource_pool,
        resource_pair_rank=local_state.best.get("resource_pair_rank") or {},
        objective_name=objective_name,
        optimizer_algo_stats=optimizer_algo_stats,
        readiness_gate_enabled=bool(readiness_gate_enabled),
        decode_session=decode_session,
    )
    candidate = evaluate_optional_local_candidate(
        evaluate=evaluate,
        attempts=attempts,
        move=RESTART_SHAKE,
        strategy=strategy,
        dispatch_mode=dispatch_mode,
        dispatch_rule=dispatch_rule,
        strict_mode=bool(strict_mode),
    )
    stamp_decode_runtime(candidate)
    if candidate is not None:
        search_report_state.mark_candidate_evaluated(candidate, origin="local_search_restart")
    return candidate


def restart_after_stall(
    *,
    local_state: LocalSearchState,
    rnd: Any,
    dispatch_mode_cfg: str,
    dispatch_rule_cfg: str,
    evaluate_shaken_order: ShakenOrderEvaluator,
    decode_session: SharedDecodeSession,
) -> RestartOutcome:
    """Shake the incumbent and move current onto the decoded shaken order.

    The shaken order is decoded for real so acceptance compares against its true score and
    the neighborhoods target its real results (A01). The common session owns decision reuse
    and records any skipped request.
    """
    shaken_order = _shake_order(local_state.best.get("order") or local_state.current_order, rnd)
    best_strat, best_params, best_dispatch_mode, best_dispatch_rule = resolve_current_strategy_state(
        local_state.best, dispatch_mode_cfg=dispatch_mode_cfg, dispatch_rule_cfg=dispatch_rule_cfg
    )
    skipped = False
    stop_reason: Optional[str] = None
    rejected_mode: Optional[str] = None
    calls_before = decode_session.actual_decoder_calls
    try:
        candidate = evaluate_shaken_order(
            shaken_order, best_strat, best_params, best_dispatch_mode, best_dispatch_rule,
        )
    except SharedSearchSkip as exc:
        candidate = None
        skipped = True
        if exc.reason in ("estimated_decode_cost", "time_budget"):
            stop_reason = exc.reason
            if stop_reason == "estimated_decode_cost":
                rejected_mode = best_dispatch_mode
    decode_attempted = decode_session.actual_decoder_calls > calls_before
    if candidate is not None:
        local_state.accept_current(candidate)
    elif not skipped:
        # Evaluation failed (strict already raised; non-strict recorded the rejection):
        # drop the shake, current returns to best as one aligned triplet.
        local_state.reset_current_to_best()
    cur_strat, cur_params, cur_dispatch_mode, cur_dispatch_rule = resolve_current_strategy_state(
        local_state.current, dispatch_mode_cfg=dispatch_mode_cfg, dispatch_rule_cfg=dispatch_rule_cfg
    )
    return RestartOutcome(
        strategy=cur_strat,
        params=cur_params,
        dispatch_mode=cur_dispatch_mode,
        dispatch_rule=cur_dispatch_rule,
        decode_attempted=decode_attempted,
        stop_reason=stop_reason,
        rejected_mode=rejected_mode,
    )


__all__ = ["RESTART_SHAKE", "RestartOutcome", "ShakenOrderEvaluator", "restart_after_stall"]
