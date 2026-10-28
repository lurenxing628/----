"""Short-budget diversification of large IG; preserve the verified incumbent.

OR-Tools changes LNS hints and base solutions after stalling. These wall-time
thresholds adapt that idea to a SGS run that may complete only a few tasks.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .iterated_greedy_neighborhoods import GeneratorRotation
from .iterated_greedy_reference import restart_from_pool

if TYPE_CHECKING:
    from .iterated_greedy_large import LargeIteratedGreedySearch


class LargeGeneratorRotation(GeneratorRotation):
    """Expose the active operator to its bounded multi-resource repair."""
    def __init__(self, generators):
        super().__init__(generators)
        self.selected = None

    def pick(self):
        self.selected = super().pick()
        return self.selected


class BudgetStagnation:
    def __init__(self, search: LargeIteratedGreedySearch):
        self.search = search
        self.last_progress = search.clock()
        self.improvements = search.report["improvements"]
        self.explore_next = False

    def reference(self):
        search, report = self.search, self.search.report["local_search"]
        reference = search.reference
        if reference is None:
            raise RuntimeError("Iterated greedy iteration started without a reference solution.")
        now = search.clock()
        if search.non_improving == 0 or search.report["improvements"] != self.improvements:
            self.last_progress = now
            self.improvements = search.report["improvements"]
        threshold = min(search.limits.stagnation_iterations, 2)
        duration = max(search.deadline - search.started, 0.0)
        waited = now - self.last_progress
        trigger = 0.15 * duration
        if search.non_improving < threshold or waited < trigger:
            return reference
        self.last_progress = now
        self.explore_next = True
        search.non_improving = 0
        report["diversification_requests"] += 1
        return restart_from_pool(search, reference)

    def consume_exploration(self):
        explore, self.explore_next = self.explore_next, False
        return explore


__all__ = ["BudgetStagnation", "LargeGeneratorRotation"]
