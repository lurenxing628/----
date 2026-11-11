from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

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
    resource_pool: Optional[Dict[str, Any]]
    downtime_meta: Mapping[str, Any]
    resource_pool_meta: Mapping[str, Any]
    optimizer_seed_version: int


@dataclass(frozen=True)
class SolverInput:
    batches: Dict[str, Batch]
    algo_ops: List[OpForScheduleAlgo]
    to_schedule: List[OpForScheduleAlgo]
    config: ScheduleConfigSnapshot
    start: datetime
    end_date: Optional[date]
    readiness_gate_enabled: bool
    seeds: SeedPreparation
    predecessors: Mapping[int, Sequence[int]] = field(default_factory=dict)

