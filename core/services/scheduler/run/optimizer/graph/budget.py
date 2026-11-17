from __future__ import annotations

from typing import Optional

from core.services.scheduler.run.optimizer.shared_budget import SharedSearchBudget


class GraphReadySearchBudget:
    """The graph stages' shared stop reason; clock and deadline are the run budget's (``shared``)."""

    def __init__(self, shared: SharedSearchBudget) -> None:
        self.shared = shared
        self.stop_reason: Optional[str] = None

    def available(self) -> bool:
        if self.stop_reason is not None:
            return False
        if self.shared.clock() >= self.shared.deadline:
            self.stop_reason = "time_budget"
            return False
        return True
