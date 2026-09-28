"""A real shipment protects its original batch without manufacturing production reports."""

import pytest

from tests.workbench.batch_support import BASE, batch_database, detail, list_data, post, ref_for
from tests.workbench.outsourcing_support import OutsourcingCase

_batch_fixture = batch_database


def register_shipment(client, *, returned=False):
    conn = client.batch_conn
    conn.execute("UPDATE BatchOperations SET source='external',supplier_id='S1',ext_days=2 WHERE batch_id='FREE-001'")
    conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id,default_days,status) VALUES ('S2','Other supplier','OT1',2,'active')")
    conn.commit()
    case = OutsourcingCase(None, conn)
    payload = {"target": {"kind": "single", "batch_ref": ref_for(client), "supplier_ref": ref_for(client, "supplier", "S1"),
                          "operation_refs": [case.operation_ref("FREE-001_01")]},
               "sent": "2026-09-07T09:00:00", "planned": "2026-09-09T12:00:00",
               "returned": "2026-09-09T11:00:00" if returned else None,
               "confirmedState": "returned" if returned else "in_transit",
               "declared_operator": "Shipping clerk", "reason": "Verified shipping sheet"}
    with client.application.app_context():
        saved = case.confirm(case.preview(payload))
    return case, saved["data"]["outsourcing_ref"]


@pytest.mark.parametrize("returned", [False, True])
@pytest.mark.parametrize("action", ["supplier", "sync", "delete", "quantity", "bulk_delete"])
def test_existing_shipment_blocks_identity_breaking_batch_actions(batch_client, action, returned):
    client = batch_client
    case, receipt_ref = register_shipment(client, returned=returned)
    entity = detail(client)["data"]
    assert entity["protected"] and not entity["operations"][0]["editable"]
    assert entity["relationships"]["plan_reference_count"] == 0
    assert entity["relationships"]["execution_reference_count"] == 0
    before = [tuple(row) for row in case.conn.execute("SELECT * FROM BatchOperations WHERE batch_id='FREE-001'")]
    if action == "supplier":
        response = post(client, "operation_update", {"operation_ref": entity["operations"][0]["ref"],
                         "fields": {"supplier_ref": ref_for(client, "supplier", "S2")}})
    elif action == "sync":
        response = client.post(BASE + "/" + entity["ref"] + "/sync-preview",
            json={"snapshot_ref": detail(client)["meta"]["snapshot_ref"], "input": {}})
    elif action == "bulk_delete":
        response = client.post(BASE + "/bulk-preview", json={"scope": {}, "snapshot_ref": list_data(client)["meta"]["snapshot_ref"],
            "input": {"action": "delete", "refs": [entity["ref"]], "patch": {}}})
    else:
        response = post(client, "delete" if action == "delete" else "update", {} if action == "delete" else {"fields": {"quantity": 6}})
    value = response.get_json()
    expected_code = "stale_write" if action in ("supplier", "delete") else "constraint_conflict"
    assert response.status_code == 409 and value["error"]["code"] == expected_code, value
    if expected_code == "stale_write":
        # Those actions are absent from the server-issued write token, before any mutation is attempted.
        assert all("外协" in reason["message"] for reason in entity["write_context"]["blocked_reasons"])
    else:
        assert "外协" in value["error"]["message"]
    assert [tuple(row) for row in case.conn.execute("SELECT * FROM BatchOperations WHERE batch_id='FREE-001'")] == before
    with client.application.app_context():
        receipt = case.detail(receipt_ref)
        assert receipt["can_preview"] and receipt["source_state"] == "current"
        assert case.confirm(case.preview({"outsourcing_ref": receipt_ref, "returned": "2026-09-10T10:00:00",
            "confirmedState": "returned", "declared_operator": "Receiver", "reason": "Return verified"}))["result"] == "committed"


def test_new_shipment_invalidates_preexisting_batch_write_context(batch_client):
    client = batch_client
    context = detail(client)["data"]["write_context"]
    register_shipment(client)
    result = post(client, "delete", {}, context=context)
    assert result.status_code == 409
    assert client.batch_conn.execute("SELECT 1 FROM Batches WHERE batch_id='FREE-001'").fetchone()


def test_non_destructive_metadata_edit_and_other_batches_remain_available(batch_client):
    client = batch_client
    register_shipment(client)
    result = post(client, "update", {"fields": {"remark": "Follow up with receiving clerk"}})
    assert result.status_code == 200, result.get_json()
    assert detail(client)["data"]["fields"]["remark"] == "Follow up with receiving clerk"


def test_historical_same_number_receipt_does_not_protect_new_batch_instance(batch_client):
    client = batch_client
    case, receipt_ref = register_shipment(client)
    old_ref = ref_for(client)
    # Simulate retained history in a restored legacy database; the UI cannot perform this deletion.
    case.conn.execute("DELETE FROM Batches WHERE batch_id='FREE-001'")
    case.conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('FREE-001','P1',5)")
    case.conn.commit()
    assert ref_for(client) != old_ref
    assert not detail(client)["data"]["protected"]
    with client.application.app_context():
        assert case.detail(receipt_ref)["source_state"] == "source_unavailable"


@pytest.mark.parametrize("table", ["WorkbenchOutsourcingReceipts", "BatchExternalContexts"])
def test_missing_current_external_tables_do_not_silently_remove_protection(batch_client, table):
    client = batch_client
    batch_ref = ref_for(client)
    client.batch_conn.execute("UPDATE SchemaVersion SET version=33 WHERE id=1")
    client.batch_conn.execute('DROP TABLE "' + table + '"')
    client.batch_conn.commit()
    response = client.get(BASE + "/" + batch_ref)
    assert response.status_code == 503, response.get_json()
    assert response.get_json()["error"]["code"] == "batch_facts_unavailable"
