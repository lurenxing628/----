from __future__ import annotations

from typing import Callable, Optional


class GraphReadySearchBudget:
    """Graph stage deadline and shared stop reason."""

    def __init__(self, *, deadline: float, clock: Callable[[], float]) -> None:
        self.deadline = deadline
        self.clock = clock
        self.stop_reason: Optional[str] = None

    def available(self) -> bool:
        if self.stop_reason is not None:
            return False
        if self.clock() >= self.deadline:
            self.stop_reason = "time_budget"
            return False
        return True
