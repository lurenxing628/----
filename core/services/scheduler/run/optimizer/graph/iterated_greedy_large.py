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
        for generator in self.generators:
            generator.completion_feedback = True
        self.diversification = BudgetStagnation(self)
        self.rotation = LargeGeneratorRotation(self.generators)

    def _reference_for_iteration(self):
        return self.diversification.reference()

    def _decode_trial(self, order, *, resume, reference):
        checkpoints = trial_request(reference, resume=resume) if self.checkpoints.enabled else None
        return self._decode(order, resume=resume, checkpoints=checkpoints)
