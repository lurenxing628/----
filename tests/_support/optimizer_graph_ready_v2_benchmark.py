from __future__ import annotations

from typing import Any, Dict, List

from core.services.scheduler.run.optimizer_graph_ready_profiles import (
    GRAPH_READY_V2_REPAIRED_ORIGIN,
    graph_ready_v2_profile_summary,
)
from core.services.scheduler.run.optimizer_graph_ready_v2_features import enrich_graph_ready_v2_metrics
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
from tests._support.optimizer_graph_ready_benchmark import (
    OBJECTIVE_NAME,
    START_DT,
    _result_order,
    _score_list,
    graph_ready_benchmark_batches,
    graph_ready_benchmark_context,
    graph_ready_benchmark_operations,
    run_graph_ready_real_sgs_case,
)
from tests._support.optimizer_graph_ready_repair_benchmark import run_production_repair_case


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
    production = run_production_repair_case(seed=seed, enabled=with_repair)
    baseline, best, state = production["baseline"], production["best"], production["state"]
    attempts = production["attempts"]
    profile_name = "graph_ready_v2_with_repair" if with_repair else "graph_ready_v2_no_repair"
    profile_summary = graph_ready_v2_profile_summary(max_candidate_profiles=60, seed=int(seed))
    if best is None:
        raise AssertionError("graph-ready v2 benchmark did not return a best candidate")
    repair_info = production["repair"]
    graph_attempts = [attempt for attempt in attempts if str(attempt.get("tag") or "").startswith("graph_ready:")]
    row = _benchmark_row(seed=seed, baseline=baseline, best=best, state=state, graph_attempts=graph_attempts,
                         runtime_ms=production["runtime_ms"])
    v1_reference_score = _score_list(run_graph_ready_real_sgs_case(seed=seed).get("objective_score"))
    row.update(
        {
            "algorithm_profile": profile_name,
            "algorithm_version": str(profile_summary["objective_candidate_version"]),
            "candidate_origin": str(best.get("candidate_origin") or ""),
            "best_origin": str(state.best_origin or best.get("candidate_origin") or ""),
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
            "repair_scope": "production_core",
            "runtime_ms": production["runtime_ms"],
            "max_candidates": production["max_candidates"],
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
    runtime_ms: float,
) -> Dict[str, Any]:
    baseline_score = _score_list(baseline.get("score"))
    best_score = _score_list(best.get("score"))
    failed_ops = int(getattr(best.get("summary"), "failed_ops", 0) or 0)
    baseline_failed_ops = int(getattr(baseline.get("summary"), "failed_ops", 0) or 0)
    graph_profile = state.candidate_profile["graph_ready_optimization"]
    efficiency = graph_profile["profile_efficiency"]
    profile_attempts = [attempt for attempt in graph_attempts if attempt["candidate_origin"] != GRAPH_READY_V2_REPAIRED_ORIGIN]
    covered_slugs = {attempt["weight_profile_slug"] for attempt in profile_attempts}
    covered_slugs.update(item["profile_slug"] for item in efficiency["equivalent_profiles"])
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
        "runtime_ms": runtime_ms,
        "candidate_profile_count": int(efficiency["configured_profiles"]),
        "decoded_profile_count": len(profile_attempts),
        "predecode_pruned_profiles": int(efficiency["predecode_pruned_profiles"]),
        "profile_efficiency": dict(efficiency),
        "configured_profile_slugs": list(graph_profile["weight_profile_slugs"]),
        "covered_profile_slugs": sorted(covered_slugs),
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


def _v2_row_passes(row: Dict[str, Any]) -> bool:
    best_origin = str(row.get("best_origin") or "")
    comparison_to_v1 = row.get("comparison_to_graph_ready_v1")
    v1_reference_score = _score_list(row.get("v1_reference_objective_score"))
    return (
        int(row.get("failed_ops") or 0) == 0
        and bool(row.get("objective_score_matched"))
        and _profile_coverage_passes(row)
        and int(row.get("distinct_candidates") or 0) >= 3
        and best_origin in {"graph_ready_v2_generated", GRAPH_READY_V2_REPAIRED_ORIGIN}
        and isinstance(comparison_to_v1, dict)
        and comparison_to_v1.get("status") == "improved"
        and tuple(_score_list(row.get("objective_score"))) <= tuple(_score_list(row.get("baseline_objective_score")))
        and tuple(_score_list(row.get("objective_score"))) < tuple(v1_reference_score)
    )


def _profile_coverage_passes(row: Dict[str, Any]) -> bool:
    efficiency = row.get("profile_efficiency")
    if not isinstance(efficiency, dict):
        return False
    configured = int(efficiency["configured_profiles"])
    considered = int(efficiency["considered_profiles"])
    decoded = int(efficiency["profile_decodes"])
    unrun = sum(int(efficiency[key]) for key in ("construction_rejected_profiles", "skipped_before_decode", "unvisited_profiles"))
    actual_decodes = int(row["decoded_profile_count"]) + int(row["repair_evaluated_candidates"])
    configured_slugs = set(row["configured_profile_slugs"])
    expected = graph_ready_v2_profile_summary(
        max_candidate_profiles=60, seed=int(row["seed"]), objective_name=row["objective_name"],
    )
    # Coverage includes proven aliases; evaluations count only actual SGS calls.
    return (
        configured == considered == int(row["candidate_profile_count"]) == len(configured_slugs)
        == expected["effective_candidate_profile_count"]
        and row["configured_profile_slugs"] == expected["weight_profile_slugs"]
        and row["formula_versions"] == expected["formula_versions"]
        and row["algorithm_version"] == expected["objective_candidate_version"]
        and unrun == 0
        and 0 < decoded == int(row["decoded_profile_count"])
        and decoded + int(efficiency["predecode_pruned_profiles"]) == considered
        and configured_slugs == set(row["covered_profile_slugs"])
        and int(row["evaluated_candidates"]) == actual_decodes + 1
        and actual_decodes <= int(row["max_candidates"])
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
