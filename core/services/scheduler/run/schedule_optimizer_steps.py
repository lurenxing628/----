from __future__ import annotations

import time
from datetime import date, datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Protocol, Tuple

from core.algorithms import ScheduleResult, SortStrategy
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.greedy.algo_stats import merge_algo_stats, snapshot_algo_stats
from core.infrastructure.errors import ValidationError

from .optimizer_attempt_records import evaluate_optional_start_candidate
from .optimizer_config import (
    ensure_optimizer_config_snapshot,
    is_ortools_enabled,
    ortools_time_limit_seconds,
    weighted_strategy_params,
)
from .optimizer_step_report_hooks import (
    _mark_report_deadline_skip,
    _mark_report_phase_skipped,
    _multi_start_deadline_reached,
    _record_multi_start_candidate,
    _record_ortools_candidate,
    _record_ortools_failure,
    _record_ortools_optional_failure,
)
from .schedule_signature_support import (
    schedule_with_optional_strict_mode as _schedule_with_optional_strict_mode,
)

if TYPE_CHECKING:
    from .optimizer_search_report import OptimizationSearchReportState


class SchedulerLike(Protocol):
    def schedule(self, *args: Any, **kwargs: Any) -> Any:
        ...


def _step_config_snapshot(cfg: Any, *, strict_mode: bool) -> Any:
    return ensure_optimizer_config_snapshot(cfg, strict_mode=bool(strict_mode))


def _solve_ortools_order(
    *,
    deadline: float,
    now: Callable[[], float],
    snapshot: Any,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    start_dt: datetime,
    logger: Any,
) -> Optional[List[str]]:
    from core.algorithms.ortools_bottleneck import try_solve_bottleneck_batch_order

    remaining = float(deadline - now())
    # 时间预算不足时跳过 OR-Tools warm-start：
    # - remaining<=0：避免已经超时仍强行跑 1s
    # - remaining<1：避免 int(remaining)=0 被 tl=max(1,...) 拉回 1s 导致超时
    if remaining < 1.0:
        return None

    tl_cfg = ortools_time_limit_seconds(snapshot)
    tl = max(1, min(int(tl_cfg), int(remaining)))
    return try_solve_bottleneck_batch_order(
        operations=algo_ops_to_schedule,
        batches=batches,
        start_dt=start_dt,
        time_limit_seconds=tl,
        logger=logger,
    )


def _ortools_strategy_params(snapshot: Any, *, strategy: SortStrategy, strict_mode: bool) -> Dict[str, Any]:
    if strategy != SortStrategy.WEIGHTED:
        return {}
    return weighted_strategy_params(snapshot, strict_mode=bool(strict_mode))


def _evaluate_ortools_candidate(
    *,
    scheduler: SchedulerLike,
    strict_mode: bool,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    strategy: SortStrategy,
    params: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    ort_order: List[str],
    seed_sr_list: List[ScheduleResult],
    dispatch_mode_cfg: str,
    dispatch_rule_cfg: str,
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    optimizer_algo_stats: Optional[Dict[str, Any]],
    readiness_gate_enabled: bool,
    graph_ready_context: Optional[Any],
) -> Dict[str, Any]:
    res, summ, used_strat, used_params = _schedule_with_optional_strict_mode(
        scheduler,
        strict_mode=bool(strict_mode),
        operations=algo_ops_to_schedule,
        batches=batches,
        strategy=strategy,
        strategy_params=params,
        start_dt=start_dt,
        end_date=end_date,
        machine_downtimes=downtime_map,
        batch_order_override=list(ort_order),
        seed_results=seed_sr_list,
        dispatch_mode=dispatch_mode_cfg,
        dispatch_rule=dispatch_rule_cfg,
        resource_pool=resource_pool,
        readiness_gate_enabled=bool(readiness_gate_enabled),
        graph_ready_context=graph_ready_context,
    )
    metrics = compute_metrics(res, batches)
    score = (float(summ.failed_ops),) + objective_score(objective_name, metrics)
    algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(scheduler))
    return {
        "results": res,
        "summary": summ,
        "strategy": used_strat,
        "params": used_params,
        "dispatch_mode": dispatch_mode_cfg,
        "dispatch_rule": dispatch_rule_cfg,
        "order": list(ort_order),
        "metrics": metrics,
        "score": score,
        "algo_stats": algo_stats,
    }


def _ortools_warmstart_skip_reason(
    *,
    algo_mode: str,
    snapshot: Any,
    deadline: float,
    now: Callable[[], float],
) -> Optional[str]:
    if algo_mode != "improve":
        return "algo_mode_not_improve"
    if not is_ortools_enabled(snapshot):
        return "disabled"
    if float(deadline - now()) < 1.0:
        return "time_budget"
    return None


