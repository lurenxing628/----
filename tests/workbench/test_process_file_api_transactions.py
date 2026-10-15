"""File rollback and lost-response recovery use the committed receipt."""

import pytest

from core.services.process.template_hours import ProcessTemplateHours
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.process.file_route import ProcessRouteFileOperations
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from data.repositories.workbench_process_hours_repo import WorkbenchProcessHoursRepository
from tests.workbench.process_file_api_support import file_api_fixture, node_contract, uncertain_failure
from tests.workbench.process_stage_api_support import rejected, success

_fixture = file_api_fixture


@pytest.mark.parametrize("kind,failure", [("route", "second-row"), ("hours", "receipt")])
def test_row_or_receipt_failure_rolls_back_whole_file(file_api, monkeypatch, kind, failure):
    preview, body = file_api.file_intent(kind)
    if failure == "receipt":
        owner, name = WorkbenchCommandRepository, "insert"
    else:
        owner, name = ProcessRouteFileOperations, "_apply_row"
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


@pytest.mark.parametrize("kind", ["route"])
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


def test_hours_batch_reads_current_once_and_rolls_back_actual_revision_change(file_api, monkeypatch):
    preview, body = file_api.file_intent("hours")
    before, calls, writes = file_api.snapshot(), [], []
    current, update = ProcessTemplateHours.current, WorkbenchProcessHoursRepository.update_operation_hours

    def observed(self, refs):
        calls.append(tuple(refs))
        return current(self, refs)

    def change_before_write(self, op_id, values, *, ref, revision):
        writes.append(op_id)
        if len(writes) == 2:
            self.conn.execute("UPDATE PartOperations SET unit_hours=99 WHERE id=?", (op_id,))
        return update(self, op_id, values, ref=ref, revision=revision)

    with monkeypatch.context() as patch:
        patch.setattr(ProcessTemplateHours, "current", observed)
        patch.setattr(WorkbenchProcessHoursRepository, "update_operation_hours", change_before_write)
        rejected(file_api.file_post("hours", "confirm", body), "stale_write")
    assert len(calls) == 1 and len(calls[0]) == 2 and len(writes) == 2
    assert file_api.snapshot() == before
    calls.clear()
    with monkeypatch.context() as patch:
        patch.setattr(ProcessTemplateHours, "current", observed)
        receipt = success(file_api.file_post("hours", "confirm", body))
    assert len(calls) == 1 and len(calls[0]) == 2
    assert receipt["data"]["summary"]["update"] == 2
    node_contract("receipt", receipt, "hours", body=body, preview=preview)
