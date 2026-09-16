"""Joint resource moves remain decisions within a bounded mutable DAG scope."""
from copy import deepcopy
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_joint import joint_orders, joint_removed
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_moves import _insertion_positions
from tests._support.optimizer_end_to_end_cases import case_environment, fixture_data
from tests.resource_dispatch.test_sgs_decode_checkpoint_contract import RUN_CONFIG, _Case

START = datetime(2026, 1, 5)


def _row(op_id, machine, operator, *, start=None, duration=1, family="T"):
    when = op_id if start is None else start
    return SimpleNamespace(op_id=op_id, batch_id=str(op_id), machine_id=machine, operator_id=operator,
                           start_time=START + timedelta(hours=when), end_time=START + timedelta(hours=when + duration),
                           op_type_name=family)


def _case(rows, *, order=None, edges=(), signals=None, metrics=None, objective="min_tardiness", window=2):
    order = tuple(row.op_id for row in rows) if order is None else order
    predecessors, successors = {op_id: set() for op_id in order}, {op_id: set() for op_id in order}
    for before, after in edges:
        predecessors[after].add(before)
        successors[before].add(after)
    features = {"signals": signals or {}}
    entry = SimpleNamespace(order=order, candidate={"results": rows}, features=features)
    search = SimpleNamespace(parent=SimpleNamespace(order=order, predecessors=predecessors, successors=successors),
                             metrics=metrics or {}, report={"objective_name": objective},
                             _require_budget=lambda: None, _features=lambda reference: reference.features,
                             limits=SimpleNamespace(insertion_window=window))
    return search, entry


def _topological(order, predecessors):
    positions = {op_id: rank for rank, op_id in enumerate(order)}
    return all(positions[before] < positions[after] for after, previous in predecessors.items() for before in previous)


def test_window_couples_shared_operator_and_downstream_machine_from_the_urgent_seed():
    rows = [_row(1, "M1", "O1"), _row(2, "M1", "O2"), _row(3, "M2", "O1"),
            _row(4, "M3", "O3"), _row(5, "M4", "O4")]
    search, entry = _case(rows, edges=((3, 4),), signals={1: 10, 3: 5})
    assert joint_removed(search, entry, (1, 2), 3) == (1, 3, 4)
    assert joint_removed(search, entry, (1, 2), 2) == (1, 3)
    assert joint_removed(search, entry, (1, 2), 1) == (1,)
    assert joint_removed(search, entry, (1, 2), 20) == (1, 3, 4)


def test_fixed_rows_and_disconnected_work_never_enter_the_window():
    rows = [_row(1, "M1", "O1"), _row(2, "M2", "O2"), _row(99, "M1", "O1")]
    search, entry = _case(rows, order=(1, 2), signals={1: 1, 99: 100})
    assert joint_removed(search, entry, (99, 1), 3) == (1,)
    assert joint_removed(search, entry, (99,), 3) == ()
    assert joint_orders(search, entry, (99, 1)) == ()


def test_window_can_follow_dependency_edges_without_inventing_a_resource_assignment():
    rows = [_row(i, "", "") for i in range(1, 5)]
    search, entry = _case(rows, edges=((1, 2), (2, 3)), signals={2: 1})
    assert joint_removed(search, entry, (2,), 3) == (1, 2, 3)
    assert all(row.machine_id == row.operator_id == "" for row in rows)


def test_weighted_tardiness_and_changeover_use_their_own_pressure():
    rows = [_row(1, "M", "O1", family="A"), _row(2, "M", "O2", family="A"),
            _row(3, "M", "O3", family="B"), _row(4, "N", "O4")]
    metrics = {1: {"due_pressure": 1, "weighted_due_pressure": 1},
               2: {"due_pressure": 1, "weighted_due_pressure": 10}}
    search, entry = _case(rows, signals={1: 5, 2: 1}, metrics=metrics)
    assert joint_removed(search, entry, (1, 2), 1) == (1,)
    search.report["objective_name"] = "min_weighted_tardiness"
    assert joint_removed(search, entry, (1, 2), 1) == (2,)
    search.report["objective_name"] = "min_changeover"
    assert joint_removed(search, entry, (1, 2), 1) == (2,)


