"""A neutral resource hint is not an input certificate or a cached preference."""
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest

from core.algorithm_runtime.resource_demand import ResourceDemand
from core.algorithm_runtime.resource_quality import MachineTypeState, prefer_resource_pair


def _operation(op_id, batch_id, op_type="T"):
    return SimpleNamespace(id=op_id, batch_id=batch_id, piece_id=None, source="internal",
                           machine_id="", operator_id="", op_type_id=op_type)


def _pool():
    return {"machines_by_op_type": {"T": ["M1", "M2"], "S": ["M1"]},
            "operators_by_machine": {"M1": ["O1"], "M2": ["O2"]}, "machines_by_operator": {}}


def _scores():
    end = datetime(2026, 9, 14, 9)
    return (end, 0, 0.0, 0, "M2", "O2"), (end, 0, 0.0, 0, "M1", "O1")


def test_equal_claims_keep_the_original_choice_without_certifying_inputs():
    first, other = _operation(1, "FIRST"), _operation(2, "OTHER")
    state = MachineTypeState()
    state.demand = ResourceDemand([first, other], _pool())
    candidate, best = _scores()
    with mock.patch.object(state.demand, "_certify", side_effect=AssertionError("neutral hint has no effect")):
        assert not prefer_resource_pair(state, first, candidate, best)
        assert prefer_resource_pair(state, first, best, candidate)
    assert state.demand.fallback_reason == ""
    assert state.demand.revision == 0


@pytest.mark.parametrize("mutation", ["pool", "operation", "descriptor", "class_default"])
def test_neutral_mutation_is_rejected_before_later_non_neutral_choice(mutation):
    class Operation:
        pass

    first = Operation()
    first.__dict__.update(vars(_operation(1, "FIRST")))
    head, successor = _operation(2, "OTHER"), _operation(3, "OTHER", "S")
    pool = _pool()
    state = MachineTypeState()
    state.demand = ResourceDemand([first, head, successor], pool)
    candidate, best = _scores()
    if mutation == "pool":
        pool["machines_by_op_type"]["S"][0] = "M2"
    elif mutation == "operation":
        setattr(first, "op_type_id", "S")
    elif mutation == "descriptor":
        def reject(_instance):
            raise AssertionError("changed descriptor must not execute")
        setattr(Operation, "op_type_id", property(reject))
    else:
        del first.__dict__["machine_id"]
        setattr(Operation, "machine_id", "M1")

    # The old and disabled hints are both equal here. We have not certified the
    # mutated inputs and do not pretend the delayed diagnostic has happened.
    assert not prefer_resource_pair(state, first, candidate, best)
    assert state.demand.fallback_reason == ""
    assert state.demand.revision == 0

    state.demand.complete(2)
    # The next head would favor M2 using the stale S->M1 qualification. Its
    # unequal hint must be certified, rejected and replaced by the old tie.
    assert not prefer_resource_pair(state, first, candidate, best)
    assert state.demand.fallback_reason == ("resource_pool_changed" if mutation == "pool" else "operation_input_changed")
    assert state.demand.revision == 2


def test_public_penalties_still_certify_equal_hints_and_report_mutation():
    first, other = _operation(1, "FIRST"), _operation(2, "OTHER")
    pool = _pool()
    demand = ResourceDemand([first, other], pool)
    pool["machines_by_op_type"]["S"][0] = "M2"
    assert demand.penalties(first, (("M1", "O1"), ("M2", "O2"))) == (0.0, 0.0)
    assert demand.fallback_reason == "resource_pool_changed"
    assert demand.revision == 1


def test_non_neutral_choice_keeps_scarcity_behavior_and_certifies_once():
    first, other = _operation(1, "FIRST"), _operation(2, "OTHER", "S")
    state = MachineTypeState()
    state.demand = ResourceDemand([first, other], _pool())
    candidate, best = _scores()
    with mock.patch.object(state.demand, "_certify", wraps=state.demand._certify) as certify:
        assert prefer_resource_pair(state, first, candidate, best)
    assert certify.call_count == 1


def test_neutral_probe_never_hashes_non_native_pair_values():
    class NoHash:
        def __hash__(self):
            raise AssertionError("unsupported pair must not be looked up")

    first = _operation(1, "FIRST")
    demand = ResourceDemand([first], _pool())
    pair: Any = (NoHash(), "O1")
    assert demand.comparison_is_neutral(first, pair, ("M1", "O1"))
