from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.algorithms import GreedyScheduler, ScheduleResult, SortStrategy
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.greedy.algo_stats import snapshot_algo_stats
from core.models.schedule_config_runtime import default_snapshot_values
from core.services.scheduler.graph.metrics import build_node_metrics
from core.services.scheduler.graph.precedence_builder import build_precedence_graph
from core.services.scheduler.graph.types import OperationGraphNode
from core.services.scheduler.run.optimizer_graph_ready import run_graph_ready_candidates
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState

GRAPH_READY_REAL_SGS_CASE_SLUG = "graph-ready-weight-grid-real-sgs"
GRAPH_READY_REAL_SGS_CASE_GROUP = "graph_ready"
GRAPH_READY_FLEXIBLE_MACHINE_CASE_SLUG = "graph-ready-flexible-machine-bottleneck-metric"
GRAPH_READY_FLEXIBLE_MACHINE_CASE_GROUP = "graph_ready_metric"
OBJECTIVE_NAME = "min_overdue"
START_DT = datetime(2026, 1, 1, 8, 0, 0)
BASE_BATCH_ORDER = ["B_LONG", "B_MED", "B_SHORT_A", "B_SHORT_B"]


class BenchmarkClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        self.now += 0.01
        return self.now


class ContinuousCalendar:
    def adjust_to_working_time(
        self,
        dt: datetime,
        priority: Any = None,
        machine_id: Any = None,
        operator_id: Any = None,
    ) -> datetime:
        return dt

    def add_working_hours(
        self,
        dt: datetime,
        hours: float,
        priority: Any = None,
        machine_id: Any = None,
        operator_id: Any = None,
    ) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, machine_id: Any = None, operator_id: Any = None) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float, machine_id: Any = None, operator_id: Any = None) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


def graph_ready_benchmark_operations() -> List[Any]:
    return [
        _operation(1, "B_LONG", hours=12.0),
        _operation(2, "B_MED", hours=8.0),
        _operation(3, "B_SHORT_A", hours=2.0),
        _operation(4, "B_SHORT_B", hours=2.0),
    ]


def graph_ready_benchmark_batches() -> Dict[str, Any]:
    return {
        batch_id: SimpleNamespace(
            batch_id=batch_id,
            priority="normal",
            due_date="2026-01-01",
            ready_status="yes",
            ready_date=None,
            quantity=1,
        )
        for batch_id in BASE_BATCH_ORDER
    }


def graph_ready_benchmark_context(*, include_bottleneck: bool = True) -> Dict[str, Any]:
    metrics_by_op_id: Dict[int, Dict[str, Any]] = {
        1: {
            "is_on_critical_path": False,
            "critical_path_rank": None,
            "impact_count": 1,
            "generation_index": 0,
            "downstream_critical_minutes": 720,
            "bottleneck_machine_score": 1.0,
        },
        2: {
            "is_on_critical_path": False,
            "critical_path_rank": None,
            "impact_count": 6,
            "generation_index": 0,
            "downstream_critical_minutes": 480,
            "bottleneck_machine_score": 1.0,
        },
        3: {
            "is_on_critical_path": True,
            "critical_path_rank": 0,
            "impact_count": 0,
            "generation_index": 0,
            "downstream_critical_minutes": 120,
            "bottleneck_machine_score": 10.0,
        },
        4: {
            "is_on_critical_path": False,
            "critical_path_rank": None,
            "impact_count": 0,
            "generation_index": 0,
            "downstream_critical_minutes": 120,
            "bottleneck_machine_score": 8.0,
        },
    }
    if not include_bottleneck:
        metrics_by_op_id = {
            op_id: {key: value for key, value in metric.items() if key != "bottleneck_machine_score"}
            for op_id, metric in metrics_by_op_id.items()
        }
    op_ids = set(metrics_by_op_id)
    return {
        "enabled": True,
        "schedulable_op_ids": op_ids,
        "fixed_op_ids": set(),
        "fixed_op_sources_by_op_id": {},
        "predecessor_op_ids_by_op_id": {op_id: set() for op_id in op_ids},
        "successor_op_ids_by_op_id": {op_id: set() for op_id in op_ids},
        "sort_key_by_op_id": {
            op_id: (0, index, op_id)
            for index, op_id in enumerate(sorted(op_ids), start=1)
        },
        "graph_priority_key_by_op_id": {op_id: (0.0,) for op_id in op_ids},
        "node_metrics_by_op_id": metrics_by_op_id,
    }