def test_joint_proposals_move_two_related_operations_and_keep_every_other_relative_order():
    rows = [_row(i, "M" + str(i % 2), "O" + str(i % 3)) for i in range(1, 7)]
    search, entry = _case(rows, edges=((2, 4),), signals={4: 10})
    actual = joint_orders(search, entry, (2, 4))
    assert actual == ((2, 4, 1, 3, 5, 6), (1, 3, 5, 6, 2, 4))
    for order in actual:
        assert tuple(op_id for op_id in order if op_id not in (2, 4)) == (1, 3, 5, 6)
        assert _topological(order, search.parent.predecessors)
        assert all(order.index(op_id) != entry.order.index(op_id) for op_id in (2, 4))
    assert joint_orders(search, entry, (2, 4), limit=1) == actual[:1]


def test_external_predecessor_and_successor_constrain_the_complete_block():
    rows = [_row(i, "M", "O") for i in range(1, 7)]
    search, entry = _case(rows, edges=((1, 3), (3, 5), (5, 6)))
    actual = joint_orders(search, entry, (3, 5))
    assert actual
    assert all(_topological(order, search.parent.predecessors) for order in actual)
    assert all(order.index(1) < order.index(3) < order.index(5) < order.index(6) for order in actual)


def test_required_untouched_middle_declines_a_joint_block_instead_of_breaking_the_dag():
    rows = [_row(i, "M", "O") for i in range(1, 7)]
    search, entry = _case(rows, edges=((2, 3), (3, 4)))
    assert joint_orders(search, entry, (2, 4)) == ()


@pytest.mark.parametrize("size", [0, -1])
def test_no_size_or_candidate_budget_produces_no_work(size):
    search, entry = _case([_row(i, "M", "O") for i in range(1, 4)])
    assert joint_removed(search, entry, (1, 2), size) == ()
    assert joint_orders(search, entry, (1, 2), limit=size) == ()


def test_reference_rows_and_graph_are_unchanged_and_resource_index_is_reused():
    rows = [_row(i, "M", "O") for i in range(1, 6)]
    search, entry = _case(rows, edges=((2, 4),), signals={2: 1})
    before_rows, before_graph = deepcopy(rows), deepcopy(search.parent)
    selected = joint_removed(search, entry, (2,), 3)
    cache = entry.features["joint_window_index"]
    first = joint_orders(search, entry, selected)
    assert joint_removed(search, entry, (2,), 3) == selected
    assert joint_orders(search, entry, selected) == first
    assert entry.features["joint_window_index"] is cache
    assert rows == before_rows and vars(search.parent) == vars(before_graph)
    assert entry.order == (1, 2, 3, 4, 5)


def _coupled_native_data():
    data = fixture_data("tiny_chain")
    original_batch, original_op = data["batches"][0], data["operations"][0]
    data["batches"] = [dict(original_batch, batch_id=bid, quantity=1, due_date=due)
                       for bid, due in (("N", "2026-02-01"), ("A", "2026-01-05"), ("P", "2026-02-01"))]
    data["operations"] = []
    for op_id, bid, seq, machine, operator, duration in (
        (1, "N", 1, "M1", "O1", 24.0), (2, "N", 2, "M2", "O2", 24.0),
        (3, "A", 1, "M1", "O1", 6.0), (4, "A", 2, "M2", "O2", 6.0),
    ):
        data["operations"].append(dict(original_op, id=op_id, op_code=str(op_id), batch_id=bid, seq=seq,
                                       machine_id=machine, operator_id=operator, unit_hours=duration, setup_hours=0.0))
    # Reach the actual large-instance boundary using an independent harmless chain.
    for op_id in range(5, 129):
        data["operations"].append(dict(original_op, id=op_id, op_code=str(op_id), batch_id="P", seq=op_id - 4,
                                       machine_id="MP", operator_id="OP", unit_hours=0.01, setup_hours=0.0))
    return data


