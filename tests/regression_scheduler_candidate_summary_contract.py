from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Iterator

from core.services.scheduler.run.schedule_candidate_runner import CandidateComparisonOutcome, CandidatePlan
from core.services.scheduler.run.schedule_candidate_selection import CandidateSelectionResult
from core.services.scheduler.run.schedule_candidate_summary import (
    candidate_comparison_log_summary,
    candidate_comparison_minimal_summary,
    candidate_comparison_public_summary,
)
from core.services.scheduler.run.schedule_orchestrator import _graph_analysis_for_summary
from core.services.scheduler.run.schedule_persistence import _operation_log_algo_summary
from core.services.scheduler.summary.summary_size_guard import apply_summary_size_guard


def _dt(hours: int) -> datetime:
    return datetime(2026, 5, 1, 8, 0, 0) + timedelta(hours=hours)


def _result() -> SimpleNamespace:
    return SimpleNamespace(
        op_id=10,
        op_code="OP10",
        batch_id="B1",
        machine_id="M1",
        operator_id="O1",
        start_time=_dt(0),
        end_time=_dt(1),
    )


def _comparison() -> CandidateComparisonOutcome:
    candidate = CandidatePlan(
        sequence=1,
        candidate_key="graph_w1_of_3",
        kind="critical_chain",
        label="重点工序优先方案 1/3",
        status="completed",
        score=(0, 0, 1.0),
        graph_critical_weight=500,
        graph_impact_weight=10,
        graph_downstream_weight=1,
        results=[_result()],
        metrics=SimpleNamespace(
            overdue_count=0,
            total_tardiness_hours=1.0,
            weighted_tardiness_hours=1.0,
            makespan_hours=1.0,
            changeover_count=0,
        ),
        graph_analysis_public={"status": "available"},
        graph_analysis_diagnostics={
            "nodes": [{"id": "op:10"}],
            "edges": [{"source": "op:10", "target": "op:20"}],
            "node_metrics": {"op:10": {"impact_count": 1}},
        },
        attempts=[{"used_params": {"large": "x" * 100}}],
        improvement_trace=[{"score": [0, 0, 1.0]}],
    )
    selection = CandidateSelectionResult(
        selected_candidate_key=candidate.candidate_key,
        selected_kind=candidate.kind,
        selection_policy="balanced",
        reason_code="balanced_critical_health_better",
        raw_score_best_key=candidate.candidate_key,
        baseline_best_key=None,
        critical_best_key=candidate.candidate_key,
        critical_health_best_key=candidate.candidate_key,
        selected_score=candidate.score or (),
        selected_plan=candidate,
    )
    return CandidateComparisonOutcome(
        candidates=[candidate],
        selection=selection,
        planned_count=1,
        completed_count=1,
        failed_count=0,
        skipped_count=0,
        time_budget_reached=False,
        selection_policy="balanced",
        run_time_budget_seconds=20.0,
        skipped_candidate_labels=[],
        baseline_missing_or_failed=True,
    )


def _baseline_adopted_comparison_with_critical_graph() -> CandidateComparisonOutcome:
    baseline = CandidatePlan(
        sequence=0,
        candidate_key="baseline",
        kind="baseline",
        label="原算法",
        status="completed",
        score=(0, 0, 1.0),
        graph_critical_weight=0,
        graph_impact_weight=0,
        graph_downstream_weight=0,
        results=[_result()],
    )
    critical = CandidatePlan(
        sequence=1,
        candidate_key="graph_w1_of_3",
        kind="critical_chain",
        label="重点工序优先方案 1/3",
        status="completed",
        score=(0, 1, 2.0),
        graph_critical_weight=500,
        graph_impact_weight=10,
        graph_downstream_weight=1,
        results=[_result()],
        graph_analysis_public={
            "status": "available",
            "effective_mode": "sgs_without_graph_ready_queue",
            "ready_queue_enabled": False,
        },
        graph_analysis_diagnostics={
            "nodes": [{"id": "op:10"}],
            "edges": [{"source": "op:10", "target": "op:20"}],
            "node_metrics": {"op:10": {"impact_count": 1}},
        },
    )
    selection = CandidateSelectionResult(
        selected_candidate_key=baseline.candidate_key,
        selected_kind=baseline.kind,
        selection_policy="balanced",
        reason_code="balanced_raw_score_best",
        raw_score_best_key=baseline.candidate_key,
        baseline_best_key=baseline.candidate_key,
        critical_best_key=critical.candidate_key,
        critical_health_best_key=None,
        selected_score=baseline.score or (),
        selected_plan=baseline,
    )
    return CandidateComparisonOutcome(
        candidates=[baseline, critical],
        selection=selection,
        planned_count=2,
        completed_count=2,
        failed_count=0,
        skipped_count=0,
        time_budget_reached=False,
        selection_policy="balanced",
        run_time_budget_seconds=20.0,
        skipped_candidate_labels=[],
        baseline_missing_or_failed=False,
    )


def _iter_keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _iter_keys(child)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_keys(item)


