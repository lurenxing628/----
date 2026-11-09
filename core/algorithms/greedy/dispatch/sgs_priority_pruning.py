"""A feasible operation in the lowest graph-key group dominates all later groups.

The actual key is (nonnegative feasibility penalty, graph key, dynamic dispatch key).
Admission fixes one graph-key width, so score the entire lowest ready group first. Any penalty-zero
member dominates every later group. IG/repair's explicit ranks are one such case. All selected operations
still go through the normal scorer and formal placement. A blocked first rank falls
back to scoring every other ready operation. Uncertified inputs keep full scoring.

The dominance holds for automatically assigned operations too: their probe only chooses the
machine/operator pair and the feasibility penalty, both of which sit behind the graph key.
Scoring always runs with ``probe_only=True``, so skipping a later group mutates neither runtime
state nor the formal ``fallback_counts``. Static resource
errors (no eligible machine or operator, assignment disabled) keep the full path so the
first error stays the same. ``fixed_resources`` tells consumers that need the stricter
fixed-resource proof (decode tail reuse) whether every operation names its machine and operator.
"""

from core.algorithm_contracts.value_domains import EXTERNAL


class GraphPriorityPruning:
    @classmethod
    def for_cache(cls, cache, graph_state):
        if cache.timing is None:
            return None
        # The cache already certified the pool and the native probe; auto-assign operations
        # are admitted only through that same certification.
        return cls(
            graph_state,
            eligible_resources=cache.eligible_resources,
            calendar_days=cache.calendar_days,
            preparation=cache.preparation,
        )

    def __init__(self, graph_state, *, eligible_resources, calendar_days, preparation):
        self._calendar_days = calendar_days
        self._preparation = preparation
        # True only when every schedulable operation names both resources; tail reuse requires it.
        self.fixed_resources = True
        self._eligible_resources = eligible_resources
        self.supported = self._prepare(graph_state)

    def _prepare(self, graph):
        if graph is None or not graph["score_enabled"]:
            return False
        if not self._preparation.all_batch_due_dates_valid():
            return False
        return self._certify_operations(graph)

    def _certify_operations(self, graph):
        for _op_id, (_batch_id, op) in graph["op_by_id"].items():
            if op.source == EXTERNAL:
                if not self._certified_external(op):
                    return False
                self.fixed_resources = False
                continue
            fixed = self._certified_resources(op)
            if fixed is None:
                return False
            self.fixed_resources = self.fixed_resources and fixed
        return True

    def _certified_external(self, op):
        if self._calendar_days is None:
            return False
        return self._preparation.certified_external_operation(op)

    def _certified_resources(self, op):
        """True for a fixed machine/operator pair, False for a certified auto-assign operation, None otherwise.

        An auto-assign operation is certified only when the native pool statically yields at least
        one machine and one operator: the probe then always produces a feasibility penalty rather
        than a validation error, so an unscored group can never hide a static input error.
        """
        if op.machine_id and op.operator_id:
            return True
        if self._eligible_resources is None:
            return None
        eligible = self._eligible_resources(op)
        if eligible is None or not eligible[0] or not eligible[1]:
            return None
        return False

    def frontier(self, candidates, graph):
        if len(candidates) < 2 or not self.supported:
            return None
        keys = graph["graph_priority_key_by_op_id"]
        selected, rank = [], None
        for item in candidates:
            key = keys[item[1].id]
            if rank is None or key < rank:
                selected, rank = [item], key
            elif key == rank:
                selected.append(item)
        return selected if len(selected) < len(candidates) else None

    def partition(self, candidates, graph):
        frontier = self.frontier(candidates, graph)
        if frontier is None:
            return candidates, []
        selected_ids = {id(item) for item in frontier}
        return frontier, [item for item in candidates if id(item) not in selected_ids]
