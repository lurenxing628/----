"""Single-operation edit contexts fence its facts without following unrelated ledger writes."""

import pytest

from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.field_workspace_support import BASE, _ledger_fixture, success
from tests.workbench.field_workspace_support import field_api as _field_api


def test_other_operation_report_does_not_expire_this_edit_context(field_api):
    api, case = field_api, field_api.case
    case.conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B2','P1',10)")
    other = case.op("OTHER", batch="B2")
    case.plan(2, [case.op_id, other])
    task_ref = case.task(2, case.op_id)
    task = next(row for row in api.read()["data"]["tasks"] if row["task_ref"] == task_ref)
    before = case.ledger.snapshot(task["operation_ref"])
    clock = case.ledger.revision_clock()
    case.command("create", case.task(2, other), case.values(1))
    assert case.ledger.revision_clock() != clock
    assert case.ledger.snapshot(task["operation_ref"]) == before
    assert api.create(case.values(1), task=task)["result"] == "committed"


def test_related_predecessor_is_rechecked_even_when_own_context_stays_current(field_api):
    api, case = field_api, field_api.case
    successor = case.op("SUCCESSOR", seq=2)
    case.plan(2, [case.op_id, successor])
    task_ref = case.task(2, successor)
    task = next(row for row in api.read()["data"]["tasks"] if row["task_ref"] == task_ref)
    snapshot = case.ledger.snapshot(task["operation_ref"])
    case.command("create", case.task(2, case.op_id), case.values(10))
    assert case.ledger.snapshot(task["operation_ref"]) == snapshot
    before = all_rows(case.conn)
    body = api.body(task["execution"]["write_context"], case.values(1))
    response = api.client.post(BASE + "/tasks/" + task_ref + "/reports", json=body)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "constraint_conflict"
    assert all_rows(case.conn) == before


@pytest.mark.parametrize("change", ["new_report", "correct", "void", "task", "plan"])
def test_own_report_history_task_or_plan_change_expires_edit_context(field_api, change):
    api, case = field_api, field_api.case
    row = case.command("create", case.task(1, case.op_id), case.values(3))["data"]["rows"][0]
    task = api.task()
    snapshot = case.ledger.snapshot(task["operation_ref"])
    if change == "new_report":
        case.command("create", task["task_ref"], case.values(1))
    elif change == "correct":
        case.command("correct", row["report_ref"], {"original_revision_ref": row["revision_ref"],
                     "completed_quantity": 4, "reason": "Checked quantity"})
    elif change == "void":
        case.command("report_void", row["report_ref"], {"original_revision_ref": row["revision_ref"],
                     "reason": "Wrong operation"})
    elif change == "task":
        case.conn.execute("UPDATE Schedule SET start_time='2026-09-09T08:30:00' WHERE version=1")
        case.conn.commit()
    else:
        case.plan(2, [case.op_id])
    assert case.ledger.snapshot(task["operation_ref"]) != snapshot
    before = all_rows(case.conn)
    body = api.body(task["execution"]["write_context"], case.values(1))
    response = api.client.post(BASE + "/tasks/" + task["task_ref"] + "/reports", json=body)
    assert response.status_code == 409, response.get_json()
    assert all_rows(case.conn) == before
