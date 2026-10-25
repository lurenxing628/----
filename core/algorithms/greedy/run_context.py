from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from core.algorithm_runtime.algo_stats import ensure_algo_stats, increment_counter
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


@dataclass
class ScheduleRunContext:
    calendar: Any
    logger: Any
    algo_stats: Any
    external_callback: ExternalScheduleCallback
    internal_callback: InternalScheduleCallback
    auto_assign_attempt_callback: AutoAssignAttemptCallback
    # Per-decode SGS dispatch-key cache owned by the scheduler; None keeps every candidate re-scored.
    sgs_score_cache: Any = None
    native_preparation: Any = None
    native_scoring: Optional[bool] = None
    _callback_bindings: Any = field(default_factory=dict)
    # Native checkpoint dispatch adaptation is selected with this context's callbacks at preparation.
    checkpoint_dispatch_guard: Optional[Callable[[], bool]] = None

    @classmethod
    def from_legacy_scheduler(cls, scheduler: Any) -> ScheduleRunContext:
        algo_stats = ensure_algo_stats(scheduler)
        return cls(
            calendar=scheduler.calendar,
            logger=scheduler.logger,
            algo_stats=algo_stats,
            external_callback=scheduler._schedule_external,
            internal_callback=scheduler._schedule_internal,
            auto_assign_attempt_callback=scheduler._auto_assign_internal_resources_attempt,
        )

    def _check_callback(self, callback: Any, args: Any, kwargs: Any, *, slot: str) -> None:
        if slot not in self._callback_bindings:
            self._callback_bindings[slot] = dispatch_callback_binding(callback, slot=slot)
        check_dispatch_callback_binding(callback, args, kwargs, slot=slot,
                                        prepared_binding=self._callback_bindings[slot])

    def increment(self, key: str, amount: int = 1, *, bucket: str = "fallback_counts") -> None:
        increment_counter(self.algo_stats, key, amount, bucket=bucket)

    def log_exception(self, message: str) -> None:
        try:
            self.logger.exception(message)
        except Exception:
            self.increment("dispatch_exception_log_failed_count")

    def schedule_external(self, *args: Any, **kwargs: Any):
        self._check_callback(self.external_callback, args, kwargs, slot="schedule_external")
        return self.external_callback(*args, **kwargs)

    def schedule_internal(self, *args: Any, **kwargs: Any):
        call_kwargs = dict(kwargs)
        strict_mode = bool(call_kwargs.pop("strict_mode", False))
        hours = self.native_preparation.total_hours_by_op_id if self.native_preparation is not None else {}
        if "op" not in call_kwargs or getattr(call_kwargs["op"], "id", None) not in hours:
            validate_dispatch_internal_input(call_kwargs, strict_mode=strict_mode)
        self._check_callback(self.internal_callback, args, call_kwargs, slot="schedule_internal")
        return self.internal_callback(*args, **call_kwargs)

    def auto_assign_internal_resources_attempt(self, *args: Any, **kwargs: Any):
        self._check_callback(self.auto_assign_attempt_callback, args, kwargs, slot="auto_assign_internal_resources_attempt")
        return auto_assign_attempt_from_result(self.auto_assign_attempt_callback(*args, **kwargs))

