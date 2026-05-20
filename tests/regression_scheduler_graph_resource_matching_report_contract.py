from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, Iterator, List, Tuple

import pytest

from core.services.scheduler.config.config_field_spec import default_snapshot_values
from core.services.scheduler.run.schedule_graph_report import prepare_schedule_graph_for_dispatch
from core.services.scheduler.run.schedule_optimizer import OptimizationOutcome
from core.services.scheduler.schedule_orchestrator import orchestrate_schedule_run


def _make_dt(hours: int) -> datetime:
    return datetime(2026, 1, 1, 8, 0, 0) + timedelta(hours=hours)


class _TxManager:
    @contextmanager
    def transaction(self) -> Iterator[None]:
        yield


class _HistoryRepo:
    def allocate_next_version(self) -> int:
        return 7


class _Svc:
    def __init__(self) -> None:
        self.logger = None
        self.tx_manager = _TxManager()
        self.history_repo = _HistoryRepo()


def _cfg(mode: str, *, graph_block_on_cycle: str = "no") -> SimpleNamespace:
    values = default_snapshot_values()
    values.update(
        {
            "graph_analysis_mode": mode,
            "graph_block_on_cycle": graph_block_on_cycle,
            "graph_critical_weight": 500,
            "graph_impact_weight": 10,
            "graph_downstream_weight": 1,
        }
    )
    return SimpleNamespace(**values)


def _op(op_id: int, batch_id: str, seq: int = 10, *, op_type_id: str = "cut") -> SimpleNamespace:
    return SimpleNamespace(
        id=op_id,
        op_code=f"OP-{batch_id}-{seq:03d}",
        batch_id=batch_id,
        seq=seq,
        source="internal",
        setup_hours=0.0,
        unit_hours=1.0,
        op_type_id=op_type_id,
        op_type_name="车削",
    )


def _schedule_input(mode: str) -> SimpleNamespace:
    ops = [_op(1, "B001"), _op(2, "B002"), _op(3, "B003")]
    return SimpleNamespace(
        cfg=_cfg(mode),
        cal_svc=SimpleNamespace(),
        cfg_svc=SimpleNamespace(),
        readiness_gate_enabled=True,
        algo_ops=ops,
        algo_ops_to_schedule=list(ops),
        batches={
            "B001": SimpleNamespace(batch_id="B001", quantity=1, due_date="2026-01-02", priority="normal"),
            "B002": SimpleNamespace(batch_id="B002", quantity=1, due_date="2026-01-02", priority="normal"),
            "B003": SimpleNamespace(batch_id="B003", quantity=1, due_date="2026-01-02", priority="normal"),
        },
        start_dt_norm=datetime(2026, 1, 1, 8, 0, 0),
        end_date_norm=None,
        downtime_map={},
        seed_results=[],
        resource_pool={
            "machines_by_op_type": {"cut": ["M1", "M2"]},
            "operators_by_machine": {"M1": ["O1"], "M2": ["O2"]},
            "machines_by_operator": {},
        },
        operations=[SimpleNamespace(id=getattr(op, "id"), batch_id=getattr(op, "batch_id")) for op in ops],
        reschedulable_operations=[SimpleNamespace(id=getattr(op, "id")) for op in ops],
        reschedulable_op_ids={1, 2, 3},
        normalized_batch_ids=["B001", "B002", "B003"],
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
        run_time_budget_seconds=None,
    )


def _optimizer_outcome() -> OptimizationOutcome:
    results = [
        SimpleNamespace(
            op_id=op_id,
            op_code=f"OP-B{op_id:03d}-010",
            batch_id=f"B{op_id:03d}",
            seq=10,
            machine_id="OLD-M",
            operator_id="OLD-O",
            start_time=_make_dt(index),
            end_time=_make_dt(index + 1),
            source="internal",
            op_type_name="车削",
        )
        for index, op_id in enumerate((1, 2, 3))
    ]
    return OptimizationOutcome(
        results=results,
        summary=SimpleNamespace(
            success=True,
            total_ops=3,
            scheduled_ops=3,
            failed_ops=0,
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        ),
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={"dispatch": "fifo"},
        metrics=None,
        best_score=(0.0,),
        best_order=["B001", "B002", "B003"],
        attempts=[{"score": [0.0], "selected_batch_ids": ["B001", "B002", "B003"]}],
        improvement_trace=[{"score": [0.0]}],
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=3,
        algo_stats={},
    )


def _summary_from_ctx(_svc: Any, *, ctx: Any) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any], str, int]:
    algo: Dict[str, Any] = {"ok": 1}
    result_summary_obj: Dict[str, Any] = {
        "algo": algo,
        "warnings": [],
        "errors": [],
        "resource_pool": {"status": "unchanged"},
    }
    if ctx.graph_analysis_public is not None:
        algo["graph_analysis"] = dict(ctx.graph_analysis_public)
    if ctx.graph_analysis_diagnostics is not None:
        result_summary_obj["diagnostics"] = {"graph_analysis": dict(ctx.graph_analysis_diagnostics)}
    return [], "success", result_summary_obj, json.dumps(result_summary_obj, ensure_ascii=False), 12


