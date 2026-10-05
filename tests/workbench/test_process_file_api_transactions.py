"""File rollback and lost-response recovery use the committed receipt."""

import pytest

from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.process.file_route import ProcessRouteFileOperations
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from tests.workbench.process_file_api_support import file_api_fixture, node_contract, uncertain_failure
from tests.workbench.process_stage_api_support import success

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
