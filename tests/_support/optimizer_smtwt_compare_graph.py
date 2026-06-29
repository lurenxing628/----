"""Graph-ready algorithm runners for SMTWT optimizer comparison."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from core.algorithms import SortStrategy
from core.algorithms.greedy.algo_stats import snapshot_algo_stats
from core.services.scheduler.run.optimizer_graph_ready import run_graph_ready_candidates
from core.services.scheduler.run.optimizer_graph_ready_profiles import (
    GRAPH_READY_V2_REPAIRED_ORIGIN,
    graph_ready_v2_profile_summary,
    graph_ready_v2_profiles,
    graph_ready_weight_profile_summary,
)
from core.services.scheduler.run.optimizer_graph_ready_v2_features import enrich_graph_ready_v2_metrics
from tests._support.optimizer_smtwt_compare_common import (
    SMTWT_OBJECTIVE_NAME,
    BenchmarkClock,
    make_report_state,
    schedule_with_scheduler,
    score_tuple,
)
from tests._support.optimizer_smtwt_compare_context import candidate_payload, row_from_candidate


def run_graph_profile(*, profile: str, context: Dict[str, Any], optimum: int, seed: int) -> Dict[str, Any]:
    config = _profile_config(profile=profile, seed=seed)
    state = make_report_state(profile=profile, seed=seed, context=context)
    state.mark_candidate_accepted(context["baseline"], origin="baseline")
    graph_context = _graph_ready_context(context=context, v2=bool(config["v2"]))
    best = _run_graph_candidates(context=context, graph_context=graph_context, state=state, config=config, seed=seed)
    if bool(config["with_repair"]):
        repaired = _repair_graph_candidate(best=best, context=context, graph_context=graph_context)
        if repaired is not None:
            best = repaired
            state.mark_candidate_evaluated(best, origin=GRAPH_READY_V2_REPAIRED_ORIGIN)
            state.mark_candidate_accepted(best, origin=GRAPH_READY_V2_REPAIRED_ORIGIN)
    return row_from_candidate(
        best,
        profile=profile,
        version=str(config["algorithm_version"]),
        context=context,
        optimum=optimum,
        seed=seed,
        state=state,
    )


def _profile_config(*, profile: str, seed: int) -> Dict[str, Any]:
    if profile == "graph_ready_v1":
        return {
            "v2": False,
            "with_repair": False,
            "max_profiles": 9,
            "profiles_override": None,
            "summary_override": graph_ready_weight_profile_summary(max_weight_profiles=9),
            "algorithm_version": "graph_ready_weight_grid_v1",
        }
    if profile in {"graph_ready_v2_no_repair", "graph_ready_v2_with_repair"}:
        profiles, _truncated, _reason = graph_ready_v2_profiles(max_candidate_profiles=60, seed=seed)
        return {
            "v2": True,
            "with_repair": profile == "graph_ready_v2_with_repair",
            "max_profiles": 60,
            "profiles_override": profiles,
            "summary_override": graph_ready_v2_profile_summary(max_candidate_profiles=60, seed=seed),
            "algorithm_version": "graph_ready_v2_objective_features_v2",
        }
    raise ValueError(f"unknown graph-ready algorithm profile: {profile}")


def _run_graph_candidates(*, context: Dict[str, Any], graph_context: Dict[str, Any], state: Any, config: Dict[str, Any], seed: int) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []
    trace: List[Dict[str, Any]] = []
    best = run_graph_ready_candidates(
        algo_mode="improve",
        best=context["baseline"],
        version=int(seed),
        scheduler=context["scheduler"],
        algo_ops_to_schedule=context["operations"],
        batches=context["batches"],
        start_dt=context["case"].start_dt,
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        base_strategy=SortStrategy.PRIORITY_FIRST,
        base_params={},
        build_order=lambda _strategy, _params: list(context["base_order"]),
        dispatch_rule_cfg=context["case"].dispatch_rule,
        resource_pool=None,
        objective_name=SMTWT_OBJECTIVE_NAME,
        deadline=2000.0,
        attempts=attempts,
        improvement_trace=trace,
        optimizer_algo_stats=snapshot_algo_stats(context["scheduler"]),
        t_begin=1000.0,
        readiness_gate_enabled=False,
        strict_mode=True,
        graph_ready_context=graph_context,
        clock=BenchmarkClock(),
        schedule_fn=schedule_with_scheduler,
        search_report_state=state,
        max_weight_profiles=int(config["max_profiles"]),
        profiles_override=config["profiles_override"],
        profile_summary_override=config["summary_override"],
    )
    return best or context["baseline"]


def _graph_ready_context(*, context: Dict[str, Any], v2: bool) -> Dict[str, Any]:
    operations = context["operations"]
    op_ids = {int(getattr(op, "id")) for op in operations}
    node_metrics = _base_node_metrics(operations)
    if v2:
        node_metrics = enrich_graph_ready_v2_metrics(
            node_metrics,
            operations=operations,
            batches=context["batches"],
            start_dt=context["case"].start_dt,
        )
    return _context_payload(op_ids=op_ids, node_metrics=node_metrics)


def _base_node_metrics(operations: Sequence[Any]) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for index, op in enumerate(operations):
        hours = float(getattr(op, "setup_hours", 0.0) or 0.0)
        out[int(getattr(op, "id"))] = {
            "is_on_critical_path": False,
            "critical_path_rank": None,
            "impact_count": 0,
            "generation_index": index,
            "downstream_critical_minutes": hours * 60.0,
            "bottleneck_machine_score": 1.0,
        }
    return out


def _context_payload(*, op_ids: set, node_metrics: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "enabled": True,
        "schedulable_op_ids": op_ids,
        "fixed_op_ids": set(),
        "fixed_op_sources_by_op_id": {},
        "predecessor_op_ids_by_op_id": {op_id: set() for op_id in op_ids},
        "successor_op_ids_by_op_id": {op_id: set() for op_id in op_ids},
        "sort_key_by_op_id": {op_id: (0, index, op_id) for index, op_id in enumerate(sorted(op_ids), start=1)},
        "graph_priority_key_by_op_id": {op_id: (0.0,) for op_id in op_ids},
        "node_metrics_by_op_id": node_metrics,
    }


def _repair_graph_candidate(*, best: Dict[str, Any], context: Dict[str, Any], graph_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    best_order = [int(getattr(result, "op_id")) for result in list(best.get("results") or [])]
    incumbent = best
    for order in _repair_orders(best_order):
        candidate = _candidate_for_op_order(order=order, context=context, graph_context=graph_context)
        if score_tuple(candidate.get("score")) < score_tuple(incumbent.get("score")):
            incumbent = candidate
    return incumbent if incumbent is not best else None


def _candidate_for_op_order(*, order: List[int], context: Dict[str, Any], graph_context: Dict[str, Any]) -> Dict[str, Any]:
    candidate_context = _context_with_order_priority(graph_context=graph_context, order=order)
    results, summary, strategy, params = context["scheduler"].schedule(
        operations=context["operations"],
        batches=context["batches"],
        strategy=SortStrategy.PRIORITY_FIRST,
        strategy_params={},
        start_dt=context["case"].start_dt,
        dispatch_mode="sgs",
        dispatch_rule=context["case"].dispatch_rule,
        seed_results=[],
        strict_mode=True,
        graph_ready_context=candidate_context,
    )
    return candidate_payload(
        results=results,
        summary=summary,
        strategy=strategy,
        params=params,
        dispatch_rule=context["case"].dispatch_rule,
        batches=context["batches"],
        objective_name=SMTWT_OBJECTIVE_NAME,
        origin=GRAPH_READY_V2_REPAIRED_ORIGIN,
        runtime_ms=0,
    )


def _context_with_order_priority(*, graph_context: Dict[str, Any], order: List[int]) -> Dict[str, Any]:
    candidate_context = dict(graph_context)
    candidate_context["score_enabled"] = True
    candidate_context["graph_priority_key_by_op_id"] = {op_id: (float(index),) for index, op_id in enumerate(order)}
    return candidate_context


def _repair_orders(order: Sequence[int]) -> List[List[int]]:
    return _adjacent_swap_orders(order, limit=8) + _single_insert_orders(order, limit=8)


def _adjacent_swap_orders(order: Sequence[int], *, limit: int) -> List[List[int]]:
    base = list(order)
    out: List[List[int]] = []
    for index in range(len(base) - 1):
        candidate = list(base)
        candidate[index], candidate[index + 1] = candidate[index + 1], candidate[index]
        out.append(candidate)
        if len(out) >= limit:
            break
    return out[:limit]


def _single_insert_orders(order: Sequence[int], *, limit: int) -> List[List[int]]:
    base = list(order)
    out: List[List[int]] = []
    for src in range(len(base)):
        _append_insert_orders(base=base, src=src, out=out, limit=limit)
        if len(out) >= limit:
            break
    return out[:limit]


def _append_insert_orders(*, base: List[int], src: int, out: List[List[int]], limit: int) -> None:
    for dst in range(len(base)):
        if src == dst:
            continue
        candidate = list(base)
        item = candidate.pop(src)
        candidate.insert(dst, item)
        out.append(candidate)
        if len(out) >= limit:
            return
