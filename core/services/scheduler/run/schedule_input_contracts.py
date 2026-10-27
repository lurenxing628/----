from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set

from core.algorithm_contracts.operation_effort import OperationEffort
from core.algorithm_contracts.types import OpForScheduleAlgo
from core.models.batch import Batch
from core.models.batch_operation import BatchOperation
from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot
from core.services.scheduler.execution.execution_fact_provider import ExecutionFact


@dataclass
class ScheduleRunInput:
    normalized_batch_ids: List[str]
    start_dt_norm: datetime
    end_date_norm: Optional[date]
    t0: float
    cal_svc: Any
    cfg: ScheduleConfigSnapshot
    readiness_gate_enabled: bool
    batches: Dict[str, Batch]
    operations: List[BatchOperation]
    missing_internal_resource_op_ids: Set[int]
    algo_ops: List[OpForScheduleAlgo]
    prev_version: int
    frozen_op_ids: Set[int]
    seed_results: List[Dict[str, Any]]
    execution_facts: Dict[int, ExecutionFact]
    execution_completed_op_ids: Set[int]
    execution_seed_results: List[Dict[str, Any]]
    execution_snapshot_revision: str
    execution_snapshot_op_ids: List[int]
    execution_snapshot_op_count: int
    schedule_output_allowed_op_ids: Set[int]
    payload_validation_operations: List[BatchOperation]
    freeze_meta: Dict[str, Any]
    algo_ops_to_schedule: List[OpForScheduleAlgo]
    downtime_meta: Dict[str, Any]
    resource_pool_meta: Dict[str, Any]
    downtime_map: Dict[str, Any]
    resource_pool: Any
    optimizer_seed_version: int
    operation_efforts: List[OperationEffort] = field(default_factory=list)
    operation_sources: Any = None

