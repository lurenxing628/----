"""The upload route alone admits format and mode; file rollback and lost-response recovery use the committed receipt."""

import pytest

from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.process.file_codec import encode_process_file
from core.services.workbench.process.file_route import ProcessRouteFileOperations
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from data.repositories.workbench_process_hours_repo import WorkbenchProcessHoursRepository
from tests.workbench.process_file_api_support import file_api_fixture, node_contract, uncertain_failure
from tests.workbench.process_stage_api_support import BASE, rejected, success

_fixture = file_api_fixture


@pytest.mark.parametrize("kind", ["route", "hours"])
def test_upload_rejects_unknown_format_without_writes(file_api, kind):
    before = file_api.snapshot()
    body = rejected(file_api.upload(kind, encode_process_file(kind, [], "csv").content, fmt="txt"), "invalid_input", 422)
    assert [field["path"] for field in body["error"]["fields"]] == ["format"]
    assert file_api.snapshot() == before


@pytest.mark.parametrize("kind", ["route", "hours"])
def test_upload_rejects_non_upsert_mode_without_writes(file_api, kind):
    before = file_api.snapshot()
    body = rejected(file_api.upload(kind, encode_process_file(kind, [], "csv").content, mode="replace"), "invalid_input", 400)
    assert body["error"]["fields"] == []
    assert file_api.snapshot() == before


@pytest.mark.parametrize("kind", ["route", "hours"])
@pytest.mark.parametrize("fmt,status", [("txt", 422), ("XLSX", 422), ("csv", 200), ("xlsx", 200)])
def test_template_admits_format_at_route(file_api, kind, fmt, status):
    response = file_api.client.get(BASE + "/process-files/" + kind + "/template", query_string={"format": fmt})
    if status == 200:
        assert response.status_code == 200 and response.headers["Content-Disposition"].startswith("attachment")
        assert response.headers["Content-Disposition"].endswith("." + fmt)
    else:
        body = rejected(response, "invalid_input", status)
        assert [field["path"] for field in body["error"]["fields"]] == ["format"]


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
    missing_resp = file_api.client.get(error["result_target"])
    assert missing_resp.status_code == 200
    missing = missing_resp.get_json()
    assert (
        missing["state"] == "not_observed"
        and missing["resolution"] == "unresolved"
        and missing["may_be_in_flight"] is True
        and missing["receipt"] is None
    )
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
    recorded_resp = file_api.client.get(error["result_target"])
    assert recorded_resp.status_code == 200
    recorded = recorded_resp.get_json()
    assert (
        recorded["state"] == "recorded"
        and recorded["resolution"] == "recorded"
        and recorded["may_be_in_flight"] is False
    )
    receipt = recorded["receipt"]
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
    from data.repositories.workbench_process_query_repo import WorkbenchProcessQueryRepository

    preview, body = file_api.file_intent("hours")
    before, calls, writes = file_api.snapshot(), [], []
    read_operations = WorkbenchProcessQueryRepository.operations
    update = WorkbenchProcessHoursRepository.update_operation_hours

    def observed(self):
        calls.append(self.part_ref)
        return read_operations(self)

    def change_before_write(self, op_id, values, *, ref, revision):
        writes.append(op_id)
        if len(writes) == 2:
            self.conn.execute("UPDATE PartOperations SET unit_hours=99 WHERE id=?", (op_id,))
        return update(self, op_id, values, ref=ref, revision=revision)

    with monkeypatch.context() as patch:
        patch.setattr(WorkbenchProcessQueryRepository, "operations", observed)
        patch.setattr(WorkbenchProcessHoursRepository, "update_operation_hours", change_before_write)
        rejected(file_api.file_post("hours", "confirm", body), "stale_write")
    assert len(calls) == 1 and len(writes) == 2
    assert file_api.snapshot() == before
    calls.clear()
    with monkeypatch.context() as patch:
        patch.setattr(WorkbenchProcessQueryRepository, "operations", observed)
        receipt = success(file_api.file_post("hours", "confirm", body))
    assert len(calls) == 1
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


@pytest.mark.parametrize("kind,row_count", [("route", 1), ("hours", 3)])
def test_detail_export_reuses_target_snapshot_across_unrelated_template_changes(file_api, kind, row_count):
    from core.services.workbench.process.file_codec import decode_process_file
    from tests.workbench.process_stage_api_support import PART

    target = file_api.ref()
    body, detail = file_api.export_body(target=target, selection="explicit", refs=[target])
    file_api.execute("UPDATE Parts SET remark='其他零件已更新' WHERE part_no='PROC-003'")
    preview = success(file_api.file_post(kind, "export-preview", body))
    assert preview["data"]["row_count"] == row_count
    file_api.execute("UPDATE PartOperations SET unit_hours=9 WHERE part_no='PROC-004'")
    download = file_api.download(kind, preview["data"]["export_ref"])
    assert download.status_code == 200, download.get_json()
    assert download.headers["X-Workbench-Snapshot-Ref"] == detail["meta"]["snapshot_ref"]
    rows, _ = decode_process_file(kind, download.data, "csv")
    assert len(rows) == row_count and all(row["values"]["business_code"] == PART for row in rows)


