"""Screened, locally budgeted IG with exact suffix reuse for large operation orders.

Picking a neighbourhood or finding a duplicate is not a full decode. Check the actual
suffix immediately before SGS. The first suffix estimate scales observed full cost by
remaining picks; subsequent estimates also retain the observed suffix cost floor.
These are duration estimates, not hard upper bounds: one started decode may overrun,
and the existing report records that overrun and retains only verified incumbents.
"""

from .optimizer_graph_ready_iterated_greedy import _BudgetExhausted, _IteratedGreedySearch
from .optimizer_graph_ready_iterated_greedy_diversify import BudgetStagnation, LargeGeneratorRotation
from .optimizer_graph_ready_iterated_greedy_local import LargeIGIteration
from .optimizer_graph_ready_iterated_greedy_tail import TailCheckpointStore, trial_request

LARGE_ORDER_MINIMUM = 128


def search_type_for(parent):
    return LargeIteratedGreedySearch if len(parent.order) >= LARGE_ORDER_MINIMUM else _IteratedGreedySearch


def iteration_for(search, original):
    return LargeIGIteration(search) if isinstance(search, LargeIteratedGreedySearch) else original(search)


class LargeIteratedGreedySearch(_IteratedGreedySearch):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cost_samples = []
        self._sampled_count = 0
        self._work_fraction = 1.0
        self.local_budget = None
        self._trial_reference = None
        self._active_tail = None
        self._trial_seconds = []
        self.checkpoints = TailCheckpointStore(self.limits.checkpoint_count)
        self.report["algorithm"] = "operation_destroy_queued_joint_insertion_v5"
        self.report["partial_evaluation"] = "checkpoint_prefix_and_reconverged_tail_exact"
        for generator in self.generators:
            generator.completion_feedback = True
        self.report["local_search"] = {
            "policy": "screened_insertion_with_local_budget_v1", "difficulty_feedback": "bounded_task_completion",
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

    def full_decode_cost(self):
        full = [elapsed for fraction, elapsed in self._cost_samples if fraction == 1.0]
        return sum(full) / len(full) if full else 0.0

    def trial_decode_cost(self):
        return max(self._trial_seconds[-3:]) if self._trial_seconds else self.full_decode_cost() / 2.0

    def _score_trial(self, order, reference):
        previous = self._trial_reference
        self._trial_reference = reference
        try:
            return super()._score_trial(order, reference)
        finally:
            self._trial_reference = previous

    def _decode_entry(self, order):
        budget, reference = self.local_budget, self._trial_reference
        self.local_budget, self._trial_reference = None, None
        try:
            return super()._decode_entry(order)
        finally:
            self.local_budget, self._trial_reference = budget, reference

    def _hard_budget_now(self):
        now = self.clock()
        if now >= self.deadline:
            raise _BudgetExhausted("time_budget")
        if self.report["decodes"] >= self.limits.max_decodes:
            raise _BudgetExhausted("decode_budget")
        return now

    def _require_budget(self):
        # Cheap neighbourhood and duplicate checks must not pay for an unknown full decode.
        self._hard_budget_now()
        if getattr(self, "local_budget", None) is not None:
            self.local_budget.check()

    def _decode(self, order, *, resume=None, checkpoints=None):
        previous = self._work_fraction
        previous_tail = self._active_tail
        trial = self._trial_reference is not None and checkpoints is None
        if trial and self.checkpoints.enabled:
            checkpoints = trial_request(self._trial_reference, resume=resume, budget=self.local_budget)
        self._active_tail = getattr(checkpoints, "tail_reuse", None)
        position = getattr(resume, "position", 0)
        fraction = (len(order) - position) / len(order) if type(position) is int and 0 <= position < len(order) else 1.0
        self._work_fraction = fraction
        before, started = self.report["decodes"], self.clock()
        try:
            result = super()._decode(order, resume=resume, checkpoints=checkpoints)
            if trial and result is not None:
                self._trial_seconds.append(max(self.clock() - started, 0.0))
                self._record_tail()
            return result
        except _BudgetExhausted:
            if self.report["decodes"] > before:
                self.report["local_search"]["interrupted_decodes"] += 1
            raise
        finally:
            # Recursive fallback after unsupported capture can already record its own sample.
            for elapsed in self.decode_seconds[self._sampled_count:]:
                self._cost_samples.append((fraction, elapsed))
            self._sampled_count = len(self.decode_seconds)
            self._work_fraction = previous
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

    def _expected_decode_seconds(self):
        if getattr(self, "_active_tail", None) is not None and self._trial_seconds:
            return self.trial_decode_cost()
        full = [elapsed for fraction, elapsed in self._cost_samples if fraction == 1.0]
        if not full:
            return 0.0
        fraction = self._work_fraction
        expected = sum(full) / len(full) * fraction
        if fraction < 1.0:
            for observed_fraction, elapsed in self._cost_samples:
                if observed_fraction < 1.0:
                    expected = max(expected, elapsed * max(1.0, fraction / observed_fraction))
        return expected

    def _before_decode(self):
        try:
            now = self._hard_budget_now()
            if getattr(self, "local_budget", None) is not None:
                self.local_budget.check()
            expected = self._expected_decode_seconds()
            self.report["decode_admission"] = {
                "policy": "observed_checkpoint_suffix_cost_v1", "remaining_pick_fraction": self._work_fraction,
                "estimated_decode_ms": expected * 1000.0, "remaining_ms": (self.deadline - now) * 1000.0,
            }
            if now + expected > self.deadline:
                raise _BudgetExhausted("decode_would_overrun")
        except _BudgetExhausted:
            self.report["budget_pruned_before_decode"] += 1
            raise
        self.report["decodes"] += 1
