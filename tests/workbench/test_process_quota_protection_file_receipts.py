"""Actual preview -> confirm -> stored receipt, keeping the public result enum."""

from copy import deepcopy

import pytest

from core.services.workbench.process_queries import WorkbenchProcessQueryService
from tests.workbench.process_file_api_support import node_contract
from tests.workbench.process_quota_protection_file_receipt_support import (
    adopt_second,
    assert_tables_preserved,
    file_rows,
    success,
)
from tests.workbench.process_quota_protection_file_receipt_support import (
    locked_quota_file_api as _locked_api,  # noqa: F401
)
from tests.workbench.process_quota_protection_file_receipt_support import quota_file_api as _file_api  # noqa: F401
from tests.workbench.process_quota_protection_support import adopt, snapshot, templates
from tests.workbench.process_quota_protection_support import quota_case as _quota  # noqa: F401
from tests.workbench.process_workflow_support import confirm_all
from tests.workbench.test_template_lineage_support import completed
from tests.workbench.test_template_lineage_support import ledger_fixture as _ledger  # noqa: F401
from tests.workbench.test_template_lineage_support import lineage_case as _lineage  # noqa: F401


@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
@pytest.mark.parametrize("detail", [False, True])
@pytest.mark.parametrize("layout", ["all_skip", "mixed", "skip_and_noop"])
def test_real_file_receipt_keeps_actual_skip_evidence_and_existing_result_contract(locked_quota_file_api, fmt, detail, layout):
    api, case = locked_quota_file_api, locked_quota_file_api.case
    target = case.ref("part", "P1") if detail else None
    rows = file_rows({"sequence": 1, "unit_hours": 99, "setup_hours": 9})
    if layout != "all_skip":
        rows += file_rows({"sequence": 2, "unit_hours": 8 if layout == "mixed" else 7})
    before, old = snapshot(case.conn), templates(case.conn)
    preview = api.preview(rows, fmt=fmt, target=target)
    assert snapshot(case.conn) == before and preview["data"]["can_confirm"]
    node_contract("preview", preview, "hours", fmt=fmt, target=target)
    body = api.body(preview)
    original_body = deepcopy(body)
    result = success(api.confirm(body))
    assert body == original_body
    node_contract("receipt", result, "hours", body=body, preview=preview, target=target)
    data = result["data"]
    assert result["result"] == ("committed" if layout == "mixed" else "unchanged")
    assert data["skipped_count"] == 1 and data["skipped_refs"] == [case.template_ref]
    assert data["skipped_rows"] == preview["data"]["skipped_rows"]
    skip = data["skipped_rows"][0]
    assert skip["row"] == 2 and skip["template_operation_ref"] == case.template_ref
    assert skip["code"] == "calibration_quota_locked" and skip["reason"] == "Adopt verified completed production samples"
    assert data["rows"][0]["result"] == "unchanged"
    assert data["rows"][0]["skip_reason"] == {key: value for key, value in skip.items() if key != "row"}
    assert data["summary"] == {"new": 0, "update": int(layout == "mixed"),
        "unchanged": len(rows) - int(layout == "mixed"), "delete": 0, "rejected": 0}
    assert data["affected_refs"] == [case.ref("part", "P1")]
    assert api.receipt(body["request_key"]) == {**result, "replayed": True}
    assert api.stored_outcome(body["request_key"]) == {key: result[key] for key in ("result", "data", "warnings")}
    assert templates(case.conn) == ({1: old[1], 2: {**old[2], "unit_hours": 8}} if layout == "mixed" else old)
    allowed = ("PartOperations", "WorkbenchEntityRefs", "WorkbenchCommandReceipts") if layout == "mixed" else ("WorkbenchCommandReceipts",)
    after = snapshot(case.conn)
    assert_tables_preserved(before, after, allowed)
    assert len(after["WorkbenchCommandReceipts"]) == len(before["WorkbenchCommandReceipts"]) + 1
    assert after["WorkbenchCommandReceipts"][:-1] == before["WorkbenchCommandReceipts"]


def test_multiple_actual_locks_retain_each_ref_adoption_and_reason_in_receipt(locked_quota_file_api):
    api, case = locked_quota_file_api, locked_quota_file_api.case
    second = adopt_second(case)
    before = snapshot(case.conn)
    preview = api.preview(file_rows({"sequence": 2, "unit_hours": 99}, {"sequence": 1, "unit_hours": 99}))
    body = api.body(preview)
    result = success(api.confirm(body))
    assert result["result"] == "unchanged" and result["data"]["skipped_count"] == 2
    assert result["data"]["skipped_refs"] == [case.other_ref, case.template_ref]
    assert result["data"]["skipped_rows"][0]["adoption_ref"] == second["data"]["adoption_ref"]
    assert [row["reason"] for row in result["data"]["skipped_rows"]] == ["CW second verified quota", "Adopt verified completed production samples"]
    assert result["data"]["summary"]["unchanged"] == 2 and result["data"]["affected_refs"] == [case.ref("part", "P1")]
    assert api.receipt(body["request_key"])["data"] == result["data"]
    assert_tables_preserved(before, snapshot(case.conn))