def flexible_machine_bottleneck_scores() -> Dict[str, float]:
    graph = build_precedence_graph(
        [
            _metric_node("op:busy", seq=10, duration_minutes=120, machine_id="MC-B"),
            _metric_node("op:light", seq=20, duration_minutes=30, machine_id="MC-A"),
            _metric_node("op:flex", seq=30, duration_minutes=60, candidate_machine_ids=("MC-A", "MC-B")),
        ],
        [],
    )
    metrics = build_node_metrics(graph)
    return {
        "busy": float(metrics["op:busy"]["bottleneck_machine_score"]),
        "light": float(metrics["op:light"]["bottleneck_machine_score"]),
        "flex": float(metrics["op:flex"]["bottleneck_machine_score"]),
    }


def run_graph_ready_flexible_machine_metric_case() -> Dict[str, Any]:
    scores = flexible_machine_bottleneck_scores()
    row = {
        "case_group": GRAPH_READY_FLEXIBLE_MACHINE_CASE_GROUP,
        "case_slug": GRAPH_READY_FLEXIBLE_MACHINE_CASE_SLUG,
        "algorithm_profile": "graph_ready",
        "candidate_origin": "graph_ready_metric",
        "seed": 0,
        "time_budget_seconds": 0,
        "objective_name": OBJECTIVE_NAME,
        "objective_score": [],
        "baseline_objective_score": [],
        "objective_score_matched": True,
        "failed_ops": 0,
        "baseline_failed_ops": 0,
        "gap_to_oracle_pct": 0.0,
        "runtime_ms": 0,
        "candidate_profile_count": 0,
        "evaluated_candidates": 0,
        "accepted_distinct_candidates": 0,
        "distinct_candidates": 0,
        "same_fingerprint_rejections": 0,
        "candidate_rejections": {},
        "best_origin": "graph_ready_metric",
        "bottleneck_scores": scores,
        "comparison_to_meta_baseline": {
            "metric": "bottleneck_scores",
            "baseline_value": scores,
            "actual_value": scores,
            "status": "same",
        },
    }
    row["status"] = "passed" if _flexible_machine_metric_row_passes(row) else "failed"
    return row


def run_graph_ready_real_sgs_case(*, seed: int = 0) -> Dict[str, Any]:
    scheduler = _scheduler()
    operations = graph_ready_benchmark_operations()
    batches = graph_ready_benchmark_batches()
    baseline = _baseline_candidate(scheduler=scheduler, operations=operations, batches=batches)
    state = OptimizationSearchReportState(
        algorithm_profile="graph_ready",
        seed=int(seed),
        time_budget_seconds=1,
        objective_name=OBJECTIVE_NAME,
        started_at=1000.0,
        candidate_profile={"acceptance": "improve_only"},
        strict_mode=True,
    )
    state.mark_candidate_accepted(baseline, origin="baseline")
    attempts: List[Dict[str, Any]] = []
    improvement_trace: List[Dict[str, Any]] = []
    best = run_graph_ready_candidates(
        algo_mode="improve",
        best=baseline,
        version=int(seed),
        scheduler=scheduler,
        algo_ops_to_schedule=operations,
        batches=batches,
        start_dt=START_DT,
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        base_strategy=SortStrategy.PRIORITY_FIRST,
        base_params={},
        build_order=lambda _strategy, _params: list(BASE_BATCH_ORDER),
        dispatch_rule_cfg="slack",
        resource_pool=None,
        objective_name=OBJECTIVE_NAME,
        deadline=2000.0,
        attempts=attempts,
        improvement_trace=improvement_trace,
        optimizer_algo_stats=snapshot_algo_stats(scheduler),
        t_begin=1000.0,
        readiness_gate_enabled=False,
        strict_mode=True,
        graph_ready_context=graph_ready_benchmark_context(),
        clock=BenchmarkClock(),
        schedule_fn=_schedule_with_scheduler,
        search_report_state=state,
    )
    if best is None:
        raise AssertionError("graph-ready benchmark did not return a best candidate")
    graph_attempts = [attempt for attempt in attempts if str(attempt.get("tag") or "").startswith("graph_ready:")]
    row = _benchmark_row(
        seed=seed,
        baseline=baseline,
        best=best,
        state=state,
        graph_attempts=graph_attempts,
    )
    row["status"] = "passed" if _row_passes(row) else "failed"
    return row


