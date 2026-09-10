"""Batch atomic previews, template copies and actual resource constraints."""

from core.infrastructure.transaction import TransactionManager
from core.services.process.workflow_state import start_workflow
from tests.workbench.batch_support import (
    BASE,
    assert_error,
    batch_database,
    body,
    detail,
    list_data,
    post,
    ref_for,
    state,
)
from tests.workbench.identity_metadata_support import insert_row

_batch_fixture = batch_database


def preview(client, action="update", refs=None, patch=None):
    response = client.post(BASE + "/bulk-preview", json={"scope": {}, "snapshot_ref": list_data(client)["meta"]["snapshot_ref"],
        "input": {"action": action, "refs": refs or [ref_for(client)], "patch": patch or {}}})
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def sync_preview(client, strict=False):
    ref = ref_for(client)
    return client.post(BASE + "/" + ref + "/sync-preview", json={"snapshot_ref": detail(client)["meta"]["snapshot_ref"], "input": {"strict_mode": strict}})


def confirm(client, data, path="/bulk-confirm", key="batch-preview-confirm-001"):
    return client.post(BASE + path, json=body(data["write_context"], {"preview_ref": data["preview_ref"]}, key))


def test_bulk_modify_copy_delete_actual_records_atomic(batch_client):
    client = batch_client
    before = state(client)
    p = preview(client, patch={"priority": "urgent", "remark": "bulk"})
    assert state(client) == before and p["count"] == 1 and p["commit_policy"] == "atomic"
    assert confirm(client, p).status_code == 200
    assert detail(client)["data"]["fields"]["remark"] == "bulk"
    p = preview(client, "copy")
    assert p["rows"][0]["after"]["business_code"] == "FREE-002"
    response = confirm(client, p, key="batch-copy-confirm-0001")
    assert response.status_code == 200, response.get_json()
    created = response.get_json()["data"]["items"][0]["entity_ref"]
    row = detail(client, created)["data"]
    assert row["status"] == "pending" and not row["all_operations_complete"]
    assert row["operations"][0]["setup_hours"] is None and row["operations"][0]["unit_hours"] == 0
    assert row["operations"][0]["ref"] != detail(client)["data"]["operations"][0]["ref"]
    p = preview(client, "delete", [created])
    assert confirm(client, p, key="batch-delete-confirm-01").status_code == 200
    assert_error(client.get(BASE + "/" + created), "entity_not_found")


def test_preview_drift_and_injected_second_write_rollback(batch_client, monkeypatch):
    from core.services.scheduler.batch_service import BatchService

    client = batch_client
    p = preview(client, patch={"remark": "x"})
    client.batch_conn.execute("UPDATE Parts SET remark='concurrent'")
    client.batch_conn.commit()
    before = state(client)
    assert_error(confirm(client, p), "stale_write")
    assert state(client) == before
    p = preview(client, refs=[ref_for(client), ref_for(client, key="B1")], patch={"remark": "x"})
    original, calls = BatchService.update, []

    def fail_second(svc, *args, **kwargs):
        calls.append(args)
        if len(calls) == 2:
            raise RuntimeError("fixture second-row failure")
        return original(svc, *args, **kwargs)

    monkeypatch.setattr(BatchService, "update", fail_second)
    before = state(client)
    assert confirm(client, p).get_json()["committed"] == "unknown"
    assert len(calls) == 2 and state(client) == before


def test_sync_managed_gate_strict_missing_fields_and_null_preservation(batch_client):
    client = batch_client
    conn = client.batch_conn
    conn.execute("UPDATE PartOperations SET source='internal',setup_hours=NULL,unit_hours=0,ext_group_id=NULL,ext_days=NULL,supplier_id=NULL")
    conn.commit()
    before = state(client)
    assert_error(sync_preview(client, strict=True), "constraint_conflict")
    assert state(client) == before
    response = sync_preview(client)
    assert response.status_code == 200, response.get_json()
    p = response.get_json()["data"]
    old = detail(client)["data"]["operations"][0]["ref"]
    assert confirm(client, p, "/" + ref_for(client) + "/sync-confirm").status_code == 200
    op = detail(client)["data"]["operations"][0]
    assert op["setup_hours"] is None and op["unit_hours"] == 0 and op["ref"] != old
    assert client.batch_conn.execute("SELECT active FROM WorkbenchPlanSourceRefs WHERE ref=?", (old,)).fetchone()[0] == 0
    with TransactionManager(conn).transaction():
        start_workflow(conn, "P1")
    before = state(client)
    assert_error(sync_preview(client), "constraint_conflict")
    assert state(client) == before


