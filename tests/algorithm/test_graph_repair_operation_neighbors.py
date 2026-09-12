"""Operation-level repair decisions retain DAG and immutable schedule inputs."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from types import SimpleNamespace

from core.services.scheduler.run import optimizer_graph_ready_operation_neighbors as neighbors
from core.services.scheduler.run.optimizer_graph_ready_operation_neighbors import operation_repair_decisions

START = datetime(2026, 9, 12, 8)


def _row(op_id, start, end, machine="M"):
    return SimpleNamespace(op_id=op_id, batch_id="B" + str(op_id), machine_id=machine, operator_id="P" + machine,
                           op_type_name="T", start_time=START + timedelta(hours=start), end_time=START + timedelta(hours=end))


def _decisions(rows, edges=None, limit=8):
    operations = [SimpleNamespace(id=row.op_id, batch_id=row.batch_id) for row in rows if row.op_id != 99]
    metrics = {op.id: {"is_on_critical_path": True, "due_deadline_hours": 1, "due_pressure": op.id} for op in operations}
    candidate = {"results": rows}
    context = {"predecessor_op_ids_by_op_id": edges or {op.id: set() for op in operations}, "fixed_op_ids": {99}}
    before = deepcopy((candidate, context, operations))
    decisions = list(operation_repair_decisions(
        candidate, operations=operations, graph_context=context, metrics_by_op_id=metrics,
        batch_order=tuple(op.batch_id for op in operations), start_dt=START, objective_name="min_overdue", limit=limit))
    assert (candidate, context, operations) == before
    return decisions


def test_critical_block_changes_operation_priority_and_keeps_dag():
    decisions = _decisions([_row(1, 0, 1), _row(3, 1, 2), _row(2, 2, 3), _row(4, 3, 4)],
                          {1: set(), 2: {1}, 3: set(), 4: {3}})
    assert any(kind == "critical_block_swap" for kind, _ in decisions)
    assert len({decision for _, decision in decisions}) == len(decisions)
    for _, decision in decisions:
        order = decision.operation_order
        assert set(order) == {1, 2, 3, 4}
        assert order.index(1) < order.index(2)
        assert order.index(3) < order.index(4)


def test_precedence_dependent_resource_neighbors_are_not_reversed():
    assert _decisions([_row(1, 0, 1), _row(2, 1, 2), _row(3, 2, 3)],
                      {1: set(), 2: {1}, 3: {2}}) == []


def test_time_insert_comes_from_decoded_gap_and_never_moves_fixed_seed():
    decisions = _decisions([_row(99, -1, 0), _row(1, 0, 1), _row(2, 3, 4), _row(3, 6, 7)])
    inserts = [decision for kind, decision in decisions if kind == "operation_time_insert"]
    assert inserts
    assert all(99 not in decision.operation_order for _, decision in decisions)
    assert any(decision.operation_order.index(3) < decision.operation_order.index(2) for decision in inserts)


def test_operation_candidate_limit_is_exact_and_repeatable():
    rows = [_row(index + 1, index, index + 1) for index in range(12)]
    assert len(_decisions(rows, limit=2)) == 2
    assert _decisions(rows, limit=2) == _decisions(rows, limit=2)


def test_rejected_chain_moves_have_a_bounded_construction_cost(monkeypatch):
    checked = []
    original = neighbors._is_topological

    def check(order, predecessors):
        checked.append(order)
        return original(order, predecessors)

    monkeypatch.setattr(neighbors, "_is_topological", check)
    rows = [_row(index + 1, index, index + 1) for index in range(100)]
    edges = {index: {index - 1} if index > 1 else set() for index in range(1, 101)}
    assert _decisions(rows, edges, limit=1) == []
    assert 0 < len(checked) <= 4
