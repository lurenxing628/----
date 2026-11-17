"""The request budget the shared optimizer receives: the run's clock and outer deadline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


class SearchBudgetExhausted(RuntimeError):
    """The shared search cannot publish a candidate within its budget."""


@dataclass(frozen=True)
class SearchBudget:
    """``clock`` is the run's monotonic clock (``SolverResources.clock``); the shared search budget owns it
    once the search opens. ``deadline`` is read on that clock."""

    clock: Callable[[], float]
    deadline: float
    assigned_seconds: float