@pytest.mark.parametrize("change_setup", [False, True])
def test_equal_locked_quota_is_not_misreported_as_skip(locked_quota_file_api, change_setup):
    api, case = locked_quota_file_api, locked_quota_file_api.case
    before = templates(case.conn)
    preview = api.preview(file_rows({"sequence": 1, "unit_hours": 3, "setup_hours": 9 if change_setup else 0}))
    result = success(api.confirm(api.body(preview)))
    assert result["result"] == ("committed" if change_setup else "unchanged")
    assert result["data"]["skipped_count"] == 0 and result["data"]["skipped_rows"] == result["data"]["skipped_refs"] == []
    assert result["data"]["rows"][0].get("skip_reason") is None
    assert templates(case.conn) == {1: {**before[1], "setup_hours": 9 if change_setup else 0}, 2: before[2]}


def test_all_skipped_zero_quota_does_not_require_zero_ack_or_change_business(locked_quota_file_api):
    api, case = locked_quota_file_api, locked_quota_file_api.case
    before = snapshot(case.conn)
    preview = api.preview(file_rows({"sequence": 1, "unit_hours": 0}))
    assert preview["data"]["zero_review_required"] is False
    body = api.body(preview)
    assert body["input"]["confirm_zero_unit_hours"] is False
    result = success(api.confirm(body))
    assert result["result"] == "unchanged" and result["data"]["skipped_count"] == 1
    assert api.receipt(body["request_key"])["data"] == result["data"]
    assert_tables_preserved(before, snapshot(case.conn))


@pytest.mark.parametrize("equal_adoption", [False, True])
@pytest.mark.parametrize("mixed", [False, True])
def test_lock_added_after_preview_rejects_old_intent_then_reuses_uncommitted_key(quota_file_api, equal_adoption, mixed):
    api, case = quota_file_api, quota_file_api.case
    if equal_adoption:
        case.conn.execute("UPDATE PartOperations SET unit_hours=3 WHERE seq=1")
        case.conn.commit()
        confirm_all(case.conn)
        completed(case, [1, 2, 3, 4, 5], prefix="CW-EQUAL", version=4)
    values = file_rows({"sequence": 1, "unit_hours": 99})
    if mixed:
        values += file_rows({"sequence": 2, "unit_hours": 8})
    preview = api.preview(values, fmt="xlsx")
    body = api.body(preview)
    assert preview["data"]["skipped_count"] == 0
    reader = WorkbenchProcessQueryService(case.conn)
    with reader.read_snapshot() as state_before:
        pass
    adopt(case)
    with reader.read_snapshot() as state_after:
        pass
    assert (state_before == state_after) == equal_adoption
    before = snapshot(case.conn)
    for _ in range(2):
        response = api.confirm(body)
        assert response.status_code == 409 and response.get_json()["error"]["code"] == "stale_write"
        assert response.get_json()["committed"] is False and snapshot(case.conn) == before
        missing = api.receipt(body["request_key"])
        assert missing["state"] == "not_recorded" and missing["may_be_in_flight"] is True
    refreshed = api.preview(values, fmt="xlsx")
    same_key = api.body(refreshed, key=body["request_key"])
    result = success(api.confirm(same_key))
    assert result["result"] == ("committed" if mixed else "unchanged") and result["data"]["skipped_count"] == 1
    assert api.receipt(body["request_key"]) == {**result, "replayed": True}
    if not mixed:
        assert_tables_preserved(before, snapshot(case.conn))


def test_route_import_receipt_contract_is_unchanged(quota_file_api):
    api, case = quota_file_api, quota_file_api.case
    before = snapshot(case.conn)
    preview = api.preview([{"business_code": "P1", "label": "Part"}], kind="route")
    body = api.body(preview)
    result = success(api.confirm(body, kind="route"))
    assert set(result["data"]) == {"kind", "rows", "summary", "affected_refs"}
    assert result["result"] == "unchanged" and result["data"]["summary"] == preview["data"]["summary"]
    node_contract("preview", preview, "route")
    node_contract("receipt", result, "route", body=body, preview=preview)
    assert_tables_preserved(before, snapshot(case.conn))
