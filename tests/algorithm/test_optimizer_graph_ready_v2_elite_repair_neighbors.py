"""Regression coverage for elite-repair neighborhoods and priority limits."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.optimizer_graph_ready_repair_contract import resolve_elite_repair_limits
from core.services.scheduler.run.optimizer_graph_ready_repair_neighbors import (
    build_repair_neighborhood,
    repair_priority_context,
)
from tests._support.optimizer_graph_ready_benchmark import START_DT


def _neighborhood(seed=0):
    operations = [SimpleNamespace(id=i, batch_id="B" + str(i)) for i in range(1, 7)]
    metrics = {op.id: dict(due_deadline_hours=2, due_pressure=op.id, is_on_critical_path=op.id == 2,
                           saveability=1.0 / op.id, sacrifice_penalty=op.id) for op in operations}
    candidate = {"decoded_batch_order": [op.batch_id for op in operations],
                 "results": [SimpleNamespace(batch_id=op.batch_id, end_time=START_DT + timedelta(hours=op.id)) for op in operations]}
    return build_repair_neighborhood(candidate, operations=operations, metrics_by_op_id=metrics, start_dt=START_DT, seed=seed)


def test_limits_default_clamp_and_disable():
    defaults = resolve_elite_repair_limits(None, enabled=True)
    assert (defaults.top_k, defaults.max_neighbors_per_elite, defaults.time_budget_ms, defaults.max_candidates) == (3, 8, None, 60)
    limits = resolve_elite_repair_limits({"graph_ready_optimization": {"elite_repair": {
        "enabled": False, "top_k": 99, "max_neighbors_per_elite": 99, "time_budget_ms": 3}}}, enabled=True)
    assert (limits.enabled, limits.top_k, limits.max_neighbors_per_elite, limits.time_budget_ms) == (False, 8, 32, 3)


@pytest.mark.parametrize("raw", [{"top_k": True}, {"top_k": 0}, {"top_k": "3"}, {"max_neighbors_per_elite": 1.5},
                                  {"time_budget_ms": -1}, {"enabled": "yes"}, {"unknown": 3}, []])
def test_invalid_internal_limits_fail_loud(raw):
    with pytest.raises(ValidationError):
        resolve_elite_repair_limits({"graph_ready_optimization": {"elite_repair": raw}}, enabled=True)


def test_neighbors_reproducible_bounded_and_permutations():
    first = _neighborhood(7)
    assert first == _neighborhood(7)
    assert len(first.moves) <= len(first.order) - 1 + 3 * 4 + 2
    assert {kind for kind, _source, _target in first.moves} == {"adjacent_swap", "single_insert", "tardy_boundary_move"}
    for kind, order in first.neighbors():
        assert sorted(order) == sorted(first.order)
        assert tuple(order) != first.order
        if kind == "adjacent_swap":
            changed = [i for i, batch in enumerate(order) if batch != first.order[i]]
            assert len(changed) == 2 and changed[1] == changed[0] + 1


def test_neighbor_move_sequence_matches_pre_extraction_seed_seven():
    assert _neighborhood(7).moves == (
        ("adjacent_swap", 4, 5), ("single_insert", 5, 0), ("tardy_boundary_move", 2, 1),
        ("adjacent_swap", 3, 4), ("single_insert", 5, 3), ("adjacent_swap", 2, 3),
        ("single_insert", 4, 0), ("adjacent_swap", 0, 1), ("single_insert", 4, 2),
        ("adjacent_swap", 1, 2), ("single_insert", 4, 5), ("single_insert", 3, 0),
        ("single_insert", 3, 1), ("single_insert", 3, 5),
    )


@pytest.mark.parametrize("size,expected", [(0, ()), (1, ()), (2, (("adjacent_swap", 0, 1),))])
def test_zero_signal_neighborhood_boundaries(size, expected):
    operations = [SimpleNamespace(id=i, batch_id="B" + str(i)) for i in range(size)]
    metrics = {op.id: dict(due_deadline_hours=2, due_pressure=0, is_on_critical_path=False,
                           saveability=1, sacrifice_penalty=0) for op in operations}
    candidate = {"decoded_batch_order": [op.batch_id for op in operations], "results": []}
    before = deepcopy(candidate)
    neighborhood = build_repair_neighborhood(candidate, operations=operations, metrics_by_op_id=metrics,
                                             start_dt=START_DT, seed=7)
    assert candidate == before
    assert neighborhood.order == tuple(op.batch_id for op in operations)
    assert neighborhood.moves == expected


def test_priority_decision_preserves_graph_and_fixed_scope():
    operations = [SimpleNamespace(id=1, batch_id="B1"), SimpleNamespace(id=2, batch_id="B2")]
    context = {"fixed_op_ids": {9}, "predecessor_op_ids_by_op_id": {1: {9}, 2: {1}},
               "graph_priority_key_by_op_id": {1: (0,), 2: (1,)}}
    before = deepcopy(context)
    changed = repair_priority_context(context, operations=operations, order=["B2", "B1"])
    assert context == before
    assert changed["predecessor_op_ids_by_op_id"] == before["predecessor_op_ids_by_op_id"]
    assert changed["fixed_op_ids"] == {9}
    assert changed["graph_priority_key_by_op_id"] == {1: (1.0,), 2: (0.0,)}
    with pytest.raises(ValidationError):
        repair_priority_context(context, operations=operations, order=["B1", "B1"])
