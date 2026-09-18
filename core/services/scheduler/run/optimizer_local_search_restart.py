"""Restart after a stall: shake the incumbent order and decode it once so current stays aligned."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from core.algorithms import ScheduleResult

from .optimizer_deadline_guard import evaluate_optional_local_or_exhausted
from .optimizer_local_search_candidate_eval import evaluate_local_search_candidate
from .optimizer_local_search_fingerprints import should_skip_seen
from .optimizer_local_search_round import stamp_decode_runtime
from .optimizer_local_search_state import LocalSearchState, resolve_current_strategy_state
from .optimizer_neighborhood_moves import NEIGHBORHOOD_MOVE_SCHEMA_VERSION, NeighborhoodMove
from .optimizer_vns import VnsState

if TYPE_CHECKING:
    from .optimizer_search_report import OptimizationSearchReportState

RESTART_SHAKE = "restart_shake"


ShakenOrderEvaluator = Callable[
    [List[str], NeighborhoodMove, Any, Dict[str, Any], str, str],
    Tuple[Optional[Dict[str, Any]], Optional[str]],
]


@dataclass(frozen=True)
class RestartOutcome:
    strategy: Any
    params: Dict[str, Any]
    dispatch_mode: str
    dispatch_rule: str
    decode_attempted: bool
    budget_exhausted: Optional[str] = None
    # The shaken order was already decoded in this search (no decode, current returns to best).
    duplicate: bool = False


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


def _restart_shake_move(
    *,
    base_order: List[str],
    shaken_order: List[str],
    dispatch_mode: str,
    dispatch_rule: str,
) -> NeighborhoodMove:
    changed = sum(1 for left, right in zip(base_order, shaken_order) if left != right)
    changed += abs(len(base_order) - len(shaken_order))
    mode = str(dispatch_mode or "")
    # Batch-order decodes are identified by the order alone, like the order-only neighborhoods;
    # under sgs the rule takes part in the decode, so the key carries it.
    decision_key: Tuple[Any, ...] = tuple(shaken_order)
    if mode == "sgs":
        decision_key = (RESTART_SHAKE, str(dispatch_rule or ""), tuple(shaken_order))
    return NeighborhoodMove(
        schema_version=NEIGHBORHOOD_MOVE_SCHEMA_VERSION,
        neighborhood_name=RESTART_SHAKE,
        move_kind="shake",
        input_scope="batch_order",
        batch_order=tuple(shaken_order),
        changed_decision_count=changed,
        expected_effect="diversify_after_stall",
        dispatch_mode=mode,
        dispatch_rule=str(dispatch_rule or ""),
        decision_key=decision_key,
        reason="restart_after_stall",
    )


def _evaluate_restart_candidate(
    *,
    shaken_order: List[str],
    move: NeighborhoodMove,
    local_state: LocalSearchState,
    strategy: Any,
    params: Dict[str, Any],
    dispatch_mode: str,
    dispatch_rule: str,
    scheduler: Any,
    strict_mode: bool,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_sr_list: List[ScheduleResult],
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    optimizer_algo_stats: Optional[Dict[str, Any]],
    schedule_fn: Callable[..., Any],
    readiness_gate_enabled: bool,
    graph_ready_context: Optional[Any],
    attempts: List[Dict[str, Any]],
    search_report_state: Optional[OptimizationSearchReportState],
    clock: Callable[[], float],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Decode the shaken order once so current's order/score/results come from one evaluation.

    Failures reuse the local candidate failure path: strict mode raises, otherwise a rejected
    attempt is recorded and ``(None, None)`` returned. A decoder refused by the budget guard
    returns ``(None, reason)`` so the caller stops instead of looping on refusals.
    """
    best_resource_pool = local_state.best.get("resource_pool")
    candidate_resource_pool = (
        dict(best_resource_pool) if isinstance(best_resource_pool, dict) else {}
    ) or resource_pool
    decode_started = clock()
    candidate, budget_exhausted = evaluate_optional_local_or_exhausted(
        evaluate=partial(
            evaluate_local_search_candidate,
            scheduler=scheduler,
            strict_mode=bool(strict_mode),
            algo_ops_to_schedule=algo_ops_to_schedule,
            batches=batches,
            strategy=strategy,
            params=params,
            start_dt=start_dt,
            end_date=end_date,
            downtime_map=downtime_map,
            order=list(shaken_order),
            seed_sr_list=seed_sr_list,
            dispatch_mode=dispatch_mode,
            dispatch_rule=dispatch_rule,
            resource_pool=candidate_resource_pool,
            objective_name=objective_name,
            optimizer_algo_stats=optimizer_algo_stats,
            schedule_fn=schedule_fn,
            readiness_gate_enabled=bool(readiness_gate_enabled),
            graph_ready_context=graph_ready_context,
            neighborhood_move=move,
        ),
        attempts=attempts,
        move=RESTART_SHAKE,
        strategy=strategy,
        dispatch_mode=dispatch_mode,
        dispatch_rule=dispatch_rule,
        strict_mode=bool(strict_mode),
        search_report_state=search_report_state,
    )
    stamp_decode_runtime(candidate, started_at=decode_started, clock=clock)
    return candidate, budget_exhausted


def restart_after_stall(
    *,
    local_state: LocalSearchState,
    rnd: Any,
    dispatch_mode_cfg: str,
    dispatch_rule_cfg: str,
    vns_state: VnsState,
    seen_hashes: set,
    evaluate_shaken_order: ShakenOrderEvaluator,
) -> RestartOutcome:
    """Shake the incumbent and move current onto the decoded shaken order.

    The shaken order is decoded for real so acceptance compares against its true score and
    the neighborhoods target its real results (A01). ``seen_hashes`` persists across restarts:
    a shaken order already decoded in this search is skipped as a duplicate and current returns
    to best, instead of paying a second decode for a known result.
    """
    vns_state.mark_shake()
    shaken_order = _shake_order(list(local_state.best.get("order") or local_state.current_order), rnd)
    best_strat, best_params, best_dispatch_mode, best_dispatch_rule = resolve_current_strategy_state(
        local_state.best, dispatch_mode_cfg=dispatch_mode_cfg, dispatch_rule_cfg=dispatch_rule_cfg
    )
    move = _restart_shake_move(
        base_order=list(local_state.best.get("order") or []),
        shaken_order=list(shaken_order),
        dispatch_mode=best_dispatch_mode,
        dispatch_rule=best_dispatch_rule,
    )
    decode_attempted = False
    budget_exhausted: Optional[str] = None
    duplicate = should_skip_seen(move, seen_hashes)
    if duplicate:
        # The shake is not a registered neighborhood, so it leaves no move row; the vns shake
        # count and the caller's duplicate counter record it.
        local_state.reset_current_to_best()
    else:
        candidate, budget_exhausted = evaluate_shaken_order(
            shaken_order, move, best_strat, best_params, best_dispatch_mode, best_dispatch_rule,
        )
        decode_attempted = budget_exhausted is None
        if candidate is not None:
            local_state.accept_current(candidate)
        else:
            # Evaluation failed (strict already raised; non-strict recorded the rejection) or the
            # budget guard refused: drop the shake, current returns to best as one aligned triplet.
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
        budget_exhausted=budget_exhausted,
        duplicate=duplicate,
    )


__all__ = ["RESTART_SHAKE", "RestartOutcome", "ShakenOrderEvaluator", "restart_after_stall"]
