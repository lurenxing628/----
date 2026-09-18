"""One outer candidate's plan: the record the comparison keeps per trial and how it is built."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Tuple

from .schedule_candidate_dedup import UNCERTIFIED_PREFIX
from .schedule_candidate_health import CandidateHealth
from .schedule_candidate_runtime_helpers import _candidate_score, _dict_list, _dict_or_none, _string_list
from .schedule_candidate_specs import CandidateRunSpec

CANDIDATE_STATUS_COMPLETED = "completed"
# O25 裁定保留：FAILED 态生产不可达（生产零 raise 点）但属已落库 status 枚举契约，裸删破坏持久化兼容。
CANDIDATE_STATUS_FAILED = "failed"
CANDIDATE_STATUS_SKIPPED = "skipped"


class CandidateTrialFailure(RuntimeError):
    """单个候选方案可记录为 failed 的运行失败。"""


@dataclass(frozen=True)
class CandidatePlan:
    sequence: int
    candidate_key: str
    kind: str
    label: str
    status: str
    score: Optional[Tuple[float, ...]]
    graph_critical_weight: int
    graph_impact_weight: int
    graph_downstream_weight: int
    results: List[Any] = field(default_factory=list)
    summary: Any = None
    metrics: Any = None
    health: Optional[CandidateHealth] = None
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
    time_budget_seconds: int = 0
    search_report: Dict[str, Any] = field(default_factory=dict)
    sort_strategy: str = ""
    # Dispatch mode the plan really decoded with; a graph tier forces ``sgs`` whatever was configured.
    dispatch_mode: str = ""
    dispatch_rule: str = ""
    objective: str = ""
    # Dispatch rule of the plan the optimizer finally adopted; may differ from the configured
    # ``dispatch_rule`` because the rule pool is an optimizer-internal search dimension.
    adopted_dispatch_rule: str = ""
    failure_reason: Optional[str] = None
    elapsed_seconds: float = 0.0
    # Set when this plan is a completed sibling's plan under this candidate's identity: the two
    # candidates had identical optimizer inputs, so no search of its own was spent on it.
    reused_from_candidate_key: Optional[str] = None
    reused_from_label: Optional[str] = None
    # ``certified`` when the optimizer inputs were fingerprinted for sibling reuse,
    # ``uncertified: <reason>`` when they could not be (the plan ran its own search), empty
    # for plans that never enter the ledger (the baseline).
    input_certification: str = ""


@dataclass(frozen=True)
class CandidateComparisonOutcome:
    candidates: List[CandidatePlan]
    selection: Any
    planned_count: int
    completed_count: int
    failed_count: int
    skipped_count: int
    time_budget_reached: bool
    selection_policy: str
    run_time_budget_seconds: Optional[float]
    skipped_candidate_labels: List[str]
    baseline_missing_or_failed: bool
    reused_count: int = 0


@dataclass(frozen=True)
class CandidateRunArtifacts:
    candidate_cfg: Any
    graph_preparation: Any
    outcome: Any


def adopted_dispatch_mode(outcome: Any, candidate_cfg: Any) -> str:
    """The mode the plan really decoded with: graph tiers force sgs regardless of the configured mode."""
    adopted = str(getattr(outcome, "dispatch_mode", None) or "").strip().lower()
    return adopted or str(candidate_cfg.dispatch_mode)


def candidate_plan_from_artifacts(
    spec: CandidateRunSpec,
    *,
    artifacts: CandidateRunArtifacts,
    health: CandidateHealth,
) -> CandidatePlan:
    candidate_cfg = artifacts.candidate_cfg
    graph_preparation = artifacts.graph_preparation
    outcome = artifacts.outcome
    return CandidatePlan(
        sequence=int(spec.sequence),
        candidate_key=spec.candidate_key,
        kind=spec.kind,
        label=spec.label,
        status=CANDIDATE_STATUS_COMPLETED,
        score=_candidate_score(outcome),
        graph_critical_weight=int(spec.graph_critical_weight),
        graph_impact_weight=int(spec.graph_impact_weight),
        graph_downstream_weight=int(spec.graph_downstream_weight),
        results=list(outcome.results or []),
        summary=getattr(outcome, "summary", None),
        metrics=getattr(outcome, "metrics", None),
        health=health,
        graph_analysis_public=_dict_or_none(getattr(graph_preparation, "graph_analysis_public", None)),
        graph_analysis_diagnostics=_dict_or_none(getattr(graph_preparation, "graph_analysis_diagnostics", None)),
        used_strategy=getattr(outcome, "used_strategy", None),
        used_params=dict(getattr(outcome, "used_params", None) or {}),
        best_order=_string_list(getattr(outcome, "best_order", None)),
        attempts=_dict_list(getattr(outcome, "attempts", None)),
        improvement_trace=_dict_list(getattr(outcome, "improvement_trace", None)),
        algo_mode=str(getattr(outcome, "algo_mode", None) or ""),
        objective_name=str(getattr(outcome, "objective_name", None) or ""),
        algo_stats=dict(getattr(outcome, "algo_stats", None) or {}),
        time_budget_seconds=int(getattr(outcome, "time_budget_seconds", None) or 0),
        search_report=dict(getattr(outcome, "search_report", None) or {}),
        sort_strategy=str(candidate_cfg.sort_strategy),
        dispatch_mode=adopted_dispatch_mode(outcome, candidate_cfg),
        dispatch_rule=str(candidate_cfg.dispatch_rule),
        objective=str(candidate_cfg.objective),
        adopted_dispatch_rule=str(getattr(outcome, "dispatch_rule", None) or ""),
    )


def with_input_certification(plan: CandidatePlan, certification: Optional[str], *, logger: Any) -> CandidatePlan:
    if certification is None:
        return plan
    if certification.startswith(UNCERTIFIED_PREFIX) and logger is not None:
        logger.warning("候选方案 %s 的优化器输入无法指纹化，不能复用兄弟方案：%s", plan.label, certification)
    return replace(plan, input_certification=certification)


def skipped_plan(spec: CandidateRunSpec, *, failure_reason: str) -> CandidatePlan:
    return CandidatePlan(
        sequence=int(spec.sequence),
        candidate_key=spec.candidate_key,
        kind=spec.kind,
        label=spec.label,
        status=CANDIDATE_STATUS_SKIPPED,
        score=None,
        graph_critical_weight=int(spec.graph_critical_weight),
        graph_impact_weight=int(spec.graph_impact_weight),
        graph_downstream_weight=int(spec.graph_downstream_weight),
        failure_reason=failure_reason,
    )


def failed_plan(spec: CandidateRunSpec, exc: Exception, *, elapsed_seconds: float) -> CandidatePlan:
    return CandidatePlan(
        sequence=int(spec.sequence),
        candidate_key=spec.candidate_key,
        kind=spec.kind,
        label=spec.label,
        status=CANDIDATE_STATUS_FAILED,
        score=None,
        graph_critical_weight=int(spec.graph_critical_weight),
        graph_impact_weight=int(spec.graph_impact_weight),
        graph_downstream_weight=int(spec.graph_downstream_weight),
        failure_reason=str(exc),
        elapsed_seconds=float(elapsed_seconds),
    )


__all__ = [
    "CANDIDATE_STATUS_COMPLETED",
    "CANDIDATE_STATUS_FAILED",
    "CANDIDATE_STATUS_SKIPPED",
    "CandidateComparisonOutcome",
    "CandidatePlan",
    "CandidateRunArtifacts",
    "CandidateTrialFailure",
    "adopted_dispatch_mode",
    "candidate_plan_from_artifacts",
    "failed_plan",
    "skipped_plan",
    "with_input_certification",
]
