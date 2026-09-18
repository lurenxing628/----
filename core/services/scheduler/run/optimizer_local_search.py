from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, cast

from core.algorithm_contracts.dispatch_rules import dispatch_rule_search_pool
from core.algorithms import ScheduleResult

from .optimizer_acceptance import ACCEPTANCE_IMPROVE_ONLY
from .optimizer_deadline_guard import can_afford_decode, guard_decoder, observed_decode_seconds
from .optimizer_local_search_fingerprints import LocalSearchFingerprintTracker
from .optimizer_local_search_limits import (
    STOP_ITERATION_LIMIT,
    STOP_SEARCH_EXHAUSTED,
    STOP_TIME_BUDGET,
    LocalSearchCounters,
    LocalSearchLimits,
    derive_local_search_limits,
    local_search_stop_reason,
)
from .optimizer_local_search_restart import (
    RESTART_SHAKE,
    RestartOutcome,
    _evaluate_restart_candidate,
    restart_after_stall,
)
from .optimizer_local_search_round import LocalSearchRoundResult, run_local_search_candidate_round
from .optimizer_local_search_state import LocalSearchState, resolve_current_strategy_state
from .optimizer_neighborhood_moves import BUSINESS_NEIGHBORHOODS, DEFAULT_SGS_DISPATCH_RULES, SGS_DISPATCH_RULE
from .optimizer_search_state import init_seen_hashes
from .optimizer_vns import VnsState

if TYPE_CHECKING:
    from .optimizer_search_report import OptimizationSearchReportState

__all__ = ["RESTART_SHAKE", "run_local_search"]


def _local_search_skip_reason(
    *,
    algo_mode: str,
    best: Optional[Dict[str, Any]],
) -> Tuple[Optional[str], Dict[str, Any]]:
    if algo_mode != "improve":
        return "algo_mode_not_improve", {}
    if best is None:
        return "best_missing", {}
    order_length = len(best.get("order") or [])
    if order_length < 2:
        return "order_too_short", {"order_length": order_length}
    return None, {}


def _mark_local_search_skipped(search_report_state: Optional[OptimizationSearchReportState], reason: str, extra: Dict[str, Any]) -> None:
    if search_report_state is not None:
        search_report_state.mark_phase_skipped("local_search", reason, **extra)


def _local_search_stop_reason(*, now_value: float, deadline: float, iteration: int, iteration_limit: int) -> Optional[str]:
    """Deadline-boundary contract: the deadline instant itself already stops the search."""
    return local_search_stop_reason(
        now_value=now_value, deadline=deadline, decodes=iteration, decode_limit=iteration_limit,
        idle_rounds=0, idle_round_limit=1,
    )


def _budget_stop_reason(budget_exhausted: Optional[str]) -> Optional[str]:
    # A guard refusal means the slice cannot pay for one more decode: the time budget stopped
    # the search, whether the deadline instant passed or the measured decode cost no longer fits.
    return STOP_TIME_BUDGET if budget_exhausted else None


def _mark_local_search_stop(
    search_report_state: Optional[OptimizationSearchReportState],
    reason: str,
    *,
    detail: Optional[str],
    counters: LocalSearchCounters,
    limits: LocalSearchLimits,
) -> None:
    if search_report_state is None:
        return
    if reason == STOP_TIME_BUDGET:
        search_report_state.mark_deadline_reached()
    elif reason == STOP_ITERATION_LIMIT:
        search_report_state.mark_iteration_limit_reached()
    elif reason == STOP_SEARCH_EXHAUSTED:
        search_report_state.mark_search_exhausted()
    stop = dict(counters.to_report_dict(), reason=str(reason), limits=limits.to_report_dict())
    if detail:
        stop["detail"] = str(detail)
    search_report_state.update_candidate_profile(local_search_stop=stop)


def _mark_local_search_entered(search_report_state: Optional[OptimizationSearchReportState], limits: LocalSearchLimits) -> None:
    if search_report_state is not None:
        search_report_state.local_search_entered = True
        search_report_state.update_candidate_profile(local_search_limits=limits.to_report_dict())


def _active_neighborhoods(
    *,
    neighborhoods: Optional[Tuple[str, ...]],
    cur_dispatch_mode: str,
    search_report_state: Optional[OptimizationSearchReportState],
) -> Tuple[str, ...]:
    configured = tuple(neighborhoods or BUSINESS_NEIGHBORHOODS)
    active = (SGS_DISPATCH_RULE,) if cur_dispatch_mode == "sgs" else configured
    if search_report_state is not None:
        search_report_state.set_effective_neighborhoods(
            configured=configured,
            effective=active,
            reason="sgs_dispatch_rule_only" if cur_dispatch_mode == "sgs" else "configured_neighborhoods",
            dispatch_mode=cur_dispatch_mode,
        )
    return active