def _run_orchestrator(schedule_input: Any) -> Any:
    return orchestrate_schedule_run(
        _Svc(),
        schedule_input=schedule_input,
        simulate=True,
        strict_mode=True,
        optimize_schedule_fn=lambda **_kwargs: _optimizer_outcome(),
        build_result_summary_fn=_summary_from_ctx,
    )


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
        outcome.result_summary_obj["resource_pool"],
    )


def _iter_keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _iter_keys(child)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_keys(item)


def test_report_and_on_add_resource_matching_without_changing_schedule_payload() -> None:
    off_outcome = _run_orchestrator(_schedule_input("off"))
    report_outcome = _run_orchestrator(_schedule_input("report"))
    on_outcome = _run_orchestrator(_schedule_input("on"))

    assert _schedule_payload_signature(report_outcome) == _schedule_payload_signature(off_outcome)
    assert _schedule_payload_signature(on_outcome) == _schedule_payload_signature(off_outcome)

    for outcome in (report_outcome, on_outcome):
        graph_analysis = outcome.result_summary_obj["algo"]["graph_analysis"]
        resource_matching = graph_analysis["resource_matching"]
        diagnostics = outcome.result_summary_obj["diagnostics"]["graph_analysis"]["resource_matching"]

        assert resource_matching["status"] == "available"
        assert resource_matching["reason"] == "ok"
        assert resource_matching["ready_operation_count"] == 3
        assert resource_matching["operation_with_candidate_count"] == 3
        assert resource_matching["machine_count"] == 2
        assert resource_matching["edge_count"] == 6
        assert resource_matching["matched_operation_count"] == 2
        assert resource_matching["unmatched_operation_count"] == 1
        assert resource_matching["bottleneck_machine_count"] >= 1
        assert diagnostics["matches_count"] == 2
        assert diagnostics["unmatched_operation_count"] == 1
        assert diagnostics["matches_sample"]


def test_resource_matching_public_has_no_samples_and_diagnostics_has_no_raw_graph_data() -> None:
    preparation = prepare_schedule_graph_for_dispatch(_schedule_input("report"))  # type: ignore[arg-type]

    assert preparation.graph_analysis_public is not None
    public = preparation.graph_analysis_public["resource_matching"]
    diagnostics = preparation.graph_analysis_diagnostics["resource_matching"]  # type: ignore[index]

    assert {
        "unmatched_operation_sample",
        "unmatched_operation_ids_sample",
        "bottleneck_machine_sample",
        "bottleneck_machine_ids_sample",
        "matches_sample",
        "matches",
    }.isdisjoint(public)
    assert diagnostics["matches_sample"]
    assert diagnostics["unmatched_operation_ids_sample"]
    assert diagnostics["bottleneck_machine_ids_sample"]
    assert {
        "resource_pool",
        "raw",
        "Graph",
        "nodes",
        "edges",
        "candidate_machine_ids",
    }.isdisjoint(set(_iter_keys(diagnostics)))
    json.dumps({"public": public, "diagnostics": diagnostics}, ensure_ascii=False)


def test_cycle_block_no_skips_resource_matching_without_fake_available(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.services.scheduler.graph import analysis_service, exporter

    class FakeGraphService:
        def analyze_linear_batches(self, _nodes: Any, *, metrics_mode: str = "full") -> object:
            return object()

    cycle_payload = {
        "node_count": 2,
        "edge_count": 2,
        "is_dag": False,
        "cycle_edges": [
            {"from": "op:1", "to": "op:2", "kind": "precedence"},
            {"from": "op:2", "to": "op:1", "kind": "explicit"},
        ],
        "topological_order": [],
        "critical_path": [],
        "critical_path_minutes": 0,
        "node_metrics": {},
        "warnings": [],
    }

    monkeypatch.setattr(analysis_service, "ScheduleGraphAnalysisService", FakeGraphService)
    monkeypatch.setattr(exporter, "graph_summary_to_dict", lambda _summary: cycle_payload)

    preparation = prepare_schedule_graph_for_dispatch(_schedule_input("on"))  # type: ignore[arg-type]

    resource_matching = preparation.graph_analysis_public["resource_matching"]  # type: ignore[index]
    assert resource_matching["status"] == "skipped"
    assert resource_matching["reason"] == "graph_not_dag"
    assert resource_matching["matched_operation_count"] == 0
    assert preparation.graph_analysis_diagnostics["resource_matching"] == {}  # type: ignore[index]


def test_networkx_unavailable_uses_top_level_graph_analysis_status(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.services.scheduler.graph import analysis_service
    from core.services.scheduler.graph.nx_runtime import NetworkXUnavailable

    class FailingGraphService:
        def analyze_linear_batches(self, _nodes: Any, *, metrics_mode: str = "full") -> object:
            raise NetworkXUnavailable("缺少可选依赖 networkx==3.1")

    monkeypatch.setattr(analysis_service, "ScheduleGraphAnalysisService", FailingGraphService)

    preparation = prepare_schedule_graph_for_dispatch(_schedule_input("report"))  # type: ignore[arg-type]

    assert preparation.graph_analysis_public is not None
    assert preparation.graph_analysis_public["status"] == "unavailable"
    assert preparation.graph_analysis_public["reason"] == "networkx_unavailable"
    assert "resource_matching" not in preparation.graph_analysis_public
    assert preparation.graph_analysis_diagnostics is None
