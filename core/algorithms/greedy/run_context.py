from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from core.algorithm_runtime.algo_stats import increment_counter
from core.algorithm_runtime.dispatch_callback_types import (
    AutoAssignAttemptCallback,
    ExternalScheduleCallback,
    InternalScheduleCallback,
)
from core.algorithm_runtime.internal_slot import require_internal_hours

if TYPE_CHECKING:
    from .schedule_preparation import NativeSchedulePreparation


@dataclass
class ScheduleRunContext:
    calendar: Any
    algo_stats: Any
    external_callback: ExternalScheduleCallback
    internal_callback: InternalScheduleCallback
    auto_assign_attempt_callback: AutoAssignAttemptCallback
    native_preparation: NativeSchedulePreparation
    # Per-decode SGS dispatch-key cache owned by the scheduler; None keeps every candidate re-scored.
    sgs_score_cache: Any = None

    @classmethod
    def from_legacy_scheduler(cls, scheduler: Any, preparation: NativeSchedulePreparation) -> ScheduleRunContext:
        return cls(
            calendar=scheduler.calendar,
            algo_stats=scheduler.last_algo_stats,
            external_callback=scheduler._schedule_external,
            internal_callback=scheduler._schedule_internal,
            auto_assign_attempt_callback=scheduler._auto_assign_internal_resources_attempt,
            native_preparation=preparation,
        )

    def increment(self, key: str) -> None:
        increment_counter(self.algo_stats, key)

    def schedule_external(self, *args: Any, **kwargs: Any):
        return self.external_callback(*args, **kwargs)

    def schedule_internal(self, *args: Any, **kwargs: Any):
        op = kwargs["op"]
        if op.id not in self.native_preparation.total_hours_by_op_id:
            self.native_preparation.total_hours_by_op_id[op.id] = require_internal_hours(op, kwargs["batch"])
        return self.internal_callback(*args, **kwargs)

    def auto_assign_internal_resources_attempt(self, *args: Any, **kwargs: Any):
        return self.auto_assign_attempt_callback(*args, **kwargs)

