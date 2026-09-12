"""One clock and deadline across candidate comparison and optimizer phases."""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

from core.models.objective import best_score_schema_parts, objective_choice_labels


class SearchBudgetExhausted(RuntimeError):
    """No decoder started: the caller must record a skipped candidate."""


@dataclass(frozen=True)
class SearchBudget:
    clock: Callable[[], float]
    started_at: float
    deadline: float
    outer_deadline: float
    assigned_seconds: float
    allocation_feedback: Optional[Dict[str, Any]] = None

    def require_available(self) -> None:
        if self.clock() >= self.deadline:
            raise SearchBudgetExhausted("candidate_time_budget_reached")

    def optimizer_deadline(self, *, started_at: float, configured_seconds: int, improve: bool) -> float:
        configured_deadline = started_at + float(configured_seconds) if improve else float("inf")
        return min(self.deadline, configured_deadline)

    def report(self, *, optimizer_deadline: float, optimizer_started_at: float) -> Dict[str, Any]:
        report: Dict[str, Any] = {
            "policy": "shared_deadline_observed_feedback_v2" if self.allocation_feedback else "shared_deadline_remaining_equal_slices_v1",
            "clock": "shared_monotonic",
            "assigned_time_budget_ms": _milliseconds(self.assigned_seconds),
            "preparation_runtime_ms": _milliseconds(max(optimizer_started_at - self.started_at, 0.0)),
            "optimizer_time_budget_ms": _milliseconds(max(optimizer_deadline - optimizer_started_at, 0.0)),
            "outer_remaining_time_ms": _milliseconds(max(self.outer_deadline - optimizer_started_at, 0.0)),
        }
        if self.allocation_feedback is not None:
            report["allocation_feedback"] = dict(self.allocation_feedback)
        return report


def allocate_candidate_budget(
    *, clock: Callable[[], float], started_at: float, deadline: float, remaining_candidates: int,
    feedback: Optional[CandidateBudgetFeedback] = None,
) -> SearchBudget:
    """Unused time returns to the pool; every remaining advertised plan keeps a slot."""
    remaining = max(deadline - started_at, 0.0)
    assigned = remaining / float(max(remaining_candidates, 1))
    allocation_feedback = None
    if feedback is not None:
        assigned, allocation_feedback = feedback.allocate(remaining, remaining_candidates=remaining_candidates)
    return SearchBudget(
        clock=clock, started_at=started_at, deadline=min(deadline, started_at + assigned),
        outer_deadline=deadline, assigned_seconds=assigned, allocation_feedback=allocation_feedback,
    )


