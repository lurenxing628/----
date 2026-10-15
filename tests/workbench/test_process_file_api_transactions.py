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
    created = next(row for row in file_api.rows("Parts") if row["part_no"] == "FILE-NEW")
    identity = next(row for row in file_api.rows("WorkbenchEntityRefs")
                    if row["kind"] == "part" and row["entity_key"] == "FILE-NEW" and row["active"])
    assert created["route_raw"] == "10车削" and created["route_parsed"] == "yes"
    assert identity["revision"] == 1


def test_hours_batch_uses_prepared_rows_and_rolls_back_actual_revision_change(file_api, monkeypatch):
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
    assert calls == [] and len(writes) == 2
    assert file_api.snapshot() == before
    calls.clear()
    with monkeypatch.context() as patch:
        patch.setattr(ProcessTemplateHours, "current", observed)
        receipt = success(file_api.file_post("hours", "confirm", body))
    assert calls == []
    assert receipt["data"]["summary"]["update"] == 2
    node_contract("receipt", receipt, "hours", body=body, preview=preview)


def test_route_file_writes_changed_part_fields_together(file_api, monkeypatch):
    from data.repositories.part_repo import PartRepository
    from tests.workbench.process_stage_api_support import PART

    preview = file_api.preview_rows("route", [{"business_code": PART, "label": "new name", "remark": "new remark",
                                               "route_raw": "10车削20热处理30终检"}])
    assert preview["data"]["can_confirm"]
    writes = []
    update = PartRepository.update

    def observed(repo, code, fields):
        writes.append((code, fields))
        return update(repo, code, fields)

    monkeypatch.setattr(PartRepository, "update", observed)
    result = success(file_api.file_post("route", "confirm", file_api.file_body(preview)))
    assert result["result"] == "committed" and len(writes) == 1
    assert writes[0][0] == PART and writes[0][1] == {
        "part_name": "new name", "remark": "new remark", "route_raw": "10车削20热处理30终检", "route_parsed": "yes"}


@pytest.mark.parametrize("kind,row_count", [("route", 1), ("hours", 3)])
def test_process_export_outlives_original_read_token(file_api, monkeypatch, kind, row_count):
    from core.services.workbench.process.file_codec import decode_process_file
    from tests.workbench.process_stage_api_support import BASE, PART
    from web import public_token_registry

    clock = [1000.0]
    monkeypatch.setattr(public_token_registry.time, "time", lambda: clock[0])
    body, listed = file_api.export_body(scope={"query": PART}, selection="filtered")
    clock[0] = 1800.0
    preview = success(file_api.file_post(kind, "export-preview", body))
    export_ref = preview["data"]["export_ref"]
    assert preview["data"]["row_count"] == row_count

    clock[0] = 1901.0
    rejected(file_api.client.get(BASE + "/entities/part", query_string={
        "query": PART, "size": 2, "snapshot_ref": body["snapshot_ref"]}), "snapshot_stale")
    download = file_api.download(kind, export_ref)
    assert download.status_code == 200, download.get_json()
    assert download.headers["X-Workbench-Snapshot-Ref"] == body["snapshot_ref"]
    assert download.headers["X-Workbench-As-Of"] == listed["meta"]["as_of"]
    rows, _ = decode_process_file(kind, download.data, "csv")
    assert len(rows) == row_count and all(row["values"]["business_code"] == PART for row in rows)

    clock[0] = 2701.0
    rejected(file_api.download(kind, export_ref), "snapshot_stale")
