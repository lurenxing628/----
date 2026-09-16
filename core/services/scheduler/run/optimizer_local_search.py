from __future__ import annotations

from datetime import date, datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, cast

from core.algorithm_contracts.dispatch_rules import dispatch_rule_search_pool
from core.algorithms import ScheduleResult

from .optimizer_acceptance import ACCEPTANCE_IMPROVE_ONLY
from .optimizer_candidate_profile import derive_iteration_limits
from .optimizer_deadline_guard import (
    can_afford_decode,
    evaluate_optional_local_with_budget,
    guard_decoder,
    observed_decode_seconds,
)
from .optimizer_local_search_candidate_eval import evaluate_local_search_candidate
from .optimizer_local_search_fingerprints import LocalSearchFingerprintTracker
from .optimizer_local_search_round import run_local_search_candidate_round
from .optimizer_local_search_state import LocalSearchState, resolve_current_strategy_state
from .optimizer_neighborhood_moves import (
    BUSINESS_NEIGHBORHOODS,
    DEFAULT_SGS_DISPATCH_RULES,
    NEIGHBORHOOD_MOVE_SCHEMA_VERSION,
    SGS_DISPATCH_RULE,
    NeighborhoodMove,
)
from .optimizer_search_state import init_seen_hashes
from .optimizer_vns import VnsState

if TYPE_CHECKING:
    from .optimizer_search_report import OptimizationSearchReportState

RESTART_SHAKE = "restart_shake"


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
    if now_value >= deadline:
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


def _mark_local_search_entered(search_report_state: Optional[OptimizationSearchReportState]) -> None:
    if search_report_state is not None:
        search_report_state.local_search_entered = True


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


def _restart_shake_move(
    *,
    base_order: List[str],
    shaken_order: List[str],
    dispatch_mode: str,
    dispatch_rule: str,
) -> NeighborhoodMove:
    changed = sum(1 for left, right in zip(base_order, shaken_order) if left != right)
    changed += abs(len(base_order) - len(shaken_order))
    return NeighborhoodMove(
        schema_version=NEIGHBORHOOD_MOVE_SCHEMA_VERSION,
        neighborhood_name=RESTART_SHAKE,
        move_kind="shake",
        input_scope="batch_order",
        batch_order=tuple(shaken_order),
        changed_decision_count=changed,
        expected_effect="diversify_after_stall",
        dispatch_mode=str(dispatch_mode or ""),
        dispatch_rule=str(dispatch_rule or ""),
        decision_key=(RESTART_SHAKE,) + tuple(shaken_order),
        reason="restart_after_stall",
    )


