"""Small, same-objective optimizer comparison matrix for GraphReady work."""

from __future__ import annotations

import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.algorithms import SortStrategy
from core.algorithms.greedy.algo_stats import snapshot_algo_stats
from core.services.scheduler.run.optimizer_candidate_profile import derive_grasp_ig_limits
from core.services.scheduler.run.optimizer_grasp_ig_candidates import run_grasp_ig_candidates
from core.services.scheduler.run.optimizer_local_search import run_local_search
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
from tests._support.optimizer_compare_algorithms_provenance import (
    COMPARE_SCHEMA_VERSION,
    MEASUREMENT,
    capture_source,
    machine_metadata,
    require_serial_workers,
    source_binding,
)
from tests._support.optimizer_compare_algorithms_report import (
    compare_to_algorithm_baseline,
    summarize_comparison_rows,
)
from tests._support.optimizer_compare_algorithms_rows import (
    _attach_comparisons,
    _comparison,
    _portfolio_row,
    _row_from_candidate,
)
from tests._support.optimizer_graph_ready_benchmark import (
    BASE_BATCH_ORDER,
    OBJECTIVE_NAME,
    START_DT,
    _baseline_candidate,
    _schedule_with_scheduler,
    _scheduler,
    graph_ready_benchmark_batches,
    graph_ready_benchmark_operations,
)
from tests._support.optimizer_graph_ready_repair_benchmark import run_production_repair_case
from tests._support.optimizer_reference_diagnostics import build_reference_diagnostics

COMPARE_CASE_GROUP = "graph_ready"
COMPARE_CASE_SLUG = "graph-ready-weight-grid-real-sgs"
POSTHOC_UPPER_BOUND_SEMANTICS = "posthoc_upper_bound"
SAME_BUDGET_SEMANTICS = "same_budget_algorithm"
DEFAULT_ALGORITHM_PROFILES = (
    "greedy",
    "local_search",
    "grasp_ig",
    "graph_ready_v1",
    "graph_ready_v2_no_repair",
    "graph_ready_v2_with_repair",
    "portfolio_all",
)


def build_algorithm_comparison(*, profiles: Sequence[str], seeds: int, workers: int = 1) -> Dict[str, Any]:
    normalized_profiles = _normalize_profiles(profiles)
    worker_count = require_serial_workers(workers)
    source_before = capture_source(Path.cwd())
    all_rows: List[Dict[str, Any]] = []
    seed_tasks = [(seed, normalized_profiles) for seed in range(int(seeds))]
    for seed_rows in map(_run_seed_profiles_task, seed_tasks):
        all_rows.extend(seed_rows)
    source_after = capture_source(Path.cwd())
    binding = source_binding(source_before, source_after)
    payload = {
        "schema_version": COMPARE_SCHEMA_VERSION,
        "status": "passed" if all_rows and all(row.get("status") == "passed" for row in all_rows) else "failed",
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "git_commit": source_after["head"],
        "dirty_worktree": not source_before["worktree_clean"] or not source_after["worktree_clean"],
        "proof_binding_status": binding,
        "source_before": source_before, "source_after": source_after,
        "measurement": dict(MEASUREMENT), "machine": machine_metadata(),
        "command": "build_algorithm_comparison",
        "command_args": {"profiles": list(normalized_profiles), "seeds": int(seeds), "workers": worker_count},
        "case_group": COMPARE_CASE_GROUP,
        "case_slug": COMPARE_CASE_SLUG,
        "seed_count": int(seeds),
        "algorithm_profiles": list(normalized_profiles),
        "ratchet_key_fields": ["case_group", "case_slug", "algorithm_profile", "algorithm_version", "seed"],
        "reference_diagnostics": build_reference_diagnostics(objective_name=OBJECTIVE_NAME),
        "rows": all_rows,
        "summary": summarize_comparison_rows(all_rows),
    }
    return payload


def _run_seed_profiles_task(task: Tuple[int, Tuple[str, ...]]) -> List[Dict[str, Any]]:
    seed, profiles = task
    seed_rows = _run_seed_profiles(seed=int(seed), profiles=profiles)
    _attach_comparisons(seed_rows)
    return seed_rows


