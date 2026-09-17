"""Equivalent native SGS decodes, with the input/exception boundaries preserved."""

import importlib
import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from core.algorithm_contracts.ordering import build_batch_sort_inputs
from core.algorithm_contracts.sort_strategies import SortStrategy, StrategyFactory
from core.algorithm_contracts.types import ScheduleSummary
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.greedy.scheduler import GreedyScheduler
from core.infrastructure.errors import ValidationError
from core.models.batch import Batch
from core.services.scheduler.calendar_service import CalendarService
from core.services.scheduler.config.config_field_spec import default_snapshot_values
from core.services.scheduler.config.config_snapshot import ScheduleConfigSnapshot
from core.services.scheduler.run.optimizer_candidate_fingerprint import build_candidate_fingerprint
from core.services.scheduler.run.optimizer_multi_start_dedup import MultiStartDecisionCache
from core.services.scheduler.run.schedule_input_builder import OpForScheduleAlgo

_START = datetime(2026, 9, 7, 8)


def _inputs(conn, *, graph=False) -> Dict[str, Any]:
    cfg = default_snapshot_values()
    cfg["auto_assign_enabled"] = "no"
    scheduler = GreedyScheduler(CalendarService(conn), ScheduleConfigSnapshot(**cfg))
    batches = {key: Batch(key, key, quantity=1, due_date="2026-09-10", created_at="2026-09-01 08:00:00")
               for key in ("B1", "B2")}
    operations = [OpForScheduleAlgo(index, key + "-1", key, None, 1, "TURN", "Turning", "internal",
                                   "M1", "O1", None, 0.0, 1.0, None, None, None, None)
                  for index, key in enumerate(batches, 1)]
    graph_context = None
    if graph:
        graph_context = {
            "enabled": True, "schedulable_op_ids": {1, 2}, "fixed_op_ids": set(),
            "fixed_op_sources_by_op_id": {}, "predecessor_op_ids_by_op_id": {1: set(), 2: {1}},
            "successor_op_ids_by_op_id": {1: {2}, 2: set()},
            "sort_key_by_op_id": {1: (0, 1, 1), 2: (1, 1, 2)},
            "graph_priority_key_by_op_id": {1: (0.0,), 2: (1.0,)},
        }
    return dict(scheduler=scheduler, strict_mode=True, operations=operations, batches=batches,
                start_dt=_START, end_date=None, downtime_map={}, seed_results=[], resource_pool=None,
                readiness_gate_enabled=False, graph_ready_context=graph_context)


def _order(inputs, strategy, params):
    rows = build_batch_sort_inputs(inputs["batches"], strict_mode=True, strategy=strategy)
    return [row.batch_id for row in StrategyFactory.create(strategy, **params).sort(rows, base_date=_START.date())]


def _evaluate(inputs, strategy=SortStrategy.PRIORITY_FIRST, params=None, *, rule="slack", order=None) -> Dict[str, Any]:
    params = {} if params is None else params
    order = _order(inputs, strategy, params) if order is None else order
    results, summary, used_strategy, used_params = inputs["scheduler"].schedule(
        operations=inputs["operations"], batches=inputs["batches"], strategy=strategy,
        strategy_params=params, start_dt=inputs["start_dt"], end_date=inputs["end_date"],
        machine_downtimes=inputs["downtime_map"], batch_order_override=order,
        seed_results=inputs["seed_results"], dispatch_mode="sgs", dispatch_rule=rule,
        resource_pool=inputs["resource_pool"], strict_mode=True,
        readiness_gate_enabled=inputs["readiness_gate_enabled"], graph_ready_context=inputs["graph_ready_context"],
    )
    metrics = compute_metrics(results, inputs["batches"], expected_operations=inputs["operations"])
    return dict(results=results, summary=summary, strategy=used_strategy, params=used_params,
                dispatch_mode="sgs", dispatch_rule=rule, order=order, metrics=metrics,
                score=(float(summary.failed_ops),) + objective_score("min_overdue", metrics))


def _key(cache, strategy=SortStrategy.PRIORITY_FIRST, params=None, *, mode="sgs", rule="slack", order=None):
    return cache.decision_key(strategy, {} if params is None else params, mode, rule, ["B1", "B2"] if order is None else order)


