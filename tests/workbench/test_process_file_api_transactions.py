"""Receipt replay and injected failures prove original-byte atomic commands."""

from dataclasses import replace

import pytest

from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.process_file_hours import ProcessHoursFileOperations
from core.services.workbench.process_file_route import ProcessRouteFileOperations
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from tests.workbench.process_file_api_support import BASE, PART, file_api_fixture, node_contract, uncertain_failure
from tests.workbench.process_stage_api_support import rejected, success
from web.routes.workbench.resource_action_context import EXTENSION


@pytest.mark.parametrize("kind", ["route", "hours"])
def test_replay_precedes_expired_context_and_changed_facts(file_api, kind):
    preview, body = file_api.file_intent(kind)
    first = success(file_api.file_post(kind, "confirm", body))
    file_api.client.application.extensions[EXTENSION].clear()
    file_api.execute("UPDATE Parts SET remark='after receipt' WHERE part_no=?", (PART,))
    body["write_token"] = "expired"
    before = file_api.snapshot()
    replay = success(file_api.file_post(kind, "confirm", body))
    node_contract("receipt", replay, kind, body=body, preview=preview)
    assert replay == {**first, "replayed": True}
    assert success(file_api.client.get(BASE + "/commands/" + body["request_key"])) == replay
    body["input"]["confirm_zero_unit_hours"] = True
    rejected(file_api.file_post(kind, "confirm", body), "request_key_conflict")
    assert file_api.snapshot() == before


@pytest.mark.parametrize("kind", ["route", "hours"])
@pytest.mark.parametrize("failure", ["second-row", "receipt"])
def test_row_or_receipt_failure_rolls_back_whole_file(file_api, monkeypatch, kind, failure):
    preview, body = file_api.file_intent(kind)
    if failure == "receipt":
        owner, name = WorkbenchCommandRepository, "insert"
    else:
        owner, name = ((ProcessRouteFileOperations, "_apply_row") if kind == "route" else
                       (ProcessHoursFileOperations, "_operation_update"))
    original = getattr(owner, name)
    calls = []

    def fail_after(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(True)
        if len(calls) == (1 if failure == "receipt" else 2):
            raise OSError("injected file failure after mutation")
        return result

    before = file_api.snapshot()
    with monkeypatch.context() as patch:
        patch.setattr(owner, name, fail_after)
        error = uncertain_failure(file_api.file_post(kind, "confirm", body))
    assert len(calls) == (1 if failure == "receipt" else 2)
    assert file_api.snapshot() == before
    missing = success(file_api.client.get(error["result_target"]))
    assert missing["state"] == "not_recorded" and missing["may_be_in_flight"] is True
    result = success(file_api.file_post(kind, "confirm", body))
    node_contract("receipt", result, kind, body=body, preview=preview)


@pytest.mark.parametrize("kind", ["route", "hours"])
def test_response_loss_recovers_actual_committed_receipt(file_api, monkeypatch, kind):
    preview, body = file_api.file_intent(kind)
    original = WorkbenchCommandService.execute

    def lose_response(self, **kwargs):
        original(self, **kwargs)
        raise OSError("response lost after commit")

    with monkeypatch.context() as patch:
        patch.setattr(WorkbenchCommandService, "execute", lose_response)
        error = uncertain_failure(file_api.file_post(kind, "confirm", body))
    before = file_api.snapshot()
    receipt = success(file_api.client.get(error["result_target"]))
    node_contract("receipt", receipt, kind, body=body, preview=preview)
    assert receipt["result"] == "committed" and receipt["replayed"] is True
    assert success(file_api.file_post(kind, "confirm", body)) == receipt
    assert file_api.snapshot() == before


@pytest.mark.parametrize("kind", ["route", "hours"])
@pytest.mark.parametrize("change", ["part", "hidden-operation", "group", "supplier", "workflow", "new-batch", "same-number", "bytes", "expired"])
def test_confirm_repreviews_bytes_and_all_facts(file_api, kind, change):
    if change == "workflow" and kind == "route":
        file_api.prepare()
    preview, body = file_api.file_intent(kind)
    if change == "part":
        file_api.execute("UPDATE Parts SET remark='unselected changed' WHERE part_no='PROC-004'")
    elif change == "hidden-operation":
        file_api.execute("UPDATE PartOperations SET private_stage_note=X'00FF' WHERE part_no='PROC-004'")
    elif change == "group":
        file_api.execute("UPDATE ExternalGroups SET remark='changed group' WHERE group_id='PROC-G'")
    elif change == "supplier":
        file_api.execute("UPDATE Suppliers SET default_days=9 WHERE supplier_id='PROC-S'")
    elif change == "workflow":
        file_api.execute("UPDATE WorkbenchProcessWorkflow SET route_confirmed_at='1999-01-01T00:00:00' WHERE part_ref=?", (file_api.ref(),))
    elif change == "new-batch":
        file_api.execute("INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date) VALUES ('NEW-B','PROC-002','New',1,'2026-10-01')")
    elif change == "same-number":
        file_api.execute("DELETE FROM Parts WHERE part_no='PROC-002'")
        file_api.execute("INSERT INTO Parts(part_no,part_name) VALUES ('PROC-002','Recreated')")
    else:
        store = file_api.client.application.extensions[EXTENSION]
        if change == "expired":
            store.clear()
        else:
            for key, value in list(store.items()):
                if value.content is not None:
                    store[key] = replace(value, content=value.content + b"\r\n")
    before = file_api.snapshot()
    rejected(file_api.file_post(kind, "confirm", body), "stale_write")
    assert file_api.snapshot() == before
