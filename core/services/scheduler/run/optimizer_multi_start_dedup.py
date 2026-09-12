"""Skip equivalent native decodes inside one multi-start read transaction.

A complete batch-order override makes the sort strategy irrelevant to dispatch,
but its parameter validation still runs. This is a decision cache, never an
output-fingerprint cache. Adapted schedulers/calendars and unknown input objects
remain on the ordinary evaluation path.
"""

from __future__ import annotations

import math
import sqlite3
from datetime import date, datetime, time
from types import SimpleNamespace
from typing import Any, Dict, Optional, Tuple

from core.algorithm_contracts.sort_strategies import SortStrategy, StrategyFactory
from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary
from core.algorithm_runtime.sgs_estimate_reuse import native_multi_start_calendar_snapshot
from core.algorithms.greedy.schedule_params import resolve_schedule_params
from core.algorithms.greedy.scheduler import GreedyScheduler
from core.models.batch import Batch
from core.models.batch_operation import BatchOperation
from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot as RuntimeSnapshot
from core.services.scheduler.config.config_snapshot import ScheduleConfigSnapshot

from .schedule_input_builder import OpForScheduleAlgo

_UNSUPPORTED = object()
_RECORD_TYPES = (SimpleNamespace, Batch, BatchOperation, OpForScheduleAlgo,
                 ScheduleResult, ScheduleConfigSnapshot, RuntimeSnapshot)
_STRATEGIES = dict(StrategyFactory._strategies)
_NATIVE_TYPES = _RECORD_TYPES + tuple(_STRATEGIES.values()) + (GreedyScheduler, StrategyFactory)
_CLASS_MEMBERS = {cls: tuple(cls.__dict__.items()) for cls in _NATIVE_TYPES}
_CLASS_LINEAGES = {cls: cls.__mro__ for cls in _NATIVE_TYPES}
DecisionKey = Optional[Tuple[Any, ...]]


def _native_class(cls: type) -> bool:
    members = _CLASS_MEMBERS[cls]
    return (cls.__mro__ is _CLASS_LINEAGES[cls] and len(cls.__dict__) == len(members)
            and all(cls.__dict__.get(key) is value for key, value in members))


def _native_instance(value: Any, cls: type) -> bool:
    if type(value) is not cls or not _native_class(cls):
        return False
    # An instance-level callback must not disappear behind a cache hit.
    names = {key for base in cls.__mro__ for key, member in base.__dict__.items()
             if callable(member) or isinstance(member, (classmethod, staticmethod, property))}
    return names.isdisjoint(vars(value))


def _freeze(value: Any, ancestors: Optional[set] = None) -> Any:
    """Value snapshots for native containers/records only; never invoke user hooks."""
    kind = type(value)
    if value is None or kind in (str, int, bool):
        return kind, value
    if kind is float:
        return (kind, value) if math.isfinite(value) else _UNSUPPORTED
    if kind in (datetime, time):
        return (kind, value) if value.tzinfo is None else _UNSUPPORTED
    if kind is date:
        return kind, value
    if kind not in (dict, list, tuple, set, frozenset) + _RECORD_TYPES:
        return _UNSUPPORTED
    active = set() if ancestors is None else ancestors
    marker = id(value)
    if marker in active:
        return _UNSUPPORTED
    active.add(marker)
    try:
        return _freeze_compound(value, kind, active)
    finally:
        active.remove(marker)


def _freeze_compound(value: Any, kind: type, active: set) -> Any:
    if kind in _RECORD_TYPES:
        if not _native_instance(value, kind):
            return _UNSUPPORTED
        payload = _freeze(vars(value), active)
        return _UNSUPPORTED if payload is _UNSUPPORTED else (kind, payload)
    if kind is dict:
        pairs = tuple((_freeze(key, active), _freeze(item, active)) for key, item in value.items())
        if any(key is _UNSUPPORTED or item is _UNSUPPORTED for key, item in pairs):
            return _UNSUPPORTED
        # Preserve dictionary iteration order, which some dispatch inputs use.
        return kind, pairs
    items = tuple(_freeze(item, active) for item in value)
    if any(item is _UNSUPPORTED for item in items):
        return _UNSUPPORTED
    return kind, frozenset(items) if kind in (set, frozenset) else items


def _calendar_snapshot(calendar: Any) -> Any:
    # The calendar owner registers this certificate when its class is defined.
    # Importing this helper after an override must not certify the override.
    certified = native_multi_start_calendar_snapshot(calendar)
    if certified is None:
        return _UNSUPPORTED
    engine, conn, policies = certified
    if type(conn) is not sqlite3.Connection:
        return _UNSUPPORTED
    if conn.row_factory is not None and conn.row_factory is not sqlite3.Row:
        return _UNSUPPORTED
    database = _database_snapshot(conn)
    if database is _UNSUPPORTED:
        return _UNSUPPORTED
    return (id(calendar), id(engine), database), policies


