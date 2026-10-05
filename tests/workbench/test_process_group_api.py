"""Outsourcing-stage preview, confirmation and receipt replay."""

from tests.workbench.process_stage_api_support import PART, stage_api_fixture, success

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
