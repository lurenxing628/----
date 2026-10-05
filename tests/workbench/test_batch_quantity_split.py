"""HTTP proposal, confirmation, replay, conservation and stale protection."""

from tests.workbench.batch_support import BASE, assert_error, batch_database, detail, post, ref_for, state
from tests.workbench.test_batch_actions import confirm

_batch_fixture = batch_database


def prepare(client):
    conn = client.batch_conn
    conn.execute("UPDATE Materials SET status='active' WHERE material_id='MAT1'")
    conn.execute("UPDATE Batches SET quantity=100 WHERE batch_id='FREE-001'")
    conn.commit()
    op_ref = detail(client)["data"]["operations"][0]["ref"]
    response = post(client, "materials_update", {"removed_keys": [], "rows": [{"row_key": None,
        "material_ref": ref_for(client, "material", "MAT1"), "required_quantity": 100,
        "available_quantity": 10, "operation_ref": op_ref,
        "arrivals": [{"arrival_date": "2026-09-28", "quantity": 30}, {"arrival_date": "2030-01-01", "quantity": 60}]}]}, key="split-material-setup-0001")
    assert response.status_code == 200, response.get_json()


def preview(client):
    entity = detail(client)
    response = client.post(BASE + "/" + ref_for(client) + "/split-preview", json={
        "snapshot_ref": entity["meta"]["snapshot_ref"], "input": {"as_of_date": "2026-09-28"}})
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def test_split_writes_each_material_final_quantity_and_readiness_once(batch_client, monkeypatch):
    from data.repositories.batch_material_repo import BatchMaterialRepository
    client = batch_client
    prepare(client)
    proposal = preview(client)
    calls, original = [], BatchMaterialRepository.update_qty
    def recorded(self, requirement_id, **fields):
        calls.append((requirement_id, fields))
        return original(self, requirement_id, **fields)
    monkeypatch.setattr(BatchMaterialRepository, "update_qty", recorded)
    response = confirm(client, proposal, path="/" + ref_for(client) + "/split-confirm", key="split-final-fields-once")
    assert response.status_code == 200, response.get_json()
    assert len(calls) == 1 and set(calls[0][1]) == {"required_qty", "available_qty", "ready_status"}


def test_preview_is_readonly_confirm_40_60_conserves_every_arrival_and_replays(batch_client):
    client = batch_client
    prepare(client)
    before = state(client)
    proposal = preview(client)
    assert state(client) == before
    assert (proposal["original_quantity"], proposal["quantity"], proposal["remaining_quantity"]) == (100, 40, 60)
    path = "/" + ref_for(client) + "/split-confirm"
    response = confirm(client, proposal, path=path, key="split-confirm-request-001")
    assert response.status_code == 200, response.get_json()
    child = detail(client, response.get_json()["data"]["child_ref"])["data"]
    assert child["fields"]["quantity"] == 40 and detail(client)["data"]["fields"]["quantity"] == 60
    assert child["materials"]["requirements"][0]["operation_ref"] == child["operations"][0]["ref"]
    assert child["materials"]["requirements"][0]["arrivals"] == [{"arrival_date": "2026-09-28", "quantity": 30.0}]
    conn = client.batch_conn
    assert tuple(conn.execute("SELECT sum(required_qty),sum(available_qty) FROM BatchMaterials WHERE batch_id IN ('FREE-001','FREE-002')").fetchone()) == (100, 10)
    assert conn.execute("SELECT sum(quantity) FROM BatchMaterialArrivals").fetchone()[0] == 90
    assert confirm(client, proposal, path=path, key="split-confirm-request-001").get_json()["replayed"] is True
    assert conn.execute("SELECT count(*) FROM BatchQuantitySplits").fetchone()[0] == 1


def test_stale_split_changes_nothing(batch_client):
    prepare(batch_client)
    proposal = preview(batch_client)
    batch_client.batch_conn.execute("UPDATE BatchMaterialArrivals SET quantity=quantity+1")
    batch_client.batch_conn.commit()
    before = state(batch_client)
    response = confirm(batch_client, proposal, path="/" + ref_for(batch_client) + "/split-confirm", key="split-stale-request-001")
    assert_error(response, "stale_write")
    assert state(batch_client) == before


def test_failure_after_material_allocation_rolls_back_child_and_source(batch_client, monkeypatch):
    from data.repositories.batch_material_stage_repo import BatchMaterialStageRepository

    prepare(batch_client)
    proposal = preview(batch_client)
    before = state(batch_client)
    def fail(*args, **kwargs):
        raise RuntimeError("injected after quantity allocation")
    monkeypatch.setattr(BatchMaterialStageRepository, "record_split", fail)
    response = confirm(batch_client, proposal, path="/" + ref_for(batch_client) + "/split-confirm", key="split-rollback-request-01")
    assert response.status_code == 500
    assert state(batch_client) == before
