"""回归测试：图 ready 候选搜索合同。"""

from __future__ import annotations

import json
import math
from datetime import datetime, time, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from core.algorithms import GreedyScheduler
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.sort_strategies import SortStrategy
from core.algorithms.types import ScheduleResult, ScheduleSummary
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.optimizer_candidate_profile import build_candidate_profile
from core.services.scheduler.run.optimizer_graph_ready import run_graph_ready_candidates
from core.services.scheduler.run.optimizer_graph_ready_candidates import (
    build_v2_common_rank_cache,
    context_for_profile,
    evaluate_graph_ready_candidate,
    priority_key_for_metric,
)
from core.services.scheduler.run.optimizer_graph_ready_context import (
    graph_node_metrics_by_op_id,
    validate_graph_ready_context,
)
from core.services.scheduler.run.optimizer_graph_ready_profiles import (
    GRAPH_READY_V2_GENERATED_ORIGIN,
    GRAPH_READY_WEIGHT_GRID_ORIGIN,
    GraphReadyWeightProfile,
    default_weight_profiles,
    graph_ready_v2_profile_summary,
    graph_ready_v2_profiles,
    graph_ready_weight_profile_summary,
)
from core.services.scheduler.run.optimizer_graph_ready_v2_features import enrich_graph_ready_v2_metrics
from core.services.scheduler.run.optimizer_runtime import OptimizerRuntime
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
from core.services.scheduler.run.schedule_optimizer import optimize_schedule
from core.services.scheduler.summary.optimizer_public_search_report import project_search_report
from tests._support.optimizer_graph_ready_benchmark import (
    ContinuousCalendar,
    graph_ready_benchmark_context,
    graph_ready_benchmark_operations,
    run_graph_ready_flexible_machine_metric_case,
    run_graph_ready_real_sgs_case,
)
from tests._support.optimizer_graph_ready_v2_benchmark import (
    _v2_row_passes,
    graph_ready_v2_benchmark_context,
    run_graph_ready_v2_real_sgs_case,
)

_START = datetime(2026, 1, 1, 8, 0, 0)
_OBJECTIVE = "min_overdue"


class _Clock:
    def __init__(self) -> None:
        self._now = 1000.0

    def __call__(self) -> float:
        self._now += 0.01
        return self._now


class _EightHourPolicy:
    efficiency = 1.0

    def __init__(self, dt: datetime) -> None:
        self._dt = dt

    def is_priority_allowed(self, _priority: Any) -> bool:
        return True

    def work_window(self):
        start = datetime.combine(self._dt.date(), time(8, 0, 0))
        return start, start + timedelta(hours=8)


class _EightHourCalendar(ContinuousCalendar):
    def policy_for_datetime(self, dt: datetime, operator_id: Any = None):
        return _EightHourPolicy(dt)


class _OptimizerScheduler:
    def __init__(self, calendar_service: Any) -> None:
        self.calendar = calendar_service
        self._last_algo_stats: Dict[str, Any] = {"fallback_counts": {}, "param_fallbacks": {}}

    def schedule(self, **kwargs: Any):
        summary = ScheduleSummary(
            success=True,
            total_ops=0,
            scheduled_ops=0,
            failed_ops=0,
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        )
        return [], summary, kwargs.get("strategy"), dict(kwargs.get("strategy_params") or {})


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


