from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, Iterator, List, Optional

from core.services.scheduler.run.schedule_persistence import build_validated_schedule_payload, persist_schedule

_PUBLIC_GRAPH_KEYS = {
    "mode",
    "effective_mode",
    "status",
    "node_count",
    "edge_count",
    "is_dag",
    "critical_path_minutes",
    "critical_path_node_count",
    "warning_count",
    "cycle_edge_count",
    "time_cost_ms",
    "input_scope",
    "total_algo_op_count",
    "reschedulable_unfrozen_op_count",
    "frozen_node_count",
    "seed_result_count",
    "graph_enhancement_allowed",
    "graph_enhancement_disabled_reason",
    "ready_queue_enabled",
    "score_enabled",
    "score_metric_status",
    "score_disabled_reason",
    "score_weight_summary",
}
_ERROR_PUBLIC_GRAPH_KEYS = {
    "mode",
    "effective_mode",
    "status",
    "reason",
    "message",
    "time_cost_ms",
    "input_scope",
    "total_algo_op_count",
    "reschedulable_unfrozen_op_count",
    "frozen_node_count",
    "seed_result_count",
}
_FORBIDDEN_LOG_KEYS = {
    "diagnostics",
    "nodes",
    "edges",
    "raw",
    "node_metrics",
    "topological_order",
    "topological_order_sample",
    "critical_path_sample",
    "warnings_sample",
    "cycle_edges_sample",
    "graph_score_sample",
    "node_metrics_sample",
    "matches_sample",
    "unmatched_operation_sample",
    "unmatched_operation_ids_sample",
    "bottleneck_machine_sample",
    "bottleneck_machine_ids_sample",
    "resource_pool",
}


def _make_dt(hours: int) -> datetime:
    return datetime(2026, 1, 1, 8, 0, 0) + timedelta(hours=hours)


class _TxManager:
    @contextmanager
    def transaction(self) -> Iterator[None]:
        yield


class _ScheduleRepo:
    def __init__(self) -> None:
        self.rows: List[Dict[str, Any]] = []

    def bulk_create(self, rows: List[Dict[str, Any]]) -> None:
        self.rows.extend(rows)


class _HistoryRepo:
    def __init__(self) -> None:
        self.rows: List[Dict[str, Any]] = []

    def create(self, row: Dict[str, Any]) -> None:
        self.rows.append(dict(row))


class _UpdateRepo:
    def __init__(self) -> None:
        self.updates: List[Any] = []

    def update(self, key: Any, payload: Dict[str, Any]) -> None:
        self.updates.append((key, dict(payload)))


class _OpLogger:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def info(self, **kwargs: Any) -> None:
        self.calls.append(dict(kwargs))


