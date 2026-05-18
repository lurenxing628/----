from __future__ import annotations

import json
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

import pytest

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


def _algo_op() -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        op_code="OP-B001-010",
        batch_id="B001",
        seq=10,
        source="internal",
        setup_hours=0,
        unit_hours=1,
        op_type_name="车削",
    )


def _graph_node() -> Any:
    from core.services.scheduler.graph.types import OperationGraphNode

    return OperationGraphNode(
        node_id="op:B001:OP-B001-010:1",
        batch_id="B001",
        op_code="OP-B001-010",
        seq=10,
        name="车削",
        duration_minutes=60,
        source="internal",
        raw={"id": 1},
    )


def _schedule_input(mode: str) -> SimpleNamespace:
    algo_ops = [_algo_op()]
    algo_ops_to_schedule = list(algo_ops)
    batches = {"B001": SimpleNamespace(batch_id="B001", quantity=1, due_date="2026-01-02")}
    resource_pool = {"machines_by_op_type": {}, "operators_by_machine": {}, "machines_by_operator": {}}
    return SimpleNamespace(
        cfg=SimpleNamespace(
            graph_analysis_mode=mode,
            graph_block_on_cycle="no",
            graph_critical_weight=500,
            graph_impact_weight=10,
        ),
        cal_svc=SimpleNamespace(),
        cfg_svc=SimpleNamespace(),
        readiness_gate_enabled=True,
        algo_ops=algo_ops,
        algo_ops_to_schedule=algo_ops_to_schedule,
        batches=batches,
        start_dt_norm=datetime(2026, 1, 1, 8, 0, 0),
        end_date_norm=None,
        downtime_map={},
        seed_results=[],
        resource_pool=resource_pool,
        operations=[SimpleNamespace(id=1, batch_id="B001")],
        reschedulable_operations=[SimpleNamespace(id=1)],
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


def _graph_payload() -> Dict[str, Any]:
    return {
        "node_count": 1,
        "edge_count": 0,
        "is_dag": True,
        "cycle_edges": [],
        "topological_order": ["op:B001:OP-B001-010:1"],
        "critical_path": ["op:B001:OP-B001-010:1"],
        "critical_path_minutes": 60,
        "node_metrics": {
            "op:B001:OP-B001-010:1": {
                "is_on_critical_path": True,
                "critical_path_rank": 0,
                "impact_count": 0,
                "generation_index": 0,
                "downstream_critical_minutes": 60,
            }
        },
        "warnings": [],
    }


def _summary_from_ctx(_svc: Any, *, ctx: Any) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any], str, int]:
    algo: Dict[str, Any] = {"ok": 1}
    result_summary_obj: Dict[str, Any] = {"algo": algo, "warnings": [], "errors": []}
    if ctx.graph_analysis_public is not None:
        algo["graph_analysis"] = dict(ctx.graph_analysis_public)
    if ctx.graph_analysis_diagnostics is not None:
        result_summary_obj["diagnostics"] = {"graph_analysis": dict(ctx.graph_analysis_diagnostics)}
    return [], "success", result_summary_obj, json.dumps(result_summary_obj, ensure_ascii=False), 12


def _run_orchestrator_for_input(schedule_input: Any) -> Any:
    return orchestrate_schedule_run(
        _Svc(),
        schedule_input=schedule_input,
        simulate=True,
        strict_mode=True,
        optimize_schedule_fn=lambda **_kwargs: _optimizer_outcome(),
        build_result_summary_fn=_summary_from_ctx,
    )


def _run_orchestrator(mode: str) -> Any:
    return _run_orchestrator_for_input(_schedule_input(mode))


def _schedule_payload_signature(outcome: Any) -> Tuple[Any, ...]:
    rows = tuple(
        (
            row.op_id,
            row.machine_id,
            row.operator_id,
            row.start_time,
            row.end_time,
            row.source,
        )
        for row in outcome.validated_schedule_payload.schedule_rows
    )
    return (
        tuple((item.op_id, item.start_time, item.end_time, item.machine_id, item.operator_id) for item in outcome.results),
        tuple(outcome.best_order),
        tuple(json.dumps(item, sort_keys=True) for item in outcome.attempts),
        tuple(json.dumps(item, sort_keys=True) for item in outcome.improvement_trace),
        rows,
        tuple(sorted(outcome.validated_schedule_payload.scheduled_op_ids)),
        dict(outcome.validated_schedule_payload.assigned_by_op_id),
    )


def test_off_mode_does_not_import_graph_modules_or_write_graph_analysis() -> None:
    code = r'''
import json
import sys
from types import SimpleNamespace

for name in list(sys.modules):
    if name == "networkx" or name.startswith("core.services.scheduler.graph"):
        sys.modules.pop(name, None)

from core.services.scheduler.run.schedule_graph_report import maybe_analyze_schedule_graph

public, diagnostics = maybe_analyze_schedule_graph(
    SimpleNamespace(cfg=SimpleNamespace(graph_analysis_mode="off"))
)
print(json.dumps({
    "public": public,
    "diagnostics": diagnostics,
    "graph_loaded": any(name.startswith("core.services.scheduler.graph") for name in sys.modules),
    "networkx_loaded": "networkx" in sys.modules,
}, sort_keys=True))
'''
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout.splitlines()[-1])
    assert payload == {
        "public": None,
        "diagnostics": None,
        "graph_loaded": False,
        "networkx_loaded": False,
    }

    outcome = _run_orchestrator("off")
    assert "graph_analysis" not in outcome.result_summary_obj["algo"]