def test_joint_order_improves_an_urgent_two_resource_chain_under_the_real_sgs_decoder():
    data = _coupled_native_data()
    with case_environment(data, "min_tardiness", RUN_CONFIG) as schedule_input:
        native = _Case(schedule_input)
        order = tuple(range(1, 129))
        before, summary, digest = native.decode(order)
        assert summary.success and summary.failed_ops == 0
        edges = tuple((previous, op_id) for op_id, previous_ids in native.predecessors.items()
                      for previous in previous_ids)
        search, reference = _case(before, order=order, edges=edges, signals={3: 6, 4: 30})
        selected = joint_removed(search, reference, (3, 4), 2)
        assert selected == (3, 4)
        proposed = joint_orders(search, reference, selected, limit=1)
        assert proposed and proposed[0][:4] == (3, 4, 1, 2)
        after, new_summary, _new_digest = native.decode(proposed[0])
        assert new_summary.success and new_summary.scheduled_ops == 128 and new_summary.failed_ops == 0
        old_by_id, new_by_id = {row.op_id: row for row in before}, {row.op_id: row for row in after}
        assert old_by_id[4].end_time == START + timedelta(hours=54)
        assert new_by_id[4].end_time == START + timedelta(hours=12)
        assert all(new_by_id[op_id].start_time < old_by_id[op_id].start_time for op_id in (3, 4))
        assert all((new_by_id[op_id].machine_id, new_by_id[op_id].operator_id)
                   == (old_by_id[op_id].machine_id, old_by_id[op_id].operator_id) for op_id in order)
        assert native.decode(order)[2] == digest


def test_the_selected_chain_cannot_improve_by_moving_either_member_alone():
    data = _coupled_native_data()
    template = data["operations"][0]
    data["batches"][2]["batch_id"] = "C"
    data["operations"] = []
    jobs = ((1, "A", 1, "M0", "O0", 6), (2, "A", 2, "M1", "O0", 15),
            (3, "N", 1, "M1", "O2", 21), (4, "N", 2, "M2", "O2", 18),
            (5, "C", 1, "M2", "O2", 3), (6, "C", 2, "M2", "O2", 12))
    for op_id, bid, seq, machine, operator, duration in jobs:
        data["operations"].append(dict(template, id=op_id, op_code=str(op_id), batch_id=bid, seq=seq,
                                       machine_id=machine, operator_id=operator, unit_hours=duration))
    with case_environment(data, "min_tardiness", RUN_CONFIG) as schedule_input:
        native = _Case(schedule_input)
        order = (3, 1, 2, 4, 5, 6)
        rows, _summary, _digest = native.decode(order)
        search, reference = _case(rows, order=order, edges=((1, 2), (3, 4), (5, 6)), signals={1: 1, 2: 12})
        old_finish = next(row.end_time for row in rows if row.op_id == 2)
        assert old_finish == START + timedelta(hours=36)
        for op_id in (1, 2):
            without = [item for item in order if item != op_id]
            positions = _insertion_positions(without, op_id, parent=search.parent, anchor=order.index(op_id), window=10)
            for position in positions:
                single = tuple(without[:position] + [op_id] + without[position:])
                actual, summary, _digest = native.decode(single)
                assert summary.success
                assert next(row.end_time for row in actual if row.op_id == 2) >= old_finish
        joint, = joint_orders(search, reference, (1, 2), limit=1)
        actual, summary, _digest = native.decode(joint)
        assert summary.success
        assert next(row.end_time for row in actual if row.op_id == 2) == START + timedelta(hours=21)
