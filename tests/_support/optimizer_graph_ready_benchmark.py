from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from core.algorithm_contracts.types import OpForScheduleAlgo
from core.algorithm_runtime.checkpoint_calendar import register_checkpoint_calendar
from core.algorithms.greedy.scheduler import GreedyScheduler
from core.models.batch import Batch
from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot
from tests._support.algo_operations import make_algo_op, make_batch
from tests._support.schedule_decode import config_snapshot

OBJECTIVE_NAME = "min_overdue"
START_DT = datetime(2026, 1, 1, 8, 0, 0)
BASE_BATCH_ORDER = ["B_LONG", "B_MED", "B_SHORT_A", "B_SHORT_B"]


class BenchmarkClock:
    """Deterministic monotonic test clock for scheduler fixtures."""
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
        return dt + timedelta(hours=float(hours))

    def add_effective_hours(self, dt: datetime, hours: float, priority: Any = None, operator_id: Any = None) -> datetime:
        return self.add_working_hours(dt, hours)  # constant efficiency 1.0

    def add_calendar_days(self, dt: datetime, days: float, machine_id: Any = None, operator_id: Any = None) -> datetime:
        return dt + timedelta(days=float(days))

    def working_hours_between(
        self,
        start: datetime,
        end: datetime,
        priority: Any = None,
        machine_id: Any = None,
        operator_id: Any = None,
    ) -> float:
        return (end - start).total_seconds() / 3600.0

    def capacity_hours_between(
        self,
        start: datetime,
        end: datetime,
        *,
        priority: Any = None,
        operator_id: Any = None,
    ) -> float:
        return (end - start).total_seconds() / 3600.0


# A continuous calendar is checkpoint-reusable only while its class and empty instance state are intact.
register_checkpoint_calendar(ContinuousCalendar, lambda calendar: () if not vars(calendar) else None)


def graph_ready_benchmark_operations() -> List[OpForScheduleAlgo]:
    return [
        _operation(1, "B_LONG", hours=12.0),
        _operation(2, "B_MED", hours=8.0),
        _operation(3, "B_SHORT_A", hours=2.0),
        _operation(4, "B_SHORT_B", hours=2.0),
    ]


def graph_ready_benchmark_batches() -> Dict[str, Batch]:
    return {
        batch_id: make_batch(batch_id=batch_id, part_no=batch_id, due_date="2026-01-01")
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


def _operation(op_id: int, batch_id: str, *, hours: float) -> OpForScheduleAlgo:
    return make_algo_op(
        id=op_id, op_code=f"OP-{batch_id}", batch_id=batch_id, seq=10, machine_id="MC-BENCH",
        operator_id="OP-BENCH", setup_hours=hours, unit_hours=0.0, op_type_id="OT-BENCH", op_type_name="BENCH",
    )


def _scheduler() -> GreedyScheduler:
    return GreedyScheduler(calendar_service=ContinuousCalendar(), config_service=_default_config())


def _default_config() -> ScheduleConfigSnapshot:
    return config_snapshot(
        sort_strategy="priority_first", dispatch_mode="sgs", dispatch_rule="slack", auto_assign_enabled="no",
        objective=OBJECTIVE_NAME, algo_mode="greedy", time_budget_seconds=1, ortools_enabled="no",
        freeze_window_enabled="no", freeze_window_days=0,
    )