def _optimizer_cfg(**overrides: Any) -> SimpleNamespace:
    data = {
        "sort_strategy": "priority_first",
        "priority_weight": 0.4,
        "due_weight": 0.5,
        "ready_weight": 0.1,
        "holiday_default_efficiency": 0.8,
        "enforce_ready_default": "no",
        "prefer_primary_skill": "no",
        "dispatch_mode": "batch_order",
        "dispatch_rule": "slack",
        "auto_assign_enabled": "no",
        "auto_assign_persist": "yes",
        "ortools_enabled": "no",
        "ortools_time_limit_seconds": 5,
        "algo_mode": "improve",
        "objective": _OBJECTIVE,
        "time_budget_seconds": 5,
        "freeze_window_enabled": "no",
        "freeze_window_days": 0,
        "graph_analysis_mode": "off",
        "graph_block_on_cycle": "no",
        "graph_critical_weight": 500,
        "graph_impact_weight": 10,
        "graph_debug_export": "no",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _optimizer_cfg_svc() -> SimpleNamespace:
    return SimpleNamespace(
        VALID_STRATEGIES=("priority_first", "weighted", "fifo", "edd"),
        VALID_DISPATCH_MODES=("batch_order", "sgs"),
        VALID_DISPATCH_RULES=("slack", "cr"),
        VALID_OBJECTIVES=(_OBJECTIVE,),
        VALID_ALGO_MODES=("greedy", "improve"),
    )


def _graph_v2_metric(index: int = 0) -> Dict[str, Any]:
    return {
        "is_on_critical_path": False,
        "critical_path_rank": None,
        "impact_count": 0,
        "generation_index": int(index),
        "downstream_critical_minutes": 0,
        "bottleneck_machine_score": 1.0,
    }


def _graph_v2_priority_metric(**overrides: Any) -> Dict[str, Any]:
    row = _graph_v2_metric()
    row.update(
        {
            "due_deadline_hours": 24.0,
            "due_budget_hours": 24.0,
            "due_pressure": 0.5,
            "slack_hours": 12.0,
            "remaining_work_hours": 8.0,
            "remaining_due_burden_hours": 8.0,
            "saveability": 0.5,
            "processing_time_rank": 0.0,
            "sacrifice_penalty": 0.0,
            "critical_ratio": 3.0,
            "bottleneck_due_gate": 0.5,
        }
    )
    row.update(overrides)
    return row


def _v2_profile(formula_slug: str) -> GraphReadyWeightProfile:
    return GraphReadyWeightProfile(
        slug="test_v2_" + formula_slug,
        profile_order=0,
        raw_weights={
            "critical_path": 0.0,
            "successor_count": 0.0,
            "downstream_work_hours": 0.0,
            "bottleneck_machine": 0.0,
        },
        effective_weights={
            "critical_path": 0.0,
            "successor_count": 0.0,
            "downstream_work_hours": 0.0,
            "bottleneck_machine": 0.0,
        },
        candidate_origin=GRAPH_READY_V2_GENERATED_ORIGIN,
        candidate_policy="objective_aware_portfolio",
        formula_slug=formula_slug,
        formula_version="graph_ready_v2_objective_features_v2",
        jitter_seed=0,
    )


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


def _v2_ops() -> List[Any]:
    return [
        SimpleNamespace(id=1, batch_id="B1", source="internal", machine_id="MC-1", operator_id="OP-1", setup_hours=2.0, unit_hours=0.0),
        SimpleNamespace(id=2, batch_id="B2", source="internal", machine_id="MC-1", operator_id="OP-1", setup_hours=1.0, unit_hours=0.0),
    ]


def _v2_batches() -> Dict[str, Any]:
    return {
        "B1": SimpleNamespace(batch_id="B1", priority="normal", due_date="2026-01-10", ready_status="yes", quantity=1),
        "B2": SimpleNamespace(batch_id="B2", priority="normal", due_date="2026-01-10", ready_status="yes", quantity=1),
    }


def _run_graph_ready_v2_for_test(
    *,
    baseline: Dict[str, Any],
    state: OptimizationSearchReportState,
    strict_mode: bool,
    profiles_override: List[GraphReadyWeightProfile],
    attempts: List[Dict[str, Any]],
    schedule_fn: Any = _same_schedule,
) -> Dict[str, Any]:
    return run_graph_ready_candidates(
        algo_mode="improve",
        best=baseline,
        version=7,
        scheduler=SimpleNamespace(_last_algo_stats={}),
        algo_ops_to_schedule=_v2_ops(),
        batches=_v2_batches(),
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
        attempts=attempts,
        improvement_trace=[],
        optimizer_algo_stats={},
        t_begin=1000.0,
        readiness_gate_enabled=False,
        strict_mode=bool(strict_mode),
        graph_ready_context=_context(),
        clock=_Clock(),
        schedule_fn=schedule_fn,
        search_report_state=state,
        profiles_override=profiles_override,
        profile_summary_override=graph_ready_v2_profile_summary(max_candidate_profiles=len(profiles_override)),
    )


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
    assert row["accepted_distinct_candidates"] == len(row["accepted_output_fingerprints"])
    assert row["best_origin"] == "graph_ready_weight_grid"
    assert row["oracle_status"] == "not_run"
    assert row["gap_to_oracle_pct"] is None
    assert tuple(row["objective_score"]) < tuple(row["baseline_objective_score"])
    assert row["best_order"] != row["baseline_order"]


def test_graph_ready_v2_context_adds_objective_aware_features() -> None:
    metrics_by_op_id = graph_ready_v2_benchmark_context()["node_metrics_by_op_id"]
    row = metrics_by_op_id[1]

    for field in (
        "due_pressure",
        "slack_hours",
        "remaining_work_hours",
        "remaining_due_burden_hours",
        "due_budget_hours",
        "saveability",
        "processing_time_rank",
        "sacrifice_penalty",
        "bottleneck_on",
        "bottleneck_release",
        "residual_capacity_hours",
        "residual_capacity_ratio",
        "residual_capacity_pressure",
    ):
        assert field in row
    assert row["residual_capacity_hours"] == 16.0
    assert row["residual_capacity_pressure"] == 0.0
    assert row["remaining_work_hours"] == 12.0
    assert row["remaining_due_burden_hours"] == 12.0
    assert row["due_budget_basis"] == "wall_clock_hours"
    assert row["sacrifice_penalty"] > metrics_by_op_id[2]["sacrifice_penalty"]
    assert row["graph_ready_v2_feature_version"] == "graph_ready_v2_objective_features_v2"


def test_graph_ready_v2_residual_capacity_uses_calendar_downtime_and_seed_segments() -> None:
    op = SimpleNamespace(
        id=1,
        batch_id="B1",
        source="internal",
        machine_id="MC-1",
        operator_id="OP-1",
        setup_hours=2.0,
        unit_hours=0.0,
    )
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", priority="normal", quantity=1)}
    seed = ScheduleResult(
        op_id=99,
        op_code="SEED",
        batch_id="B0",
        seq=10,
        machine_id="MC-1",
        operator_id="OP-1",
        start_time=_START + timedelta(hours=2),
        end_time=_START + timedelta(hours=4),
        op_type_name="cut",
    )

    enriched = enrich_graph_ready_v2_metrics(
        {1: _graph_v2_metric()},
        operations=[op],
        batches=batches,
        start_dt=_START,
        calendar_service=_EightHourCalendar(),
        downtime_map={"MC-1": [(_START, _START + timedelta(hours=1))]},
        seed_results=[seed],
    )
    row = enriched[1]

    assert row["residual_capacity_window_hours"] == 8.0
    assert row["residual_capacity_blocked_hours"] == 3.0
    assert row["residual_capacity_hours"] == 5.0
    assert row["residual_capacity_ratio"] == 0.625
    assert row["residual_capacity_pressure"] == 0.375
    assert row["bottleneck_on"] == 1.375


def test_graph_ready_v2_due_budget_uses_calendar_capacity_for_internal_work() -> None:
    op = SimpleNamespace(
        id=1,
        batch_id="B1",
        source="internal",
        machine_id="MC-1",
        operator_id="OP-1",
        setup_hours=4.0,
        unit_hours=0.0,
    )
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", priority="normal", quantity=1)}

    enriched = enrich_graph_ready_v2_metrics(
        {1: _graph_v2_metric()},
        operations=[op],
        batches=batches,
        start_dt=_START,
        calendar_service=_EightHourCalendar(),
    )
    row = enriched[1]

    assert row["due_deadline_hours"] == 16.0
    assert row["due_budget_hours"] == 8.0
    assert row["due_budget_basis"] == "calendar_capacity_hours"
    assert row["due_pressure"] == 0.5
    assert row["slack_hours"] == 4.0


def test_graph_ready_v2_calendar_policy_legacy_signature_still_works() -> None:
    class _LegacyCalendar(ContinuousCalendar):
        def policy_for_datetime(self, dt: datetime):
            return _EightHourPolicy(dt)

    op = SimpleNamespace(
        id=1,
        batch_id="B1",
        source="internal",
        machine_id="MC-1",
        operator_id="OP-1",
        setup_hours=4.0,
        unit_hours=0.0,
    )
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", priority="normal", quantity=1)}

    enriched = enrich_graph_ready_v2_metrics(
        {1: _graph_v2_metric()},
        operations=[op],
        batches=batches,
        start_dt=_START,
        calendar_service=_LegacyCalendar(),
    )

    assert enriched[1]["due_budget_basis"] == "calendar_capacity_hours"
    assert enriched[1]["due_budget_hours"] == 8.0


def test_graph_ready_v2_calendar_policy_internal_type_error_is_not_retried_without_operator() -> None:
    class _BrokenOperatorCalendar(ContinuousCalendar):
        def policy_for_datetime(self, dt: datetime, operator_id: Any = None):
            raise TypeError("operator calendar payload is broken")

    op = SimpleNamespace(
        id=1,
        batch_id="B1",
        source="internal",
        machine_id="MC-1",
        operator_id="OP-1",
        setup_hours=4.0,
        unit_hours=0.0,
    )
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", priority="normal", quantity=1)}

    with pytest.raises(TypeError, match="operator calendar payload is broken"):
        enrich_graph_ready_v2_metrics(
            {1: _graph_v2_metric()},
            operations=[op],
            batches=batches,
            start_dt=_START,
            calendar_service=_BrokenOperatorCalendar(),
        )


def test_graph_ready_v2_due_budget_keeps_external_lead_time_on_wall_clock() -> None:
    op = SimpleNamespace(
        id=1,
        batch_id="B1",
        source="external",
        ext_days=2.0,
    )
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-03", priority="normal", quantity=1)}

    enriched = enrich_graph_ready_v2_metrics(
        {1: _graph_v2_metric()},
        operations=[op],
        batches=batches,
        start_dt=_START,
        calendar_service=_EightHourCalendar(),
    )
    row = enriched[1]

    assert row["remaining_work_hours"] == 48.0
    assert row["remaining_due_burden_hours"] == 48.0
    assert row["due_budget_hours"] == 64.0
    assert row["due_budget_basis"] == "wall_clock_hours"


def test_graph_ready_v2_missing_due_date_stays_in_v2_and_is_deprioritized() -> None:
    operations = [
        SimpleNamespace(id=1, batch_id="B1", source="internal", machine_id="MC-1", operator_id="OP-1", setup_hours=1.0, unit_hours=0.0),
        SimpleNamespace(id=2, batch_id="B2", source="internal", machine_id="MC-1", operator_id="OP-1", setup_hours=1.0, unit_hours=0.0),
    ]
    batches = {
        "B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", priority="normal", quantity=1),
        "B2": SimpleNamespace(batch_id="B2", due_date=None, priority="normal", quantity=1),
    }

    enriched = enrich_graph_ready_v2_metrics(
        {1: _graph_v2_metric(), 2: _graph_v2_metric()},
        operations=operations,
        batches=batches,
        start_dt=_START,
        calendar_service=_EightHourCalendar(),
    )
    keys = context_for_profile(
        graph_ready_context={},
        metrics_by_op_id=enriched,
        profile=_v2_profile("edd"),
    )["graph_priority_key_by_op_id"]

    assert enriched[2]["due_budget_basis"] == "no_due_placeholder"
    assert enriched[2]["due_pressure"] == 0.0
    assert enriched[2]["saveability"] == 0.0
    assert enriched[2]["sacrifice_penalty"] > enriched[1]["sacrifice_penalty"]
    assert tuple(sorted(keys, key=lambda op_id: keys[op_id])) == (1, 2)


def test_graph_ready_v2_bad_due_date_non_strict_fails_loud() -> None:
    operations = [
        SimpleNamespace(id=1, batch_id="B1", source="internal", machine_id="MC-1", operator_id="OP-1", setup_hours=1.0, unit_hours=0.0),
        SimpleNamespace(id=2, batch_id="B2", source="internal", machine_id="MC-1", operator_id="OP-1", setup_hours=1.0, unit_hours=0.0),
    ]
    batches = {
        "B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", priority="normal", quantity=1),
        "B2": SimpleNamespace(batch_id="B2", due_date="bad-date", priority="normal", quantity=1),
    }

    with pytest.raises(ValidationError) as exc_info:
        enrich_graph_ready_v2_metrics(
            {1: _graph_v2_metric(), 2: _graph_v2_metric()},
            operations=operations,
            batches=batches,
            start_dt=_START,
            calendar_service=_EightHourCalendar(),
            strict_mode=False,
        )

    assert exc_info.value.field == "graph_ready_v2_features"
    assert exc_info.value.details["reason"] == "graph_ready_v2_bad_due_date"


def test_graph_ready_v2_bad_due_date_strict_fails_loud() -> None:
    op = SimpleNamespace(
        id=1,
        batch_id="B1",
        source="internal",
        machine_id="MC-1",
        operator_id="OP-1",
        setup_hours=1.0,
        unit_hours=0.0,
    )
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="bad-date", priority="normal", quantity=1)}

    with pytest.raises(ValidationError) as exc_info:
        enrich_graph_ready_v2_metrics(
            {1: _graph_v2_metric()},
            operations=[op],
            batches=batches,
            start_dt=_START,
            calendar_service=_EightHourCalendar(),
            strict_mode=True,
        )

    assert exc_info.value.field == "graph_ready_v2_features"
    assert exc_info.value.details["reason"] == "graph_ready_v2_bad_due_date"


