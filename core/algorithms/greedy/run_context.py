from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Optional

from core.algorithm_runtime.algo_stats import increment_counter
from core.algorithm_runtime.auto_assign_contract import auto_assign_attempt_from_result
from core.algorithm_runtime.dispatch_callback_types import (
    AutoAssignAttemptCallback,
    ExternalScheduleCallback,
    InternalScheduleCallback,
)
from core.algorithm_runtime.dispatch_context import (
    check_dispatch_callback_binding,
    dispatch_callback_binding,
    validate_dispatch_internal_input,
)

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
    native_scoring: bool
    # Per-decode SGS dispatch-key cache owned by the scheduler; None keeps every candidate re-scored.
    sgs_score_cache: Any = None
    _callback_bindings: Any = field(default_factory=dict)
    # Native checkpoint dispatch adaptation is selected with this context's callbacks at preparation.
    checkpoint_dispatch_guard: Optional[Callable[[], bool]] = None

    @classmethod
    def from_legacy_scheduler(cls, scheduler: Any, preparation: NativeSchedulePreparation, *,
                              native_scoring: bool) -> ScheduleRunContext:
        return cls(
            calendar=scheduler.calendar,
            algo_stats=scheduler.last_algo_stats,
            external_callback=scheduler._schedule_external,
            internal_callback=scheduler._schedule_internal,
            auto_assign_attempt_callback=scheduler._auto_assign_internal_resources_attempt,
            native_preparation=preparation,
            native_scoring=native_scoring,
        )

    def _check_callback(self, callback: Any, args: Any, kwargs: Any, *, slot: str) -> None:
        if slot not in self._callback_bindings:
            self._callback_bindings[slot] = dispatch_callback_binding(callback)
        check_dispatch_callback_binding(self._callback_bindings[slot], args, kwargs, slot=slot)

    def increment(self, key: str) -> None:
        increment_counter(self.algo_stats, key)

    def schedule_external(self, *args: Any, **kwargs: Any):
        self._check_callback(self.external_callback, args, kwargs, slot="schedule_external")
        return self.external_callback(*args, **kwargs)

    def schedule_internal(self, *args: Any, **kwargs: Any):
        if "op" not in kwargs or kwargs["op"].id not in self.native_preparation.total_hours_by_op_id:
            validate_dispatch_internal_input(kwargs)
        self._check_callback(self.internal_callback, args, kwargs, slot="schedule_internal")
        return self.internal_callback(*args, **kwargs)

    def auto_assign_internal_resources_attempt(self, *args: Any, **kwargs: Any):
        self._check_callback(self.auto_assign_attempt_callback, args, kwargs, slot="auto_assign_internal_resources_attempt")
        return auto_assign_attempt_from_result(self.auto_assign_attempt_callback(*args, **kwargs))

