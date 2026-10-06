"""Batch atomic previews, template copies and actual resource constraints."""

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

    # 到料日也会改变有效齐套筛选；午夜前后的 60 秒仍在 900 秒口令有效期内。
    from datetime import date, datetime

    from core.services.workbench.batch import facts as batch_facts
    from core.services.workbench.batch.queries import WorkbenchBatchQueryService
    from web import public_token_registry
    from web.routes.workbench import read_context

    monkeypatch.setattr(BatchService, "update", original)
    clock = [datetime(2026, 10, 7, 23, 59, 30)]

    class LocalDate(date):
        @classmethod
        def today(cls):
            return clock[0].date()

    class LocalDateTime(datetime):
        @classmethod
        def now(cls):
            return clock[0]

    monkeypatch.setattr(batch_facts, "date", LocalDate)
    monkeypatch.setattr(read_context, "datetime", LocalDateTime)
    monkeypatch.setattr(public_token_registry.time, "time", lambda: clock[0].timestamp())
    client.batch_conn.execute("UPDATE Materials SET status='active' WHERE material_id='MAT1'")
    client.batch_conn.commit()
    response = post(client, "materials_update", {"removed_keys": [], "rows": [{
        "row_key": None, "material_ref": ref_for(client, "material", "MAT1"), "required_quantity": 10,
        "available_quantity": 0, "arrivals": [{"arrival_date": "2026-10-08", "quantity": 10}]}]},
        key="batch-midnight-material-001")
    assert response.status_code == 200, response.get_json()
    listed = list_data(client, query="FREE-001", ready_status="no")
    scope = {"query": "FREE-001", "ready_status": "no", "snapshot_ref": listed["meta"]["snapshot_ref"]}
    assert listed["data"]["page"]["total"] == 1 and listed["meta"]["as_of"] == "2026-10-07T23:59:30"
    exported = client.post(BASE + "/export-preview", json={"selection": "filtered", "scope": scope}).get_json()
    assert exported["data"]["count"] == 1
    before = state(client)
    changes = client.batch_conn.total_changes
    reader = WorkbenchBatchQueryService(client.batch_conn)
    with reader.detached_read_snapshot() as old_fingerprint:
        old = reader.detail(ref_for(client))
        clock[0] = datetime(2026, 10, 8, 0, 0, 30)
        pinned = reader.detail(ref_for(client))
        assert reader.fingerprint() == old_fingerprint
        assert old["display_ready_status"] == pinned["display_ready_status"] == pinned["materials"]["display_status"] == "no"
    with reader.detached_read_snapshot() as new_fingerprint:
        current = reader.detail(ref_for(client))
        assert new_fingerprint != old_fingerprint
        assert current["display_ready_status"] == current["materials"]["display_status"] == "yes"
    assert_error(client.get(BASE, query_string=scope), "snapshot_stale", 409)
    assert_error(client.post(BASE + "/selection", json=scope), "snapshot_stale", 409)
    assert_error(client.post(BASE + "/export-preview", json={"selection": "filtered", "scope": scope}), "snapshot_stale", 409)
    assert_error(client.get(BASE + "/export", query_string={"export_ref": exported["data"]["export_ref"]}), "snapshot_stale", 409)
    fresh = list_data(client, query="FREE-001", ready_status="yes")
    assert fresh["data"]["page"]["total"] == 1 and fresh["meta"]["as_of"] == "2026-10-08T00:00:30"
    assert state(client) == before and client.batch_conn.total_changes == changes
