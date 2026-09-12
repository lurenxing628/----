"""Repair priorities and resource choices must preserve the original scheduling scope."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
from itertools import islice
from types import SimpleNamespace

import pytest

from core.infrastructure.errors import ValidationError
from core.models.batch_operation import BatchOperation
from core.services.scheduler.run.optimizer_graph_ready_repair_decisions import (
    RepairDecision,
    apply_repair_decision,
    iter_resource_decisions,
)
from core.services.scheduler.run.optimizer_graph_ready_repair_neighbors import RepairNeighborhood
from core.services.scheduler.run.optimizer_graph_ready_repair_portfolio import RepairPortfolio


def _op(op_id=1, batch="A", **kwargs):
    return BatchOperation(id=op_id, batch_id=batch, op_code="OP" + str(op_id), op_type_id="T", **kwargs)


def _pool():
    return {
        "machines_by_op_type": {"T": ["M1", "M2", "M3"]},
        "operators_by_machine": {"M1": ["O1", "O2"], "M2": ["O1", "O3"], "M3": ["O4"]},
        "machines_by_operator": {"O1": ["M1", "M2"]},
        "pair_rank": {("O1", "M1"): 0},
    }


def _candidate(*pairs):
    return {"results": [SimpleNamespace(op_id=op_id, machine_id=mid, operator_id=oid) for op_id, mid, oid in pairs]}


def test_decision_is_frozen_and_does_not_accept_mutable_fields():
    decision = RepairDecision(("A",))
    with pytest.raises(FrozenInstanceError):
        decision.batch_order = ("B",)
    with pytest.raises(ValidationError):
        RepairDecision(["A"])
    with pytest.raises(ValidationError):
        RepairDecision(("A",), resource_overrides=([1, "M1", "O1"],))


def test_operation_priority_can_reverse_dag_but_preserves_graph_and_inputs():
    ops = [_op(1), _op(2, "B")]
    context = {
        "fixed_op_ids": [99], "fixed_op_sources_by_op_id": {99: "freeze_window"},
        "predecessor_op_ids_by_op_id": {1: {99}, 2: {1}},
        "successor_op_ids_by_op_id": {99: {1}, 1: {2}},
        "graph_priority_key_by_op_id": {1: (0,), 2: (1,)},
    }
    pool = _pool()
    before = deepcopy((context, ops, pool))
    changed, copied = apply_repair_decision(context, ops, RepairDecision(("A", "B"), (2, 1)), pool)
    assert (context, ops, pool) == before
    assert changed["graph_priority_key_by_op_id"][2] < changed["graph_priority_key_by_op_id"][1]
    for key in context.keys() - {"graph_priority_key_by_op_id"}:
        assert changed[key] is context[key]
    assert all(left is not right for left, right in zip(ops, copied))


@pytest.mark.parametrize("order", [(1,), (1, 3), (1, 1), (True, 2), (0, 2), (1.0, 2), ("1", 2)])
def test_rejects_non_exact_or_non_integer_operation_order(order):
    with pytest.raises(ValidationError):
        decision = RepairDecision(("A",), order)
        apply_repair_decision({}, [_op(1), _op(2)], decision, None)


@pytest.mark.parametrize("ids", [(1, 1), (0, 2), (True, 2), ("1", 2)])
def test_rejects_bad_mutable_operation_ids(ids):
    with pytest.raises(ValidationError):
        apply_repair_decision({}, [_op(v) for v in ids], RepairDecision(("A",)), None)


@pytest.mark.parametrize("order", [("A", "A"), (), ("B",)])
def test_reuses_exact_batch_scope_contract(order):
    with pytest.raises(ValidationError):
        apply_repair_decision({}, [_op()], RepairDecision(order), None)


def test_fixed_seed_operation_cannot_enter_mutable_scope():
    with pytest.raises(ValidationError):
        apply_repair_decision({"fixed_op_ids": [1]}, [_op()], RepairDecision(("A",)), _pool())


@pytest.mark.parametrize("kwargs,pair", [
    ({}, ("M2", "O3")), ({"machine_id": "M1"}, ("M1", "O2")),
    ({"operator_id": "O1"}, ("M2", "O1")),
])
def test_applies_only_qualified_unfixed_dimensions_on_copies(kwargs, pair):
    ops = [_op(**kwargs)]
    pool = _pool()
    before = deepcopy((ops, pool))
    _, changed = apply_repair_decision({}, ops, RepairDecision(("A",), resource_overrides=((1,) + pair,)), pool)
    assert (changed[0].machine_id, changed[0].operator_id) == pair
    assert (ops, pool) == before


@pytest.mark.parametrize("kwargs,pair", [
    ({"source": "external"}, ("M1", "O1")),
    ({"machine_id": "M1"}, ("M2", "O1")),
    ({"operator_id": "O1"}, ("M1", "O2")),
    ({"machine_id": "M1", "operator_id": "O1"}, ("M1", "O1")),
    ({}, ("UNKNOWN", "O1")), ({}, ("M1", "O3")),
])
def test_rejects_fixed_external_and_unqualified_overrides(kwargs, pair):
    with pytest.raises(ValidationError):
        apply_repair_decision({}, [_op(**kwargs)], RepairDecision(("A",), resource_overrides=((1,) + pair,)), _pool())


@pytest.mark.parametrize("rows", [((2, "M1", "O1"),), ((1, "M1", "O1"), (1, "M2", "O3")), ((True, "M1", "O1"),)])
def test_rejects_unknown_duplicate_or_boolean_override_id(rows):
    with pytest.raises(ValidationError):
        apply_repair_decision({}, [_op()], RepairDecision(("A",), resource_overrides=rows), _pool())


def test_machine_and_pair_qualification_require_independent_evidence():
    pool = _pool()
    pool["machines_by_op_type"] = {}
    with pytest.raises(ValidationError):
        apply_repair_decision({}, [_op()], RepairDecision(("A",), resource_overrides=((1, "M1", "O1"),)), pool)
    pool = _pool()
    pool["operators_by_machine"] = {}
    with pytest.raises(ValidationError):
        apply_repair_decision({}, [_op()], RepairDecision(("A",), resource_overrides=((1, "M1", "O1"),)), pool)


def test_original_fixed_machine_allows_operator_selection_without_type_pool():
    pool = {"operators_by_machine": {"M1": ["O1", "O2"]}}
    op = _op(machine_id="M1")
    op.op_type_id = None
    _, changed = apply_repair_decision({}, [op], RepairDecision(("A",), resource_overrides=((1, "M1", "O2"),)), pool)
    assert changed[0].operator_id == "O2"


def test_fixed_machine_still_respects_existing_type_evidence():
    pool = _pool()
    pool["machines_by_op_type"]["T"] = ["M2"]
    with pytest.raises(ValidationError):
        apply_repair_decision({}, [_op(machine_id="M1")], RepairDecision(("A",), resource_overrides=((1, "M1", "O2"),)), pool)


def test_fixed_operator_respects_nonempty_reverse_pool_like_auto_assign():
    pool = _pool()
    pool["machines_by_operator"]["O1"] = ["M1"]
    with pytest.raises(ValidationError):
        apply_repair_decision({}, [_op(operator_id="O1")], RepairDecision(("A",), resource_overrides=((1, "M2", "O1"),)), pool)
    decisions = list(iter_resource_decisions(_candidate((1, "M1", "O1")), [_op(operator_id="O1")], pool, ("A",)))
    assert decisions == []


def test_fixed_dimension_keeps_original_representation():
    _, changed = apply_repair_decision(
        {}, [_op(machine_id=" M1 ")], RepairDecision(("A",), resource_overrides=((1, "M1", "O2"),)), _pool(),
    )
    assert changed[0].machine_id == " M1 "


def test_generator_is_bounded_deterministic_qualified_and_preserves_inputs():
    ops = [_op(1), _op(2), _op(3, source="external"), _op(4, machine_id="M1", operator_id="O1")]
    candidate = _candidate((1, "M1", "O1"), (2, "M1", "O1"), (3, "", ""), (4, "M1", "O1"), (99, "M9", "O9"))
    pool = _pool()
    before = deepcopy((candidate, ops, pool))
    decisions = list(iter_resource_decisions(candidate, ops, pool, ("A",)))
    assert len(decisions) == 8
    assert decisions == list(iter_resource_decisions(candidate, ops, pool, ("A",)))
    assert (candidate, ops, pool) == before
    assert all(d.resource_overrides[0][0] in (1, 2) for d in decisions)
    assert all(d.resource_overrides[0][1:] != ("M1", "O1") for d in decisions)
    for decision in decisions:
        apply_repair_decision({}, ops, decision, pool)
    assert len(list(iter_resource_decisions(candidate, ops, pool, ("A",), max_decisions=1))) == 1


def test_generator_preserves_previous_overrides_and_operation_priority():
    ops = [_op(1), _op(2)]
    candidate = _candidate((1, "M2", "O3"), (2, "M3", "O4"))
    candidate["repair_decision"] = {"resource_overrides": [[1, "M2", "O3"], [2, "M3", "O4"]]}
    decision = next(iter_resource_decisions(candidate, ops, _pool(), ("A",), (2, 1)))
    assert decision.operation_order == (2, 1)
    assert decision.resource_overrides == ((1, "M1", "O1"), (2, "M3", "O4"))


def test_generator_no_pool_has_no_alternatives_but_apply_rejects_missing_evidence():
    assert list(iter_resource_decisions(_candidate((1, "M1", "O1")), [_op()], None, ("A",))) == []
    with pytest.raises(ValidationError):
        apply_repair_decision({}, [_op()], RepairDecision(("A",), resource_overrides=((1, "M1", "O1"),)), None)


@pytest.mark.parametrize("pool", [{"machines_by_op_type": []}, {"machines_by_op_type": {"T": "M1"}}, {"operators_by_machine": {"M1": [None]}}])
def test_rejects_malformed_qualification_pool(pool):
    with pytest.raises(ValidationError):
        apply_repair_decision({}, [_op(machine_id="M1")], RepairDecision(("A",), resource_overrides=((1, "M1", "O1"),)), pool)


def test_generator_rejects_duplicate_results_and_invalid_inherited_decisions():
    with pytest.raises(ValidationError):
        list(iter_resource_decisions(_candidate((1, "M1", "O1"), (1, "M2", "O3")), [_op()], _pool(), ("A",)))
    candidate = _candidate((1, "M1", "O1"))
    candidate["repair_decision"] = {"resource_overrides": [[1, "M1", "O3"]]}
    with pytest.raises(ValidationError):
        list(iter_resource_decisions(candidate, [_op()], _pool(), ("A",)))


def test_portfolio_covers_batch_families_before_interleaving_extras_lazily(monkeypatch):
    moves = (("adjacent_swap", 0, 1), ("adjacent_swap", 1, 2), ("single_insert", 3, 0),
             ("single_insert", 3, 1), ("tardy_boundary_move", 0, 3), ("adjacent_swap", 2, 3))
    batches = RepairNeighborhood(("A", "B", "C", "D"), moves)
    inherited = ((1, "M1", "O1"),)
    extras = (("critical_block_swap", RepairDecision(batches.order, (4, 3, 2, 1), inherited)),
              ("resource_alternative", RepairDecision(batches.order, (), ((2, "M2", "O2"),))))
    portfolio = RepairPortfolio(batches, extras, inherited)
    expanded = []
    original = RepairNeighborhood.neighbors

    def observed(neighborhood):
        expanded.extend(neighborhood.moves)
        yield from original(neighborhood)

    monkeypatch.setattr(RepairNeighborhood, "neighbors", observed)
    stream = portfolio.decisions()
    assert portfolio.batch_family_representative_count == 3
    assert expanded == [], "metadata inspection must not expand batch permutations"
    prefix = list(islice(stream, 3))
    assert [kind for kind, _decision in prefix] == ["adjacent_swap", "single_insert", "tardy_boundary_move"]
    assert expanded == [moves[0], moves[2], moves[4]]
    rows = prefix + list(stream)
    assert [kind for kind, _decision in rows[3:]] == [
        "adjacent_swap", "critical_block_swap", "single_insert", "resource_alternative", "adjacent_swap"]
    assert len(rows) == portfolio.candidate_count == len(moves) + len(extras)
    assert sorted(expanded) == sorted(moves), "each original move is expanded once"
    assert [row for row in rows if row[0] not in {move[0] for move in moves}] == list(extras)
    assert all(decision.resource_overrides == inherited for kind, decision in rows if kind in {move[0] for move in moves})


@pytest.mark.parametrize("moves", [(), (("adjacent_swap", 0, 1),)])
def test_portfolio_missing_batch_families_leave_room_for_extras(moves):
    batches = RepairNeighborhood(("A", "B"), moves)
    extra = ("critical_block_swap", RepairDecision(batches.order, (2, 1)))
    portfolio = RepairPortfolio(batches, (extra,), ())
    rows = list(portfolio.decisions())
    assert portfolio.batch_family_representative_count == len(moves)
    assert rows[-1] == extra
    assert len(rows) == portfolio.candidate_count == len(moves) + 1
