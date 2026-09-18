"""Share earliest slots between operations released inside one constant-efficiency span.

For fixed resource occupancy and constant positive processing time, let T be the earliest
feasible start found for release S. Every release r with S <= adjust(r) <= T has the same
earliest feasible start: its feasible set is a subset of the first one and still contains
T. The native walk finds that minimum only while the attempt end is monotone in the attempt
start, which holds when every certified work window the walk can touch, from S up to the
result's end, reports the same efficiency (shift lengths and non-working gaps never break
monotonicity; a faster later day would). A single window is the smallest such span; a
chain of same-efficiency windows extends the proof across days, so saturated resources
whose slots land days later can still share. Walks that carry attempt-path flags (early
stop, efficiency fallback) are never shared. Operation-specific changeover penalties are
always recomputed.
"""

import math
from datetime import datetime

from . import busy_block_skip, internal_slot
from .calendar_timing_memo import MemoizedTimingCalendar
from .owned_timeline import owned_segment_certificate, owned_segment_round_reader

_UNSUPPORTED = object()
_LIMIT = 1024
# Certified windows a span proof may chain; one per calendar day is the practical maximum.
_MAX_SPAN_WINDOWS = 64
_NATIVE_FUNCTIONS = tuple(
    (module, name, value)
    for module in (internal_slot, busy_block_skip)
    for name, value in vars(module).items()
    if callable(value) and getattr(value, "__module__", None) == module.__name__
)


def _native_walk():
    return all(vars(module).get(name) is value for module, name, value in _NATIVE_FUNCTIONS)


def _instant(value):
    return type(value) is datetime and value.tzinfo is None


def _segments_token(values):
    certificate = owned_segment_certificate(values)
    if certificate is not None:
        return certificate
    if type(values) in (list, tuple) and not values:
        return ()
    return _UNSUPPORTED


def _downtime_token(values):
    if values is None:
        return ()
    if type(values) not in (list, tuple):
        return _UNSUPPORTED
    if any(type(row) is not tuple or len(row) != 2 or not all(_instant(value) for value in row) for row in values):
        return _UNSUPPORTED
    return tuple(values)


def _native_slot_inputs(prev_end, base_time, cutoff, hours, priority, machine_id, operator_id):
    return (_instant(prev_end) and _instant(base_time) and (cutoff is None or _instant(cutoff))
            and type(hours) is float and math.isfinite(hours) and hours > 0
            and (priority is None or type(priority) is str)
            and type(machine_id) is str and type(operator_id) is str)


def constant_efficiency_span(calendar, start, end, priority, operator_id):
    """True when certified work windows chain from ``start`` past ``end`` with one efficiency throughout.

    Each window certifies a constant policy; the next one starts at the first working instant
    after the previous window ends. A cross-midnight window, a non-certified instant or a
    change of efficiency ends the proof.
    """
    efficiency = None
    cursor = start
    for _ in range(_MAX_SPAN_WINDOWS):
        window = busy_block_skip._certified_window(calendar, cursor, priority, operator_id)
        if window is None:
            return False
        current = calendar.get_efficiency(cursor, operator_id=operator_id)
        if efficiency is None:
            efficiency = current
        elif current != efficiency:
            return False
        if end <= window[1]:
            return True
        cursor = calendar.adjust_to_working_time(window[1], priority=priority, operator_id=operator_id)
    return False


class SharedSlotEstimateCache:
    """Bounded to one SGS round; native owner revisions also detect intervening mutations."""

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self._entries = {}
        self._native_round = None
        self._owners = {}

    def clear(self):
        self._entries.clear()
        self._owners.clear()
        self._native_round = None

    def begin_round(self):
        # Match the existing calendar/scorer native guards: re-certify code at each SGS
        # round boundary; only immutable native timing calls run inside a certified round.
        self._native_round = _native_walk()

    def _token(self, values):
        if self._native_round is None:
            return _segments_token(values)
        entry = self._owners.get(id(values))
        if entry is None or entry[0] is not values:
            reader = owned_segment_round_reader(values)
            if reader is None:
                return () if type(values) in (tuple, list) and not values else _UNSUPPORTED
            entry = self._owners[id(values)] = (values, reader)
        certificate = entry[1]()
        return certificate if certificate is not None else _UNSUPPORTED

    def resolve(self, *, state, calendar, op, priority, machine_id, operator_id, prev_end,
                total_hours, end_dt_exclusive, machine_downtimes, compute, read_scan, note_scan):
        key = self._key(state, calendar, priority, machine_id, operator_id, prev_end,
                        total_hours, end_dt_exclusive, machine_downtimes)
        if key is None:
            return compute()
        earliest = calendar.adjust_to_working_time(max(prev_end, state.base_time), priority=priority, operator_id=operator_id)
        if not _instant(earliest):
            return compute()
        entry = self._entries.get(key)
        if entry is not None and entry[0] <= earliest <= entry[1].start_time:
            self.hits += 1
            note_scan(*entry[2])  # A conservative superset of the later release's actual scan.
            return internal_slot.refresh_changeover_penalty(
                entry[1], op=op, machine_id=machine_id, last_op_type_by_machine=state.last_op_type_by_machine)
        self.misses += 1
        estimate = compute()
        scan = read_scan()
        if scan is None or estimate.abort_after_hit or estimate.efficiency_fallback_used:
            return estimate
        if not earliest <= estimate.start_time < estimate.end_time:
            return estimate
        if constant_efficiency_span(calendar, earliest, estimate.end_time, priority, operator_id):
            if len(self._entries) >= _LIMIT:
                # Evict the oldest entry of the round instead of dropping every proof at once.
                del self._entries[next(iter(self._entries))]
            self._entries[key] = (earliest, estimate, scan)
        return estimate

    def _key(self, state, calendar, priority, machine_id, operator_id, prev_end, total_hours, end_dt_exclusive, downtimes):
        native = _native_walk() if self._native_round is None else self._native_round
        if type(calendar) is not MemoizedTimingCalendar or not native:
            return None
        if not _native_slot_inputs(prev_end, state.base_time, end_dt_exclusive,
                                   total_hours, priority, machine_id, operator_id):
            return None
        machine = self._token(state.machine_timeline.get(machine_id, ()))
        operator = self._token(state.operator_timeline.get(operator_id, ()))
        downtime = _downtime_token(downtimes)
        if any(value is _UNSUPPORTED for value in (machine, operator, downtime)):
            return None
        return calendar, machine_id, operator_id, machine, operator, downtime, total_hours, priority, end_dt_exclusive
