"""Short-budget diversification of large IG; preserve the verified incumbent.

OR-Tools changes LNS hints and base solutions after stalling. These wall-time
thresholds adapt that idea to a SGS run that may complete only a few tasks.
"""
from __future__ import annotations

from .optimizer_graph_ready_iterated_greedy_neighborhoods import GeneratorRotation


class LargeGeneratorRotation(GeneratorRotation):
    """Expose the active operator to its bounded multi-resource repair."""
    def __init__(self, generators):
        super().__init__(generators)
        self.selected = None

    def pick(self):
        self.selected = super().pick()
        return self.selected


class BudgetStagnation:
    def __init__(self, search):
        self.search = search
        self.last_progress = search.clock()
        self.improvements = search.report["improvements"]
        self.explore_next = False

    def reference(self):
        search, report = self.search, self.search.report["local_search"]
        now = search.clock()
        if search.non_improving == 0 or search.report["improvements"] != self.improvements:
            self.last_progress = now
            self.improvements = search.report["improvements"]
        threshold = min(search.limits.stagnation_iterations, 2)
        duration = max(search.deadline - search.started, 0.0)
        waited = now - self.last_progress
        trigger = max(2.0 * search.trial_decode_cost(), 0.15 * duration)
        if search.non_improving < threshold or waited < trigger:
            return search.reference
        reserve = search.full_decode_cost() + 2.0 * search.trial_decode_cost()
        if search.deadline - now < reserve:
            report["diversification_budget_pruned"] += 1
            return search.reference
        self.last_progress = now
        self.explore_next = True
        search.non_improving = 0
        report["diversification_requests"] += 1
        return self._restart()

    def _restart(self):
        search = self.search
        reference = search.reference
        search._seed_solution_pool()
        restart = search.solution_pool.pick(search.pool_rnd, exclude_entry=reference)
        if restart is None or restart.decision_key() == reference.decision_key():
            return reference
        search._activate_entry(restart)
        if not restart.decoded_order:
            decoded = search._decode_entry(restart.order)
            if decoded is None:
                search._activate_entry(reference)
                return reference
            restart = decoded
            search.solution_pool.refresh(restart)
        search.report["pool"]["restarts"] += 1
        search.rotation.reset_sizes()
        search.idle_iterations = search.rejected_iterations = 0
        search.reference = restart
        return restart

    def consume_exploration(self):
        explore, self.explore_next = self.explore_next, False
        return explore


def extended_positions(without, op_id, positions, parent):
    """Add distant feasible ranks when stale hints are relaxed; preserve DAG order."""
    index = {item: position for position, item in enumerate(without)}
    low = max((index[item] + 1 for item in parent.predecessors[op_id]), default=0)
    high = min((index[item] for item in parent.successors[op_id]), default=len(without))
    result = list(positions)
    for position in (low, (low + high) // 2, high):
        if position not in result:
            result.append(position)
    return result


__all__ = ["BudgetStagnation", "LargeGeneratorRotation", "extended_positions"]
