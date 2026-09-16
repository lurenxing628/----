"""A feasible operation in the lowest graph-key group dominates all later groups.

The actual key is (nonnegative feasibility penalty, graph key, dynamic dispatch key).
With fixed-width graph keys, score the entire lowest ready group first. Any penalty-zero
member dominates every later group. IG/repair's explicit ranks are one such case. All selected operations
still go through the normal scorer and formal placement. A blocked first rank falls
back to scoring every other ready operation. Unknown/callback inputs keep full scoring.
"""

import math
from types import GetSetDescriptorType, MemberDescriptorType

from core.algorithm_runtime.native_snapshot import UNSUPPORTED, make_class_guard, scalar_snapshot
from core.algorithm_runtime.static_attribute import static_class_attribute
from core.infrastructure.errors import ValidationError

from .sgs_score_cache import plain_record_class
from .sgs_scoring import _parse_due_date

_FIELDS = ("id", "seq", "batch_id", "piece_id", "source", "machine_id", "operator_id", "op_type_name",
           "setup_hours", "unit_hours", "quantity", "priority", "due_date", "ready_date", "ready_status")


class GraphPriorityPruning:
    @classmethod
    def for_cache(cls, cache, graph_state, batches, hours, *, strict_mode):
        if cache is None or cache._timing is None:
            return None
        return cls(graph_state, batches, hours, strict_mode=strict_mode)

    def __init__(self, graph_state, batches, hours, *, strict_mode):
        self.examples = {}
        self.guards = {}
        self.key_width = 0
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
        return all(scalar_snapshot(getattr(record, name, None)) is not UNSUPPORTED for name in _FIELDS)

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
        for op_id, (_batch_id, op) in graph["op_by_id"].items():
            if not self._record(op) or not self._fixed_operation(op, op_id, hours):
                return False
        return True

    @staticmethod
    def _fixed_operation(op, op_id, hours):
        machine, operator = getattr(op, "machine_id", None), getattr(op, "operator_id", None)
        source = getattr(op, "source", "internal")
        return (type(source) is str and source.strip().lower() == "internal"
                and type(machine) is str and bool(machine.strip())
                and type(operator) is str and bool(operator.strip())
                and type(getattr(op, "id", None)) is int and type(getattr(op, "seq", None)) is int
                and op_id in hours and type(hours[op_id]) is float and math.isfinite(hours[op_id]) and hours[op_id] >= 0)

    def _key_valid(self, key):
        return (type(key) is tuple and len(key) == self.key_width
                and all(type(value) in (int, float) and math.isfinite(value) for value in key))

    def frontier(self, candidates, graph):
        if not self.supported or len(candidates) < 2:
            return None
        if any(not self.guards[kind](record) for kind, record in self.examples.items()):
            self.supported = False
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