def _database_snapshot(conn: sqlite3.Connection) -> Any:
    try:
        if not conn.in_transaction:
            return _UNSUPPORTED
        row = conn.execute("PRAGMA data_version").fetchone()
        if row is None or type(row[0]) is not int:
            return _UNSUPPORTED
        return id(conn), conn.total_changes, row[0]
    except sqlite3.Error:
        # A caller's SQLite authorizer may reject this optional cache probe.
        # Evaluate normally, preserving all errors from the real decoder.
        return _UNSUPPORTED


def _complete_order(order: Any, batches: Any) -> bool:
    if type(order) is not list or type(batches) is not dict or not batches:
        return False
    if len(order) != len(batches) or not _canonical_ids(order) or not _canonical_ids(batches):
        return False
    if len(set(order)) != len(order) or set(order) != set(batches):
        return False
    return all(type(batch) in _RECORD_TYPES and vars(batch).get("batch_id") == key
               for key, batch in batches.items())


def _canonical_ids(items: Any) -> bool:
    return all(type(item) is str and item == item.strip() and bool(item) for item in items)


def _native_strategies() -> bool:
    current = StrategyFactory._strategies
    return (type(current) is dict and len(current) == len(_STRATEGIES)
            and all(type(key) is SortStrategy and value is _STRATEGIES.get(key) for key, value in current.items())
            and all(_native_class(cls) for cls in _STRATEGIES.values()))


class MultiStartDecisionCache:
    """Run-local native fast path. Call remember only after a real decode returns.

    The owner must create one cache per _run_multi_start call, inside the same
    read transaction, and still build/validate each strategy's requested order.
    Keys are opaque; None always means evaluate normally.
    """

    def __init__(self, *, scheduler: Any, strict_mode: bool, operations: Any, batches: Any,
                 start_dt: Any, end_date: Any, downtime_map: Any, seed_results: Any,
                 resource_pool: Any, readiness_gate_enabled: bool, graph_ready_context: Any) -> None:
        self.scheduler = scheduler
        self.strict_mode = strict_mode
        self.batches = batches
        self.start_dt = start_dt
        self.end_date = end_date
        self.resource_pool = resource_pool
        self.inputs = (operations, batches, start_dt, end_date, downtime_map, seed_results,
                       resource_pool, readiness_gate_enabled, graph_ready_context)
        self._seen: set = set()

    def _context(self) -> Any:
        if self.strict_mode is not True or not _native_instance(self.scheduler, GreedyScheduler):
            return _UNSUPPORTED
        if type(self.start_dt) is not datetime or self.start_dt.tzinfo is not None:
            return _UNSUPPORTED
        inputs = _freeze((self.inputs, self.scheduler.config))
        if inputs is _UNSUPPORTED:
            return _UNSUPPORTED
        calendar = _calendar_snapshot(self.scheduler.calendar)
        if calendar is _UNSUPPORTED:
            return _UNSUPPORTED
        return inputs, calendar

    def decision_key(self, strategy: Any, params: Any, dispatch_mode: Any,
                     dispatch_rule: Any, order: Any) -> DecisionKey:
        context = self._context()
        if context is _UNSUPPORTED or not _complete_order(order, self.batches):
            return None
        if (type(strategy) is not SortStrategy or type(params) is not dict
                or type(dispatch_mode) is not str or type(dispatch_rule) is not str
                or _freeze(params) is _UNSUPPORTED or not _native_class(StrategyFactory)
                or not _native_strategies()):
            return None
        # Match schedule() parameter validation for every strategy, even when
        # the complete override bypasses strategy sorting inside the decoder.
        resolved = resolve_schedule_params(
            config=self.scheduler.config, strategy=strategy, strategy_params=params,
            start_dt=self.start_dt, end_date=self.end_date, dispatch_mode=dispatch_mode,
            dispatch_rule=dispatch_rule, resource_pool=self.resource_pool, strict_mode=True,
        )
        StrategyFactory.create(resolved.strategy, **resolved.used_params).get_name()
        decision = (resolved.dispatch_mode_key, resolved.dispatch_rule_enum.value,
                    resolved.base_time, resolved.end_dt_exclusive, resolved.auto_assign_enabled, tuple(order))
        return context, decision

    def has(self, key: DecisionKey) -> bool:
        return key is not None and key in self._seen

    def remember(self, key: DecisionKey, candidate: Optional[Dict[str, Any]]) -> None:
        if key is None or type(candidate) is not dict or type(candidate.get("summary")) is not ScheduleSummary:
            return
        summary = candidate["summary"]
        if summary.success is not True or summary.failed_ops != 0:
            return
        current = self._context()
        if current is _UNSUPPORTED:
            return
        old_context, decision = key
        # A native successful decode can populate the calendar's policy cache;
        # all input values, calendar identity and DB writes must remain fixed.
        if current[0] != old_context[0] or current[1][0] != old_context[1][0]:
            return
        self._seen.add((current, decision))


__all__ = ["MultiStartDecisionCache"]