def _fingerprint(candidate):
    return build_candidate_fingerprint(candidate, objective_name="min_overdue", parent_fingerprint=None,
                                       seen_output_fingerprints=set()).output_fingerprint


@pytest.mark.parametrize("graph", [False, True])
def test_four_strategies_three_rules_need_three_native_decodes_with_equal_outputs(schema_conn, graph):
    schema_conn.execute("BEGIN")
    inputs = _inputs(schema_conn, graph=graph)
    cache = MultiStartDecisionCache(**inputs)
    original, optimized, decode_count = [], [], 0
    for strategy in SortStrategy:
        params = {"priority_weight": 0.4, "due_weight": 0.5} if strategy is SortStrategy.WEIGHTED else {}
        order = _order(inputs, strategy, params)
        for rule in ("slack", "cr", "atc"):
            # Independent uncached evaluation remains the parity oracle.
            original.append(_evaluate(inputs, strategy, params, rule=rule, order=order))
            key = _key(cache, strategy, params, rule=rule, order=order)
            assert key is not None
            if not cache.has(key):
                candidate = _evaluate(inputs, strategy, params, rule=rule, order=order)
                cache.remember(key, candidate)
                optimized.append(candidate)
                decode_count += 1
    assert len(original) == 12 and decode_count == 3
    assert all(candidate["summary"].failed_ops == 0 for candidate in original + optimized)
    assert {candidate["score"] for candidate in original} == {candidate["score"] for candidate in optimized}
    assert {_fingerprint(candidate) for candidate in original} == {_fingerprint(candidate) for candidate in optimized}


def test_remember_requires_a_real_candidate_and_handles_initial_calendar_cache_fill(schema_conn):
    schema_conn.execute("BEGIN")
    inputs = _inputs(schema_conn)
    cache = MultiStartDecisionCache(**inputs)
    key = _key(cache)
    assert key is not None and not cache.has(key)
    cache.remember(key, None)
    assert not cache.has(key)
    assert inputs["scheduler"].calendar._engine._policy_cache == {}
    candidate = _evaluate(inputs)
    cache.remember(key, candidate)
    assert inputs["scheduler"].calendar._engine._policy_cache
    assert cache.has(_key(cache))


def test_failed_decode_return_does_not_enter_seen_cache(schema_conn):
    schema_conn.execute("BEGIN")
    inputs = _inputs(schema_conn)
    cache = MultiStartDecisionCache(**inputs)
    key = _key(cache)
    failed = ScheduleSummary(False, 2, 1, 1, [], ["resource unavailable"], 0.0)
    cache.remember(key, {"summary": failed})
    assert not cache.has(_key(cache))


@pytest.mark.parametrize("field", ["operations", "batches", "resource_pool", "seed_results", "downtime_map", "graph_ready_context", "config"])
def test_mutable_input_changes_never_reuse_a_previous_decision(schema_conn, field):
    schema_conn.execute("BEGIN")
    inputs = _inputs(schema_conn, graph=True)
    inputs["resource_pool"] = {"pair_rank": {("O1", "M1"): 1}}
    cache = MultiStartDecisionCache(**inputs)
    key = _key(cache)
    cache.remember(key, _evaluate(inputs))
    assert cache.has(_key(cache))
    if field == "operations":
        inputs[field][0].unit_hours = 2.0
    elif field == "batches":
        inputs[field]["B1"].due_date = "2026-09-09"
    elif field == "resource_pool":
        inputs[field]["pair_rank"][("O1", "M1")] = -1
    elif field == "seed_results":
        inputs[field].append(SimpleNamespace(op_id=7))
    elif field == "downtime_map":
        inputs[field]["M1"] = [(_START, _START + timedelta(hours=1))]
    elif field == "graph_ready_context":
        inputs[field]["graph_priority_key_by_op_id"][1] = (-3.0,)
    else:
        inputs["scheduler"].config.auto_assign_enabled = "yes"
    assert not cache.has(_key(cache))


