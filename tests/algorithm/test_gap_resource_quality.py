"""Real decoder witnesses for neighboring changeovers and scarce resource choices."""
import inspect
from copy import deepcopy
from datetime import datetime, timedelta
from itertools import product
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest

from core.algorithm_runtime.resource_demand import ResourceDemand
from core.algorithm_runtime.resource_quality import (
    MachineTypeState,
    _plain_operation_type,
    initialize_resource_quality,
    prefer_resource_pair,
    slot_changeover_penalty,
)
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithms import GreedyScheduler, ScheduleResult
from core.algorithms.evaluation import _count_changeovers

BASE = datetime(2026, 9, 14, 8)


class Calendar:
    def adjust_to_working_time(self, dt, priority=None, operator_id=None):
        return dt

    def add_working_hours(self, dt, hours, priority=None, operator_id=None):
        return dt + timedelta(hours=hours)

    def get_efficiency(self, dt, operator_id=None):
        return 1.0

    def add_calendar_days(self, dt, days, **kwargs):
        return dt + timedelta(days=days)


def batch(batch_id, quantity=1):
    return SimpleNamespace(batch_id=batch_id, quantity=quantity, priority="normal", due_date="2026-09-15",
                           ready_status="yes", ready_date=None, created_at=None)


def operation(op_id, op_type="T", machine_id="", operator_id="", piece_id=None):
    return SimpleNamespace(id=op_id, op_code="OP" + str(op_id), batch_id="B" + str(op_id), seq=1,
                           source="internal", machine_id=machine_id, operator_id=operator_id,
                           setup_hours=0.0, unit_hours=1.0, op_type_id=op_type, op_type_name=op_type,
                           piece_id=piece_id)


def pool():
    return {"machines_by_op_type": {"T": ["M1", "M2"], "FLEX": ["M1", "M2"], "SCARCE": ["M1"]},
            "operators_by_machine": {"M1": ["O1"], "M2": ["O2"]}, "machines_by_operator": {}, "pair_rank": {}}


def result(op_id, machine_id, start, end, op_type):
    return ScheduleResult(op_id=op_id, op_code="SEED" + str(op_id), batch_id="SEED", seq=op_id,
                          machine_id=machine_id, operator_id="O" + machine_id[1:], start_time=BASE + timedelta(hours=start),
                          end_time=BASE + timedelta(hours=end), source="internal", op_type_name=op_type)


def changeovers(rows):
    return _count_changeovers({mid: [row for row in rows if row.machine_id == mid] for mid in ("M1", "M2")})


def start_of(row: ScheduleResult) -> datetime:
    assert isinstance(row.start_time, datetime)
    return row.start_time


def end_of(row: ScheduleResult) -> datetime:
    assert isinstance(row.end_time, datetime)
    return row.end_time


def run(ops, *, seeds=None, mode="batch_order", graph=None, batches=None):
    return GreedyScheduler(Calendar(), {"auto_assign_enabled": "yes"}).schedule(
        ops, batches or {op.batch_id: batch(op.batch_id) for op in ops}, start_dt=BASE,
        dispatch_mode=mode, dispatch_rule="slack", resource_pool=pool(), seed_results=seeds,
        batch_order_override=list(dict.fromkeys(op.batch_id for op in ops)), graph_ready_context=graph,
    )


@pytest.mark.parametrize("mode", ["batch_order", "sgs"])
def test_real_gap_choice_reduces_four_changeovers_to_two_without_moving_seeds(mode):
    seeds = [result(100 + i * 3 + j, mid, start, start + 1, name)
             for i, (mid, names) in enumerate((("M1", ("A", "A", "B")), ("M2", ("B", "B", "A"))))
             for j, (start, name) in enumerate(zip((0, 3, 5), names))]
    original = deepcopy(seeds)
    automatic = operation(1)
    automatic.op_type_name = "B"
    forced = deepcopy(automatic)
    forced.machine_id, forced.operator_id = "M1", "O1"
    rows, summary, *_ = run([automatic], seeds=seeds, mode=mode)
    old_rows, *_ = run([forced], seeds=seeds, mode=mode)
    chosen = next(row for row in rows if row.op_id == 1)
    assert summary.failed_ops == 0
    assert (chosen.machine_id, chosen.start_time, chosen.end_time) == ("M2", BASE + timedelta(hours=1), BASE + timedelta(hours=2))
    assert (changeovers(old_rows), changeovers(rows)) == (4, 2)
    assert seeds == original
    assert [row for row in rows if row.op_id != 1] == original


