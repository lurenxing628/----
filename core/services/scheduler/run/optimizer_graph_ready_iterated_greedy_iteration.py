"""Cooperative destroy/repair iteration: yield after each trial and its required validation.

The parent context stays fixed until the iteration ends. Elapsed generator time includes only
its own tasks, so another stage's work cannot distort neighbourhood feedback.
"""
from __future__ import annotations

from typing import Any, Generator, Optional, Tuple

from .optimizer_graph_ready_iterated_greedy_contract import _BudgetExhausted
from .optimizer_graph_ready_iterated_greedy_moves import _insertion_positions, _park


class IGIteration:
    def __init__(self, search: Any) -> None:
        self.search = search
        self.elapsed = 0.0
        self.task_started: Optional[float] = None
        self.tasks = self._tasks()

    def step(self) -> bool:
        self.task_started = self.search.clock()
        try:
            next(self.tasks)
            return True
        except StopIteration:
            return False
        finally:
            self.elapsed += max(self.search.clock() - self.task_started, 0.0)
            self.task_started = None

    def close(self) -> None:
        self.tasks.close()

    def seconds(self) -> float:
        active = max(self.search.clock() - self.task_started, 0.0) if self.task_started is not None else 0.0
        return self.elapsed + active

    def _tasks(self) -> Generator[None, None, None]:
        search, report = self.search, self.search.report
        search._require_budget()
        reference = search._reference_for_iteration()
        generator = search.rotation.pick()
        before, scored_before = report["decodes"], search.scored_decodes
        search.improved_incumbent = False
        removed = generator.select(reference.order, size=generator.size(), rnd=search.rnd, features=search._features(reference))
        try:
            final = yield from self._repair(reference, removed)
            idle = final == reference.order
            entry = None if idle else search._decode_entry(final)
        except (_BudgetExhausted, GeneratorExit):
            generator.record(self.seconds(), improved=False, fully_solved=False, idle=False)
            report["interrupted_iterations"] += 1
            raise
        report["iterations"] += 1
        rejected = (report["decodes"] - before) - (search.scored_decodes - scored_before)
        generator.record(self.seconds(), improved=entry is not None and entry.score < reference.score,
                         fully_solved=rejected == 0 and (idle or entry is not None), idle=idle,
                         worse=entry is not None and entry.score > reference.score)
        search.idle_iterations = search.idle_iterations + 1 if report["decodes"] == before else 0
        if search.idle_iterations >= max(5, search.limits.stagnation_iterations * 2):
            raise _BudgetExhausted("search_space_exhausted")
        search.rejected_iterations = search.rejected_iterations + 1 if (
            report["decodes"] > before and search.scored_decodes == scored_before) else 0
        if search.rejected_iterations >= 3:
            raise _BudgetExhausted("decoder_rejections")
        search.non_improving = 0 if search.improved_incumbent else search.non_improving + 1
        if entry is not None:
            search._accept_walk(entry, reference)
        elif not idle:
            report["acceptance"]["rejected"] += 1

    def _repair(self, reference: Any, removed: Tuple[int, ...]) -> Generator[None, None, Tuple[int, ...]]:
        search, order = self.search, reference.order
        working = _park(order, set(removed), successors=search.parent.successors)
        pending = list(removed)
        search.rnd.shuffle(pending)
        for op_id in pending:
            without = [item for item in working if item != op_id]
            best_position, best_score = None, None
            for position in _insertion_positions(without, op_id, parent=search.parent, anchor=order.index(op_id),
                                                 window=search.limits.insertion_window):
                search._require_budget()
                before = search.report["decodes"]
                scored = search._score_trial(tuple(without[:position] + [op_id] + without[position:]), reference)
                if scored is not None:
                    score, feasible = scored
                    if feasible and (best_score is None or score < best_score):
                        best_position, best_score = position, score
                if search.report["decodes"] > before:
                    yield
            if best_position is not None:
                working = without[:best_position] + [op_id] + without[best_position:]
        return tuple(working)


__all__ = ["IGIteration"]
