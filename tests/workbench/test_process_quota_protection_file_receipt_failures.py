"""Persisted skip receipts retain original-key replay and whole-command rollback."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier

import pytest

from core.services.workbench import process_files
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.process_file_hours import ProcessHoursFileOperations
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from tests.workbench import process_quota_protection_file_receipt_support as support
from tests.workbench.process_quota_protection_file_receipt_support import BASE, file_rows, success
from tests.workbench.process_quota_protection_file_receipt_support import (
    locked_quota_file_api as _locked_api,  # noqa: F401
)
from tests.workbench.process_quota_protection_file_receipt_support import quota_file_api as _file_api  # noqa: F401
from tests.workbench.process_quota_protection_support import connect, snapshot
from tests.workbench.process_quota_protection_support import quota_case as _quota  # noqa: F401
from tests.workbench.test_template_lineage_support import ledger_fixture as _ledger  # noqa: F401
from tests.workbench.test_template_lineage_support import lineage_case as _lineage  # noqa: F401
from web.routes.workbench.resource_action_context import EXTENSION


def request_for(api, mixed):
    rows = file_rows({"sequence": 1, "unit_hours": 99})
    if mixed:
        rows += file_rows({"sequence": 2, "unit_hours": 8})
    return api.body(api.preview(rows))


def uncertain(response, key):
    body = response.get_json()
    assert response.status_code == 500 and body["ok"] is False
    assert body["committed"] == "unknown" and body["error"]["code"] == "storage_failure"
    assert body["error"]["request_key"] == key
    assert body["error"]["result_target"] == BASE + "/commands/" + key
    return body


@pytest.mark.parametrize("mixed", [False, True])
def test_committed_skip_receipt_replays_before_expired_preview_and_rejects_key_reuse(locked_quota_file_api, mixed):
    api, case = locked_quota_file_api, locked_quota_file_api.case
    body = request_for(api, mixed)
    result = success(api.confirm(body))
    case.app.extensions[EXTENSION].clear()
    body["write_token"] = "expired"
    before = snapshot(case.conn)
    replay = success(api.confirm(body))
    assert replay == {**result, "replayed": True} == api.receipt(body["request_key"])
    assert replay["data"]["skipped_count"] == 1 and replay["data"]["skipped_refs"] == [case.template_ref]
    conflict = deepcopy(body)
    conflict["input"]["confirm_zero_unit_hours"] = True
    response = api.confirm(conflict)
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "request_key_conflict"
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("mixed,phase", [(True, "write"), (True, "summary"), (False, "receipt"),
                                       (True, "receipt"), (False, "commit"), (True, "commit")])
def test_failures_roll_back_business_and_skip_receipt_then_retry_original_key(locked_quota_file_api, monkeypatch, mixed, phase):
    api, case = locked_quota_file_api, locked_quota_file_api.case
    body = request_for(api, mixed)
    original_body = deepcopy(body)
    before = snapshot(case.conn)
    calls = []

    class FailCommit(sqlite3.Connection):
        def commit(self):
            calls.append("commit")
            raise OSError("CW HTTP commit failure")

    with monkeypatch.context() as patch:
        if phase == "commit":
            patch.setattr(support, "connect", lambda target: connect(target, factory=FailCommit))
        else:
            owner, name = ((ProcessHoursFileOperations, "_operation_update") if phase == "write" else
                           (process_files, "_hours_result_rows") if phase == "summary" else
                           (WorkbenchCommandRepository, "insert"))
            original = getattr(owner, name)

            def fail_after(*args, **kwargs):
                result = original(*args, **kwargs)
                calls.append(phase)
                if len(calls) == (2 if phase == "summary" else 1):
                    raise OSError("CW HTTP failure after " + phase)
                return result

            patch.setattr(owner, name, fail_after)
        uncertain(api.confirm(body), body["request_key"])
    assert len(calls) == (2 if phase == "summary" else 1)
    assert body == original_body and snapshot(case.conn) == before
    missing = api.receipt(body["request_key"])
    assert missing["state"] == "not_recorded" and missing["may_be_in_flight"] is True
    result = success(api.confirm(body))
    assert result["result"] == ("committed" if mixed else "unchanged") and result["data"]["skipped_count"] == 1
    assert api.receipt(body["request_key"]) == {**result, "replayed": True}
    assert len(snapshot(case.conn)["WorkbenchCommandReceipts"]) == len(before["WorkbenchCommandReceipts"]) + 1


@pytest.mark.parametrize("mixed", [False, True])
def test_response_loss_recovers_actual_skip_receipt_without_reapplying(locked_quota_file_api, monkeypatch, mixed):
    api, case = locked_quota_file_api, locked_quota_file_api.case
    body = request_for(api, mixed)
    execute = WorkbenchCommandService.execute
    saved = []

    def lose_response(service, **kwargs):
        saved.append(execute(service, **kwargs))
        raise OSError("CW lost response after commit")

    with monkeypatch.context() as patch:
        patch.setattr(WorkbenchCommandService, "execute", lose_response)
        uncertain(api.confirm(body), body["request_key"])
    before_retry = snapshot(case.conn)
    assert len(saved) == 1 and saved[0]["data"]["skipped_count"] == 1
    replay = api.receipt(body["request_key"])
    assert replay == {**saved[0], "replayed": True} == success(api.confirm(body))
    assert snapshot(case.conn) == before_retry


def test_two_http_connections_with_same_key_commit_one_skip_receipt(locked_quota_file_api):
    api, case = locked_quota_file_api, locked_quota_file_api.case
    body = request_for(api, True)
    barrier = Barrier(2)
    before = snapshot(case.conn)

    def worker(_):
        client = case.app.test_client()
        barrier.wait(timeout=5)
        return success(client.post(BASE + "/process-files/hours/confirm", json=body))

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(worker, range(2)))
    assert sorted([first["replayed"], second["replayed"]]) == [False, True]
    assert first["receipt_ref"] == second["receipt_ref"] and first["data"] == second["data"]
    assert first["data"]["skipped_count"] == 1 and first["data"]["summary"]["update"] == 1
    after = snapshot(case.conn)
    assert len(after["WorkbenchCommandReceipts"]) == len(before["WorkbenchCommandReceipts"]) + 1
    assert api.receipt(body["request_key"])["data"] == first["data"]
