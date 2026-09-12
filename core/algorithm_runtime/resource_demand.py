"""Bounded resource reservation hints for one already ordered dispatch run.

Only plain input values are inspected. This is a tie breaker, not a resource
validator: unsupported inputs retain the existing dispatch validation path.
"""

from collections import Counter, deque
from dataclasses import dataclass
from inspect import getattr_static
from types import GetSetDescriptorType, MemberDescriptorType, SimpleNamespace
from typing import Any, Dict, FrozenSet, Optional, Tuple

_MISSING = object()
_FIELDS = ("id", "batch_id", "piece_id", "source", "machine_id", "operator_id", "op_type_id")
_RELATIONS = ("machines_by_op_type", "operators_by_machine", "machines_by_operator")
_PLAIN_GETATTRIBUTE = (object.__getattribute__, SimpleNamespace.__getattribute__)
_WINDOW_SIZE = 64


def _plain_class(cls: Any) -> bool:
    if type(cls) is not type:
        return False
    method = getattr_static(cls, "__getattribute__", None)
    if all(method is not allowed for allowed in _PLAIN_GETATTRIBUTE):
        return False
    if getattr_static(cls, "__getattr__", _MISSING) is not _MISSING:
        return False
    descriptor = getattr_static(cls, "__dict__", None)
    if type(descriptor) not in (GetSetDescriptorType, MemberDescriptorType):
        return False
    return all(getattr_static(type(getattr_static(cls, name, _MISSING)), "__get__", _MISSING) is _MISSING for name in _FIELDS)


def _plain_fields(op: Any) -> Optional[Dict[str, Any]]:
    try:
        values = object.__getattribute__(op, "__dict__")
    except (AttributeError, TypeError):
        return None
    if type(values) is not dict or any(type(key) is not str for key in values):
        return None
    snapshot = {}
    for name in _FIELDS:
        if name not in values and getattr_static(type(op), name, None) is not None:
            return None
        value = values.get(name)
        if type(value) not in (str, int, type(None)):
            return None
        snapshot[name] = value
    return snapshot


def _fields_match(record: Any) -> bool:
    try:
        values = object.__getattribute__(record.op, "__dict__")
    except (AttributeError, TypeError):
        return False
    if type(values) is not dict or any(type(key) is not str for key in values):
        return False
    for name, expected in record.fields.items():
        value = values.get(name, _MISSING)
        if value is _MISSING:
            if expected is not None or getattr_static(type(record.op), name, None) is not None:
                return False
        elif value is not expected and (type(value) not in (str, int, type(None)) or value != expected):
            return False
    return True


def _text(value: Any) -> str:
    return str(value).strip() if value else ""


def _native_pair(pair: Any) -> bool:
    return type(pair) in (list, tuple) and len(pair) == 2 and all(type(value) is str for value in pair)


def _pool_snapshot(pool: Any) -> Optional[Dict[str, Dict[str, Tuple[str, ...]]]]:
    if type(pool) is not dict or any(type(key) is not str for key in pool):
        return None
    result = {}
    for name in _RELATIONS:
        relation = pool.get(name, {})
        if type(relation) is not dict:
            relation = {}
        if any(type(key) is not str for key in relation):
            return None
        frozen = {}
        for key, values in relation.items():
            if values is None:
                values = ()
            if type(values) not in (list, tuple):
                return None
            if any(type(value) not in (str, int) for value in values):
                return None
            frozen[key] = tuple(str(value) for value in values if str(value).strip())
        result[name] = frozen
    return result


def _machine_candidates(machine: str, operator: str, op_type: str, pool: Dict[str, Any]) -> Tuple[str, ...]:
    if machine:
        return (machine,)
    if not operator:
        return pool["machines_by_op_type"].get(op_type, ())
    candidates = pool["machines_by_operator"].get(operator, ())
    if candidates:
        return candidates
    return tuple(mid.strip() for mid, operators in pool["operators_by_machine"].items() if any(oid.strip() == operator for oid in operators))


def _filter_machine_type(candidates: Tuple[str, ...], machine: str, op_type: str, by_type: Dict[str, Any]) -> Tuple[str, ...]:
    if not op_type or (machine and op_type not in by_type):
        return candidates
    allowed = {mid.strip() for mid in by_type.get(op_type, ())}
    return tuple(mid for mid in candidates if mid in allowed)


def _qualified_pairs(fields: Dict[str, Any], pool: Dict[str, Any]) -> FrozenSet[Tuple[str, str]]:
    if _text(fields["source"]).lower() != "internal":
        return frozenset()
    machine, operator, op_type = (_text(fields[name]) for name in ("machine_id", "operator_id", "op_type_id"))
    if not machine and not op_type:
        return frozenset()
    candidates = _machine_candidates(machine, operator, op_type, pool)
    candidates = _filter_machine_type(candidates, machine, op_type, pool["machines_by_op_type"])
    return frozenset(
        (mid, oid)
        for mid in candidates
        for oid in pool["operators_by_machine"].get(mid, ())
        if not operator or oid == operator
    )


