"""R1-I: actual computation, complete artifacts and unchanged failure propagation."""

from concurrent.futures import CancelledError
from dataclasses import fields, replace

import pytest

from core.models.workbench_run_compute import CandidateRunInputError
from core.models.workbench_run_job import durable_value
from core.services.workbench import run_compute
from core.services.workbench.run_input import prepare_candidate_run_input
from data.repositories.workbench_run_result_repo import prepare_run_result
from tests.workbench.run_compute_support import run_case as _run_case
from tests.workbench.run_compute_support import unchanged


@pytest.fixture
def computed(run_case):
    case = run_case
    result = unchanged(case, lambda: run_compute.compute_candidate_run(case.conn, case.settings(), case.projections()))
    refs = {row["op_id"]: row["operation_ref"] for row in result.dispositions}
    return case, result, refs


def _comparison(result, candidates):
    comparison = replace(result.orchestration.candidate_comparison, candidates=candidates)
    return replace(result, orchestration=replace(result.orchestration, candidate_comparison=comparison))


def test_result_preparation_retains_all_candidate_dataclass_fields_and_nested_raw(computed):
    case, result, identities = computed
    plans = [replace(plan, search_report={"rawsnapshot": {"bytes": b"\x00\xff", "null": None, "zero": 0}},
                     attempts=[{"nested": [0, False, None]}])
             for plan in result.orchestration.candidate_comparison.candidates]
    result = _comparison(result, plans)
    rows, receipt = unchanged(case, lambda: prepare_run_result(result, identities))
    assert len(rows) == len(receipt["candidates"]) == 4
    assert len({row["candidate_ref"] for row in rows}) == 4
    assert sum(item["selected"] for item in receipt["candidates"]) == 1
    for plan, row in zip(plans, rows):
        payload = result.candidate_payloads[plan.candidate_key]
        expected = {item.name: durable_value(getattr(plan, item.name)) for item in fields(plan)}
        assert row["artifact"] == {**expected, "validated_payload": durable_value(payload)}
        assert row["status"] == "completed" and len(row["tasks"]) == len(payload.schedule_rows)
        for task, source in zip(row["tasks"], payload.schedule_rows):
            assert task["operation_ref"] == identities[source.op_id] and len(task["row_ref"]) == 48
            assert task["payload"] == {**durable_value(source), "locked": source.op_id in result.schedule_input.frozen_op_ids}
    assert receipt["dispositions"] == durable_value(result.dispositions)
    assert receipt["summary"] == durable_value(result.orchestration.result_summary_obj)
    assert receipt["result_persisted"] is True and result.result_persisted is False


def test_failed_and_skipped_candidates_are_retained_without_tasks(computed):
    case, result, identities = computed
    selected = result.orchestration.candidate_comparison.selection.selected_candidate_key
    plans = list(result.orchestration.candidate_comparison.candidates)
    indices = [index for index, plan in enumerate(plans) if plan.candidate_key != selected]
    for index, status in zip(indices, ("failed", "skipped")):
        plans[index] = replace(plans[index], status=status, failure_reason="retained reason")
    result = replace(_comparison(result, plans), state="partial")
    rows, receipt = unchanged(case, lambda: prepare_run_result(result, identities))
    assert len(rows) == 4 and receipt["state"] == "partial"
    for index in indices[:2]:
        assert rows[index]["tasks"] == []
        assert "validated_payload" not in rows[index]["artifact"]
        assert rows[index]["artifact"]["failure_reason"] == "retained reason"
        assert receipt["candidates"][index]["task_count"] == 0


@pytest.mark.parametrize("damage,message", [
    ("identity", "identity is missing"), ("scope", "scope disagree"),
    ("errors", "validation errors"), ("outside", "validation errors"),
    ("duplicate", "Duplicate candidate identity"), ("selected", "Selected candidate is missing"),
])
def test_invalid_prepared_artifacts_fail_before_any_persistence(computed, damage, message):
    case, result, identities = computed
    selected = result.orchestration.candidate_comparison.selection.selected_candidate_key
    if damage == "identity":
        identities = {}
    elif damage in ("scope", "errors", "outside"):
        payload = result.candidate_payloads[selected]
        changes = {"scope": {"scheduled_op_ids": set()}, "errors": {"validation_errors": ["invalid"]},
                   "outside": {"out_of_scope_op_ids": [999]}}[damage]
        result = replace(result, candidate_payloads={**result.candidate_payloads, selected: replace(payload, **changes)})
    else:
        plans = list(result.orchestration.candidate_comparison.candidates)
        if damage == "duplicate":
            plans.append(plans[0])
        else:
            plans = [plan for plan in plans if plan.candidate_key != selected]
        result = _comparison(result, plans)
    with pytest.raises(ValueError, match=message):
        unchanged(case, lambda: prepare_run_result(result, identities))


@pytest.mark.parametrize("version", [False, -1, 1.5, "0"])
def test_version_context_is_never_coerced_before_dispatch(run_case, version):
    case = run_case
    prepared = prepare_candidate_run_input(case.conn, case.settings(), case.projections())
    with pytest.raises(CandidateRunInputError) as error:
        unchanged(case, lambda: run_compute.compute_prepared_candidate_run(case.conn, prepared, version_override=version))
    assert error.value.reason == "invalid_version_context"


@pytest.mark.parametrize("target", ["orchestrate_schedule_run", "validate_candidate"])
def test_cancellation_propagates_without_partial_result_or_db_mutation(run_case, monkeypatch, target):
    case = run_case
    prepared = prepare_candidate_run_input(case.conn, case.settings(), case.projections())
    cancellation = CancelledError("R1-I cancellation")

    def cancel(*args, **kwargs):
        raise cancellation

    monkeypatch.setattr(run_compute, target, cancel)
    with pytest.raises(CancelledError) as error:
        unchanged(case, lambda: run_compute.compute_prepared_candidate_run(case.conn, prepared))
    assert error.value is cancellation
    assert not case.conn.in_transaction
