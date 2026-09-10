"""Exact batch sets, immutable ledger preservation, copy and receipt replay."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.batch_bulk import WorkbenchBatchBulkService
from core.services.workbench.commands import WorkbenchCommandService
from tests.workbench.batch_support import BASE, assert_error, batch_database, body, detail, post, ref_for, state
from tests.workbench.test_batch_actions import confirm, preview
from tests.workbench.test_batch_execution_ledger_support import batch_ledger_fixture, report
from tests.workbench.test_batch_files import confirm as file_confirm
from tests.workbench.test_batch_files import uploaded

_batch_fixture = batch_database
_ledger_fixture = batch_ledger_fixture
LEDGER_TABLES = ("WorkbenchExecutionLegacyFacts", "WorkbenchProductionReports", "WorkbenchProductionReportRevisions", "WorkbenchExecutionLedgerClock")


@pytest.mark.parametrize("evidence", ["report", "legacy"])
def test_copy_never_copies_reports_legacy_progress_or_old_identity(batch_ledger, evidence):
    case = batch_ledger
    if evidence == "report":
        report(case, 5)
    else:
        case.event(case.op_id, "start", version=7, batch_id="FREE-001")
        case.event(case.op_id, "finish", version=7, quantity=5, batch_id="FREE-001")
    before = state(case.client)
    pending = preview(case.client, "copy")
    after = pending["rows"][0]["after"]
    assert not after["protected"] and after["relationships"]["execution_reference_count"] == 0
    assert after["operations"][0]["execution"] is None and not after["operations"][0]["completed"]
    response = confirm(case.client, pending)
    assert response.status_code == 200, response.get_json()
    saved = response.get_json()
    copy_ref = saved["data"]["items"][0]["entity_ref"]
    entity = detail(case.client, copy_ref)["data"]
    assert entity["business_code"] == "FREE-002" and not entity["protected"]
    op = entity["operations"][0]
    assert op["operation_ref"] != case.operation_ref and op["execution_state"] == "unreported"
    assert op["execution"]["reports"] == [] and op["execution"]["legacy_facts"] == []
    assert op["execution"]["remaining_quantity"] == 5 and not op["completed"]
    changed = state(case.client)
    for table in LEDGER_TABLES:
        assert changed[1][table] == before[1][table]
    retry = {**pending, "write_context": {"write_token": "expired"}}
    again = confirm(case.client, retry).get_json()
    assert again["replayed"] and again["receipt_ref"] == saved["receipt_ref"]
    assert state(case.client) == changed
    assert post(case.client, "delete", {}, ref=copy_ref, key="batch-copy-delete-0001").status_code == 200


@pytest.mark.parametrize("failure", ["second_write", "receipt"])
def test_bulk_metadata_rolls_back_every_table_including_receipt(batch_ledger, monkeypatch, failure):
    from core.services.scheduler.batch_service import BatchService
    from data.repositories.workbench_command_repo import WorkbenchCommandRepository

    case = batch_ledger
    report(case)
    pending = preview(case.client, refs=[case.batch_ref, ref_for(case.client, key="B1")], patch={"remark": "atomic"})
    before = state(case.client)
    original, calls = BatchService.update, []

    def fail_second(service, *args, **kwargs):
        calls.append(args)
        if len(calls) == 2:
            raise RuntimeError("AP injected second-row failure")
        return original(service, *args, **kwargs)

    def fail_receipt(*args, **kwargs):
        raise RuntimeError("AP injected receipt failure")

    with monkeypatch.context() as patch:
        if failure == "second_write":
            patch.setattr(BatchService, "update", fail_second)
        else:
            patch.setattr(WorkbenchCommandRepository, "insert", fail_receipt)
        response = confirm(case.client, pending)
    assert response.status_code == 500 and response.get_json()["committed"] == "unknown"
    assert state(case.client) == before
    if failure == "second_write":
        assert len(calls) == 2
    saved = confirm(case.client, pending).get_json()
    assert saved["ok"] and saved["data"]["count"] == 2 and saved["data"]["commit_policy"] == "atomic"
    assert {item["entity_ref"] for item in saved["data"]["items"]} == {case.batch_ref, ref_for(case.client, key="B1")}
    committed = state(case.client)
    assert confirm(case.client, {**pending, "write_context": {"write_token": "expired"}}).get_json()["receipt_ref"] == saved["receipt_ref"]
    assert state(case.client) == committed
    for table in LEDGER_TABLES:
        assert committed[1][table] == before[1][table]


def test_file_replacement_quantity_and_stale_confirmation_respect_new_reports(batch_ledger):
    case = batch_ledger
    rows = [["FREE-001", "P1", 5, None, None, None, None, "metadata"]]
    pending = uploaded(case.client, rows).get_json()["data"]
    assert pending["can_confirm"]
    report(case)
    before = state(case.client)
    assert_error(file_confirm(case.client, pending), "stale_write")
    assert state(case.client) == before
    quantity = uploaded(case.client, [["FREE-001", "P1", 6, None, None, None, None, "quantity"]]).get_json()["data"]
    assert not quantity["can_confirm"]
    replacement = uploaded(case.client, rows, mode="replace").get_json()["data"]
    assert not replacement["can_confirm"]
    row = next(item for item in replacement["deleted"] if item["entity_ref"] == case.batch_ref)
    assert row["errors"]
    current = uploaded(case.client, rows).get_json()["data"]
    assert current["can_confirm"]
    response = file_confirm(case.client, current, key="batch-file-metadata-001")
    assert response.status_code == 200, response.get_json()
    assert detail(case.client)["data"]["fields"]["remark"] == "metadata"
    after = state(case.client)
    for table in LEDGER_TABLES:
        assert after[1][table] == before[1][table]


def test_correction_invalidates_preview_even_when_report_count_unchanged(batch_ledger):
    case = batch_ledger
    saved = report(case)["data"]["rows"][0]
    pending = preview(case.client, patch={"remark": "pending"})
    case.command("correct", saved["report_ref"], {"remark": "verified correction",
        "original_revision_ref": saved["revision_ref"], "reason": "source verified"})
    before = state(case.client)
    assert_error(confirm(case.client, pending), "stale_write")
    assert state(case.client) == before
    op = detail(case.client)["data"]["operations"][0]
    assert len(op["execution"]["reports"]) == 1
    assert len(op["execution"]["reports"][0]["correction_history"]) == 2


def test_bulk_delete_mixed_reported_and_free_is_all_or_nothing(batch_ledger):
    case = batch_ledger
    report(case)
    case.conn.execute("DELETE FROM Schedule")
    case.conn.execute("DELETE FROM BatchMaterials")
    case.conn.commit()
    free_ref = ref_for(case.client, key="B1")
    assert not detail(case.client, free_ref)["data"]["protected"]
    assert detail(case.client)["data"]["protected"]
    before = state(case.client)
    payload = {"action": "delete", "refs": [free_ref, case.batch_ref]}
    with pytest.raises(WorkbenchCommandRejected) as error:
        WorkbenchCommandService(case.conn).execute(request_key="batch-ledger-mixed-delete", action="batch.bulk_confirm",
            context_ref=case.batch_ref, normalized_input=payload, guard=lambda: None,
            mutate=lambda _: WorkbenchBatchBulkService(case.conn).apply(payload))
    assert error.value.code == "constraint_conflict" and state(case.client) == before
    assert WorkbenchCommandService(case.conn).lookup("batch-ledger-mixed-delete") is None
