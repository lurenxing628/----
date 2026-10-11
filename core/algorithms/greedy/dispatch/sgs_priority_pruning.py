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
from types import GetSetDescriptorType, MemberDescriptorType, SimpleNamespace

from core.algorithm_runtime.calendar_timing_memo import native_timing_calendar
from core.algorithm_runtime.native_snapshot import UNSUPPORTED, make_class_guard, scalar_snapshot
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithm_runtime.static_attribute import static_attribute, static_class_attribute
from core.errors import ValidationError

from .sgs_score_cache import plain_record_class
from .sgs_scoring import _external_candidate_window, _parse_due_date

_FIELDS = ("id", "seq", "batch_id", "piece_id", "source", "machine_id", "operator_id", "op_type_name",
           "setup_hours", "unit_hours", "quantity", "priority", "due_date", "ready_date", "material_ready_date", "ready_status",
           "ext_merge_mode", "ext_group_id", "ext_group_total_days", "ext_days")


def _blank_or_text(value):
    return value is None or type(value) is str


class GraphPriorityPruning:
    @classmethod
    def for_cache(cls, cache, graph_state, batches, hours, *, strict_mode):
        if cache is None or cache._timing is None:
            return None
        # The cache already certified the pool and the native probe; auto-assign operations
        # are admitted only through that same certification.
        return cls(graph_state, batches, hours, strict_mode=strict_mode,
                   resource_pool=cache._pool, eligible_resources=cache._probe.eligible_resources,
                   calendar=cache._timing.calendar)

    def __init__(self, graph_state, batches, hours, *, strict_mode, resource_pool=None, eligible_resources=None, calendar=None):
        self.examples = {}
        self.guards = {}
        self.key_width = 0
        # True only when every schedulable operation names both resources; tail reuse requires it.
        self.fixed_resources = True
        self._pool = resource_pool if isinstance(resource_pool, dict) and eligible_resources is not None else None
        self._eligible_resources = eligible_resources
        self._calendar = calendar
        self._has_external = False
        self.supported = self._prepare(graph_state, batches, hours, strict_mode)

    def _record(self, record):
        kind = type(record)
        if kind not in self.guards:
            if (not plain_record_class(kind)
                    or type(static_class_attribute(kind, "__dict__")) not in
                    (GetSetDescriptorType, MemberDescriptorType)):
                return False
            self.guards[kind] = make_class_guard(kind)
        if not self.guards[kind](record):
            return False
        self.examples[kind] = record
        # Production uses the normalized OpForScheduleAlgo DTO, which also carries an
        # unrelated merge-audit list. Certify scoring fields, not unused metadata.
        return all(scalar_snapshot(static_attribute(record, name)) is not UNSUPPORTED for name in _FIELDS)

    def _prepare(self, graph, batches, hours, strict):
        if graph is None or not graph.get("score_enabled"):
            return False
        keys = graph["graph_priority_key_by_op_id"]
        widths = {len(key) for key in keys.values() if type(key) is tuple}
        if len(widths) != 1:
            return False
        self.key_width = widths.pop()
        if not self.key_width or not all(self._key_valid(key) for key in keys.values()):
            return False
        for batch in batches.values():
            if not self._record(batch):
                return False
            try:
                _parse_due_date(getattr(batch, "due_date", None), strict_mode=strict)
            except (ValidationError, ValueError, OverflowError):
                return False
        return self._certify_operations(graph, hours, strict)

    def _certify_operations(self, graph, hours, strict):
        for op_id, (_batch_id, op) in graph["op_by_id"].items():
            if (not self._record(op) or type(getattr(op, "id", None)) is not int
                    or type(getattr(op, "seq", None)) is not int):
                return False
            source = getattr(op, "source", "internal")
            if type(source) is not str:
                return False
            if source.strip().lower() == "external":
                if not self._certified_external(op, strict):
                    return False
                self._has_external, self.fixed_resources = True, False
                continue
            if not self._certified_internal(op, op_id, hours):
                return False
            fixed = self._certified_resources(op)
            if fixed is None:
                return False
            self.fixed_resources = self.fixed_resources and fixed
        return True

    def _certified_external(self, op, strict):
        if not native_timing_calendar(self._calendar, include_calendar_days=True):
            return False
        # Run the normal duration/merge/calendar validation with an empty group cache.
        # A native natural-day call is pure arithmetic; the earliest datetime leaves room
        # for every valid duration without depending on this operation's future progress.
        try:
            _external_candidate_window(
                SimpleNamespace(calendar=self._calendar), ScheduleRunState(base_time=datetime.min),
                op=op, batch_id=op.batch_id, prev_end=datetime.min, strict_mode=strict,
            )
        except (ValidationError, ValueError, OverflowError):
            return False
        return True

    @staticmethod
    def _certified_internal(op, op_id, hours):
        source = getattr(op, "source", "internal")
        return (type(source) is str and source.strip().lower() == "internal"
                and type(getattr(op, "id", None)) is int and type(getattr(op, "seq", None)) is int
                and op_id in hours and type(hours[op_id]) is float and math.isfinite(hours[op_id]) and hours[op_id] >= 0)

    def _certified_resources(self, op):
        """True for a fixed machine/operator pair, False for a certified auto-assign operation, None otherwise.

        An auto-assign operation is certified only when the native pool statically yields at least
        one machine and one operator: the probe then always produces a feasibility penalty rather
        than a validation error, so an unscored group can never hide a static input error.
        """
        machine, operator = getattr(op, "machine_id", None), getattr(op, "operator_id", None)
        if not _blank_or_text(machine) or not _blank_or_text(operator):
            return None
        if machine and machine.strip() and operator and operator.strip():
            return True
        if self._pool is None or self._eligible_resources is None:
            return None
        eligible = self._eligible_resources(op, self._pool)
        if eligible is None or not eligible[0] or not eligible[1]:
            return None
        return False

    def _key_valid(self, key):
        return (type(key) is tuple and len(key) == self.key_width
                and all(type(value) in (int, float) and math.isfinite(value) for value in key))

    def intact(self):
        """Both ready-set narrowing paths require the same current input and timing proof."""
        if not self.supported:
            return False
        if ((self._has_external and not native_timing_calendar(self._calendar, include_calendar_days=True))
                or any(not self.guards[kind](record) for kind, record in self.examples.items())):
            self.supported = False
        return self.supported

    def frontier(self, candidates, graph):
        if len(candidates) < 2 or not self.intact():
            return None
        keys = graph["graph_priority_key_by_op_id"]
        selected, rank = [], None
        for item in candidates:
            key = keys.get(item[1].id)
            if not self._key_valid(key):
                return None
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
