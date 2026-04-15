from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from core.services.common.build_outcome import BuildOutcome


@dataclass(frozen=True)
class SummaryBuildContext:
    cfg: Any
    version: int
    normalized_batch_ids: List[str]
    start_dt: datetime
    end_date: Optional[Any]
    batches: Dict[str, Any]
    operations: List[Any]
    results: List[Any]
    summary: Any
    used_strategy: Any
    used_params: Dict[str, Any]
    algo_mode: str
    objective_name: str
    time_budget_seconds: int
    best_score: Optional[Tuple[float, ...]]
    best_metrics: Optional[Any]
    best_order: List[str]
    attempts: List[Dict[str, Any]]
    improvement_trace: List[Dict[str, Any]]
    frozen_op_ids: Set[int]
    freeze_meta: Optional[Dict[str, Any]] = None
    input_build_outcome: Optional[BuildOutcome[Any]] = None
    downtime_meta: Optional[Dict[str, Any]] = None
    resource_pool_meta: Optional[Dict[str, Any]] = None
    algo_stats: Optional[Dict[str, Any]] = None
    algo_warnings: Optional[List[str]] = None
    warning_merge_status: Optional[Dict[str, Any]] = None
    simulate: bool = False
    t0: float = 0.0


@dataclass(frozen=True)
class RuntimeState:
    finish_by_batch: Dict[str, datetime]
    overdue_items: List[Dict[str, Any]]
    invalid_due_count: int
    invalid_due_batch_ids_sample: List[str]
    unscheduled_batch_count: int
    unscheduled_batch_ids_sample: List[str]


@dataclass(frozen=True)
class WarningState:
    summary_warnings: List[str]
    algo_warning_list: List[str]
    all_warnings: List[str]
    merge_context_degraded: bool
    merge_context_events: List[Dict[str, Any]]


@dataclass(frozen=True)
class FreezeState:
    data: Dict[str, Any]
    all_warnings: List[str]

    @property
    def status(self) -> str:
        return str(self.data.get("freeze_state") or "")


@dataclass(frozen=True)
class FallbackState:
    raw_stats: Dict[str, Any]
    fallback_counts: Dict[str, int]
    param_fallbacks: Dict[str, int]
    legacy_external_days_defaulted_count: int
    ortools_warmstart_failed_count: int


@dataclass(frozen=True)
class AlgorithmSummaryState:
    ctx: SummaryBuildContext
    input_state: Dict[str, Any]
    downtime_state: Dict[str, Any]
    hard_constraints: List[str]
    warning_state: WarningState
    freeze_state: FreezeState
    frozen_batch_ids: List[str]
    resource_pool_meta: Optional[Dict[str, Any]]
    resource_pool_enabled: bool
    resource_pool_degraded: bool
    resource_pool_degradation_reason: Optional[str]
    resource_pool_attempted: bool
    warning_pipeline: Dict[str, Any]
    fallback_state: FallbackState


@dataclass(frozen=True)
class TruncationTier:
    trace_limit: int
    warning_limit: int
    attempt_limit: int
    best_order_limit: Optional[int] = None
    selected_ids_limit: Optional[int] = None
    overdue_items_limit: Optional[int] = None


DEFAULT_TRUNCATION_TIERS: Tuple[TruncationTier, ...] = (
    TruncationTier(80, 50, 12),
    TruncationTier(20, 20, 12),
    TruncationTier(0, 20, 12),
    TruncationTier(0, 10, 6),
    TruncationTier(0, 0, 6, 2000, 2000, 500),
    TruncationTier(0, 0, 6, 500, 1000, 200),
    TruncationTier(0, 0, 6, 100, 200, 50),
    TruncationTier(0, 0, 6, 0, 50, 20),
    TruncationTier(0, 0, 0, 0, 0, 0),
)
