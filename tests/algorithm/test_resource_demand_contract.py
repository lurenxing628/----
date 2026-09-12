"""Resource reservation hints preserve qualification and callback boundaries."""

from types import SimpleNamespace
from typing import Any, Dict

import pytest

from core.algorithm_runtime.resource_demand import ResourceDemand


def _op(op_id, batch_id=None, **changes):
    fields = dict(id=op_id, batch_id=batch_id or "B" + str(op_id), piece_id=None,
                  source="internal", machine_id=None, operator_id=None, op_type_id="T")
    fields.update(changes)
    return SimpleNamespace(**fields)


def _pool() -> Dict[str, Any]:
    return {
        "machines_by_op_type": {"T": ["M1", "M2"], "S": ["M1"]},
        "operators_by_machine": {"M1": ["O1"], "M2": ["O2"]},
        "machines_by_operator": {"O1": ["M1"], "O2": ["M2"]},
    }


def test_preserves_unique_pair_and_excludes_current_operation():
    a, b = _op(1), _op(2, op_type_id="S")
    demand = ResourceDemand([a, b], _pool())
    assert demand.penalty(a, "M1", "O1") == 1.0
    assert demand.penalty(a, "M2", "O2") == 0.0
    assert ResourceDemand([a], _pool()).penalty(a, "M1", "O1") == 0.0


@pytest.mark.parametrize("op_id", ["2", "02", 0, -1, None, True])
def test_only_positive_integer_identities_enter_lifecycle_reservations(op_id):
    a, b = _op(1), _op(op_id, op_type_id="S")
    demand = ResourceDemand([a, b], _pool())
    # Greedy results and failure details normalize identities to integers.
    # A string-keyed reservation must never survive complete(2).
    assert demand.penalty(a, "M1", "O1") == 0.0
    demand.complete(2)
    assert demand.penalty(a, "M1", "O1") == 0.0


def test_operator_conflict_counts_even_on_a_different_machine():
    pool = _pool()
    pool["operators_by_machine"]["M2"] = ["O1", "O2"]
    a, b = _op(1), _op(2, op_type_id="S")
    demand = ResourceDemand([a, b], pool)
    assert demand.penalty(a, "M2", "O1") == 1.0
    assert demand.penalty(a, "M2", "O2") == 0.0


def test_tied_pairs_share_one_fresh_certificate(monkeypatch):
    a, b = _op(1), _op(2, op_type_id="S")
    pool = _pool()
    demand = ResourceDemand([a, b], pool)
    certify = demand._certify
    calls = []

    def counted(current):
        calls.append(current)
        return certify(current)

    monkeypatch.setattr(demand, "_certify", counted)
    assert demand.penalties(a, (("M1", "O1"), ("M2", "O2"))) == (1.0, 0.0)
    assert len(calls) == 1
    pool["machines_by_op_type"]["S"][0] = "M2"
    assert demand.penalties(a, (("M1", "O1"), ("M2", "O2"))) == (0.0, 0.0)
    assert len(calls) == 2


def test_partial_conflicts_do_not_penalize_remaining_qualified_pairs():
    pool = _pool()
    pool["operators_by_machine"] = {"M1": ["O1", "O2"], "M2": ["O1", "O2"]}
    a, b = _op(1), _op(2)
    demand = ResourceDemand([a, b], pool)
    assert demand.penalty(a, "M1", "O1") == 0.0
    assert demand.penalty(a, "M1", "O3") == 0.0


@pytest.mark.parametrize("pool", [None, {}, {"machines_by_op_type": {"T": []}},
                                  {"machines_by_op_type": {"T": ["M1"]}}])
def test_empty_or_incomplete_pool_never_invents_qualification(pool):
    a, b = _op(1), _op(2, machine_id="M1", operator_id="O1")
    assert ResourceDemand([a, b], pool).penalty(a, "M1", "O1") == 0.0


@pytest.mark.parametrize("changes", [dict(machine_id="UNKNOWN"), dict(operator_id="UNKNOWN"),
                                      dict(op_type_id="UNKNOWN"), dict(op_type_id=None),
                                      dict(source="external"), dict(source="unknown")])
def test_unknown_and_external_operations_have_no_resource_claim(changes):
    a, b = _op(1), _op(2, **changes)
    assert ResourceDemand([a, b], _pool()).penalty(a, "M1", "O1") == 0.0


