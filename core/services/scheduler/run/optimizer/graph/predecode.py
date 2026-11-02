from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Sequence

from core.services.scheduler.run.optimizer.graph_ready_profiles import GraphReadyWeightProfile
from core.services.scheduler.run.optimizer.shared_budget import SharedSearchSkip

from .budget import GraphReadySearchBudget


class GraphReadyProfileSearch:
    """Profile construction uses the run's shared decode admission and receipts."""

    def __init__(self, *, evaluate: Callable[..., Dict[str, Any]], budget: GraphReadySearchBudget) -> None:
        self._evaluate = evaluate
        self.budget = budget

    def can_start(self) -> bool:
        return self.budget.available()

    def evaluate(self, *, profile: GraphReadyWeightProfile, order: Sequence[str]) -> Optional[Dict[str, Any]]:
        try:
            return self._evaluate(profile=profile, order=order)
        except SharedSearchSkip as exc:
            if exc.reason in ("estimated_decode_cost", "time_budget"):
                self.budget.stop_reason = exc.reason
            return None
