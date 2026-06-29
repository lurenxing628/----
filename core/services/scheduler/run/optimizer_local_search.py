from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, cast

from core.algorithms import ScheduleResult

from .optimizer_acceptance import ACCEPTANCE_IMPROVE_ONLY
from .optimizer_candidate_profile import derive_iteration_limits
from .optimizer_local_search_fingerprints import LocalSearchFingerprintTracker
from .optimizer_local_search_round import run_local_search_candidate_round
from .optimizer_local_search_state import LocalSearchState, resolve_current_strategy_state
from .optimizer_neighborhood_moves import (
    BUSINESS_NEIGHBORHOODS,
    DEFAULT_SGS_DISPATCH_RULES,
    SGS_DISPATCH_RULE,
)
from .optimizer_search_state import init_seen_hashes
from .optimizer_vns import VnsState

if TYPE_CHECKING:
    from .optimizer_search_report import OptimizationSearchReportState


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
    if now_value > deadline:
        return "time_budget"
    if iteration >= iteration_limit:
        return "iteration_limit"
    return None


def _mark_local_search_stop(search_report_state: Optional[OptimizationSearchReportState], reason: str) -> None:
    if search_report_state is None:
        return
    if reason == "time_budget":
        search_report_state.mark_deadline_reached()
    elif reason == "iteration_limit":
        search_report_state.mark_iteration_limit_reached()


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
    skip_reason, skip_extra = _local_search_skip_reason(algo_mode=algo_mode, best=best)
    if skip_reason:
        _mark_local_search_skipped(search_report_state, skip_reason, skip_extra)
        return best
    if graph_ready_context is not None:
        _mark_local_search_skipped(search_report_state, "graph_ready_requires_graph_neighborhood", {})
        return best
    best = cast(Dict[str, Any], best)

    rnd = rng_factory(int(version))
    if search_report_state is not None:
        search_report_state.local_search_entered = True
    local_state = LocalSearchState.from_best(best, resource_pool=resource_pool)
    cur_strat, cur_params, cur_dispatch_mode, cur_dispatch_rule = resolve_current_strategy_state(
        best, dispatch_mode_cfg=dispatch_mode_cfg, dispatch_rule_cfg=dispatch_rule_cfg
    )
    sgs_dispatch_rules = _resolve_sgs_dispatch_rules(valid_dispatch_rules, cur_dispatch_rule)
    active_neighborhoods = (SGS_DISPATCH_RULE,) if cur_dispatch_mode == "sgs" else tuple(neighborhoods or BUSINESS_NEIGHBORHOODS)
    if search_report_state is not None:
        search_report_state.set_effective_neighborhoods(
            configured=tuple(neighborhoods or BUSINESS_NEIGHBORHOODS),
            effective=active_neighborhoods,
            reason="sgs_dispatch_rule_only" if cur_dispatch_mode == "sgs" else "configured_neighborhoods",
            dispatch_mode=cur_dispatch_mode,
        )
    vns_state = VnsState(active_neighborhoods)
    fingerprint_tracker = LocalSearchFingerprintTracker(objective_name=objective_name, initial_best=best)
    it = 0
    it_limit, restart_after = derive_iteration_limits(time_budget_seconds)
    no_improve = 0
    seen_hashes = init_seen_hashes(local_state.current_order, best)

    while True:
        now_value = clock()
        stop_reason = _local_search_stop_reason(
            now_value=now_value,
            deadline=deadline,
            iteration=it,
            iteration_limit=it_limit,
        )
        if stop_reason:
            _mark_local_search_stop(search_report_state, stop_reason)
            break
        it += 1
        if search_report_state is not None:
            search_report_state.set_iterations(it)

        no_improve, _accepted_current, best_improved, move = run_local_search_candidate_round(
            local_state=local_state,
            vns_state=vns_state,
            attempts=attempts,
            improvement_trace=improvement_trace,
            cur_strat=cur_strat,
            cur_params=cur_params,
            cur_dispatch_mode=cur_dispatch_mode,
            cur_dispatch_rule=cur_dispatch_rule,
            seen_hashes=seen_hashes,
            rnd=rnd,
            search_report_state=search_report_state,
            no_improve=no_improve,
            acceptance=acceptance,
            version=version,
            iteration=it,
            iteration_limit=it_limit,
            scheduler=scheduler,
            strict_mode=strict_mode,
            algo_ops_to_schedule=algo_ops_to_schedule,
            batches=batches,
            start_dt=start_dt,
            end_date=end_date,
            downtime_map=downtime_map,
            seed_sr_list=seed_sr_list,
            resource_pool=resource_pool,
            objective_name=objective_name,
            optimizer_algo_stats=optimizer_algo_stats,
            schedule_fn=schedule_fn,
            readiness_gate_enabled=readiness_gate_enabled,
            graph_ready_context=graph_ready_context,
            valid_dispatch_rules=sgs_dispatch_rules,
            fingerprint_tracker=fingerprint_tracker,
            clock=clock,
            t_begin=t_begin,
        )
        cur_strat, cur_params, cur_dispatch_mode, cur_dispatch_rule = resolve_current_strategy_state(
            local_state.current, dispatch_mode_cfg=dispatch_mode_cfg, dispatch_rule_cfg=dispatch_rule_cfg
        )
        vns_event = vns_state.record_round(
            best_improved=best_improved,
            noop=bool(move.noop),
            fallback_used=bool(move.fallback_used),
        )
        if search_report_state is not None:
            search_report_state.mark_vns_event(
                vns_event
            )

        if no_improve >= restart_after:
            no_improve = 0
            vns_state.mark_shake()
            local_state.reset_current_to_best(
                order=_shake_order(list(local_state.best.get("order") or local_state.current_order), rnd)
            )
            cur_strat, cur_params, cur_dispatch_mode, cur_dispatch_rule = resolve_current_strategy_state(
                local_state.current, dispatch_mode_cfg=dispatch_mode_cfg, dispatch_rule_cfg=dispatch_rule_cfg
            )
            seen_hashes = init_seen_hashes(local_state.current_order, local_state.best)
    return local_state.best


def _resolve_sgs_dispatch_rules(valid_dispatch_rules: Optional[List[str]], current_dispatch_rule: str) -> List[str]:
    out: List[str] = []
    for item in list(valid_dispatch_rules or DEFAULT_SGS_DISPATCH_RULES):
        text = str(item or "").strip().lower()
        if text and text not in out:
            out.append(text)
    current = str(current_dispatch_rule or "").strip().lower()
    if current and current not in out:
        out.insert(0, current)
    if not out:
        out.extend(DEFAULT_SGS_DISPATCH_RULES)
    return out
