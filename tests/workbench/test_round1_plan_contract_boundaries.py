"""R1-E: real adoption evidence and read-only APIs keep their original identity."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_adoption import adoption_input
from core.services.workbench.plan_adoption_baseline_identity import _captured_row_binding
from core.services.workbench.plan_adoption_baseline_values import AdoptionBaselineUnavailable
from tests.workbench.plan_adoption_baseline_support import mutate_json, two_versions
from tests.workbench.plan_read_support import make_api
from tests.workbench.run_candidate_adoption_support import service, snapshot
from tests.workbench.trial_support import trial_case as trial_case


def test_adoption_intent_retains_boolean_and_normalized_text():
    value = {"confirm": True, "reason": "  approved  ", "declared_operator": "  planner  "}
    result = adoption_input(value)
    assert result == {"confirm": True, "reason": "approved", "declared_operator": "planner"}
    assert type(result["confirm"]) is bool
    assert value["reason"] == "  approved  "


@pytest.mark.parametrize("field,value", [("confirm", 1), ("reason", True), ("declared_operator", None)])
def test_adoption_intent_never_coerces_invalid_values(field, value):
    intent = {"confirm": True, "reason": "approved", "declared_operator": "planner"}
    intent[field] = value
    with pytest.raises(WorkbenchCommandRejected) as caught:
        adoption_input(intent)
    assert caught.value.code == "invalid_input"


def test_missing_captured_operation_is_a_classified_evidence_gap():
    with pytest.raises(AdoptionBaselineUnavailable) as caught:
        _captured_row_binding({"op_id": 17}, {}, None)
    assert caught.value.code == "adoption_snapshot_invalid"
    assert caught.value.gap == "baseline.task_operation_binding"


@pytest.mark.parametrize("field", ["context_factory", "context_validator"])
@pytest.mark.parametrize("value", [None, "not-callable"])
def test_unconnected_adoption_callbacks_fail_before_storage(trial_case, field, value):
    svc = service(trial_case.conn)
    setattr(svc, field, value)
    before, changes = snapshot(trial_case.conn), trial_case.conn.total_changes
    with pytest.raises(WorkbenchCommandRejected) as caught:
        svc.preview("a" * 48)
    assert caught.value.code == "storage_failure"
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert snapshot(trial_case.conn) == before
    assert trial_case.conn.total_changes == changes


@pytest.mark.parametrize("source,basis", [("candidate", "run_admission"), ("trial", "trial_creation")])
def test_real_api_preserves_captured_quantities_pagination_and_baseline(trial_case, source, basis):
    case = trial_case
    case.conn.execute("UPDATE Batches SET quantity=3 WHERE batch_id='B1'")
    case.conn.commit()
    first, second = two_versions(case, source)
    case.conn.execute("UPDATE Batches SET quantity=99 WHERE batch_id='B1'")
    case.conn.commit()
    api = make_api(case.path)
    before = api.state()
    latest = api.read(size=1)
    page = api.read(size=1, cursor=latest["data"]["page"]["next_cursor"],
                    snapshot_ref=latest["meta"]["snapshot_ref"])
    assert latest["data"]["plans"][0]["plan_ref"] == second["plan_ref"]
    assert page["data"]["plans"][0]["plan_ref"] == first["plan_ref"]
    data = api.read("/" + second["plan_ref"] + "/workspace")["data"]
    task, = data["tasks"]
    assert {name: task[name] for name in ("piece_id", "quantity", "batch_quantity", "quantity_basis", "quantity_reason")} == {
        "piece_id": None, "quantity": 3, "batch_quantity": 3, "quantity_basis": basis, "quantity_reason": None,
    }
    baseline = data["projections"]["baseline"]
    item, = baseline["items"]
    assert baseline["baseline_plan"]["plan_ref"] == first["plan_ref"]
    assert item["before"]["plan_ref"] == first["plan_ref"]
    assert item["after"] == task
    assert item["before"]["task_ref"] != task["task_ref"]
    assert item["before"]["operation_ref"] == task["operation_ref"]
    assert item["before"]["quantity"] == item["before"]["batch_quantity"] == 3
    assert api.state() == before
    assert api.statements
    assert all(sql.lstrip().upper().startswith(("SELECT", "WITH", "BEGIN", "COMMIT", "--")) for sql in api.statements)


@pytest.mark.parametrize("source", ["candidate", "trial"])
def test_corrupt_receipt_count_cannot_supply_baseline_or_target(trial_case, source):
    _, second = two_versions(trial_case, source)
    key = "da-adopt-" + source + "-second"
    mutate_json(trial_case.conn, "WorkbenchCommandReceipts", "outcome_json",
                lambda receipt: receipt["data"].update(row_count=999), "request_key=?", (key,))
    api = make_api(trial_case.path)
    before = api.state()
    data = api.read("/" + second["plan_ref"] + "/workspace")["data"]
    assert data["projections"]["baseline"]["reason_code"] == "adoption_snapshot_invalid"
    assert data["projections"]["baseline"]["items"] == []
    task, = data["tasks"]
    assert task["quantity"] is None and task["batch_quantity"] is None
    assert task["quantity_reason"] == "plan_target_unavailable"
    assert api.state() == before
