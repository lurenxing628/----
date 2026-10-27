"""A feasible operation in the lowest graph-key group dominates all later groups.

The actual key is (nonnegative feasibility penalty, graph key, dynamic dispatch key).
With fixed-width graph keys, score the entire lowest ready group first. Any penalty-zero
member dominates every later group. IG/repair's explicit ranks are one such case. All selected operations
still go through the normal scorer and formal placement. A blocked first rank falls
back to scoring every other ready operation. Unknown/callback inputs keep full scoring.

The dominance holds for automatically assigned operations too: their probe only chooses the
machine/operator pair and the feasibility penalty, both of which sit behind the graph key.
Scoring is read-only, so skipping a later group changes no state; it only changes how many
times the auto-assign attempt counters in ``fallback_counts`` are charged. Static resource
errors (no eligible machine or operator, assignment disabled) keep the full path so the
first error stays the same. ``fixed_resources`` tells consumers that need the stricter
fixed-resource proof (decode tail reuse) whether every operation names its machine and operator.
"""

import math
from datetime import datetime
from types import MappingProxyType

from core.algorithm_contracts.value_domains import EXTERNAL
from core.algorithm_runtime.native_snapshot import UNSUPPORTED, scalar_snapshot
from core.errors import ValidationError

from .sgs_due_span import external_candidate_window
from .sgs_priority_keys import ValidatedGraphPriorityKeys
from .sgs_scoring import parse_due_date

_FIELDS = ("id", "seq", "batch_id", "piece_id", "source", "machine_id", "operator_id", "op_type_name",
           "setup_hours", "unit_hours", "quantity", "priority", "due_date", "ready_date", "material_ready_date", "ready_status",
           "ext_merge_mode", "ext_group_id", "ext_group_total_days", "ext_days")
_NO_PLACED_GROUPS = MappingProxyType({})


def prepare_pruning_record(record, plain_classes):
    kind = type(record)
    return plain_classes.get(kind, False) and all(scalar_snapshot(getattr(record, name, None)) is not UNSUPPORTED for name in _FIELDS)


class GraphPriorityPruning:
    @classmethod
    def for_cache(cls, cache, graph_state, batches, hours):
        if cache is None or cache._timing is None:
            return None
        # The cache already certified the pool and the native probe; auto-assign operations
        # are admitted only through that same certification.
        return cls(graph_state, batches, hours,
                   eligible_resources=cache.eligible_resources,
                   calendar=cache._timing.calendar, calendar_days=cache.calendar_days, preparation=cache.preparation)

    def __init__(self, graph_state, batches, hours, *, eligible_resources=None, calendar=None, calendar_days=None, preparation):
        self._plain_classes = preparation.plain_classes
        self._calendar_days = calendar_days
        self._records = preparation.pruning_records
        self._candidate_records = {}
        self._preparation = preparation
        self.key_width = 0
        # True only when every schedulable operation names both resources; tail reuse requires it.
        self.fixed_resources = True
        self._eligible_resources = eligible_resources
        self._calendar = calendar
        self.supported = self._prepare(graph_state, batches, hours)

    def _record(self, record):
        token = id(record)
        records = self._records if token in self._preparation.records_by_token else self._candidate_records
        if token not in records:
            records[token] = prepare_pruning_record(record, self._plain_classes)
        return records[token]

    def _prepare(self, graph, batches, hours):
        if graph is None or not graph.get("score_enabled"):
            return False
        keys = graph["graph_priority_key_by_op_id"]
        if type(keys) is not ValidatedGraphPriorityKeys:
            return False
        widths = {len(key) for key in keys.values()}
        if len(widths) != 1:
            return False
        self.key_width = widths.pop()
        if not self.key_width:
            return False
        for batch in batches.values():
            if not self._record(batch):
                return False
            try:
                parse_due_date(batch.due_date)
            except ValidationError:
                return False
        return self._certify_operations(graph, hours)

    def _certify_operations(self, graph, hours):
        for op_id, (_batch_id, op) in graph["op_by_id"].items():
            if not self._record(op):
                return False
            if op.source == EXTERNAL:
                if not self._certified_external(op):
                    return False
                self.fixed_resources = False
                continue
            if not self._certified_internal(op_id, hours):
                return False
            fixed = self._certified_resources(op)
            if fixed is None:
                return False
            self.fixed_resources = self.fixed_resources and fixed
        return True

    def _certified_external(self, op):
        if self._calendar_days is None:
            return False
        # Run the normal merge/calendar path with an empty group cache; the calendar rejects a
        # duration it cannot add. A native natural-day call is pure arithmetic; the earliest datetime
        # leaves room for every valid duration without depending on this operation's future progress.
        try:
            external_candidate_window(self._calendar, _NO_PLACED_GROUPS, op=op, prev_end=datetime.min)
        except (ValidationError, ValueError, OverflowError):
            return False
        return True

    @staticmethod
    def _certified_internal(op_id, hours):
        return op_id in hours and type(hours[op_id]) is float and math.isfinite(hours[op_id]) and hours[op_id] >= 0

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

    def intact(self):
        """Both ready-set narrowing paths require the same current input and timing proof."""
        return self.supported

    def frontier(self, candidates, graph):
        if len(candidates) < 2 or not self.intact():
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