def test_fixed_machine_is_counted_only_with_pool_evidence():
    a, b = _op(1), _op(2, machine_id="M1", operator_id="O1", op_type_id=None)
    assert ResourceDemand([a, b], _pool()).penalty(a, "M1", "O1") == 1.0
    pool = _pool()
    pool["machines_by_op_type"]["S"] = []
    b.op_type_id = "S"
    assert ResourceDemand([a, b], pool).penalty(a, "M1", "O1") == 0.0


@pytest.mark.parametrize("inverse", [{"O1": ["M1", "M2"]}, {}])
def test_fixed_operator_still_respects_operation_type(inverse):
    pool = _pool()
    pool["operators_by_machine"] = {"M1": ["O1"], "M2": ["O1"]}
    pool["machines_by_operator"] = inverse
    a, b = _op(1), _op(2, op_type_id="S", operator_id="O1")
    demand = ResourceDemand([a, b], pool)
    assert demand.penalty(a, "M1", "OTHER") == 1.0
    assert demand.penalty(a, "M2", "OTHER") == 0.0


def test_complete_and_block_remove_claims_and_advance_chain_heads():
    a, b, c = _op(1), _op(2, "OTHER", op_type_id="S"), _op(3, "OTHER", machine_id="M2")
    demand = ResourceDemand([a, b, c], _pool())
    assert demand.penalty(a, "M1", "O1") == 1.0
    assert demand.penalty(a, "M2", "O2") == 0.0
    demand.complete(b.id)
    assert demand.revision == 1
    assert demand.penalty(a, "M1", "O1") == 0.0
    assert demand.penalty(a, "M2", "O2") == 1.0
    demand.block_batch("OTHER")
    assert demand.revision == 2
    assert demand.penalty(a, "M2", "O2") == 0.0
    demand.complete(c.id)
    demand.block_batch("OTHER")
    assert demand.revision == 2


def test_failure_can_remove_a_non_head_before_its_predecessor_completes():
    a, b, c = _op(1), _op(2, "OTHER", machine_id="M2"), _op(3, "OTHER", op_type_id="S")
    demand = ResourceDemand([a, b, c], _pool())
    demand.complete(c.id)
    demand.complete(b.id)
    assert demand.penalty(a, "M1", "O1") == 0.0
    assert demand.penalty(a, "M2", "O2") == 0.0


def test_piece_heads_are_independent_within_one_batch():
    a = _op(1, "SAME", piece_id="P1")
    b = _op(2, "SAME", piece_id="P2", op_type_id="S")
    c = _op(3, "SAME", piece_id="P1", machine_id="M2")
    demand = ResourceDemand([a, b, c], _pool())
    assert demand.penalty(a, "M1", "O1") == 1.0
    assert demand.penalty(a, "M2", "O2") == 0.0
    demand.block_batch("SAME")
    assert demand.penalty(a, "M1", "O1") == 0.0


def test_long_chain_occupies_one_window_position_and_current_chain_does_not_look_ahead():
    a = _op(1, "LONG")
    successors = [_op(i, "LONG", machine_id="M2") for i in range(2, 102)]
    b = _op(102, op_type_id="S")
    demand = ResourceDemand([a] + successors + [b], _pool())
    assert demand.penalty(a, "M1", "O1") == 1.0
    assert demand.penalty(a, "M2", "O2") == 0.0


def test_window_is_bounded_and_admits_the_next_chain_on_completion():
    a = _op(1)
    first_heads = [_op(i, machine_id="M2") for i in range(2, 65)]
    b = _op(65, op_type_id="S")
    demand = ResourceDemand([a] + first_heads + [b], _pool())
    assert demand.penalty(a, "M1", "O1") == 0.0
    demand.complete(first_heads[0].id)
    assert demand.penalty(a, "M1", "O1") == 1.0


def test_external_head_does_not_promote_its_successor_before_completion():
    a, b, c = _op(1), _op(2, "OTHER", source="external"), _op(3, "OTHER", op_type_id="S")
    demand = ResourceDemand([a, b, c], _pool())
    assert demand.penalty(a, "M1", "O1") == 0.0
    demand.complete(b.id)
    assert demand.penalty(a, "M1", "O1") == 1.0


class _NoTouch:
    def __str__(self):
        raise AssertionError("unexpected conversion")

    def __bool__(self):
        raise AssertionError("unexpected truth test")


