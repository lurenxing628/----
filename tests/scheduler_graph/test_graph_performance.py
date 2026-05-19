from __future__ import annotations

import json
import time
from pathlib import Path
from statistics import mean, median
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

from core.algorithms.greedy.dispatch.sgs_graph import (
    _collect_candidates,
    _mark_graph_operation_completed,
    _op_id,
    _prepare_graph_ready_state,
)
from core.services.scheduler.graph.exporter import graph_summary_to_dict
from core.services.scheduler.graph.input_adapter import build_operation_nodes_from_rows
from core.services.scheduler.graph.metrics import build_node_metrics, get_critical_path, get_topological_order
from core.services.scheduler.graph.precedence_builder import build_linear_edges_by_batch, build_precedence_graph
from core.services.scheduler.graph.types import GraphAnalysisSummary, OperationGraphEdge, OperationGraphNode
from core.services.scheduler.graph.validators import collect_graph_warnings, find_cycle_edges, is_dag
from core.services.scheduler.run.schedule_graph_report import _project_graph_analysis_payload

REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = REPO_ROOT / "evidence" / "scheduler_graph" / "performance_2000_nodes.txt"

NODE_COUNT = 2000
BATCH_COUNT = 100
OPS_PER_BATCH = 20
EDGE_COUNT = BATCH_COUNT * (OPS_PER_BATCH - 1)

BASIC_REPORT_AVG_LIMIT_MS = 2500
BASIC_REPORT_MAX_LIMIT_MS = 5000
FULL_REPORT_AVG_LIMIT_MS = 2500
FULL_REPORT_MAX_LIMIT_MS = 5000
GRAPH_DIAGNOSTICS_BYTES_LIMIT = 20000
GRAPH_PROJECTION_BYTES_LIMIT = 30000
LONG_CHAIN_NODE_COUNT = 5000
LONG_CHAIN_METRICS_MEDIAN_LIMIT_MS = 1500
READY_CHAIN_NODE_COUNT = 2000
READY_CHAIN_LOOP_LIMIT_MS = 1500


def _make_rows() -> Tuple[List[Any], Dict[str, Any], Dict[str, Any]]:
    batches: Dict[str, Any] = {}
    rows: List[Any] = []
    for batch_index in range(BATCH_COUNT):
        batch_id = f"B{batch_index + 1:03d}"
        batches[batch_id] = SimpleNamespace(
            batch_id=batch_id,
            part_no=f"P{batch_index + 1:03d}",
            quantity=1,
            due_date="2026-02-10",
            priority="normal",
        )
        for op_index in range(OPS_PER_BATCH):
            seq = (op_index + 1) * 10
            op_id = batch_index * OPS_PER_BATCH + op_index + 1
            rows.append(
                SimpleNamespace(
                    id=op_id,
                    op_code=f"OP-{batch_id}-{seq:03d}",
                    batch_id=batch_id,
                    seq=seq,
                    source="internal",
                    setup_hours=0.0,
                    unit_hours=1.0,
                    op_type_name="测试工序",
                    op_type_id="OT_A",
                    machine_id=None,
                    operator_id=None,
                    supplier_id=None,
                    ext_group_id=None,
                    ext_merge_mode="",
                    merge_context_degraded=False,
                )
            )
    resource_pool: Dict[str, Any] = {
        "machines_by_op_type": {},
        "operators_by_machine": {},
        "machines_by_operator": {},
    }
    return rows, batches, resource_pool


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _make_linear_graph(node_count: int) -> Any:
    nodes = [
        OperationGraphNode(
            node_id=f"op:{index}",
            batch_id="B001",
            op_code=f"B001_{index * 10:05d}",
            seq=index * 10,
            name="测试工序",
            duration_minutes=1,
        )
        for index in range(1, node_count + 1)
    ]
    edges = [
        OperationGraphEdge(
            from_node_id=f"op:{index}",
            to_node_id=f"op:{index + 1}",
            kind="precedence",
            lag_minutes=0,
            note="测试边",
        )
        for index in range(1, node_count)
    ]
    return build_precedence_graph(nodes, edges)


