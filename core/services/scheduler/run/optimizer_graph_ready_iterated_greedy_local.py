"""Bound one large IG neighbourhood independently of the overall optimizer deadline."""
from __future__ import annotations

from .optimizer_graph_ready_iterated_greedy_contract import _BudgetExhausted
from .optimizer_graph_ready_iterated_greedy_diversify import extended_positions
from .optimizer_graph_ready_iterated_greedy_iteration import IGIteration
from .optimizer_graph_ready_iterated_greedy_joint import joint_orders, joint_removed
from .optimizer_graph_ready_iterated_greedy_moves import _insertion_positions, _park
from .optimizer_graph_ready_iterated_greedy_screen import InsertionScreen

LOCAL_BUDGET_REASON = "neighborhood_time_budget"


class NeighborhoodBudget:
    def __init__(self, search, elapsed, requested_size):
        self.search, self.elapsed = search, elapsed
        remaining = max(search.deadline - search.clock(), 0.0)
        full_cost = search.full_decode_cost()
        # Reserve a full validation before choosing the first destruction size.
        available = max(remaining - full_cost, 0.0)
        trial_cost = search.trial_decode_cost()
        if full_cost > 0 and available < trial_cost:
            search.report["local_search"]["validation_room_pruned"] += 1
            search.report["local_search"]["end_budget"] = {
                "remaining_ms": remaining * 1000.0, "trial_ms": trial_cost * 1000.0,
                "full_validation_ms": full_cost * 1000.0,
            }
            raise _BudgetExhausted("decode_would_overrun")
        self.size = max(1, min(requested_size, int(available / max(trial_cost * 2, 0.001))))
        if search.report["iterations"] == 0:
            self.size = 1  # Measure a complete minimal neighbourhood before expanding it.
        # A measured trial must fit its own slice; repeatedly giving it less than
        # its known setup cost would abort every retry before useful work.
        target = max(available / 2.0, trial_cost * self.size * 1.15)
        self.seconds = min(remaining, max(0.1, min(available, target)))
        self.started_elapsed = elapsed()
        self.last_pick_check = 0

    def check(self):
        self.search._hard_budget_now()
        if self.elapsed() - self.started_elapsed >= self.seconds:
            raise _BudgetExhausted(LOCAL_BUDGET_REASON)

    def check_pick(self, position):
        if position >= self.last_pick_check:
            self.last_pick_check = position + 32
            self.check()

    def can_try(self, reserve_trials=0):
        """Do not start another trial that would consume its validation reserve."""
        trial = self.search.trial_decode_cost()
        own_left = self.seconds - (self.elapsed() - self.started_elapsed) - trial * reserve_trials
        total_left = self.search.deadline - self.search.clock() - self.search.full_decode_cost()
        return min(own_left, total_left) >= max(trial, 0.001)


class LargeIGIteration(IGIteration):
    def _repair(self, reference, removed):
        search = self.search
        budget = NeighborhoodBudget(search, self.seconds, len(removed))
        search.local_budget = budget
        report = search.report["local_search"]
        report["neighborhoods"] += 1
        report["last_budget_ms"] = int(budget.seconds * 1000)
        try:
            removed = removed[:budget.size]
            joint = search.rotation.selected.name == "resource_window" and budget.size >= 2
            if joint:
                removed = joint_removed(search, reference, removed, budget.size)
            report["last_destroy_size"] = len(removed)
            if joint:
                improved = yield from self._joint_repair(reference, removed)
                if improved is not None:
                    return improved
            return (yield from self._screened_repair(reference, removed))
        finally:
            search.local_budget = None

    def _joint_repair(self, reference, removed):
        search, report = self.search, self.search.report["local_search"]
        for order in joint_orders(search, reference, removed):
            if not search.local_budget.can_try():
                report["queue_budget_stops"] += 1
                break
            if order in search.scores:
                continue
            report["joint_candidates"] += 1
            before = search.report["decodes"]
            scored = search._score_trial(order, reference)
            if search.report["decodes"] > before:
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
        for op_id in pending:
            self.pending_insertions -= 1
            working = yield from self._insert(screen, reference, working, op_id, explore)
        final = tuple(working)
        known = search.scores.get(final)
        # A different, non-improving walk reference is useful only if there is
        # time to validate it and search from it. Keep the verified reference
        # when that last full decode would consume the remaining search window.
        reserve = search.full_decode_cost() + 2.0 * search.trial_decode_cost()
        if (explore and final == reference.order and self.walk is not None
                and search.deadline - search.clock() >= reserve):
            search.report["local_search"]["exploratory_walks"] += 1
            return self.walk[1]
        if (known is not None and known[0] >= reference.score
                and search.deadline - search.clock() < reserve):
            search.report["local_search"]["reference_changes_deferred"] += int(final != reference.order)
            return reference.order
        return final

    def _insert(self, screen, reference, working, op_id, explore):
        search, report = self.search, self.search.report["local_search"]
        without = [item for item in working if item != op_id]
        anchor = reference.order.index(op_id)
        positions = _insertion_positions(without, op_id, parent=search.parent, anchor=anchor,
                                         window=search.limits.insertion_window)
        if explore:
            positions = extended_positions(without, op_id, positions, search.parent)
        queue = screen.ranked_positions(without, op_id, positions, anchor=anchor, diversify=explore)
        best_position, best_score = _best_cached(search, without, op_id, positions)
        # Leave time for another generator as well as the complete validation.
        # Unlike fixed Top 1, a rejection/non-improvement can advance the queue.
        for index, position in enumerate(queue[:3]):
            if not search.local_budget.can_try(self.pending_insertions if index else 0):
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
            if search.report["decodes"] > before:
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


def _best_cached(search, without, op_id, positions):
    best_position, best_score = None, None
    for position in positions:
        known = search.scores.get(tuple(without[:position] + [op_id] + without[position:]))
        if known is not None and known[1] and (best_score is None or known[0] < best_score):
            best_position, best_score = position, known[0]
    return best_position, best_score


__all__ = ["LOCAL_BUDGET_REASON", "LargeIGIteration", "NeighborhoodBudget"]