def test_graph_ready_v2_merged_external_group_counts_group_total_once_for_remaining_and_ready_offset() -> None:
    operations = [
        SimpleNamespace(
            id=1,
            batch_id="B1",
            seq=10,
            source="external",
            ext_merge_mode="merged",
            ext_group_id="G1",
            ext_group_total_days=3.0,
        ),
        SimpleNamespace(
            id=2,
            batch_id="B1",
            seq=20,
            source="external",
            ext_merge_mode="merged",
            ext_group_id="G1",
            ext_group_total_days=3.0,
        ),
        SimpleNamespace(
            id=3,
            batch_id="B1",
            seq=30,
            source="internal",
            machine_id="MC-1",
            operator_id="OP-1",
            setup_hours=2.0,
            unit_hours=0.0,
        ),
    ]
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-10", priority="normal", quantity=1)}

    enriched = enrich_graph_ready_v2_metrics(
        {1: _graph_v2_metric(), 2: _graph_v2_metric(), 3: _graph_v2_metric()},
        operations=operations,
        batches=batches,
        start_dt=_START,
    )

    assert enriched[1]["remaining_work_hours"] == 74.0
    assert enriched[2]["remaining_work_hours"] == 74.0
    assert enriched[3]["remaining_work_hours"] == 74.0
    assert enriched[1]["residual_capacity_start_offset_hours"] == 0.0
    assert enriched[2]["residual_capacity_start_offset_hours"] == 0.0
    assert enriched[3]["residual_capacity_start_offset_hours"] == 72.0


def test_graph_ready_v2_residual_capacity_merges_overlapping_blocked_segments() -> None:
    op = SimpleNamespace(
        id=1,
        batch_id="B1",
        source="internal",
        machine_id="MC-1",
        operator_id="OP-1",
        setup_hours=2.0,
        unit_hours=0.0,
    )
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", priority="normal", quantity=1)}
    seed = ScheduleResult(
        op_id=99,
        op_code="SEED",
        batch_id="B0",
        seq=10,
        machine_id="MC-1",
        operator_id="OP-1",
        start_time=_START + timedelta(hours=1),
        end_time=_START + timedelta(hours=3),
        op_type_name="cut",
    )

    enriched = enrich_graph_ready_v2_metrics(
        {1: _graph_v2_metric()},
        operations=[op],
        batches=batches,
        start_dt=_START,
        calendar_service=_EightHourCalendar(),
        downtime_map={"MC-1": [(_START, _START + timedelta(hours=2))]},
        seed_results=[seed],
    )
    row = enriched[1]

    assert row["residual_capacity_window_hours"] == 8.0
    assert row["residual_capacity_blocked_hours"] == 3.0
    assert row["residual_capacity_hours"] == 5.0
    assert row["residual_capacity_pressure"] == 0.375


def test_graph_ready_v2_residual_capacity_counts_fixed_operator_seed_on_other_machine() -> None:
    op = SimpleNamespace(
        id=1,
        batch_id="B1",
        source="internal",
        machine_id="MC-1",
        operator_id="OP-1",
        setup_hours=2.0,
        unit_hours=0.0,
    )
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", priority="normal", quantity=1)}
    seed = ScheduleResult(
        op_id=99,
        op_code="SEED",
        batch_id="B0",
        seq=10,
        machine_id="MC-2",
        operator_id="OP-1",
        start_time=_START + timedelta(hours=2),
        end_time=_START + timedelta(hours=5),
        op_type_name="cut",
    )

    enriched = enrich_graph_ready_v2_metrics(
        {1: _graph_v2_metric()},
        operations=[op],
        batches=batches,
        start_dt=_START,
        calendar_service=_EightHourCalendar(),
        seed_results=[seed],
    )
    row = enriched[1]

    assert row["residual_capacity_window_hours"] == 8.0
    assert row["residual_capacity_blocked_hours"] == 3.0
    assert row["residual_capacity_hours"] == 5.0
    assert row["residual_capacity_pressure"] == 0.375


def test_graph_ready_v2_residual_capacity_uses_best_complete_candidate_machine_payload() -> None:
    op = SimpleNamespace(
        id=1,
        batch_id="B1",
        source="internal",
        machine_id=None,
        operator_id=None,
        op_type_id="CUT",
        setup_hours=2.0,
        unit_hours=0.0,
    )
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", priority="normal", quantity=1)}
    resource_pool = {
        "machines_by_op_type": {"CUT": ["MC-TIGHT", "MC-OPEN"]},
        "operators_by_machine": {"MC-TIGHT": ["OP-TIGHT"], "MC-OPEN": ["OP-OPEN"]},
        "machines_by_operator": {"OP-TIGHT": ["MC-TIGHT"], "OP-OPEN": ["MC-OPEN"]},
    }

    enriched = enrich_graph_ready_v2_metrics(
        {1: _graph_v2_metric()},
        operations=[op],
        batches=batches,
        start_dt=_START,
        calendar_service=_EightHourCalendar(),
        downtime_map={
            "MC-TIGHT": [(_START, _START + timedelta(hours=7))],
            "MC-OPEN": [(_START, _START + timedelta(hours=1))],
        },
        resource_pool=resource_pool,
    )
    row = enriched[1]

    assert row["candidate_machine_count"] == 2
    assert row["effective_candidate_machine_count"] == 2
    assert row["resource_candidate_machine_count"] == 2
    assert row["residual_capacity_window_hours"] == 8.0
    assert row["residual_capacity_blocked_hours"] == 1.0
    assert row["residual_capacity_hours"] == 7.0
    assert row["residual_capacity_pressure"] == 0.125
    assert row["bottleneck_on"] == pytest.approx(1.0 + 0.125 / math.sqrt(2.0))


def test_graph_ready_v2_residual_capacity_excludes_no_operator_machine_from_bottleneck_count() -> None:
    op = SimpleNamespace(
        id=1,
        batch_id="B1",
        source="internal",
        machine_id=None,
        operator_id=None,
        op_type_id="CUT",
        setup_hours=2.0,
        unit_hours=0.0,
    )
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", priority="normal", quantity=1)}
    resource_pool = {
        "machines_by_op_type": {"CUT": ["MC-OPEN", "MC-NO-OP"]},
        "operators_by_machine": {"MC-OPEN": ["OP-OPEN"], "MC-NO-OP": []},
        "machines_by_operator": {"OP-OPEN": ["MC-OPEN"]},
    }

    enriched = enrich_graph_ready_v2_metrics(
        {1: _graph_v2_metric()},
        operations=[op],
        batches=batches,
        start_dt=_START,
        calendar_service=_EightHourCalendar(),
        downtime_map={"MC-OPEN": [(_START, _START + timedelta(hours=4))]},
        resource_pool=resource_pool,
    )
    row = enriched[1]

    assert row["resource_candidate_machine_count"] == 2
    assert row["candidate_machine_count"] == 1
    assert row["effective_candidate_machine_count"] == 1
    assert row["bottleneck_machine_count"] == 1
    assert row["residual_capacity_pressure"] == 0.5
    assert row["bottleneck_on"] == 1.5


def test_graph_ready_v2_residual_capacity_rejects_auto_assign_machine_without_operator_capacity() -> None:
    op = SimpleNamespace(
        id=1,
        batch_id="B1",
        source="internal",
        machine_id=None,
        operator_id=None,
        op_type_id="CUT",
        setup_hours=2.0,
        unit_hours=0.0,
    )
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", priority="normal", quantity=1)}
    resource_pool = {
        "machines_by_op_type": {"CUT": ["MC-NO-OP"]},
        "operators_by_machine": {"MC-NO-OP": []},
        "machines_by_operator": {},
    }

    enriched = enrich_graph_ready_v2_metrics(
        {1: _graph_v2_metric()},
        operations=[op],
        batches=batches,
        start_dt=_START,
        calendar_service=_EightHourCalendar(),
        resource_pool=resource_pool,
    )
    row = enriched[1]

    assert row["resource_candidate_machine_count"] == 1
    assert row["candidate_machine_count"] == 0
    assert row["effective_candidate_machine_count"] == 0
    assert row["bottleneck_machine_count"] == 1
    assert row["residual_capacity_window_hours"] == 0.0
    assert row["residual_capacity_hours"] == 0.0
    assert row["residual_capacity_pressure"] == 1.0
    assert row["bottleneck_on"] == 2.0