def _make_ready_chain_state(node_count: int) -> Tuple[Dict[str, Any], Dict[str, List[Any]], List[str], Dict[str, int]]:
    ops_by_batch = {
        f"B{index:05d}": [
            SimpleNamespace(
                id=index,
                batch_id=f"B{index:05d}",
                op_code=f"OP-{index:05d}",
                seq=10,
            )
        ]
        for index in range(1, node_count + 1)
    }
    predecessor_map = {1: set()}
    successor_map = {index: set() for index in range(1, node_count + 1)}
    for index in range(2, node_count + 1):
        predecessor_map[index] = {index - 1}
        successor_map[index - 1].add(index)
    graph_ready_context = {
        "enabled": True,
        "schedulable_op_ids": set(range(1, node_count + 1)),
        "fixed_op_ids": set(),
        "predecessor_op_ids_by_op_id": predecessor_map,
        "successor_op_ids_by_op_id": successor_map,
        "sort_key_by_op_id": {index: (index, 10, index) for index in range(1, node_count + 1)},
    }
    graph_state = _prepare_graph_ready_state(graph_ready_context, ops_by_batch=ops_by_batch)
    assert graph_state is not None
    batch_ids = list(ops_by_batch)
    next_idx = {batch_id: 0 for batch_id in batch_ids}
    return graph_state, ops_by_batch, batch_ids, next_idx


def _measure_basic_report_once() -> Dict[str, Any]:
    rows, batches, resource_pool = _make_rows()

    started = time.perf_counter()
    nodes = build_operation_nodes_from_rows(
        rows,
        batches=batches,
        resource_pool=resource_pool,
        frozen_op_ids=set(),
    )
    build_nodes_ms = _elapsed_ms(started)

    started = time.perf_counter()
    edges = build_linear_edges_by_batch(nodes)
    graph = build_precedence_graph(nodes, edges)
    build_graph_ms = _elapsed_ms(started)

    started = time.perf_counter()
    cycle_edges = find_cycle_edges(graph)
    dag_ok = is_dag(graph)
    warnings = collect_graph_warnings(graph)
    validate_dag_ms = _elapsed_ms(started)

    started = time.perf_counter()
    topological_order = get_topological_order(graph)
    critical_path, critical_path_minutes = get_critical_path(graph)
    critical_path_ms = _elapsed_ms(started)

    summary = GraphAnalysisSummary(
        node_count=graph.number_of_nodes(),
        edge_count=graph.number_of_edges(),
        is_dag=dag_ok,
        cycle_edges=cycle_edges,
        topological_order=topological_order,
        critical_path=critical_path,
        critical_path_minutes=critical_path_minutes,
        node_metrics={},
        warnings=warnings,
    )
    payload = graph_summary_to_dict(summary)
    public, diagnostics = _project_graph_analysis_payload(
        mode="report",
        payload=payload,
        elapsed_ms=build_nodes_ms + build_graph_ms + validate_dag_ms + critical_path_ms,
        scope={
            "input_scope": "all_algo_ops_with_frozen_markers",
            "total_algo_op_count": NODE_COUNT,
            "reschedulable_unfrozen_op_count": NODE_COUNT,
            "frozen_node_count": 0,
            "seed_result_count": 0,
        },
    )
    projection_json = json.dumps(
        {"algo": {"graph_analysis": public}, "diagnostics": {"graph_analysis": diagnostics}},
        ensure_ascii=False,
        sort_keys=True,
    )

    return {
        "node_count": int(summary.node_count),
        "edge_count": int(summary.edge_count),
        "is_dag": bool(summary.is_dag),
        "metrics_mode": "basic",
        "build_nodes_ms": int(build_nodes_ms),
        "build_graph_ms": int(build_graph_ms),
        "validate_dag_ms": int(validate_dag_ms),
        "critical_path_ms": int(critical_path_ms),
        "impact_metrics_ms": 0,
        "impact_metrics_status": "skipped_basic_report",
        "basic_report_total_ms": int(build_nodes_ms + build_graph_ms + validate_dag_ms + critical_path_ms),
        "critical_path_minutes": int(summary.critical_path_minutes),
        "critical_path_node_count": int(len(summary.critical_path)),
        "topological_order_count": int(len(summary.topological_order)),
        "node_metrics_count": int(len(summary.node_metrics)),
        "warnings_count": int(len(summary.warnings)),
        "diagnostics_bytes": int(len(json.dumps(diagnostics, ensure_ascii=False).encode("utf-8"))),
        "projection_bytes": int(len(projection_json.encode("utf-8"))),
    }