def test_explicit_list_export_downloads_preflighted_refs_and_rechecks_the_snapshot(file_api, monkeypatch):
    from core.services.workbench.process import scope as process_scope
    from core.services.workbench.process.file_codec import decode_process_file
    from tests.workbench.process_stage_api_support import PART
    from web.routes.workbench import process_file_exports

    body, _ = file_api.export_body(selection="explicit", refs=[file_api.ref()])
    preview = success(file_api.file_post("route", "export-preview", body))
    with monkeypatch.context() as patch:
        for owner, name in ((process_file_exports, "_export_selection"), (process_scope, "check_part_ref")):
            patch.setattr(owner, name, lambda *args: pytest.fail("下载不该再准入预检已存的范围"))
        download = file_api.download("route", preview["data"]["export_ref"])
    assert download.status_code == 200, download.get_json()
    rows, _ = decode_process_file("route", download.data, "csv")
    assert [row["values"]["business_code"] for row in rows] == [PART]
    preview = success(file_api.file_post("route", "export-preview", body))
    file_api.execute("UPDATE Parts SET remark='导出预检后已改' WHERE part_no=?", (PART,))
    rejected(file_api.download("route", preview["data"]["export_ref"]), "snapshot_stale")


def test_detail_export_rejects_nontext_target_before_capture(file_api):
    target = file_api.ref()
    body, _ = file_api.export_body(target=target, selection="explicit", refs=[target])
    body["target_ref"] = {"ref": target}
    rejected(file_api.file_post("route", "export-preview", body), "invalid_input", 400)
    bad_refs_body, _ = file_api.export_body(selection="explicit", refs=["not-a-part-ref"])
    bad_refs = rejected(file_api.file_post("route", "export-preview", bad_refs_body), "invalid_input", 422)
    assert bad_refs["error"]["message"] == "请选择有效的零件记录，选择列表不能为空或重复。"
    bad_target = rejected(file_api.upload("route", b"bad,header\r\n1,2\r\n", target="not-a-part-ref"), "entity_not_found", 404)
    assert bad_target["error"]["message"] == "零件记录不存在，请返回列表重新选择。"


def test_route_file_create_reuses_workflow_identities_and_outer_command_transaction(file_api, monkeypatch):
    from core.infrastructure.transaction import TransactionManager
    from core.services.workbench.process.queries import WorkbenchProcessQueryService

    preview = file_api.preview_rows(
        "route",
        [
            {"business_code": "FILE-NEW-ROUTE", "label": "带路线新件", "route_raw": "10车削", "remark": ""},
            {"business_code": "FILE-NEW-EMPTY", "label": "无路线新件", "route_raw": "", "remark": ""},
        ],
    )
    assert preview["data"]["can_confirm"]
    statements = []
    original_execute = WorkbenchCommandService.execute

    def trace_execute(self, **kwargs):
        self.conn.set_trace_callback(statements.append)
        try:
            return original_execute(self, **kwargs)
        finally:
            self.conn.set_trace_callback(None)

    with monkeypatch.context() as patch:
        patch.setattr(WorkbenchCommandService, "execute", trace_execute)
        receipt = success(file_api.file_post("route", "confirm", file_api.file_body(preview)))

    assert any(sql == "BEGIN IMMEDIATE" for sql in statements)
    assert any(sql == "COMMIT" for sql in statements)
    assert not any("SAVEPOINT" in sql for sql in statements)
    assert not any("FROM WorkbenchEntityRefs WHERE kind = 'part' AND entity_key =" in sql for sql in statements)

    route_ref = file_api.ref(code="FILE-NEW-ROUTE")
    empty_ref = file_api.ref(code="FILE-NEW-EMPTY")
    rows_by_code = {row["business_code"]: row for row in receipt["data"]["rows"]}
    assert rows_by_code["FILE-NEW-ROUTE"]["entity_ref"] == route_ref
    assert rows_by_code["FILE-NEW-EMPTY"]["entity_ref"] == empty_ref
    assert receipt["data"]["affected_refs"] == sorted([route_ref, empty_ref])

    route_detail = file_api.detail("FILE-NEW-ROUTE")["data"]["workflow"]
    empty_detail = file_api.detail("FILE-NEW-EMPTY")["data"]["workflow"]
    assert route_detail["origin"] == "managed" and route_detail["route"]["state"] == "confirmed"
    assert empty_detail["origin"] == "managed" and empty_detail["route"]["state"] == "missing"

    with file_api.database() as conn:
        reader = WorkbenchProcessQueryService(conn)
        assert not conn.in_transaction
        with reader.read_snapshot():
            assert conn.in_transaction
        assert not conn.in_transaction

        nested_sql = []
        with TransactionManager(conn).transaction(begin_immediate=True):
            assert conn.in_transaction
            conn.set_trace_callback(nested_sql.append)
            try:
                with reader.read_snapshot():
                    assert conn.in_transaction
            finally:
                conn.set_trace_callback(None)
            assert conn.in_transaction
        assert not conn.in_transaction
        assert not any("SAVEPOINT" in sql for sql in nested_sql)