def _run_ortools_warmstart(
    *,
    algo_mode: str,
    cfg: Any,
    strategy_enum: SortStrategy,
    objective_name: str,
    deadline: float,
    scheduler: SchedulerLike,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_sr_list: List[ScheduleResult],
    dispatch_mode_cfg: str,
    dispatch_rule_cfg: str,
    resource_pool: Optional[Dict[str, Any]],
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    best: Optional[Dict[str, Any]],
    t_begin: float,
    logger: Any,
    optimizer_algo_stats: Optional[Dict[str, Any]] = None,
    readiness_gate_enabled: bool = False,
    graph_ready_context: Optional[Any] = None,
    strict_mode: bool = False,
    clock: Optional[Callable[[], float]] = None,
    search_report_state: Optional[OptimizationSearchReportState] = None,
) -> Optional[Dict[str, Any]]:
    # 可选：OR-Tools 高质量起点（瓶颈子问题）
    snapshot = _step_config_snapshot(cfg, strict_mode=bool(strict_mode))
    now = clock or time.time

    skip_reason = _ortools_warmstart_skip_reason(algo_mode=algo_mode, snapshot=snapshot, deadline=deadline, now=now)
    if skip_reason == "time_budget":
        _mark_report_deadline_skip(search_report_state, "ortools_warmstart")
        return best
    if skip_reason:
        _mark_report_phase_skipped(search_report_state, "ortools_warmstart", skip_reason)
        return best

    try:
        ort_order = _solve_ortools_order(
            deadline=deadline,
            now=now,
            snapshot=snapshot,
            algo_ops_to_schedule=algo_ops_to_schedule,
            batches=batches,
            start_dt=start_dt,
            logger=logger,
        )
        if not ort_order:
            _mark_report_phase_skipped(search_report_state, "ortools_warmstart", "no_candidate")
            return best
        if now() > deadline:
            _mark_report_deadline_skip(search_report_state, "ortools_warmstart")
            return best

        ort_strat = strategy_enum
        cand = _evaluate_ortools_candidate(
            scheduler=scheduler,
            strict_mode=bool(strict_mode),
            algo_ops_to_schedule=algo_ops_to_schedule,
            batches=batches,
            strategy=ort_strat,
            params=_ortools_strategy_params(snapshot, strategy=ort_strat, strict_mode=bool(strict_mode)),
            start_dt=start_dt,
            end_date=end_date,
            downtime_map=downtime_map,
            ort_order=list(ort_order),
            seed_sr_list=seed_sr_list,
            dispatch_mode_cfg=dispatch_mode_cfg,
            dispatch_rule_cfg=dispatch_rule_cfg,
            resource_pool=resource_pool,
            objective_name=objective_name,
            optimizer_algo_stats=optimizer_algo_stats,
            readiness_gate_enabled=bool(readiness_gate_enabled),
            graph_ready_context=graph_ready_context,
        )
        best = _record_ortools_candidate(
            best=best,
            candidate=cand,
            attempts=attempts,
            improvement_trace=improvement_trace,
            search_report_state=search_report_state,
            now=now,
            t_begin=t_begin,
        )
    except ValidationError as e:
        if bool(strict_mode):
            raise
        _record_ortools_optional_failure(
            attempts=attempts,
            strategy=strategy_enum,
            dispatch_mode=dispatch_mode_cfg,
            dispatch_rule=dispatch_rule_cfg,
            search_report_state=search_report_state,
            optimizer_algo_stats=optimizer_algo_stats,
            scheduler=scheduler,
            logger=logger,
            exc=e,
        )
    except Exception as e:
        _record_ortools_optional_failure(
            attempts=attempts,
            strategy=strategy_enum,
            dispatch_mode=dispatch_mode_cfg,
            dispatch_rule=dispatch_rule_cfg,
            search_report_state=search_report_state,
            optimizer_algo_stats=optimizer_algo_stats,
            scheduler=scheduler,
            logger=logger,
            exc=e,
        )
    return best


__all__ = [
    "_record_ortools_failure",
    "_run_multi_start",
    "_run_ortools_warmstart",
]


def _dispatch_rules_for_mode(dispatch_mode: str, dispatch_rule_cfg: str, valid_dispatch_rules: List[str]) -> List[str]:
    if dispatch_mode != "sgs":
        return [dispatch_rule_cfg]
    return [dispatch_rule_cfg] + [rule for rule in valid_dispatch_rules if rule != dispatch_rule_cfg]