def _normalize_profiles(profiles: Sequence[str]) -> Tuple[str, ...]:
    out: List[str] = []
    for item in profiles:
        text = str(item or "").strip().lower()
        if text == "graph_ready":
            text = "graph_ready_v1"
        if text and text not in out:
            out.append(text)
    return tuple(out or DEFAULT_ALGORITHM_PROFILES)


def _run_seed_profiles(*, seed: int, profiles: Tuple[str, ...]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    real_profiles = [profile for profile in profiles if profile != "portfolio_all"]
    for profile in real_profiles:
        rows.append(_run_single_profile(profile=profile, seed=seed))
    if "portfolio_all" in profiles:
        rows.append(_portfolio_row(rows, seed=seed))
    return rows


def _run_single_profile(*, profile: str, seed: int) -> Dict[str, Any]:
    if profile == "greedy":
        return _baseline_row(seed=seed)
    if profile == "graph_ready_v1":
        return _graph_ready_v1_row(seed=seed)
    if profile == "graph_ready_v2_no_repair":
        return _graph_ready_v2_row(seed=seed, with_repair=False)
    if profile == "graph_ready_v2_with_repair":
        return _graph_ready_v2_row(seed=seed, with_repair=True)
    if profile == "local_search":
        return _local_search_row(seed=seed)
    if profile == "grasp_ig":
        return _grasp_ig_row(seed=seed)
    raise ValueError(f"unknown algorithm profile: {profile}")


def _baseline_setup() -> Tuple[Any, List[Any], Dict[str, Any], Dict[str, Any]]:
    scheduler = _scheduler()
    operations = graph_ready_benchmark_operations()
    batches = graph_ready_benchmark_batches()
    baseline = _baseline_candidate(scheduler=scheduler, operations=operations, batches=batches)
    return scheduler, operations, batches, baseline


def _baseline_row(*, seed: int) -> Dict[str, Any]:
    started = time.perf_counter()
    _scheduler_obj, _operations, _batches, baseline = _baseline_setup()
    return _row_from_candidate(
        candidate=baseline,
        profile="greedy",
        version="baseline_v1",
        seed=seed,
        evaluated_candidates=1,
        distinct_candidates=1,
        accepted_candidates=1,
        candidate_rejections={},
        status="passed",
        runtime_ms=(time.perf_counter() - started) * 1000.0,
    )


def _graph_ready_v1_row(*, seed: int) -> Dict[str, Any]:
    return _graph_ready_row(seed=seed, v2=False, with_repair=False)


def _graph_ready_v2_row(*, seed: int, with_repair: bool) -> Dict[str, Any]:
    return _graph_ready_row(seed=seed, v2=True, with_repair=with_repair)


def _graph_ready_row(*, seed: int, v2: bool, with_repair: bool) -> Dict[str, Any]:
    production = run_production_repair_case(seed=seed, enabled=with_repair, v2=v2)
    best, state = production["best"], production["state"]
    row = _row_from_candidate(
        candidate=best, profile=production["profile"],
        version="graph_ready_v2_objective_features_v2" if v2 else "graph_ready_weight_grid_v1",
        seed=seed, evaluated_candidates=int(state.evaluated_candidates),
        distinct_candidates=len(state.candidate_fingerprints), accepted_candidates=int(state.accepted_candidates),
        candidate_rejections=dict(state.rejection_summary), status="passed",
        candidate_output_fingerprints=sorted(state.candidate_fingerprints),
        accepted_output_fingerprints=sorted(state.accepted_fingerprints),
        runtime_ms=production["runtime_ms"],
    )
    row["repair_scope"] = "production_core"
    row["repair"] = production["repair"]
    row["max_candidates"] = production["max_candidates"]
    return row


def _local_search_row(*, seed: int) -> Dict[str, Any]:
    started = time.perf_counter()
    scheduler, operations, batches, baseline = _baseline_setup()
    state = _state(profile="local_search", seed=seed, started=started)
    state.mark_candidate_evaluated(baseline, origin="baseline")
    state.mark_candidate_accepted(baseline, origin="baseline")
    attempts: List[Dict[str, Any]] = []
    trace: List[Dict[str, Any]] = []
    best = run_local_search(
        algo_mode="improve",
        best=baseline,
        version=int(seed),
        time_budget_seconds=1,
        deadline=started + 1.0,
        scheduler=scheduler,
        algo_ops_to_schedule=operations,
        batches=batches,
        start_dt=START_DT,
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        dispatch_mode_cfg="sgs",
        dispatch_rule_cfg="slack",
        resource_pool=None,
        objective_name=OBJECTIVE_NAME,
        attempts=attempts,
        improvement_trace=trace,
        optimizer_algo_stats=snapshot_algo_stats(scheduler),
        t_begin=started,
        readiness_gate_enabled=False,
        strict_mode=True,
        clock=time.perf_counter,
        rng_factory=random.Random,
        schedule_fn=_schedule_with_scheduler,
        graph_ready_context=None,
        search_report_state=state,
        valid_dispatch_rules=["slack"],
    )
    return _row_from_candidate(
        candidate=best or baseline,
        profile="local_search",
        version="vns_sa_v1",
        seed=seed,
        evaluated_candidates=int(state.evaluated_candidates),
        distinct_candidates=int(len(state.candidate_fingerprints)),
        accepted_candidates=int(state.accepted_candidates),
        candidate_rejections=dict(state.rejection_summary),
        candidate_output_fingerprints=sorted(state.candidate_fingerprints),
        accepted_output_fingerprints=sorted(state.accepted_fingerprints),
        status="passed",
        runtime_ms=(time.perf_counter() - started) * 1000.0,
    )


def _grasp_ig_row(*, seed: int) -> Dict[str, Any]:
    started = time.perf_counter()
    scheduler, operations, batches, baseline = _baseline_setup()
    state = _state(profile="grasp_ig", seed=seed, started=started)
    state.mark_candidate_evaluated(baseline, origin="baseline")
    state.mark_candidate_accepted(baseline, origin="baseline")
    attempts: List[Dict[str, Any]] = []
    trace: List[Dict[str, Any]] = []
    best = run_grasp_ig_candidates(
        algo_mode="improve",
        best=baseline,
        version=int(seed),
        candidate_construction=derive_grasp_ig_limits(1),
        scheduler=scheduler,
        algo_ops_to_schedule=operations,
        batches=batches,
        start_dt=START_DT,
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        base_strategy=SortStrategy.PRIORITY_FIRST,
        base_params={},
        build_order=lambda _strategy, _params: list(BASE_BATCH_ORDER),
        dispatch_rule_cfg="slack",
        valid_dispatch_rules=["slack"],
        batch_order_enabled=True,
        resource_pool=None,
        objective_name=OBJECTIVE_NAME,
        deadline=started + 1.0,
        attempts=attempts,
        improvement_trace=trace,
        optimizer_algo_stats=snapshot_algo_stats(scheduler),
        t_begin=started,
        readiness_gate_enabled=False,
        strict_mode=True,
        graph_ready_context=None,
        clock=time.perf_counter,
        rng_factory=random.Random,
        schedule_fn=_schedule_with_scheduler,
        search_report_state=state,
    )
    return _row_from_candidate(
        candidate=best or baseline,
        profile="grasp_ig",
        version="grasp_ig_v1",
        seed=seed,
        evaluated_candidates=int(state.evaluated_candidates),
        distinct_candidates=int(len(state.candidate_fingerprints)),
        accepted_candidates=int(state.accepted_candidates),
        candidate_rejections=dict(state.rejection_summary),
        candidate_output_fingerprints=sorted(state.candidate_fingerprints),
        accepted_output_fingerprints=sorted(state.accepted_fingerprints),
        status="passed",
        runtime_ms=(time.perf_counter() - started) * 1000.0,
    )


def _state(*, profile: str, seed: int, started: float) -> OptimizationSearchReportState:
    return OptimizationSearchReportState(
        algorithm_profile=profile,
        seed=int(seed),
        time_budget_seconds=1,
        objective_name=OBJECTIVE_NAME,
        started_at=started,
        candidate_profile={"acceptance": "improve_only"},
        strict_mode=True,
    )




__all__ = [
    "COMPARE_SCHEMA_VERSION",
    "DEFAULT_ALGORITHM_PROFILES",
    "POSTHOC_UPPER_BOUND_SEMANTICS",
    "SAME_BUDGET_SEMANTICS",
    "build_algorithm_comparison",
    "compare_to_algorithm_baseline",
    "summarize_comparison_rows",
]