def test_policy_cache_changes_and_same_connection_writes_invalidate_key(schema_conn):
    schema_conn.execute("BEGIN")
    inputs = _inputs(schema_conn)
    cache = MultiStartDecisionCache(**inputs)
    key = _key(cache)
    cache.remember(key, _evaluate(inputs))
    assert cache.has(_key(cache))
    policy = next(iter(inputs["scheduler"].calendar._engine._policy_cache.values()))
    policy.efficiency = 0.5
    assert not cache.has(_key(cache))
    policy.efficiency = 1.0
    assert cache.has(_key(cache))
    schema_conn.execute("INSERT INTO Operators (operator_id, name) VALUES ('OTHER', 'Other')")
    assert not cache.has(_key(cache))


@pytest.mark.parametrize("order", [["B1"], ["B1", "B1"], ["B1", " B2"], ["B1", "B3"]])
def test_partial_or_noncanonical_override_is_not_equivalent(schema_conn, order):
    schema_conn.execute("BEGIN")
    cache = MultiStartDecisionCache(**_inputs(schema_conn))
    assert _key(cache, order=order) is None


def test_dispatch_rule_mode_and_order_are_part_of_decision(schema_conn):
    schema_conn.execute("BEGIN")
    inputs = _inputs(schema_conn)
    cache = MultiStartDecisionCache(**inputs)
    cache.remember(_key(cache), _evaluate(inputs))
    assert cache.has(_key(cache))
    assert not cache.has(_key(cache, rule="cr"))
    assert not cache.has(_key(cache, mode="batch_order"))
    assert not cache.has(_key(cache, order=["B2", "B1"]))


def test_bad_weighted_parameters_keep_native_validation_after_seen_order(schema_conn):
    schema_conn.execute("BEGIN")
    inputs = _inputs(schema_conn)
    cache = MultiStartDecisionCache(**inputs)
    cache.remember(_key(cache), _evaluate(inputs))
    bad = {"priority_weight": -1.0, "due_weight": 0.5}
    with pytest.raises(ValidationError) as cached:
        _key(cache, SortStrategy.WEIGHTED, bad)
    with pytest.raises(ValidationError) as native:
        _evaluate(inputs, SortStrategy.WEIGHTED, bad, order=["B1", "B2"])
    assert (cached.value.field, str(cached.value)) == (native.value.field, str(native.value))


@pytest.mark.parametrize("target", ["scheduler", "calendar", "engine"])
def test_instance_callbacks_keep_normal_execution_and_exception(schema_conn, monkeypatch, target):
    schema_conn.execute("BEGIN")
    inputs = _inputs(schema_conn)
    scheduler = inputs["scheduler"]
    owner, method = {"scheduler": (scheduler, "schedule"), "calendar": (scheduler.calendar, "add_working_hours"),
                     "engine": (scheduler.calendar._engine, "add_working_hours")}[target]

    def fail(*args, **kwargs):
        raise RuntimeError("injected decode failure")

    monkeypatch.setattr(owner, method, fail)
    assert _key(MultiStartDecisionCache(**inputs)) is None
    with pytest.raises(RuntimeError, match="injected decode failure"):
        _evaluate(inputs)


def test_class_override_unknown_objects_and_non_strict_input_disable_cache(schema_conn, monkeypatch):
    schema_conn.execute("BEGIN")
    inputs = _inputs(schema_conn)
    original = GreedyScheduler.schedule
    monkeypatch.setattr(GreedyScheduler, "schedule", lambda *args, **kwargs: original(*args, **kwargs))
    assert _key(MultiStartDecisionCache(**inputs)) is None
    monkeypatch.undo()
    inputs["operations"][0].unknown = object()
    assert _key(MultiStartDecisionCache(**inputs)) is None
    del inputs["operations"][0].unknown
    inputs["strict_mode"] = False
    assert _key(MultiStartDecisionCache(**inputs)) is None