def test_report_and_on_modes_add_summary_without_changing_schedule_payload(monkeypatch: Any) -> None:
    from core.services.scheduler.graph import analysis_service, exporter, input_adapter

    captured: List[Dict[str, Any]] = []

    def fake_build_operation_nodes_from_rows(
        rows: Any,
        *,
        batches: Any,
        resource_pool: Any,
        frozen_op_ids: Any,
    ) -> List[Any]:
        captured.append({"rows": rows, "batches": batches, "resource_pool": resource_pool, "frozen_op_ids": frozen_op_ids})
        return [_graph_node()]

    class FakeGraphService:
        def analyze_linear_batches(self, nodes: Any, *, metrics_mode: str = "full") -> object:
            captured[-1]["nodes"] = nodes
            captured[-1]["metrics_mode"] = metrics_mode
            return object()

    monkeypatch.setattr(input_adapter, "build_operation_nodes_from_rows", fake_build_operation_nodes_from_rows)
    monkeypatch.setattr(analysis_service, "ScheduleGraphAnalysisService", FakeGraphService)
    monkeypatch.setattr(exporter, "graph_summary_to_dict", lambda _summary: _graph_payload())

    off_outcome = _run_orchestrator("off")
    report_input = _schedule_input("report")
    on_input = _schedule_input("on")
    report_outcome = _run_orchestrator_for_input(report_input)
    on_outcome = _run_orchestrator_for_input(on_input)

    assert _schedule_payload_signature(report_outcome) == _schedule_payload_signature(off_outcome)
    assert _schedule_payload_signature(on_outcome) == _schedule_payload_signature(off_outcome)
    assert report_outcome.result_summary_obj["algo"]["graph_analysis"]["effective_mode"] == "report"
    assert on_outcome.result_summary_obj["algo"]["graph_analysis"]["effective_mode"] == "graph_ready_queue"
    assert on_outcome.result_summary_obj["algo"]["graph_analysis"]["ready_queue_enabled"] is True
    assert captured[0]["rows"] is report_input.algo_ops
    assert captured[0]["batches"] is report_input.batches
    assert captured[0]["resource_pool"] is report_input.resource_pool
    assert captured[0]["frozen_op_ids"] is report_input.frozen_op_ids
    assert captured[1]["rows"] is on_input.algo_ops


def test_report_mode_uses_real_graph_path_and_marks_frozen_scope() -> None:
    schedule_input = _schedule_input("report")
    frozen_op = _algo_op()
    frozen_op.id = 2
    frozen_op.op_code = "OP-B001-005"
    frozen_op.seq = 5
    schedule_input.algo_ops = [frozen_op] + list(schedule_input.algo_ops)
    schedule_input.algo_ops_to_schedule = [schedule_input.algo_ops[1]]
    schedule_input.frozen_op_ids = {2, 999}
    schedule_input.seed_results = [{"op_id": 2}]

    outcome = _run_orchestrator_for_input(schedule_input)

    graph_analysis = outcome.result_summary_obj["algo"]["graph_analysis"]
    diagnostics = outcome.result_summary_obj["diagnostics"]["graph_analysis"]
    assert graph_analysis["status"] == "available"
    assert graph_analysis["input_scope"] == "all_algo_ops_with_frozen_markers"
    assert graph_analysis["total_algo_op_count"] == 2
    assert graph_analysis["reschedulable_unfrozen_op_count"] == 1
    assert graph_analysis["frozen_node_count"] == 1
    assert graph_analysis["seed_result_count"] == 1
    assert graph_analysis["node_count"] == 2
    assert diagnostics["node_metrics_sample"] == []
    assert diagnostics["node_metrics_count"] == 0
    assert diagnostics["node_metrics_status"] == "skipped_basic_report"


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
def test_known_graph_errors_are_visible_without_changing_schedule(
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

    off_outcome = _run_orchestrator("off")
    report_outcome = _run_orchestrator("report")

    graph_analysis = report_outcome.result_summary_obj["algo"]["graph_analysis"]
    assert graph_analysis["status"] == status
    assert graph_analysis["reason"] == reason
    assert graph_analysis["message"]
    assert "graph_analysis" not in report_outcome.result_summary_obj.get("diagnostics", {})
    assert not report_outcome.result_summary_obj.get("errors")
    assert _schedule_payload_signature(report_outcome) == _schedule_payload_signature(off_outcome)


def test_unknown_graph_error_is_not_swallowed(monkeypatch: Any) -> None:
    from core.services.scheduler.graph import analysis_service

    class FailingGraphService:
        def analyze_linear_batches(self, _nodes: Any, *, metrics_mode: str = "full") -> object:
            raise RuntimeError("boom")

    monkeypatch.setattr(analysis_service, "ScheduleGraphAnalysisService", FailingGraphService)

    with pytest.raises(RuntimeError, match="boom"):
        _run_orchestrator("report")