def _resolve_multi_start_strategy_params(
    *,
    strategy: SortStrategy,
    cfg: Any,
    strict_mode: bool,
    optimizer_algo_stats: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if strategy != SortStrategy.WEIGHTED:
        return {}
    return weighted_strategy_params(cfg, strict_mode=bool(strict_mode))


def _get_cached_multi_start_order(
    *,
    strategy: SortStrategy,
    params: Dict[str, Any],
    order_cache: Dict[Tuple[str, Tuple[Tuple[str, Any], ...]], List[str]],
    build_order: Any,
) -> List[str]:
    cache_key = (str(strategy.value), tuple(sorted((str(key), value) for key, value in (params or {}).items())))
    if cache_key not in order_cache:
        order_cache[cache_key] = list(build_order(strategy, params))
    return list(order_cache[cache_key])


def _evaluate_multi_start_candidate(
    *,
    scheduler: SchedulerLike,
    strict_mode: bool,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    strategy: SortStrategy,
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
    readiness_gate_enabled: bool,
    graph_ready_context: Optional[Any],
) -> Dict[str, Any]:
    res, summ, used_strat, used_params = _schedule_with_optional_strict_mode(
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
    score = (float(summ.failed_ops),) + objective_score(objective_name, metrics)
    algo_stats = merge_algo_stats(optimizer_algo_stats, snapshot_algo_stats(scheduler))
    return {
        "results": res,
        "summary": summ,
        "strategy": used_strat,
        "params": used_params,
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "order": order,
        "metrics": metrics,
        "score": score,
        "algo_stats": algo_stats,
    }


def _run_multi_start(
    *,
    keys: List[str],
    dispatch_modes: List[str],
    dispatch_rule_cfg: str,
    valid_dispatch_rules: List[str],
    scheduler: SchedulerLike,
    algo_ops_to_schedule: List[Any],
    batches: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
    seed_sr_list: List[ScheduleResult],
    cfg: Any,
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    deadline: float,
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    best: Optional[Dict[str, Any]],
    t_begin: float,
    build_order: Any,
    optimizer_algo_stats: Optional[Dict[str, Any]] = None,
    readiness_gate_enabled: bool = False,
    graph_ready_context: Optional[Any] = None,
    strict_mode: bool = False,
    clock: Optional[Callable[[], float]] = None,
    search_report_state: Optional[OptimizationSearchReportState] = None,
) -> Optional[Dict[str, Any]]:
    order_cache: Dict[Tuple[str, Tuple[Tuple[str, Any], ...]], List[str]] = {}
    snapshot = _step_config_snapshot(cfg, strict_mode=bool(strict_mode))
    now = clock or time.time
    primary = (
        str(keys[0]) if keys else "",
        str(dispatch_modes[0]) if dispatch_modes else "",
        str(dispatch_rule_cfg),
    )

    # 执行策略轮询（multi-start）
    for dm in dispatch_modes:
        if _multi_start_deadline_reached(now=now, deadline=deadline, search_report_state=search_report_state):
            break
        dispatch_rules = _dispatch_rules_for_mode(dm, dispatch_rule_cfg, valid_dispatch_rules)
        for k in keys:
            if _multi_start_deadline_reached(now=now, deadline=deadline, search_report_state=search_report_state):
                break
            strat = SortStrategy(k)
            params0 = _resolve_multi_start_strategy_params(
                strategy=strat,
                cfg=snapshot,
                strict_mode=bool(strict_mode),
                optimizer_algo_stats=optimizer_algo_stats,
            )

            for dr in dispatch_rules:
                if _multi_start_deadline_reached(now=now, deadline=deadline, search_report_state=search_report_state):
                    break
                order = _get_cached_multi_start_order(
                    strategy=strat,
                    params=params0,
                    order_cache=order_cache,
                    build_order=build_order,
                )
                cand = evaluate_optional_start_candidate(
                    evaluate=partial(
                        _evaluate_multi_start_candidate,
                        scheduler=scheduler,
                        strict_mode=bool(strict_mode),
                        algo_ops_to_schedule=algo_ops_to_schedule,
                        batches=batches,
                        strategy=strat,
                        params=params0,
                        start_dt=start_dt,
                        end_date=end_date,
                        downtime_map=downtime_map,
                        order=order,
                        seed_sr_list=seed_sr_list,
                        dispatch_mode=dm,
                        dispatch_rule=dr,
                        resource_pool=resource_pool,
                        objective_name=objective_name,
                        optimizer_algo_stats=optimizer_algo_stats,
                        readiness_gate_enabled=bool(readiness_gate_enabled),
                        graph_ready_context=graph_ready_context,
                    ),
                    attempts=attempts,
                    strategy_key=k,
                    dispatch_mode=dm,
                    dispatch_rule=dr,
                    primary=primary,
                    strict_mode=bool(strict_mode),
                    search_report_state=search_report_state,
                )
                if cand is None:
                    continue
                best = _record_multi_start_candidate(
                    best=best,
                    candidate=cand,
                    strategy_key=k,
                    dispatch_mode=dm,
                    dispatch_rule=dr,
                    attempts=attempts,
                    improvement_trace=improvement_trace,
                    search_report_state=search_report_state,
                    now=now,
                    t_begin=t_begin,
                )
    return best
