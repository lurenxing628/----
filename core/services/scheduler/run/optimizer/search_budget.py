"""One clock and outer request deadline for the shared optimizer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


class SearchBudgetExhausted(RuntimeError):
    """The shared search cannot publish a candidate within its budget."""


@dataclass(frozen=True)
class SearchBudget:
    clock: Callable[[], float]
    started_at: float
    deadline: float
    assigned_seconds: float
