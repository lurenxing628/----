"""Bound large IG neighbourhood enumeration under common decode admission."""
from __future__ import annotations

from typing import TYPE_CHECKING

from .iterated_greedy_iteration import IGIteration
from .iterated_greedy_joint import joint_orders, joint_removed
from .iterated_greedy_moves import _insertion_positions, _park
from .iterated_greedy_screen import InsertionScreen

if TYPE_CHECKING:
    from .iterated_greedy_large import LargeIteratedGreedySearch


class NeighborhoodBudget:
    def __init__(self, search: LargeIteratedGreedySearch, requested_size):
        self.search = search
        self.size = max(1, requested_size)
        self.seconds = max(search.deadline - search.clock(), 0.0)

    def can_try(self):
        """Check the deadline and decode cap before adding an insertion trial."""
        return (self.search.clock() < self.search.deadline
                and self.search.report["decodes"] < self.search.limits.max_decodes)


class LargeIGIteration(IGIteration):
    search: LargeIteratedGreedySearch

    def _repair(self, reference, removed):
        search = self.search
        budget = NeighborhoodBudget(search, len(removed))
        self.local_budget = budget
        report = search.report["local_search"]
        report["neighborhoods"] += 1
        report["last_budget_ms"] = int(budget.seconds * 1000)
        selected = search.rotation.selected
        joint = selected is not None and selected.name == "resource_window" and budget.size >= 2
        if joint:
            removed = joint_removed(search, reference, removed, budget.size)
        report["last_destroy_size"] = len(removed)
        if joint:
            improved = yield from self._joint_repair(reference, removed)
            if improved is not None:
                return improved
        return (yield from self._screened_repair(reference, removed))

    def _joint_repair(self, reference, removed):
        search, report = self.search, self.search.report["local_search"]
        for order in joint_orders(search, reference, removed):
            if not self.local_budget.can_try():
                report["queue_budget_stops"] += 1
                break
            if order in search.scores:
                search._record_local_reuse("local_trial_reused")
                continue
            report["joint_candidates"] += 1
            before = search.report["decodes"]
            scored = search._score_trial(order, reference)
            if search.report["decodes"] > before or search.last_decode_skip is not None:
                yield
            if scored is not None and scored[1] and scored[0] < reference.score:
                report["joint_improvements"] += 1
                return order
        return None

    def _screened_repair(self, reference, removed):
        search, order = self.search, reference.order
        screen = InsertionScreen(search, reference)
        explore = search.diversification.consume_exploration()
        self.walk = None
        working = _park(order, set(removed), successors=search.parent.successors)
        pending = list(removed)
        search.rnd.shuffle(pending)
        self.pending_insertions = len(pending)
        anchors = {op_id: idx for idx, op_id in enumerate(order)}
        for op_id in pending:
            self.pending_insertions -= 1
            working = yield from self._insert(screen, reference, working, op_id, explore, anchor=anchors[op_id])
        final = tuple(working)
        if explore and final == reference.order and self.walk is not None:
            search.report["local_search"]["exploratory_walks"] += 1
            return self.walk[1]
        return final

    def _insert(self, screen, reference, working, op_id, explore, *, anchor):
        search, report = self.search, self.search.report["local_search"]
        without = [item for item in working if item != op_id]
        positions = _insertion_positions(without, op_id, parent=search.parent, anchor=anchor,
                                         window=search.limits.insertion_window, explore=explore)
        queue, best_position, best_score = screen.ranked_positions(
            without, op_id, positions, anchor=anchor, diversify=explore)
        # A rejection or non-improvement can advance the bounded queue.
        for index, position in enumerate(queue[:3]):
            if not self.local_budget.can_try():
                report["queue_budget_stops"] += 1
                break
            report["queue_continuations"] += int(index > 0)
            report["shortlisted_positions"] += 1
            search._require_budget()
            trial = tuple(without[:position] + [op_id] + without[position:])
            before = search.report["decodes"]
            scored = self._score_position(trial, reference)
            if scored is not None and scored[1]:
                score = scored[0]
                if best_score is None or score < best_score:
                    best_position, best_score = position, score
            if search.report["decodes"] > before or search.last_decode_skip is not None:
                yield
            if self._position_finished(scored, best_score, reference, explore):
                break
        else:
            report["queue_exhausted"] += int(len(queue) <= 3)
        return working if best_position is None else without[:best_position] + [op_id] + without[best_position:]

    def _score_position(self, trial, reference):
        scored = self.search._score_trial(trial, reference)
        if scored is not None and scored[1]:
            if self.walk is None or scored[0] < self.walk[0]:
                self.walk = (scored[0], trial)
        return scored

    def _position_finished(self, scored, best_score, reference, explore):
        if best_score is not None and best_score < reference.score:
            return True
        # An unfinished destroy/repair can look worse simply because other
        # removed operations are still parked. Complete its first pass before
        # spending extra trials on a feasible position, unless diversifying.
        return (not explore and self.pending_insertions > 0
                and scored is not None and scored[1])


__all__ = ["LargeIGIteration", "NeighborhoodBudget"]