def test_graph_ready_v2_residual_capacity_rejects_fixed_machine_without_operator_candidate() -> None:
    op = SimpleNamespace(
        id=1,
        batch_id="B1",
        source="internal",
        machine_id="MC-NO-OP",
        operator_id=None,
        op_type_id="CUT",
        setup_hours=2.0,
        unit_hours=0.0,
    )
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", priority="normal", quantity=1)}
    resource_pool = {
        "machines_by_op_type": {"CUT": ["MC-NO-OP"]},
        "operators_by_machine": {"MC-NO-OP": []},
        "machines_by_operator": {},
    }

    enriched = enrich_graph_ready_v2_metrics(
        {1: _graph_v2_metric()},
        operations=[op],
        batches=batches,
        start_dt=_START,
        calendar_service=_EightHourCalendar(),
        resource_pool=resource_pool,
    )
    row = enriched[1]

    assert row["resource_candidate_machine_count"] == 1
    assert row["candidate_machine_count"] == 0
    assert row["effective_candidate_machine_count"] == 0
    assert row["bottleneck_machine_count"] == 1
    assert row["residual_capacity_window_hours"] == 0.0
    assert row["residual_capacity_hours"] == 0.0
    assert row["residual_capacity_pressure"] == 1.0


def test_graph_ready_v2_residual_capacity_rejects_fixed_machine_when_operator_pool_is_empty() -> None:
    op = SimpleNamespace(
        id=1,
        batch_id="B1",
        source="internal",
        machine_id="MC-NO-OP",
        operator_id=None,
        op_type_id="CUT",
        setup_hours=2.0,
        unit_hours=0.0,
    )
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", priority="normal", quantity=1)}
    resource_pool = {
        "machines_by_op_type": {"CUT": ["MC-NO-OP"]},
        "operators_by_machine": {},
        "machines_by_operator": {},
    }

    enriched = enrich_graph_ready_v2_metrics(
        {1: _graph_v2_metric()},
        operations=[op],
        batches=batches,
        start_dt=_START,
        calendar_service=_EightHourCalendar(),
        resource_pool=resource_pool,
    )
    row = enriched[1]

    assert row["resource_candidate_machine_count"] == 1
    assert row["candidate_machine_count"] == 0
    assert row["effective_candidate_machine_count"] == 0
    assert row["bottleneck_machine_count"] == 1
    assert row["residual_capacity_window_hours"] == 0.0
    assert row["residual_capacity_hours"] == 0.0
    assert row["residual_capacity_pressure"] == 1.0


def test_graph_ready_v2_residual_capacity_rejects_fixed_machine_when_resource_pool_is_empty() -> None:
    op = SimpleNamespace(
        id=1,
        batch_id="B1",
        source="internal",
        machine_id="MC-NO-OP",
        operator_id=None,
        op_type_id="CUT",
        setup_hours=2.0,
        unit_hours=0.0,
    )
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", priority="normal", quantity=1)}

    enriched = enrich_graph_ready_v2_metrics(
        {1: _graph_v2_metric()},
        operations=[op],
        batches=batches,
        start_dt=_START,
        calendar_service=_EightHourCalendar(),
        resource_pool={},
    )
    row = enriched[1]

    assert row["resource_candidate_machine_count"] == 1
    assert row["candidate_machine_count"] == 0
    assert row["effective_candidate_machine_count"] == 0
    assert row["bottleneck_machine_count"] == 1
    assert row["residual_capacity_window_hours"] == 0.0
    assert row["residual_capacity_hours"] == 0.0
    assert row["residual_capacity_pressure"] == 1.0


def test_graph_ready_v2_residual_capacity_calendar_window_never_moves_backward() -> None:
    class _PastWindowPolicy:
        efficiency = 1.0

        def is_priority_allowed(self, _priority: Any) -> bool:
            return True

        def work_window(self):
            start = datetime.combine(_START.date(), time(0, 0, 0))
            return start, start + timedelta(hours=1)

    class _PastWindowCalendar(ContinuousCalendar):
        def policy_for_datetime(self, _dt: datetime, operator_id: Any = None):
            return _PastWindowPolicy()

    op = SimpleNamespace(
        id=1,
        batch_id="B1",
        source="internal",
        machine_id="MC-1",
        operator_id="OP-1",
        setup_hours=2.0,
        unit_hours=0.0,
    )
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", priority="normal", quantity=1)}

    enriched = enrich_graph_ready_v2_metrics(
        {1: _graph_v2_metric()},
        operations=[op],
        batches=batches,
        start_dt=_START,
        calendar_service=_PastWindowCalendar(),
    )
    row = enriched[1]

    assert row["residual_capacity_window_hours"] == 0.0
    assert row["residual_capacity_pressure"] == 1.0


def test_graph_ready_v2_residual_capacity_caps_far_future_due_window() -> None:
    op = SimpleNamespace(
        id=1,
        batch_id="B1",
        source="internal",
        machine_id="MC-1",
        operator_id="OP-1",
        setup_hours=2.0,
        unit_hours=0.0,
    )
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2099-12-31", priority="normal", quantity=1)}

    enriched = enrich_graph_ready_v2_metrics(
        {1: _graph_v2_metric()},
        operations=[op],
        batches=batches,
        start_dt=_START,
        calendar_service=_EightHourCalendar(),
    )
    row = enriched[1]

    assert row["residual_capacity_window_hours"] == 240.0
    assert row["residual_capacity_hours"] == 240.0
    assert row["residual_capacity_pressure"] == 0.0


def test_graph_ready_v2_residual_capacity_starts_after_prior_batch_work() -> None:
    operations = [
        SimpleNamespace(id=1, batch_id="B1", seq=10, source="internal", machine_id="MC-1", operator_id="OP-1", setup_hours=4.0, unit_hours=0.0),
        SimpleNamespace(id=2, batch_id="B1", seq=20, source="internal", machine_id="MC-1", operator_id="OP-1", setup_hours=2.0, unit_hours=0.0),
    ]
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", priority="normal", quantity=1)}

    enriched = enrich_graph_ready_v2_metrics(
        {1: _graph_v2_metric(), 2: _graph_v2_metric()},
        operations=operations,
        batches=batches,
        start_dt=_START,
        calendar_service=_EightHourCalendar(),
    )

    assert enriched[1]["residual_capacity_start_offset_hours"] == 0.0
    assert enriched[1]["residual_capacity_window_hours"] == 8.0
    assert enriched[2]["residual_capacity_start_offset_hours"] == 4.0
    assert enriched[2]["residual_capacity_window_hours"] == 4.0


def test_graph_ready_v2_remaining_work_sums_only_schedulable_batch_operations() -> None:
    operations = [
        SimpleNamespace(id=1, batch_id="B1", setup_hours=2.0, unit_hours=0.0),
        SimpleNamespace(id=2, batch_id="B1", setup_hours=5.0, unit_hours=0.0),
        SimpleNamespace(id=3, batch_id="B1", setup_hours=99.0, unit_hours=0.0),
    ]
    metrics = {1: _graph_v2_metric(0), 2: _graph_v2_metric(1)}
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", quantity=1)}

    enriched = enrich_graph_ready_v2_metrics(metrics, operations=operations, batches=batches, start_dt=_START)

    assert set(enriched) == {1, 2}
    assert enriched[1]["remaining_work_hours"] == 7.0
    assert enriched[2]["remaining_work_hours"] == 7.0


