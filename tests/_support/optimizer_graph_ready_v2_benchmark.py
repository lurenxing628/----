from __future__ import annotations

from typing import Any, Dict, List, Tuple

from core.algorithms import SortStrategy
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.greedy.algo_stats import snapshot_algo_stats
from core.services.scheduler.run.optimizer_graph_ready import run_graph_ready_candidates
from core.services.scheduler.run.optimizer_graph_ready_profiles import (
    GRAPH_READY_V2_REPAIRED_ORIGIN,
    graph_ready_v2_profile_summary,
    graph_ready_v2_profiles,
)
from core.services.scheduler.run.optimizer_graph_ready_v2_features import enrich_graph_ready_v2_metrics
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
from tests._support.optimizer_graph_ready_benchmark import (
    BASE_BATCH_ORDER,
    OBJECTIVE_NAME,
    START_DT,
    BenchmarkClock,
    _baseline_candidate,
    _result_order,
    _schedule_with_scheduler,
    _scheduler,
    _score_list,
    graph_ready_benchmark_batches,
    graph_ready_benchmark_context,
    graph_ready_benchmark_operations,
    run_graph_ready_real_sgs_case,
)


def graph_ready_v2_benchmark_context() -> Dict[str, Any]:
    context = graph_ready_benchmark_context()
    context["node_metrics_by_op_id"] = enrich_graph_ready_v2_metrics(
        context["node_metrics_by_op_id"],
        operations=graph_ready_benchmark_operations(),
        batches=graph_ready_benchmark_batches(),
        start_dt=START_DT,
    )
    return context


def run_graph_ready_v2_real_sgs_case(*, seed: int = 0, with_repair: bool = False) -> Dict[str, Any]:
    scheduler = _scheduler()
    operations = graph_ready_benchmark_operations()
    batches = graph_ready_benchmark_batches()
    baseline = _baseline_candidate(scheduler=scheduler, operations=operations, batches=batches)
    profile_name = "graph_ready_v2_with_repair" if with_repair else "graph_ready_v2_no_repair"
    state = OptimizationSearchReportState(
        algorithm_profile=profile_name,
        seed=int(seed),
        time_budget_seconds=1,
        objective_name=OBJECTIVE_NAME,
        started_at=1000.0,
        candidate_profile={"acceptance": "improve_only"},
        strict_mode=True,
    )
    state.mark_candidate_accepted(baseline, origin="baseline")
    attempts: List[Dict[str, Any]] = []
    improvement_trace: List[Dict[str, Any]] = []
    profiles, _truncated, _reason = graph_ready_v2_profiles(max_candidate_profiles=60, seed=int(seed))
    profile_summary = graph_ready_v2_profile_summary(max_candidate_profiles=60, seed=int(seed))
    best = run_graph_ready_candidates(
        algo_mode="improve",
        best=baseline,
        version=int(seed),
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
        resource_pool=None,
        objective_name=OBJECTIVE_NAME,
        deadline=2000.0,
        attempts=attempts,
        improvement_trace=improvement_trace,
        optimizer_algo_stats=snapshot_algo_stats(scheduler),
        t_begin=1000.0,
        readiness_gate_enabled=False,
        strict_mode=True,
        graph_ready_context=graph_ready_v2_benchmark_context(),
        clock=BenchmarkClock(),
        schedule_fn=_schedule_with_scheduler,
        search_report_state=state,
        max_weight_profiles=60,
        profiles_override=profiles,
        profile_summary_override=profile_summary,
    )
    if best is None:
        raise AssertionError("graph-ready v2 benchmark did not return a best candidate")
    repair_info = {"repair_evaluated_candidates": 0, "repair_accepted": False, "repair_status": "not_run"}
    if with_repair:
        best, repair_info = _repair_graph_ready_v2_candidate(best)
        if best.get("candidate_origin") == GRAPH_READY_V2_REPAIRED_ORIGIN:
            state.mark_candidate_accepted(best, origin=GRAPH_READY_V2_REPAIRED_ORIGIN)
    graph_attempts = [attempt for attempt in attempts if str(attempt.get("tag") or "").startswith("graph_ready:")]
    row = _benchmark_row(seed=seed, baseline=baseline, best=best, state=state, graph_attempts=graph_attempts)
    v1_reference_score = _score_list(run_graph_ready_real_sgs_case(seed=seed).get("objective_score"))
    row.update(
        {
            "algorithm_profile": profile_name,
            "algorithm_version": "graph_ready_v2_objective_features_v2",
            "candidate_origin": str(best.get("candidate_origin") or ""),
            "best_origin": str(state.best_origin or best.get("candidate_origin") or ""),
            "candidate_profile_count": len(graph_attempts),
            "accepted_candidates": int(state.accepted_candidates),
            "formula_versions": list(profile_summary.get("formula_versions") or []),
            "normalization_version": str(profile_summary.get("normalization_version") or ""),
            "v1_reference_objective_score": v1_reference_score,
            "comparison_to_graph_ready_v1": _score_comparison(
                actual=row["objective_score"],
                baseline=v1_reference_score,
                reference="graph_ready_v1",
            ),
            "candidate_families": [
                "v1_weighted_graph",
                "edd",
                "spt",
                "min_slack",
                "critical_ratio",
                "atc_like",
                "saveability",
                "sacrifice_long",
                "graph_due_hybrid",
                "bottleneck_due_gated",
                "micro_perturbation",
            ],
            "repair_scope": "benchmark_support_only_not_core",
        }
    )
    row.update(repair_info)
    row["status"] = "passed" if _v2_row_passes(row) else "failed"
    return row


