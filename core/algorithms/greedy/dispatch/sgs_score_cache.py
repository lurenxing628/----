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

from typing import Any, Callable, Dict, NamedTuple, Optional, Tuple

from core.algorithm_contracts.value_domains import INTERNAL
from core.algorithm_runtime.resource_quality import MachineTypeState
from core.algorithm_runtime.run_state import ScheduleRunState

_FIXED = "fixed"
_AUTO = "auto"
_HEAPTYPE = 1 << 9  # Py_TPFLAGS_HEAPTYPE: only Python-level classes can carry accessor hooks
_UNCLASSIFIED = object()
# Every operation and batch field the dispatch key can depend on; a class-level accessor hook
# or descriptor on any of them means reads may vary between steps, so such records are never cached.
_RECORD_FIELDS = (
    "id", "seq", "batch_id", "piece_id", "source", "machine_id", "operator_id", "op_type_id", "op_type_name",
    "setup_hours", "unit_hours", "quantity", "priority", "due_date", "ready_date", "ready_status", "created_at",
)
_AUTO_ASSIGN_CALLBACKS = (
    ("auto_assign_callback", "_auto_assign_internal_resources"),
    ("auto_assign_attempt_callback", "_auto_assign_internal_resources_attempt"),
)
Witness = Tuple[Any, ...]
EligibleResources = Optional[Tuple[Tuple[str, ...], Tuple[str, ...]]]


class AutoAssignProbeContract(NamedTuple):
    """What the parent package tells the cache about its auto-assign probe; dispatch never imports it."""

    eligible_resources: Callable[[Any, Any], EligibleResources]
    natives_intact: Callable[[], bool]


def native_auto_assign_context(ctx: Any, scheduler: Any, native_type: type) -> bool:
    """Both auto-assign callbacks are the untouched methods of ``native_type`` bound to ``scheduler``."""
    for field, name in _AUTO_ASSIGN_CALLBACKS:
        callback = getattr(ctx, field, None)
        if getattr(callback, "__self__", None) is not scheduler:
            return False
        if getattr(callback, "__func__", None) is not vars(native_type).get(name):
            return False
    return True


def attach_sgs_score_cache(
    ctx: Any, scheduler: Any, native_type: type, *, state: ScheduleRunState, params: Any, resource_pool: Any,
    probe: AutoAssignProbeContract,
) -> None:
    """Give the SGS loop its per-decode cache through the context; batch-order dispatch never scores candidates."""
    if params.dispatch_mode_key != "sgs":
        return
    ctx.sgs_score_cache = SgsScoreCache(
        state,
        auto_assign_enabled=bool(params.auto_assign_enabled),
        resource_pool=resource_pool,
        native_auto_assign=native_auto_assign_context(ctx, scheduler, native_type),
        probe=probe,
    )


def sgs_score_cache_stats(cache: Any) -> Dict[str, int]:
    return cache.stats() if cache is not None else {"hits": 0, "misses": 0, "pair_hits": 0, "pair_misses": 0}


def plain_record_class(cls: Any) -> bool:
    """Instance attribute reads on ``cls`` are the builtin path: no accessor hooks, no field descriptors."""
    if type(cls) is not type:
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