def test_graph_ready_v2_duplicate_normalized_metric_ids_fail_loud() -> None:
    op = SimpleNamespace(id=1, batch_id="B1", setup_hours=2.0, unit_hours=0.0)
    batches = {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", quantity=1)}

    with pytest.raises(ValidationError, match="重复 node_metrics_by_op_id"):
        enrich_graph_ready_v2_metrics(
            {1: _graph_v2_metric(0), "1": _graph_v2_metric(1)},
            operations=[op],
            batches=batches,
            start_dt=_START,
        )


@pytest.mark.parametrize("missing_field", ["unit_hours", "setup_hours", "quantity"])
def test_graph_ready_v2_required_duration_fields_fail_loud(missing_field: str) -> None:
    op = SimpleNamespace(id=1, batch_id="B1", setup_hours=2.0, unit_hours=3.0)
    batch = SimpleNamespace(batch_id="B1", due_date="2026-01-01", quantity=1)
    if missing_field == "quantity":
        delattr(batch, missing_field)
    else:
        delattr(op, missing_field)

    with pytest.raises(ValidationError, match=missing_field):
        enrich_graph_ready_v2_metrics(
            {1: _graph_v2_metric()},
            operations=[op],
            batches={"B1": batch},
            start_dt=_START,
        )


@pytest.mark.parametrize("nonfinite", [float("inf"), float("-inf"), float("nan")])
@pytest.mark.parametrize("field_name", ["setup_hours", "unit_hours", "quantity"])
def test_graph_ready_v2_nonfinite_duration_fields_fail_loud(field_name: str, nonfinite: float) -> None:
    op = SimpleNamespace(id=1, batch_id="B1", setup_hours=2.0, unit_hours=3.0)
    batch = SimpleNamespace(batch_id="B1", due_date="2026-01-01", quantity=1)
    if field_name == "quantity":
        batch.quantity = nonfinite
    else:
        setattr(op, field_name, nonfinite)

    with pytest.raises(ValidationError, match=field_name):
        enrich_graph_ready_v2_metrics(
            {1: _graph_v2_metric()},
            operations=[op],
            batches={"B1": batch},
            start_dt=_START,
        )


def test_graph_ready_production_candidate_construction_uses_v2_without_profile_override() -> None:
    scheduler = SimpleNamespace(_last_algo_stats={})
    operations = [
        SimpleNamespace(id=1, batch_id="B1", source="internal", machine_id="MC-1", operator_id="OP-1", setup_hours=2.0, unit_hours=0.0),
        SimpleNamespace(id=2, batch_id="B2", source="internal", machine_id="MC-1", operator_id="OP-1", setup_hours=1.0, unit_hours=0.0),
    ]
    batches = {
        "B1": SimpleNamespace(batch_id="B1", priority="normal", due_date="2026-01-10", ready_status="yes", quantity=1),
        "B2": SimpleNamespace(batch_id="B2", priority="normal", due_date="2026-01-10", ready_status="yes", quantity=1),
    }
    baseline = _candidate([_result(1, "B1", 2), _result(2, "B2", 3)], failed_ops=1)
    state = _state()
    state.mark_candidate_accepted(baseline, origin="baseline")
    candidate_profile = build_candidate_profile(
        algo_mode="improve",
        dispatch_mode="sgs",
        dispatch_rule="slack",
        time_budget_seconds=5,
        version=7,
        strict_mode=True,
        ortools_enabled=False,
        graph_sgs_required=True,
    )
    attempts: List[Dict[str, Any]] = []

    best = run_graph_ready_candidates(
        algo_mode="improve",
        best=baseline,
        version=7,
        scheduler=scheduler,
        algo_ops_to_schedule=operations,
        batches=batches,
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
        attempts=attempts,
        improvement_trace=[],
        optimizer_algo_stats={},
        t_begin=1000.0,
        readiness_gate_enabled=False,
        strict_mode=True,
        graph_ready_context=_context(),
        clock=_Clock(),
        schedule_fn=_same_schedule,
        search_report_state=state,
        candidate_construction=candidate_profile.candidate_construction,
    )

    graph_profile = state.candidate_profile["graph_ready_optimization"]
    assert best is not None
    assert graph_profile["candidate_policy"] == "objective_aware_portfolio"
    assert graph_profile["effective_candidate_profile_count"] >= 10
    assert any(attempt["candidate_origin"] == GRAPH_READY_V2_GENERATED_ORIGIN for attempt in attempts)
    assert any(str(attempt["weight_profile_slug"]).startswith("v2_") for attempt in attempts)


def test_graph_ready_v2_feature_error_fails_loud_even_when_not_strict() -> None:
    scheduler = SimpleNamespace(_last_algo_stats={})
    operations = [
        SimpleNamespace(id=1, batch_id="B1", source="internal", machine_id="MC-1", operator_id="OP-1", setup_hours=float("inf"), unit_hours=0.0),
        SimpleNamespace(id=2, batch_id="B2", source="internal", machine_id="MC-1", operator_id="OP-1", setup_hours=1.0, unit_hours=0.0),
    ]
    batches = {
        "B1": SimpleNamespace(batch_id="B1", priority="normal", due_date="2026-01-10", ready_status="yes", quantity=1),
        "B2": SimpleNamespace(batch_id="B2", priority="normal", due_date="2026-01-10", ready_status="yes", quantity=1),
    }
    baseline = _candidate([_result(1, "B1", 2), _result(2, "B2", 3)], failed_ops=1)
    state = _state()
    state.mark_candidate_accepted(baseline, origin="baseline")
    candidate_profile = build_candidate_profile(
        algo_mode="improve",
        dispatch_mode="sgs",
        dispatch_rule="slack",
        time_budget_seconds=5,
        version=7,
        strict_mode=False,
        ortools_enabled=False,
        graph_sgs_required=True,
    )

    with pytest.raises(ValidationError, match="必须是有限数字"):
        run_graph_ready_candidates(
            algo_mode="improve",
            best=baseline,
            version=7,
            scheduler=scheduler,
            algo_ops_to_schedule=operations,
            batches=batches,
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
            strict_mode=False,
            graph_ready_context=_context(),
            clock=_Clock(),
            schedule_fn=_same_schedule,
            search_report_state=state,
            candidate_construction=candidate_profile.candidate_construction,
        )


def test_graph_ready_v2_bad_formula_fails_loud_even_when_not_strict_with_profile_override() -> None:
    baseline = _candidate([_result(1, "B1", 2), _result(2, "B2", 3)], failed_ops=1)
    state = _state()
    state.mark_candidate_accepted(baseline, origin="baseline")
    attempts: List[Dict[str, Any]] = []

    with pytest.raises(ValidationError) as exc_info:
        _run_graph_ready_v2_for_test(
            baseline=baseline,
            state=state,
            strict_mode=False,
            profiles_override=[_v2_profile("unknown_formula")],
            attempts=attempts,
        )

    assert exc_info.value.field == "graph_ready_v2_formula"
    assert exc_info.value.details["reason"] == "graph_ready_bad_v2_formula"
    assert attempts == []


def test_graph_ready_v2_bad_formula_strict_fails_loud() -> None:
    baseline = _candidate([_result(1, "B1", 2), _result(2, "B2", 3)], failed_ops=1)
    state = _state()
    state.mark_candidate_accepted(baseline, origin="baseline")

    with pytest.raises(ValidationError) as exc_info:
        _run_graph_ready_v2_for_test(
            baseline=baseline,
            state=state,
            strict_mode=True,
            profiles_override=[_v2_profile("unknown_formula")],
            attempts=[],
        )

    assert exc_info.value.field == "graph_ready_v2_formula"
    assert exc_info.value.details["reason"] == "graph_ready_bad_v2_formula"


def test_graph_ready_v2_missing_due_date_keeps_v2_production_candidates_even_in_strict_mode() -> None:
    scheduler = SimpleNamespace(_last_algo_stats={})
    operations = [
        SimpleNamespace(id=1, batch_id="B1", source="internal", machine_id="MC-1", operator_id="OP-1", setup_hours=1.0, unit_hours=0.0),
        SimpleNamespace(id=2, batch_id="B2", source="internal", machine_id="MC-1", operator_id="OP-1", setup_hours=1.0, unit_hours=0.0),
    ]
    batches = {
        "B1": SimpleNamespace(batch_id="B1", priority="normal", due_date=None, ready_status="yes", quantity=1),
        "B2": SimpleNamespace(batch_id="B2", priority="normal", due_date=None, ready_status="yes", quantity=1),
    }
    baseline = _candidate([_result(1, "B1", 2), _result(2, "B2", 3)], failed_ops=1)
    state = _state()
    state.mark_candidate_accepted(baseline, origin="baseline")
    candidate_profile = build_candidate_profile(
        algo_mode="improve",
        dispatch_mode="sgs",
        dispatch_rule="slack",
        time_budget_seconds=5,
        version=7,
        strict_mode=True,
        ortools_enabled=False,
        graph_sgs_required=True,
    )
    attempts: List[Dict[str, Any]] = []

    best = run_graph_ready_candidates(
        algo_mode="improve",
        best=baseline,
        version=7,
        scheduler=scheduler,
        algo_ops_to_schedule=operations,
        batches=batches,
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
        attempts=attempts,
        improvement_trace=[],
        optimizer_algo_stats={},
        t_begin=1000.0,
        readiness_gate_enabled=False,
        strict_mode=True,
        graph_ready_context=_context(),
        clock=_Clock(),
        schedule_fn=_same_schedule,
        search_report_state=state,
        candidate_construction=candidate_profile.candidate_construction,
    )

    graph_profile = state.candidate_profile["graph_ready_optimization"]
    assert best is not None
    assert "v2_status" not in graph_profile
    assert any(attempt["candidate_origin"] == GRAPH_READY_WEIGHT_GRID_ORIGIN for attempt in attempts)
    assert any(attempt["candidate_origin"] == GRAPH_READY_V2_GENERATED_ORIGIN for attempt in attempts)


def test_graph_ready_v2_bad_due_date_non_strict_fails_loud_in_production_candidate_chain() -> None:
    scheduler = SimpleNamespace(_last_algo_stats={})
    operations = [
        SimpleNamespace(id=1, batch_id="B1", source="internal", machine_id="MC-1", operator_id="OP-1", setup_hours=1.0, unit_hours=0.0),
        SimpleNamespace(id=2, batch_id="B2", source="internal", machine_id="MC-1", operator_id="OP-1", setup_hours=1.0, unit_hours=0.0),
    ]
    batches = {
        "B1": SimpleNamespace(batch_id="B1", priority="normal", due_date="bad-date", ready_status="yes", quantity=1),
        "B2": SimpleNamespace(batch_id="B2", priority="normal", due_date="2026-01-10", ready_status="yes", quantity=1),
    }
    baseline = _candidate([_result(1, "B1", 2), _result(2, "B2", 3)], failed_ops=1)
    state = _state()
    state.mark_candidate_accepted(baseline, origin="baseline")
    candidate_profile = build_candidate_profile(
        algo_mode="improve",
        dispatch_mode="sgs",
        dispatch_rule="slack",
        time_budget_seconds=5,
        version=7,
        strict_mode=False,
        ortools_enabled=False,
        graph_sgs_required=True,
    )
    attempts: List[Dict[str, Any]] = []

    with pytest.raises(ValidationError) as exc_info:
        run_graph_ready_candidates(
            algo_mode="improve",
            best=baseline,
            version=7,
            scheduler=scheduler,
            algo_ops_to_schedule=operations,
            batches=batches,
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
            attempts=attempts,
            improvement_trace=[],
            optimizer_algo_stats={},
            t_begin=1000.0,
            readiness_gate_enabled=False,
            strict_mode=False,
            graph_ready_context=_context(),
            clock=_Clock(),
            schedule_fn=_same_schedule,
            search_report_state=state,
            candidate_construction=candidate_profile.candidate_construction,
        )

    assert exc_info.value.field == "graph_ready_v2_features"
    assert exc_info.value.details["reason"] == "graph_ready_v2_bad_due_date"
    assert attempts == []


def test_graph_ready_v2_bad_sorting_metric_fails_loud_even_when_not_strict() -> None:
    scheduler = SimpleNamespace(_last_algo_stats={})
    operations = [
        SimpleNamespace(id=1, batch_id="B1", source="internal", machine_id="MC-1", operator_id="OP-1", setup_hours=1.0, unit_hours=0.0),
        SimpleNamespace(id=2, batch_id="B2", source="internal", machine_id="MC-1", operator_id="OP-1", setup_hours=1.0, unit_hours=0.0),
    ]
    batches = {
        "B1": SimpleNamespace(batch_id="B1", priority="normal", due_date="2026-01-10", ready_status="yes", quantity=1),
        "B2": SimpleNamespace(batch_id="B2", priority="normal", due_date="2026-01-10", ready_status="yes", quantity=1),
    }
    baseline = _candidate([_result(1, "B1", 2), _result(2, "B2", 3)], failed_ops=1)
    state = _state()
    state.mark_candidate_accepted(baseline, origin="baseline")
    candidate_profile = build_candidate_profile(
        algo_mode="improve",
        dispatch_mode="sgs",
        dispatch_rule="slack",
        time_budget_seconds=5,
        version=7,
        strict_mode=False,
        ortools_enabled=False,
        graph_sgs_required=True,
    )
    bad_context = _context()
    bad_context["node_metrics_by_op_id"][1]["downstream_critical_minutes"] = float("inf")

    with pytest.raises(ValidationError, match="必须是有限数字"):
        run_graph_ready_candidates(
            algo_mode="improve",
            best=baseline,
            version=7,
            scheduler=scheduler,
            algo_ops_to_schedule=operations,
            batches=batches,
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
            strict_mode=False,
            graph_ready_context=bad_context,
            clock=_Clock(),
            schedule_fn=_same_schedule,
            search_report_state=state,
            candidate_construction=candidate_profile.candidate_construction,
        )


def test_graph_ready_bad_candidate_policy_fails_loud_even_when_not_strict() -> None:
    scheduler = SimpleNamespace(_last_algo_stats={})
    operations = [
        SimpleNamespace(id=1, batch_id="B1", source="internal", machine_id="MC-1", operator_id="OP-1", setup_hours=1.0, unit_hours=0.0),
        SimpleNamespace(id=2, batch_id="B2", source="internal", machine_id="MC-1", operator_id="OP-1", setup_hours=1.0, unit_hours=0.0),
    ]
    batches = {
        "B1": SimpleNamespace(batch_id="B1", priority="normal", due_date="2026-01-10", ready_status="yes", quantity=1),
        "B2": SimpleNamespace(batch_id="B2", priority="normal", due_date="2026-01-10", ready_status="yes", quantity=1),
    }
    baseline = _candidate([_result(1, "B1", 2), _result(2, "B2", 3)], failed_ops=1)
    state = _state()
    state.mark_candidate_accepted(baseline, origin="baseline")
    candidate_profile = build_candidate_profile(
        algo_mode="improve",
        dispatch_mode="sgs",
        dispatch_rule="slack",
        time_budget_seconds=5,
        version=7,
        strict_mode=False,
        ortools_enabled=False,
        graph_sgs_required=True,
    )
    candidate_construction = dict(candidate_profile.candidate_construction)
    graph_ready_optimization = dict(candidate_construction["graph_ready_optimization"])
    graph_ready_optimization["candidate_policy"] = "unknown_policy"
    candidate_construction["graph_ready_optimization"] = graph_ready_optimization

    with pytest.raises(ValidationError) as exc_info:
        run_graph_ready_candidates(
            algo_mode="improve",
            best=baseline,
            version=7,
            scheduler=scheduler,
            algo_ops_to_schedule=operations,
            batches=batches,
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
            strict_mode=False,
            graph_ready_context=_context(),
            clock=_Clock(),
            schedule_fn=_same_schedule,
            search_report_state=state,
            candidate_construction=candidate_construction,
        )

    assert exc_info.value.field == "graph_ready_candidate_policy"
    assert exc_info.value.details["reason"] == "graph_ready_bad_candidate_policy"


def test_graph_ready_production_optimizer_path_passes_v2_candidate_construction() -> None:
    captured: Dict[str, Any] = {}
    clock = _Clock()

    def _capture_graph_ready(**kwargs: Any):
        captured.update(kwargs)
        return kwargs.get("best")

    runtime = OptimizerRuntime(
        scheduler_factory=lambda **kwargs: _OptimizerScheduler(kwargs["calendar_service"]),
        clock=clock,
        rng_factory=lambda _seed: None,
        run_ortools_warmstart=lambda **kwargs: kwargs.get("best"),
        run_multi_start=lambda **kwargs: kwargs.get("best"),
        run_graph_ready_candidates=_capture_graph_ready,
        run_grasp_ig_candidates=lambda **kwargs: kwargs.get("best"),
        run_local_search=lambda **kwargs: kwargs.get("best"),
    )

    optimize_schedule(
        calendar_service=_EightHourCalendar(),
        cfg_svc=_optimizer_cfg_svc(),
        cfg=_optimizer_cfg(),
        algo_ops_to_schedule=[],
        batches={},
        start_dt=_START,
        end_date=None,
        downtime_map={},
        seed_results=[],
        resource_pool=None,
        version=7,
        graph_ready_context=_context(),
        strict_mode=False,
        _runtime=runtime,
    )

    graph_profile = captured["candidate_construction"]["graph_ready_optimization"]
    assert captured["algo_mode"] == "improve"
    assert captured["graph_ready_context"]["enabled"] is True
    assert graph_profile["candidate_policy"] == "objective_aware_portfolio"
    assert graph_profile["effective_candidate_profile_count"] >= 10
    assert any(str(slug).startswith("v2_") for slug in graph_profile["weight_profile_slugs"])


def test_graph_ready_v2_priority_normalization_is_translation_invariant() -> None:
    profile = _v2_profile("edd")
    metrics = {
        1: _graph_v2_priority_metric(due_deadline_hours=24.0, slack_hours=12.0),
        2: _graph_v2_priority_metric(due_deadline_hours=48.0, slack_hours=36.0),
    }
    shifted = {
        op_id: dict(row, due_deadline_hours=row["due_deadline_hours"] + 1000.0, slack_hours=row["slack_hours"] + 1000.0)
        for op_id, row in metrics.items()
    }

    keys = context_for_profile(graph_ready_context={}, metrics_by_op_id=metrics, profile=profile)["graph_priority_key_by_op_id"]
    shifted_keys = context_for_profile(graph_ready_context={}, metrics_by_op_id=shifted, profile=profile)["graph_priority_key_by_op_id"]

    assert tuple(sorted(keys, key=lambda op_id: keys[op_id])) == (1, 2)
    assert tuple(sorted(shifted_keys, key=lambda op_id: shifted_keys[op_id])) == (1, 2)
    assert keys[1][0] == shifted_keys[1][0] == 0.0
    assert keys[2][0] == shifted_keys[2][0] == 1.0


def test_graph_ready_v2_saveability_formula_prioritizes_more_saveable_batch() -> None:
    profile = _v2_profile("saveability")
    metrics = {
        1: _graph_v2_priority_metric(saveability=0.9, remaining_work_hours=2.0),
        2: _graph_v2_priority_metric(saveability=0.2, remaining_work_hours=10.0),
    }

    keys = context_for_profile(graph_ready_context={}, metrics_by_op_id=metrics, profile=profile)["graph_priority_key_by_op_id"]

    assert tuple(sorted(keys, key=lambda op_id: keys[op_id])) == (1, 2)


def test_graph_ready_v2_formula_portfolio_keeps_distinct_ready_orders() -> None:
    metrics_by_op_id = graph_ready_v2_benchmark_context()["node_metrics_by_op_id"]
    profiles, truncated, reason = graph_ready_v2_profiles(max_candidate_profiles=60, seed=0)

    orders = {}
    for profile in profiles:
        if not str(profile.formula_version or "").startswith("graph_ready_v2"):
            continue
        keys = context_for_profile(
            graph_ready_context={},
            metrics_by_op_id=metrics_by_op_id,
            profile=profile,
        )["graph_priority_key_by_op_id"]
        orders[profile.formula_slug] = tuple(sorted(metrics_by_op_id, key=lambda op_id: keys[op_id]))

    assert truncated is False
    assert reason is None
    assert len(orders) == 10
    assert len(set(orders.values())) >= 6


def test_graph_ready_v2_rank01_cache_preserves_priority_keys_for_all_profiles() -> None:
    metrics_by_op_id = graph_ready_v2_benchmark_context()["node_metrics_by_op_id"]
    profiles, _truncated, _reason = graph_ready_v2_profiles(max_candidate_profiles=60, seed=3)
    rank_cache = build_v2_common_rank_cache(metrics_by_op_id)

    for profile in profiles:
        if not str(profile.formula_version or "").startswith("graph_ready_v2"):
            continue
        uncached = context_for_profile(
            graph_ready_context={},
            metrics_by_op_id=metrics_by_op_id,
            profile=profile,
        )["graph_priority_key_by_op_id"]
        cached = context_for_profile(
            graph_ready_context={},
            metrics_by_op_id=metrics_by_op_id,
            profile=profile,
            v2_common_rank_cache=rank_cache,
        )["graph_priority_key_by_op_id"]

        assert cached == uncached


@pytest.mark.parametrize(
    "formula_slug, metric_overrides, match",
    [
        ("unknown_formula", {}, "不支持候选公式"),
        ("edd", {"due_pressure": -1.0}, "必须是非负数"),
        ("edd", {"remaining_work_hours": 0.0}, "必须大于 0"),
    ],
)
def test_graph_ready_v2_bad_formula_or_bad_features_fail_loud(
    formula_slug: str,
    metric_overrides: Dict[str, Any],
    match: str,
) -> None:
    metrics = {1: _graph_v2_priority_metric(**metric_overrides)}

    with pytest.raises(ValidationError, match=match):
        context_for_profile(graph_ready_context={}, metrics_by_op_id=metrics, profile=_v2_profile(formula_slug))


def test_graph_ready_v2_missing_feature_fails_loud() -> None:
    metric = _graph_v2_priority_metric()
    metric.pop("due_pressure")

    with pytest.raises(ValidationError, match="due_pressure"):
        context_for_profile(graph_ready_context={}, metrics_by_op_id={1: metric}, profile=_v2_profile("edd"))


@pytest.mark.parametrize("missing_field", ["due_budget_hours", "remaining_due_burden_hours"])
def test_graph_ready_v2_budget_and_burden_features_are_required(missing_field: str) -> None:
    metric = _graph_v2_priority_metric()
    metric.pop(missing_field)

    with pytest.raises(ValidationError, match=missing_field):
        context_for_profile(graph_ready_context={}, metrics_by_op_id={1: metric}, profile=_v2_profile("spt"))


def test_graph_ready_v2_due_budget_and_remaining_burden_do_not_fallback_to_old_fields() -> None:
    budget_metrics = {
        1: _graph_v2_priority_metric(due_deadline_hours=100.0, due_budget_hours=5.0, processing_time_rank=0.0),
        2: _graph_v2_priority_metric(due_deadline_hours=1.0, due_budget_hours=50.0, processing_time_rank=0.0),
    }
    budget_keys = context_for_profile(
        graph_ready_context={},
        metrics_by_op_id=budget_metrics,
        profile=_v2_profile("spt"),
    )["graph_priority_key_by_op_id"]

    burden_metrics = {
        1: _graph_v2_priority_metric(remaining_work_hours=1.0, remaining_due_burden_hours=50.0),
        2: _graph_v2_priority_metric(remaining_work_hours=100.0, remaining_due_burden_hours=5.0),
    }
    burden_keys = context_for_profile(
        graph_ready_context={},
        metrics_by_op_id=burden_metrics,
        profile=_v2_profile("sacrifice_long"),
    )["graph_priority_key_by_op_id"]

    assert tuple(sorted(budget_keys, key=lambda op_id: budget_keys[op_id])) == (1, 2)
    assert tuple(sorted(burden_keys, key=lambda op_id: burden_keys[op_id])) == (2, 1)


def test_graph_ready_v2_profile_count_contract_is_nineteen_before_baseline() -> None:
    summary = graph_ready_v2_profile_summary(max_candidate_profiles=60)

    assert summary["configured_candidate_profile_count"] == 19
    assert summary["effective_candidate_profile_count"] == 19


def test_graph_ready_v2_profiles_include_named_candidate_families() -> None:
    profiles, truncated, reason = graph_ready_v2_profiles(max_candidate_profiles=60, seed=3)
    by_slug = {profile.slug: profile for profile in profiles}

    assert truncated is False
    assert reason is None
    assert by_slug["v2_edd"].formula_slug == "edd"
    assert by_slug["v2_spt"].formula_slug == "spt"
    assert by_slug["v2_min_slack"].formula_slug == "min_slack"
    assert by_slug["v2_critical_ratio"].formula_slug == "critical_ratio"
    assert by_slug["v2_atc_like"].formula_slug == "atc_like"
    assert by_slug["v2_saveability"].formula_slug == "saveability"
    assert by_slug["v2_sacrifice_long"].formula_slug == "sacrifice_long"
    assert by_slug["v2_graph_due_hybrid"].formula_slug == "graph_due_hybrid"
    assert by_slug["v2_bottleneck_due_gated"].formula_slug == "bottleneck_due_gated"
    assert by_slug["v2_seeded_micro_perturbation"].formula_slug == "micro_perturbation"


def test_graph_ready_v2_runs_real_sgs_and_keeps_repair_attribution_separate() -> None:
    v1 = run_graph_ready_real_sgs_case(seed=0)
    no_repair = run_graph_ready_v2_real_sgs_case(seed=0, with_repair=False)
    with_repair = run_graph_ready_v2_real_sgs_case(seed=0, with_repair=True)

    assert no_repair["status"] == "passed"
    assert with_repair["status"] == "passed"
    assert no_repair["algorithm_profile"] == "graph_ready_v2_no_repair"
    assert with_repair["algorithm_profile"] == "graph_ready_v2_with_repair"
    assert no_repair["best_origin"] == "graph_ready_v2_generated"
    assert no_repair["formula_versions"] == ["graph_ready_v1", "graph_ready_v2_objective_features_v2"]
    assert no_repair["comparison_to_graph_ready_v1"]["status"] == "improved"
    assert v1["oracle_status"] == "not_run"
    assert v1["gap_to_oracle_pct"] is None
    assert no_repair["oracle_status"] == "not_run"
    assert no_repair["gap_to_oracle_pct"] is None
    assert no_repair["accepted_distinct_candidates"] == len(no_repair["accepted_output_fingerprints"])
    assert with_repair["repair_scope"] == "benchmark_support_only_not_core"
    assert with_repair["accepted_distinct_candidates"] == len(with_repair["accepted_output_fingerprints"])
    assert "saveability" in no_repair["candidate_families"]
    assert with_repair["repair_evaluated_candidates"] > 0
    assert tuple(no_repair["objective_score"]) < tuple(v1["objective_score"])
    assert tuple(with_repair["objective_score"]) <= tuple(no_repair["objective_score"])


def test_graph_ready_v2_row_status_rejects_v1_origin_or_non_improvement() -> None:
    row = run_graph_ready_v2_real_sgs_case(seed=0, with_repair=False)

    v1_origin = dict(row)
    v1_origin["best_origin"] = "graph_ready_weight_grid"
    assert _v2_row_passes(v1_origin) is False

    not_better_than_v1 = dict(row)
    not_better_than_v1["comparison_to_graph_ready_v1"] = {"status": "same"}
    not_better_than_v1["v1_reference_objective_score"] = list(not_better_than_v1["objective_score"])
    assert _v2_row_passes(not_better_than_v1) is False


def test_graph_ready_v2_seeded_micro_perturbation_changes_candidate_order_without_worse_score() -> None:
    rows = [run_graph_ready_v2_real_sgs_case(seed=seed, with_repair=False) for seed in range(8)]
    orders = {tuple(row["best_order"]) for row in rows}
    v1_score = tuple(run_graph_ready_real_sgs_case(seed=0)["objective_score"])

    assert len(orders) > 1
    assert all(row["best_origin"] == "graph_ready_v2_generated" for row in rows)
    assert all(tuple(row["objective_score"]) < v1_score for row in rows)


def test_graph_ready_v2_micro_perturbation_keeps_due_pressure_ahead_of_jitter() -> None:
    # 门控合同:micro_perturbation 的 jitter 必须排在主交期目标(牺牲度、交期压力)之后,不得跨交期分数重排。
    profile = _v2_profile("micro_perturbation")
    metrics = {
        1: _graph_v2_priority_metric(sacrifice_penalty=0.0, due_pressure=0.9),
        2: _graph_v2_priority_metric(sacrifice_penalty=0.0, due_pressure=0.1),
    }
    keys = context_for_profile(graph_ready_context={}, metrics_by_op_id=metrics, profile=profile)["graph_priority_key_by_op_id"]

    # 两候选牺牲度相同(rank01 均 0.5),交期压力更高的 op1 应严格优先,且由第 2 位 -due_pressure_rank01 决定,而非 jitter。
    assert keys[1][0] == keys[2][0] == 0.5
    assert keys[1][1] == -1.0
    assert keys[2][1] == 0.0
    assert keys[1] < keys[2]


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
        strict_mode=False,
        graph_ready_context=_context(),
        clock=_Clock(),
        schedule_fn=_same_schedule,
        search_report_state=state,
    )

    assert best["candidate_origin"] == "graph_ready_base"
    assert state.rejection_summary["same_fingerprint"] >= 1


