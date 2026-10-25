"""Reuse SGS dispatch keys for candidates whose inputs did not change since the last step.

One SGS step only changes the dispatched batch's progress, the two occupied resource
timelines, that machine's type history and busy hours, and the resource-demand window.
A ready candidate that reads none of the changed cells produces the same dispatch key,
so re-estimating it is wasted work. Rather than tracking every write path, the cache
recomputes an O(1) witness of the cells a candidate reads straight from the live state
and reuses the previous key only when the witness is identical.

Fixed-resource candidates read the predecessor end, one machine and one operator
timeline and that machine's type history. Native auto-assign candidates read the same
cells for every eligible machine and operator plus busy hours; they consult the demand
window only after two probes tied on (end_time, changeover), which the probe reports
itself. External candidates are cheap and never cached. The cache stays out of the way
while the certificate reuse owns a round and whenever scoring or auto-assign internals
are monkeypatched, so instrumented runs still observe every estimate they hook.
"""
from __future__ import annotations

from functools import partial
from types import GetSetDescriptorType, MemberDescriptorType, MethodType
from typing import TYPE_CHECKING, Any, Callable, Dict, NamedTuple, Optional, Tuple

from core.algorithm_contracts.value_domains import INTERNAL
from core.algorithm_runtime.auto_assign_contract import AutoAssignAttempt
from core.algorithm_runtime.calendar_timing_memo import MemoizedTimingCalendar, native_timing_calendar
from core.algorithm_runtime.internal_slot import refresh_changeover_penalty
from core.algorithm_runtime.resource_quality import MachineTypeState
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithm_runtime.sgs_shared_slot import SharedSlotEstimateCache

if TYPE_CHECKING:
    from core.algorithm_contracts.types import OpForScheduleAlgo
    from core.models.batch import Batch

_FIXED = "fixed"
_AUTO = "auto"
_HEAPTYPE = 1 << 9  # Py_TPFLAGS_HEAPTYPE: only Python-level classes can carry accessor hooks
_UNCLASSIFIED = object()
# Every operation and batch field the dispatch key can depend on; a class-level accessor hook
# or descriptor on any of them means reads may vary between steps, so such records are never cached.
_RECORD_FIELDS = (
    "id", "seq", "batch_id", "piece_id", "source", "machine_id", "operator_id", "op_type_id", "op_type_name",
    "setup_hours", "unit_hours", "quantity", "priority", "due_date", "ready_date", "material_ready_date", "ready_status", "created_at",
    "ext_merge_mode", "ext_group_id", "ext_group_total_days", "ext_days",
)
Witness = Tuple[Any, ...]
EligibleResources = Optional[Tuple[Tuple[str, ...], Tuple[str, ...]]]


class AutoAssignProbeContract(NamedTuple):
    """What the parent package tells the cache about its auto-assign probe; dispatch never imports it."""

    natives_intact: Callable[[], bool]


def native_auto_assign_context(ctx: Any, scheduler: Any, native_type: type) -> bool:
    """The auto-assign callback is ``native_type``'s untouched probe method bound to ``scheduler``.

    A patched probe (plain function, mock or another method) is not a bound native method, so the cache stays off.
    """
    callback = ctx.auto_assign_attempt_callback
    return (type(callback) is MethodType and callback.__self__ is scheduler
            and callback.__func__ is vars(native_type).get("_auto_assign_internal_resources_attempt"))


def make_sgs_score_cache_factory(ctx: Any, scheduler: Any, native_type: type, *,
                                 preparation: Any, probe: AutoAssignProbeContract) -> Any:
    """Select the native input and calendar adapters at the preparation boundary."""
    native_auto_assign = native_auto_assign_context(ctx, scheduler, native_type) and probe.natives_intact()
    timing_calendar = ctx.calendar if native_timing_calendar(ctx.calendar) else None
    calendar_days = ctx.calendar.add_calendar_days if native_timing_calendar(ctx.calendar, include_calendar_days=True) else None
    return partial(SgsScoreCache, native_auto_assign=native_auto_assign, eligible_resources=preparation.eligible_auto_assign_resources,
                   timing_calendar=timing_calendar, calendar_days=calendar_days, preparation=preparation)


def attach_sgs_score_cache(ctx: Any, *, state: ScheduleRunState, params: Any, resource_pool: Any) -> None:
    if params.dispatch_mode_key == "sgs":
        ctx.sgs_score_cache = ctx.native_preparation.score_cache_factory(
            state, auto_assign_enabled=bool(params.auto_assign_enabled), resource_pool=resource_pool,
        )