def _benchmark_row(
    *,
    seed: int,
    baseline: Dict[str, Any],
    best: Dict[str, Any],
    state: OptimizationSearchReportState,
    graph_attempts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    baseline_score = _score_list(baseline.get("score"))
    best_score = _score_list(best.get("score"))
    failed_ops = int(getattr(best.get("summary"), "failed_ops", 0) or 0)
    baseline_failed_ops = int(getattr(baseline.get("summary"), "failed_ops", 0) or 0)
    return {
        "case_group": "graph_ready",
        "case_slug": "graph-ready-weight-grid-real-sgs",
        "seed": int(seed),
        "time_budget_seconds": 1,
        "objective_name": OBJECTIVE_NAME,
        "objective_score": best_score,
        "baseline_objective_score": baseline_score,
        "objective_score_matched": bool(tuple(best_score) <= tuple(baseline_score)),
        "failed_ops": failed_ops,
        "baseline_failed_ops": baseline_failed_ops,
        "oracle_status": "not_run",
        "oracle_scope": "not_available_for_graph_ready_v2_real_sgs_case",
        "gap_to_oracle_pct": None,
        "runtime_ms": int(best.get("runtime_ms") or 0),
        "candidate_profile_count": len(graph_attempts),
        "evaluated_candidates": int(state.evaluated_candidates),
        "accepted_distinct_candidates": int(len(state.accepted_fingerprints)),
        "distinct_candidates": int(len(state.candidate_fingerprints)),
        "same_fingerprint_rejections": int(state.rejection_summary.get("same_fingerprint") or 0),
        "candidate_rejections": dict(state.rejection_summary),
        "best_origin": str(state.best_origin or best.get("candidate_origin") or ""),
        "best_output_fingerprint": str(state.best_fingerprint or ""),
        "candidate_output_fingerprints": sorted(state.candidate_fingerprints),
        "accepted_output_fingerprints": sorted(state.accepted_fingerprints),
        "best_order": _result_order(best.get("results")),
        "baseline_order": _result_order(baseline.get("results")),
        "comparison_to_meta_baseline": {
            "metric": "objective_score",
            "baseline_value": baseline_score,
            "actual_value": best_score,
            "status": "improved" if tuple(best_score) < tuple(baseline_score) else "same",
        },
    }


def _repair_graph_ready_v2_candidate(candidate: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    base_order = [str(getattr(item, "batch_id", "") or "") for item in list(candidate.get("results") or [])]
    neighbor_orders = _repair_neighbor_orders(base_order)
    best = candidate
    evaluated = 0
    for order in neighbor_orders[:8]:
        evaluated += 1
        repaired = _candidate_for_batch_order(order)
        if tuple(_score_list(repaired.get("score"))) < tuple(_score_list(best.get("score"))):
            best = repaired
    accepted = best is not candidate
    return best, {
        "repair_evaluated_candidates": evaluated,
        "repair_accepted": bool(accepted),
        "repair_status": "strict_improvement" if accepted else "no_strict_improvement",
    }


def _repair_neighbor_orders(order: List[str]) -> List[List[str]]:
    out: List[List[str]] = []
    for index in range(max(len(order) - 1, 0)):
        cur = list(order)
        cur[index], cur[index + 1] = cur[index + 1], cur[index]
        out.append(cur)
    for source in range(len(order)):
        for target in range(len(order)):
            if source == target:
                continue
            cur = list(order)
            item = cur.pop(source)
            cur.insert(target, item)
            if cur not in out:
                out.append(cur)
    return out


def _candidate_for_batch_order(order: List[str]) -> Dict[str, Any]:
    scheduler = _scheduler()
    operations = graph_ready_benchmark_operations()
    batches = graph_ready_benchmark_batches()
    results, summary, strategy, params = scheduler.schedule(
        operations=operations,
        batches=batches,
        strategy=SortStrategy.PRIORITY_FIRST,
        strategy_params={},
        start_dt=START_DT,
        dispatch_mode="sgs",
        dispatch_rule="slack",
        batch_order_override=list(order),
        seed_results=[],
        strict_mode=True,
    )
    metrics = compute_metrics(results, batches)
    return {
        "results": results,
        "summary": summary,
        "strategy": strategy,
        "params": params,
        "dispatch_mode": "sgs",
        "dispatch_rule": "slack",
        "order": list(order),
        "metrics": metrics,
        "score": (float(summary.failed_ops),) + objective_score(OBJECTIVE_NAME, metrics),
        "algo_stats": snapshot_algo_stats(scheduler),
        "candidate_origin": GRAPH_READY_V2_REPAIRED_ORIGIN,
        "runtime_ms": 0,
    }


def _v2_row_passes(row: Dict[str, Any]) -> bool:
    best_origin = str(row.get("best_origin") or "")
    comparison_to_v1 = row.get("comparison_to_graph_ready_v1")
    v1_reference_score = _score_list(row.get("v1_reference_objective_score"))
    return (
        int(row.get("failed_ops") or 0) == 0
        and bool(row.get("objective_score_matched"))
        and int(row.get("candidate_profile_count") or 0) >= 10
        and int(row.get("distinct_candidates") or 0) >= 3
        and best_origin in {"graph_ready_v2_generated", GRAPH_READY_V2_REPAIRED_ORIGIN}
        and isinstance(comparison_to_v1, dict)
        and comparison_to_v1.get("status") == "improved"
        and tuple(_score_list(row.get("objective_score"))) <= tuple(_score_list(row.get("baseline_objective_score")))
        and tuple(_score_list(row.get("objective_score"))) < tuple(v1_reference_score)
    )


def _score_comparison(*, actual: Any, baseline: Any, reference: str) -> Dict[str, Any]:
    actual_score = tuple(_score_list(actual))
    baseline_score = tuple(_score_list(baseline))
    status = "same"
    if actual_score < baseline_score:
        status = "improved"
    elif actual_score > baseline_score:
        status = "degraded"
    return {
        "reference": reference,
        "baseline_value": list(baseline_score),
        "actual_value": list(actual_score),
        "status": status,
    }


__all__ = ["graph_ready_v2_benchmark_context", "run_graph_ready_v2_real_sgs_case"]