def test_graph_ready_strict_score_improvement_marks_report_improved() -> None:
    state = _state()
    baseline = _candidate([_result(1, "B1", 2), _result(2, "B2", 3)], failed_ops=1)
    state.mark_candidate_accepted(baseline, origin="baseline")
    attempts: List[Dict[str, Any]] = []

    best = _run_graph_ready_v2_for_test(
        baseline=baseline,
        state=state,
        strict_mode=False,
        profiles_override=[_v2_profile("edd")],
        attempts=attempts,
    )
    report = state.finalize(runtime_ms=50, attempts=attempts, improvement_trace=[])

    assert best["candidate_origin"] == GRAPH_READY_V2_GENERATED_ORIGIN
    assert report["improvement_conditions"]["score_strictly_better"] is True
    assert report["improvement_conditions"]["acceptance_passed"] is True
    assert report["improved"] is True
    assert report["acceptance_summary"]["improve_only"]["accepted"] == 1


def test_graph_ready_same_score_fingerprint_tiebreak_does_not_mark_report_improved() -> None:
    state = _state()
    baseline = _candidate([_result(1, "B1", 2), _result(2, "B2", 3)], failed_ops=0)
    state.mark_candidate_accepted(baseline, origin="baseline")
    attempts: List[Dict[str, Any]] = []

    best = _run_graph_ready_v2_for_test(
        baseline=baseline,
        state=state,
        strict_mode=False,
        profiles_override=[_v2_profile("edd")],
        attempts=attempts,
    )
    report = state.finalize(runtime_ms=50, attempts=attempts, improvement_trace=[])

    assert best["candidate_origin"] == GRAPH_READY_V2_GENERATED_ORIGIN
    assert report["best_fingerprint_changed"] is True
    assert report["improvement_conditions"]["score_strictly_better"] is False
    assert report["improvement_conditions"]["acceptance_passed"] is False
    assert report["improved"] is False
    assert report["acceptance_summary"] == {}