@pytest.mark.parametrize("target", ["calendar", "engine", "policy", "shift", "repository"])
def test_calendar_overrides_before_helper_reload_are_not_certified_native(schema_conn, monkeypatch, target):
    schema_conn.execute("BEGIN")
    inputs = _inputs(schema_conn)
    _evaluate(inputs)
    calendar = inputs["scheduler"].calendar
    engine = calendar._engine
    policy = next(iter(engine._policy_cache.values()))
    owner, method = {
        "calendar": (type(calendar), "add_working_hours"),
        "engine": (type(engine), "add_working_hours"),
        "policy": (type(policy), "is_priority_allowed"),
        "shift": (type(engine.operator_shift_calendar), "apply_policy"),
        "repository": (type(engine.repo), "get"),
    }[target]
    module = importlib.import_module("core.services.scheduler.run.optimizer_multi_start_dedup")

    def changed(*args, **kwargs):
        raise RuntimeError("preloaded override")

    monkeypatch.setattr(owner, method, changed)
    try:
        # Registration belongs to the calendar definition, not this helper's
        # import time: reloading must not recapture an override as native.
        reloaded = importlib.reload(module)
        assert _key(reloaded.MultiStartDecisionCache(**inputs)) is None
    finally:
        monkeypatch.undo()
        importlib.reload(module)


def test_every_cached_policy_instance_keeps_its_own_method_guard(schema_conn):
    schema_conn.execute("BEGIN")
    inputs = _inputs(schema_conn)
    _evaluate(inputs)
    engine = inputs["scheduler"].calendar._engine
    policy = next(iter(engine._policy_cache.values()))
    second = replace(policy)
    vars(second)["is_priority_allowed"] = lambda priority: True
    engine._policy_cache[("OTHER", policy.date_str)] = second
    assert _key(MultiStartDecisionCache(**inputs)) is None


def test_no_cache_outside_transaction_or_across_cache_instances(schema_conn):
    inputs = _inputs(schema_conn)
    assert _key(MultiStartDecisionCache(**inputs)) is None
    schema_conn.execute("BEGIN")
    cache = MultiStartDecisionCache(**inputs)
    cache.remember(_key(cache), _evaluate(inputs))
    assert cache.has(_key(cache))
    schema_conn.rollback()
    assert _key(cache) is None
    schema_conn.execute("BEGIN")
    assert not MultiStartDecisionCache(**inputs).has(_key(cache))


def test_transaction_reopened_after_external_commit_invalidates_seen(schema_conn, tmp_path):
    conn = sqlite3.connect(str(tmp_path / "read-snapshot.sqlite3"))
    other = None
    try:
        schema_conn.backup(conn)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        inputs = _inputs(conn)
        conn.execute("BEGIN")
        cache = MultiStartDecisionCache(**inputs)
        cache.remember(_key(cache), _evaluate(inputs))
        assert cache.has(_key(cache))
        previous_changes = conn.total_changes
        conn.commit()
        other = sqlite3.connect(str(tmp_path / "read-snapshot.sqlite3"))
        other.execute("INSERT INTO Operators (operator_id, name) VALUES ('EXTERNAL', 'External')")
        other.commit()
        conn.execute("BEGIN")
        assert conn.total_changes == previous_changes
        assert not cache.has(_key(cache))
    finally:
        if other is not None:
            other.close()
        conn.close()


def test_denied_optional_pragma_disables_cache_without_hiding_native_decode(schema_conn):
    schema_conn.execute("BEGIN")
    inputs = _inputs(schema_conn)
    schema_conn.set_authorizer(lambda action, *args: sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_PRAGMA else sqlite3.SQLITE_OK)
    try:
        assert _key(MultiStartDecisionCache(**inputs)) is None
        assert _evaluate(inputs)["summary"].success is True
    finally:
        schema_conn.set_authorizer(None)


def test_copy_and_pickle_bookkeeping_on_native_classes_keeps_certification(schema_conn):
    # CPython's copyreg stores ``__slotnames__`` on a class the first time an instance is copied or
    # pickled (a real schedule run does this). Interpreter bookkeeping must not disable the cache
    # for the rest of the process; it used to, which only showed up in whole-directory test runs.
    import copy
    import pickle

    schema_conn.execute("BEGIN")
    inputs = _inputs(schema_conn)
    cache = MultiStartDecisionCache(**inputs)
    copy.deepcopy(inputs["operations"][0])
    pickle.dumps(inputs["batches"]["B1"])
    assert "__slotnames__" in vars(OpForScheduleAlgo)
    key = _key(cache)
    assert key is not None
    cache.remember(key, _evaluate(inputs))
    assert cache.has(_key(cache))
    OpForScheduleAlgo.extra_member = 1
    try:
        assert _key(cache) is None
    finally:
        del OpForScheduleAlgo.extra_member
    assert _key(cache) is not None