def test_operations_patch_preserves_null_zero_and_rejects_wrong_authorization(batch_client):
    client = batch_client
    op = detail(client)["data"]["operations"][0]
    response = post(client, "operation_update", {"operation_ref": op["ref"], "fields": {"machine_ref": ref_for(client, "machine", "M1"), "operator_ref": ref_for(client, "operator", "O1")}})
    assert response.status_code == 200, response.get_json()
    changed = detail(client)["data"]["operations"][0]
    assert changed["setup_hours"] is None and changed["unit_hours"] == 0 and changed["ref"] == op["ref"]
    client.batch_conn.execute("DELETE FROM OperatorMachine")
    client.batch_conn.commit()
    before = state(client)
    assert_error(post(client, "operation_update", {"operation_ref": op["ref"], "fields": {"unit_hours": 1}}, key="batch-unauth-00000001"), "invalid_input")
    assert state(client) == before


def test_merged_external_period_never_overridden(batch_client):
    client = batch_client
    client.batch_conn.execute("UPDATE BatchOperations SET source='external',supplier_id='S1' WHERE batch_id='FREE-001'")
    client.batch_conn.execute("UPDATE ExternalGroups SET merge_mode='merged',total_days=7")
    client.batch_conn.commit()
    op = detail(client)["data"]["operations"][0]
    before = state(client)
    assert op["external_group"]["merge_mode"] == "merged" and op["external_group"]["total_days"] == 7
    assert_error(post(client, "operation_update", {"operation_ref": op["ref"], "fields": {"external_days": 2}}), "constraint_conflict")
    assert state(client) == before


def test_partial_completion_is_not_batch_completion(batch_client):
    client = batch_client
    client.batch_conn.execute("UPDATE BatchOperations SET status='completed' WHERE batch_id='FREE-001'")
    insert_row(client.batch_conn, "BatchOperations", dict(op_code="FREE-001_02", batch_id="FREE-001", seq=2,
               op_type_id="OT1", op_type_name="turning", source="internal", setup_hours=0, unit_hours=0, status="pending"))
    client.batch_conn.execute("UPDATE Batches SET status='completed' WHERE batch_id='FREE-001'")
    client.batch_conn.commit()
    entity = detail(client)["data"]
    assert entity["relationships"]["completed_count"] == 1 and entity["relationships"]["operation_count"] == 2
    assert not entity["all_operations_complete"] and any(row["code"] == "completion_inconsistent" for row in entity["issues"])
    assert entity["operations"][1]["status"] == "pending" and not entity["operations"][1]["completed"]


def test_selection_facets_and_filter_before_pagination(batch_client):
    client = batch_client
    scope = {"page": 1, "size": 1, "sort": "quantity", "direction": "desc", "column_filters": {"ready_status": ["no"]}}
    response = client.post(BASE + "/query", json=scope)
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    assert result["data"]["page"]["total"] == 2 and len(result["data"]["entities"]) == 1
    assert result["data"]["entities"][0]["business_code"] == "B1"
    scope["snapshot_ref"] = result["meta"]["snapshot_ref"]
    selection = client.post(BASE + "/selection", json=scope).get_json()
    assert selection["data"]["count"] == 2
    facets = client.post(BASE + "/facets", json={"scope": scope, "field": "quantity"}).get_json()
    assert sorted(facets["data"]["values"]) == [5, 17]
    old = state(client)
    scope["column_filters"] = {"quantity": []}
    assert_error(client.post(BASE + "/query", json=scope), "snapshot_stale")
    del scope["snapshot_ref"]
    assert client.post(BASE + "/query", json=scope).get_json()["data"]["page"]["total"] == 0
    assert state(client) == old