def test_graph_ready_same_fingerprint_does_not_add_acceptance_event() -> None:
    state = _state()
    baseline = _candidate([_result(1, "B1", 0), _result(2, "B2", 1)], failed_ops=0)
    state.mark_candidate_accepted(baseline, origin="baseline")
    attempts: List[Dict[str, Any]] = []

    best = _run_graph_ready_v2_for_test(
        baseline=baseline,
        state=state,
        strict_mode=False,
        profiles_override=[_v2_profile("edd")],
        attempts=attempts,
    )
    report = state.finalize(runtime_ms=50, attempts=attempts, improvement_trace=[])

    assert best is baseline
    assert state.rejection_summary["same_fingerprint"] == 1
    assert report["acceptance_events"] == []
    assert report["acceptance_summary"] == {}
    assert report["improved"] is False


def test_graph_ready_acceptance_event_stays_out_of_public_projection() -> None:
    state = _state()
    baseline = _candidate([_result(1, "B1", 2), _result(2, "B2", 3)], failed_ops=1)
    state.mark_candidate_accepted(baseline, origin="baseline")
    attempts: List[Dict[str, Any]] = []
    _run_graph_ready_v2_for_test(
        baseline=baseline,
        state=state,
        strict_mode=False,
        profiles_override=[_v2_profile("edd")],
        attempts=attempts,
    )

    report = state.finalize(runtime_ms=50, attempts=attempts, improvement_trace=[])
    public, diagnostics = project_search_report(report)
    public_text = json.dumps(public, ensure_ascii=False, sort_keys=True)

    assert public["acceptance_summary"]["improve_only"]["accepted"] == 1
    assert "acceptance_events" not in public_text
    assert "deterministic_random_draw" not in public_text
    assert "decision_fingerprint" not in public_text
    assert "output_fingerprint" not in public_text
    assert diagnostics["acceptance_events"][0]["acceptance_name"] == "improve_only"