def _operation(op_id: int, batch_id: str, *, hours: float) -> Any:
    return SimpleNamespace(
        id=int(op_id),
        op_code=f"OP-{batch_id}",
        batch_id=str(batch_id),
        seq=10,
        source="internal",
        machine_id="MC-BENCH",
        operator_id="OP-BENCH",
        setup_hours=float(hours),
        unit_hours=0.0,
        op_type_id="OT-BENCH",
        op_type_name="BENCH",
    )


def _metric_node(
    node_id: str,
    *,
    seq: int,
    duration_minutes: int,
    machine_id: Optional[str] = None,
    candidate_machine_ids: Tuple[str, ...] = (),
) -> OperationGraphNode:
    return OperationGraphNode(
        node_id=node_id,
        batch_id="B_METRIC",
        op_code=node_id.replace("op:", "METRIC-"),
        seq=int(seq),
        name=node_id,
        duration_minutes=int(duration_minutes),
        machine_id=machine_id,
        candidate_machine_ids=candidate_machine_ids,
    )


def _scheduler() -> GreedyScheduler:
    return GreedyScheduler(calendar_service=ContinuousCalendar(), config_service=_default_config())


def _default_config() -> Any:
    values = default_snapshot_values()
    values.update(
        {
            "sort_strategy": "priority_first",
            "dispatch_mode": "sgs",
            "dispatch_rule": "slack",
            "auto_assign_enabled": "no",
            "objective": OBJECTIVE_NAME,
            "algo_mode": "greedy",
            "time_budget_seconds": 1,
            "ortools_enabled": "no",
            "freeze_window_enabled": "no",
            "freeze_window_days": 0,
        }
    )
    return SimpleNamespace(**values)


def _baseline_candidate(*, scheduler: GreedyScheduler, operations: List[Any], batches: Dict[str, Any]) -> Dict[str, Any]:
    results, summary, strategy, params = scheduler.schedule(
        operations=operations,
        batches=batches,
        strategy=SortStrategy.PRIORITY_FIRST,
        strategy_params={},
        start_dt=START_DT,
        dispatch_mode="sgs",
        dispatch_rule="slack",
        batch_order_override=list(BASE_BATCH_ORDER),
        seed_results=[],
        strict_mode=True,
    )
    metrics = compute_metrics(results, batches)
    return {
        "results": results,
        "summary": summary,
        "strategy": strategy,
        "params": params,
        "dispatch_mode": "sgs",
        "dispatch_rule": "slack",
        "order": list(BASE_BATCH_ORDER),
        "metrics": metrics,
        "score": (float(summary.failed_ops),) + objective_score(OBJECTIVE_NAME, metrics),
        "algo_stats": snapshot_algo_stats(scheduler),
        "candidate_origin": "baseline",
        "runtime_ms": 0,
    }


def _schedule_with_scheduler(scheduler: GreedyScheduler, **kwargs: Any) -> Any:
    return scheduler.schedule(**kwargs)


