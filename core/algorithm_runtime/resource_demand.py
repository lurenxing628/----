"""Live bounded resource reservation hints over prepared static eligibility claims."""

from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Optional, Tuple

from core.algorithm_contracts.types import OpForScheduleAlgo

_WINDOW_SIZE = 64


def _text(value: Any) -> str:
    return str(value).strip() if value else ""


@dataclass(frozen=True)
class ResourceClaim:
    token: int
    op_id: Any
    batch_id: str
    group: Tuple[str, Optional[str]]
    pairs: FrozenSet[Tuple[str, str]]
    machines: Dict[str, int]
    operators: Dict[str, int]

    def blocks_all_pairs(self, machine_id: str, operator_id: str) -> bool:
        if not self.pairs:
            return False
        count = self.machines.get(machine_id, 0) + self.operators.get(operator_id, 0)
        return count - int((machine_id, operator_id) in self.pairs) == len(self.pairs)


class ResourceDemand:
    """Reserve the next operation of at most 64 distinct batch/piece chains.

    Only removal of every qualified pair counts as a reservation hint. Losing
    some alternatives is neutral; no global schedule improvement is implied.

    Static claims belong to NativeSchedulePreparation and arrive in dispatch order.
    Completion/failure owners advance only this decode's live claim window.
    """

    def __init__(self, claims: Any) -> None:
        self.revision = 0
        self._groups = {}  # type: Dict[Tuple[str, Optional[str]], Any]
        self._by_id = {}  # type: Dict[Any, Any]
        self._by_token = {}  # type: Dict[int, ResourceClaim]
        self._by_batch = {}  # type: Dict[str, Any]
        self._window_revision = -1
        self._window_tokens = set()
        self._window = ()
        self._blocking_counts = {}  # type: Dict[Tuple[str, str], int]
        for record in claims:
            self._groups.setdefault(record.group, deque()).append(record)
            self._by_id.setdefault(record.op_id, []).append(record)
            self._by_token[record.token] = record
            self._by_batch.setdefault(record.batch_id, set()).add(record.group)

    def comparison_is_neutral(self, op: OpForScheduleAlgo, first: Tuple[str, str], second: Tuple[str, str]) -> bool:
        """Skip equal reservation hints before forming the tie-break score."""
        current = self._by_token.get(id(op))
        if current is None:
            return True
        self._refresh_window()
        return self._score(current, *first) == self._score(current, *second)

    def penalties(self, op: OpForScheduleAlgo, pairs: Tuple[Tuple[str, str], ...]) -> Tuple[float, ...]:
        """Compare tied pairs against the current decode window."""
        current = self._by_token.get(id(op))
        if current is None:
            return tuple(0.0 for _ in pairs)
        self._refresh_window()
        return tuple(self._score(current, mid, oid) for mid, oid in pairs)

    def _score(self, current: ResourceClaim, machine_id: str, operator_id: str) -> float:
        # Losing some alternatives is not the same as blocking a ready head.
        # Count only heads whose every qualified pair conflicts with this pair.
        # This remains a bounded, local hint; it predicts no global due-date gain.
        pair = (machine_id, operator_id)
        if pair not in self._blocking_counts:
            self._blocking_counts[pair] = sum(record.blocks_all_pairs(machine_id, operator_id) for record in self._window)
        count = self._blocking_counts[pair]
        if current.token in self._window_tokens:
            count -= int(current.blocks_all_pairs(machine_id, operator_id))
        return float(count)

    def complete(self, op_id: Any) -> None:
        if type(op_id) not in (str, int):
            return
        records = self._by_id.pop(op_id, ())
        changed = False
        for record in records:
            changed = self._by_token.pop(record.token, None) is not None or changed
            pending = self._groups.get(record.group)
            if pending is None:
                continue
            while pending and pending[0].token not in self._by_token:
                pending.popleft()
            if not pending:
                del self._groups[record.group]
        if changed:
            self.revision += 1

    def block_batch(self, batch_id: Any) -> None:
        if type(batch_id) not in (str, int):
            return
        changed = False
        for group in self._by_batch.pop(_text(batch_id), ()):
            for record in self._groups.pop(group, ()):
                changed = self._by_token.pop(record.token, None) is not None or changed
        if changed:
            self.revision += 1

    def _refresh_window(self) -> None:
        if self._window_revision == self.revision:
            return
        self._window_tokens = set()
        window = []
        # These counts derive only from the current run-owned immutable claims.
        self._blocking_counts = {}
        for pending in self._groups.values():
            if len(self._window_tokens) == _WINDOW_SIZE:
                break
            record = pending[0]
            window.append(record)
            self._window_tokens.add(record.token)
        self._window = tuple(window)
        self._window_revision = self.revision
