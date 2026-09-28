"""Outsourcing-stage review is read-only and binds exact edits to the receipt."""

from copy import deepcopy

import pytest

from tests.workbench.process_stage_api_support import PART, rejected, stage_api_fixture, success

_api_fixture = stage_api_fixture


def edit(api, days=8.125):
    entity = api.detail()["data"]
    return {"groups": [{"ref": entity["external_groups"][0]["ref"],
                        "operation_refs": [entity["operations"][1]["ref"]],
                        "supplier_ref": entity["operations"][1]["supplier_ref"], "total_days": days}],
            "discard_group_refs": []}


def test_group_preview_command_and_receipt_roundtrip(stage_api):
    api = stage_api
    api.prepare()
    before = api.snapshot()
    payload = edit(api)
    preview = success(api.preview("groups_confirm", payload))
    assert api.snapshot() == before
    assert preview["data"]["changes"][0]["before"]["total_days"] == 6.75
    assert preview["data"]["changes"][0]["after"]["total_days"] == 8.125
    body = api.body("groups_confirm", payload)
    first = success(api.post("groups_confirm", body))
    assert first["data"]["stage"] == "groups"
    assert success(api.post("groups_confirm", body)) == {**first, "replayed": True}
    detail = api.detail()["data"]
    assert detail["external_groups"][0]["total_days"] == 8.125
    assert detail["operations"][1]["external_days_source"] == "group"
    assert detail["workflow"]["source"]["state"] == "confirmed" and not detail["workflow"]["ready"]
    assert api.rows("PartOperations", "part_no=? AND seq=20", (PART,))[0]["ext_days"] == 3.25
    api.confirm("hours_confirm", api.hours())
    assert api.detail()["data"]["workflow"]["ready"]


@pytest.mark.parametrize("tamper", ("days", "discard", "data"))
def test_group_review_token_rejects_changed_input_or_snapshot(stage_api, tamper):
    api = stage_api
    api.prepare()
    body = api.body("groups_confirm", edit(api))
    if tamper == "days":
        body["input"]["groups"][0]["total_days"] += 1
    elif tamper == "discard":
        body["input"] = {"groups": [], "discard_group_refs": [body["input"]["groups"][0]["ref"]]}
    else:
        api.execute("UPDATE Parts SET remark='changed snapshot' WHERE part_no=?", (PART,))
    before = api.snapshot()
    rejected(api.post("groups_confirm", body), "stale_write")
    assert api.snapshot() == before


def test_group_release_requires_own_fresh_preview_and_does_not_confirm_source(stage_api):
    api = stage_api
    api.prepare("source")
    group = api.detail()["data"]["external_groups"][0]
    payload = {"groups": [], "discard_group_refs": [group["ref"]]}
    preview = success(api.preview("groups_confirm", payload))["data"]
    assert preview["changes"][0]["action"] == "discard" and preview["changes"][0]["after"] is None
    api.confirm("groups_confirm", payload)
    entity = api.detail()["data"]
    assert entity["external_groups"] == [] and entity["operations"][1]["external_group_ref"] is None
    assert entity["operations"][1]["external_days"] == 3.25
    assert entity["workflow"]["source"]["state"] == "unconfirmed"


def test_supplier_capability_errors_identify_operation_and_supplier_at_preview(stage_api):
    api = stage_api
    api.prepare("source")
    api.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id,default_days) VALUES ('WRONG','表面厂',NULL,2)")
    payload = api.source()
    payload["operations"][1]["supplier_ref"] = api.ref("supplier", "WRONG")
    before = api.snapshot()
    body = rejected(api.preview("source_confirm", deepcopy(payload)), "supplier_capability_mismatch", 422)
    error = body["error"]
    assert "20" in error["message"] and "表面厂" in error["message"] and "热处理" in error["message"]
    assert error["fields"][0]["path"] == "operations." + payload["operations"][1]["ref"] + ".supplier_ref"
    assert api.snapshot() == before
