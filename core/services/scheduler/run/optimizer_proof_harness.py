from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.objective_specs import objective_metric_keys
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.optimizer_proof_cases import (
    TinyBatchSpec,
    TinyBenchmarkCase,
    TinyOperationSpec,
    build_default_tiny_cases,
)
from core.services.scheduler.run.optimizer_proof_contracts import (
    BOUND_SCOPE_FOLDED_FJSP,
    BOUND_SCOPE_SAME_MODEL,
    FORBIDDEN_PUBLIC_TOKENS,
    REFERENCE_FOLDED_NOT_COMPARABLE,
    REFERENCE_LOWER_BOUND,
    REFERENCE_PROVEN_OPTIMUM,
    REFERENCE_SCHEMA_VERSION,
    assert_benchmark_reference_contract,
    assert_public_payload_safe,
    best_known_score,
    gap_pct,
    gap_to_score,
    render_optimizer_proof_report,
    require_known_objective,
    score_equal,
)
from core.services.scheduler.run.optimizer_proof_oracle import (
    assert_oracle_decoder_matches_greedy,
    batch_objects,
    makespan_lower_bound,
    run_case_with_greedy,
    run_exact_oracle,
)

HARNESS_SCHEMA_VERSION = 1


def run_optimizer_proof_harness(
    cases: Optional[Sequence[TinyBenchmarkCase]] = None,
    *,
    require_optimal: bool = False,
) -> Dict[str, Any]:
    selected_cases = tuple(cases or build_default_tiny_cases())
    references = [build_tiny_case_reference(case) for case in selected_cases]
    public_cases = [dict(ref["public"]) for ref in references]
    public = {
        "schema_version": HARNESS_SCHEMA_VERSION,
        "status": "passed",
        "case_count": len(public_cases),
        "cases": public_cases,
    }
    assert_public_payload_safe(public)
    blockers = _proof_blockers(references, require_optimal=bool(require_optimal))
    status = "failed" if blockers else "passed"
    public["status"] = status
    return {
        "schema_version": HARNESS_SCHEMA_VERSION,
        "status": status,
        "references": references,
        "public": public,
        "blockers": blockers,
    }


def build_tiny_case_reference(case: TinyBenchmarkCase) -> Dict[str, Any]:
    objective_name = require_known_objective(case.objective_name)
    actual_results, actual_summary = run_case_with_greedy(case)
    assert_oracle_decoder_matches_greedy(case, actual_results)
    actual_metrics = compute_metrics(actual_results, batch_objects(case))
    actual_score = (float(actual_summary.failed_ops),) + objective_score(objective_name, actual_metrics)
    oracle = run_exact_oracle(case, objective_name=objective_name)
    makespan_bound_value, makespan_bound_sources = makespan_lower_bound(case)
    actual_makespan = float(actual_metrics.makespan_hours)
    if actual_makespan + 1e-9 < float(makespan_bound_value):
        raise ValidationError(
            "benchmark lower bound is inconsistent with the decoded schedule.",
            field="lower_bound_value",
            details={
                "case_slug": case.slug,
                "actual_makespan_hours": actual_makespan,
                "lower_bound_value": makespan_bound_value,
            },
        )

    oracle_proven = oracle.status == "proven_optimal"
    reference_type = REFERENCE_PROVEN_OPTIMUM if oracle_proven else REFERENCE_LOWER_BOUND
    oracle_score = list(oracle.best_score or []) if oracle_proven else []
    score_matched = bool(oracle_proven and oracle.best_score is not None and score_equal(actual_score, oracle.best_score))
    gap_to_oracle_pct = None
    if oracle_proven and oracle.best_score is not None:
        gap_to_oracle_pct, _gap_metric_key = gap_to_score(actual_score, oracle.best_score, objective_name)
    known_score = best_known_score(actual_score, oracle.best_score)
    gap_to_best_pct, gap_to_best_metric = gap_to_score(actual_score, known_score, objective_name)
    bound_fields = _reference_bound_fields(
        reference_type=reference_type,
        objective_name=objective_name,
        actual_score=actual_score,
        oracle_score=oracle.best_score,
        actual_makespan=actual_makespan,
        makespan_bound_value=float(makespan_bound_value),
        makespan_bound_sources=makespan_bound_sources,
    )
    ref = {
        "schema_version": REFERENCE_SCHEMA_VERSION,
        "case_slug": str(case.slug),
        "reference_type": reference_type,
        "objective_name": objective_name,
        "objective_metric_keys": list(objective_metric_keys(objective_name)),
        "oracle_status": oracle.status,
        "oracle_optimum": oracle_score if oracle_proven else None,
        "oracle_objective_score": oracle_score,
        "actual_objective_score": list(actual_score),
        "objective_score_matched": bool(score_matched),
        "makespan_lower_bound_value": float(makespan_bound_value),
        "makespan_lower_bound_sources": list(makespan_bound_sources),
        "best_known_upper_bound": list(known_score),
        "gap_to_oracle_pct": gap_to_oracle_pct,
        "gap_to_best_known_pct": gap_to_best_pct,
        "gap_to_best_known_metric_key": gap_to_best_metric,
        "oracle_stats": {
            "nodes": int(oracle.nodes),
            "pruned_by_bound": int(oracle.pruned_by_bound),
            "pruned_by_dominance": int(oracle.pruned_by_dominance),
            "runtime_ms": int(oracle.runtime_ms),
        },
        "public": {
            "case_slug": str(case.slug),
            "status": "reference" if reference_type == REFERENCE_PROVEN_OPTIMUM else "not_comparable",
            "objective_name": objective_name,
            "reference_type": reference_type,
            "oracle_status": oracle.status,
            "objective_score_matched": bool(score_matched),
            "gap_to_oracle_pct": gap_to_oracle_pct,
            "aggregate_counts": {
                "scheduled_ops": int(actual_summary.scheduled_ops),
                "failed_ops": int(actual_summary.failed_ops),
                "oracle_nodes": int(oracle.nodes),
            },
        },
        "diagnostics_ref": None,
    }
    ref.update(bound_fields)
    ref["public"]["bound_metric"] = ref["bound_metric"]
    ref["public"]["bound_is_objective_comparable"] = bool(ref["bound_is_objective_comparable"])
    assert_benchmark_reference_contract(ref)
    return ref