_STAT_NAMES = ("hits", "misses", "pair_hits", "pair_misses", "pair_revalidated", "calendar_hits", "calendar_misses",
               "shared_slot_hits", "shared_slot_misses", "key_cache_disabled", "graph_candidates_pruned")


def sgs_score_cache_stats(cache: Any) -> Dict[str, int]:
    return cache.stats() if cache is not None else dict.fromkeys(_STAT_NAMES, 0)


def plain_record_class(cls: Any) -> bool:
    """Instance attribute reads on ``cls`` are the builtin path: no accessor hooks, no field descriptors."""
    if type(cls) is not type:
        return False
    from core.algorithm_runtime.static_attribute import static_class_attribute
    if type(static_class_attribute(cls, "__dict__")) not in (GetSetDescriptorType, MemberDescriptorType):
        return False
    for klass in cls.__mro__[:-1]:
        if not klass.__flags__ & _HEAPTYPE:
            continue
        fields = vars(klass)
        if any(type(key) is not str for key in fields):
            return False
        if "__getattribute__" in fields or "__getattr__" in fields:
            return False
        if any(hasattr(type(fields.get(name)), "__get__") for name in _RECORD_FIELDS if fields.get(name) is not None):
            return False
    return True


def _segments_witness(timeline: Any, resource_id: str) -> Optional[Tuple[int, int]]:
    segments = timeline.get(resource_id)
    # Every mutation path appends one segment; identity guards against wholesale replacement.
    return None if segments is None else (id(segments), len(segments))


def _type_witness(types: Any, machine_id: str) -> Any:
    if isinstance(types, MachineTypeState):
        return types.neighbor_witness(machine_id)
    return None if types is None else (None, types.get(machine_id))


class _Entry:
    __slots__ = ("witness", "demand_revision", "key", "round", "resources", "estimate")

    def __init__(
        self, witness: Witness, demand_revision: Optional[int], key: Tuple[float, ...], round_no: int,
        resources: Optional[Tuple[str, str]], estimate: Optional[Tuple[Any, ...]],
    ) -> None:
        self.witness = witness
        self.demand_revision = demand_revision
        self.key = key
        # Round in which this entry was last proved current; formal placement only trusts the current round.
        self.round = round_no
        self.resources = resources
        self.estimate = estimate


class _PairEntry:
    __slots__ = ("witness", "estimate", "scan", "seq")

    def __init__(self, witness: Witness, estimate: Any, scan: Optional[Tuple[Any, Any]], seq: int) -> None:
        self.witness = witness
        self.estimate = estimate
        # [scan_start, scan_end]: the span whose busy blocks steered the estimate's avoidance path.
        self.scan = scan
        # Occupation sequence number when the estimate was last proved current.
        self.seq = seq