def test_graph_ready_candidate_payload_separates_decision_and_decoded_batch_order() -> None:
    def _reversed_result_schedule(*args: Any, **kwargs: Any):
        results = [_result(2, "B2", 0), _result(1, "B1", 1)]
        return results, _summary(results), kwargs["strategy"], dict(kwargs.get("strategy_params") or {})

    candidate = evaluate_graph_ready_candidate(
        profile=_v2_profile("edd"),
        graph_ready_context={},
        metrics_by_op_id={
            1: _graph_v2_priority_metric(due_deadline_hours=24.0),
            2: _graph_v2_priority_metric(due_deadline_hours=48.0),
        },
        scheduler=SimpleNamespace(_last_algo_stats={}),
        strict_mode=False,
        algo_ops_to_schedule=[_op(1, "B1"), _op(2, "B2")],
        batches=_batches(),
        strategy=SortStrategy.PRIORITY_FIRST,
        params={},
        start_dt=_START,
        end_date=None,
        downtime_map={},
        order=["B1", "B2"],
        seed_sr_list=[],
        dispatch_rule="slack",
        resource_pool=None,
        objective_name=_OBJECTIVE,
        optimizer_algo_stats={},
        schedule_fn=_reversed_result_schedule,
        readiness_gate_enabled=False,
        version=7,
        runtime_ms=0,
    )

    assert candidate["decision_batch_order"] == ["B1", "B2"]
    assert candidate["decoded_batch_order"] == ["B2", "B1"]
    assert candidate["order"] == ["B2", "B1"]


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


def test_graph_ready_v2_public_projection_keeps_diagnostic_profile_fields() -> None:
    report = {
        "schema_version": 1,
        "algorithm_profile": "graph_ready",
        "candidate_profile": {
            "profile": "graph_ready",
            "candidate_strategy_families": ["graph_ready_base", "graph_ready_weight_grid", "graph_ready_v2_no_repair"],
            "candidate_construction": {"graph_ready_optimization": graph_ready_v2_profile_summary(max_candidate_profiles=60)},
        },
    }
    public, diagnostics = project_search_report(report)
    graph_ready = diagnostics["profile_diagnostics"]["candidate_construction"]["graph_ready_optimization"]
    public_text = json.dumps(public, ensure_ascii=False, sort_keys=True)

    assert graph_ready["candidate_policy"] == "objective_aware_portfolio"
    assert graph_ready["max_candidate_profiles"] == 60
    assert graph_ready["effective_candidate_profile_count"] >= 10
    assert graph_ready["normalization_version"] == "rank_percentile_v1"
    assert graph_ready["formula_versions"] == ["graph_ready_v1", "graph_ready_v2_objective_features_v2"]
    assert "candidate_construction" not in public_text
