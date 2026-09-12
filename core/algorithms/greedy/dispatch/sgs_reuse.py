"""Reuse successful fixed-resource scores only with exact native content evidence."""

from collections import Counter
from types import GetSetDescriptorType, SimpleNamespace
from typing import Any

from core.algorithm_runtime.native_snapshot import (
    UNSUPPORTED,
    content_snapshot,
    make_class_guard,
    native_record_snapshot,
    scalar_tuple_snapshot,
)
from core.algorithm_runtime.owned_timeline import OwnedSegments, OwnedTimeline
from core.algorithm_runtime.resource_quality import MachineTypeState
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithm_runtime.sgs_estimate_reuse import native_sgs_policy_snapshot
from core.algorithm_runtime.slot_overlap_reuse import SlotReuseTimeline
from core.models.batch import Batch
from core.models.batch_operation import BatchOperation

_BATCH_GUARD = make_class_guard(Batch)
_OP_GUARD = make_class_guard(BatchOperation)
_STATE_GUARD = make_class_guard(ScheduleRunState)
_TYPE_STATE_GUARD = make_class_guard(MachineTypeState)
_SEGMENTS_GUARD = make_class_guard(OwnedSegments)
_TIMELINE_GUARDS = {cls: make_class_guard(cls) for cls in (SlotReuseTimeline, OwnedTimeline)}
_SEGMENTS_SAMPLE = OwnedSegments()
_SEGMENT_MUTATORS = {name: getattr(OwnedSegments, name) for name in (
    "append", "extend", "clear", "pop", "remove", "__iadd__", "__imul__", "insert",
    "__setitem__", "__delitem__", "sort", "reverse", "certificate", "__getitem__", "__iter__", "__len__",
    "_native_item",
)}
_RECORD_TYPES = (Batch, BatchOperation, SimpleNamespace)
_OP_FIELDS = ("id", "seq", "batch_id", "piece_id", "source", "machine_id", "operator_id",
              "op_type_name", "setup_hours", "unit_hours")
_BATCH_FIELDS = ("batch_id", "quantity", "priority", "due_date", "ready_date")


def _native_model_access(cls):
    # A helper-import snapshot cannot prove hooks changed before that import.
    # Establish the builtin access path without constructing a DTO or invoking
    # a descriptor; unknown class layouts keep their existing dispatch path.
    if type(cls) is not type:
        return False
    lineage, fields = cls.__mro__, vars(cls)
    if len(lineage) != 2 or lineage[1] is not object or any(type(key) is not str for key in fields):
        return False
    if fields.get("__getattribute__", object.__getattribute__) is not object.__getattribute__ or "__getattr__" in fields:
        return False
    descriptor = fields.get("__dict__")
    return (type(descriptor) is GetSetDescriptorType and descriptor.__objclass__ is cls
            and descriptor.__name__ == "__dict__")


def _native_model_fields(cls, names):
    if not _native_model_access(cls):
        return False
    fields = vars(cls)
    for name in names:
        value = fields.get(name)
        kind = type(value)
        if value is not None and kind is not str and kind is not int and kind is not float and kind is not bool:
            return False
    return True


def _native_dispatch_access():
    if not _native_model_access(BatchOperation):
        return False
    fields = vars(BatchOperation)
    source = fields.get("source")
    return (type(source) is str and source == "internal" and fields.get("machine_id", UNSUPPORTED) is None
            and fields.get("operator_id", UNSUPPORTED) is None)


def _plain_dispatch_fields(op):
    kind = type(op)
    if kind is BatchOperation:
        if not _native_dispatch_access():
            return None
    elif kind is not SimpleNamespace:
        return None
    data = vars(op)
    # Even a native DTO can have a replaced dict or keys with custom equality.
    if type(data) is not dict or any(type(key) is not str for key in data):
        return None
    if kind is BatchOperation and not _OP_GUARD(op):
        return None
    return data


def can_skip_native_sgs_reuse(operations):
    """Conservatively forgo optional caching; later callbacks still score live data."""
    if type(operations) is not list:
        return False
    for op in operations:
        data = _plain_dispatch_fields(op)
        if data is None:
            return False
        source = data.get("source", "internal")
        machine, operator = data.get("machine_id"), data.get("operator_id")
        if type(source) is not str or source not in ("internal", "external"):
            return False
        if any(value is not None and type(value) is not str for value in (machine, operator)):
            return False
        if source == "internal" and machine and machine.strip() and operator and operator.strip():
            return False
    return True


