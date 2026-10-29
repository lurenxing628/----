from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Set, Tuple, Union

from core.algorithm_contracts.sort_strategies import SortStrategy
from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary
from core.models.batch import Batch
from core.models.batch_operation import BatchOperation
from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot


class SummaryMetrics(Protocol):
    invalid_due_count: int
    invalid_due_batch_ids_sample: List[str]
    unscheduled_batch_count: int
    unscheduled_batch_ids_sample: List[str]

    def to_dict(self) -> Dict[str, Any]: ...


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
    end_date: Optional[Union[date, str]]
    batches: Dict[str, Batch]
    operations: List[BatchOperation]
    results: List[ScheduleResult]
    summary: Optional[ScheduleSummary]
    used_strategy: SortStrategy
    # Metadata and traces are heterogeneous producer-owned payloads, not normalized here.
    used_params: Dict[str, Any]
    algo_mode: str
    objective_name: str
    time_budget_seconds: int
    best_score: Optional[Tuple[float, ...]]
    best_metrics: Optional[SummaryMetrics]
    attempts: List[Dict[str, Any]]
    improvement_trace: List[Dict[str, Any]]
    frozen_op_ids: Set[int]
    scheduled_op_ids: Set[int]
    freeze_meta: Dict[str, Any]
    search_report: Dict[str, Any] = field(default_factory=dict)
    missing_internal_resource_op_ids: Optional[Set[int]] = None
    downtime_meta: Dict[str, Any] = field(default_factory=dict)
    resource_pool_meta: Optional[Dict[str, Any]] = None
    readiness_gate_enabled: bool = False
    algo_stats: Optional[Dict[str, Any]] = None
    graph_analysis_public: Optional[Dict[str, Any]] = None
    graph_analysis_diagnostics: Optional[Dict[str, Any]] = None
    candidate_comparison_public: Optional[Dict[str, Any]] = None
    execution_snapshot_revision: Optional[str] = None
    execution_snapshot_op_ids: List[int] = field(default_factory=list)
    execution_snapshot_op_count: int = 0
    simulate: bool = False
    t0: float = 0.0


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
class FallbackState:
    fallback_counts: Dict[str, int]
    ortools_warmstart_failed_count: int


@dataclass(frozen=True)
class AlgorithmSummaryState:
    ctx: SummaryBuildContext
    hard_constraints: List[str]
    freeze_state: Dict[str, Any]
    frozen_batch_ids: List[str]
    resource_pool_meta: Optional[Dict[str, Any]]
    resource_pool_enabled: bool
    resource_pool_attempted: bool
    fallback_state: FallbackState