def build_folded_fjsp_reference(
    *,
    case_slug: str,
    objective_name: str,
    actual_makespan_hours: float,
    reference_makespan_hours: float,
    reference_label: str = "BKS",
) -> Dict[str, Any]:
    objective_name = require_known_objective(objective_name)
    actual_value = float(actual_makespan_hours)
    reference_value = float(reference_makespan_hours)
    if actual_value <= 0 or not math.isfinite(actual_value):
        raise ValidationError("FJSP actual makespan must be positive.", field="actual_makespan_hours")
    if reference_value <= 0 or not math.isfinite(reference_value):
        raise ValidationError("FJSP reference makespan must be positive.", field="reference_makespan_hours")
    ref = {
        "schema_version": REFERENCE_SCHEMA_VERSION,
        "case_slug": str(case_slug),
        "reference_type": REFERENCE_FOLDED_NOT_COMPARABLE,
        "objective_name": objective_name,
        "objective_metric_keys": list(objective_metric_keys(objective_name)),
        "bound_metric": "makespan_hours",
        "bound_scope": BOUND_SCOPE_FOLDED_FJSP,
        "bound_is_objective_comparable": False,
        "oracle_status": "not_run",
        "oracle_optimum": None,
        "oracle_objective_score": [],
        "objective_score_matched": False,
        "actual_metric_value": actual_value,
        "actual_objective_score": [],
        "lower_bound_value": None,
        "lower_bound_sources": [],
        "best_known_upper_bound": reference_value,
        "gap_to_oracle_pct": None,
        "gap_to_bound_pct": None,
        "gap_to_bound_metric_key": None,
        "gap_to_best_known_pct": gap_pct(actual_value, reference_value),
        "gap_to_best_known_metric_key": "makespan_hours",
        "oracle_stats": {
            "nodes": 0,
            "pruned_by_bound": 0,
            "pruned_by_dominance": 0,
            "runtime_ms": 0,
        },
        "public": {
            "case_slug": str(case_slug),
            "status": "not_comparable",
            "objective_name": objective_name,
            "bound_metric": "makespan_hours",
            "reference_type": REFERENCE_FOLDED_NOT_COMPARABLE,
            "reference_label": str(reference_label),
            "bound_is_objective_comparable": False,
            "oracle_status": "not_run",
            "objective_score_matched": False,
            "gap_to_oracle_pct": None,
            "gap_to_best_known_pct": gap_pct(actual_value, reference_value),
            "aggregate_counts": {},
        },
        "diagnostics_ref": None,
    }
    assert_benchmark_reference_contract(ref)
    return ref


def _reference_bound_fields(
    *,
    reference_type: str,
    objective_name: str,
    actual_score: Sequence[float],
    oracle_score: Optional[Sequence[float]],
    actual_makespan: float,
    makespan_bound_value: float,
    makespan_bound_sources: Sequence[str],
) -> Dict[str, Any]:
    if reference_type == REFERENCE_PROVEN_OPTIMUM:
        gap_to_bound_pct, gap_to_bound_metric = gap_to_score(actual_score, oracle_score or (), objective_name)
        return {
            "bound_metric": "objective_score",
            "bound_scope": BOUND_SCOPE_SAME_MODEL,
            "bound_is_objective_comparable": True,
            "actual_metric_value": list(actual_score),
            "lower_bound_value": list(oracle_score or []),
            "lower_bound_sources": ["exact_oracle"],
            "gap_to_bound_pct": gap_to_bound_pct,
            "gap_to_bound_metric_key": gap_to_bound_metric,
        }
    return {
        "bound_metric": "makespan_hours",
        "bound_scope": BOUND_SCOPE_SAME_MODEL,
        "bound_is_objective_comparable": False,
        "actual_metric_value": actual_makespan,
        "lower_bound_value": float(makespan_bound_value),
        "lower_bound_sources": list(makespan_bound_sources),
        "gap_to_bound_pct": gap_pct(actual_makespan, float(makespan_bound_value)),
        "gap_to_bound_metric_key": "makespan_hours",
    }


def _proof_blockers(references: Sequence[Dict[str, Any]], *, require_optimal: bool) -> List[Dict[str, Any]]:
    blockers: List[Dict[str, Any]] = []
    for ref in references:
        if ref.get("reference_type") == REFERENCE_PROVEN_OPTIMUM and ref.get("oracle_status") != "proven_optimal":
            blockers.append({"case_slug": ref.get("case_slug"), "reason": "oracle_not_proven"})
        if require_optimal:
            if ref.get("oracle_status") != "proven_optimal":
                blockers.append({"case_slug": ref.get("case_slug"), "reason": "oracle_not_proven"})
            elif not ref.get("objective_score_matched"):
                blockers.append({"case_slug": ref.get("case_slug"), "reason": "actual_not_oracle_optimal"})
    return blockers