def _segments(values):
    if type(values) is list and not values:
        return list, ()
    if type(values) is OwnedSegments:
        if not vars(values).keys().isdisjoint(_SEGMENT_MUTATORS):
            return UNSUPPORTED
        certificate = values.certificate()
        return UNSUPPORTED if certificate is None else certificate
    return content_snapshot(values)


def _record(value):
    if type(value) is Batch and (not _native_model_fields(Batch, _BATCH_FIELDS) or not _BATCH_GUARD(value)):
        return UNSUPPORTED
    if type(value) is BatchOperation and (not _native_model_fields(BatchOperation, _OP_FIELDS) or not _OP_GUARD(value)):
        return UNSUPPORTED
    return native_record_snapshot(value, _RECORD_TYPES)


def _type_state(mapping, machine_id):
    if type(mapping) is dict:
        return content_snapshot(mapping.get(machine_id))
    if type(mapping) is MachineTypeState:
        version = mapping.score_certificate(machine_id)
        tail = mapping.get(machine_id)
        if version is not None and (tail is None or type(tail) is str):
            return type(tail), tail, version
        entries = mapping.certificate(machine_id)
        if not entries and (tail is None or type(tail) is str):
            return type(tail), tail, ()
        return content_snapshot((tail, entries))
    return UNSUPPORTED


def _calendar(calendar, operator_id) -> Any:
    # Exact registered classes keep overlays and custom callbacks on their old path.
    result = native_sgs_policy_snapshot(calendar, operator_id)
    return UNSUPPORTED if result is None else result


def _estimate_inputs(inputs, reuse, *, during_score=False):
    op, batch = reuse._fields(inputs["op"], _OP_FIELDS), reuse._fields(inputs["batch"], _BATCH_FIELDS)
    if op is UNSUPPORTED or batch is UNSUPPORTED:
        return UNSUPPORTED
    machine_id, operator_id = inputs["machine_id"], inputs["operator_id"]
    types = reuse._machine_types(machine_id) if during_score else _type_state(inputs["last_op_type_by_machine"], machine_id)
    timing = content_snapshot(tuple(inputs[key] for key in (
        "machine_id", "operator_id", "base_time", "prev_end", "end_dt_exclusive",
    )))
    segments = tuple(_segments(inputs[key]) for key in ("machine_timeline", "operator_timeline", "machine_downtimes"))
    calendar = None if during_score else _calendar(inputs["calendar"], operator_id)
    if any(value is UNSUPPORTED for value in (types, timing, calendar) + segments):
        return UNSUPPORTED
    return op, batch, types, (timing, segments), calendar