def _evaluate_restart_candidate(
    *,
    shaken_order: List[str],
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
) -> Optional[Dict[str, Any]]:
    """对 restart 的扰动顺序做一次真实评估，产出 order/score/results 对齐的候选。

    失败路径复用既有候选失败处理（evaluate_optional_local_candidate）：strict 模式
    直接抛出，非 strict 记 candidate_rejected 留痕并返回 None。
    """
    move = _restart_shake_move(
        base_order=list(local_state.best.get("order") or []),
        shaken_order=list(shaken_order),
        dispatch_mode=dispatch_mode,
        dispatch_rule=dispatch_rule,
    )
    best_resource_pool = local_state.best.get("resource_pool")
    candidate_resource_pool = (
        dict(best_resource_pool) if isinstance(best_resource_pool, dict) else {}
    ) or resource_pool
    return evaluate_optional_local_with_budget(
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


def _restart_after_stall(
    *,
    local_state: LocalSearchState,
    rnd: Any,
    dispatch_mode_cfg: str,
    dispatch_rule_cfg: str,
    vns_state: VnsState,
    evaluate_shaken_order: Callable[[List[str], Any, Dict[str, Any], str, str], Optional[Dict[str, Any]]],
) -> Tuple[Any, Any, str, str, Optional[set]]:
    vns_state.mark_shake()
    shaken_order = _shake_order(list(local_state.best.get("order") or local_state.current_order), rnd)
    best_strat, best_params, best_dispatch_mode, best_dispatch_rule = resolve_current_strategy_state(
        local_state.best, dispatch_mode_cfg=dispatch_mode_cfg, dispatch_rule_cfg=dispatch_rule_cfg
    )
    # 取舍说明（A01）：restart 在 deadline 预算内多做一次真实评估（schedule_fn）。
    # 一次解码的成本换来 current 的 order/score/results 三元组对齐——接受准则参照扰动点
    # 真实分数（而非 best 分数）、邻域按当前顺序的真实排程结果选靶；否则 improve_only 下
    # 扰动区域的非改进中间步永远走不进去，整段 restart 后的搜索预算被结构性浪费。
    # restart 受 no_improve>=restart_after 节流，频次有界，额外评估成本可控。
    candidate = evaluate_shaken_order(shaken_order, best_strat, best_params, best_dispatch_mode, best_dispatch_rule)
    if candidate is not None:
        local_state.accept_current(candidate)
    else:
        # 扰动顺序评估失败（strict 已抛；非 strict 已按既有失败路径留痕）：
        # 放弃本次扰动，current 完全回到 best，保持三元组一致。
        local_state.reset_current_to_best()
    cur_strat, cur_params, cur_dispatch_mode, cur_dispatch_rule = resolve_current_strategy_state(
        local_state.current, dispatch_mode_cfg=dispatch_mode_cfg, dispatch_rule_cfg=dispatch_rule_cfg
    )
    return (
        cur_strat,
        cur_params,
        cur_dispatch_mode,
        cur_dispatch_rule,
        init_seen_hashes(local_state.current_order, local_state.best),
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

    rnd = rng_factory(int(version))
    _mark_local_search_entered(search_report_state)
    local_state = LocalSearchState.from_best(best, resource_pool=resource_pool)
    cur_strat, cur_params, cur_dispatch_mode, cur_dispatch_rule = resolve_current_strategy_state(
        best, dispatch_mode_cfg=dispatch_mode_cfg, dispatch_rule_cfg=dispatch_rule_cfg
    )
    sgs_dispatch_rules = _resolve_sgs_dispatch_rules(valid_dispatch_rules, cur_dispatch_rule)
    active_neighborhoods = _active_neighborhoods(
        neighborhoods=neighborhoods,
        cur_dispatch_mode=cur_dispatch_mode,
        search_report_state=search_report_state,
    )
    vns_state = VnsState(active_neighborhoods)
    fingerprint_tracker = LocalSearchFingerprintTracker(objective_name=objective_name, initial_best=best)
    it = 0
    it_limit, restart_after = derive_iteration_limits(time_budget_seconds)
    no_improve = 0
    seen_hashes = init_seen_hashes(local_state.current_order, best)

    schedule_fn = guard_decoder(schedule_fn, clock=clock, deadline=deadline, search_report_state=search_report_state,
                                minimum_decode_seconds=observed_decode_seconds(best))
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
        _mark_vns_round(search_report_state, vns_state, best_improved=best_improved, move=move)

        if no_improve >= restart_after:
            no_improve = 0
            cur_strat, cur_params, cur_dispatch_mode, cur_dispatch_rule, seen_hashes = _restart_after_stall(
                local_state=local_state,
                rnd=rnd,
                dispatch_mode_cfg=dispatch_mode_cfg,
                dispatch_rule_cfg=dispatch_rule_cfg,
                vns_state=vns_state,
                evaluate_shaken_order=lambda shaken_order, strategy, params, dispatch_mode, dispatch_rule: _evaluate_restart_candidate(
                    shaken_order=shaken_order,
                    local_state=local_state,
                    strategy=strategy,
                    params=params,
                    dispatch_mode=dispatch_mode,
                    dispatch_rule=dispatch_rule,
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
                    attempts=attempts,
                    search_report_state=search_report_state,
                ),
            )
    return local_state.best


def _resolve_sgs_dispatch_rules(valid_dispatch_rules: Optional[List[str]], current_dispatch_rule: str) -> List[str]:
    # The rule neighborhood searches the registry rules plus the ATC k ladder; the
    # current rule may already be a ladder token adopted by an earlier phase.
    out = list(dispatch_rule_search_pool(valid_dispatch_rules or DEFAULT_SGS_DISPATCH_RULES))
    current = str(current_dispatch_rule or "").strip().lower()
    if current and current not in out:
        out.insert(0, current)
    return out
