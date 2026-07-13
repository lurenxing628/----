from __future__ import annotations

from typing import Any

from core.algorithm_runtime.algo_stats import ensure_algo_stats, increment_counter
from core.algorithm_runtime.auto_assign_contract import auto_assign_attempt_from_result


class _LegacyDispatchContext:
    def __init__(self, candidate: Any) -> None:
        self._candidate = candidate
        self.calendar = getattr(candidate, "calendar", None)
        if self.calendar is None:
            self.calendar = getattr(candidate, "calendar_service", None)
        self.logger: Any = getattr(candidate, "logger", None)
        self.algo_stats = ensure_algo_stats(candidate)

    def increment(self, key: str, amount: int = 1, *, bucket: str = "fallback_counts") -> None:
        increment_counter(self.algo_stats, key, amount, bucket=bucket)

    def log_exception(self, message: str) -> None:
        try:
            self.logger.exception(message)
        except Exception:
            self.increment("dispatch_exception_log_failed_count")

    def schedule_external(self, *args: Any, **kwargs: Any):
        callback = getattr(self._candidate, "_schedule_external", None)
        if not callable(callback):
            raise TypeError("legacy dispatch context does not provide _schedule_external")
        return callback(*args, **kwargs)

    def schedule_internal(self, *args: Any, **kwargs: Any):
        callback = getattr(self._candidate, "_schedule_internal", None)
        if not callable(callback):
            raise TypeError("legacy dispatch context does not provide _schedule_internal")
        call_kwargs = dict(kwargs)
        call_kwargs.pop("strict_mode", None)
        return callback(*args, **call_kwargs)

    def auto_assign_internal_resources_attempt(self, *args: Any, **kwargs: Any):
        callback = getattr(self._candidate, "_auto_assign_internal_resources_attempt", None)
        if callable(callback):
            return auto_assign_attempt_from_result(callback(*args, **kwargs))
        callback = getattr(self._candidate, "_auto_assign_internal_resources", None)
        if callable(callback):
            return auto_assign_attempt_from_result(callback(*args, **kwargs))
        raise TypeError("legacy dispatch context does not provide auto-assign callback")

    def auto_assign_internal_resources(self, *args: Any, **kwargs: Any):
        attempt = self.auto_assign_internal_resources_attempt(*args, **kwargs)
        if attempt.machine_id and attempt.operator_id:
            return attempt.machine_id, attempt.operator_id
        return None


def ensure_dispatch_context(candidate: Any) -> Any:
    required = ("schedule_external", "schedule_internal", "auto_assign_internal_resources_attempt", "increment", "log_exception")
    if all(callable(getattr(candidate, name, None)) for name in required):
        return candidate
    return _LegacyDispatchContext(candidate)
