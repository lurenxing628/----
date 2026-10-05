"""Batch atomic previews, template copies and actual resource constraints."""

from tests.workbench.batch_support import (
    BASE,
    assert_error,
    batch_database,
    body,
    detail,
    list_data,
    ref_for,
    state,
)

_batch_fixture = batch_database


def preview(client, action="update", refs=None, patch=None):
    response = client.post(BASE + "/bulk-preview", json={"scope": {}, "snapshot_ref": list_data(client)["meta"]["snapshot_ref"],
        "input": {"action": action, "refs": refs or [ref_for(client)], "patch": patch or {}}})
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


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
    from core.services.batch.service import BatchService

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
