from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from core.algorithm_contracts.resource_pool import ResourcePool
from core.algorithm_contracts.types import OpForScheduleAlgo
from core.models.batch import Batch
from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot
from core.services.scheduler.calendar.engine import CalendarEngine
from core.services.scheduler.execution.execution_fact_provider import ExecutionFact


@dataclass(frozen=True)
class ExecutionGuardState:
    execution_facts: Mapping[int, ExecutionFact]
    execution_resource_segments: Mapping[
        Tuple[str, str], Sequence[Tuple[datetime, Optional[datetime], int]]
    ]
    execution_completed_op_ids: Set[int]
    execution_seed_results: Sequence[Dict[str, Any]]
    execution_snapshot_revision: str
    execution_snapshot_op_ids: Tuple[int, ...]
    execution_snapshot_op_count: int


@dataclass(frozen=True)
class SeedPreparation:
    frozen_op_ids: Set[int]
    seed_results: List[Dict[str, Any]]
    freeze_meta: Mapping[str, Any]
    to_schedule: List[OpForScheduleAlgo]
    unscheduled_external_seed_by_op: Mapping[int, Tuple[datetime, datetime]]


@dataclass(frozen=True)
class SolverResources:
    calendar_engine: CalendarEngine
    downtime_map: Dict[str, List[Tuple[datetime, datetime]]]
    resource_pool: ResourcePool
    optimizer_seed_version: int
    # The run's monotonic clock: the candidate comparison's budget runs on it (run_candidate_comparison).
    clock: Callable[[], float]


@dataclass(frozen=True)
class SolverInput:
    batches: Dict[str, Batch]
    algo_ops: List[OpForScheduleAlgo]
    to_schedule: List[OpForScheduleAlgo]
    config: ScheduleConfigSnapshot
    start: datetime
    end_date: date
    readiness_gate_enabled: bool
    seeds: SeedPreparation
    # Required standard hours of every internal operation this run schedules, taken from the run's
    # operation efforts (the one standard-work formula); the decoder reads them, never recomputes them.
    required_hours_by_op_id: Mapping[int, float]
    predecessors: Mapping[int, Sequence[int]] = field(default_factory=dict)

