"""Independent same-budget before/after benchmark. No production DB or mocks."""
from __future__ import annotations

import argparse
import hashlib
import importlib.machinery
import importlib.util
import json
import statistics
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

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
from tests._support.optimizer_graph_ready_repair_benchmark import smtwt_repair_context


def load_before(name, filename):
    module_name = "core.services.scheduler.run." + name
    loader = importlib.machinery.SourceFileLoader(module_name, str(Path(__file__).with_name(filename)))
    spec = importlib.util.spec_from_loader(module_name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    loader.exec_module(module)
    return module


def case_data(case_name):
    if case_name.startswith("smtwt"):
        context = smtwt_repair_context(size=40, index=int(case_name.split("_")[-1]))
        return (context["scheduler"], context["operations"], context["batches"], context["graph_context"],
                context["baseline"], context["case"].start_dt, list(context["base_order"]))
    scheduler, operations, batches = _scheduler(), graph_ready_benchmark_operations(), graph_ready_benchmark_batches()
    baseline = _baseline_candidate(scheduler=scheduler, operations=operations, batches=batches)
    return scheduler, operations, batches, graph_ready_benchmark_context(), baseline, START_DT, list(BASE_BATCH_ORDER)


def run_arm(run_fn, old_profiles, *, case_name, seed, count, seconds):
    scheduler, operations, batches, context, baseline, start, order = case_data(case_name)
    calls, attempts, trace = [], [], []
    began = perf_counter()
    state = OptimizationSearchReportState(algorithm_profile="candidate_efficiency", seed=seed,
                                          time_budget_seconds=seconds, objective_name=OBJECTIVE_NAME,
                                          started_at=began, strict_mode=True,
                                          candidate_profile={"acceptance": "improve_only"})
    state.mark_candidate_accepted(baseline, origin="baseline")

    def schedule(scheduler, **kwargs):
        calls.append({"start_ms": (perf_counter() - began) * 1000,
                      "origin": kwargs["strategy_params"]["graph_ready_profile"]["candidate_origin"]})
        return _schedule_with_scheduler(scheduler, **kwargs)

    overrides = {}
    if old_profiles is not None:
        overrides = {"profiles_override": old_profiles.graph_ready_v2_profiles(max_candidate_profiles=count, seed=seed)[0],
                     "profile_summary_override": old_profiles.graph_ready_v2_profile_summary(max_candidate_profiles=count, seed=seed)}
    best = run_fn(
        algo_mode="improve", best=baseline, version=seed, scheduler=scheduler,
        algo_ops_to_schedule=operations, batches=batches, start_dt=start, end_date=None,
        downtime_map={}, seed_sr_list=[], base_strategy=SortStrategy.PRIORITY_FIRST, base_params={},
        build_order=lambda _strategy, _params: list(order), dispatch_rule_cfg="slack", resource_pool=None,
        objective_name=OBJECTIVE_NAME, deadline=began + seconds, attempts=attempts, improvement_trace=trace,
        optimizer_algo_stats=None, t_begin=began, readiness_gate_enabled=False, strict_mode=True,
        graph_ready_context=context, clock=perf_counter, schedule_fn=schedule, search_report_state=state,
        candidate_construction={"graph_ready_optimization": {"candidate_policy": "objective_aware_portfolio",
                                "max_candidate_profiles": count, "elite_repair": {"enabled": True}}}, **overrides,
    )
    elapsed = (perf_counter() - began) * 1000
    repair = state.candidate_profile["graph_ready_optimization"]["elite_repair"]
    efficiency = state.candidate_profile["graph_ready_optimization"].get("profile_efficiency")
    return {"score": list(best["score"]), "baseline_score": list(baseline["score"]), "runtime_ms": elapsed,
            "decodes": len(calls), "profile_decodes": len(calls) - repair["repair_evaluated_candidates"],
            "repair_decodes": repair["repair_evaluated_candidates"], "repair_status": repair["repair_status"],
            "distinct_outputs_with_baseline": len(state.candidate_fingerprints),
            "profile_efficiency": efficiency, "decode_starts": calls,
            "baseline_safe": tuple(best["score"]) <= tuple(baseline["score"])}


def source_hashes():
    paths = ["optimizer_graph_ready.py", "optimizer_graph_ready_profiles.py", "optimizer_graph_ready_candidates.py",
             "optimizer_graph_ready_predecode.py", "optimizer_graph_ready_budget.py", "optimizer_graph_ready_repair.py"]
    result = {}
    for name in paths:
        path = ROOT / "core/services/scheduler/run" / name
        result[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ("core/algorithms/evaluation.py", "core/algorithms/greedy/dispatch/sgs.py",
                 "core/algorithms/greedy/dispatch/sgs_scoring.py"):
        result[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    for name in ("before_optimizer_graph_ready.txt", "before_optimizer_graph_ready_profiles.txt"):
        result[name] = hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
    return result


def benchmark(seeds):
    original = load_before("_efficiency_before_entry", "before_optimizer_graph_ready.txt")
    old_profiles = load_before("_efficiency_before_profiles", "before_optimizer_graph_ready_profiles.txt")
    hashes = source_hashes()
    rows = []
    suites = [("tiny", 6, 0.1), ("tiny", 19, 0.1), ("tiny", 60, 0.1),
              ("smtwt40_0", 19, 0.1), ("smtwt40_1", 60, 0.1)]
    for case_name, count, seconds in suites:
        for seed in range(seeds):
            arms = [("before", original.run_graph_ready_candidates, old_profiles),
                    ("after", run_graph_ready_candidates, None)]
            if seed % 2:
                arms.reverse()
            row = {"case": case_name, "seed": seed, "max_candidates": count, "time_budget_seconds": seconds}
            for label, run_fn, profiles in arms:
                row[label] = run_arm(run_fn, profiles, case_name=case_name, seed=seed, count=count, seconds=seconds)
            before, after = tuple(row["before"]["score"]), tuple(row["after"]["score"])
            row["comparison"] = "win" if after < before else "loss" if after > before else "tie"
            rows.append(row)
    summaries = []
    for case_name, count, seconds in suites:
        group = [row for row in rows if row["case"] == case_name and row["max_candidates"] == count]
        summaries.append({"case": case_name, "max_candidates": count, "time_budget_seconds": seconds,
                          "wins": sum(row["comparison"] == "win" for row in group),
                          "ties": sum(row["comparison"] == "tie" for row in group),
                          "losses": sum(row["comparison"] == "loss" for row in group),
                          "median_runtime_ms": {arm: statistics.median(row[arm]["runtime_ms"] for row in group)
                                                for arm in ("before", "after")},
                          "mean_decodes": {arm: statistics.mean(row[arm]["decodes"] for row in group)
                                           for arm in ("before", "after")},
                          "mean_repair_decodes": {arm: statistics.mean(row[arm]["repair_decodes"] for row in group)
                                                  for arm in ("before", "after")}})
    return {"proof_binding_status": "unbound_dirty_worktree", "clock": "time.perf_counter",
            "scope": "same current A18 evaluation and SGS; old/new profile order and phase orchestration",
            "source_hashes": hashes, "sources_stable_during_run": hashes == source_hashes(),
            "baseline_safe_all": all(row[arm]["baseline_safe"] for row in rows for arm in ("before", "after")),
            "count_budget_safe_all": all(row[arm]["decodes"] <= row["max_candidates"] for row in rows for arm in ("before", "after")),
            "summary": summaries, "rows": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("before-after.json"))
    args = parser.parse_args()
    evidence = benchmark(args.seeds)
    args.output.write_text(json.dumps(evidence, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({key: evidence[key] for key in ("summary", "baseline_safe_all", "count_budget_safe_all", "sources_stable_during_run")}, indent=2))
