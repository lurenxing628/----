"""Graph-ready SMTWT comparisons use the production phase and its repair budget."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Sequence

from core.algorithms import SortStrategy
from core.algorithms.greedy.algo_stats import snapshot_algo_stats
from core.services.scheduler.run.optimizer_graph_ready import run_graph_ready_candidates
from core.services.scheduler.run.optimizer_graph_ready_profiles import GRAPH_READY_V2_REPAIRED_ORIGIN
from tests._support.optimizer_smtwt_compare_common import (
    SMTWT_OBJECTIVE_NAME,
    make_report_state,
    schedule_with_scheduler,
)
from tests._support.optimizer_smtwt_compare_context import row_from_candidate


def run_graph_profile(*, profile: str, context: Dict[str, Any], optimum: int, seed: int) -> Dict[str, Any]:
    config = _profile_config(profile=profile, seed=seed)
    state = make_report_state(profile=profile, seed=seed, context=context)
    state.mark_candidate_accepted(context["baseline"], origin="baseline")
    graph_context = _graph_ready_context(context=context, v2=bool(config["v2"]))
    best = _run_graph_candidates(context=context, graph_context=graph_context, state=state, config=config, seed=seed)
    row = row_from_candidate(
        best, profile=profile, version=str(config["algorithm_version"]), context=context,
        optimum=optimum, seed=seed, state=state,
    )
    row["repair_scope"] = "production_core"
    row["repair"] = dict(state.candidate_profile.get("graph_ready_optimization", {}).get("elite_repair", {}))
    return row


def _profile_config(*, profile: str, seed: int) -> Dict[str, Any]:
    if profile == "graph_ready_v1":
        return {"v2": False, "with_repair": False, "max_profiles": 9,
                "algorithm_version": "graph_ready_weight_grid_v1"}
    if profile in {"graph_ready_v2_no_repair", "graph_ready_v2_with_repair"}:
        return {"v2": True, "with_repair": profile == "graph_ready_v2_with_repair", "max_profiles": 60,
                "algorithm_version": "graph_ready_v2_objective_features_v2"}
    raise ValueError(f"unknown graph-ready algorithm profile: {profile}")


def _run_graph_candidates(*, context: Dict[str, Any], graph_context: Dict[str, Any], state: Any, config: Dict[str, Any], seed: int) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []
    trace: List[Dict[str, Any]] = []
    optimization = {
        "candidate_policy": "objective_aware_portfolio" if config["v2"] else "weight_grid",
        "max_candidate_profiles": int(config["max_profiles"]),
        "elite_repair": {"enabled": bool(config["with_repair"])},
    }
    best = run_graph_ready_candidates(
        algo_mode="improve", best=context["baseline"], version=int(seed),
        scheduler=context["scheduler"], algo_ops_to_schedule=context["operations"],
        batches=context["batches"], start_dt=context["case"].start_dt, end_date=None,
        downtime_map={}, seed_sr_list=[], base_strategy=SortStrategy.PRIORITY_FIRST, base_params={},
        build_order=lambda _strategy, _params: list(context["base_order"]),
        dispatch_rule_cfg=context["case"].dispatch_rule, resource_pool=None,
        objective_name=SMTWT_OBJECTIVE_NAME, deadline=context["deadline"],
        attempts=attempts, improvement_trace=trace, optimizer_algo_stats=snapshot_algo_stats(context["scheduler"]),
        t_begin=context["started_at"], readiness_gate_enabled=False, strict_mode=True,
        graph_ready_context=graph_context, clock=time.perf_counter, schedule_fn=schedule_with_scheduler,
        search_report_state=state, max_weight_profiles=int(config["max_profiles"]),
        candidate_construction={"graph_ready_optimization": optimization},
    )
    return best or context["baseline"]


def _graph_ready_context(*, context: Dict[str, Any], v2: bool) -> Dict[str, Any]:
    # Production enriches v2 metrics inside the measured phase, exactly once.
    operations = context["operations"]
    op_ids = {int(getattr(op, "id")) for op in operations}
    return _context_payload(op_ids=op_ids, node_metrics=_base_node_metrics(operations))


def _base_node_metrics(operations: Sequence[Any]) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for index, op in enumerate(operations):
        hours = float(getattr(op, "setup_hours", 0.0) or 0.0)
        out[int(getattr(op, "id"))] = {
            "is_on_critical_path": False, "critical_path_rank": None, "impact_count": 0,
            "generation_index": index, "downstream_critical_minutes": hours * 60.0,
            "bottleneck_machine_score": 1.0,
        }
    return out


def _context_payload(*, op_ids: set, node_metrics: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "enabled": True, "schedulable_op_ids": op_ids, "fixed_op_ids": set(),
        "fixed_op_sources_by_op_id": {},
        "predecessor_op_ids_by_op_id": {op_id: set() for op_id in op_ids},
        "successor_op_ids_by_op_id": {op_id: set() for op_id in op_ids},
        "sort_key_by_op_id": {op_id: (0, index, op_id) for index, op_id in enumerate(sorted(op_ids), start=1)},
        "graph_priority_key_by_op_id": {op_id: (0.0,) for op_id in op_ids},
        "node_metrics_by_op_id": node_metrics,
    }


__all__ = ["run_graph_profile", "GRAPH_READY_V2_REPAIRED_ORIGIN"]
