"""Time-balanced stage tasks with bounded feedback from strict incumbent improvements.

The availability/lowest-score loop follows OR-Tools' SubSolver structure; the feedback policy is
local to APS. Each available stage gets one task opportunity before a tried stage runs again.
After that, a recent improvement rate can discount charged time by at most a factor of 1.25.
The positive task charge prevents zero-duration work from starving other stages. Wall time is
reported separately and never padded. Tasks are cooperative: a deadline cannot preempt a task.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Callable, Deque, Dict, Optional, Sequence, Tuple

ROTATION_POLICY = "time_equalized_feedback_v2"
_MIN_TASK_SECONDS = 0.001
_RECENT_TASKS = 8
_MAX_FEEDBACK_BONUS = 0.25


class SearchStage:
    """One strategy of the graph phase, split into resumable units of work."""

    name = ""

    def available(self) -> bool:
        raise NotImplementedError

    def run_task(self) -> int:
        """Run one resumable task and return its strict incumbent improvement event count."""
        raise NotImplementedError

    def unavailable_reason(self) -> Optional[str]:
        """Explain why this stage cannot currently start; None means it can start."""
        return None if self.available() else "no_available_task"

    def finish(self) -> None:
        """Publish the stage report once the rotation ended (also when the stage never ran)."""
        raise NotImplementedError


class StageScheduler:
    def __init__(self, stages: Sequence[SearchStage], *, clock: Callable[[], float], deadline: float) -> None:
        if not stages:
            raise ValueError("at least one search stage is required")
        names = [stage.name for stage in stages]
        if len(set(names)) != len(names) or not all(names):
            raise ValueError("search stages need distinct non-empty names")
        self.stages = list(stages)
        self.clock = clock
        self.deadline = deadline
        self.seconds: Dict[str, float] = {name: 0.0 for name in names}
        self.charged_seconds: Dict[str, float] = {name: 0.0 for name in names}
        self.tasks: Dict[str, int] = {name: 0 for name in names}
        self.improvements: Dict[str, int] = {name: 0 for name in names}
        self.recent: Dict[str, Deque[Tuple[float, int]]] = {name: deque(maxlen=_RECENT_TASKS) for name in names}
        self.switches = 0
        self.stop_reason: Optional[str] = None
        self._last: Optional[SearchStage] = None

    def recent_rate(self, stage: SearchStage) -> float:
        measured = [(seconds, events) for seconds, events in self.recent[stage.name] if seconds > 0]
        seconds = sum(item[0] for item in measured)
        return sum(item[1] for item in measured) / seconds if seconds else 0.0

    def score(self, stage: SearchStage, *, best_rate: float) -> float:
        bonus = _MAX_FEEDBACK_BONUS * self.recent_rate(stage) / best_rate if best_rate > 0 else 0.0
        return self.charged_seconds[stage.name] / (1.0 + bonus)

    def pick(self) -> Optional[SearchStage]:
        available = [stage for stage in self.stages if stage.available()]
        if not available:
            return None
        # A stage that becomes available later still receives its first opportunity immediately.
        for stage in available:
            if self.tasks[stage.name] == 0:
                return stage
        best_rate = max(self.recent_rate(stage) for stage in available)
        # min() retains configured order on equal scores, including zero measured clock samples.
        return min(available, key=lambda stage: self.score(stage, best_rate=best_rate))

    def run(self) -> None:
        try:
            while True:
                if self.clock() >= self.deadline:
                    self.stop_reason = "time_budget"
                    break
                stage = self.pick()
                if self.clock() >= self.deadline:
                    self.stop_reason = "time_budget"
                    break
                if stage is None:
                    self.stop_reason = "stages_exhausted"
                    break
                if self._last is not None and stage is not self._last:
                    self.switches += 1
                self._last = stage
                started = self.clock()
                events = stage.run_task()
                elapsed = max(self.clock() - started, 0.0)
                if isinstance(events, bool) or not isinstance(events, int) or events < 0:
                    raise ValueError("search stage must return a nonnegative strict improvement event count")
                self.seconds[stage.name] += elapsed
                self.charged_seconds[stage.name] += max(elapsed, _MIN_TASK_SECONDS)
                self.tasks[stage.name] += 1
                self.improvements[stage.name] += events
                self.recent[stage.name].append((elapsed, events))
        finally:
            for stage in self.stages:
                stage.finish()

    def summary(self) -> Dict[str, Any]:
        return {
            "rotation_policy": ROTATION_POLICY,
            "rotation_stop_reason": self.stop_reason,
            "stage_order": [stage.name for stage in self.stages],
            "stage_time_ms": {name: int(seconds * 1000) for name, seconds in self.seconds.items()},
            "stage_charged_time_ms": {name: int(seconds * 1000) for name, seconds in self.charged_seconds.items()},
            "stage_tasks": dict(self.tasks),
            "stage_strict_improvements": dict(self.improvements),
            "stage_recent_improvements_per_second": {stage.name: self.recent_rate(stage) for stage in self.stages},
            "stage_startup": {stage.name: self._startup_status(stage) for stage in self.stages},
            "startup_min_tasks": 1, "feedback_recent_tasks": _RECENT_TASKS,
            "feedback_max_bonus": _MAX_FEEDBACK_BONUS, "minimum_task_charge_ms": _MIN_TASK_SECONDS * 1000,
            "feedback_rate_scope": "strict_incumbent_events_from_positive_duration_tasks",
            "stage_switches": self.switches,
        }

    def _startup_status(self, stage: SearchStage) -> Dict[str, Any]:
        if self.tasks[stage.name]:
            return {"status": "task_started", "reason": None}
        reason = stage.unavailable_reason()
        if reason is None:
            reason = self.stop_reason or "rotation_not_started"
        return {"status": "skipped", "reason": reason}


__all__ = ["ROTATION_POLICY", "SearchStage", "StageScheduler"]