@dataclass(frozen=True)
class _Demand:
    op: Any
    fields: Dict[str, Any]
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

    ``operations`` must be the dispatch run's already ordered plain list/tuple.
    Completion/failure owners must call ``complete`` or ``block_batch``.
    ``revision`` versions lifecycle and disable events, not external input
    immutability; it must not alone authorize reuse of a whole scheduling score.
    """

    def __init__(self, operations: Any, resource_pool: Any) -> None:
        self.revision = 0
        self.fallback_reason = ""
        self._groups = {}  # type: Dict[Tuple[str, Optional[str]], Any]
        self._by_id = {}  # type: Dict[Any, Any]
        self._by_token = {}  # type: Dict[int, _Demand]
        self._by_batch = {}  # type: Dict[str, Any]
        self._window_revision = -1
        self._window_tokens = set()
        self._window = ()
        self._blocking_counts = {}  # type: Dict[Tuple[str, str], int]
        self._resource_pool = resource_pool
        self._pool = _pool_snapshot(resource_pool)
        if self._pool is None or type(operations) not in (list, tuple):
            self.fallback_reason = "unsupported_resource_pool" if self._pool is None else "unsupported_operations"
            return
        plain_classes = {}
        for op in operations:
            cls = type(op)
            if id(cls) not in plain_classes:
                plain_classes[id(cls)] = _plain_class(cls)
            if not plain_classes[id(cls)]:
                continue
            fields = _plain_fields(op)
            if fields is not None:
                self._add(op, fields, self._pool)

    def _add(self, op: Any, fields: Dict[str, Any], pool: Dict[str, Any]) -> None:
        op_id, batch_id, piece_id = fields["id"], _text(fields["batch_id"]), fields["piece_id"]
        # Result/failure lifecycle events carry positive integer identities.
        # Other input forms keep the original dispatch conversion/validation.
        if type(op_id) is not int or op_id <= 0 or not batch_id:
            return
        if piece_id is not None and (type(piece_id) is not str or not piece_id or piece_id.strip() != piece_id):
            return
        pairs = _qualified_pairs(fields, pool)
        group = (batch_id, piece_id)
        record = _Demand(op, fields, id(op), op_id, batch_id, group, pairs, Counter(mid for mid, _ in pairs), Counter(oid for _, oid in pairs))
        self._groups.setdefault(group, deque()).append(record)
        self._by_id.setdefault(op_id, []).append(record)
        self._by_token[record.token] = record
        self._by_batch.setdefault(batch_id, set()).add(group)

    def penalty(self, op: Any, machine_id: str, operator_id: str) -> float:
        return self.penalties(op, ((machine_id, operator_id),))[0]

    def comparison_is_neutral(self, op: Any, first: Tuple[str, str], second: Tuple[str, str]) -> bool:
        """No input certificate is needed when neither outcome can prefer a pair.

        Equal stored hints and disabled/stale hints both retain the original tie
        breaker. This does not certify inputs or update fallback diagnostics;
        any later comparison with unequal hints must still call ``penalties``.
        """
        if not _native_pair(first) or not _native_pair(second):
            return True
        current = self._by_token.get(id(op))
        if self.fallback_reason or current is None:
            return True
        self._refresh_window()
        return self._score(current, *first) == self._score(current, *second)

    def penalties(self, op: Any, pairs: Tuple[Tuple[str, str], ...]) -> Tuple[float, ...]:
        """Compare tied pairs against one fresh, callback-free certificate."""
        if type(pairs) not in (list, tuple):
            return ()
        zeroes = tuple(0.0 for _ in pairs)
        if not all(_native_pair(pair) for pair in pairs):
            return zeroes
        current = self._by_token.get(id(op))
        if self.fallback_reason or current is None:
            return zeroes
        self._refresh_window()
        if not self._certify(current):
            return zeroes
        return tuple(self._score(current, mid, oid) for mid, oid in pairs)

    def _score(self, current: _Demand, machine_id: str, operator_id: str) -> float:
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

    def _certify(self, current: _Demand) -> bool:
        reason = ""
        if _pool_snapshot(self._resource_pool) != self._pool:
            reason = "resource_pool_changed"
        else:
            records = self._window if current.token in self._window_tokens else self._window + (current,)
            plain_classes = {}
            for record in records:
                cls = type(record.op)
                if id(cls) not in plain_classes:
                    plain_classes[id(cls)] = _plain_class(cls)
                if not plain_classes[id(cls)] or not _fields_match(record):
                    reason = "operation_input_changed"
                    break
        if reason:
            self.fallback_reason = reason
            self.revision += 1
        return not reason

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
        # External input evidence is still certified before a hint can decide.
        self._blocking_counts = {}
        for pending in self._groups.values():
            if len(self._window_tokens) == _WINDOW_SIZE:
                break
            record = pending[0]
            window.append(record)
            self._window_tokens.add(record.token)
        self._window = tuple(window)
        self._window_revision = self.revision
