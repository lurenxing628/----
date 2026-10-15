"""Screened IG with exact suffix reuse for large operation orders.

The common decode session admits actual requests. The search keeps its bounded
insertion queues, exact tail reuse and verified incumbents.
"""

from typing import Optional

from .iterated_greedy import _BudgetExhausted, _IteratedGreedySearch
from .iterated_greedy_diversify import BudgetStagnation, LargeGeneratorRotation
from .iterated_greedy_local import LargeIGIteration, NeighborhoodBudget
from .iterated_greedy_tail import TailCheckpointStore, trial_request

LARGE_ORDER_MINIMUM = 128


def search_type_for(parent):
    return LargeIteratedGreedySearch if len(parent.order) >= LARGE_ORDER_MINIMUM else _IteratedGreedySearch


def iteration_for(search, original):
    return LargeIGIteration(search) if isinstance(search, LargeIteratedGreedySearch) else original(search)


class LargeIteratedGreedySearch(_IteratedGreedySearch):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.local_budget: Optional[NeighborhoodBudget] = None
        self._trial_reference = None
        self._active_tail = None
        self.checkpoints = TailCheckpointStore(self.limits.checkpoint_count)
        self.report["algorithm"] = "operation_destroy_queued_joint_insertion_v5"
        self.report["partial_evaluation"] = "checkpoint_prefix_and_reconverged_tail_exact"
        for generator in self.generators:
            generator.completion_feedback = True
        self.report["local_search"] = {
            "policy": "screened_insertion_shared_admission_v1",
            "difficulty_feedback": "bounded_task_completion",
            "neighborhoods": 0,
            "local_timeouts": 0, "interrupted_decodes": 0, "screened_positions": 0,
            "shortlisted_positions": 0, "tail_checks": 0, "tail_reused_picks": 0,
            "tail_reused_decodes": 0, "last_budget_ms": 0, "last_destroy_size": 0,
            "reference_changes_deferred": 0,
            "validation_room_pruned": 0,
            "queue_continuations": 0, "queue_budget_stops": 0, "queue_exhausted": 0,
            "diversification_requests": 0, "diversification_budget_pruned": 0,
            "exploratory_walks": 0, "joint_candidates": 0, "joint_improvements": 0,
            "tail_bulk_installs": 0,
        }
        self.diversification = BudgetStagnation(self)
        self.rotation = LargeGeneratorRotation(self.generators)

    def _reference_for_iteration(self):
        return self.diversification.reference()

    def _score_trial(self, order, reference):
        previous = self._trial_reference
        self._trial_reference = reference
        try:
            return super()._score_trial(order, reference)
        finally:
            self._trial_reference = previous

    def _decode_entry(self, order, *, redecode_reason=None):
        budget, reference = self.local_budget, self._trial_reference
        self.local_budget, self._trial_reference = None, None
        try:
            return super()._decode_entry(order, redecode_reason=redecode_reason)
        finally:
            self.local_budget, self._trial_reference = budget, reference

    def _decode(self, order, *, resume=None, checkpoints=None, redecode_reason=None):
        previous_tail = self._active_tail
        trial = self._trial_reference is not None and checkpoints is None
        if trial and self.checkpoints.enabled:
            checkpoints = trial_request(self._trial_reference, resume=resume)
        self._active_tail = getattr(checkpoints, "tail_reuse", None)
        before = self.report["decodes"]
        try:
            result = super()._decode(order, resume=resume, checkpoints=checkpoints, redecode_reason=redecode_reason)
            if trial and result is not None:
                self._record_tail()
            return result
        except _BudgetExhausted:
            if self.report["decodes"] > before:
                self.report["local_search"]["interrupted_decodes"] += 1
            raise
        finally:
            self._active_tail = previous_tail

    def _record_tail(self):
        if self._active_tail is None:
            return
        report = self.report["local_search"]
        report["tail_checks"] += self._active_tail.checks
        report["tail_reused_picks"] += self._active_tail.reused_picks
        report["tail_reused_decodes"] += int(self._active_tail.reused_picks > 0)
        report["tail_bulk_installs"] += self._active_tail.bulk_installs
        report["last_tail_reason"] = self._active_tail.reason
