"""回归测试：图 ready 候选搜索合同。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from core.algorithms import GreedyScheduler
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.sort_strategies import SortStrategy
from core.algorithms.types import ScheduleResult, ScheduleSummary
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.optimizer_graph_ready import run_graph_ready_candidates
from core.services.scheduler.run.optimizer_graph_ready_candidates import priority_key_for_metric
from core.services.scheduler.run.optimizer_graph_ready_context import (
    graph_node_metrics_by_op_id,
    validate_graph_ready_context,
)
from core.services.scheduler.run.optimizer_graph_ready_profiles import (
    default_weight_profiles,
    graph_ready_weight_profile_summary,
)
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
from core.services.scheduler.summary.optimizer_public_search_report import project_search_report
from tests._support.optimizer_graph_ready_benchmark import (
    ContinuousCalendar,
    graph_ready_benchmark_context,
    graph_ready_benchmark_operations,
    run_graph_ready_flexible_machine_metric_case,
    run_graph_ready_real_sgs_case,
)

_START = datetime(2026, 1, 1, 8, 0, 0)
_OBJECTIVE = "min_overdue"


class _Clock:
    def __init__(self) -> None:
        self._now = 1000.0

    def __call__(self) -> float:
        self._now += 0.01
        return self._now


def _op(op_id: int, batch_id: str) -> SimpleNamespace:
    return SimpleNamespace(id=op_id, batch_id=batch_id)


def _result(op_id: int, batch_id: str, offset: int) -> ScheduleResult:
    start_time = _START + timedelta(hours=offset)
    return ScheduleResult(
        op_id=op_id,
        op_code=f"{batch_id}-{op_id}",
        batch_id=batch_id,
        seq=op_id * 10,
        machine_id="MC-1",
        operator_id="OP-1",
        start_time=start_time,
        end_time=start_time + timedelta(hours=1),
        op_type_name="cut",
    )


def _summary(results: List[ScheduleResult], *, failed_ops: int = 0) -> ScheduleSummary:
    return ScheduleSummary(
        success=failed_ops == 0,
        total_ops=len(results),
        scheduled_ops=len(results),
        failed_ops=failed_ops,
        warnings=[],
        errors=[],
        duration_seconds=0.0,
    )


def _batches() -> Dict[str, Any]:
    return {
        batch_id: SimpleNamespace(batch_id=batch_id, priority="normal", due_date="2026-01-10", ready_status="yes")
        for batch_id in ("B1", "B2")
    }


def _context() -> Dict[str, Any]:
    return {
        "enabled": True,
        "schedulable_op_ids": {1, 2},
        "fixed_op_ids": set(),
        "fixed_op_sources_by_op_id": {},
        "predecessor_op_ids_by_op_id": {1: set(), 2: {1}},
        "successor_op_ids_by_op_id": {1: {2}, 2: set()},
        "sort_key_by_op_id": {1: (0, 0, 1), 2: (1, 0, 2)},
        "graph_priority_key_by_op_id": {1: (0.0,), 2: (1.0,)},
        "node_metrics_by_op_id": {
            1: {
                "is_on_critical_path": True,
                "critical_path_rank": 0,
                "impact_count": 1,
                "downstream_critical_minutes": 60,
                "bottleneck_machine_score": 2.0,
            },
            2: {
                "is_on_critical_path": False,
                "critical_path_rank": 1,
                "impact_count": 0,
                "downstream_critical_minutes": 0,
                "bottleneck_machine_score": 1.0,
            },
        },
    }


def _candidate(results: List[ScheduleResult], *, failed_ops: int = 0) -> Dict[str, Any]:
    metrics = compute_metrics(results, _batches())
    return {
        "results": results,
        "summary": _summary(results, failed_ops=failed_ops),
        "strategy": SortStrategy.PRIORITY_FIRST,
        "params": {},
        "dispatch_mode": "sgs",
        "dispatch_rule": "slack",
        "order": ["B1", "B2"],
        "metrics": metrics,
        "score": (float(failed_ops),) + objective_score(_OBJECTIVE, metrics),
        "algo_stats": {},
    }


def _state() -> OptimizationSearchReportState:
    return OptimizationSearchReportState(
        algorithm_profile="graph_ready",
        seed=42,
        time_budget_seconds=5,
        objective_name=_OBJECTIVE,
        started_at=1000.0,
        candidate_profile={"acceptance": "improve_only"},
    )


def _same_schedule(*args: Any, **kwargs: Any):
    results = [_result(1, "B1", 0), _result(2, "B2", 1)]
    return results, _summary(results), kwargs["strategy"], dict(kwargs.get("strategy_params") or {})


def test_graph_ready_weight_profile_summary_lists_nine_profiles() -> None:
    summary = graph_ready_weight_profile_summary()
    assert summary["effective_weight_profile_count"] == 9
    assert summary["weight_profile_slugs"] == [
        "balanced",
        "critical_path_first",
        "successor_fanout_first",
        "downstream_work_first",
        "bottleneck_relief",
        "critical_bottleneck",
        "fanout_downstream",
        "bottleneck_downstream",
        "graph_neutral",
    ]
    assert summary["selection_tiebreaker"] == [
        "failed_ops",
        "objective_score",
        "best_fingerprint_changed",
        "runtime_ms",
        "candidate_origin",
    ]


def test_graph_ready_context_rejects_cycle_and_extra_keys() -> None:
    bad = _context()
    bad["predecessor_op_ids_by_op_id"] = {1: {2}, 2: {1}}
    bad["successor_op_ids_by_op_id"] = {1: {2}, 2: {1}}
    with pytest.raises(ValidationError, match="环形"):
        validate_graph_ready_context(bad, algo_ops_to_schedule=[_op(1, "B1"), _op(2, "B2")])

    bad = _context()
    bad["sort_key_by_op_id"][3] = (2, 0, 3)
    with pytest.raises(ValidationError, match="完全一致"):
        validate_graph_ready_context(bad, algo_ops_to_schedule=[_op(1, "B1"), _op(2, "B2")])


def test_graph_ready_requires_node_metrics_for_weight_grid() -> None:
    bad = _context()
    bad.pop("node_metrics_by_op_id")
    with pytest.raises(ValidationError, match="node_metrics_by_op_id"):
        graph_node_metrics_by_op_id(bad)


def test_graph_ready_rejects_missing_bottleneck_machine_metric_loudly() -> None:
    bad = graph_ready_benchmark_context(include_bottleneck=False)
    baseline = _candidate([_result(1, "B1", 2), _result(2, "B2", 3)], failed_ops=1)
    with pytest.raises(ValidationError, match="bottleneck_machine_score"):
        run_graph_ready_candidates(
            algo_mode="improve",
            best=baseline,
            version=42,
            scheduler=GreedyScheduler(calendar_service=ContinuousCalendar()),
            algo_ops_to_schedule=graph_ready_benchmark_operations(),
            batches={
                "B_LONG": _batches()["B1"],
                "B_MED": _batches()["B2"],
                "B_SHORT_A": _batches()["B1"],
                "B_SHORT_B": _batches()["B2"],
            },
            start_dt=_START,
            end_date=None,
            downtime_map={},
            seed_sr_list=[],
            base_strategy=SortStrategy.PRIORITY_FIRST,
            base_params={},
            build_order=lambda _strategy, _params: ["B_LONG", "B_MED", "B_SHORT_A", "B_SHORT_B"],
            dispatch_rule_cfg="slack",
            resource_pool=None,
            objective_name=_OBJECTIVE,
            deadline=2000.0,
            attempts=[],
            improvement_trace=[],
            optimizer_algo_stats={},
            t_begin=1000.0,
            readiness_gate_enabled=False,
            strict_mode=True,
            graph_ready_context=bad,
            clock=_Clock(),
            schedule_fn=_same_schedule,
            search_report_state=_state(),
        )


def test_graph_ready_weight_grid_uses_bottleneck_metric_in_priority_keys() -> None:
    metrics_by_op_id = graph_ready_benchmark_context()["node_metrics_by_op_id"]
    profiles, truncated, reason = default_weight_profiles(max_weight_profiles=9)
    assert truncated is False
    assert reason is None

    orders = {
        profile.slug: tuple(
            sorted(
                metrics_by_op_id,
                key=lambda op_id: priority_key_for_metric(metrics_by_op_id[op_id], profile=profile),
            )
        )
        for profile in profiles
    }

    assert len(set(orders.values())) >= 3
    assert orders["downstream_work_first"][0] == 1
    assert orders["successor_fanout_first"][0] == 2
    assert orders["bottleneck_relief"][0] == 3


def test_graph_ready_candidates_run_real_sgs_weight_grid() -> None:
    row = run_graph_ready_real_sgs_case(seed=0)

    assert row["status"] == "passed"
    assert row["candidate_profile_count"] == 9
    assert row["evaluated_candidates"] >= 10
    assert row["distinct_candidates"] >= 3
    assert row["accepted_distinct_candidates"] >= 2
    assert row["best_origin"] == "graph_ready_weight_grid"
    assert tuple(row["objective_score"]) < tuple(row["baseline_objective_score"])
    assert row["best_order"] != row["baseline_order"]


def test_graph_ready_flexible_machine_metric_case_keeps_candidates_from_collapsing_to_busy_machine() -> None:
    row = run_graph_ready_flexible_machine_metric_case()
    scores = row["bottleneck_scores"]

    assert row["status"] == "passed"
    assert scores["busy"] == 2.5
    assert scores["light"] == 1.0
    assert scores["flex"] == 0.707107
    assert scores["flex"] < scores["light"] < scores["busy"]


def test_graph_ready_candidates_deduplicate_same_output_fingerprint() -> None:
    state = _state()
    baseline = _candidate([_result(1, "B1", 2), _result(2, "B2", 3)], failed_ops=1)
    state.mark_candidate_accepted(baseline, origin="baseline")

    best = run_graph_ready_candidates(
        algo_mode="improve",
        best=baseline,
        version=42,
        scheduler=SimpleNamespace(_last_algo_stats={}),
        algo_ops_to_schedule=[_op(1, "B1"), _op(2, "B2")],
        batches=_batches(),
        start_dt=_START,
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        base_strategy=SortStrategy.PRIORITY_FIRST,
        base_params={},
        build_order=lambda _strategy, _params: ["B1", "B2"],
        dispatch_rule_cfg="slack",
        resource_pool=None,
        objective_name=_OBJECTIVE,
        deadline=2000.0,
        attempts=[],
        improvement_trace=[],
        optimizer_algo_stats={},
        t_begin=1000.0,
        readiness_gate_enabled=False,
        strict_mode=True,
        graph_ready_context=_context(),
        clock=_Clock(),
        schedule_fn=_same_schedule,
        search_report_state=state,
    )

    assert best["candidate_origin"] == "graph_ready_base"
    assert state.rejection_summary["same_fingerprint"] >= 1


def test_graph_ready_public_projection_does_not_leak_internal_context() -> None:
    report = {
        "schema_version": 1,
        "algorithm_profile": "graph_ready",
        "candidate_profile": {
            "profile": "graph_ready",
            "candidate_strategy_families": ["graph_ready_base", "graph_ready_weight_grid"],
            "candidate_construction": {"graph_ready_optimization": graph_ready_weight_profile_summary()},
            "graph_ready_context": {
                "schedulable_op_ids": ["op:SECRET"],
                "predecessor_op_ids_by_op_id": {"op:SECRET": ["other"]},
                "graph_priority_key_by_op_id": {"op:SECRET": [1.0]},
            },
        },
    }
    public, diagnostics = project_search_report(report)
    public_text = json.dumps(public, ensure_ascii=False, sort_keys=True)
    diagnostic_text = json.dumps(diagnostics, ensure_ascii=False, sort_keys=True)

    assert "graph_ready_weight_grid" in public_text
    assert "graph_ready_optimization" in diagnostic_text
    assert "schedulable_op_ids" not in public_text
    assert "predecessor_op_ids_by_op_id" not in public_text
    assert "graph_priority_key_by_op_id" not in public_text
    assert "op:SECRET" not in public_text
