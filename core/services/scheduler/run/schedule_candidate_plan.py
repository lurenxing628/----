"""Business representatives of one shared search; the stored artifact keys are in facts/candidate_artifact."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary

if TYPE_CHECKING:
    from core.services.scheduler.contracts.schedule_summary_types import SummaryMetrics

# The business facts every candidate of the unified search records: the receipt summary, the stored artifact and
# the public candidate cards all carry these CandidatePlan attributes.
BUSINESS_FIELDS = ("representative_objectives", "evaluations", "origin", "first_found_elapsed_ms", "search_evidence_ref")
# What an archive entry keeps of the search stage that found it (``search_origin``): the search direction, stage
# and origin, how the decode dispatched, and the decode request behind it. Every decode the search produces carries
# its receipt, so every published plan's origin has all of these.
ORIGIN_FIELDS = ("search_objective", "phase", "origin", "dispatch_mode", "dispatch_rule", "strategy",
                 "repair_decision", "request_id", "source_event_ref", "execution_kind")
# A plan decoded with a graph-ready weight profile (its used_params name one) records that profile in its origin too.
GRAPH_PROFILE_FIELD = "graph_ready_profile"


def search_origin(candidate: Dict[str, Any], receipt: Dict[str, Any], *, search_objective: str, phase: str,
                  origin: str) -> Dict[str, Any]:
    """The ORIGIN_FIELDS of one observed decode: the decode session's receipt names the request and its event.

    Every candidate builder (multi-start, GRASP/IG, local search, graph payload) writes the dispatch pair and
    ``repair_decision``, which is None unless a graph repair decision produced the decode."""
    return {"search_objective": search_objective, "phase": phase, "origin": origin,
            "dispatch_mode": candidate["dispatch_mode"], "dispatch_rule": candidate["dispatch_rule"],
            "strategy": candidate["strategy"].value, "repair_decision": candidate["repair_decision"],
            "request_id": receipt["request_id"], "source_event_ref": receipt["source_event_ref"],
            "execution_kind": receipt["execution_kind"]}


def origin_fields(used_params: Dict[str, Any]) -> Tuple[str, ...]:
    """The keys of a published plan's origin: ORIGIN_FIELDS, and the profile when the plan decoded with one."""
    return ORIGIN_FIELDS + ((GRAPH_PROFILE_FIELD,) if used_params.get(GRAPH_PROFILE_FIELD) is not None else ())


def plan_origin(entry_origin: Dict[str, Any], used_params: Dict[str, Any]) -> Dict[str, Any]:
    """A published plan's own origin record: its archive entry's origin with the profile the plan decoded with."""
    values = dict(entry_origin, **{GRAPH_PROFILE_FIELD: used_params.get(GRAPH_PROFILE_FIELD)})
    return {name: values[name] for name in origin_fields(used_params)}


@dataclass(frozen=True)
class CandidatePlan:
    sequence: int
    candidate_key: str
    label: str
    score: Tuple[float, ...]
    summary: ScheduleSummary
    metrics: SummaryMetrics
    origin: Dict[str, Any]
    first_found_elapsed_ms: int
    search_evidence_ref: Dict[str, Any]
    used_params: Dict[str, Any]
    results: List[ScheduleResult] = field(default_factory=list)
    graph_analysis_public: Optional[Dict[str, Any]] = None
    graph_analysis_diagnostics: Optional[Dict[str, Any]] = None
    used_strategy: Any = None
    best_order: List[str] = field(default_factory=list)
    algo_mode: str = ""
    objective_name: str = ""
    algo_stats: Dict[str, Any] = field(default_factory=dict)
    time_budget_seconds: float = 0
    # Dispatch mode the plan really decoded with; a graph tier forces ``sgs`` whatever was configured.
    dispatch_mode: str = ""
    representative_objectives: List[str] = field(default_factory=list)
    evaluations: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class CandidateComparisonOutcome:
    candidates: List[CandidatePlan]
    selection: Any
    time_budget_reached: bool
    run_time_budget_seconds: float
    primary_objective: str
    unified_process: Dict[str, Any]
    target_objectives: List[str] = field(default_factory=list)


__all__ = [
    "BUSINESS_FIELDS", "GRAPH_PROFILE_FIELD", "ORIGIN_FIELDS", "CandidateComparisonOutcome", "CandidatePlan",
    "origin_fields", "plan_origin", "search_origin",
]