@pytest.mark.parametrize("field", ["id", "source", "batch_id", "piece_id", "machine_id", "operator_id", "op_type_id"])
def test_complex_fields_are_not_converted_or_validated_early(field):
    a, b = _op(1), _op(2, op_type_id="S")
    setattr(b, field, _NoTouch())
    assert ResourceDemand([a, b], _pool()).penalty(a, "M1", "O1") == 0.0


def test_descriptors_and_custom_getattribute_are_not_called():
    class DescriptorOperation:
        def __init__(self):
            self.__dict__.update(vars(_op(2, op_type_id="S")))

        @property
        def source(self):
            raise AssertionError("unexpected descriptor")

    class DynamicOperation:
        def __getattribute__(self, name):
            raise AssertionError("unexpected attribute callback")

    a = _op(1)
    demand = ResourceDemand([a, DescriptorOperation(), DynamicOperation()], _pool())
    assert demand.penalty(a, "M1", "O1") == 0.0


def test_custom_metaclass_and_dictionary_descriptor_are_not_called():
    class Meta(type):
        def __hash__(cls):
            raise AssertionError("unexpected metaclass hash")

    class MetaOperation(metaclass=Meta):
        pass

    class DictionaryOperation:
        @property
        def __dict__(self):
            raise AssertionError("unexpected dictionary descriptor")

    a = _op(1)
    demand = ResourceDemand([a, MetaOperation(), DictionaryOperation()], _pool())
    assert demand.penalty(a, "M1", "O1") == 0.0


def test_native_batch_operation_fields_take_the_reservation_path():
    from core.models.batch_operation import BatchOperation

    a = BatchOperation(id=1, op_code="A", batch_id="A", op_type_id="T")
    b = BatchOperation(id=2, op_code="B", batch_id="B", op_type_id="S")
    demand = ResourceDemand([a, b], _pool())
    assert demand.penalties(a, (("M1", "O1"), ("M2", "O2"))) == (1.0, 0.0)


def test_class_defaults_cannot_be_mistaken_for_missing_instance_fields():
    class ClassDefaultOperation:
        machine_id = "M1"

    b = ClassDefaultOperation()
    b.__dict__.update(vars(_op(2)))
    del b.__dict__["machine_id"]
    a = _op(1)
    assert ResourceDemand([a, b], _pool()).penalty(a, "M1", "O1") == 0.0


def test_custom_pool_values_and_containers_are_not_iterated_or_converted():
    class DynamicList(list):
        def __iter__(self):
            raise AssertionError("unexpected iteration")

    a, b = _op(1), _op(2, op_type_id="S")
    for values in ([_NoTouch()], DynamicList(["M1"])):
        pool = _pool()
        pool["machines_by_op_type"]["S"] = values
        demand = ResourceDemand([a, b], pool)
        assert demand.penalty(a, "M1", "O1") == 0.0
        assert demand.fallback_reason == "unsupported_resource_pool"


@pytest.mark.parametrize("target", ["pool", "operation", "descriptor"])
def test_same_length_native_mutation_or_new_descriptor_disables_stale_claim(target):
    class Operation:
        pass

    pool = _pool()
    a, b = _op(1), Operation()
    b.__dict__.update(vars(_op(2, op_type_id="S")))
    demand = ResourceDemand([a, b], pool)
    assert demand.penalty(a, "M1", "O1") == 1.0
    if target == "pool":
        pool["machines_by_op_type"]["S"][0] = "M2"
    elif target == "operation":
        setattr(b, "op_type_id", "T")
    else:
        def reject(_self):
            raise AssertionError("new descriptor must not run")
        setattr(Operation, "source", property(reject))
    assert demand.penalty(a, "M1", "O1") == 0.0
    assert demand.fallback_reason == ("resource_pool_changed" if target == "pool" else "operation_input_changed")
    assert demand.revision == 1


def test_mutation_beyond_the_window_is_checked_when_chain_enters():
    a = _op(1)
    heads = [_op(i, machine_id="M2") for i in range(2, 65)]
    b = _op(65, op_type_id="S")
    demand = ResourceDemand([a] + heads + [b], _pool())
    b.op_type_id = "T"
    assert demand.penalty(a, "M1", "O1") == 0.0
    assert demand.fallback_reason == ""
    demand.complete(heads[0].id)
    assert demand.penalty(a, "M1", "O1") == 0.0
    assert demand.fallback_reason == "operation_input_changed"
