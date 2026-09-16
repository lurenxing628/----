"""Round-one process typing must retain exact JSON and finite-number contracts."""

from copy import deepcopy
from types import MappingProxyType

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_commands import normalize_process_input

REF = "a" * 48
OTHER_REF = "b" * 48


def _payload(operations):
    return {"operations": operations, "groups": [], "confirm_zero_unit_hours": True}


def test_hours_keep_references_floats_and_unknown_external_cycle_without_mutation():
    payload = _payload([
        {"ref": OTHER_REF, "external_days": None},
        {"ref": REF, "setup_hours": 0, "unit_hours": 2.5},
    ])
    payload["groups"] = [{"ref": OTHER_REF, "total_days": 3}]
    before = deepcopy(payload)
    result = normalize_process_input("hours_confirm", payload)
    assert payload == before
    assert result == {
        "operations": [
            {"ref": REF, "setup_hours": 0.0, "unit_hours": 2.5},
            {"ref": OTHER_REF, "external_days": None},
        ],
        "groups": [{"ref": OTHER_REF, "total_days": 3.0}],
        "confirm_zero_unit_hours": True,
    }
    assert type(result["operations"][0]["setup_hours"]) is float
    assert type(result["groups"][0]["total_days"]) is float


@pytest.mark.parametrize("field,value", [
    (field, value)
    for field in ("setup_hours", "unit_hours", "external_days")
    for value in (True, False, "2.5", float("nan"), float("inf"), -1, 10 ** 1000)
] + [("setup_hours", None), ("unit_hours", None)])
def test_hours_reject_invalid_numbers_instead_of_coercing_them(field, value):
    operation = {"ref": REF, "external_days": 2} if field == "external_days" else {
        "ref": REF, "setup_hours": 0, "unit_hours": 1,
    }
    operation[field] = value
    with pytest.raises(WorkbenchCommandRejected) as caught:
        normalize_process_input("hours_confirm", _payload([operation]))
    assert caught.value.code == "invalid_input" and caught.value.status == 422


@pytest.mark.parametrize("operation", [
    None, [], [("ref", REF)], MappingProxyType({"ref": REF, "external_days": 2}),
    {"ref": REF}, {"ref": REF, "setup_hours": 0},
    {"ref": REF, "external_days": 2, "unit_hours": 1},
    {"ref": REF, "setup_hours": 0, "unit_hours": 1, "extra": 1},
])
def test_hours_require_exact_objects_and_fields(operation):
    with pytest.raises(WorkbenchCommandRejected) as caught:
        normalize_process_input("hours_confirm", _payload([operation]))
    assert caught.value.code == "invalid_input" and caught.value.status == 400


@pytest.mark.parametrize("value", [True, False, 1, None, "short"])
def test_hours_references_do_not_accept_boolean_or_numeric_identity(value):
    with pytest.raises(WorkbenchCommandRejected) as caught:
        normalize_process_input("hours_confirm", _payload([{"ref": value, "external_days": 2}]))
    assert caught.value.code == "invalid_input" and caught.value.status == 422


def test_zero_confirmation_type_is_checked_before_content_bound_business_validation():
    payload = _payload([{"ref": REF, "setup_hours": 0, "unit_hours": 0}])
    payload["confirm_zero_unit_hours"] = False
    assert normalize_process_input("hours_confirm", payload)["confirm_zero_unit_hours"] is False
    for value, code in [(1, "invalid_input"), (None, "invalid_input")]:
        payload["confirm_zero_unit_hours"] = value
        with pytest.raises(WorkbenchCommandRejected) as caught:
            normalize_process_input("hours_confirm", payload)
        assert caught.value.code == code


def test_duplicate_hours_operations_are_not_silently_deduplicated():
    operation = {"ref": REF, "setup_hours": 0, "unit_hours": 1}
    with pytest.raises(WorkbenchCommandRejected) as caught:
        normalize_process_input("hours_confirm", _payload([operation, dict(operation)]))
    assert caught.value.code == "invalid_input" and caught.value.status == 422
