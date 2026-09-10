"""Serial quality matrix using the production GraphReady repair and real SGS."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

from core.algorithms import GreedyScheduler, SortStrategy
from core.algorithms.evaluation import compute_metrics, objective_score
from core.services.scheduler.run.optimizer_graph_ready import run_graph_ready_candidates
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
from tests._support.optimizer_quality_matrix_cases import (
    OBJECTIVES,
    REPO_ROOT,
    SCENARIOS,
    START,
    case_environment,
    json_hash,
    scheduler_config,
)
from tests._support.optimizer_quality_matrix_schedule import audit_schedule, schedule_payload

DEFAULT_RUN_CONFIG = {"seed": 0, "time_budget_seconds": 10.0, "max_candidates": 60,
                      "repair_top_k": 3, "repair_max_neighbors_per_elite": 8, "workers": 1}


def validate_run_config(config):
    if not isinstance(config, dict) or set(config) != set(DEFAULT_RUN_CONFIG):
        raise ValueError("unknown or missing run config")
    for key in ("seed", "max_candidates", "repair_top_k", "repair_max_neighbors_per_elite", "workers"):
        if type(config[key]) is not int:
            raise ValueError("integer config required: " + key)
    if config["seed"] < 0 or config["max_candidates"] < 40:
        raise ValueError("seed must be nonnegative; candidate budget must leave room for production repair (>=40)")
    if not 1 <= config["repair_top_k"] <= 8 or not 1 <= config["repair_max_neighbors_per_elite"] <= 32:
        raise ValueError("repair limits outside production range")
    if config["workers"] != 1:
        raise ValueError("runtime matrix requires serial single-worker measurement")
    budget = config["time_budget_seconds"]
    if type(budget) not in (int, float) or not 0 < budget <= 300:
        raise ValueError("time_budget_seconds must be finite and in (0, 300]")


def run_case(scenario, objective, config=None):
    config = dict(DEFAULT_RUN_CONFIG if config is None else config)
    validate_run_config(config)
    if os.environ.get("PYTEST_XDIST_WORKER"):
        raise ValueError("run quality matrix without xdist")
    with case_environment(scenario) as env:
        values = scheduler_config(scenario, objective, config["time_budget_seconds"])
        scheduler = GreedyScheduler(calendar_service=env["calendar"], config_service=SimpleNamespace(**values))
        shared = {
            "strict_mode": True, "operations": env["operations"], "batches": env["batches"],
            "strategy": SortStrategy.PRIORITY_FIRST, "start_dt": START, "end_date": None,
            "machine_downtimes": env["downtime"], "seed_results": [], "dispatch_mode": "sgs",
            "dispatch_rule": "slack", "resource_pool": env["resource_pool"], "readiness_gate_enabled": False,
        }
        started = perf_counter()
        results, summary, strategy, params = scheduler.schedule(
            **shared, strategy_params={}, batch_order_override=list(env["batches"]), graph_ready_context=env["graph"])
        metrics = compute_metrics(results, env["batches"])
        baseline_ms = (perf_counter() - started) * 1000
        baseline = {"results": results, "summary": summary, "strategy": strategy, "params": params,
                    "metrics": metrics, "score": (float(summary.failed_ops),) + objective_score(objective, metrics),
                    "order": list(env["batches"]), "dispatch_mode": "sgs", "dispatch_rule": "slack",
                    "candidate_origin": "baseline", "runtime_ms": baseline_ms, "algo_stats": {}}
        best, counters, repair, improve_ms = _improve(scheduler, env, baseline, shared, objective, config)
        before, after = schedule_payload(baseline), schedule_payload(best)
        errors = []
        for label, payload in (("baseline", before), ("improved", after)):
            try:
                audit_schedule(payload, env, objective)
            except ValueError as exc:
                errors.append(label + ": " + str(exc))
        if after["failed_ops"] > before["failed_ops"] or tuple(after["objective_score"]) > tuple(before["objective_score"]):
            errors.append("quality regressed against same-environment baseline")
        if counters["repair_decode_count"] <= 0:
            errors.append("production repair did not decode a candidate")
        return {
            "case_id": scenario + "/" + objective, "scenario": scenario, "objective": objective,
            "seed": config["seed"], "operation_count": len(env["operations"]),
            "fixture_sha256": json_hash(env["data"]), "scheduler_config": values,
            "baseline": before, "improved": after, "baseline_runtime_ms": baseline_ms,
            "improve_runtime_ms": improve_ms, "runtime_ms": baseline_ms + improve_ms,
            "counts": counters, "repair": repair, "status": "failed" if errors else "passed", "errors": errors,
        }


def _improve(scheduler, env, baseline, shared, objective, config):
    counts = {"baseline_decode_count": 1, "graph_decode_count": 0, "repair_decode_count": 0}

    def decode(actual_scheduler, **kwargs):
        if actual_scheduler is not scheduler or scheduler.calendar is not env["calendar"]:
            raise ValueError("same-environment scheduler/calendar mismatch")
        if any(kwargs[key] != value for key, value in shared.items()):
            raise ValueError("same-environment schedule inputs changed")
        profile = kwargs["strategy_params"]["graph_ready_profile"]
        counter = "repair_decode_count" if profile["candidate_policy"] == "elite_repair" else "graph_decode_count"
        counts[counter] += 1
        return scheduler.schedule(**kwargs)

    started = perf_counter()
    state = OptimizationSearchReportState(
        algorithm_profile="graph_ready_v2_with_repair", seed=config["seed"],
        time_budget_seconds=config["time_budget_seconds"], objective_name=objective, started_at=started,
        strict_mode=True, candidate_profile={"acceptance": "improve_only"})
    state.mark_candidate_accepted(baseline, origin="baseline")
    best = run_graph_ready_candidates(
        algo_mode="improve", best=baseline, version=config["seed"], scheduler=scheduler,
        algo_ops_to_schedule=env["operations"], batches=env["batches"], start_dt=START, end_date=None,
        downtime_map=env["downtime"], seed_sr_list=[], base_strategy=SortStrategy.PRIORITY_FIRST, base_params={},
        build_order=lambda _strategy, _params: list(env["batches"]), dispatch_rule_cfg="slack",
        resource_pool=env["resource_pool"], objective_name=objective,
        deadline=started + config["time_budget_seconds"], attempts=[], improvement_trace=[],
        optimizer_algo_stats=None, t_begin=started, readiness_gate_enabled=False, strict_mode=True,
        graph_ready_context=env["graph"], clock=perf_counter, schedule_fn=decode, search_report_state=state,
        candidate_construction={"graph_ready_optimization": {
            "candidate_policy": "objective_aware_portfolio", "max_candidate_profiles": config["max_candidates"],
            "elite_repair": {"enabled": True, "top_k": config["repair_top_k"],
                             "max_neighbors_per_elite": config["repair_max_neighbors_per_elite"]}}})
    runtime_ms = (perf_counter() - started) * 1000
    if best is None:
        raise ValueError("production optimizer returned no schedule")
    report = state.candidate_profile["graph_ready_optimization"]["elite_repair"]
    repair = {key: report[key] for key in ("repair_scope", "repair_status", "repair_evaluated_candidates")}
    if repair["repair_evaluated_candidates"] != counts["repair_decode_count"]:
        raise ValueError("production repair decode counter mismatch")
    if counts["graph_decode_count"] + counts["repair_decode_count"] > config["max_candidates"]:
        raise ValueError("candidate decode budget exceeded")
    return best, counts, repair, runtime_ms


def build_quality_matrix(repo_root, config=None):
    from tests._support.optimizer_quality_matrix_provenance import capture_source, machine_metadata, proof_binding

    if Path(repo_root).resolve() != REPO_ROOT:
        raise ValueError("source receipt must describe the repository containing the running matrix code")
    config = dict(DEFAULT_RUN_CONFIG if config is None else config)
    validate_run_config(config)
    before = capture_source(repo_root)
    started = datetime.now(timezone.utc).isoformat()
    cases = [run_case(scenario, objective, config) for scenario in SCENARIOS for objective in OBJECTIVES]
    after = capture_source(repo_root)
    return {
        "schema_version": 1, "kind": "optimizer_quality_matrix", "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if all(row["status"] == "passed" for row in cases) else "failed",
        "claim": "feasibility_and_non_regression_only_not_optimality", "config": config,
        "measurement": {"clock": "time.perf_counter", "execution": "serial_single_worker",
                        "scope": "baseline_sgs_plus_graph_ready_production_repair_excludes_fixture_and_audit"},
        "machine": machine_metadata(), "source_before": before, "source_after": after,
        "proof_binding": proof_binding(before, after), "cases": cases,
    }
