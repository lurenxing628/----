"""New report facts protect destructive writes inside the command transaction."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.batch_operations import WorkbenchBatchOperationService
from core.services.workbench.batches import WorkbenchBatchService
from core.services.workbench.commands import WorkbenchCommandService
from tests.workbench.batch_execution_ledger_support import batch_ledger_fixture, remove_plan_rows, report
from tests.workbench.batch_support import BASE, assert_error, batch_database, body, detail, list_data, post, state
from tests.workbench.test_batch_actions import confirm, preview

_batch_fixture = batch_database
_ledger_fixture = batch_ledger_fixture


@pytest.mark.parametrize("quantity", [None, 0, 2, 5])
@pytest.mark.parametrize("evidence", ["report", "legacy"])
def test_execution_protects_without_old_status_events_or_plan_rows(batch_ledger, quantity, evidence):
    case = batch_ledger
    if evidence == "report":
        report(case, quantity)
    else:
        case.event(case.op_id, "start", version=7, batch_id="FREE-001")
        case.event(case.op_id, "finish", version=7, quantity=quantity, batch_id="FREE-001")
        case.conn.execute("DELETE FROM OperationExecutionEvents")
        case.conn.commit()
    remove_plan_rows(case)
    assert case.conn.execute("SELECT count(*) FROM OperationExecutionEvents").fetchone()[0] == 0
    entity = detail(case.client)["data"]
    assert entity["protected"]
    for action in ("batch.delete", "batch.sync_confirm", "batch.operation_update"):
        assert not entity["write_context"]["capabilities"][action]
    before = state(case.client)
    mutations = [lambda: WorkbenchBatchService(case.conn).apply("delete", {}, case.batch_ref),
                 lambda: WorkbenchBatchService(case.conn).apply("update", {"fields": {"quantity": 6}}, case.batch_ref),
                 lambda: WorkbenchBatchOperationService(case.conn).sync(case.batch_ref, {}),
                 lambda: WorkbenchBatchOperationService(case.conn).update(case.batch_ref,
                     {"operation_ref": case.operation_ref, "fields": {"unit_hours": 2}})]
    for index, mutate in enumerate(mutations):
        with pytest.raises(WorkbenchCommandRejected) as error:
            WorkbenchCommandService(case.conn).execute(request_key=f"batch-ledger-guard-{index:02d}",
                action="batch.fixture", context_ref=case.batch_ref, normalized_input={}, guard=lambda: None,
                mutate=lambda _, apply=mutate: apply())
        assert error.value.code == "constraint_conflict"
        assert state(case.client) == before
    response = post(case.client, "update", {"fields": {"remark": "retained", "priority": "urgent", "due_date": "2026-10-01"}})
    assert response.status_code == 200, response.get_json()
    assert detail(case.client)["data"]["fields"]["remark"] == "retained"
    after = state(case.client)
    for table in ("WorkbenchProductionReports", "WorkbenchProductionReportRevisions", "WorkbenchExecutionLegacyFacts", "WorkbenchExecutionLedgerClock"):
        assert before[1][table] == after[1][table]


def test_new_report_invalidates_old_token_list_snapshot_and_bulk_preview(batch_ledger):
    case = batch_ledger
    initial = list_data(case.client)
    token = detail(case.client)["data"]["write_context"]
    pending = preview(case.client, patch={"remark": "previewed"})
    report(case)
    before = state(case.client)
    assert_error(post(case.client, "update", {"fields": {"remark": "stale"}}, context=token), "stale_write")
    assert_error(case.client.get(BASE, query_string={"snapshot_ref": initial["meta"]["snapshot_ref"]}), "snapshot_stale")
    assert_error(confirm(case.client, pending), "stale_write")
    assert state(case.client) == before


def test_sync_preview_drift_when_reporting_other_current_operation(batch_ledger):
    case = batch_ledger
    # FREE has no plan or execution; another operation can report after its preview.
    case.conn.execute("DELETE FROM Schedule WHERE op_id=?", (case.op_id,))
    case.conn.commit()
    source = detail(case.client)
    response = case.client.post(BASE + "/" + case.batch_ref + "/sync-preview", json={
        "snapshot_ref": source["meta"]["snapshot_ref"], "input": {}})
    assert response.status_code == 200, response.get_json()
    payload = response.get_json()["data"]
    case.command("create", case.task(7, 31), case.values(1))
    before = state(case.client)
    assert_error(confirm(case.client, payload, "/" + case.batch_ref + "/sync-confirm"), "stale_write")
    assert state(case.client) == before