class NativeSgsReuse:
    """A run owns entries; content comparisons also detect same-length mutation."""

    def __init__(self, scheduler, ctx, state, scheduler_guard, context_guard, operations, batches):
        self.scheduler, self.ctx, self.state = scheduler, ctx, state
        self.scheduler_guard = scheduler_guard
        self.context_guard = context_guard
        self.operations, self.batches = operations, batches
        self.entries = {}
        self.estimates = {}
        self.scoring_op = None
        self.round_policies = None
        self.field_tokens = {}
        self.round_types = {}
        self.round_supported = False
        self.eligible = set()
        self.hits, self.misses = 0, 0
        self.model_examples = {type(value): value for value in operations + list(batches.values())}

    def supported(self):
        if not self.scheduler_guard(self.scheduler) or not self.context_guard(self.ctx) or not _STATE_GUARD(self.state):
            return False
        if not self._state_supported():
            return False
        for cls, guard in ((Batch, _BATCH_GUARD), (BatchOperation, _OP_GUARD)):
            if cls in self.model_examples and not guard(self.model_examples[cls]):
                return False
        return self._callbacks_supported() and self.ctx.calendar is self.scheduler.calendar

    def _state_supported(self):
        if (type(self.state.machine_timeline) not in (SlotReuseTimeline, OwnedTimeline)
                or type(self.state.operator_timeline) not in (dict, OwnedTimeline)):
            return False
        for mapping in (self.state.machine_timeline, self.state.operator_timeline):
            if type(mapping) is not dict and not _TIMELINE_GUARDS[type(mapping)](mapping):
                return False
        if not _SEGMENTS_GUARD(_SEGMENTS_SAMPLE):
            return False
        if type(self.state.last_op_type_by_machine) is MachineTypeState and not _TYPE_STATE_GUARD(self.state.last_op_type_by_machine):
            return False
        return True

    def _callbacks_supported(self):
        for field, name in (("internal_callback", "_schedule_internal"), ("external_callback", "_schedule_external"),
                            ("auto_assign_callback", "_auto_assign_internal_resources"),
                            ("auto_assign_attempt_callback", "_auto_assign_internal_resources_attempt")):
            callback = vars(self.ctx).get(field)
            if getattr(callback, "__self__", None) is not self.scheduler:
                return False
            if getattr(callback, "__func__", None) is not vars(type(self.scheduler)).get(name):
                return False
        return True

    def begin_round(self, candidates=None):
        self.round_supported = self.supported()
        self.round_types = {}
        self.eligible = _eligible_candidates(candidates, self.entries) if self.round_supported and candidates is not None else None
        if self.round_supported and (self.eligible is None or self.eligible):
            self._refresh_policies()
        return self.round_supported and (self.eligible is None or bool(self.eligible))

    def _refresh_policies(self):
        policies = _calendar(self.ctx.calendar, None)
        self.round_policies = None if policies is UNSUPPORTED else policies
        self.round_policy_tokens = {}

    def _operator_policies(self, operator_id, previous=None):
        if self.round_policies is None:
            return UNSUPPORTED
        keys = tuple(key for key, _ in previous) if previous is not None else None
        if keys is not None and any(key[0] != operator_id for key in keys):
            keys = None
        cache_key = operator_id, keys
        if cache_key not in self.round_policy_tokens:
            snapshot = self.round_policies.snapshot(operator_id, keys)
            self.round_policy_tokens[cache_key] = UNSUPPORTED if snapshot is None else snapshot
        return self.round_policy_tokens[cache_key]

    def _machine_types(self, machine_id):
        if machine_id not in self.round_types:
            self.round_types[machine_id] = _type_state(self.state.last_op_type_by_machine, machine_id)
        return self.round_types[machine_id]

    def _fields(self, record, names):
        if type(record) not in _RECORD_TYPES:
            return UNSUPPORTED
        data = vars(record)
        values = tuple(data.get(name) for name in names)
        key = id(record), names
        token = scalar_tuple_snapshot(values, self.field_tokens.get(key))
        if token is UNSUPPORTED:
            return UNSUPPORTED
        self.field_tokens[key] = token
        return type(record), token

    def score_token(self, *, op, batch, batch_id, batch_order, graph_state, end_dt_exclusive,
                    machine_downtimes, dispatch_rule, strict_mode, avg_proc_hours, total_hours_by_op_id, after=False) -> Any:
        op_token, batch_token = self._fields(op, _OP_FIELDS), self._fields(batch, _BATCH_FIELDS)
        if op_token is UNSUPPORTED or batch_token is UNSUPPORTED:
            return UNSUPPORTED
        resources = _fixed_resources(op, batch_order, self.state.batch_progress, machine_downtimes)
        if resources is None:
            return UNSUPPORTED
        data, machine_id, operator_id = resources
        graph = _graph_token(graph_state, data.get("id"))
        previous = self.entries.get(id(op)) if not after else None
        timing = scalar_tuple_snapshot((
            self.state.base_time, self.state.batch_progress.get(batch_id, self.state.base_time),
            end_dt_exclusive,
            batch_order.get(batch_id, 999999), strict_mode, avg_proc_hours, total_hours_by_op_id.get(data.get("id")),
        ), previous[0][3][0] if previous is not None else None)
        segments = tuple(_segments(values) for values in (
            self.state.machine_timeline.get(machine_id, []), self.state.operator_timeline.get(operator_id, []),
            (machine_downtimes or {}).get(machine_id, []),
        ))
        types = self._machine_types(machine_id)
        calendar = self._operator_policies(operator_id, previous[0][-1] if previous is not None else None)
        if any(value is UNSUPPORTED for value in (graph, timing, types, calendar) + segments):
            return UNSUPPORTED
        return op_token, batch_token, graph, (timing, segments), types, dispatch_rule, calendar

    def score(self, score, inputs):
        if not self.round_supported or (self.eligible is not None and id(inputs["op"]) not in self.eligible):
            return score()
        token = self.score_token(**inputs)
        if token is UNSUPPORTED:
            return score()
        op = inputs["op"]
        previous = self.entries.get(id(op))
        if previous is not None and previous[0] == token:
            self.hits += 1
            return previous[1]
        self.misses += 1
        self.scoring_op = op
        try:
            result = score()
        finally:
            self.scoring_op = None
        self._refresh_policies()
        after = self.score_token(**inputs, after=True)
        # Calendar warming is the only allowed difference during a native score.
        if after is not UNSUPPORTED and token[:-1] == after[:-1] and _policies_retained(token[-1], after[-1]):
            self.entries[id(op)] = after, result
            estimate = self.estimates.get(id(op))
            if estimate is not None:
                self.estimates[id(op)] = estimate[0][:-1] + (after[-1],), estimate[1], estimate[2]
        else:
            self.entries.pop(id(op), None)
            self.estimates.pop(id(op), None)
        return result

    def remember_estimate(self, estimate, inputs):
        if self.scoring_op is not inputs["op"]:
            return
        token = _estimate_inputs(inputs, self, during_score=True)
        if token is not UNSUPPORTED:
            self.estimates[id(inputs["op"])] = token, estimate, inputs["total_hours_base"]

    def selected_estimate(self, inputs):
        if not self.supported():
            return None
        entry = self.estimates.get(id(inputs["op"]))
        if entry is None:
            return None
        token = _estimate_inputs(inputs, self)
        return entry[1:] if token is not UNSUPPORTED and token == entry[0] else None


