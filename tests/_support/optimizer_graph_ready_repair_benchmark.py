"""Real production GraphReady phase with equal wall-clock and candidate budgets."""
from __future__ import annotations

from time import perf_counter
from typing import Any, Dict

from core.algorithms import SortStrategy
from core.services.scheduler.run.optimizer_graph_ready import run_graph_ready_candidates
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
from tests._support.optimizer_graph_ready_benchmark import (
    BASE_BATCH_ORDER,
    OBJECTIVE_NAME,
    START_DT,
    _baseline_candidate,
    _schedule_with_scheduler,
    _scheduler,
    graph_ready_benchmark_batches,
    graph_ready_benchmark_context,
    graph_ready_benchmark_operations,
)


def run_production_repair_case(*, seed: int = 0, enabled: bool = True, limits=None, max_candidates: int = 60,
                               time_budget_seconds: float = 1.0, clock=perf_counter, schedule_fn=None,
                               case=None, strict_mode=True, keep_report=True, v2=True, iterated_greedy=None) -> Dict[str, Any]:
    started = clock()
    start_dt = START_DT
    base_order = list(BASE_BATCH_ORDER)
    if case is None:
        scheduler = _scheduler()
        operations, batches, context = graph_ready_benchmark_operations(), graph_ready_benchmark_batches(), graph_ready_benchmark_context()
        baseline = _baseline_candidate(scheduler=scheduler, operations=operations, batches=batches)
    else:
        operations, batches, context = case["operations"], case["batches"], case["graph_context"]
        from tests._support.optimizer_smtwt_compare_context import baseline_candidate
        scheduler = case["scheduler"]
        baseline = baseline_candidate(scheduler=scheduler, operations=operations, batches=batches, case=case["case"])
        start_dt, base_order = case["case"].start_dt, list(case["base_order"])
    profile = ("graph_ready_v2_with_repair" if enabled else "graph_ready_v2_no_repair") if v2 else "graph_ready_v1"
    state = OptimizationSearchReportState(algorithm_profile=profile, seed=seed, time_budget_seconds=time_budget_seconds,
                                          objective_name=OBJECTIVE_NAME, started_at=started, strict_mode=strict_mode,
                                          candidate_profile={"acceptance": "improve_only"})
    state.mark_candidate_accepted(baseline, origin="baseline")
    attempts = []
    trace = []
    calls = []

    def schedule(scheduler, **kwargs):
        calls.append(kwargs)
        return (schedule_fn or _schedule_with_scheduler)(scheduler, **kwargs)

    optimization = {"candidate_policy": "objective_aware_portfolio" if v2 else "weight_grid", "max_candidate_profiles": max_candidates,
                    "elite_repair": dict({"enabled": enabled}, **(limits or {}))}
    if iterated_greedy is not None:
        optimization["iterated_greedy"] = dict(iterated_greedy)
    best = run_graph_ready_candidates(
        algo_mode="improve", best=baseline, version=seed, scheduler=scheduler,
        algo_ops_to_schedule=operations, batches=batches, start_dt=start_dt, end_date=None,
        downtime_map={}, seed_sr_list=[], base_strategy=SortStrategy.PRIORITY_FIRST, base_params={},
        build_order=lambda _strategy, _params: list(base_order), dispatch_rule_cfg="slack",
        resource_pool=None, objective_name=OBJECTIVE_NAME, deadline=started + time_budget_seconds,
        attempts=attempts, improvement_trace=trace, optimizer_algo_stats=None, t_begin=started,
        readiness_gate_enabled=False, strict_mode=strict_mode, graph_ready_context=context,
        clock=clock, schedule_fn=schedule, search_report_state=state if keep_report else None,
        candidate_construction={"graph_ready_optimization": optimization},
    )
    runtime_ms = (clock() - started) * 1000.0
    if keep_report:
        report = state.candidate_profile["graph_ready_optimization"].get("elite_repair", {})
        ig_report = state.candidate_profile["graph_ready_optimization"].get("iterated_greedy", {})
    else:
        report = next((attempt["elite_repair"] for attempt in attempts if "elite_repair" in attempt), {})
        ig_report = next((attempt["iterated_greedy"] for attempt in attempts if "iterated_greedy" in attempt), {})
    ig_calls = [call for call in calls
                if call["strategy_params"]["graph_ready_profile"]["candidate_origin"] == "graph_ready_v2_iterated_greedy"]
    phase_calls = [call for call in calls if call not in ig_calls]
    return {"best": best, "baseline": baseline, "state": state, "repair": report, "iterated_greedy": ig_report, "attempts": attempts,
            "phase_calls": phase_calls, "ig_calls": ig_calls,
            "calls": calls, "trace": trace, "runtime_ms": runtime_ms, "profile": profile, "seed": seed,
            "time_budget_seconds": time_budget_seconds, "max_candidates": max_candidates,
            "clock_scope": "time.perf_counter" if clock is perf_counter else "test_injected_clock"}


def repair_comparison(*, seeds: int = 10, case=None, time_budget_seconds=1) -> Dict[str, Any]:
    counts = {"wins": 0, "ties": 0, "losses": 0}
    rows = []
    for seed in range(seeds):
        off = run_production_repair_case(seed=seed, enabled=False, case=case, time_budget_seconds=time_budget_seconds)
        on = run_production_repair_case(seed=seed, enabled=True, case=case, time_budget_seconds=time_budget_seconds)
        before, after = tuple(off["best"]["score"]), tuple(on["best"]["score"])
        counts["wins" if after < before else "losses" if after > before else "ties"] += 1
        rows.append({"seed": seed, "without_repair": list(before), "with_repair": list(after),
                     "runtime_ms_without": off["runtime_ms"], "runtime_ms_with": on["runtime_ms"],
                     "decodes_without": len(off["calls"]), "decodes_with": len(on["calls"]),
                     "repair_evaluated": on["repair"]["repair_evaluated_candidates"],
                     "repair_pruned": on["repair"]["repair_pruned_candidates"],
                     "repair_skipped": on["repair"]["repair_skipped_by_budget"],
                     "repair_status": on["repair"]["repair_status"]})
    return {"comparison": counts, "rows": rows, "time_budget_seconds": time_budget_seconds, "max_candidates": 60,
            "proof_binding_status": "unbound_dirty_worktree", "comparison_semantics": "same_budget_algorithm"}


def smtwt_repair_context(*, size=40, index=0):
    from tests._support.optimizer_benchmark_grading import smtwt_overdue_case
    from tests._support.optimizer_benchmark_loaders import load_smtwt_instances
    from tests._support.optimizer_smtwt_compare_context import build_case_context
    from tests._support.optimizer_smtwt_compare_graph import _graph_ready_context

    instance = load_smtwt_instances(size)[index]
    context = build_case_context(case=smtwt_overdue_case(instance), time_budget_seconds=1)
    context["graph_context"] = _graph_ready_context(context=context, v2=False)
    return context