class CandidateBudgetFeedback:
    """One observed trial adjusts the next slice; no future improvement is inferred.

    Reserve half an equal share for every untried plan. A measured strict
    improvement earns a bounded bonus, scaled by improvements per second;
    a measured non-improvement leaves more time for the untried plans. Baseline,
    incomplete scores, different objectives and unknown elapsed time earn no signal.
    """

    def __init__(self, objective_name: str) -> None:
        self.objective_name = objective_name
        self._score_keys = tuple(key for key, _label in best_score_schema_parts(objective_name))
        self._best_score: Optional[Tuple[float, ...]] = None
        self._last: Dict[str, Any] = {}
        self.observed_completed_count = 0
        self.observed_improvement_count = 0

    def observe(self, plan: Any) -> None:
        score = _completed_feedback_score(plan, objective_name=self.objective_name, score_keys=self._score_keys)
        elapsed = _positive_measured_seconds(getattr(plan, "elapsed_seconds", None))
        self._last = {}
        if score is None or elapsed is None:
            return
        improved = None if self._best_score is None else score < self._best_score
        self.observed_completed_count += 1
        if improved:
            self.observed_improvement_count += 1
        if self._best_score is None or improved:
            self._best_score = score
        self._last = {
            "candidate_sequence": int(plan.sequence), "strict_improvement": improved,
            "elapsed_seconds": elapsed,
            "improvements_per_second": _measured_improvement_rate(improved, elapsed),
        }

    def allocate(self, remaining: float, *, remaining_candidates: int) -> Tuple[float, Dict[str, Any]]:
        count = max(int(remaining_candidates), 1)
        equal_slice = remaining / float(count)
        factor, reason = self._allocation_factor(equal_slice, remaining_candidates=count)
        minimum_share = equal_slice * 0.5
        maximum_share = remaining - minimum_share * (count - 1) if math.isfinite(remaining) else remaining
        assigned = min(equal_slice * factor, maximum_share)
        report: Dict[str, Any] = {
            "policy": "observed_strict_improvement_per_second_v1",
            "reason": reason, "observed_completed_count": self.observed_completed_count,
            "observed_improvement_count": self.observed_improvement_count,
            "feedback_applied": factor != 1.0,
            "allocation_factor": assigned / equal_slice if equal_slice > 0 and math.isfinite(equal_slice) else 1.0,
            "equal_slice_ms": _milliseconds(equal_slice),
            "minimum_untried_share_ms": _milliseconds(minimum_share),
            "reserved_for_other_candidates_ms": _milliseconds(max(remaining - assigned, 0.0)) if math.isfinite(remaining) else None,
        }
        report.update(self._last)
        return assigned, report

    def _allocation_factor(self, equal_slice: float, *, remaining_candidates: int) -> Tuple[float, str]:
        if remaining_candidates == 1:
            return 1.0, "last_candidate_uses_remaining"
        if not math.isfinite(equal_slice) or equal_slice <= 0:
            return 1.0, "no_finite_remaining_budget"
        improved = self._last.get("strict_improvement")
        if improved is None:
            return 1.0, "no_measured_comparable_improvement"
        if self._last.get("improvements_per_second") is None:
            return 1.0, "unrepresentable_improvement_rate"
        if not improved:
            return 0.5, "observed_no_improvement_reserve_untried"
        # Equivalent to 1 + (equal_slice * observed_rate) / (1 + equal_slice * observed_rate),
        # written this way so a very large rate cannot overflow the product.
        return 1.0 + 1.0 / (1.0 + self._last["elapsed_seconds"] / equal_slice), "observed_strict_improvement_bonus"


def _completed_feedback_score(
    plan: Any, *, objective_name: str, score_keys: Tuple[str, ...],
) -> Optional[Tuple[float, ...]]:
    if objective_name not in objective_choice_labels() or getattr(plan, "status", None) != "completed":
        return None
    if getattr(plan, "objective_name", None) != objective_name or getattr(plan, "objective", None) != objective_name:
        return None
    summary = getattr(plan, "summary", None)
    completion = getattr(getattr(plan, "metrics", None), "completion", None)
    if getattr(summary, "success", None) is not True or getattr(completion, "objective_defined", None) is not True:
        return None
    if getattr(summary, "failed_ops", None) != 0:
        return None
    return _canonical_feedback_score(getattr(plan, "score", None), score_keys)


def _canonical_feedback_score(score: Any, score_keys: Tuple[str, ...]) -> Optional[Tuple[float, ...]]:
    if type(score) is not tuple or len(score) != len(score_keys):
        return None
    values = []
    for key, value in zip(score_keys, score):
        number = _finite_feedback_number(value)
        if number is None or number < 0 or number == sys.float_info.max:
            return None
        if key in ("failed_ops", "overdue_count", "changeover_count") and not number.is_integer():
            return None
        values.append(number)
    return tuple(values) if values[0] == 0 else None


def _positive_measured_seconds(value: Any) -> Optional[float]:
    number = _finite_feedback_number(value)
    return number if number is not None and number > 0 else None


def _finite_feedback_number(value: Any) -> Optional[float]:
    if type(value) not in (int, float):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) else None