def test_candidate_public_summary_is_small_and_does_not_embed_rows_or_graph_diagnostics() -> None:
    public = candidate_comparison_public_summary(_comparison())
    keys = set(_iter_keys(public))

    assert public["adopted_candidate_key"] == "graph_w1_of_3"
    assert public["run_time_budget_seconds"] == 20.0
    assert public["skipped_candidate_labels"] == []
    assert public["baseline_missing_or_failed"] is True
    assert len(public["candidates"]) == 1
    assert public["candidates"][0]["detail_saved"] is False
    assert "results" not in keys
    assert "start_time" not in keys
    assert "end_time" not in keys
    assert "nodes" not in keys
    assert "edges" not in keys
    assert "node_metrics" not in keys
    assert "graph_analysis_diagnostics" not in keys
    assert "attempts" not in keys
    assert "improvement_trace" not in keys


def test_candidate_operation_log_summary_drops_candidate_list_and_details() -> None:
    public = candidate_comparison_public_summary(_comparison())
    log_summary = candidate_comparison_log_summary(public)

    assert log_summary == {
        "enabled": True,
        "planned_candidate_count": 1,
        "completed_candidate_count": 1,
        "time_budget_reached": False,
        "run_time_budget_seconds": 20.0,
        "skipped_candidate_labels": [],
        "baseline_missing_or_failed": True,
        "adopted_candidate_key": "graph_w1_of_3",
        "selection_policy": "balanced",
        "selection_reason_code": "balanced_critical_health_better",
    }


def test_summary_size_guard_keeps_minimal_candidate_comparison_when_summary_is_too_large() -> None:
    public = candidate_comparison_public_summary(_comparison())
    guarded = apply_summary_size_guard(
        {
            "summary_schema_version": "1.2",
            "is_simulation": False,
            "completion_status": "success",
            "version": 7,
            "strategy": "priority_first",
            "result_status": "success",
            "counts": {"op_count": 1, "scheduled_ops": 1, "failed_ops": 0},
            "time_cost_ms": 12,
            "algo": {
                "mode": "greedy",
                "objective": "min_overdue",
                "comparison_metric": "overdue_count",
                "time_budget_seconds": 20,
                "candidate_comparison": public,
            },
            "untrimmed_blob": "x" * 700000,
        }
    )

    candidate_summary = guarded["algo"]["candidate_comparison"]
    assert guarded["summary_truncated"] is True
    assert candidate_summary["adopted_candidate_key"] == "graph_w1_of_3"
    assert candidate_summary["run_time_budget_seconds"] == 20.0
    assert candidate_summary["skipped_candidate_labels"] == []
    assert candidate_summary["baseline_missing_or_failed"] is True
    assert "candidates" not in candidate_summary


def test_baseline_adopted_still_exposes_critical_graph_public_summary_without_log_details() -> None:
    comparison = _baseline_adopted_comparison_with_critical_graph()
    public, diagnostics = _graph_analysis_for_summary(comparison, comparison.selection.selected_plan)

    assert public == {
        "status": "available",
        "effective_mode": "sgs_without_graph_ready_queue",
        "ready_queue_enabled": False,
    }
    assert diagnostics is not None

    algo = _operation_log_algo_summary(
        {
            "algo": {
                "graph_analysis": public,
                "candidate_comparison": candidate_comparison_public_summary(comparison),
            },
            "diagnostics": {"graph_analysis": diagnostics},
        }
    )
    keys = set(_iter_keys(algo))
    assert algo["graph_analysis"] == public
    assert algo["candidate_comparison"]["adopted_candidate_key"] == "baseline"
    assert "candidates" not in keys
    assert "diagnostics" not in keys
    assert "nodes" not in keys
    assert "edges" not in keys
    assert "node_metrics" not in keys


def test_candidate_summary_preserves_skipped_labels_in_public_minimal_and_log_views() -> None:
    comparison = _baseline_adopted_comparison_with_critical_graph()
    skipped = CandidatePlan(
        sequence=2,
        candidate_key="graph_w2_of_3",
        kind="critical_chain",
        label="重点工序优先方案 2/3",
        status="skipped",
        score=None,
        graph_critical_weight=500,
        graph_impact_weight=10,
        graph_downstream_weight=1,
        failure_reason="candidate_time_budget_reached",
    )
    comparison = replace(
        comparison,
        candidates=list(comparison.candidates) + [skipped],
        planned_count=3,
        skipped_count=1,
        time_budget_reached=True,
        skipped_candidate_labels=["重点工序优先方案 2/3"],
    )

    public = candidate_comparison_public_summary(comparison)
    minimal = candidate_comparison_minimal_summary(public)
    log_summary = candidate_comparison_log_summary(public)

    assert public["skipped_candidate_labels"] == ["重点工序优先方案 2/3"]
    assert minimal["skipped_candidate_labels"] == ["重点工序优先方案 2/3"]
    assert minimal["baseline_missing_or_failed"] is False
    assert log_summary["skipped_candidate_labels"] == ["重点工序优先方案 2/3"]
    assert log_summary["baseline_missing_or_failed"] is False
