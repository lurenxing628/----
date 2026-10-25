"""守护 orchestrate_schedule_run 的工序依赖图循环处置策略：report 模式遇环只报 warning 并继续排产、on+block_on_cycle=yes 在分配版本号前抛 ValidationError(field=schedule_graph_cycle)、on+block_on_cycle=no 关闭图增强回退普通 SGS、networkx 缺失/输入/构建等已知图错误按各自 reason 上报而非误判为循环、未知异常不得在排产前被吞掉。"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta
from functools import partial
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

import pytest

from core.algorithms import GreedyScheduler, ScheduleResult, ScheduleSummary, SortStrategy
from core.errors import ValidationError
from core.models.batch import Batch
from core.models.batch_operation import BatchOperation
from core.models.schedule_config_runtime import ScheduleConfigSnapshot
from core.services.common.build_outcome import BuildOutcome
from core.services.scheduler.run.optimizer.runtime import _default_runtime
from core.services.scheduler.run.schedule_candidate_runner import run_candidate_comparison
from core.services.scheduler.run.schedule_graph_report import prepare_schedule_graph_for_dispatch
from core.services.scheduler.run.schedule_input_contracts import ScheduleRunInput
from core.services.scheduler.run.schedule_orchestrator import orchestrate_schedule_run
from core.services.scheduler.run.schedule_shared_optimizer import optimize_shared_schedule


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


def _schedule_input(mode: str, *, block_on_cycle: str) -> ScheduleRunInput:
    algo_ops = [_algo_op()]
    operations = [BatchOperation(id=1, op_code="OP-B001-010", batch_id="B001", source="internal")]
    return ScheduleRunInput(
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
        batches={"B001": Batch(batch_id="B001", part_no="P001", quantity=1, due_date="2026-01-02")},
        start_dt_norm=datetime(2026, 1, 1, 8, 0, 0),
        end_date_norm=None,
        downtime_map={},
        seed_results=[],
        resource_pool={"machines_by_op_type": {}, "operators_by_machine": {}, "machines_by_operator": {}},
        operations=operations,
        schedule_output_allowed_op_ids={1},
        payload_validation_operations=operations,
        operation_sources=None,
        execution_snapshot_revision="rev-0",
        execution_snapshot_op_ids=[1],
        execution_snapshot_op_count=1,
        run_time_budget_seconds=None,
        normalized_batch_ids=["B001"],
        freeze_meta={"loaded": True},
        algo_input_outcome=BuildOutcome([]),
        downtime_meta={"load_ok": True},
        resource_pool_meta={"build_ok": True},
        algo_warnings=[],
        frozen_op_ids=set(),
        t0=0.0,
        optimizer_seed_version=6,
        prev_version=5,
        missing_internal_resource_op_ids=set(),
        execution_facts={}, execution_fixed_op_ids=set(), execution_completed_op_ids=set(), execution_seed_results=[],
    )


def _valid_result() -> ScheduleResult:
    return ScheduleResult(
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


def _optimizer_outcome() -> Tuple[List[ScheduleResult], ScheduleSummary, SortStrategy, Dict[str, Any]]:
    return (
        [_valid_result()],
        ScheduleSummary(
            success=True,
            total_ops=1,
            scheduled_ops=1,
            failed_ops=0,
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        ),
        SortStrategy.PRIORITY_FIRST,
        {"dispatch": "fifo"},
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


def _summary_from_ctx(*, ctx: Any, logger: Any = None) -> Dict[str, Any]:
    algo: Dict[str, Any] = {"ok": 1, "used_params": dict(ctx.used_params)}
    result_summary_obj: Dict[str, Any] = {"algo": algo, "warnings": [], "errors": []}
    if ctx.graph_analysis_public is not None:
        algo["graph_analysis"] = dict(ctx.graph_analysis_public)
    if ctx.graph_analysis_diagnostics is not None:
        result_summary_obj["diagnostics"] = {"graph_analysis": dict(ctx.graph_analysis_diagnostics)}
    return result_summary_obj


def _run_orchestrator(schedule_input: Any, svc: _Svc) -> Any:
    return _run_orchestrator_with_decoder(schedule_input, svc, decode_fn=lambda **_kwargs: _optimizer_outcome())


def _run_orchestrator_with_decoder(schedule_input: Any, svc: _Svc, *, decode_fn: Any) -> Any:
    preparation = None

    def prepare_graph(inputs):
        nonlocal preparation
        preparation = prepare_schedule_graph_for_dispatch(inputs)
        return preparation

    class ContractScheduler(GreedyScheduler):
        def schedule(self, **kwargs):
            assert preparation is not None
            results, summary, used_strategy, used_params = decode_fn(
                **kwargs, graph_dispatch_mode_override=preparation.graph_dispatch_mode_override
            )
            params = dict(used_params, dispatch_mode=kwargs["dispatch_mode"], dispatch_rule=kwargs["dispatch_rule"])
            return results, summary, used_strategy, params

    compare = partial(run_candidate_comparison, prepare_graph_fn=prepare_graph,
        optimize_shared_schedule_fn=partial(optimize_shared_schedule,
            _runtime=replace(_default_runtime(), scheduler_factory=ContractScheduler)))
    return orchestrate_schedule_run(
        schedule_input=schedule_input,
        version=7,
        logger=svc.logger,
        strict_mode=True,
        candidate_comparison_fn=compare,
        build_result_summary_fn=_summary_from_ctx,
    )


@pytest.fixture()
def cycle_graph(monkeypatch: Any) -> None:
    from core.services.scheduler.graph import analysis_service, exporter

    class FakeGraphService:
        def analyze_precedence(self, _nodes: Any, _edges: Any, *, metrics_mode: str = "full") -> object:
            return object()

    monkeypatch.setattr(analysis_service, "ScheduleGraphAnalysisService", FakeGraphService)
    monkeypatch.setattr(exporter, "graph_summary_to_dict", lambda _summary: _cycle_graph_payload())


def test_report_mode_cycle_only_reports_warning_and_keeps_scheduling(cycle_graph: None) -> None:
    svc = _Svc()

    outcome = _run_orchestrator(_schedule_input("report", block_on_cycle="yes"), svc)

    graph_analysis = outcome.result_summary_obj["algo"]["graph_analysis"]
    assert graph_analysis["mode"] == "report"
    assert graph_analysis["effective_mode"] == "report"
    assert graph_analysis["status"] == "available"
    assert graph_analysis["is_dag"] is False
    assert graph_analysis["cycle_edge_count"] == 2
    assert outcome.candidate_comparison.selection.selected_plan.dispatch_mode == "batch_order"
    assert outcome.result_summary_obj["algo"]["used_params"]["dispatch_mode"] == "batch_order"
    assert svc.history_repo.allocate_calls == 0


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

    def _optimize(**kwargs: Any) -> Tuple[List[ScheduleResult], ScheduleSummary, SortStrategy, Dict[str, Any]]:
        captured.update(kwargs)
        return _optimizer_outcome()

    outcome = _run_orchestrator_with_decoder(_schedule_input("on", block_on_cycle="no"), svc, decode_fn=_optimize)

    graph_analysis = outcome.result_summary_obj["algo"]["graph_analysis"]
    assert graph_analysis["effective_mode"] == "sgs_without_graph_ready_queue"
    assert graph_analysis["graph_enhancement_allowed"] is False
    assert graph_analysis["graph_enhancement_disabled_reason"] == "schedule_graph_cycle"
    assert graph_analysis["ready_queue_enabled"] is False
    assert "继续按普通排法处理" in graph_analysis["graph_enhancement_message"]
    assert captured["graph_ready_context"] is None
    assert captured["graph_dispatch_mode_override"] == "sgs"
    assert captured["dispatch_mode"] == "sgs"
    selected = outcome.candidate_comparison.selection.selected_plan
    assert selected.dispatch_mode == "sgs"
    assert "graph_ready_profile" not in selected.origin
    assert outcome.result_summary_obj["algo"]["used_params"]["dispatch_mode"] == "sgs"
    assert svc.history_repo.allocate_calls == 0


def test_on_mode_improve_with_zero_score_weights_skips_graph_feature_prep_and_keeps_scheduling() -> None:
    svc = _Svc()
    schedule_input = _schedule_input("on", block_on_cycle="yes")
    schedule_input.cfg = replace(
        schedule_input.cfg,
        algo_mode="improve",
        graph_critical_weight=0,
        graph_impact_weight=0,
    )

    outcome = _run_orchestrator(schedule_input, svc)

    graph_analysis = outcome.result_summary_obj["algo"]["graph_analysis"]
    assert graph_analysis["mode"] == "on"
    assert graph_analysis["effective_mode"] == "graph_ready_queue"
    assert graph_analysis["score_enabled"] is False
    assert graph_analysis["score_disabled_reason"] == "score_weights_zero"
    selected = outcome.candidate_comparison.selection.selected_plan
    assert "graph_ready_profile" not in selected.origin
    assert svc.history_repo.allocate_calls == 0


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
        def analyze_precedence(self, _nodes: Any, _edges: Any, *, metrics_mode: str = "full") -> object:
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
        def analyze_precedence(self, _nodes: Any, _edges: Any, *, metrics_mode: str = "full") -> object:
            raise RuntimeError("boom")

    monkeypatch.setattr(analysis_service, "ScheduleGraphAnalysisService", FailingGraphService)
    svc = _Svc()

    with pytest.raises(RuntimeError, match="boom"):
        _run_orchestrator(_schedule_input("on", block_on_cycle="yes"), svc)
    assert svc.history_repo.allocate_calls == 0


def _analysis_graph(durations: List[Tuple[str, int]], edges: List[Tuple[str, str, int]]) -> Any:
    from core.services.scheduler.graph.nx_runtime import import_networkx

    graph = import_networkx().DiGraph()
    for node_id, duration in durations:
        graph.add_node(node_id, batch_id="B", piece_id=None, seq=0, op_code=node_id, duration_minutes=duration)
    for parent, child, lag in edges:
        graph.add_edge(parent, child, lag_minutes=lag, kind="precedence")
    return graph


def _build_duration_weighted_graph(graph: Any) -> Any:
    from core.services.scheduler.graph.nx_runtime import import_networkx

    weighted = import_networkx().DiGraph()
    source_node_id = "__GRAPH_METRICS_SOURCE__"
    weighted.add_node(source_node_id)
    for node_id, data in graph.nodes(data=True):
        weighted.add_node(node_id, **data)
    for node_id in graph.nodes:
        if graph.in_degree(node_id) == 0:
            weighted.add_edge(source_node_id, node_id, weight=int(graph.nodes[node_id]["duration_minutes"]))
    for parent, child, data in graph.edges(data=True):
        weighted.add_edge(parent, child, weight=int(graph.nodes[child]["duration_minutes"]) + int(data["lag_minutes"]))
    return weighted


@pytest.mark.parametrize(
    ("durations", "edges", "expected"),
    [
        ([("b", 1), ("a", 1), ("c", 1)], [("a", "c", 0), ("b", "c", 0)], (["b", "c"], 2)),
        ([("z", 1), ("a", 1)], [], (["a"], 1)),
        ([("a", 0), ("b", 0)], [("a", "b", 0)], ([], 0)),
        ([("a", 3), ("b", 2), ("c", 4)], [("b", "c", 0), ("a", "c", 2)], (["a", "c"], 9)),
        ([("a", 5), ("b", 1), ("c", 10)], [("a", "b", -6), ("b", "c", 0)], (["a", "b", "c"], 10)),
        ([("a", 5), ("b", 1), ("c", 10)], [("a", "b", -7), ("b", "c", 0)], (["b", "c"], 10)),
    ],
)
def test_critical_path_keeps_original_networkx_order_and_zero_semantics(
    durations: List[Tuple[str, int]], edges: List[Tuple[str, str, int]], expected: Tuple[List[str], int],
) -> None:
    from core.services.scheduler.graph import metrics
    from core.services.scheduler.graph.nx_runtime import import_networkx

    graph = _analysis_graph(durations, edges)
    weighted = _build_duration_weighted_graph(graph)

    def _node_sort_key(node_id: str) -> Tuple[str, int, str, str]:
        if node_id == "__GRAPH_METRICS_SOURCE__":
            return "", -1, "", node_id
        data = weighted.nodes[node_id]
        return str(data["batch_id"]), int(data["seq"]), str(data["op_code"]), node_id

    nx = import_networkx()
    weighted_order = [
        node_id
        for group in nx.topological_generations(weighted)
        for node_id in sorted(group, key=_node_sort_key)
    ]
    raw_path = nx.dag_longest_path(weighted, weight="weight", topo_order=weighted_order)
    oracle = (
        [node_id for node_id in raw_path if node_id != "__GRAPH_METRICS_SOURCE__"],
        sum(weighted.edges[parent, child]["weight"] for parent, child in zip(raw_path, raw_path[1:])),
    )
    assert oracle == expected
    order = metrics.get_topological_order(graph)
    assert metrics.get_critical_path(graph, topological_order=order) == oracle
    assert metrics.get_critical_path(graph) == oracle


@pytest.mark.parametrize("metrics_mode", ["basic", "full"])
def test_graph_analysis_reuses_one_topology_without_success_path_cycle_scan(
    monkeypatch: Any, metrics_mode: str,
) -> None:
    from unittest.mock import Mock

    from core.services.scheduler.graph import analysis_service
    from core.services.scheduler.graph.nx_runtime import import_networkx

    graph = _analysis_graph([("a", 3), ("b", 4)], [("a", "b", 2)])
    nx = import_networkx()
    topology = Mock(wraps=nx.topological_generations)
    cycle = Mock(wraps=nx.find_cycle)
    monkeypatch.setattr(nx, "topological_generations", topology)
    monkeypatch.setattr(nx, "find_cycle", cycle)

    summary = analysis_service.ScheduleGraphAnalysisService()._analyze_graph(graph, metrics_mode=metrics_mode)
    assert summary.is_dag is True
    assert (summary.critical_path, summary.critical_path_minutes) == (["a", "b"], 9)
    assert bool(summary.node_metrics) is (metrics_mode == "full")
    assert topology.call_count == 1
    assert cycle.call_count == 0


def test_graph_analysis_keeps_cycle_evidence_after_topology_failure(monkeypatch: Any) -> None:
    from unittest.mock import Mock

    from core.services.scheduler.graph import analysis_service
    from core.services.scheduler.graph.nx_runtime import import_networkx

    nx = import_networkx()
    topology = Mock(wraps=nx.topological_generations)
    cycle = Mock(wraps=nx.find_cycle)
    monkeypatch.setattr(nx, "topological_generations", topology)
    monkeypatch.setattr(nx, "find_cycle", cycle)
    graph = _analysis_graph([("a", 1), ("b", 1)], [("a", "b", 0), ("b", "a", 0)])

    summary = analysis_service.ScheduleGraphAnalysisService()._analyze_graph(graph, metrics_mode="full")
    assert summary.is_dag is False
    assert [(edge["from"], edge["to"]) for edge in summary.cycle_edges] == [("a", "b"), ("b", "a")]
    assert (summary.topological_order, summary.critical_path, summary.node_metrics) == ([], [], {})
    assert summary.warnings[-1].code == "GRAPH_HAS_CYCLE"
    assert summary.warnings[-1].data == {"cycle_edges": summary.cycle_edges}
    assert topology.call_count == cycle.call_count == 1


def test_standalone_node_metrics_prepares_topology_once_and_reuses_given_order(monkeypatch: Any) -> None:
    from unittest.mock import Mock

    from core.services.scheduler.graph import metrics
    from core.services.scheduler.graph.nx_runtime import import_networkx

    graph = _analysis_graph([("a", 3), ("b", 4)], [("a", "b", 2)])
    nx = import_networkx()
    topology = Mock(wraps=nx.topological_generations)
    monkeypatch.setattr(nx, "topological_generations", topology)

    expected = metrics.build_node_metrics(graph)
    assert topology.call_count == 1
    topology.reset_mock()
    assert metrics.build_node_metrics(graph, topological_order=["a", "b"]) == expected
    assert topology.call_count == 0


def test_piece_sequences_chain_and_duplicate_check_stay_within_each_piece() -> None:
    """回归：同批不同分件各自从 seq=10 起排，线性边不跨分件串连，也不误报 DUPLICATE_SEQ；同一分件内真重复仍告警。"""
    from core.services.scheduler.graph.input_adapter import build_operation_nodes_from_rows
    from core.services.scheduler.graph.precedence_builder import build_linear_edges_by_batch, build_precedence_graph
    from core.services.scheduler.graph.validators import collect_graph_warnings

    def _row(op_id: int, piece_id: Any, seq: int) -> Dict[str, Any]:
        return {"id": op_id, "batch_id": "B001", "piece_id": piece_id, "op_code": f"OP{op_id}", "seq": seq,
                "source": "internal", "setup_hours": 0, "unit_hours": 1}

    rows = [_row(1, "P1", 10), _row(2, "P2", 10), _row(3, "P1", 20), _row(4, "P2", 20), _row(5, "P2", 20)]
    nodes = build_operation_nodes_from_rows(rows, batches={"B001": {"quantity": 1}})
    assert [node.piece_id for node in nodes] == ["P1", "P2", "P1", "P2", "P2"]

    edges = build_linear_edges_by_batch(nodes)
    op_id_by_node = {node.node_id: node.raw["id"] for node in nodes}
    assert sorted((op_id_by_node[edge.from_node_id], op_id_by_node[edge.to_node_id]) for edge in edges) == [
        (1, 3), (2, 4), (4, 5),
    ]

    graph = build_precedence_graph(nodes, edges)
    duplicates = [warning for warning in collect_graph_warnings(graph) if warning.code == "DUPLICATE_SEQ"]
    assert [(warning.data["batch_id"], warning.data["seq"], warning.data["op_codes"]) for warning in duplicates] == [
        ("B001", 20, ["OP4", "OP5"]),
    ]