def _measured_improvement_rate(improved: Optional[bool], elapsed: float) -> Optional[float]:
    if improved is None:
        return None
    rate = 1.0 / elapsed if improved else 0.0
    return rate if math.isfinite(rate) else None


@dataclass(frozen=True)
class OptimizerPhaseBudget:
    deadline: float
    multi_start_deadline: float
    warmstart_deadline: float
    heuristic_deadline: float

    @classmethod
    def create(cls, *, started_at: float, deadline: float, improve: bool, graph_ready: bool) -> OptimizerPhaseBudget:
        if not improve or not math.isfinite(deadline):
            return cls(deadline, deadline, deadline, deadline)
        remaining = max(deadline - started_at, 0.0)
        return cls(
            deadline=deadline,
            multi_start_deadline=started_at + remaining * 0.25,
            warmstart_deadline=started_at + remaining * 0.35,
            heuristic_deadline=deadline if graph_ready else started_at + remaining * 0.65,
        )


class ReservedPhaseReport:
    """Report a phase slice ending without claiming that the whole run timed out."""

    def __init__(self, state: Any, *, clock: Callable[[], float], deadline: float, phase: str) -> None:
        self._state = state
        self._clock = clock
        self._deadline = deadline
        self._phase = phase

    def __getattr__(self, name: str) -> Any:
        return getattr(self._state, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("_state", "_clock", "_deadline", "_phase"):
            object.__setattr__(self, name, value)
        else:
            setattr(self._state, name, value)

    def mark_deadline_reached(self) -> None:
        if self._clock() >= self._deadline:
            self._state.mark_deadline_reached()
        else:
            self._state.mark_phase_skipped(self._phase, "reserved_for_later_phases")

    def mark_phase_skipped(self, phase: str, reason: str, **extra: Any) -> None:
        if reason == "time_budget" and self._clock() < self._deadline:
            reason = "reserved_for_later_phases"
        self._state.mark_phase_skipped(phase, reason, **extra)


def publish_search_budget(
    *, report_state: Any, attempts: Any, budget: Optional[SearchBudget],
    phases: OptimizerPhaseBudget, started_at: float, finished_at: Optional[float] = None,
) -> None:
    if finished_at is not None and finished_at >= phases.deadline:
        report_state.mark_deadline_reached()
    if budget is None:
        return
    report = budget.report(optimizer_deadline=phases.deadline, optimizer_started_at=started_at)
    report.update({
        "phase_policy": "baseline_then_reserved_search_v1",
        "multi_start_budget_ms": _milliseconds(max(phases.multi_start_deadline - started_at, 0.0)),
        "warmstart_cutoff_ms": _milliseconds(max(phases.warmstart_deadline - started_at, 0.0)),
        "heuristic_cutoff_ms": _milliseconds(max(phases.heuristic_deadline - started_at, 0.0)),
    })
    if finished_at is not None:
        report["deadline_overrun_ms"] = _milliseconds(max(finished_at - phases.deadline, 0.0))
        report["outer_deadline_overrun_ms"] = _milliseconds(max(finished_at - budget.outer_deadline, 0.0))
        attempts.append({"tag": "optimizer_budget", "candidate_status": "phase_summary", "optimizer_budget": report})
    profile = dict(report_state.candidate_profile or {})
    message = str(profile.get("message") or "")
    assigned_ms = report["assigned_time_budget_ms"]
    marker = "本方案共享总预算"
    if marker not in message and assigned_ms is not None:
        message += " 本方案共享总预算，分配 %.3f 秒，准备工作计入这段时间。" % (assigned_ms / 1000.0)
    report_state.update_candidate_profile(
        assigned_time_budget_ms=assigned_ms, optimizer_budget=report, message=message.strip(),
    )


def _milliseconds(seconds: float) -> Optional[int]:
    return max(int(seconds * 1000), 0) if math.isfinite(seconds) else None
