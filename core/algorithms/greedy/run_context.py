from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from .algo_stats import ensure_algo_stats, increment_counter
from .auto_assign import auto_assign_internal_resources
from .external_groups import schedule_external
from .internal_operation import schedule_internal_operation
from .internal_slot import validate_internal_hours_for_mode


@dataclass
class ScheduleRunContext:
    calendar: Any
    logger: Any
    algo_stats: Any
    external_callback: Optional[Callable[..., Any]] = None
    internal_callback: Optional[Callable[..., Any]] = None
    auto_assign_callback: Optional[Callable[..., Any]] = None

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
        )

    def increment(self, key: str, amount: int = 1, *, bucket: str = "fallback_counts") -> None:
        increment_counter(self.algo_stats, key, amount, bucket=bucket)

    def log_exception(self, message: str) -> None:
        try:
            self.logger.exception(message)
        except Exception:
            pass

    def schedule_external(self, *args: Any, **kwargs: Any):
        if callable(self.external_callback):
            return self.external_callback(*args, **kwargs)
        call_kwargs = dict(kwargs)
        return schedule_external(_ScheduleFacade(self.calendar, self.algo_stats), *args, **call_kwargs)

    def schedule_internal(self, *args: Any, **kwargs: Any):
        call_kwargs = dict(kwargs)
        strict_mode = bool(call_kwargs.pop("strict_mode", False))
        _validate_strict_internal_input(call_kwargs, strict_mode=strict_mode)
        if callable(self.internal_callback):
            return self.internal_callback(*args, **call_kwargs)
        call_kwargs.setdefault("calendar", self.calendar)
        call_kwargs.setdefault("algo_stats", self.algo_stats)
        call_kwargs.setdefault("auto_assign_resources", self.auto_assign_internal_resources)
        call_kwargs["strict_mode"] = strict_mode
        return schedule_internal_operation(
            *args,
            **call_kwargs,
        )

    def auto_assign_internal_resources(self, *args: Any, **kwargs: Any):
        if callable(self.auto_assign_callback):
            return self.auto_assign_callback(*args, **kwargs)
        call_kwargs = dict(kwargs)
        call_kwargs.setdefault("calendar", self.calendar)
        call_kwargs.setdefault("algo_stats", self.algo_stats)
        return auto_assign_internal_resources(*args, **call_kwargs)


def ensure_run_context(candidate: Any) -> ScheduleRunContext:
    if isinstance(candidate, ScheduleRunContext):
        return candidate
    return ScheduleRunContext.from_legacy_scheduler(candidate)


def _validate_strict_internal_input(call_kwargs: dict, *, strict_mode: bool) -> None:
    if not strict_mode:
        return
    validate_internal_hours_for_mode(call_kwargs["op"], call_kwargs["batch"], strict_mode=True)


class _ScheduleFacade:
    def __init__(self, calendar: Any, algo_stats: Any) -> None:
        self.calendar = calendar
        self._last_algo_stats = algo_stats
