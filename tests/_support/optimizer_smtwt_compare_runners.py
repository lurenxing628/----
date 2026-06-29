"""Non-graph algorithm runners for SMTWT optimizer comparison."""

from __future__ import annotations

import random
import time
from typing import Any, Dict, List

from core.algorithms import SortStrategy
from core.algorithms.greedy.algo_stats import snapshot_algo_stats
from core.services.scheduler.run.optimizer_candidate_profile import derive_grasp_ig_limits
from core.services.scheduler.run.optimizer_grasp_ig_candidates import run_grasp_ig_candidates
from core.services.scheduler.run.optimizer_local_search import run_local_search
from tests._support.optimizer_smtwt_compare_common import (
    SMTWT_OBJECTIVE_NAME,
    make_report_state,
    schedule_with_scheduler,
)
from tests._support.optimizer_smtwt_compare_context import row_from_candidate


def run_standard_profile(*, profile: str, context: Dict[str, Any], optimum: int, seed: int) -> Dict[str, Any]:
    if profile == "greedy":
        return row_from_candidate(context["baseline"], profile=profile, version="baseline_v1", context=context, optimum=optimum, seed=seed)
    if profile == "local_search":
        return _local_search_row(context=context, optimum=optimum, seed=seed)
    if profile == "grasp_ig":
        return _grasp_ig_row(context=context, optimum=optimum, seed=seed)
    raise ValueError(f"unknown standard algorithm profile: {profile}")


def _local_search_row(*, context: Dict[str, Any], optimum: int, seed: int) -> Dict[str, Any]:
    state = _seeded_state(profile="local_search", context=context, seed=seed)
    attempts: List[Dict[str, Any]] = []
    trace: List[Dict[str, Any]] = []
    t_begin = time.perf_counter()
    best = run_local_search(
        algo_mode="improve",
        best=context["baseline"],
        version=int(seed),
        time_budget_seconds=int(context["time_budget_seconds"]),
        deadline=t_begin + int(context["time_budget_seconds"]),
        scheduler=context["scheduler"],
        algo_ops_to_schedule=context["operations"],
        batches=context["batches"],
        start_dt=context["case"].start_dt,
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        dispatch_mode_cfg="sgs",
        dispatch_rule_cfg=context["case"].dispatch_rule,
        resource_pool=None,
        objective_name=SMTWT_OBJECTIVE_NAME,
        attempts=attempts,
        improvement_trace=trace,
        optimizer_algo_stats=snapshot_algo_stats(context["scheduler"]),
        t_begin=t_begin,
        readiness_gate_enabled=False,
        strict_mode=True,
        clock=time.perf_counter,
        rng_factory=random.Random,
        schedule_fn=schedule_with_scheduler,
        graph_ready_context=None,
        search_report_state=state,
        valid_dispatch_rules=[context["case"].dispatch_rule],
    )
    return row_from_candidate(best or context["baseline"], profile="local_search", version="vns_sa_v1", context=context, optimum=optimum, seed=seed, state=state)


def _grasp_ig_row(*, context: Dict[str, Any], optimum: int, seed: int) -> Dict[str, Any]:
    state = _seeded_state(profile="grasp_ig", context=context, seed=seed)
    attempts: List[Dict[str, Any]] = []
    trace: List[Dict[str, Any]] = []
    t_begin = time.perf_counter()
    best = run_grasp_ig_candidates(
        algo_mode="improve",
        best=context["baseline"],
        version=int(seed),
        candidate_construction=derive_grasp_ig_limits(int(context["time_budget_seconds"])),
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
        valid_dispatch_rules=[context["case"].dispatch_rule],
        resource_pool=None,
        objective_name=SMTWT_OBJECTIVE_NAME,
        deadline=t_begin + int(context["time_budget_seconds"]),
        attempts=attempts,
        improvement_trace=trace,
        optimizer_algo_stats=snapshot_algo_stats(context["scheduler"]),
        t_begin=t_begin,
        readiness_gate_enabled=False,
        strict_mode=True,
        graph_ready_context=None,
        clock=time.perf_counter,
        rng_factory=random.Random,
        schedule_fn=schedule_with_scheduler,
        batch_order_enabled=True,
        search_report_state=state,
    )
    return row_from_candidate(best or context["baseline"], profile="grasp_ig", version="grasp_ig_v1", context=context, optimum=optimum, seed=seed, state=state)


def _seeded_state(*, profile: str, context: Dict[str, Any], seed: int):
    state = make_report_state(profile=profile, seed=seed, context=context)
    state.mark_candidate_evaluated(context["baseline"], origin="baseline")
    state.mark_candidate_accepted(context["baseline"], origin="baseline")
    return state
