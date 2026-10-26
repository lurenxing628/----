"""Screened IG with exact suffix reuse for large operation orders.

The common decode session admits actual requests. The search keeps its bounded
insertion queues, exact tail reuse and verified incumbents.
"""

from .iterated_greedy import _IteratedGreedySearch
from .iterated_greedy_diversify import BudgetStagnation, LargeGeneratorRotation
from .iterated_greedy_iteration import IGIteration
from .iterated_greedy_local import LargeIGIteration
from .iterated_greedy_tail import TailCheckpointStore, trial_request

LARGE_ORDER_MINIMUM = 128


def search_type_for(parent):
    return LargeIteratedGreedySearch if len(parent.order) >= LARGE_ORDER_MINIMUM else _IteratedGreedySearch


def iteration_for(search):
    return LargeIGIteration(search) if isinstance(search, LargeIteratedGreedySearch) else IGIteration(search)


class LargeIteratedGreedySearch(_IteratedGreedySearch):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.checkpoints = TailCheckpointStore(self.limits.checkpoint_count)
        self.report["algorithm"] = "operation_destroy_queued_joint_insertion_v5"
        self.report["partial_evaluation"] = "checkpoint_prefix_and_reconverged_tail_exact"
        for generator in self.generators:
            generator.completion_feedback = True
        self.report["local_search"] = {
            "policy": "screened_insertion_shared_admission_v1",
            "difficulty_feedback": "bounded_task_completion",
            "neighborhoods": 0,
            "screened_positions": 0,
            "shortlisted_positions": 0, "tail_checks": 0, "tail_reused_picks": 0,
            "tail_reused_decodes": 0, "last_budget_ms": 0, "last_destroy_size": 0,
            "queue_continuations": 0, "queue_budget_stops": 0, "queue_exhausted": 0,
            "diversification_requests": 0,
            "exploratory_walks": 0, "joint_candidates": 0, "joint_improvements": 0,
            "tail_bulk_installs": 0,
        }
        self.diversification = BudgetStagnation(self)
        self.rotation = LargeGeneratorRotation(self.generators)

    def _reference_for_iteration(self):
        return self.diversification.reference()

    def _decode_trial(self, order, *, resume, reference):
        checkpoints = trial_request(reference, resume=resume) if self.checkpoints.enabled else None
        tail = checkpoints.tail_reuse if checkpoints is not None else None
        result = self._decode(order, resume=resume, checkpoints=checkpoints)
        if result is not None:
            self._record_tail(tail)
        return result

    def _record_tail(self, tail):
        if tail is None:
            return
        report = self.report["local_search"]
        report["tail_checks"] += tail.checks
        report["tail_reused_picks"] += tail.reused_picks
        report["tail_reused_decodes"] += int(tail.reused_picks > 0)
        report["tail_bulk_installs"] += tail.bulk_installs
        report["last_tail_reason"] = tail.reason
