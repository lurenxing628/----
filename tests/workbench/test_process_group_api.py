"""Outsourcing-stage preview, confirmation and receipt replay."""

from core.infrastructure.transaction import TransactionManager
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
