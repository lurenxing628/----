"""Reuse SGS dispatch keys for candidates whose inputs did not change since the last step.

One SGS step only changes the dispatched batch's progress, the two occupied resource
timelines, that machine's type history and busy hours, and the resource-demand window.
A ready candidate that reads none of the changed cells produces the same dispatch key,
so re-estimating it is wasted work. Rather than tracking every write path, the cache
recomputes an O(1) witness of the cells a candidate reads straight from the live state
and reuses the previous key only when the witness is identical.

Fixed-resource candidates read the predecessor end, one machine and one operator
timeline and that machine's type history. Auto-assign candidates read the same
cells for every eligible machine and operator plus busy hours; they consult the demand
window only after two probes tied on (end_time, changeover), which the probe reports
itself. External candidates are cheap and never cached.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple, cast

from core.algorithm_contracts.value_domains import INTERNAL
from core.algorithm_runtime.calendar_timing_memo import MemoizedTimingCalendar, native_timing_calendar
from core.algorithm_runtime.internal_slot import InternalSlotEstimate, refresh_changeover_penalty
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithm_runtime.sgs_shared_slot import SharedSlotEstimateCache

if TYPE_CHECKING:
    from core.algorithm_contracts.types import OpForScheduleAlgo
    from core.models.batch import Batch

    from ..schedule_preparation import NativeSchedulePreparation
    from .sgs_scoring import SgsCandidateScore

_FIXED = "fixed"
_AUTO = "auto"
_UNCLASSIFIED = object()
Witness = Tuple[Any, ...]
EligibleResources = Optional[Tuple[Tuple[str, ...], Tuple[str, ...]]]


def _segments_witness(timeline: Any, resource_id: str) -> Optional[Tuple[int, int]]:
    segments = timeline.get(resource_id)
    # Every mutation path appends one segment; identity guards against wholesale replacement.
    return None if segments is None else (id(segments), len(segments))


def _type_witness(types: Any, machine_id: str) -> Any:
    return types.neighbor_witness(machine_id)


class _Entry:
    __slots__ = ("witness", "demand_revision", "score")

    def __init__(
        self, witness: Witness, demand_revision: Optional[int], score: SgsCandidateScore,
    ) -> None:
        self.witness = witness
        self.demand_revision = demand_revision
        self.score = score


class _PairEntry:
    __slots__ = ("witness", "estimate", "seq")

    def __init__(self, witness: Witness, estimate: InternalSlotEstimate, seq: int) -> None:
        self.witness = witness
        self.estimate = estimate
        # Occupation sequence number when the estimate was last proved current.
        self.seq = seq


class SgsScoreCache:
    """Per-decode memo of candidate scores, validated against the live state on every read.

    Entries are keyed by operation identity: the loop scores the very same objects every round.
    """

    @classmethod
    def for_preparation(
        cls,
        preparation: NativeSchedulePreparation,
        *,
        state: ScheduleRunState,
        auto_assign_enabled: bool,
        resource_pool: Any,
    ) -> SgsScoreCache:
        """Bind the native preparation's eligibility and certified calendar adapters for one SGS decode."""
        calendar = preparation.calendar
        native = native_timing_calendar(calendar)
        return cls(
            state,
            auto_assign_enabled=auto_assign_enabled,
            resource_pool=resource_pool,
            eligible_resources=preparation.eligible_auto_assign_resources,
            timing_calendar=calendar if native else None,
            calendar_days=calendar.add_calendar_days if native else None,
            preparation=preparation,
        )

    def __init__(
        self, state: ScheduleRunState, *, auto_assign_enabled: bool, resource_pool: Any,
        eligible_resources: Callable[[Any], EligibleResources], timing_calendar: Any, calendar_days: Any,
        preparation: NativeSchedulePreparation,
    ) -> None:
        self.state = state
        self.calendar_days = calendar_days
        self.preparation = preparation
        self.hits = 0
        self.misses = 0
        self._reuse_keys = True
        self._saw_auto = False
        self.graph_candidates_pruned = 0
        self.eligible_resources: Optional[Callable[[Any], EligibleResources]] = (
            eligible_resources if (auto_assign_enabled and isinstance(resource_pool, dict)) else None
        )
        self.timing = MemoizedTimingCalendar(timing_calendar) if timing_calendar is not None else None
        self._shared_slots = SharedSlotEstimateCache()
        # Every timeline occupation performed inside this decode, per (timeline identity, resource): (seq, start, end).
        self._occupations: Dict[Tuple[int, str], list] = {}
        self._occupation_seq = 0
        self.pair_revalidated = 0
        self._entries: Dict[int, _Entry] = {}
        # Per operation: False when it can never be cached (external, no native
        # pool), else its eligible auto-assign resources or None for fixed resources.
        self._eligible: Dict[Tuple[int, Optional[str], Optional[str]], Any] = {}
        self.round = 0
        self.pair_hits = 0
        self.pair_misses = 0
        # op identity -> (machine, operator) -> abort-free estimate with its witness; one probe pair reads only these cells.
        self._pairs: Dict[int, Dict[Tuple[str, str], _PairEntry]] = {}

    def stats(self) -> Dict[str, int]:
        timing = self.timing
        return {
            "hits": self.hits, "misses": self.misses, "pair_hits": self.pair_hits, "pair_misses": self.pair_misses,
            "pair_revalidated": self.pair_revalidated,
            "calendar_hits": timing.hits if timing is not None else 0, "calendar_misses": timing.misses if timing is not None else 0,
            "shared_slot_hits": self._shared_slots.hits,
            "shared_slot_misses": self._shared_slots.misses,
            "key_cache_disabled": int(not self._reuse_keys), "graph_candidates_pruned": self.graph_candidates_pruned,
        }

    def scoring_slot_estimate(
        self,
        *,
        op: OpForScheduleAlgo,
        batch: Batch,
        machine_id: str,
        operator_id: str,
        prev_end: Any,
        total_hours: float,
        end_dt_exclusive: Any,
        machine_timeline: Any,
        operator_timeline: Any,
        compute: Callable[[], InternalSlotEstimate],
    ) -> InternalSlotEstimate:
        timing = self.timing
        if timing is not None:
            raw_compute = compute

            def shared_compute() -> InternalSlotEstimate:
                return self._shared_slots.resolve(
                    state=self.state,
                    calendar=timing,
                    op=op,
                    priority=batch.priority,
                    machine_id=machine_id,
                    operator_id=operator_id,
                    prev_end=prev_end,
                    total_hours=total_hours,
                    end_dt_exclusive=end_dt_exclusive,
                    compute=raw_compute,
                )

            slot_compute: Callable[[], InternalSlotEstimate] = shared_compute
        else:
            slot_compute = compute
        estimate = self.pair_estimate(
            op=op,
            machine_id=machine_id,
            operator_id=operator_id,
            prev_end=prev_end,
            machine_timeline=machine_timeline,
            operator_timeline=operator_timeline,
            compute=slot_compute,
        )
        return slot_compute() if estimate is None else estimate

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
        operator_timeline: Any, compute: Callable[[], InternalSlotEstimate],
    ) -> Optional[InternalSlotEstimate]:
        """Abort-free slot estimate of one probe pair, reused while the pair's cells are unchanged.

        Returns None when the memo is not applicable so the caller runs its own estimator; ``compute``
        must estimate the very same pair against the same timelines with ``abort_after=None``.
        """
        state = self.state
        if (not self._reuse_keys or self.eligible_resources is None
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
        estimate = compute()
        self.pair_misses += 1
        pairs[pair] = _PairEntry(witness, estimate, self._occupation_seq)
        return estimate

    def _revalidated(
        self, entry: _PairEntry, witness: Witness, op: OpForScheduleAlgo, machine_id: str, operator_id: str, machine_timeline: Any,
        operator_timeline: Any,
    ) -> Optional[InternalSlotEstimate]:
        """The memoized estimate brought up to date without a new scan, or None when a new scan is required.

        A scan is a deterministic walk steered only by the busy blocks inside its span; new blocks
        that lie entirely outside the span leave every hop, hence the slot, unchanged. Only the
        changeover penalty reads the machine's type history and is recomputed when that changed.
        """
        old = entry.witness
        if old[0] != witness[0]:
            return None
        scan = cast(Tuple[Any, Any], entry.estimate.scan_span)
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
        """One SGS step: saturation may retire key reuse; round-scoped shared slots always reset."""
        self.round += 1
        # Re-scoring remains exact. On a resource shared by every ready operation, repeatedly
        # proving that old keys are stale costs more than recomputing their cheap key suffixes.
        if self.timing is not None:
            if self.round >= 8 and not self._saw_auto and self.hits == 0 and self._shared_slots.hits >= 256:
                self._reuse_keys = False
                self._entries.clear()
                self._pairs.clear()
            self._shared_slots.clear()

    def resolve(
        self, op: OpForScheduleAlgo, batch_id: str, graph_state: Optional[Dict[str, Any]],
        score: Callable[[], SgsCandidateScore],
    ) -> SgsCandidateScore:
        """Reuse the previous score while every cell the candidate reads is unchanged; otherwise score and remember."""
        witness = self._witness(op, batch_id, graph_state)
        entry = self._entries.get(id(op)) if witness is not None else None
        if (entry is not None and witness == entry.witness
                and (entry.demand_revision is None or entry.demand_revision == self._demand_revision())):
            self.hits += 1
            return entry.score
        scored = score()
        self.misses += 1
        if witness is None:
            return scored
        demand_revision = (
            self._demand_revision()
            if witness[0] == _AUTO and scored.pair_tie_occurred
            else None
        )
        self._entries[id(op)] = _Entry(witness, demand_revision, scored)
        return scored

    def _demand_revision(self) -> Optional[int]:
        demand = self.state.last_op_type_by_machine.demand
        return None if demand is None else demand.revision

    def _classify(self, op: OpForScheduleAlgo, machine_id: Optional[str], operator_id: Optional[str]) -> Any:
        if op.source != INTERNAL:
            return False
        if machine_id and operator_id:
            return None
        if self.eligible_resources is None:
            return False
        eligible = self.eligible_resources(op)
        return False if eligible is None else eligible

    def _witness(
        self, op: OpForScheduleAlgo, batch_id: str, graph_state: Optional[Dict[str, Any]],
    ) -> Optional[Witness]:
        machine_id, operator_id = op.machine_id, op.operator_id
        memo_key = (id(op), machine_id, operator_id)
        eligible = self._eligible.get(memo_key, _UNCLASSIFIED)
        if eligible is _UNCLASSIFIED:
            eligible = self._eligible[memo_key] = self._classify(op, machine_id, operator_id)
        if eligible is False:
            return None
        if eligible is not None:
            # Automatic assignment can become cacheable only after its shared resource demand
            # settles. Do not extrapolate fixed-resource zero-hit behavior to that search.
            self._saw_auto = True
            self._reuse_keys = True
        if not self._reuse_keys:
            return None
        state = self.state
        # Piece scope scores against predecessor completion evidence that never changes once the
        # operation is ready; every other scope reads the live batch progress.
        prev_end = (None if graph_state is not None and "end_time_by_op_id" in graph_state
                    else state.batch_progress.get(batch_id, state.base_time))
        types = state.last_op_type_by_machine
        if machine_id and operator_id:  # classified None: the operation names both resources
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
