"""R1-I: retain durable values, comparison cases and strict history scope gaps."""

import json
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_baseline import RunBaselineComparison
from core.models.workbench_run_job import durable_value
from core.services.workbench.run_history_projection import scope_summary


class _Status(Enum):
    COMPLETE = "complete"


@dataclass
class _Artifact:
    status: _Status
    fields: dict


def test_durable_value_preserves_every_supported_nested_type_and_zero():
    value = _Artifact(_Status.COMPLETE, {
        "null": None, "bool": False, "int": 0, "float": 0.0, "str": "",
        "date": date(2026, 9, 10), "datetime": datetime(2026, 9, 10, 8, 0),
        "blob": b"\x00\xff", "tuple": (1, None), "list": [False, 0],
        "set": {2, 1}, "frozen": frozenset((3, 1)), "mapping": {5: "value"},
    })
    assert durable_value(value) == {"status": "complete", "fields": {
        "null": None, "bool": False, "int": 0, "float": 0.0, "str": "",
        "date": "2026-09-10", "datetime": "2026-09-10T08:00:00",
        "blob": {"sqlite_blob_base64": "AP8="}, "tuple": [1, None], "list": [False, 0],
        "set": [1, 2], "frozen": [1, 3], "mapping": {"5": "value"},
    }}


@pytest.mark.parametrize("value,error,message", [
    ({1: 0, "1": 1}, ValueError, "keys collide"),
    ({(1,): 0}, TypeError, "keys must"),
    ([float("nan")], ValueError, "Nonfinite"),
    ({"a": float("inf")}, ValueError, "Nonfinite"),
    (float("-inf"), ValueError, "Nonfinite"),
    (object(), TypeError, "Unsupported"),
])
def test_durable_value_never_drops_or_stringifies_invalid_artifacts(value, error, message):
    with pytest.raises(error, match=message):
        durable_value(value)


def _execution(**patch):
    return {"execution_state": "unreported", "known_completed_quantity": 0,
            "remaining_quantity": 0, "data_quality": "complete", **patch}


def _interval(comparable=True):
    return {"interval_comparable": comparable, "start": "2026-09-10T08:00:00",
            "end": "2026-09-10T08:00:00", "elapsed_hours": 0,
            "machine": {"ref": "m"}, "operator": {"ref": "o"},
            "event_kind": "point", "duration_seconds": 0, "occupies_resources": False}


@pytest.mark.parametrize("has_candidate,selected,segments,status,reasons", [
    (False, True, [], "unscheduled", ["candidate_operation_unscheduled"]),
    (False, False, [], "baseline_only", ["outside_selected_batches"]),
    (True, True, [], "newly_scheduled", ["no_baseline_operation"]),
    (True, True, [False], "not_comparable", ["baseline_interval_unavailable"]),
    (True, True, [True, False], "not_comparable",
     ["baseline_multiple_segments", "baseline_interval_unavailable"]),
    (True, True, [True], "matched", []),
])
def test_comparison_status_reasons_and_full_point_snapshot_survive(
        has_candidate, selected, segments, status, reasons):
    candidate = _interval() if has_candidate else None
    old = [_interval(comparable) for comparable in segments]
    labels = {"execution_at_generation": _execution(), "piece_id": "P1", "quantity": 0,
              "batch_quantity": 5, "retained_raw": {"future_field": None}}
    result = RunBaselineComparison("a" * 48, None, labels, candidate, old, selected, None).to_dict()
    assert result["status"] == status
    assert [reason["code"] for reason in result["reasons"]] == reasons
    assert result["candidate"] == candidate and result["baseline_segments"] == old
    assert all(result[key] == value for key, value in labels.items())
    assert result["improvement_assessment"] is None and result["execution_affected"] is False
    assert result["delta"]["supplier_changed"] is None
    assert result["delta"]["effective_processing_hours"] is None
    if status == "matched":
        assert result["delta"]["elapsed_hours"] == 0
        assert result["delta"]["machine_changed"] is False
    else:
        assert all(value is None for value in result["delta"].values())


@pytest.mark.parametrize("execution", [None, _execution(execution_state="complete"),
    _execution(known_completed_quantity=1), _execution(remaining_quantity=None),
    _execution(data_quality=None), _execution(data_quality="invalid"),
    _execution(data_quality="legacy_incomplete")])
def test_execution_affected_never_becomes_an_optimization_score(execution):
    result = RunBaselineComparison("a" * 48, None, {"execution_at_generation": execution},
                                   None, [], True, "skipped").to_dict()
    assert result["execution_affected"] is True
    assert [reason["code"] for reason in result["reasons"]] == [
        "candidate_operation_unscheduled", "execution_affected"]
    assert result["improvement_assessment"] is None


@pytest.mark.parametrize("refs", [None, [], "a" * 48, [None], [1], ["bad"]])
def test_history_scope_keeps_missing_references_as_gaps(refs):
    result = scope_summary(json.dumps({"batch_refs": refs, "ready_check": 0}))
    assert result["batch_count"] is None and result["ready_check"] is None
    assert [item["field"] for item in result["data_gaps"]] == [
        "start_date", "end_date", "ready_check", "missing_resource_policy", "completed_policy", "batch_count"]
    assert result["data_gaps"][2]["code"] == "invalid_stored_value"


def test_history_duplicate_refs_and_reversed_dates_remain_hard_failures():
    for value in ({"batch_refs": ["a" * 48, "a" * 48]},
                  {"start_date": "2026-09-11", "end_date": "2026-09-10"}):
        with pytest.raises(WorkbenchCommandRejected) as error:
            scope_summary(json.dumps(value))
        assert error.value.code == "run_result_inconsistent"