class SgsScoreCache:
    """Per-decode memo of dispatch keys, validated against the live state on every read.

    Entries are keyed by operation identity: the loop scores the very same objects every round.
    """

    def __init__(
        self, state: ScheduleRunState, *, auto_assign_enabled: bool, resource_pool: Any, native_auto_assign: bool,
        probe: AutoAssignProbeContract,
    ) -> None:
        self.state = state
        self.hits = 0
        self.misses = 0
        self._probe = probe
        self._pool = resource_pool if (auto_assign_enabled and native_auto_assign and isinstance(resource_pool, dict)) else None
        self._entries: Dict[int, _Entry] = {}
        # Per operation: False when it can never be cached (external, hooked record classes, no native
        # pool), else its eligible auto-assign resources or None for fixed resources.
        self._eligible: Dict[Tuple[int, str, str], Any] = {}
        self._plain_classes: Dict[type, bool] = {}
        self.round = 0
        self.pair_hits = 0
        self.pair_misses = 0
        # (op identity, machine, operator) -> (witness, abort-free estimate); one probe pair reads only these cells.
        self._pairs: Dict[Tuple[int, str, str], Tuple[Witness, Any]] = {}
        self._scoring_op: Any = None
        self._pending_tie: Optional[bool] = None
        self._pending_resources: Optional[Tuple[str, str]] = None
        self._pending_estimate: Optional[Tuple[Any, ...]] = None

    def stats(self) -> Dict[str, int]:
        return {"hits": self.hits, "misses": self.misses, "pair_hits": self.pair_hits, "pair_misses": self.pair_misses}

    def forget(self, op: Any) -> None:
        """A dispatched operation never becomes a candidate again."""
        self._entries.pop(id(op), None)
        if self._pairs:
            for key in [key for key in self._pairs if key[0] == id(op)]:
                del self._pairs[key]

    def pair_estimate(
        self, *, op: Any, machine_id: str, operator_id: str, prev_end: Any, machine_timeline: Any, operator_timeline: Any,
        compute: Callable[[], Any],
    ) -> Any:
        """Abort-free slot estimate of one probe pair, reused while the pair's cells are unchanged.

        Returns None when the memo is not applicable so the caller runs its own estimator; ``compute``
        must estimate the very same pair against the same timelines with ``abort_after=None``.
        """
        state = self.state
        if self._pool is None or machine_timeline is not state.machine_timeline or operator_timeline is not state.operator_timeline:
            return None
        witness = (
            prev_end,
            _segments_witness(machine_timeline, machine_id),
            _segments_witness(operator_timeline, operator_id),
            _type_witness(state.last_op_type_by_machine, machine_id),
        )
        key = (id(op), machine_id, operator_id)
        entry = self._pairs.get(key)
        if entry is not None and entry[0] == witness:
            self.pair_hits += 1
            return entry[1]
        estimate = compute()
        self.pair_misses += 1
        self._pairs[key] = (witness, estimate)
        return estimate

    def next_round(self) -> None:
        """One SGS step: entries proved in earlier rounds no longer qualify for placement handoff."""
        self.round += 1

    def begin_round(self) -> bool:
        """Auto-assign keys may only be reused while the probe still runs the module's own code."""
        if self._pool is not None and not self._probe.natives_intact():
            self._pool = None
            self._eligible = {}
        return True

    def record_attempt(self, attempt: Any) -> None:
        """Sink for the probe result of the candidate currently being scored."""
        self._pending_tie = getattr(attempt, "pair_tie_occurred", None)
        machine_id = str(getattr(attempt, "machine_id", "") or "")
        operator_id = str(getattr(attempt, "operator_id", "") or "")
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
        if entry is None or entry.round != self.round or entry.estimate is None:
            return None
        estimate, total_hours_base, machine_id, operator_id, prev_end, calendar, end_dt_exclusive = entry.estimate
        if (inputs.get("machine_id"), inputs.get("operator_id")) != (machine_id, operator_id):
            return None
        if inputs.get("prev_end") != prev_end or inputs.get("calendar") is not calendar:
            return None
        if inputs.get("end_dt_exclusive") != end_dt_exclusive:
            return None
        return estimate, total_hours_base

    def selected_resources(self, op: Any) -> Optional[Tuple[str, str]]:
        """Auto-assign pair the scoring probe chose for ``op``, valid only within the same round."""
        entry = self._entries.get(id(op))
        if entry is None or entry.round != self.round or entry.witness[0] != _AUTO:
            return None
        return entry.resources

    def resolve(
        self, op: Any, batch: Any, batch_id: str, graph_state: Optional[Dict[str, Any]], score: Callable[[], Tuple[float, ...]],
    ) -> Tuple[float, ...]:
        """Reuse the previous key while every cell the candidate reads is unchanged; otherwise score and remember."""
        witness = self._witness(op, batch, batch_id, graph_state)
        entry = self._entries.get(id(op)) if witness is not None else None
        if (entry is not None and witness == entry.witness
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
        cls = type(record)
        if cls not in self._plain_classes:
            self._plain_classes[cls] = plain_record_class(cls)
        return self._plain_classes[cls]

    def _classify(self, op: Any, batch: Any, machine_id: str, operator_id: str) -> Any:
        if not self._plain(op) or not self._plain(batch):
            return False
        if str(getattr(op, "source", INTERNAL) or INTERNAL).strip().lower() != INTERNAL:
            return False
        if machine_id and operator_id:
            return None
        if self._pool is None:
            return False
        eligible = self._probe.eligible_resources(op, self._pool)
        return False if eligible is None else eligible

    def _witness(self, op: Any, batch: Any, batch_id: str, graph_state: Optional[Dict[str, Any]]) -> Optional[Witness]:
        machine_id = str(getattr(op, "machine_id", None) or "").strip()
        operator_id = str(getattr(op, "operator_id", None) or "").strip()
        memo_key = (id(op), machine_id, operator_id)
        eligible = self._eligible.get(memo_key, _UNCLASSIFIED)
        if eligible is _UNCLASSIFIED:
            eligible = self._eligible[memo_key] = self._classify(op, batch, machine_id, operator_id)
        if eligible is False:
            return None
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