@pytest.mark.parametrize("mode", ["batch_order", "sgs"])
def test_real_scarcity_choice_finishes_two_one_hour_jobs_in_one_hour(mode):
    ops = [operation(1, "FLEX"), operation(2, "SCARCE")]
    rows, summary, *_ = run(ops, mode=mode)
    by_id = {row.op_id: row for row in rows}
    assert summary.failed_ops == 0
    assert (by_id[1].machine_id, by_id[2].machine_id) == ("M2", "M1")
    assert max(end_of(row) for row in rows) == BASE + timedelta(hours=1)
    forced = deepcopy(ops)
    forced[0].machine_id, forced[0].operator_id = "M1", "O1"
    old_rows, *_ = run(forced, mode=mode)
    assert max(end_of(row) for row in old_rows) == BASE + timedelta(hours=2)


def test_scarcity_never_overrides_an_earlier_finish():
    rows, *_ = run([operation(1, "FLEX"), operation(2, "SCARCE")], seeds=[result(100, "M2", 0, 2, "FLEX")])
    chosen = next(row for row in rows if row.op_id == 1)
    assert (chosen.machine_id, chosen.end_time) == ("M1", BASE + timedelta(hours=1))


def test_fixed_seed_is_never_reassigned_to_reserve_scarce_capacity():
    fixed = result(1, "M1", 0, 1, "FLEX")
    fixed.batch_id = "B1"
    fixed.op_code = "OP1"
    fixed.seq = 1
    rows, summary, *_ = run([operation(1, "FLEX"), operation(2, "SCARCE")], seeds=[fixed], mode="sgs")
    assert summary.failed_ops == 0
    assert next(row for row in rows if row.op_id == 1) == fixed
    assert next(row for row in rows if row.op_id == 2).start_time == fixed.end_time


def test_piece_scarcity_uses_separate_piece_frontiers_and_preserves_single_piece_work():
    ops = [operation(1, "FLEX", piece_id="P1"), operation(2, "SCARCE", piece_id="P2")]
    for op in ops:
        op.batch_id = "B1"
    graph = {"enabled": True, "piece_scope": True, "schedulable_op_ids": [1, 2], "fixed_op_ids": [],
             "predecessor_op_ids_by_op_id": {1: [], 2: []}, "successor_op_ids_by_op_id": {1: [], 2: []},
             "score_enabled": False, "sort_key_by_op_id": {1: (0, 1, 1), 2: (0, 1, 2)}}
    rows, summary, *_ = run(ops, mode="sgs", graph=graph, batches={"B1": batch("B1", quantity=10)})
    assert summary.failed_ops == 0
    assert [(row.op_id, row.machine_id) for row in rows] == [(1, "M2"), (2, "M1")]
    assert all(row.start_time == BASE and row.end_time == BASE + timedelta(hours=1) for row in rows)


def test_piece_predecessor_remains_a_lower_bound_despite_alternative_resources():
    ops = [operation(1, "FLEX", piece_id="P1"), operation(2, "SCARCE", piece_id="P1")]
    for index, op in enumerate(ops, 1):
        op.batch_id, op.seq = "B1", index
    graph = {"enabled": True, "piece_scope": True, "schedulable_op_ids": [1, 2], "fixed_op_ids": [],
             "predecessor_op_ids_by_op_id": {1: [], 2: [1]}, "successor_op_ids_by_op_id": {1: [2], 2: []},
             "score_enabled": False, "sort_key_by_op_id": {1: (0, 1, 1), 2: (0, 2, 2)}}
    rows, summary, *_ = run(ops, mode="sgs", graph=graph, batches={"B1": batch("B1", quantity=2)})
    assert summary.failed_ops == 0
    assert start_of(rows[1]) >= end_of(rows[0])
    assert rows[1].end_time == BASE + timedelta(hours=2)


def test_neighbor_delta_matches_final_metric_for_all_three_type_neighbors():
    for before, middle, after in product(("A", "B", ""), repeat=3):
        state = MachineTypeState()
        old = [result(1, "M1", 0, 1, before), result(3, "M1", 3, 4, after)]
        for row in reversed(old):
            assert isinstance(row.op_type_name, str)
            state.record("M1", start_of(row), end_of(row), row.op_id, row.op_type_name)
        new = result(2, "M1", 1, 2, middle)
        predicted = state.insertion_penalty("M1", start_of(new), end_of(new), 2, middle)
        assert predicted == changeovers(old + [new]) - changeovers(old)


def test_neighbor_metric_uses_chronological_order_even_when_latest_end_is_earlier_in_that_order():
    state = ScheduleRunState(base_time=BASE)
    state.record_seed_result(result(1, "M1", 0, 8, "A"))
    state.record_seed_result(result(2, "M1", 1, 2, "B"))
    assert state.last_op_type_by_machine["M1"] == "A"
    assert slot_changeover_penalty(state.last_op_type_by_machine, op=operation(3, "B"), machine_id="M1",
                                  start=BASE + timedelta(hours=8), end=BASE + timedelta(hours=9), legacy_penalty=1) == 0


