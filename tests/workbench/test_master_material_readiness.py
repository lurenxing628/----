"""The material overview uses the same dated readiness facts as batch maintenance."""

import json
from datetime import date, timedelta

import pytest
from flask import Blueprint

from tests.workbench.batch_support import create_batch_client, detail, post, ref_for

BASE = "/api/workbench/v1/master-overview"
SCOPE = {"domain": "material", "view": "entities"}


@pytest.fixture
def overview_client(schema_conn):
    client = create_batch_client(schema_conn)
    schema_conn.execute("DELETE FROM BatchMaterials")
    schema_conn.execute("UPDATE Materials SET status='active' WHERE material_id='MAT1'")
    schema_conn.commit()
    from web.routes.workbench.master_overview import register_master_overview_routes

    bp = Blueprint("master_readiness", __name__)
    register_master_overview_routes(bp)
    client.application.register_blueprint(bp)
    return client


def _save(client, available, arrivals=()):
    response = post(client, "materials_update", {"rows": [{
        "row_key": None, "material_ref": ref_for(client, "material", "MAT1"),
        "required_quantity": 10, "available_quantity": available,
        "operation_ref": None, "arrivals": list(arrivals)}], "removed_keys": []})
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def _overview(client):
    response = client.get(BASE, query_string={"scope": json.dumps(SCOPE)})
    assert response.status_code == 200, response.get_json()
    data = response.get_json()
    entity = next(row for row in data["data"]["rows"] if row["business_code"] == "MAT1")
    return data, entity


def _section(client, result, entity, section):
    query = {"scope": json.dumps(SCOPE), "snapshot_ref": result["meta"]["snapshot_ref"], "section": section}
    path = BASE + "/entities/material/" + entity["ref"]
    response = client.get(path, query_string=query)
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    rows = data["rows"]
    for page in range(2, data["page"]["pages"] + 1):
        response = client.get(path, query_string={**query, "detail_page": page})
        assert response.status_code == 200, response.get_json()
        rows.extend(response.get_json()["data"]["rows"])
    return rows


def test_overview_material_readiness_follows_arrival_day_and_quantity_review(overview_client, monkeypatch):
    from core.services.workbench.master import overview_facts

    client = overview_client
    tomorrow = date.today() + timedelta(days=1)
    arrival = {"arrival_date": tomorrow.isoformat(), "quantity": 8}
    receipt = _save(client, 2, [arrival])
    assert receipt["data"]["ready_status"] == "partial"
    result, entity = _overview(client)
    issue = _section(client, result, entity, "issues")[0]
    assert issue["rule"] == "batch_material.pending" and "已到料 2" in issue["evidence"]
    fields = {row["label"]: row["value"] for row in _section(client, result, entity, "fields")}
    assert fields["FREE-001 当前到料数量"] == 2

    class Tomorrow(date):
        @classmethod
        def today(cls):
            return tomorrow

    monkeypatch.setattr(overview_facts, "date", Tomorrow)
    response = client.get(BASE + "/entities/material/" + entity["ref"], query_string={
        "scope": json.dumps(SCOPE), "snapshot_ref": result["meta"]["snapshot_ref"], "section": "issues"})
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"
    _, entity = _overview(client)
    assert entity["status"] == "checked" and entity["issue_count"] == 0

    response = post(client, "update", {"fields": {"quantity": 10}}, key="master-quantity-update-0001")
    assert response.status_code == 200, response.get_json()
    assert detail(client)["data"]["display_ready_status"] is None
    result, entity = _overview(client)
    assert entity["status"] == "attention" and entity["issue_count"] == 1
    issue = _section(client, result, entity, "issues")[0]
    assert issue["rule"] == "batch_material.material_review_required"
    assert issue["target"]["view"] == "batches"
    assert issue["target"]["context"]["entity_ref"] == ref_for(client)
    fields = {row["label"]: row["value"] for row in _section(client, result, entity, "fields")}
    assert fields["FREE-001 批次当前有效齐套"] == "待核对"