def _mark_vns_round(
    search_report_state: Optional[OptimizationSearchReportState],
    vns_state: VnsState,
    *,
    best_improved: bool,
    move: Any,
) -> None:
    vns_event = vns_state.record_round(
        best_improved=best_improved,
        noop=bool(move.noop),
        fallback_used=bool(move.fallback_used),
    )
    if search_report_state is not None:
        search_report_state.mark_vns_event(vns_event)


def _resolve_sgs_dispatch_rules(valid_dispatch_rules: Optional[List[str]], current_dispatch_rule: str) -> List[str]:
    # The rule neighborhood searches the registry rules plus the ATC k ladder; the
    # current rule may already be a ladder token adopted by an earlier phase.
    out = list(dispatch_rule_search_pool(valid_dispatch_rules or DEFAULT_SGS_DISPATCH_RULES))
    current = str(current_dispatch_rule or "").strip().lower()
    if current and current not in out:
        out.insert(0, current)
    return out


class _LocalSearchRun:
    """One local search over the incumbent: the decode inputs shared by every round and restart."""

    def __init__(self, **decode_inputs: Any) -> None:
        self.inputs = decode_inputs

    def round(self, *, local_state: LocalSearchState, vns_state: VnsState, strategy_state: Tuple[Any, Any, str, str],
              seen_hashes: set, counters: LocalSearchCounters, limits: LocalSearchLimits, started_at: float) -> LocalSearchRoundResult:
        cur_strat, cur_params, cur_dispatch_mode, cur_dispatch_rule = strategy_state
        return run_local_search_candidate_round(
            local_state=local_state, vns_state=vns_state, cur_strat=cur_strat, cur_params=cur_params,
            cur_dispatch_mode=cur_dispatch_mode, cur_dispatch_rule=cur_dispatch_rule, seen_hashes=seen_hashes,
            no_improve=counters.no_improve, iteration=counters.decodes, iteration_limit=limits.decode_limit,
            started_at=started_at, **self.inputs,
        )

    def restart(self, *, local_state: LocalSearchState, vns_state: VnsState, seen_hashes: set,
                dispatch_mode_cfg: str, dispatch_rule_cfg: str) -> RestartOutcome:
        inputs = self.inputs

        def _evaluate(shaken_order: List[str], move: Any, strategy: Any, params: Dict[str, Any],
                      dispatch_mode: str, dispatch_rule: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
            return _evaluate_restart_candidate(
                shaken_order=shaken_order, move=move, local_state=local_state, strategy=strategy, params=params,
                dispatch_mode=dispatch_mode, dispatch_rule=dispatch_rule, scheduler=inputs["scheduler"],
                strict_mode=inputs["strict_mode"], algo_ops_to_schedule=inputs["algo_ops_to_schedule"],
                batches=inputs["batches"], start_dt=inputs["start_dt"], end_date=inputs["end_date"],
                downtime_map=inputs["downtime_map"], seed_sr_list=inputs["seed_sr_list"],
                resource_pool=inputs["resource_pool"], objective_name=inputs["objective_name"],
                optimizer_algo_stats=inputs["optimizer_algo_stats"], schedule_fn=inputs["schedule_fn"],
                readiness_gate_enabled=inputs["readiness_gate_enabled"], graph_ready_context=inputs["graph_ready_context"],
                attempts=inputs["attempts"], search_report_state=inputs["search_report_state"], clock=inputs["clock"],
            )

        return restart_after_stall(
            local_state=local_state, rnd=inputs["rnd"], dispatch_mode_cfg=dispatch_mode_cfg,
            dispatch_rule_cfg=dispatch_rule_cfg, vns_state=vns_state, seen_hashes=seen_hashes,
            evaluate_shaken_order=_evaluate,
        )


def run_local_search(
    *,
    algo_mode: str,
    best: Optional[Dict[str, Any]],
    version: int,
    time_budget_seconds: int,
    deadline: float,
    scheduler: Any,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_sr_list: List[ScheduleResult],
    dispatch_mode_cfg: str,
    dispatch_rule_cfg: str,
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    optimizer_algo_stats: Optional[Dict[str, Any]],
    t_begin: float,
    readiness_gate_enabled: bool,
    strict_mode: bool,
    clock: Callable[[], float],
    rng_factory: Callable[[int], Any],
    schedule_fn: Callable[..., Any],
    graph_ready_context: Optional[Any] = None,
    search_report_state: Optional[OptimizationSearchReportState] = None,
    neighborhoods: Optional[Tuple[str, ...]] = None,
    valid_dispatch_rules: Optional[List[str]] = None,
    acceptance: str = ACCEPTANCE_IMPROVE_ONLY,
) -> Optional[Dict[str, Any]]:
    """Improve the incumbent until the slice, the decode limit or the neighborhood is exhausted.

    An iteration is one decoder invocation. Rounds whose move is a no-op or a decision already
    decoded in this search cost nothing and only lengthen an idle streak; ``time_budget_seconds``
    stays in the signature for the profile contract, the runtime limits come from the remaining
    slice and the incumbent's measured decode cost.
    """
    del time_budget_seconds
    skip_reason, skip_extra = _local_search_skip_reason(algo_mode=algo_mode, best=best)
    if skip_reason:
        _mark_local_search_skipped(search_report_state, skip_reason, skip_extra)
        return best
    if graph_ready_context is not None:
        _mark_local_search_skipped(search_report_state, "graph_ready_uses_graph_candidate_phase", {})
        return best
    best = cast(Dict[str, Any], best)
    if not can_afford_decode(best, clock=clock, deadline=deadline, search_report_state=search_report_state, phase="local_search"):
        return best

    decode_cost = observed_decode_seconds(best)
    local_state = LocalSearchState.from_best(best, resource_pool=resource_pool)
    strategy_state = resolve_current_strategy_state(best, dispatch_mode_cfg=dispatch_mode_cfg, dispatch_rule_cfg=dispatch_rule_cfg)
    active_neighborhoods = _active_neighborhoods(
        neighborhoods=neighborhoods, cur_dispatch_mode=strategy_state[2], search_report_state=search_report_state,
    )
    # One clock reading per round: the first reading sizes the limits and starts the first decode.
    entered_at = clock()
    limits = derive_local_search_limits(
        remaining_seconds=deadline - entered_at, decode_cost_seconds=decode_cost, neighborhood_count=len(active_neighborhoods),
    )
    _mark_local_search_entered(search_report_state, limits)
    vns_state = VnsState(active_neighborhoods)
    seen_hashes = init_seen_hashes(local_state.current_order, best)
    counters = LocalSearchCounters()
    run = _LocalSearchRun(
        attempts=attempts, improvement_trace=improvement_trace, rnd=rng_factory(int(version)),
        search_report_state=search_report_state, acceptance=acceptance, version=version, scheduler=scheduler,
        strict_mode=strict_mode, algo_ops_to_schedule=algo_ops_to_schedule, batches=batches, start_dt=start_dt,
        end_date=end_date, downtime_map=downtime_map, seed_sr_list=seed_sr_list, resource_pool=resource_pool,
        objective_name=objective_name, optimizer_algo_stats=optimizer_algo_stats,
        schedule_fn=guard_decoder(schedule_fn, clock=clock, deadline=deadline, search_report_state=search_report_state,
                                  minimum_decode_seconds=decode_cost),
        readiness_gate_enabled=readiness_gate_enabled, graph_ready_context=graph_ready_context,
        valid_dispatch_rules=_resolve_sgs_dispatch_rules(valid_dispatch_rules, strategy_state[3]),
        fingerprint_tracker=LocalSearchFingerprintTracker(objective_name=objective_name, initial_best=best),
        clock=clock, t_begin=t_begin,
    )
    stop_detail: Optional[str] = None
    now_value: Optional[float] = entered_at
    while True:
        now_value = clock() if now_value is None else now_value
        stop_reason = local_search_stop_reason(
            now_value=now_value, deadline=deadline, decodes=counters.decodes, decode_limit=limits.decode_limit,
            idle_rounds=counters.idle_rounds, idle_round_limit=limits.idle_round_limit,
        )
        if stop_reason:
            break
        outcome = run.round(
            local_state=local_state, vns_state=vns_state, strategy_state=strategy_state, seen_hashes=seen_hashes,
            counters=counters, limits=limits, started_at=now_value,
        )
        now_value = None
        counters.record_round(decode_attempted=outcome.decode_attempted, duplicate=outcome.duplicate, noop=bool(outcome.move.noop))
        counters.no_improve = outcome.no_improve
        if search_report_state is not None:
            search_report_state.set_iterations(counters.decodes)
        strategy_state = resolve_current_strategy_state(
            local_state.current, dispatch_mode_cfg=dispatch_mode_cfg, dispatch_rule_cfg=dispatch_rule_cfg
        )
        _mark_vns_round(search_report_state, vns_state, best_improved=outcome.best_improved, move=outcome.move)
        stop_reason, stop_detail = _budget_stop_reason(outcome.budget_exhausted), outcome.budget_exhausted
        if stop_reason:
            break
        if counters.no_improve >= limits.restart_after:
            counters.no_improve = 0
            restart = run.restart(
                local_state=local_state, vns_state=vns_state, seen_hashes=seen_hashes,
                dispatch_mode_cfg=dispatch_mode_cfg, dispatch_rule_cfg=dispatch_rule_cfg,
            )
            counters.record_round(decode_attempted=restart.decode_attempted, duplicate=restart.duplicate)
            if search_report_state is not None:
                search_report_state.set_iterations(counters.decodes)
            strategy_state = (restart.strategy, restart.params, restart.dispatch_mode, restart.dispatch_rule)
            stop_reason, stop_detail = _budget_stop_reason(restart.budget_exhausted), restart.budget_exhausted
            if stop_reason:
                break
    _mark_local_search_stop(search_report_state, stop_reason, detail=stop_detail, counters=counters, limits=limits)
    return local_state.best