def _measure_full_report_once() -> Dict[str, Any]:
    rows, batches, resource_pool = _make_rows()

    started = time.perf_counter()
    nodes = build_operation_nodes_from_rows(
        rows,
        batches=batches,
        resource_pool=resource_pool,
        frozen_op_ids=set(),
    )
    build_nodes_ms = _elapsed_ms(started)

    started = time.perf_counter()
    edges = build_linear_edges_by_batch(nodes)
    graph = build_precedence_graph(nodes, edges)
    build_graph_ms = _elapsed_ms(started)

    started = time.perf_counter()
    cycle_edges = find_cycle_edges(graph)
    dag_ok = is_dag(graph)
    warnings = collect_graph_warnings(graph)
    validate_dag_ms = _elapsed_ms(started)

    started = time.perf_counter()
    topological_order = get_topological_order(graph)
    critical_path, critical_path_minutes = get_critical_path(graph)
    critical_path_ms = _elapsed_ms(started)

    started = time.perf_counter()
    node_metrics = build_node_metrics(
        graph,
        topological_order=topological_order,
        critical_path=critical_path,
    )
    impact_metrics_ms = _elapsed_ms(started)

    summary = GraphAnalysisSummary(
        node_count=graph.number_of_nodes(),
        edge_count=graph.number_of_edges(),
        is_dag=dag_ok,
        cycle_edges=cycle_edges,
        topological_order=topological_order,
        critical_path=critical_path,
        critical_path_minutes=critical_path_minutes,
        node_metrics=node_metrics,
        warnings=warnings,
    )
    payload = graph_summary_to_dict(summary)
    public, diagnostics = _project_graph_analysis_payload(
        mode="on",
        payload=payload,
        elapsed_ms=build_nodes_ms + build_graph_ms + validate_dag_ms + critical_path_ms + impact_metrics_ms,
        scope={
            "input_scope": "all_algo_ops_with_frozen_markers",
            "total_algo_op_count": NODE_COUNT,
            "reschedulable_unfrozen_op_count": NODE_COUNT,
            "frozen_node_count": 0,
            "seed_result_count": 0,
        },
        score_public={
            "score_enabled": True,
            "score_metric_status": "available",
            "score_disabled_reason": None,
            "score_weight_summary": {"critical_weight": 500, "impact_weight": 10},
        },
        score_diagnostics={
            "graph_score_sample": [],
            "graph_score_sample_count": NODE_COUNT,
            "graph_score_sample_truncated": True,
        },
    )
    projection_json = json.dumps(
        {"algo": {"graph_analysis": public}, "diagnostics": {"graph_analysis": diagnostics}},
        ensure_ascii=False,
        sort_keys=True,
    )

    return {
        "node_count": int(summary.node_count),
        "edge_count": int(summary.edge_count),
        "is_dag": bool(summary.is_dag),
        "metrics_mode": "full",
        "build_nodes_ms": int(build_nodes_ms),
        "build_graph_ms": int(build_graph_ms),
        "validate_dag_ms": int(validate_dag_ms),
        "critical_path_ms": int(critical_path_ms),
        "impact_metrics_ms": int(impact_metrics_ms),
        "impact_metrics_status": "available",
        "full_report_total_ms": int(build_nodes_ms + build_graph_ms + validate_dag_ms + critical_path_ms + impact_metrics_ms),
        "critical_path_minutes": int(summary.critical_path_minutes),
        "critical_path_node_count": int(len(summary.critical_path)),
        "topological_order_count": int(len(summary.topological_order)),
        "node_metrics_count": int(len(summary.node_metrics)),
        "warnings_count": int(len(summary.warnings)),
        "diagnostics_bytes": int(len(json.dumps(diagnostics, ensure_ascii=False).encode("utf-8"))),
        "projection_bytes": int(len(projection_json.encode("utf-8"))),
    }