def test_equal_time_point_events_use_operation_id_as_the_metric_tie_breaker():
    types = MachineTypeState()
    types["M1"] = "B"
    types.record("M1", BASE, BASE, 5, "A")
    types.record("M1", BASE, BASE, 15, "B")
    assert slot_changeover_penalty(types, op=operation(10, "A"), machine_id="M1",
                                  start=BASE, end=BASE, legacy_penalty=1) == 0


def test_legacy_dictionary_and_descriptor_keep_existing_penalty_without_extra_reads():
    class Dynamic:
        id = 1

        @property
        def op_type_name(self):
            raise AssertionError("quality evidence must not read dynamic fields")

    types = MachineTypeState()
    types.record("M1", BASE + timedelta(hours=2), BASE + timedelta(hours=3), 2, "A")
    for mapping in ({"M1": "A"}, types):
        assert slot_changeover_penalty(mapping, op=Dynamic(), machine_id="M1", start=BASE,
                                      end=BASE + timedelta(hours=1), legacy_penalty=1) == 1


def test_native_operation_identity_reads_current_fields_without_reflection():
    op = SimpleNamespace(id=1, op_type_name=" A ")
    # These instance keys do not replace the exact builtin's access protocol.
    op.__dict__.update({"__dict__": {}, "__getattribute__": object(), "__class__": object()})
    with mock.patch("core.algorithm_runtime.resource_quality.static_attribute",
                    side_effect=AssertionError("native operation should not require reflection")), \
            mock.patch("core.algorithm_runtime.resource_quality.static_class_attribute",
                       side_effect=AssertionError("native operation should not require reflection")):
        assert _plain_operation_type(op) == (1, "A")
        op.id, op.op_type_name = 2, " B "
        assert _plain_operation_type(op) == (2, "B")
        op.op_type_name = " \t "
        assert _plain_operation_type(op) == (2, "")
        del op.id
        assert _plain_operation_type(op) is None
        op.id = 3
        del op.op_type_name
        assert _plain_operation_type(op) is None


@pytest.mark.parametrize("op_id,op_type", [(True, "A"), (0, "A"), (-1, "A"), ("1", "A"), (1, None), (1, 3)])
def test_native_operation_identity_rejects_non_native_or_invalid_values(op_id, op_type):
    assert _plain_operation_type(SimpleNamespace(id=op_id, op_type_name=op_type)) is None


def test_native_operation_identity_does_not_call_value_conversion_or_descriptors():
    class DynamicValue:
        def __get__(self, instance, owner=None):
            raise AssertionError("must not invoke instance field as descriptor")

        def __bool__(self):
            raise AssertionError("must not convert field to bool")

        def __int__(self):
            raise AssertionError("must not convert field to int")

        def __str__(self):
            raise AssertionError("must not convert field to str")

    class DynamicName(str):
        def strip(self, *args, **kwargs):
            raise AssertionError("must not call subclass strip")

    value = DynamicValue()
    for op_id, op_type in ((value, "A"), (1, value), (1, DynamicName("A"))):
        assert _plain_operation_type(SimpleNamespace(id=op_id, op_type_name=op_type)) is None


def test_namespace_subclass_class_mutation_and_descriptor_keep_static_contract():
    class MutableOperation(SimpleNamespace):
        pass

    op = MutableOperation(id=1, op_type_name="A")
    assert _plain_operation_type(op) == (1, "A")
    with mock.patch.object(MutableOperation, "op_type_name", new=property(
            lambda self: pytest.fail("must not invoke dynamically installed property")), create=True):
        assert _plain_operation_type(op) is None
    assert _plain_operation_type(op) == (1, "A")
    op.id, op.op_type_name = 2, "B"
    assert _plain_operation_type(op) == (2, "B")


def test_namespace_subclass_custom_access_keeps_legacy_penalty_without_callbacks():
    reads = []

    class DynamicOperation(SimpleNamespace):
        def __getattribute__(self, key):
            reads.append(key)
            raise AssertionError("quality lookup must not add the first callback error")

    types = MachineTypeState()
    types.record("M1", BASE + timedelta(hours=2), BASE + timedelta(hours=3), 2, "A")
    assert slot_changeover_penalty(types, op=DynamicOperation(id=1, op_type_name="A"), machine_id="M1",
                                  start=BASE, end=BASE + timedelta(hours=1), legacy_penalty=1) == 1
    assert reads == []


