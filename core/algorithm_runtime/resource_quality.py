"""Run-owned resource quality evidence; borrowed legacy maps keep their semantics."""
from __future__ import annotations

from bisect import bisect_left, insort
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .owned_timeline import OwnedTypeEntries, owned_type_certificate
from .resource_demand import ResourceDemand
from .static_attribute import static_attribute, static_class_attribute

TypeEntry = Tuple[datetime, datetime, int, str]


class MachineTypeState(Dict[str, str]):
    """The existing tail map, plus actual machine neighbors from recorded results."""

    def __init__(self) -> None:
        super().__init__()
        self._entries: Dict[str, List[TypeEntry]] = {}
        self.demand: Optional[ResourceDemand] = None
        # Lifecycle events already applied to ``demand``: ("complete", op_id) / ("block_batch", batch_id).
        # A decode resumed from a checkpoint rebuilds the demand for its own operation objects and
        # replays these, because demand records are keyed by operation identity, not op_id.
        self.demand_events: List[Tuple[str, Any]] = []

    def clone(self) -> MachineTypeState:
        """Snapshot for a decode checkpoint: tail map, neighbour rows and demand events; no live demand."""
        clone = MachineTypeState()
        clone.update(self)
        for machine_id, entries in self._entries.items():
            clone._entries[machine_id] = OwnedTypeEntries(entries)
        clone.demand_events = list(self.demand_events)
        return clone

    def replay_demand_events(self) -> None:
        """Bring a freshly initialised demand up to the recorded lifecycle point."""
        if self.demand is None:
            return
        for kind, key in list(self.demand_events):
            if kind == "complete":
                self.demand.complete(key)
            elif kind == "block_batch":
                self.demand.block_batch(key)
            else:
                raise ValueError("unknown demand event: " + str(kind))

    def record(self, machine_id: str, start: Optional[datetime], end: datetime, op_id: Optional[int], op_type: str) -> None:
        if type(start) is datetime and type(end) is datetime and type(op_id) is int and op_id > 0 and op_type and end >= start:
            owned: Any = OwnedTypeEntries()
            insort(self._entries.setdefault(machine_id, owned), (start, end, op_id, op_type))

    def neighbor_witness(self, machine_id: str) -> Tuple[int, Optional[str]]:
        """O(1) change witness for one machine: recorded neighbor count plus the tail type."""
        entries = self._entries.get(machine_id)
        return (len(entries) if entries is not None else 0), self.get(machine_id)

    def certificate(self, machine_id: str) -> Tuple[TypeEntry, ...]:
        """Content certificate for consumers whose cached scores depend on neighbors."""
        return tuple(self._entries.get(machine_id, ()))

    def score_certificate(self, machine_id: str):
        """Only a run-owned sequence with a complete mutation protocol earns a version."""
        entries = self._entries.get(machine_id)
        return () if entries is None else owned_type_certificate(entries)

    def insertion_penalty(self, machine_id: str, start: datetime, end: datetime, op_id: int, op_type: str) -> int:
        if not op_type:
            return 0
        entries = self._entries.get(machine_id, [])
        index = bisect_left(entries, (start, end, op_id, op_type))
        before = entries[index - 1][3] if index else ""
        after = entries[index][3] if index < len(entries) else ""
        old = int(bool(before and after and before != after))
        return int(bool(before and before != op_type)) + int(bool(after and after != op_type)) - old

    def complete(self, op_id: int) -> None:
        if self.demand is not None:
            self.demand_events.append(("complete", op_id))
            self.demand.complete(op_id)

    def block_batch(self, batch_id: str) -> None:
        if self.demand is not None:
            self.demand_events.append(("block_batch", batch_id))
            self.demand.block_batch(batch_id)


def _plain_operation_type(op: Any) -> Optional[Tuple[int, str]]:
    # Do not add dynamic field reads to callback/descriptor-bearing legacy inputs.
    if type(op) is SimpleNamespace:
        # The exact builtin has an immutable class and a native instance dict.
        # Read both current values each time; identity/length is not a certificate.
        fields = op.__dict__
        op_id, op_type = fields.get("id"), fields.get("op_type_name")
    else:
        accessor = static_class_attribute(type(op), "__getattribute__")
        if accessor is not object.__getattribute__ and accessor is not SimpleNamespace.__getattribute__:
            return None
        op_id = static_attribute(op, "id")
        op_type = static_attribute(op, "op_type_name")
    if type(op_id) is not int or op_id <= 0 or type(op_type) is not str:
        return None
    return op_id, op_type.strip()


def slot_changeover_penalty(
    state: Optional[Mapping[str, str]], *, op: Any, machine_id: str,
    start: datetime, end: datetime, legacy_penalty: int,
) -> int:
    if not isinstance(state, MachineTypeState):
        return legacy_penalty
    if type(start) is not datetime or type(end) is not datetime:
        return legacy_penalty
    entries = state._entries.get(machine_id)
    if not entries or (start > entries[-1][0] and entries[-1][3] == state.get(machine_id)):
        # Appending has the same predecessor as the established tail-map rule.
        # Equal-time/overlapping seeds can have a different chronological tail.
        # Only an insertion or such a mismatch needs native identity checks.
        return legacy_penalty
    identity = _plain_operation_type(op)
    if identity is None:
        return legacy_penalty
    return state.insertion_penalty(machine_id, start, end, identity[0], identity[1])


def prefer_resource_pair(state: Mapping[str, str], op: Any, candidate: Tuple[Any, ...], best: Tuple[Any, ...]) -> bool:
    if candidate[:2] != best[:2] or not isinstance(state, MachineTypeState) or state.demand is None:
        return candidate < best
    pairs = ((candidate[-2], candidate[-1]), (best[-2], best[-1]))
    if state.demand.comparison_is_neutral(op, *pairs):
        return candidate < best
    # Certify only hints that could change this choice. Equal unverified hints
    # and a failed certificate both preserve the original tie breaker.
    penalties = state.demand.penalties(op, pairs)
    return (penalties[0],) + candidate[2:] < (penalties[1],) + best[2:]


def initialize_resource_quality(state: Any, operations: List[Any], resource_pool: Any) -> None:
    types = state.last_op_type_by_machine
    if isinstance(types, MachineTypeState) and resource_pool is not None:
        types.demand = ResourceDemand(operations, resource_pool)
