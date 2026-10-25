"""Actual decoder costs and target opportunities under one run deadline."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, Iterable, NoReturn, Optional, Tuple


class SharedSearchSkip(RuntimeError):
    """This request did not execute; the current stage must yield control."""

    def __init__(self, reason: str, request_id: Optional[int] = None,
                 receipt: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.request_id = request_id
        self.receipt = receipt


@dataclass
class _GoalOpportunity:
    weight: float
    elapsed_seconds: float = 0.0
    charged_seconds: float = 0.0
    preparation_seconds: float = 0.0
    actions: int = 0
    new_decisions: int = 0
    reused_decisions: int = 0
    probe_decisions: int = 0
    improvement_actions: int = 0
    minimum_opportunity: bool = False
    has_gain: bool = False
    paused: bool = False
    not_applicable: bool = False
    unavailable_reason: Optional[str] = None
    budget_reason: Optional[str] = None
    phase_seconds: Dict[str, float] = field(default_factory=dict)


class SharedSearchBudget:
    """Own admission samples, actual costs and the 60/20/20 opportunity ledger.

    Decoder elapsed time is measured by the decode session. Action elapsed time
    includes preparation, request generation, observation and reference upkeep;
    these are two views of the same wall time, never added to each other.
    """

    _KINDS = ("batch_order_full", "sgs_full", "sgs_resume")

    def __init__(self, *, clock: Callable[[], float], started_at: float, deadline: float,
                 target_objectives: Tuple[str, ...], configured_seconds: float) -> None:
        self.clock = clock
        self.started_at = started_at
        self.deadline = deadline
        self.target_objectives = tuple(target_objectives)
        self.configured_seconds = float(configured_seconds)
        self._goals = {objective: _GoalOpportunity(0.6 if index == 0 else 0.2)
                       for index, objective in enumerate(self.target_objectives)}
        self._samples: Dict[str, Deque[float]] = {kind: deque(maxlen=3) for kind in self._KINDS}
        self._unpruned_sgs_samples: Deque[float] = deque(maxlen=3)
        self._max_full_seconds: float = 0.0
        self._decode_counts: Dict[str, int] = dict.fromkeys(self._KINDS, 0)
        self._decode_seconds = 0.0
        self._first_construction_admitted = False
        self._admission_skips: Dict[str, int] = {}
        self._feedback: Deque[Tuple[str, float, bool]] = deque(maxlen=8)
        self._first_complete_at: Optional[float] = None
        self._last_progress_at = started_at
        self._stalled_decisions = 0
        self._startup_cursor = 0
        self._available: Optional[Tuple[str, ...]] = None
        self._defer_once: Optional[str] = None
        self._action_count = 0
        self._phase_seconds: Dict[str, float] = {}
        self.auxiliary_probe_limit = 4 if self.configured_seconds >= 30.0 else 2
        self.stall_decision_limit = 10 if self.configured_seconds >= 30.0 else 6
        self.stall_seconds = 5.0 if self.configured_seconds >= 30.0 else 2.0

    def remaining(self) -> float:
        return max(self.deadline - self.clock(), 0.0)

    def estimate(self, kind: str) -> float:
        """Use three measured calls; an unseen kind borrows the full-call maximum."""
        samples = self._samples[kind]
        if samples:
            return max(samples) * 1.25
        full_samples = tuple(self._samples["batch_order_full"]) + tuple(self._samples["sgs_full"])
        return max(full_samples) * 1.25 if full_samples else 0.0

    def _required_estimate(self, kind: str, *, reserve_full: bool = False, unpruned_sgs: bool = False) -> float:
        estimate = self.estimate(kind)
        if unpruned_sgs and kind == "sgs_full":
            unpruned_base = max(self._unpruned_sgs_samples) if self._unpruned_sgs_samples else self._max_full_seconds
            estimate = max(estimate, unpruned_base * 1.25)
        if reserve_full:
            estimate += self.estimate("sgs_full")
        return estimate

    def can_afford_decode(self, kind: str, *, reserve_full: bool = False) -> bool:
        """Check whether the remaining budget can cover one decode without mutating admission state."""
        remaining = self.remaining()
        if remaining <= 0.0 or not any(self._decode_counts.values()):
            return False
        return self._required_estimate(kind, reserve_full=reserve_full) <= remaining

    def reject(self, reason: str) -> NoReturn:
        """Count one admission rejection without inventing a decode request."""
        self._admission_skips[reason] = self._admission_skips.get(reason, 0) + 1
        raise SharedSearchSkip(reason)

    def require_decode(self, kind: str, *, reserve_full: bool = False,
                       first_construction: bool = False, unpruned_sgs: bool = False) -> None:
        """Recheck the actual clock immediately before each real decoder call."""
        remaining = self.remaining()
        reason = None
        estimate = self._required_estimate(kind, reserve_full=reserve_full, unpruned_sgs=unpruned_sgs)
        if remaining <= 0.0:
            reason = "time_budget"
        elif not any(self._decode_counts.values()):
            if not first_construction or self._first_construction_admitted:
                reason = "estimated_decode_cost"
            else:
                self._first_construction_admitted = True
        elif estimate > remaining:
            reason = "estimated_decode_cost"
        if reason is not None:
            self.reject(reason)

    def record_decode(self, kind: str, elapsed_seconds: float, *, unpruned_sgs: bool = False) -> None:
        """Record exactly one real schedule/metrics call, including failed calls."""
        elapsed = max(float(elapsed_seconds), 0.0)
        self._samples[kind].append(elapsed)
        if kind in ("batch_order_full", "sgs_full"):
            self._max_full_seconds = max(self._max_full_seconds, elapsed)
        if unpruned_sgs and kind == "sgs_full":
            self._unpruned_sgs_samples.append(elapsed)
        self._decode_counts[kind] += 1
        self._decode_seconds += elapsed

    def _charge(self, objective: str, phase: str, elapsed_seconds: float) -> float:
        elapsed = max(float(elapsed_seconds), 0.0)
        goal = self._goals[objective]
        goal.elapsed_seconds += elapsed
        goal.charged_seconds += max(elapsed, 0.001)
        goal.phase_seconds[phase] = goal.phase_seconds.get(phase, 0.0) + elapsed
        self._phase_seconds[phase] = self._phase_seconds.get(phase, 0.0) + elapsed
        return elapsed

    def charge_preparation(self, objective: str, phase: str, elapsed_seconds: float) -> None:
        elapsed = self._charge(objective, phase, elapsed_seconds)
        self._goals[objective].preparation_seconds += elapsed

    def record_action(self, objective: str, phase: str, elapsed_seconds: float, *,
                      new_decisions: int = 0, reused_decisions: int = 0,
                      improved_objectives: Iterable[str] = (), first_complete: bool = False,
                      initial: bool = False, skip_reason: Optional[str] = None) -> None:
        elapsed = self._charge(objective, phase, elapsed_seconds)
        goal = self._goals[objective]
        goal.actions += 1
        self._action_count += 1
        goal.new_decisions += new_decisions
        goal.reused_decisions += reused_decisions
        complete_before_action = self._first_complete_at is not None
        improved = bool(tuple(improved_objectives))
        if elapsed > 0.0:
            self._feedback.append((objective, elapsed, improved))
        if improved:
            goal.has_gain = True
            goal.improvement_actions += 1
        if complete_before_action and not initial and new_decisions > 0:
            goal.minimum_opportunity = True
            goal.probe_decisions += new_decisions
            goal.unavailable_reason = None
            goal.budget_reason = None
        if first_complete and self._first_complete_at is None:
            self._first_complete_at = self.clock()
            self._startup_cursor = 0
        if improved or first_complete:
            self._last_progress_at = self.clock()
            self._stalled_decisions = 0
        elif complete_before_action and not initial:
            self._stalled_decisions += new_decisions
        if (objective != self.target_objectives[0] and not goal.has_gain
                and goal.probe_decisions >= self.auxiliary_probe_limit):
            goal.paused = True
        if complete_before_action and not initial and new_decisions == 0:
            self._defer_once = objective
        if skip_reason in ("estimated_decode_cost", "time_budget"):
            goal.budget_reason = skip_reason
            self._defer_once = objective

    def has_minimum_opportunity(self, objective: str) -> bool:
        return self._goals[objective].minimum_opportunity

    def mark_unavailable(self, objective: str, reason: str, *, not_applicable: bool = False) -> None:
        """The caller distinguishes exhausted work from a stage waiting for a parent."""
        goal = self._goals[objective]
        goal.unavailable_reason = reason
        goal.not_applicable = not_applicable

    def _minimum_resolved(self, goal: _GoalOpportunity) -> bool:
        return (goal.minimum_opportunity or goal.not_applicable or goal.paused
                or goal.unavailable_reason is not None or goal.budget_reason is not None)

    def _feedback_rates(self) -> Dict[str, float]:
        elapsed = dict.fromkeys(self.target_objectives, 0.0)
        improvements = dict.fromkeys(self.target_objectives, 0)
        for objective, seconds, improved in self._feedback:
            elapsed[objective] += seconds
            improvements[objective] += int(improved)
        return {objective: improvements[objective] / seconds if seconds > 0.0 else 0.0
                for objective, seconds in elapsed.items()}

    def _feedback_bonuses(self, rates: Dict[str, float]) -> Dict[str, float]:
        maximum = max(rates.values(), default=0.0)
        return {objective: 0.25 * rate / maximum if maximum > 0.0 else 0.0
                for objective, rate in rates.items()}

    def select_goal(self, available_objectives: Iterable[str]) -> Optional[str]:
        """Select a startup opportunity, then the least charged weighted direction."""
        available = set(available_objectives)
        self._available = tuple(objective for objective in self.target_objectives
                                if objective in available and not self._goals[objective].paused
                                and not self._goals[objective].not_applicable)
        for objective in self._available:
            self._goals[objective].unavailable_reason = None
        if self.should_stop() is not None:
            return None
        if self._first_complete_at is None:
            primary = self.target_objectives[0]
            return primary if primary in self._available else None
        candidates = self._available
        if len(candidates) > 1 and self._defer_once in candidates:
            candidates = tuple(objective for objective in candidates if objective != self._defer_once)
        self._defer_once = None
        for offset in range(len(self.target_objectives)):
            index = (self._startup_cursor + offset) % len(self.target_objectives)
            objective = self.target_objectives[index]
            if objective in candidates and not self._minimum_resolved(self._goals[objective]):
                self._startup_cursor = (index + 1) % len(self.target_objectives)
                return objective
        if not candidates:
            return None
        bonuses = self._feedback_bonuses(self._feedback_rates())
        return min(candidates, key=lambda objective: (
            self._goals[objective].charged_seconds / self._goals[objective].weight
            / (1.0 + bonuses[objective]), self.target_objectives.index(objective)))

    def should_stop(self, *, at: Optional[float] = None) -> Optional[str]:
        now = self.clock() if at is None else at
        if now >= self.deadline:
            return "time_budget"
        if self._available == ():
            return "search_exhausted"
        if (self._first_complete_at is not None
                and all(self._minimum_resolved(goal) for goal in self._goals.values())
                and self._stalled_decisions >= self.stall_decision_limit
                and now - self._last_progress_at >= self.stall_seconds):
            return "stagnation"
        return None

    @staticmethod
    def _status(goal: _GoalOpportunity) -> str:
        if goal.paused:
            return "paused_no_gain"
        if goal.new_decisions > 0:
            return "searched"
        if goal.budget_reason is not None:
            return "not_searched_budget"
        return "not_applicable" if goal.not_applicable else "not_searched_budget"

    def summary(self, *, finished_at: Optional[float] = None) -> Dict[str, Any]:
        now = self.clock() if finished_at is None else finished_at
        rates = self._feedback_rates()
        bonuses = self._feedback_bonuses(rates)
        goals = {
            objective: {
                "objective_status": self._status(goal), "weight": goal.weight,
                "elapsed_seconds": goal.elapsed_seconds, "charged_seconds": goal.charged_seconds,
                "preparation_seconds": goal.preparation_seconds, "action_count": goal.actions,
                "new_decisions": goal.new_decisions, "reused_decisions": goal.reused_decisions,
                "probe_decisions": goal.probe_decisions, "minimum_opportunity": goal.minimum_opportunity,
                "improvement_action_count": goal.improvement_actions, "has_gain": goal.has_gain,
                "feedback_rate": rates[objective], "feedback_bonus": bonuses[objective],
                "unavailable_reason": goal.unavailable_reason, "budget_reason": goal.budget_reason,
                "phase_elapsed_seconds": dict(goal.phase_seconds),
            } for objective, goal in self._goals.items()
        }
        return {
            "policy": "shared_search_budget_v1", "clock": "shared_monotonic",
            "configured_seconds": self.configured_seconds,
            "elapsed_seconds": max(now - self.started_at, 0.0),
            "remaining_seconds": max(self.deadline - now, 0.0),
            "deadline_overrun_seconds": max(now - self.deadline, 0.0),
            "actual_decoder_count": sum(self._decode_counts.values()),
            "actual_decode_seconds": self._decode_seconds, "decode_counts_by_kind": dict(self._decode_counts),
            "cost_samples": {kind: list(samples) for kind, samples in self._samples.items()},
            "cost_estimates": {kind: self.estimate(kind) for kind in self._KINDS},
            "admission_skips": dict(self._admission_skips), "action_count": self._action_count,
            "new_decisions": sum(goal.new_decisions for goal in self._goals.values()),
            "reused_decisions": sum(goal.reused_decisions for goal in self._goals.values()),
            "phase_elapsed_seconds": dict(self._phase_seconds),
            "first_complete_elapsed_seconds": (max(self._first_complete_at - self.started_at, 0.0)
                                               if self._first_complete_at is not None else None),
            "last_improvement_elapsed_seconds": max(self._last_progress_at - self.started_at, 0.0),
            "stalled_new_decisions": self._stalled_decisions,
            "stall_decision_limit": self.stall_decision_limit, "stall_seconds": self.stall_seconds,
            "auxiliary_probe_limit": self.auxiliary_probe_limit, "stop_reason": self.should_stop(at=now),
            "objective_status": {objective: data["objective_status"] for objective, data in goals.items()},
            "objectives": goals,
        }


__all__ = ["SharedSearchBudget", "SharedSearchSkip"]
