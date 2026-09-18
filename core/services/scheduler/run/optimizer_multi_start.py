"""Multi-start construction, evaluation and safe decision deduplication."""
from __future__ import annotations

import math
import time
from datetime import date, datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterator, List, Optional, Tuple

from core.algorithm_contracts.dispatch_rules import dispatch_rule_search_pool
from core.algorithms import ScheduleResult, SortStrategy
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.greedy.algo_stats import merge_algo_stats, snapshot_algo_stats

from .optimizer_attempt_records import candidate_tag, evaluate_optional_start_candidate
from .optimizer_config import ensure_optimizer_config_snapshot, weighted_strategy_params
from .optimizer_multi_start_dedup import MultiStartDecisionCache
from .optimizer_step_report_hooks import _multi_start_deadline_reached, _record_multi_start_candidate
from .schedule_signature_support import schedule_with_optional_strict_mode as _schedule_with_optional_strict_mode

if TYPE_CHECKING:
    from .optimizer_search_report import OptimizationSearchReportState
    from .schedule_optimizer_steps import SchedulerLike


GRAPH_RULE_SCOPE_CONFIGURED_ONLY = "configured_only"
GRAPH_RULE_SCOPE_REGISTRY_AND_LADDER = "registry_and_ladder"


def _finite_key(value: Any) -> Optional[Tuple[float, ...]]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)) or not value:
        return None
    out: List[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)):
            return None
        out.append(float(item))
    return tuple(out)


def graph_rule_search_scope(graph_ready_context: Optional[Any]) -> Optional[Dict[str, Any]]:
    """How many rule starts a graph candidate needs, proven from the graph priority keys.

    SGS compares ``(penalty, *graph_key, *dispatch_key)`` and every schedulable operation must
    carry a graph key (the decoder rejects a missing one). When all keys are pairwise distinct
    the dispatch rule never breaks a tie, so every rule decodes the same schedule and only the
    configured rule is started. Ties hand the decision to the rule key, so the registry rules and
    the ATC k ladder are all worth a start. Returns None without a graph context.
    """
    if graph_ready_context is None:
        return None
    if not isinstance(graph_ready_context, dict):
        return {"policy": GRAPH_RULE_SCOPE_REGISTRY_AND_LADDER, "reason": "graph_context_not_mapping"}
    if graph_ready_context.get("score_enabled") is not True:
        return {"policy": GRAPH_RULE_SCOPE_REGISTRY_AND_LADDER, "reason": "graph_score_disabled"}
    raw_keys = graph_ready_context.get("graph_priority_key_by_op_id")
    if not isinstance(raw_keys, dict) or not raw_keys:
        return {"policy": GRAPH_RULE_SCOPE_REGISTRY_AND_LADDER, "reason": "graph_keys_missing"}
    keys = [_finite_key(value) for value in raw_keys.values()]
    if any(key is None for key in keys) or len({len(key) for key in keys if key is not None}) != 1:
        return {"policy": GRAPH_RULE_SCOPE_REGISTRY_AND_LADDER, "reason": "graph_keys_not_uniform_finite"}
    distinct = len(set(keys))
    scope: Dict[str, Any] = {"operation_count": len(keys), "distinct_key_count": distinct}
    if distinct == len(keys):
        scope.update(policy=GRAPH_RULE_SCOPE_CONFIGURED_ONLY, reason="graph_keys_pairwise_distinct")
    else:
        scope.update(policy=GRAPH_RULE_SCOPE_REGISTRY_AND_LADDER, reason="graph_key_ties")
    return scope


def _dispatch_rules_for_mode(dispatch_mode: str, dispatch_rule_cfg: str, valid_dispatch_rules: List[str],
                             *, graph_rule_scope: Optional[Dict[str, Any]] = None) -> List[str]:
    if dispatch_mode != "sgs":
        return [dispatch_rule_cfg]
    if graph_rule_scope is not None and graph_rule_scope.get("policy") == GRAPH_RULE_SCOPE_CONFIGURED_ONLY:
        return [dispatch_rule_cfg]
    # Configured rule first, then the registry rules, then the ATC k ladder nearest-first; the
    # phase slice truncates from the far end when decodes are expensive.
    pool = dispatch_rule_search_pool(valid_dispatch_rules)
    return [dispatch_rule_cfg] + [rule for rule in pool if rule != dispatch_rule_cfg]


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
    metrics = compute_metrics(
        res, batches, expected_operations=algo_ops_to_schedule,
        seed_results=seed_sr_list, failure_details=getattr(summ, "failure_details", ()),
    )
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
        "resource_pool": resource_pool or {},
        "seed_result_count": len(seed_sr_list or []),
        "locked_seed_range": [getattr(item, "op_id", None) for item in list(seed_sr_list or [])],
        "mutable_scope": {"scope": "batch_order", "batch_count": len(order or [])},
    }