@pytest.mark.parametrize("key_kind", ["object", "str_subclass"])
@pytest.mark.parametrize("behavior", ["match", "mutate_next", "miss_id", "raise_id", "raise_type", "raise_bool"])
def test_native_type_collision_keys_match_old_static_reads_and_first_error(key_kind, behavior):
    def old_static_read(op):
        accessor = inspect.getattr_static(type(op), "__getattribute__", None)
        if accessor is not object.__getattribute__ and accessor is not SimpleNamespace.__getattribute__:
            return None
        op_id = inspect.getattr_static(op, "id", None)
        op_type = inspect.getattr_static(op, "op_type_name", None)
        if type(op_id) is not int or op_id <= 0 or type(op_type) is not str:
            return None
        return op_id, op_type.strip()

    def observe(read):
        events = []
        op = SimpleNamespace()
        fields: Any = op.__dict__

        class EqualityResult:
            def __bool__(self):
                events.append(("bool", "id"))
                raise ValueError("first equality-result error")

        def equal(key, other) -> Any:
            events.append((key.target, other))
            if key.target == "id":
                if behavior == "raise_id":
                    raise RuntimeError("first id collision error")
                if behavior == "raise_bool":
                    return EqualityResult()
                if behavior == "mutate_next":
                    fields[type_key] = " B "
                if behavior == "miss_id":
                    return False
            elif behavior == "raise_type":
                raise AttributeError("first type collision error")
            return key.target == other

        class CollisionKey:
            def __init__(self, target):
                self.target = target

            def __hash__(self):
                return hash(self.target)

            __eq__ = equal

        class CollisionString(str):
            target: str

            def __new__(cls, target):
                value = super().__new__(cls, target)
                value.target = target
                return value

            __hash__ = str.__hash__
            __eq__ = equal

        key_type = CollisionKey if key_kind == "object" else CollisionString
        id_key, type_key = key_type("id"), key_type("op_type_name")
        fields[id_key], fields[type_key] = 1, " A "
        events.clear()
        try:
            outcome = ("return", read(op))
        except (RuntimeError, AttributeError, ValueError) as error:
            outcome = ("error", type(error).__name__, str(error))
        return outcome, events

    expected = observe(old_static_read)
    assert observe(_plain_operation_type) == expected
    assert expected[1][0] == ("id", "id")
    if behavior in ("match", "mutate_next", "raise_type"):
        assert expected[1] == [("id", "id"), ("op_type_name", "op_type_name")]
    elif behavior == "miss_id":
        # Dict probing may revisit the colliding slot before concluding absence.
        assert expected[1][-1] == ("op_type_name", "op_type_name")
        assert all(event == ("id", "id") for event in expected[1][:-1])


@pytest.mark.parametrize("event", ["success", "failure", "exception", "missing", "skipped", "graph_blocked"])
def test_run_state_removes_completed_and_failed_resource_demand(event):
    ops = [operation(1, "FLEX"), operation(2, "SCARCE")]
    state = ScheduleRunState(base_time=BASE)
    initialize_resource_quality(state, ops, pool())
    types = state.last_op_type_by_machine
    assert isinstance(types, MachineTypeState) and types.demand is not None
    assert types.demand.penalty(ops[0], "M1", "O1") == 1.0
    if event == "success":
        state.record_dispatch_success(result(2, "M1", 0, 1, "SCARCE"))
    elif event == "failure":
        state.record_dispatch_failure("B2", block=True, failed_op=ops[1])
    elif event == "exception":
        state.record_dispatch_exception(ops[1], "B2", dispatch_mode="sgs")
    elif event == "missing":
        state.record_missing_batch(ops[1], "B2")
    elif event == "skipped":
        state.record_skipped_after_batch_failure(ops[1], "B2")
    else:
        state.record_graph_blocked_after_failure(ops[1], "B2", failed_op=ops[0])
    assert types.demand.penalty(ops[0], "M1", "O1") == 0.0


def test_non_tied_resource_pairs_do_not_pay_for_a_demand_certificate():
    ops = [operation(1, "FLEX"), operation(2, "SCARCE")]
    types = MachineTypeState()
    types.demand = ResourceDemand(ops, pool())
    better = (BASE, 0, 0.0, 0, "M1", "O1")
    later = (BASE + timedelta(hours=1), 0, 0.0, 0, "M2", "O2")
    more_changeovers = (BASE, 1, 0.0, 0, "M2", "O2")
    with mock.patch.object(ResourceDemand, "penalties", side_effect=AssertionError("unexpected certificate")):
        assert prefer_resource_pair(types, ops[0], better, later)
        assert prefer_resource_pair(types, ops[0], better, more_changeovers)
        assert not prefer_resource_pair(types, ops[0], later, better)