def _policies_retained(before, after):
    current = dict(after)
    return all(key in current and current[key] == value for key, value in before)


def _eligible_candidates(candidates, entries):
    resources = []
    for _, op in candidates:
        if type(op) not in _RECORD_TYPES:
            continue
        data = vars(op)
        machine, operator = data.get("machine_id"), data.get("operator_id")
        if data.get("source", "internal") == "internal" and type(machine) is str and type(operator) is str:
            if machine.strip() and operator.strip():
                resources.append((id(op), machine.strip(), operator.strip()))
    machines = Counter(machine for _, machine, _ in resources)
    operators = Counter(operator for _, _, operator in resources)
    # Measured shared-resource workloads pay more for invalidation than rescoring.
    # Start caching only when both resources are exclusive among current ready peers.
    return {key for key, machine, operator in resources if key in entries
            or (len(resources) > 1 and machines[machine] == 1 and operators[operator] == 1)}


def _fixed_resources(op, batch_order, batch_progress, machine_downtimes):
    data = vars(op)
    machine_id, operator_id = data.get("machine_id"), data.get("operator_id")
    if data.get("source", "internal") != "internal" or type(machine_id) is not str or type(operator_id) is not str:
        return None
    if not machine_id.strip() or not operator_id.strip():
        return None
    if type(batch_order) is not dict or type(batch_progress) is not dict:
        return None
    if machine_downtimes is not None and type(machine_downtimes) is not dict:
        return None
    return data, machine_id.strip(), operator_id.strip()


def _graph_token(graph, op_id):
    if graph is None:
        return None
    if type(graph) is not dict:
        return UNSUPPORTED
    priority = graph.get("graph_priority_key_by_op_id") or {}
    if type(priority) is not dict:
        return UNSUPPORTED
    result = [graph.get("score_enabled"), priority.get(op_id)]
    if "end_time_by_op_id" in graph:
        ends, predecessors = graph["end_time_by_op_id"], graph.get("predecessor_op_ids_by_op_id")
        if type(ends) is not dict or type(predecessors) is not dict:
            return UNSUPPORTED
        keys = predecessors.get(op_id, set())
        if type(keys) not in (set, frozenset) or any(type(key) is not int for key in keys):
            return UNSUPPORTED
        result.append({key: ends.get(key) for key in keys})
    return content_snapshot(result)


def create_native_sgs_reuse(scheduler, ctx, state, operations, batches, scheduler_guard, context_guard):
    if type(operations) is not list or type(batches) is not dict:
        return None
    if any(_record(value) is UNSUPPORTED for value in operations + list(batches.values())):
        return None
    reuse = NativeSgsReuse(scheduler, ctx, state, scheduler_guard, context_guard, operations, batches)
    return reuse if reuse.supported() else None