def _iter_multi_start_specs(
    *, keys: List[str], dispatch_modes: List[str], dispatch_rule_cfg: str, valid_dispatch_rules: List[str],
    snapshot: Any, strict_mode: bool, optimizer_algo_stats: Optional[Dict[str, Any]], deadline_reached: Callable[[], bool],
    graph_rule_scope: Optional[Dict[str, Any]] = None,
) -> Iterator[Tuple[str, str, str, SortStrategy, Dict[str, Any]]]:
    for dm in dispatch_modes:
        if deadline_reached():
            break
        dispatch_rules = _dispatch_rules_for_mode(dm, dispatch_rule_cfg, valid_dispatch_rules, graph_rule_scope=graph_rule_scope)
        for key in keys:
            if deadline_reached():
                break
            strategy = SortStrategy(key)
            params = _resolve_multi_start_strategy_params(
                strategy=strategy, cfg=snapshot, strict_mode=strict_mode,
                optimizer_algo_stats=optimizer_algo_stats,
            )
            for rule in dispatch_rules:
                if deadline_reached():
                    break
                yield dm, key, rule, strategy, params


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
    phase_deadline: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    order_cache: Dict[Tuple[str, Tuple[Tuple[str, Any], ...]], List[str]] = {}
    snapshot = ensure_optimizer_config_snapshot(cfg, strict_mode=bool(strict_mode))
    now = clock or time.time
    primary = (
        str(keys[0]) if keys else "",
        str(dispatch_modes[0]) if dispatch_modes else "",
        str(dispatch_rule_cfg),
    )
    decisions = MultiStartDecisionCache(
        scheduler=scheduler, strict_mode=bool(strict_mode), operations=algo_ops_to_schedule,
        batches=batches, start_dt=start_dt, end_date=end_date, downtime_map=downtime_map,
        seed_results=seed_sr_list, resource_pool=resource_pool,
        readiness_gate_enabled=bool(readiness_gate_enabled), graph_ready_context=graph_ready_context,
    )
    graph_rule_scope = graph_rule_search_scope(graph_ready_context)
    efficiency: Dict[str, Any] = {
        "proof": "native_complete_override_same_snapshot_v1",
        "configured_candidates": sum(len(keys) * len(_dispatch_rules_for_mode(
            dm, dispatch_rule_cfg, valid_dispatch_rules, graph_rule_scope=graph_rule_scope)) for dm in dispatch_modes),
        "eligible_candidates": 0, "decoded_candidates": 0, "predecode_pruned_candidates": 0, "skipped_by_budget": 0,
    }
    if graph_rule_scope is not None:
        efficiency["graph_rule_scope"] = dict(graph_rule_scope)

    def deadline_reached() -> bool:
        return _multi_start_deadline_reached(
            now=now, deadline=deadline, search_report_state=search_report_state,
            phase_deadline=phase_deadline, has_baseline=best is not None,
        )

    for dm, k, dr, strat, params0 in _iter_multi_start_specs(
        keys=keys, dispatch_modes=dispatch_modes, dispatch_rule_cfg=dispatch_rule_cfg,
        valid_dispatch_rules=valid_dispatch_rules, snapshot=snapshot, strict_mode=bool(strict_mode),
        optimizer_algo_stats=optimizer_algo_stats, deadline_reached=deadline_reached,
        graph_rule_scope=graph_rule_scope,
    ):
        order = _get_cached_multi_start_order(
            strategy=strat,
            params=params0,
            order_cache=order_cache,
            build_order=build_order,
        )
        decision_key = decisions.decision_key(strat, params0, dm, dr, order)
        if decision_key is not None:
            efficiency["eligible_candidates"] += 1
        if deadline_reached():
            break
        if decisions.has(decision_key):
            efficiency["predecode_pruned_candidates"] += 1
            attempts.append({
                "tag": candidate_tag(k, dm, dr), "candidate_status": "pruned",
                "reason": "equivalent_decision", "proof": efficiency["proof"],
                "strategy": k, "dispatch_mode": dm, "dispatch_rule": dr,
            })
            continue
        efficiency["decoded_candidates"] += 1
        decode_started = now()
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
        cand["initial_decode_runtime_ms"] = max((now() - decode_started) * 1000.0, 0.0)
        decisions.remember(decision_key, cand)
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
    efficiency["skipped_by_budget"] = (
        efficiency["configured_candidates"] - efficiency["decoded_candidates"] - efficiency["predecode_pruned_candidates"]
    )
    if search_report_state is not None:
        search_report_state.update_candidate_profile(multi_start_efficiency=efficiency)
    if efficiency["predecode_pruned_candidates"] or efficiency["skipped_by_budget"]:
        attempts.append({"tag": "multi_start_efficiency", "candidate_status": "phase_summary", "multi_start_efficiency": efficiency})
    return best