class _Svc:
    def __init__(self) -> None:
        self.tx_manager = _TxManager()
        self.schedule_repo = _ScheduleRepo()
        self.history_repo = _HistoryRepo()
        self.op_repo = _UpdateRepo()
        self.batch_repo = _UpdateRepo()
        self.op_logger = _OpLogger()

    @staticmethod
    def _format_dt(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


def _result() -> SimpleNamespace:
    return SimpleNamespace(
        op_id=1,
        batch_id="B001",
        machine_id="MC1",
        operator_id="OP1",
        start_time=_make_dt(0),
        end_time=_make_dt(1),
        source="internal",
    )


def _result_summary_obj() -> Dict[str, Any]:
    return {
        "algo": {
            "graph_analysis": {
                "mode": "report",
                "effective_mode": "report",
                "status": "available",
                "node_count": 2,
                "edge_count": 1,
                "is_dag": True,
                "critical_path_minutes": 60,
                "critical_path_node_count": 2,
                "warning_count": 0,
                "cycle_edge_count": 0,
                "time_cost_ms": 4,
                "input_scope": "all_algo_ops_with_frozen_markers",
                "total_algo_op_count": 2,
                "reschedulable_unfrozen_op_count": 2,
                "frozen_node_count": 0,
                "seed_result_count": 0,
                "graph_enhancement_allowed": True,
                "graph_enhancement_disabled_reason": None,
                "ready_queue_enabled": True,
                "score_enabled": True,
                "score_metric_status": "available",
                "score_disabled_reason": None,
                "score_weight_summary": {
                    "critical_weight": 500,
                    "impact_weight": 10,
                    "downstream_minutes_weight": 1,
                },
            }
        },
        "diagnostics": {
            "graph_analysis": {
                "topological_order_sample": ["op:1", "op:2"],
                "critical_path_sample": ["op:1", "op:2"],
                "warnings_sample": [],
                "cycle_edges_sample": [],
                "node_metrics_sample": [{"node_id": "op:1"}],
                "graph_score_sample": [{"op_id": 1, "bonus": 560}],
            }
        },
    }


def _known_error_result_summary_obj() -> Dict[str, Any]:
    return {
        "algo": {
            "graph_analysis": {
                "mode": "report",
                "effective_mode": "report",
                "status": "unavailable",
                "reason": "networkx_unavailable",
                "message": "缺少可选依赖 networkx==3.1",
                "time_cost_ms": 4,
                "input_scope": "all_algo_ops_with_frozen_markers",
                "total_algo_op_count": 2,
                "reschedulable_unfrozen_op_count": 2,
                "frozen_node_count": 0,
                "seed_result_count": 0,
            }
        }
    }


def _resource_matching_result_summary_obj() -> Dict[str, Any]:
    return {
        "algo": {
            "graph_analysis": {
                "mode": "report",
                "effective_mode": "report",
                "status": "available",
                "node_count": 3,
                "edge_count": 0,
                "is_dag": True,
                "critical_path_minutes": 60,
                "critical_path_node_count": 1,
                "warning_count": 0,
                "cycle_edge_count": 0,
                "time_cost_ms": 4,
                "input_scope": "all_algo_ops_with_frozen_markers",
                "total_algo_op_count": 3,
                "reschedulable_unfrozen_op_count": 3,
                "frozen_node_count": 0,
                "seed_result_count": 0,
                "resource_matching": {
                    "status": "available",
                    "reason": "ok",
                    "ready_operation_count": 3,
                    "operation_with_candidate_count": 3,
                    "machine_count": 2,
                    "edge_count": 6,
                    "matched_operation_count": 2,
                    "unmatched_operation_count": 1,
                    "bottleneck_machine_count": 2,
                },
            }
        },
        "diagnostics": {
            "graph_analysis": {
                "resource_matching": {
                    "matches_sample": [{"operation_id": "1", "machine_id": "M1"}],
                    "matches_count": 2,
                    "unmatched_operation_ids_sample": ["3"],
                    "unmatched_operation_count": 1,
                    "bottleneck_machine_ids_sample": ["M1", "M2"],
                    "bottleneck_machine_count": 2,
                    "warnings_sample": [],
                    "resource_pool": {"machines_by_op_type": {"cut": ["M1", "M2"]}},
                }
            }
        },
    }


def _iter_keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _iter_keys(child)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_keys(item)


def _persist_once(*, simulate: bool, result_summary_obj: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    svc = _Svc()
    result = _result()
    payload = build_validated_schedule_payload([result], allowed_op_ids={1})
    summary_obj = result_summary_obj if result_summary_obj is not None else _result_summary_obj()
    persist_schedule(
        svc,
        cfg=SimpleNamespace(auto_assign_persist="no"),
        version=3,
        validated_schedule_payload=payload,
        summary=SimpleNamespace(total_ops=1, scheduled_ops=1, failed_ops=0),
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={"dispatch": "fifo"},
        batches={"B001": SimpleNamespace(batch_id="B001", status="pending")},
        reschedulable_operations=[SimpleNamespace(id=1, batch_id="B001", source="internal")],
        normalized_batch_ids=["B001"],
        created_by="pytest",
        simulate=simulate,
        frozen_op_ids=set(),
        result_status="simulated" if simulate else "success",
        result_summary_json="{}",
        result_summary_obj=summary_obj,
        missing_internal_resource_op_ids=set(),
        overdue_items=[],
        time_cost_ms=9,
    )
    assert len(svc.op_logger.calls) == 1
    return svc.op_logger.calls[0]


def test_operation_logs_keep_only_graph_public_summary_for_simulate_and_schedule() -> None:
    for simulate, action in ((True, "simulate"), (False, "schedule")):
        call = _persist_once(simulate=simulate)
        detail = call["detail"]
        graph_analysis = detail["algo"]["graph_analysis"]

        assert call["action"] == action
        assert set(graph_analysis) == _PUBLIC_GRAPH_KEYS
        assert graph_analysis["status"] == "available"
        assert "diagnostics" not in detail
        assert _FORBIDDEN_LOG_KEYS.isdisjoint(set(_iter_keys(detail)))


def test_operation_logs_keep_known_graph_error_public_and_small() -> None:
    call = _persist_once(simulate=True, result_summary_obj=_known_error_result_summary_obj())
    detail = call["detail"]
    graph_analysis = detail["algo"]["graph_analysis"]

    assert set(graph_analysis) == _ERROR_PUBLIC_GRAPH_KEYS
    assert graph_analysis["status"] == "unavailable"
    assert graph_analysis["reason"] == "networkx_unavailable"
    assert graph_analysis["message"] == "缺少可选依赖 networkx==3.1"
    assert "diagnostics" not in detail
    assert _FORBIDDEN_LOG_KEYS.isdisjoint(set(_iter_keys(detail)))


def test_operation_logs_keep_resource_matching_public_counts_without_samples() -> None:
    call = _persist_once(simulate=True, result_summary_obj=_resource_matching_result_summary_obj())
    detail = call["detail"]
    graph_analysis = detail["algo"]["graph_analysis"]
    resource_matching = graph_analysis["resource_matching"]

    assert resource_matching == {
        "status": "available",
        "reason": "ok",
        "ready_operation_count": 3,
        "operation_with_candidate_count": 3,
        "machine_count": 2,
        "edge_count": 6,
        "matched_operation_count": 2,
        "unmatched_operation_count": 1,
        "bottleneck_machine_count": 2,
    }
    assert "diagnostics" not in detail
    assert _FORBIDDEN_LOG_KEYS.isdisjoint(set(_iter_keys(detail)))
