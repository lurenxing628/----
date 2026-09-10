"""Actual route/hours bytes through preflight, confirmation and Node contracts."""

import hashlib

import pytest

from core.models.workbench_process_file import INT64_MAX
from core.services.workbench.process_file_codec import encode_process_file
from tests.workbench.process_file_api_support import PART, file_api_fixture, node_contract
from tests.workbench.process_stage_api_support import rejected, success


@pytest.mark.parametrize("kind", ["route", "hours"])
@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
@pytest.mark.parametrize("detail", [False, True])
def test_real_bytes_confirm_and_receipt_match_node(file_api, kind, fmt, detail):
    target = file_api.ref() if detail else None
    history = {name: file_api.rows(name) for name in ("Batches", "BatchOperations", "Schedule")}
    preview, body = file_api.file_intent(kind, fmt, target)
    node_contract("preview", preview, kind, target=target, fmt=fmt)
    assert all(not {"expected", "input", "related"} & set(row) for row in preview["data"]["rows"])
    receipt = success(file_api.file_post(kind, "confirm", body))
    node_contract("receipt", receipt, kind, body=body, preview=preview, target=target)
    assert receipt["result"] == "committed" and receipt["replayed"] is False
    assert {name: file_api.rows(name) for name in history} == history
    if kind == "hours":
        operations = {row["seq"]: row for row in file_api.rows("PartOperations", "part_no=?", (PART,))}
        assert operations[10]["unit_hours"] == 2 and operations[30]["unit_hours"] == 3
        assert operations[10]["private_stage_note"] == " hidden original "
    else:
        assert file_api.rows("Parts", "part_no=?", (PART,))[0]["part_name"] == "Changed label"


@pytest.mark.parametrize("kind", ["route", "hours"])
@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_export_import_unchanged_keeps_all_business_and_confirmation_rows(file_api, kind, fmt):
    if kind == "hours":
        file_api.prepare()
    target = file_api.ref()
    _, _, download = file_api.export(kind, fmt=fmt, selection="explicit", refs=[target], target=target)
    before = file_api.snapshot()
    preview = success(file_api.upload(kind, download.data, fmt, target))
    assert file_api.snapshot() == before
    assert preview["data"]["file_sha256"] == hashlib.sha256(download.data).hexdigest()
    assert preview["data"]["summary"]["unchanged"] == len(preview["data"]["rows"])
    node_contract("preview", preview, kind, target=target, fmt=fmt)
    body = file_api.file_body(preview, zero=True)
    result = success(file_api.file_post(kind, "confirm", body))
    node_contract("receipt", result, kind, body=body, preview=preview, target=target)
    after = file_api.snapshot()
    assert result["result"] == "unchanged"
    assert {key: value for key, value in after[1].items() if key != "WorkbenchCommandReceipts"} == {
        key: value for key, value in before[1].items() if key != "WorkbenchCommandReceipts"}
    assert len(after[1]["WorkbenchCommandReceipts"]) == len(before[1]["WorkbenchCommandReceipts"]) + 1


@pytest.mark.parametrize("kind", ["route", "hours"])
@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_rejected_row_rejects_whole_import(file_api, kind, fmt):
    if kind == "hours":
        file_api.prepare()
    rows = [{"business_code": "PROC-002", "label": "must not change"}, {"business_code": "BAD-NEW"}] if kind == "route" else [
        {"business_code": PART, "sequence": 10, "unit_hours": 9}, {"business_code": "MISSING", "sequence": 10, "unit_hours": 9}]
    before = file_api.snapshot()
    preview = file_api.preview_rows(kind, rows, fmt)
    node_contract("preview", preview, kind, fmt=fmt)
    assert not preview["data"]["can_confirm"] and preview["data"]["summary"]["rejected"] == 1
    rejected(file_api.file_post(kind, "confirm", file_api.file_body(preview)), "constraint_conflict")
    assert file_api.snapshot() == before