class SgsScoreCache:
    """Per-decode memo of dispatch keys, validated against the live state on every read.

    Entries are keyed by operation identity: the loop scores the very same objects every round.
    """

    def __init__(
        self, state: ScheduleRunState, *, auto_assign_enabled: bool, resource_pool: Any, native_auto_assign: bool,
        eligible_resources: Callable[[Any], EligibleResources], timing_calendar: Any, calendar_days: Any, preparation: Any,
    ) -> None:
        self.state = state
        self.preparation = preparation
        self.calendar_days = calendar_days
        self.hits = 0
        self.misses = 0
        self._reuse_keys = True
        self._saw_auto = False
        self.graph_candidates_pruned = 0
        self.eligible_resources: Optional[Callable[[Any], EligibleResources]] = (
            eligible_resources if (auto_assign_enabled and native_auto_assign and isinstance(resource_pool, dict)) else None
        )
        self._timing = MemoizedTimingCalendar(timing_calendar) if timing_calendar is not None else None
        self._shared_slots = SharedSlotEstimateCache() if self._timing is not None else None
        # Every timeline occupation performed inside this decode, per (timeline identity, resource): (seq, start, end).
        self._occupations: Dict[Tuple[int, str], list] = {}
        self._occupation_seq = 0
        self._last_scan: Optional[Tuple[Any, Any]] = None
        self.pair_revalidated = 0
        self._entries: Dict[int, _Entry] = {}
        # Per operation: False when it can never be cached (external, hooked record classes, no native
        # pool), else its eligible auto-assign resources or None for fixed resources.
        self._eligible: Dict[Tuple[int, str, str], Any] = {}
        self._plain_classes: Dict[type, bool] = preparation.plain_classes
        self.round = 0
        self.pair_hits = 0
        self.pair_misses = 0
        # op identity -> (machine, operator) -> abort-free estimate with its witness; one probe pair reads only these cells.
        self._pairs: Dict[int, Dict[Tuple[str, str], _PairEntry]] = {}
        # Set for a round whose scoring internals are instrumented: nothing is handed back until a native round begins.
        self._suspended = False
        self._scoring_op: Any = None
        self._pending_tie: Optional[bool] = None
        self._pending_resources: Optional[Tuple[str, str]] = None
        self._pending_estimate: Optional[Tuple[Any, ...]] = None

    def stats(self) -> Dict[str, int]:
        timing = self._timing
        return {
            "hits": self.hits, "misses": self.misses, "pair_hits": self.pair_hits, "pair_misses": self.pair_misses,
            "pair_revalidated": self.pair_revalidated,
            "calendar_hits": timing.hits if timing is not None else 0, "calendar_misses": timing.misses if timing is not None else 0,
            "shared_slot_hits": self._shared_slots.hits if self._shared_slots is not None else 0,
            "shared_slot_misses": self._shared_slots.misses if self._shared_slots is not None else 0,
            "key_cache_disabled": int(not self._reuse_keys), "graph_candidates_pruned": self.graph_candidates_pruned,
        }

    def shared_slot_estimate(self, *, calendar, op, batch, machine_id, operator_id, prev_end, total_hours,
                             end_dt_exclusive, machine_downtimes, compute):
        if (self._suspended or self._timing is None or self._shared_slots is None
                or not self._plain(op) or not self._plain(batch)):
            return compute()
        return self._shared_slots.resolve(
            state=self.state, calendar=self.timing_calendar(calendar), op=op, priority=batch.priority,
            machine_id=machine_id, operator_id=operator_id, prev_end=prev_end, total_hours=total_hours,
            end_dt_exclusive=end_dt_exclusive, machine_downtimes=machine_downtimes, compute=compute,
            read_scan=lambda: self._last_scan, note_scan=self.note_scan)

    def timing_calendar(self, calendar: Any) -> Any:
        """The per-decode memo of ``calendar``'s pure timing calls, or ``calendar`` itself when it is not certified."""
        timing = self._timing
        if self._suspended or timing is None or timing.calendar is not calendar:
            return calendar
        return timing

    def note_scan(self, scan_start: Any, scan_end: Any) -> None:
        """Span of busy blocks that steered the estimate just computed inside ``pair_estimate``."""
        self._last_scan = (scan_start, scan_end)

    def observe_occupation(self, timeline: Any, resource_id: str, start: Any, end: Any) -> None:
        """One segment was inserted into ``timeline[resource_id]``; pair memos check new segments against their scan span."""
        self._occupation_seq += 1
        self._occupations.setdefault((id(timeline), resource_id), []).append((self._occupation_seq, start, end))

    def forget(self, op: OpForScheduleAlgo) -> None:
        """A dispatched operation never becomes a candidate again."""
        identity = id(op)
        self._entries.pop(identity, None)
        self._pairs.pop(identity, None)

    def pair_estimate(
        self, *, op: OpForScheduleAlgo, machine_id: str, operator_id: str, prev_end: Any, machine_timeline: Any,
        operator_timeline: Any, compute: Callable[[], Any],
    ) -> Any:
        """Abort-free slot estimate of one probe pair, reused while the pair's cells are unchanged.

        Returns None when the memo is not applicable so the caller runs its own estimator; ``compute``
        must estimate the very same pair against the same timelines with ``abort_after=None``.
        """
        state = self.state
        if (self._suspended or not self._reuse_keys or self.eligible_resources is None
                or machine_timeline is not state.machine_timeline or operator_timeline is not state.operator_timeline):
            return None
        witness = (
            prev_end,
            _segments_witness(machine_timeline, machine_id),
            _segments_witness(operator_timeline, operator_id),
            _type_witness(state.last_op_type_by_machine, machine_id),
        )
        pairs = self._pairs.setdefault(id(op), {})
        pair = (machine_id, operator_id)
        entry = pairs.get(pair)
        if entry is not None:
            if entry.witness == witness:
                self.pair_hits += 1
                return entry.estimate
            estimate = self._revalidated(entry, witness, op, machine_id, operator_id, machine_timeline, operator_timeline)
            if estimate is not None:
                self.pair_revalidated += 1
                entry.witness, entry.estimate, entry.seq = witness, estimate, self._occupation_seq
                return estimate
        self._last_scan = None
        estimate = compute()
        self.pair_misses += 1
        pairs[pair] = _PairEntry(witness, estimate, self._last_scan, self._occupation_seq)
        return estimate

    def _revalidated(
        self, entry: _PairEntry, witness: Witness, op: OpForScheduleAlgo, machine_id: str, operator_id: str, machine_timeline: Any,
        operator_timeline: Any,
    ) -> Any:
        """The memoized estimate brought up to date without a new scan, or None when a new scan is required.

        A scan is a deterministic walk steered only by the busy blocks inside its span; new blocks
        that lie entirely outside the span leave every hop, hence the slot, unchanged. Only the
        changeover penalty reads the machine's type history and is recomputed when that changed.
        """
        old = entry.witness
        scan = entry.scan
        if scan is None or old[0] != witness[0]:
            return None
        for timeline, resource_id, before, after in (
            (machine_timeline, machine_id, old[1], witness[1]), (operator_timeline, operator_id, old[2], witness[2]),
        ):
            if before != after and not self._new_segments_outside_scan(timeline, resource_id, before, after, entry, scan):
                return None
        estimate = entry.estimate
        if old[3] != witness[3]:
            estimate = refresh_changeover_penalty(
                estimate, op=op, machine_id=machine_id, last_op_type_by_machine=self.state.last_op_type_by_machine,
            )
        return estimate

    def _new_segments_outside_scan(
        self, timeline: Any, resource_id: str, before: Any, after: Any, entry: _PairEntry, scan: Tuple[Any, Any],
    ) -> bool:
        """Every segment that grew ``timeline[resource_id]`` since the memo is known and misses ``scan``, the entry's span."""
        if after is None or (before is not None and before[0] != after[0]):
            return False
        grown = after[1] - (before[1] if before is not None else 0)
        log = self._occupations.get((id(timeline), resource_id))
        if grown <= 0 or log is None or len(log) < grown:
            return False
        recent = log[-grown:]
        # Exactly ``grown`` occupations newer than the memo account for the growth; anything else is an unknown mutation.
        if recent[0][0] <= entry.seq or (len(log) > grown and log[-grown - 1][0] > entry.seq):
            return False
        scan_start, scan_end = scan
        # A block touching the end of a certified skip still extends the skip, so the end is closed here.
        return all(start > scan_end or end <= scan_start for _seq, start, end in recent)

    def next_round(self) -> None:
        """One SGS step: entries proved in earlier rounds no longer qualify for placement handoff."""
        self.round += 1
        # Re-scoring remains exact. On a resource shared by every ready operation, repeatedly
        # proving that old keys are stale costs more than recomputing their cheap key suffixes.
        if self._shared_slots is not None:
            if self.round >= 8 and not self._saw_auto and self.hits == 0 and self._shared_slots.hits >= 256:
                self._reuse_keys = False
                self._pairs.clear()
            self._shared_slots.clear()

    def suspend_round(self) -> None:
        """The scoring loop is not running its own code this round: serve no memo, hand nothing to placement.

        The handoff scope stays installed for the whole decode, so without this the probe memo and
        the calendar memo would keep answering behind an instrumented scorer's back.
        """
        self._suspended = True

    def begin_round(self) -> None:
        """Auto-assign keys may only be reused while the probe still runs the module's own code."""
        self._suspended = False
        if self._timing is not None and self._shared_slots is not None:
            self._shared_slots.begin_round()

    def record_attempt(self, attempt: AutoAssignAttempt) -> None:
        """Sink for the probe result of the candidate currently being scored."""
        self._pending_tie = attempt.pair_tie_occurred
        machine_id = attempt.machine_id
        operator_id = attempt.operator_id
        self._pending_resources = (machine_id, operator_id) if machine_id and operator_id else None

    def remember_estimate(self, estimate: Any, inputs: Dict[str, Any]) -> None:
        """Scoring estimate of the candidate being scored, kept for same-round formal placement."""
        if inputs.get("op") is not self._scoring_op:
            return
        self._pending_estimate = (
            estimate, inputs.get("total_hours_base"), inputs.get("machine_id"), inputs.get("operator_id"),
            inputs.get("prev_end"), inputs.get("calendar"), inputs.get("end_dt_exclusive"),
        )

    def selected_estimate(self, inputs: Dict[str, Any]) -> Optional[Tuple[Any, float]]:
        """(estimate, total_hours_base) proved current this round for exactly these placement inputs."""
        entry = self._entries.get(id(inputs.get("op")))
        if self._suspended or entry is None or entry.round != self.round or entry.estimate is None:
            return None
        estimate, total_hours_base, machine_id, operator_id, prev_end, calendar, end_dt_exclusive = entry.estimate
        if (inputs.get("machine_id"), inputs.get("operator_id")) != (machine_id, operator_id):
            return None
        if inputs.get("prev_end") != prev_end or inputs.get("calendar") is not calendar:
            return None
        if inputs.get("end_dt_exclusive") != end_dt_exclusive:
            return None
        return estimate, total_hours_base

    def selected_resources(self, op: OpForScheduleAlgo) -> Optional[Tuple[str, str]]:
        """Auto-assign pair the scoring probe chose for ``op``, valid only within the same round."""
        entry = self._entries.get(id(op))
        if self._suspended or entry is None or entry.round != self.round or entry.witness[0] != _AUTO:
            return None
        return entry.resources

    def resolve(
        self, op: OpForScheduleAlgo, batch: Batch, batch_id: str, graph_state: Optional[Dict[str, Any]],
        score: Callable[[], Tuple[float, ...]],
    ) -> Tuple[float, ...]:
        """Reuse the previous key while every cell the candidate reads is unchanged; otherwise score and remember."""
        witness = self._witness(op, batch, batch_id, graph_state)
        entry = self._entries.get(id(op)) if witness is not None else None
        if (self._reuse_keys and entry is not None and witness == entry.witness
                and (entry.demand_revision is None or entry.demand_revision == self._demand_revision())):
            self.hits += 1
            entry.round = self.round
            return entry.key
        self._pending_tie = None
        self._pending_resources = None
        self._pending_estimate = None
        self._scoring_op = op
        try:
            key = score()
        finally:
            self._scoring_op = None
        self.misses += 1
        if witness is None:
            return key
        demand_revision = None
        resources = None
        if witness[0] == _AUTO:
            if self._pending_tie is None:
                # The probe did not report tie provenance; its result cannot be validated later.
                return key
            if self._pending_tie:
                demand_revision = self._demand_revision()
            resources = self._pending_resources
        self._entries[id(op)] = _Entry(witness, demand_revision, key, self.round, resources, self._pending_estimate)
        return key

    def _demand_revision(self) -> Optional[int]:
        types = self.state.last_op_type_by_machine
        demand = types.demand if isinstance(types, MachineTypeState) else None
        return None if demand is None else demand.revision

    def _plain(self, record: Any) -> bool:
        return self._plain_classes.get(type(record), False)

    def _classify(self, op: OpForScheduleAlgo, batch: Batch, machine_id: str, operator_id: str) -> Any:
        if not self._plain(op) or not self._plain(batch):
            return False
        if op.source != INTERNAL:
            return False
        if machine_id and operator_id:
            return None
        if self.eligible_resources is None:
            return False
        eligible = self.eligible_resources(op)
        return False if eligible is None else eligible

    def _witness(
        self, op: OpForScheduleAlgo, batch: Batch, batch_id: str, graph_state: Optional[Dict[str, Any]],
    ) -> Optional[Witness]:
        # None (not specified) and the empty string an optimizer resource variant may carry both mean unassigned.
        machine_id = op.machine_id or ""
        operator_id = op.operator_id or ""
        memo_key = (id(op), machine_id, operator_id)
        eligible = self._eligible.get(memo_key, _UNCLASSIFIED)
        if eligible is _UNCLASSIFIED:
            eligible = self._eligible[memo_key] = self._classify(op, batch, machine_id, operator_id)
        if eligible is False:
            return None
        if eligible is not None:
            # Automatic assignment can become cacheable only after its shared resource demand
            # settles. Do not extrapolate fixed-resource zero-hit behavior to that search.
            self._saw_auto = True
            self._reuse_keys = True
        if not self._reuse_keys:
            # Retain same-round estimate/resource handoff; never reuse a previous round's key.
            return (_FIXED,)
        state = self.state
        # Piece scope scores against predecessor completion evidence that never changes once the
        # operation is ready; every other scope reads the live batch progress.
        prev_end = (None if graph_state is not None and "end_time_by_op_id" in graph_state
                    else state.batch_progress.get(batch_id, state.base_time))
        types = state.last_op_type_by_machine
        if eligible is None:
            return (
                _FIXED, prev_end, machine_id, operator_id,
                _segments_witness(state.machine_timeline, machine_id),
                _segments_witness(state.operator_timeline, operator_id),
                _type_witness(types, machine_id),
            )
        machines, operators = eligible
        return (
            _AUTO, prev_end, machine_id, operator_id,
            tuple([_segments_witness(state.machine_timeline, mid) for mid in machines]),
            tuple([_segments_witness(state.operator_timeline, oid) for oid in operators]),
            tuple([_type_witness(types, mid) for mid in machines]),
            tuple([state.machine_busy_hours.get(mid) for mid in machines]),
            tuple([state.operator_busy_hours.get(oid) for oid in operators]),
        )
