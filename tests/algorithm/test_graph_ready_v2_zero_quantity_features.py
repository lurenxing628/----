"""合同测试：GraphReadyV2 特征层不复辟 quantity>0 硬闸（audit 2026-07-20 A17）。

系统口径（schedule_input_runtime_support._ensure_internal_runtime_hours 护栏注释 +
core/algorithm_runtime/internal_slot.validate_internal_hours + 回归测试
test_ensure_internal_runtime_hours_allows_zero_quantity）：quantity==0 合法，总量=setup；
总工时 0 合法。v2 特征层必须同口径：
- quantity==0 且 setup>0 的批次不再抛 ValidationError，duration 特征与正式运行口径一致；
- total==0 的真零工时工序按文档化 epsilon 计入 duration 特征并留痕（日志可见），
  保住 remaining_hours>0 的除零安全承重合同与下游 remaining_work_hours>0 合同；
- 外协分支 total<=0 的 fail-loud 有意保留（录入全链要求 ext_days>0，不对称是设计）。
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from core.algorithm_runtime.internal_slot import validate_internal_hours
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.sort_strategies import SortStrategy
from core.algorithms.types import ScheduleResult, ScheduleSummary
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.optimizer_candidate_profile import build_candidate_profile
from core.services.scheduler.run.optimizer_graph_ready import run_graph_ready_candidates
from core.services.scheduler.run.optimizer_graph_ready_candidates import context_for_profile
from core.services.scheduler.run.optimizer_graph_ready_profiles import (
    GRAPH_READY_V2_GENERATED_ORIGIN,
    GraphReadyWeightProfile,
)
from core.services.scheduler.run.optimizer_graph_ready_v2_features import (
    _ZERO_TOTAL_DURATION_EPSILON_HOURS,
    enrich_graph_ready_v2_metrics,
)
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState

_START = datetime(2026, 1, 1, 8, 0, 0)
_OBJECTIVE = "min_overdue"
_FEATURES_LOGGER = "core.services.scheduler.run.optimizer_graph_ready_v2_features"


class _Clock:
    def __init__(self) -> None:
        self._now = 1000.0

    def __call__(self) -> float:
        self._now += 0.01
        return self._now


def _graph_v2_metric(index: int = 0) -> Dict[str, Any]:
    return {
        "is_on_critical_path": False,
        "critical_path_rank": None,
        "impact_count": 0,
        "generation_index": int(index),
        "downstream_critical_minutes": 0,
        "bottleneck_machine_score": 1.0,
    }


def _internal_op(op_id: int, batch_id: str, *, setup_hours: float, unit_hours: float) -> SimpleNamespace:
    return SimpleNamespace(
        id=op_id,
        batch_id=batch_id,
        source="internal",
        machine_id="MC-1",
        operator_id="OP-1",
        setup_hours=setup_hours,
        unit_hours=unit_hours,
    )


def _batch(batch_id: str, *, quantity: float, due_date: Any = "2026-01-10") -> SimpleNamespace:
    return SimpleNamespace(
        batch_id=batch_id,
        priority="normal",
        due_date=due_date,
        ready_status="yes",
        quantity=quantity,
    )


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


@pytest.mark.parametrize("strict_mode", [False, True])
def test_zero_quantity_with_setup_passes_and_matches_runtime_hours(strict_mode: bool) -> None:
    """quantity==0 且 setup>0：不再抛，duration 特征与 validate_internal_hours 正式口径一致。"""
    op = _internal_op(1, "B1", setup_hours=2.0, unit_hours=5.0)
    batch = _batch("B1", quantity=0)

    enriched = enrich_graph_ready_v2_metrics(
        {1: _graph_v2_metric()},
        operations=[op],
        batches={"B1": batch},
        start_dt=_START,
        strict_mode=strict_mode,
    )
    row = enriched[1]

    runtime_total = validate_internal_hours(op, batch)
    assert runtime_total == 2.0
    assert row["remaining_work_hours"] == runtime_total
    assert row["remaining_due_burden_hours"] == runtime_total
    assert math.isfinite(row["critical_ratio"])
    assert row["critical_ratio"] == row["due_budget_hours"] / runtime_total


@pytest.mark.parametrize("strict_mode", [False, True])
def test_zero_total_operation_uses_epsilon_leaves_trace_and_keeps_division_safe(
    strict_mode: bool, caplog: pytest.LogCaptureFixture
) -> None:
    """total==0（setup=unit=0）：按文档化 epsilon 计入、日志留痕、_critical_ratio 无除零。"""
    op = _internal_op(1, "B1", setup_hours=0.0, unit_hours=0.0)
    batch = _batch("B1", quantity=0)

    with caplog.at_level(logging.WARNING, logger=_FEATURES_LOGGER):
        enriched = enrich_graph_ready_v2_metrics(
            {1: _graph_v2_metric()},
            operations=[op],
            batches={"B1": batch},
            start_dt=_START,
            strict_mode=strict_mode,
        )
    row = enriched[1]

    assert row["remaining_work_hours"] == _ZERO_TOTAL_DURATION_EPSILON_HOURS
    assert row["remaining_due_burden_hours"] == _ZERO_TOTAL_DURATION_EPSILON_HOURS
    assert math.isfinite(row["critical_ratio"]) and row["critical_ratio"] > 0.0
    assert row["saveability"] == 1.0
    assert row["sacrifice_penalty"] == 0.0
    # 留痕合同：降级可见，日志里必须能查到零工时工序被 epsilon 计入。
    assert "总工时为 0" in caplog.text
    assert "epsilon" in caplog.text

    # 下游公式层合同：remaining_work_hours 恒>0，epsilon 行必须能通过 v2 公式排序不被拒绝。
    keys = context_for_profile(
        graph_ready_context={},
        metrics_by_op_id=enriched,
        profile=_v2_profile("edd"),
    )["graph_priority_key_by_op_id"]
    assert set(keys) == {1}


def test_mixed_batch_zero_total_op_keeps_remaining_positive_and_near_real_total() -> None:
    """同批混排：零工时工序按 epsilon 计入，remaining 仍以真实工时为主导。"""
    operations = [
        _internal_op(1, "B1", setup_hours=0.0, unit_hours=0.0),
        _internal_op(2, "B1", setup_hours=2.0, unit_hours=0.0),
    ]
    batches = {"B1": _batch("B1", quantity=0)}

    enriched = enrich_graph_ready_v2_metrics(
        {1: _graph_v2_metric(0), 2: _graph_v2_metric(1)},
        operations=operations,
        batches=batches,
        start_dt=_START,
    )

    expected = 2.0 + _ZERO_TOTAL_DURATION_EPSILON_HOURS
    assert enriched[1]["remaining_work_hours"] == pytest.approx(expected)
    assert enriched[2]["remaining_work_hours"] == pytest.approx(expected)
    assert math.isfinite(enriched[1]["critical_ratio"])


def test_external_zero_days_still_fails_loud() -> None:
    """外协分支不对称有意保留：ext_days 录入全链要求 >0，total<=0 仍 fail-loud。"""
    op = SimpleNamespace(id=1, batch_id="B1", source="external", ext_days=0.0)
    batches = {"B1": _batch("B1", quantity=1)}

    with pytest.raises(ValidationError, match="必须大于 0") as exc_info:
        enrich_graph_ready_v2_metrics(
            {1: _graph_v2_metric()},
            operations=[op],
            batches=batches,
            start_dt=_START,
        )
    assert exc_info.value.field == "graph_ready_v2_features"


# ---- optimizer run 完整跑通（生产 v2 候选族链路） ----


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


def _candidate(results: List[ScheduleResult], batches: Dict[str, Any], *, failed_ops: int = 0) -> Dict[str, Any]:
    metrics = compute_metrics(results, batches)
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


def _graph_context() -> Dict[str, Any]:
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


def _same_schedule(*args: Any, **kwargs: Any):
    results = [_result(1, "B1", 0), _result(2, "B2", 1)]
    return results, _summary(results), kwargs["strategy"], dict(kwargs.get("strategy_params") or {})


@pytest.mark.parametrize("strict_mode", [False, True])
def test_optimizer_run_completes_with_zero_quantity_batch(strict_mode: bool) -> None:
    """A17 主场景：单个 quantity==0 批次不再打崩整个 optimizer run（生产 v2 候选族链路）。"""
    operations = [
        _internal_op(1, "B1", setup_hours=2.0, unit_hours=5.0),
        _internal_op(2, "B2", setup_hours=1.0, unit_hours=0.0),
    ]
    batches = {
        "B1": _batch("B1", quantity=0),
        "B2": _batch("B2", quantity=1),
    }
    baseline = _candidate([_result(1, "B1", 2), _result(2, "B2", 3)], batches, failed_ops=1)
    state = _state()
    state.mark_candidate_accepted(baseline, origin="baseline")
    candidate_profile = build_candidate_profile(
        algo_mode="improve",
        dispatch_mode="sgs",
        dispatch_rule="slack",
        time_budget_seconds=5,
        version=7,
        strict_mode=strict_mode,
        ortools_enabled=False,
        graph_sgs_required=True,
    )
    attempts: List[Dict[str, Any]] = []

    best = run_graph_ready_candidates(
        algo_mode="improve",
        best=baseline,
        version=7,
        scheduler=SimpleNamespace(_last_algo_stats={}),
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
        strict_mode=strict_mode,
        graph_ready_context=_graph_context(),
        clock=_Clock(),
        schedule_fn=_same_schedule,
        search_report_state=state,
        candidate_construction=candidate_profile.candidate_construction,
    )

    assert best is not None
    assert any(attempt["candidate_origin"] == GRAPH_READY_V2_GENERATED_ORIGIN for attempt in attempts)
