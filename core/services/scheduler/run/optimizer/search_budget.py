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
    outer_deadline: float
    assigned_seconds: float

    def optimizer_deadline(self, *, started_at: float, configured_seconds: int, improve: bool) -> float:
        configured_deadline = started_at + float(configured_seconds) if improve else float("inf")
        return min(self.deadline, configured_deadline)
