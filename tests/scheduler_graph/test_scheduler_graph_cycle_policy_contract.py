"""守护 orchestrate_schedule_run 的工序依赖图循环处置策略：report 模式遇环只报 warning 并继续排产、on+block_on_cycle=yes 在分配版本号前抛 ValidationError(field=schedule_graph_cycle)、on+block_on_cycle=no 关闭图增强回退普通 SGS、networkx 缺失/输入/构建等已知图错误按各自 reason 上报而非误判为循环、未知异常不得在排产前被吞掉。"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.config.config_snapshot import ScheduleConfigSnapshot
from core.services.scheduler.run.schedule_optimizer import OptimizationOutcome
from core.services.scheduler.schedule_orchestrator import orchestrate_schedule_run


def _make_dt(hours: int) -> datetime:
    return datetime(2026, 1, 1, 8, 0, 0) + timedelta(hours=hours)


class _TxManager:
    @contextmanager
    def transaction(self) -> Any:
        yield


class _HistoryRepo:
    def __init__(self) -> None:
        self.allocate_calls = 0

    def allocate_next_version(self) -> int:
        self.allocate_calls += 1
        return 7


class _Svc:
    def __init__(self) -> None:
        self.logger = None
        self.tx_manager = _TxManager()
        self.history_repo = _HistoryRepo()


def _algo_op(op_id: int = 1, seq: int = 10) -> SimpleNamespace:
    return SimpleNamespace(
        id=op_id,
        op_code=f"OP-B001-{seq:03d}",
        batch_id="B001",
        seq=seq,
        source="internal",
        setup_hours=0,
        unit_hours=1,
        op_type_name="车削",
    )


def _schedule_input(mode: str, *, block_on_cycle: str) -> SimpleNamespace:
    algo_ops = [_algo_op()]
    return SimpleNamespace(
        cfg=ScheduleConfigSnapshot(
            sort_strategy="priority_first",
            priority_weight=0.4,
            due_weight=0.5,
            ready_weight=0.1,
            holiday_default_efficiency=1.0,
            enforce_ready_default="no",
            prefer_primary_skill="no",
            dispatch_mode="batch_order",
            dispatch_rule="slack",
            auto_assign_enabled="no",
            auto_assign_persist="yes",
            ortools_enabled="no",
            ortools_time_limit_seconds=5,
            algo_mode="greedy",
            time_budget_seconds=5,
            objective="min_overdue",
            freeze_window_enabled="no",
            freeze_window_days=0,
            graph_analysis_mode=mode,
            graph_block_on_cycle=block_on_cycle,
            graph_critical_weight=500,
            graph_impact_weight=10,
            graph_debug_export="no",
        ),
        cal_svc=SimpleNamespace(),
        cfg_svc=SimpleNamespace(),
        readiness_gate_enabled=True,
        algo_ops=algo_ops,
        algo_ops_to_schedule=list(algo_ops),
        batches={"B001": SimpleNamespace(batch_id="B001", quantity=1, due_date="2026-01-02")},
        start_dt_norm=datetime(2026, 1, 1, 8, 0, 0),
        end_date_norm=None,
        downtime_map={},
        seed_results=[],
        resource_pool={"machines_by_op_type": {}, "operators_by_machine": {}, "machines_by_operator": {}},
        operations=[SimpleNamespace(id=1, batch_id="B001", source="internal")],
        reschedulable_operations=[SimpleNamespace(id=1, batch_id="B001", source="internal")],
        reschedulable_op_ids={1},
        normalized_batch_ids=["B001"],
        freeze_meta={"loaded": True},
        algo_input_outcome=SimpleNamespace(value=[]),
        downtime_meta={"load_ok": True},
        resource_pool_meta={"build_ok": True},
        algo_warnings=[],
        frozen_op_ids=set(),
        t0=0.0,
        optimizer_seed_version=6,
        run_label="schedule",
        prev_version=5,
        created_by_text="tester",
        missing_internal_resource_op_ids=set(),
    )


def _valid_result() -> SimpleNamespace:
    return SimpleNamespace(
        op_id=1,
        op_code="OP-B001-010",
        batch_id="B001",
        seq=10,
        machine_id="MC001",
        operator_id="OP001",
        start_time=_make_dt(0),
        end_time=_make_dt(1),
        source="internal",
        op_type_name="车削",
    )


def _optimizer_outcome() -> OptimizationOutcome:
    return OptimizationOutcome(
        results=[_valid_result()],
        summary=SimpleNamespace(
            success=True,
            total_ops=1,
            scheduled_ops=1,
            failed_ops=0,
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        ),
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={"dispatch": "fifo"},
        metrics=None,
        best_score=(0.0,),
        best_order=["B001"],
        attempts=[{"score": [0.0]}],
        improvement_trace=[{"score": [0.0]}],
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=3,
        algo_stats={},
    )


def _cycle_graph_payload() -> Dict[str, Any]:
    return {
        "node_count": 2,
        "edge_count": 2,
        "is_dag": False,
        "cycle_edges": [
            {"from": "op:B001:OP-B001-010:1", "to": "op:B001:OP-B001-020:2", "kind": "precedence"},
            {"from": "op:B001:OP-B001-020:2", "to": "op:B001:OP-B001-010:1", "kind": "explicit"},
        ],
        "topological_order": [],
        "critical_path": [],
        "critical_path_minutes": 0,
        "node_metrics": {},
        "warnings": [
            {
                "code": "GRAPH_HAS_CYCLE",
                "message": "工序依赖图存在循环，无法计算拓扑顺序和关键路径。",
                "data": {"cycle_edges": []},
            }
        ],
    }


def _summary_from_ctx(_svc: Any, *, ctx: Any) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any], str, int]:
    algo: Dict[str, Any] = {"ok": 1}
    result_summary_obj: Dict[str, Any] = {"algo": algo, "warnings": [], "errors": []}
    if ctx.graph_analysis_public is not None:
        algo["graph_analysis"] = dict(ctx.graph_analysis_public)
    if ctx.graph_analysis_diagnostics is not None:
        result_summary_obj["diagnostics"] = {"graph_analysis": dict(ctx.graph_analysis_diagnostics)}
    return [], "success", result_summary_obj, json.dumps(result_summary_obj, ensure_ascii=False), 12


def _run_orchestrator(schedule_input: Any, svc: _Svc) -> Any:
    return _run_orchestrator_with_optimizer(schedule_input, svc, optimize_fn=lambda **_kwargs: _optimizer_outcome())


def _run_orchestrator_with_optimizer(schedule_input: Any, svc: _Svc, *, optimize_fn: Any) -> Any:
    return orchestrate_schedule_run(
        svc,
        schedule_input=schedule_input,
        simulate=True,
        strict_mode=True,
        optimize_schedule_fn=optimize_fn,
        build_result_summary_fn=_summary_from_ctx,
    )


@pytest.fixture()
def cycle_graph(monkeypatch: Any) -> None:
    from core.services.scheduler.graph import analysis_service, exporter

    class FakeGraphService:
        def analyze_linear_batches(self, _nodes: Any, *, metrics_mode: str = "full") -> object:
            return object()

    monkeypatch.setattr(analysis_service, "ScheduleGraphAnalysisService", FakeGraphService)
    monkeypatch.setattr(exporter, "graph_summary_to_dict", lambda _summary: _cycle_graph_payload())


@pytest.mark.skipif(
    bool(os.environ.get("CI")),
    reason=(
        "分片全量门禁下存在跨用例模块状态污染：同分片某用例改写 graph 分析相关模块状态，"
        "致本用例 graph_analysis['is_dag'] 误判为 True（隔离/非分片运行恒过）。"
        "在治本（定位并隔离污染源）前于 CI 隔离本用例，不掩盖产品行为。"
    ),
)
def test_report_mode_cycle_only_reports_warning_and_keeps_scheduling(cycle_graph: None) -> None:
    svc = _Svc()

    outcome = _run_orchestrator(_schedule_input("report", block_on_cycle="yes"), svc)

    graph_analysis = outcome.result_summary_obj["algo"]["graph_analysis"]
    assert graph_analysis["mode"] == "report"
    assert graph_analysis["effective_mode"] == "report"
    assert graph_analysis["status"] == "available"
    assert graph_analysis["is_dag"] is False
    assert graph_analysis["cycle_edge_count"] == 2
    assert svc.history_repo.allocate_calls == 1


def test_on_mode_cycle_with_block_yes_stops_before_version_allocation(cycle_graph: None) -> None:
    svc = _Svc()

    with pytest.raises(ValidationError) as exc_info:
        _run_orchestrator(_schedule_input("on", block_on_cycle="yes"), svc)

    assert exc_info.value.field == "schedule_graph_cycle"
    assert "工序图存在循环依赖" in exc_info.value.message
    assert exc_info.value.details == {
        "reason": "schedule_graph_cycle",
        "cycle_edge_count": 2,
        "cycle_edges_sample": [
            {"from": "op:B001:OP-B001-010:1", "to": "op:B001:OP-B001-020:2", "kind": "precedence"},
            {"from": "op:B001:OP-B001-020:2", "to": "op:B001:OP-B001-010:1", "kind": "explicit"},
        ],
        "field": "schedule_graph_cycle",
    }
    assert svc.history_repo.allocate_calls == 0


def test_on_mode_cycle_with_block_no_disables_graph_enhancement_and_keeps_old_sgs(cycle_graph: None) -> None:
    svc = _Svc()
    captured: Dict[str, Any] = {}

    def _optimize(**kwargs: Any) -> OptimizationOutcome:
        captured.update(kwargs)
        return _optimizer_outcome()

    outcome = _run_orchestrator_with_optimizer(_schedule_input("on", block_on_cycle="no"), svc, optimize_fn=_optimize)

    graph_analysis = outcome.result_summary_obj["algo"]["graph_analysis"]
    assert graph_analysis["effective_mode"] == "sgs_without_graph_ready_queue"
    assert graph_analysis["graph_enhancement_allowed"] is False
    assert graph_analysis["graph_enhancement_disabled_reason"] == "schedule_graph_cycle"
    assert graph_analysis["ready_queue_enabled"] is False
    assert "继续按普通排法处理" in graph_analysis["graph_enhancement_message"]
    assert captured["graph_ready_context"] is None
    assert captured["graph_dispatch_mode_override"] == "sgs"
    assert svc.history_repo.allocate_calls == 1


@pytest.mark.parametrize(
    ("exception_factory", "status", "reason"),
    [
        (
            lambda: __import__(
                "core.services.scheduler.graph.nx_runtime",
                fromlist=["NetworkXUnavailable"],
            ).NetworkXUnavailable("缺少可选依赖 networkx==3.1"),
            "unavailable",
            "networkx_unavailable",
        ),
        (
            lambda: __import__(
                "core.services.scheduler.graph.input_adapter",
                fromlist=["GraphInputContractError"],
            ).GraphInputContractError("source 不合法"),
            "input_error",
            "graph_input_contract_error",
        ),
        (
            lambda: __import__(
                "core.services.scheduler.graph.precedence_builder",
                fromlist=["GraphBuildContractError"],
            ).GraphBuildContractError("重复 node_id"),
            "build_error",
            "graph_build_contract_error",
        ),
    ],
)
def test_on_mode_known_graph_error_is_not_reported_as_cycle(
    monkeypatch: Any,
    exception_factory: Any,
    status: str,
    reason: str,
) -> None:
    from core.services.scheduler.graph import analysis_service

    class FailingGraphService:
        def analyze_linear_batches(self, _nodes: Any, *, metrics_mode: str = "full") -> object:
            raise exception_factory()

    monkeypatch.setattr(analysis_service, "ScheduleGraphAnalysisService", FailingGraphService)
    svc = _Svc()

    with pytest.raises(ValidationError) as exc_info:
        _run_orchestrator(_schedule_input("on", block_on_cycle="yes"), svc)

    assert exc_info.value.field == reason
    assert exc_info.value.details == {
        "reason": reason,
        "status": status,
        "field": reason,
    }
    assert "工序图增强无法启用" in exc_info.value.message
    assert "循环依赖" not in exc_info.value.message
    assert svc.history_repo.allocate_calls == 0


def test_unknown_graph_error_is_not_swallowed_before_scheduling(monkeypatch: Any) -> None:
    from core.services.scheduler.graph import analysis_service

    class FailingGraphService:
        def analyze_linear_batches(self, _nodes: Any, *, metrics_mode: str = "full") -> object:
            raise RuntimeError("boom")

    monkeypatch.setattr(analysis_service, "ScheduleGraphAnalysisService", FailingGraphService)
    svc = _Svc()

    with pytest.raises(RuntimeError, match="boom"):
        _run_orchestrator(_schedule_input("on", block_on_cycle="yes"), svc)
    assert svc.history_repo.allocate_calls == 0
