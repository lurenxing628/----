"""Outsourcing-stage preview, confirmation and receipt replay."""

import json

from core.infrastructure.transaction import TransactionManager
from core.models.content import content_text
from core.services.process.workflow_state import record_confirmation
from tests.workbench.process_stage_api_support import PART, rejected, stage_api_fixture, success

_api_fixture = stage_api_fixture


def edit(api, days=8.125):
    entity = api.detail()["data"]
    return {"groups": [{"ref": entity["external_groups"][0]["ref"],
                        "operation_refs": [row["ref"] for row in entity["operations"] if row["source"] == "external"],
                        "supplier_ref": entity["operations"][1]["supplier_ref"], "total_days": days}],
            "discard_group_refs": []}


def test_group_preview_command_and_receipt_roundtrip(stage_api):
    api = stage_api
    with api.database() as conn:
        conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id,default_days,status) "
                     "VALUES ('PROC-S2','另一热处理厂','PROC-EX',3.25,'active')")
        conn.execute("UPDATE ExternalGroups SET end_seq=21,supplier_id=NULL WHERE group_id='PROC-G'")
        conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days,"
                     "ext_group_id,setup_hours,unit_hours) VALUES ('PROC-001',21,'PROC-EX','热处理','external','PROC-S2',3.25,'PROC-G',0,0)")
        conn.execute("DELETE FROM Schedule WHERE op_id IN (SELECT id FROM BatchOperations WHERE batch_id='PROC-B')")
        with TransactionManager(conn).transaction():
            record_confirmation(conn, PART, "route")
    before = api.snapshot()
    rejected(api.preview("source_confirm", api.source()), "group_supplier_mismatch", 422)
    assert api.snapshot() == before
    entity = api.detail()["data"]
    assert not entity["workflow"]["ready"]
    assert any(row["code"] == "external_group_supplier_mismatch" for row in entity["external_groups"][0]["issues"])
    path = "/api/workbench/v1/entities/batch/" + api.ref("batch", "PROC-B")
    detail = success(api.client.get(path))
    assert not detail["data"]["template"]["complete"]
    rejected(api.client.post(path + "/sync-preview", json={"input": {}, "snapshot_ref": detail["meta"]["snapshot_ref"]}),
             "constraint_conflict")
    api.execute("UPDATE PartOperations SET supplier_id='PROC-S' WHERE part_no=? AND seq=21", (PART,))
    api.confirm("source_confirm", api.source())
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
    part_ref = api.ref()
    confirmations = api.rows("WorkbenchProcessOperationConfirmations", "part_ref=?", (part_ref,))
    stored = api.rows("WorkbenchProcessWorkflow", "part_ref=?", (part_ref,))[0]
    assert all(row["signature"] is None and row["content_json"] for row in confirmations)
    assert all(stored[stage + "_signature"] is None and stored[stage + "_content_json"] for stage in ("route", "source", "hours"))
    source_document = json.loads(stored["source_content_json"])
    group_ref = detail["external_groups"][0]["ref"]
    assert len(source_document[3]) == 1 and len(source_document[3][group_ref]["members"]) == 2
    external_refs = {row["ref"] for row in api.detail()["data"]["operations"] if row["source"] == "external"}
    source_row = next(row for row in confirmations if row["stage"] == "source" and row["operation_ref"] in external_refs)
    local_document = json.loads(source_row["content_json"])
    assert "members" not in local_document[2][8]
    assert local_document[2][7]["capable"] is True
    local_document[2][7]["capable"] = 1
    api.execute("UPDATE WorkbenchProcessOperationConfirmations SET content_json=? WHERE operation_ref=? AND stage='source'",
                (content_text(local_document), source_row["operation_ref"]))
    changed = api.detail()["data"]
    assert not changed["workflow"]["ready"]
    assert next(row for row in changed["operations"] if row["ref"] == source_row["operation_ref"])["confirmation"]["source"]["state"] == "unconfirmed"
    api.confirm("source_confirm", api.source())
    assert api.detail()["data"]["workflow"]["ready"]
    # A shared membership change affects the group's operations, not an unrelated internal operation.
    api.execute("UPDATE PartOperations SET ext_group_id=NULL WHERE part_no=? AND seq=21", (PART,))
    changed = api.detail()["data"]
    assert not changed["workflow"]["ready"]
    assert all(row["confirmation"]["source"]["state"] == "unconfirmed" for row in changed["operations"] if row["ref"] in external_refs)
    assert all(row["confirmation"]["source"]["state"] == "confirmed" for row in changed["operations"] if row["source"] == "internal")
    api.execute("UPDATE PartOperations SET ext_group_id='PROC-G' WHERE part_no=? AND seq=21", (PART,))
    assert api.detail()["data"]["workflow"]["ready"]
    # Old markers preserve the actual historical record while current facts require a new confirmation.
    legacy_marker, legacy_stamp, legacy_person = "a" * 64, "2001-02-03T04:05:06Z", "原确认人"
    business = api.preserved()
    with api.database() as conn:
        for stage in ("route", "source", "hours"):
            conn.execute("UPDATE WorkbenchProcessWorkflow SET " + stage + "_signature=?," + stage + "_content_json=NULL,"
                         + stage + "_confirmed_at=?," + stage + "_confirmed_by=? WHERE part_ref=?",
                         (legacy_marker, legacy_stamp, legacy_person, part_ref))
        conn.execute("UPDATE WorkbenchProcessOperationConfirmations SET signature=?,content_json=NULL,confirmed_at=?,confirmed_by=? WHERE part_ref=?",
                     (legacy_marker, legacy_stamp, legacy_person, part_ref))
    old_rows = api.snapshot()
    historical = api.detail()["data"]
    assert historical["workflow"]["route"]["state"] == "unconfirmed" and not historical["workflow"]["ready"]
    for stage in ("route", "source", "hours"):
        current = historical["workflow"][stage]
        assert current["content_state"] == "missing_original" and "重新确认" in current["reason"]
        assert current["history"] == {"confirmed_at": legacy_stamp, "confirmed_by": legacy_person}
        assert current["confirmed_at"] is None and current["confirmed_by"] is None
    assert all(row["confirmation"]["source"]["content_state"] == "missing_original" for row in historical["operations"] if row["status"] == "active")
    assert api.snapshot() == old_rows
    rejected(api.preview("source_confirm", api.source()), "stage_locked")
    with api.database() as conn:
        with TransactionManager(conn).transaction():
            record_confirmation(conn, PART, "route")
    api.confirm("source_confirm", api.source())
    api.confirm("hours_confirm", api.hours())
    assert api.detail()["data"]["workflow"]["ready"] and api.preserved() == business
    stored = api.rows("WorkbenchProcessWorkflow", "part_ref=?", (part_ref,))[0]
    assert all(stored[stage + "_signature"] == legacy_marker and stored[stage + "_content_json"]
               and stored[stage + "_confirmed_at"] != legacy_stamp for stage in ("route", "source", "hours"))
    assert all(row["signature"] == legacy_marker and row["content_json"] and row["confirmed_at"] != legacy_stamp
               for row in api.rows("WorkbenchProcessOperationConfirmations", "part_ref=?", (part_ref,)))
    detail = success(api.client.get(path))
    assert detail["data"]["template"]["complete"]
    preview = success(api.client.post(path + "/sync-preview", json={"input": {}, "snapshot_ref": detail["meta"]["snapshot_ref"]}))["data"]
    synced = success(api.client.post(path + "/sync-confirm", json={"request_key": "supplier-group-sync-merged",
        "write_token": preview["write_context"]["write_token"], "input": {"preview_ref": preview["preview_ref"]}}))
    assert synced["result"] == "committed"
    external = [row for row in success(api.client.get(path))["data"]["operations"] if row["source"] == "external"]
    assert len(external) == 2 and {row["resources"]["supplier"]["business_code"] for row in external} == {"PROC-S"}
    # The same route may keep an old default supplier while its separate work
    # is assigned elsewhere. Only the actual members' qualification matters.
    api.execute("UPDATE ExternalGroups SET merge_mode='separate',total_days=NULL WHERE group_id='PROC-G'")
    source = api.source()
    for row in source["operations"]:
        if row["source"] == "external":
            row["supplier_ref"] = api.ref("supplier", "PROC-S2")
    api.confirm("source_confirm", source)
    api.confirm("hours_confirm", api.hours())
    assert api.detail()["data"]["workflow"]["ready"]
    api.execute("UPDATE Suppliers SET status='inactive' WHERE supplier_id='PROC-S'")
    assert api.detail()["data"]["workflow"]["ready"]
    detail = success(api.client.get(path))
    assert detail["data"]["template"]["complete"]
    success(api.client.post(path + "/sync-preview", json={"input": {}, "snapshot_ref": detail["meta"]["snapshot_ref"]}))
    api.execute("UPDATE Suppliers SET status='inactive' WHERE supplier_id='PROC-S2'")
    assert not api.detail()["data"]["workflow"]["ready"]
