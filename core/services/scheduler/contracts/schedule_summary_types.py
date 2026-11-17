from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Set, Tuple

from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary
from core.models.batch import Batch
from core.models.batch_operation import BatchOperation
from core.models.enums import SortStrategy
from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot


class SummaryMetrics(Protocol):
    invalid_due_count: int
    invalid_due_batch_ids_sample: List[str]
    unscheduled_batch_count: int
    unscheduled_batch_ids_sample: List[str]
    _due_by_batch: Dict[str, Optional[date]]
    _finish_by_batch: Dict[str, datetime]

    def numeric_dict(self) -> Dict[str, Any]: ...
    def public_dict(self) -> Dict[str, Any]: ...


class ScheduleResultStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SIMULATED = "simulated"


@dataclass(frozen=True)
class SummaryBuildContext:
    cfg: ScheduleConfigSnapshot
    version: int
    normalized_batch_ids: List[str]
    start_dt: datetime
    end_date: date
    batches: Dict[str, Batch]
    operations: List[BatchOperation]
    results: List[ScheduleResult]
    summary: ScheduleSummary
    used_strategy: SortStrategy
    # Metadata and traces are heterogeneous producer-owned payloads, not normalized here.
    used_params: Dict[str, Any]
    algo_mode: str
    objective_name: str
    time_budget_seconds: int
    best_score: Tuple[float, ...]
    best_metrics: SummaryMetrics
    frozen_op_ids: Set[int]
    scheduled_op_ids: Set[int]
    freeze_meta: Dict[str, Any]
    missing_internal_resource_op_ids: Set[int]
    t0: float
    readiness_gate_enabled: bool
    algo_stats: Dict[str, Any]
    graph_analysis_public: Optional[Dict[str, Any]]
    graph_analysis_diagnostics: Optional[Dict[str, Any]]
    candidate_comparison_public: Optional[Dict[str, Any]]
    execution_snapshot_revision: Optional[str]
    execution_snapshot_op_ids: List[int]
    execution_snapshot_op_count: int


@dataclass(frozen=True)
class RuntimeState:
    finish_by_batch: Dict[str, datetime]
    overdue_items: List[Dict[str, Any]]
    near_due_items: List[Dict[str, Any]]
    invalid_due_count: int
    invalid_due_batch_ids_sample: List[str]
    unscheduled_batch_count: int
    unscheduled_batch_ids_sample: List[str]
    incomplete_batch_ids: Set[str] = field(default_factory=set)


@dataclass(frozen=True)
class AlgorithmSummaryState:
    ctx: SummaryBuildContext
    hard_constraints: List[str]
    freeze_state: Dict[str, Any]
    frozen_batch_ids: List[str]
    fallback_counts: Dict[str, int]
