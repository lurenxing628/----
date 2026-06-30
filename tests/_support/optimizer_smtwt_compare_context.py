"""Case context and row builders for SMTWT optimizer comparison."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.algorithms import GreedyScheduler, SortStrategy
from core.algorithms.evaluation import compute_metrics, objective_score
from core.services.scheduler.run.optimizer_candidate_fingerprint import build_candidate_fingerprint
from core.services.scheduler.run.optimizer_proof_oracle import _operation_object, batch_objects
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
from tests._support.optimizer_smtwt_compare_common import (
    SAME_BUDGET_SEMANTICS,
    SMTWT_COMPARE_SCHEMA_VERSION,
    make_scheduler,
    score_list,
)


def build_case_context(*, case: Any, time_budget_seconds: int) -> Dict[str, Any]:
    operations = [_operation_object(op) for op in case.operations]
    batches = batch_objects(case)
    scheduler = make_scheduler()
    baseline = baseline_candidate(scheduler=scheduler, operations=operations, batches=batches, case=case)
    return {
        "case": case,
        "operations": operations,
        "batches": batches,
        "scheduler": scheduler,
        "baseline": baseline,
        "time_budget_seconds": int(time_budget_seconds),
        "base_order": [batch.batch_id for batch in case.batches],
    }


def baseline_candidate(*, scheduler: GreedyScheduler, operations: List[Any], batches: Dict[str, Any], case: Any) -> Dict[str, Any]:
    results, summary, strategy, params = scheduler.schedule(
        operations=operations,
        batches=batches,
        strategy=SortStrategy.PRIORITY_FIRST,
        start_dt=case.start_dt,
        dispatch_mode="sgs",
        dispatch_rule=case.dispatch_rule,
        seed_results=[],
        strict_mode=True,
    )
    return candidate_payload(
        results=results,
        summary=summary,
        strategy=strategy,
        params=params,
        dispatch_rule=case.dispatch_rule,
        batches=batches,
        objective_name=case.objective_name,
        origin="baseline",
        runtime_ms=0,
    )


def candidate_payload(
    *,
    results: List[Any],
    summary: Any,
    strategy: SortStrategy,
    params: Dict[str, Any],
    dispatch_rule: str,
    batches: Dict[str, Any],
    objective_name: str,
    origin: str,
    runtime_ms: int,
) -> Dict[str, Any]:
    metrics = compute_metrics(results, batches)
    return {
        "results": results,
        "summary": summary,
        "strategy": strategy,
        "params": dict(params or {}),
        "dispatch_mode": "sgs",
        "dispatch_rule": dispatch_rule,
        "metrics": metrics,
        "score": (float(summary.failed_ops),) + objective_score(objective_name, metrics),
        "algo_stats": {},
        "resource_pool": {},
        "candidate_origin": origin,
        "runtime_ms": int(runtime_ms),
    }


def row_from_candidate(
    candidate: Dict[str, Any],
    *,
    profile: str,
    version: str,
    context: Dict[str, Any],
    optimum: int,
    seed: int,
    state: Optional[OptimizationSearchReportState] = None,
) -> Dict[str, Any]:
    metrics = candidate["metrics"]
    overdue = int(metrics.overdue_count)
    failed_ops = int(getattr(candidate.get("summary"), "failed_ops", 0) or 0)
    output_fingerprint = _candidate_output_fingerprint(candidate, objective_name=str(context["case"].objective_name))
    row = _base_row(profile=profile, version=version, context=context, seed=seed)
    row.update(
        {
            "objective_score": score_list(candidate.get("score")),
            "overdue_count": overdue,
            "optimal_overdue_count": int(optimum),
            "overdue_gap_to_opt": int(overdue - int(optimum)),
            "failed_ops": failed_ops,
            "runtime_ms": int(candidate.get("runtime_ms") or 0),
            "evaluated_candidates": _state_number(state, "evaluated_candidates", 1),
            "distinct_candidates": _distinct_count(state),
            "accepted_candidates": _state_number(state, "accepted_candidates", 1),
            "accepted_distinct_candidates": _accepted_distinct_count(state, output_fingerprint),
            "candidate_rejections": dict(getattr(state, "rejection_summary", {}) if state is not None else {}),
            "best_origin": str(getattr(state, "best_origin", "") or candidate.get("candidate_origin") or profile),
            "candidate_origin": str(candidate.get("candidate_origin") or profile),
            "best_output_fingerprint": str(getattr(state, "best_fingerprint", "") or output_fingerprint),
            "candidate_output_fingerprints": _state_fingerprints(state, "candidate_fingerprints", output_fingerprint),
            "accepted_output_fingerprints": _state_fingerprints(state, "accepted_fingerprints", output_fingerprint),
            "best_order": [int(getattr(result, "op_id")) for result in list(candidate.get("results") or [])],
            "status": "passed" if failed_ops == 0 and overdue >= int(optimum) else "failed",
        }
    )
    return row


def _base_row(*, profile: str, version: str, context: Dict[str, Any], seed: int) -> Dict[str, Any]:
    return {
        "schema_version": SMTWT_COMPARE_SCHEMA_VERSION,
        "case_group": "smtwt_overdue",
        "case_slug": str(context["case"].slug),
        "algorithm_profile": profile,
        "algorithm_version": version,
        "seed": int(seed),
        "time_budget_seconds": int(context["time_budget_seconds"]),
        "comparison_semantics": SAME_BUDGET_SEMANTICS,
        "objective_name": str(context["case"].objective_name),
    }


def _state_number(state: Optional[OptimizationSearchReportState], name: str, default: int) -> int:
    if state is None:
        return int(default)
    return int(getattr(state, name, default) or 0)


def _distinct_count(state: Optional[OptimizationSearchReportState]) -> int:
    if state is None:
        return 1
    return int(len(getattr(state, "candidate_fingerprints", [])))


def _accepted_distinct_count(state: Optional[OptimizationSearchReportState], fallback: str) -> int:
    return len(_state_fingerprints(state, "accepted_fingerprints", fallback))


def _state_fingerprints(state: Optional[OptimizationSearchReportState], name: str, fallback: str) -> List[str]:
    if state is None:
        return [str(fallback)]
    values = sorted(str(item) for item in getattr(state, name, set()) if str(item))
    return values or [str(fallback)]


def _candidate_output_fingerprint(candidate: Dict[str, Any], *, objective_name: str) -> str:
    return build_candidate_fingerprint(
        candidate,
        objective_name=objective_name,
        parent_fingerprint=None,
        seen_output_fingerprints=set(),
    ).output_fingerprint