def _benchmark_row(
    *,
    seed: int,
    baseline: Dict[str, Any],
    best: Dict[str, Any],
    state: OptimizationSearchReportState,
    graph_attempts: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    baseline_score = _score_list(baseline.get("score"))
    best_score = _score_list(best.get("score"))
    failed_ops = int(getattr(best.get("summary"), "failed_ops", 0) or 0)
    baseline_failed_ops = int(getattr(baseline.get("summary"), "failed_ops", 0) or 0)
    return {
        "case_group": GRAPH_READY_REAL_SGS_CASE_GROUP,
        "case_slug": GRAPH_READY_REAL_SGS_CASE_SLUG,
        "algorithm_profile": "graph_ready",
        "candidate_origin": "graph_ready_weight_grid",
        "seed": int(seed),
        "time_budget_seconds": 1,
        "objective_name": OBJECTIVE_NAME,
        "objective_score": best_score,
        "baseline_objective_score": baseline_score,
        "objective_score_matched": bool(tuple(best_score) <= tuple(baseline_score)),
        "failed_ops": failed_ops,
        "baseline_failed_ops": baseline_failed_ops,
        "gap_to_oracle_pct": 0.0,
        "runtime_ms": int(best.get("runtime_ms") or 0),
        "candidate_profile_count": len(graph_attempts),
        "evaluated_candidates": int(state.evaluated_candidates),
        "accepted_distinct_candidates": int(len(state.accepted_fingerprints)),
        "distinct_candidates": int(len(state.candidate_fingerprints)),
        "same_fingerprint_rejections": int(state.rejection_summary.get("same_fingerprint") or 0),
        "candidate_rejections": dict(state.rejection_summary),
        "best_origin": str(state.best_origin or best.get("candidate_origin") or ""),
        "best_output_fingerprint": str(state.best_fingerprint or ""),
        "candidate_output_fingerprints": sorted(state.candidate_fingerprints),
        "accepted_output_fingerprints": sorted(state.accepted_fingerprints),
        "best_order": _result_order(best.get("results")),
        "baseline_order": _result_order(baseline.get("results")),
        "comparison_to_meta_baseline": {
            "metric": "objective_score",
            "baseline_value": baseline_score,
            "actual_value": best_score,
            "status": "improved" if tuple(best_score) < tuple(baseline_score) else "same",
        },
    }


def _row_passes(row: Dict[str, Any]) -> bool:
    return (
        int(row.get("failed_ops") or 0) == 0
        and bool(row.get("objective_score_matched"))
        and int(row.get("candidate_profile_count") or 0) == 9
        and int(row.get("evaluated_candidates") or 0) >= 10
        and int(row.get("distinct_candidates") or 0) >= 3
        and int(row.get("accepted_distinct_candidates") or 0) >= 2
        and str(row.get("best_origin") or "") != "baseline"
        and tuple(_score_list(row.get("objective_score"))) < tuple(_score_list(row.get("baseline_objective_score")))
    )


def _flexible_machine_metric_row_passes(row: Dict[str, Any]) -> bool:
    scores = row.get("bottleneck_scores") if isinstance(row.get("bottleneck_scores"), dict) else {}
    return (
        int(row.get("failed_ops") or 0) == 0
        and bool(row.get("objective_score_matched"))
        and float(scores.get("busy") or 0.0) == 2.5
        and float(scores.get("light") or 0.0) == 1.0
        and float(scores.get("flex") or 0.0) == 0.707107
        and float(scores.get("flex") or 0.0) < float(scores.get("light") or 0.0) < float(scores.get("busy") or 0.0)
    )


def _score_list(value: Any) -> List[float]:
    if not isinstance(value, (list, tuple)):
        return []
    return [float(item) for item in value]


def _result_order(value: Any) -> List[int]:
    return [int(getattr(item, "op_id")) for item in list(value or [])]