@pytest.mark.parametrize("kind", ["route", "hours"])
def test_detail_import_never_updates_other_part(file_api, kind):
    if kind == "hours":
        file_api.prepare()
    target = file_api.ref(code="PROC-002")
    rows = [{"business_code": PART, "label": "forbidden"}] if kind == "route" else [
        {"business_code": PART, "sequence": 10, "unit_hours": 9}]
    before = file_api.snapshot()
    preview = file_api.preview_rows(kind, rows, target=target)
    node_contract("preview", preview, kind, target=target)
    assert not preview["data"]["can_confirm"]
    rejected(file_api.file_post(kind, "confirm", file_api.file_body(preview)), "constraint_conflict")
    assert file_api.snapshot() == before


@pytest.mark.parametrize("zero", [False, None, 0, "true"])
def test_zero_requires_explicit_boolean_ack(file_api, zero):
    file_api.prepare()
    preview = file_api.preview_rows("hours", [{"business_code": PART, "sequence": 10, "unit_hours": 0}])
    node_contract("preview", preview, "hours")
    assert preview["data"]["zero_review_required"] is True
    assert preview["data"]["rows"][0]["requires_confirmation"] is True
    body = file_api.file_body(preview, zero=zero)
    before = file_api.snapshot()
    rejected(file_api.file_post("hours", "confirm", body), "zero_review_required" if zero is False else "invalid_input",
             409 if zero is False else 400)
    assert file_api.snapshot() == before
    body["input"]["confirm_zero_unit_hours"] = True
    result = success(file_api.file_post("hours", "confirm", body))
    node_contract("receipt", result, "hours", body=body, preview=preview)


def test_group_ack_is_exact_complete_set(file_api):
    file_api.execute("INSERT INTO Parts(part_no,part_name,route_raw) VALUES ('GROUP-OTHER','Other','10\u70ed\u5904\u7406')")
    file_api.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days) VALUES ('GROUP-2','GROUP-OTHER',10,10,'merged',3)")
    file_api.execute("INSERT INTO PartOperations(part_no,seq,op_type_name,op_type_id,source,ext_group_id) VALUES ('GROUP-OTHER',10,'\u70ed\u5904\u7406','PROC-EX','external','GROUP-2')")
    rows = [{"business_code": PART, "route_raw": "10\u8f66\u524a30\u68c0\u9a8c"},
            {"business_code": "GROUP-OTHER", "route_raw": "10\u8f66\u524a"}]
    preview = file_api.preview_rows("route", rows)
    node_contract("preview", preview, "route")
    refs = [group["ref"] for group in preview["data"]["affected_groups"]]
    assert len(refs) == 2 and preview["data"]["can_confirm"]
    before = file_api.snapshot()
    for ack in ([], refs[:1], refs + [file_api.ref()], refs + refs):
        response = file_api.file_post("route", "confirm", file_api.file_body(preview, groups=ack))
        assert response.status_code in (409, 422), response.get_json()
        assert file_api.snapshot() == before
    body = file_api.file_body(preview, groups=refs)
    result = success(file_api.file_post("route", "confirm", body))
    node_contract("receipt", result, "route", body=body, preview=preview)
    assert file_api.rows("ExternalGroups") == []


@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_hours_int64_preview_and_receipt_are_precise_text(file_api, fmt):
    file_api.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,setup_hours,unit_hours) VALUES ('PROC-002',?,'PROC-IN','\u8f66\u524a','internal',0,1)", (INT64_MAX,))
    from core.infrastructure.transaction import TransactionManager
    from core.services.process.workflow_state import record_confirmation

    with file_api.database() as conn:
        with TransactionManager(conn).transaction(begin_immediate=True):
            record_confirmation(conn, "PROC-002", "route")
            record_confirmation(conn, "PROC-002", "source")
    target = file_api.ref(code="PROC-002")
    content = encode_process_file("hours", [{"business_code": "PROC-002", "sequence": INT64_MAX, "unit_hours": 5}], fmt).content
    preview = success(file_api.upload("hours", content, fmt, target))
    node_contract("preview", preview, "hours", target=target, fmt=fmt)
    assert preview["data"]["rows"][0]["sequence"] == str(INT64_MAX)
    body = file_api.file_body(preview)
    result = success(file_api.file_post("hours", "confirm", body))
    node_contract("receipt", result, "hours", body=body, preview=preview, target=target)
    assert result["data"]["rows"][0]["sequence"] == str(INT64_MAX)