def test_basic_report_handles_2000_nodes_with_bounded_diagnostics() -> None:
    runs = [_measure_basic_report_once() for _index in range(3)]
    totals = [int(item["basic_report_total_ms"]) for item in runs]
    latest = runs[-1]

    assert latest["node_count"] == NODE_COUNT
    assert latest["edge_count"] == EDGE_COUNT
    assert latest["is_dag"] is True
    assert latest["metrics_mode"] == "basic"
    assert latest["critical_path_node_count"] == OPS_PER_BATCH
    assert latest["topological_order_count"] == NODE_COUNT
    assert latest["node_metrics_count"] == 0
    assert latest["impact_metrics_status"] == "skipped_basic_report"
    assert latest["diagnostics_bytes"] < GRAPH_DIAGNOSTICS_BYTES_LIMIT
    assert latest["projection_bytes"] < GRAPH_PROJECTION_BYTES_LIMIT

    assert mean(totals) < BASIC_REPORT_AVG_LIMIT_MS
    assert max(totals) < BASIC_REPORT_MAX_LIMIT_MS


def test_full_metrics_handles_2000_nodes_for_on_score_path() -> None:
    runs = [_measure_full_report_once() for _index in range(3)]
    totals = [int(item["full_report_total_ms"]) for item in runs]
    latest = runs[-1]

    assert latest["node_count"] == NODE_COUNT
    assert latest["edge_count"] == EDGE_COUNT
    assert latest["is_dag"] is True
    assert latest["metrics_mode"] == "full"
    assert latest["critical_path_node_count"] == OPS_PER_BATCH
    assert latest["topological_order_count"] == NODE_COUNT
    assert latest["node_metrics_count"] == NODE_COUNT
    assert latest["impact_metrics_status"] == "available"
    assert latest["diagnostics_bytes"] < GRAPH_DIAGNOSTICS_BYTES_LIMIT
    assert latest["projection_bytes"] < GRAPH_PROJECTION_BYTES_LIMIT

    assert mean(totals) < FULL_REPORT_AVG_LIMIT_MS
    assert max(totals) < FULL_REPORT_MAX_LIMIT_MS


def test_build_node_metrics_handles_5000_node_single_chain_without_4s_regression() -> None:
    graph = _make_linear_graph(LONG_CHAIN_NODE_COUNT)
    build_node_metrics(graph)

    samples = []
    latest_metrics: Dict[str, Dict[str, Any]] = {}
    for _index in range(5):
        started = time.perf_counter()
        latest_metrics = build_node_metrics(graph)
        samples.append((time.perf_counter() - started) * 1000)

    assert len(latest_metrics) == LONG_CHAIN_NODE_COUNT
    assert latest_metrics["op:1"]["impact_count"] == LONG_CHAIN_NODE_COUNT - 1
    assert latest_metrics[f"op:{LONG_CHAIN_NODE_COUNT}"]["impact_count"] == 0
    assert latest_metrics["op:1"]["downstream_critical_minutes"] == LONG_CHAIN_NODE_COUNT
    assert median(samples) < LONG_CHAIN_METRICS_MEDIAN_LIMIT_MS, samples


def test_incremental_ready_queue_handles_2000_node_single_chain_without_full_scan_regression() -> None:
    graph_state, ops_by_batch, batch_ids, next_idx = _make_ready_chain_state(READY_CHAIN_NODE_COUNT)

    started = time.perf_counter()
    for expected_op_id in range(1, READY_CHAIN_NODE_COUNT + 1):
        candidates = _collect_candidates(
            graph_state=graph_state,
            batch_ids=batch_ids,
            ops_by_batch=ops_by_batch,
            next_idx=next_idx,
            blocked_batches=set(),
        )
        assert [_op_id(op) for _batch_id, op in candidates] == [expected_op_id]
        _mark_graph_operation_completed(graph_state, expected_op_id)
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert elapsed_ms < READY_CHAIN_LOOP_LIMIT_MS


def test_committed_2000_node_performance_evidence_matches_pr4_contract() -> None:
    text = EVIDENCE_PATH.read_text(encoding="utf-8")

    assert "metrics_mode: basic" in text
    assert "metrics_mode: full" in text
    assert "node_count: 2000" in text
    assert "edge_count: 1900" in text
    assert "impact_metrics_status: skipped_basic_report" in text
    assert "impact_metrics_status: available" in text
