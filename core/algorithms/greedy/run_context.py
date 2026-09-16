from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from core.algorithm_runtime.algo_stats import ensure_algo_stats, increment_counter
from core.algorithm_runtime.auto_assign_contract import auto_assign_attempt_from_result
from core.algorithm_runtime.dispatch_callback_types import (
    AutoAssignAttemptCallback,
    AutoAssignCallback,
    ExternalScheduleCallback,
    InternalScheduleCallback,
)
from core.algorithm_runtime.dispatch_context import check_dispatch_callback_binding, validate_dispatch_internal_input

from .auto_assign import auto_assign_internal_resources_attempt
from .external_groups import schedule_external
from .internal_operation import schedule_internal_operation


@dataclass
class ScheduleRunContext:
    calendar: Any
    logger: Any
    algo_stats: Any
    external_callback: Optional[ExternalScheduleCallback] = None
    internal_callback: Optional[InternalScheduleCallback] = None
    auto_assign_callback: Optional[AutoAssignCallback] = None
    auto_assign_attempt_callback: Optional[AutoAssignAttemptCallback] = None
    # Per-decode SGS dispatch-key cache owned by the scheduler; None keeps every candidate re-scored.
    sgs_score_cache: Any = None
    # Certificate that dispatch still runs the native scheduler/context/internal-operation code;
    # the scheduler arms it only for tail-reuse decodes, so it stays None everywhere else.
    checkpoint_dispatch_guard: Optional[Callable[[], bool]] = None

    @classmethod
    def from_legacy_scheduler(cls, scheduler: Any) -> ScheduleRunContext:
        algo_stats = ensure_algo_stats(scheduler)
        return cls(
            calendar=getattr(scheduler, "calendar", None),
            logger=getattr(scheduler, "logger", None),
            algo_stats=algo_stats,
            external_callback=getattr(scheduler, "_schedule_external", None),
            internal_callback=getattr(scheduler, "_schedule_internal", None),
            auto_assign_callback=getattr(scheduler, "_auto_assign_internal_resources", None),
            auto_assign_attempt_callback=getattr(scheduler, "_auto_assign_internal_resources_attempt", None),
        )

    def increment(self, key: str, amount: int = 1, *, bucket: str = "fallback_counts") -> None:
        increment_counter(self.algo_stats, key, amount, bucket=bucket)

    def log_exception(self, message: str) -> None:
        try:
            self.logger.exception(message)
        except Exception:
            self.increment("dispatch_exception_log_failed_count")

    def schedule_external(self, *args: Any, **kwargs: Any):
        if callable(self.external_callback):
            check_dispatch_callback_binding(self.external_callback, args, kwargs, slot="schedule_external")
            return self.external_callback(*args, **kwargs)
        call_kwargs = dict(kwargs)
        facade = _ScheduleFacade(self.calendar, self.algo_stats)
        check_dispatch_callback_binding(schedule_external, (facade,) + args, call_kwargs, slot="schedule_external fallback")
        return schedule_external(facade, *args, **call_kwargs)

    def schedule_internal(self, *args: Any, **kwargs: Any):
        call_kwargs = dict(kwargs)
        strict_mode = bool(call_kwargs.pop("strict_mode", False))
        _validate_strict_internal_input(call_kwargs, strict_mode=strict_mode)
        if callable(self.internal_callback):
            check_dispatch_callback_binding(self.internal_callback, args, call_kwargs, slot="schedule_internal")
            return self.internal_callback(*args, **call_kwargs)
        call_kwargs.setdefault("calendar", self.calendar)
        call_kwargs.setdefault("algo_stats", self.algo_stats)
        call_kwargs.setdefault("auto_assign_resources", self.auto_assign_internal_resources_attempt)
        call_kwargs["strict_mode"] = strict_mode
        check_dispatch_callback_binding(schedule_internal_operation, args, call_kwargs, slot="schedule_internal fallback")
        return schedule_internal_operation(
            *args,
            **call_kwargs,
        )

    def auto_assign_internal_resources(self, *args: Any, **kwargs: Any):
        if callable(self.auto_assign_callback):
            check_dispatch_callback_binding(self.auto_assign_callback, args, kwargs, slot="auto_assign_internal_resources")
            return self.auto_assign_callback(*args, **kwargs)
        attempt = self.auto_assign_internal_resources_attempt(*args, **kwargs)
        if attempt.machine_id and attempt.operator_id:
            return attempt.machine_id, attempt.operator_id
        return None

    def auto_assign_internal_resources_attempt(self, *args: Any, **kwargs: Any):
        if callable(self.auto_assign_attempt_callback):
            check_dispatch_callback_binding(self.auto_assign_attempt_callback, args, kwargs, slot="auto_assign_internal_resources_attempt")
            return auto_assign_attempt_from_result(self.auto_assign_attempt_callback(*args, **kwargs))
        if callable(self.auto_assign_callback):
            check_dispatch_callback_binding(self.auto_assign_callback, args, kwargs, slot="auto_assign_internal_resources")
            return auto_assign_attempt_from_result(self.auto_assign_callback(*args, **kwargs))
        call_kwargs = dict(kwargs)
        call_kwargs.setdefault("calendar", self.calendar)
        call_kwargs.setdefault("algo_stats", self.algo_stats)
        check_dispatch_callback_binding(auto_assign_internal_resources_attempt, args, call_kwargs, slot="auto_assign_internal_resources_attempt fallback")
        return auto_assign_internal_resources_attempt(*args, **call_kwargs)


def ensure_run_context(candidate: Any) -> ScheduleRunContext:
    if isinstance(candidate, ScheduleRunContext):
        return candidate
    return ScheduleRunContext.from_legacy_scheduler(candidate)


def _validate_strict_internal_input(call_kwargs: dict, *, strict_mode: bool) -> None:
    validate_dispatch_internal_input(call_kwargs, strict_mode=strict_mode)


class _ScheduleFacade:
    def __init__(self, calendar: Any, algo_stats: Any) -> None:
        self.calendar = calendar
        self._last_algo_stats = algo_stats
