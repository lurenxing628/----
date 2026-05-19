from __future__ import annotations

from importlib import import_module
from typing import Any, List

__all__ = ["ScheduleOrchestrationOutcome", "orchestrate_schedule_run"]  # noqa: F822

_TARGET_MODULE = "core.services.scheduler.run.schedule_orchestrator"


def __getattr__(name: str) -> Any:
    if name in __all__:
        return getattr(import_module(_TARGET_MODULE), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> List[str]:
    return sorted(set(globals()).union(__all__))
