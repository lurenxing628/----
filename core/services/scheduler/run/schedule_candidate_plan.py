"""Business representatives and the retained shape of archived candidate records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary

if TYPE_CHECKING:
    from core.services.scheduler.contracts.schedule_summary_types import SummaryMetrics


@dataclass(frozen=True)
class CandidatePlan:
    sequence: int
    candidate_key: str
    kind: str
    label: str
    status: str
    score: Optional[Tuple[float, ...]]
    graph_critical_weight: Optional[int]
    graph_impact_weight: Optional[int]
    graph_downstream_weight: Optional[int]
    results: List[ScheduleResult] = field(default_factory=list)
    summary: Optional[ScheduleSummary] = None
    metrics: Optional[SummaryMetrics] = None
    health: Optional[Dict[str, Any]] = None
    graph_analysis_public: Optional[Dict[str, Any]] = None
    graph_analysis_diagnostics: Optional[Dict[str, Any]] = None
    used_strategy: Any = None
    used_params: Dict[str, Any] = field(default_factory=dict)
    best_order: List[str] = field(default_factory=list)
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    improvement_trace: List[Dict[str, Any]] = field(default_factory=list)
    algo_mode: str = ""
    objective_name: str = ""
    algo_stats: Dict[str, Any] = field(default_factory=dict)
    time_budget_seconds: float = 0
    search_report: Dict[str, Any] = field(default_factory=dict)
    sort_strategy: str = ""
    # Dispatch mode the plan really decoded with; a graph tier forces ``sgs`` whatever was configured.
    dispatch_mode: str = ""
    dispatch_rule: str = ""
    objective: str = ""
    # Dispatch rule of the plan the optimizer finally adopted; may differ from the configured
    # ``dispatch_rule`` because the rule pool is an optimizer-internal search dimension.
    adopted_dispatch_rule: str = ""
    elapsed_seconds: float = 0.0
    generation_policy_version: Optional[str] = None
    representative_objectives: List[str] = field(default_factory=list)
    evaluations: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    origin: Optional[Dict[str, Any]] = None
    first_found_elapsed_ms: Optional[int] = None
    search_evidence_ref: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class CandidateComparisonOutcome:
    candidates: List[CandidatePlan]
    selection: Any
    time_budget_reached: bool
    run_time_budget_seconds: Optional[float]
    generation_policy_version: Optional[str] = None
    primary_objective: Optional[str] = None
    target_objectives: List[str] = field(default_factory=list)
    unified_process: Optional[Dict[str, Any]] = None


__all__ = [
    "CandidateComparisonOutcome", "CandidatePlan",
]
