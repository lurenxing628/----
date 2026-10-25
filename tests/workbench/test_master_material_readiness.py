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


def test_overview_material_readiness_follows_arrival_day_and_quantity_review(overview_client, monkeypatch, record_property):
    from core.services.workbench.master import overview_facts
    from core.services.workbench.master.overview import MasterOverviewService

    client = overview_client
    client.batch_conn.executemany("INSERT INTO Materials(material_id,name,unit,stock_qty) VALUES (?,?,'kg',0)",
                                 [("R18-" + str(index).zfill(2), "test material") for index in range(20)])
    client.batch_conn.commit()
    original, calls = MasterOverviewService.page, []
    load_facts, captures = overview_facts.MasterOverviewFacts._load, []

    def page(reader, scope, number=1):
        calls.append(number)
        return original(reader, scope, number)

    def capture(facts):
        captures.append(facts)
        return load_facts(facts)

    query = {"scope": json.dumps(SCOPE), "page": 2}
    with monkeypatch.context() as patch:
        patch.setattr(MasterOverviewService, "page", page)
        patch.setattr(overview_facts.MasterOverviewFacts, "_load", capture)
        restored = client.get(BASE, query_string=query)
    assert restored.status_code == 200, restored.get_json()
    direct = restored.get_json()
    assert calls == [2] and direct["data"]["page"]["number"] == 2
    assert direct["data"]["rows"]
    assert len(captures) == 1
    assert direct["data"]["selected_detail"]["entity"]["ref"] == direct["data"]["rows"][0]["ref"]
    record_property("direct_page", 2)
    record_property("page_query_calls", len(calls))
    record_property("data_fields", sorted(direct["data"]))
    repeated = client.get(BASE, query_string={**query, "snapshot_ref": direct["meta"]["snapshot_ref"]}).get_json()
    assert repeated["data"] == direct["data"] and repeated["meta"].keys() == direct["meta"].keys()
    assert repeated["meta"]["request_ref"] != direct["meta"]["request_ref"]
    assert all(repeated["meta"][key] == value for key, value in direct["meta"].items() if key not in ("request_ref", "as_of"))
    target = direct["data"]["rows"][-1]
    located = client.get(BASE + "/locate/material/" + target["ref"], query_string={
        "scope": json.dumps(SCOPE), "snapshot_ref": direct["meta"]["snapshot_ref"]})
    assert located.status_code == 200, located.get_json()
    assert located.get_json()["data"]["selected_detail"]["entity"]["ref"] == target["ref"]
    missing = client.get(BASE + "/export", query_string={"scope": json.dumps(SCOPE)})
    assert missing.status_code == 409 and missing.get_json()["error"]["code"] == "snapshot_stale"
    # Keep the original readiness oracle's single-material first screen after
    # the independent pagination proof has consumed its temporary rows.
    client.batch_conn.execute("DELETE FROM Materials WHERE material_id GLOB 'R18-*'")
    client.batch_conn.commit()
    tomorrow = date.today() + timedelta(days=1)
    arrival = {"arrival_date": tomorrow.isoformat(), "quantity": 8}
    receipt = _save(client, 2, [arrival])
    assert receipt["data"]["ready_status"] == "partial"
    result, entity = _overview(client)
    captured_detail = result["data"]["selected_detail"]
    assert captured_detail["entity"]["ref"] == entity["ref"]
    assert "已到料 2" in captured_detail["rows"][0]["evidence"]
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
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["data"]["counts"]["issues"] == 0
    # The original scope remains valid while each read follows current facts.
    current = client.get(BASE, query_string={"scope": json.dumps(SCOPE), "snapshot_ref": result["meta"]["snapshot_ref"]})
    assert current.status_code == 200, current.get_json()
    download = client.get(BASE + "/export", query_string={"scope": json.dumps(SCOPE), "snapshot_ref": result["meta"]["snapshot_ref"]})
    assert download.status_code == 200 and int(download.headers["X-Workbench-Row-Count"]) == current.get_json()["data"]["page"]["total"]
    changed_scope = client.get(BASE, query_string={"scope": json.dumps({**SCOPE, "query": "other"}), "snapshot_ref": result["meta"]["snapshot_ref"]})
    assert changed_scope.status_code == 409 and changed_scope.get_json()["error"]["code"] == "snapshot_stale"
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


@pytest.mark.parametrize("stored_status,reviewed", [("no", False), ("partial", True)])
def test_bad_requirement_does_not_own_other_materials_pending_diagnosis(overview_client, stored_status, reviewed):
    client = overview_client
    conn = client.batch_conn
    conn.execute("INSERT INTO Materials(material_id,name,spec,unit) VALUES ('MAT2','second material','second spec','kg')")
    conn.execute("UPDATE Batches SET ready_status=? WHERE batch_id='FREE-001'", (stored_status,))
    conn.executemany("INSERT INTO BatchMaterials(batch_id,material_id,required_qty,available_qty,ready_status) "
                     "VALUES ('FREE-001',?,?,?,?)", [("MAT1", 0, 0, stored_status), ("MAT2", 10, 2, stored_status)])
    if reviewed:
        conn.execute("INSERT INTO BatchMaterialReviews(requirement_id,batch_quantity) SELECT id,5 FROM BatchMaterials")
    conn.commit()

    current = detail(client)["data"]
    assert current["fields"]["ready_status"] == stored_status
    assert current["display_ready_status"] is None and current["materials"]["display_status"] is None
    assert {row["ready_status"] for row in current["materials"]["requirements"]} == {stored_status}

    result, invalid = _overview(client)
    pending = next(row for row in result["data"]["rows"] if row["business_code"] == "MAT2")
    invalid_issues = _section(client, result, invalid, "issues")
    assert [row["rule"] for row in invalid_issues] == ["batch_material.required_qty"]
    pending_issues = _section(client, result, pending, "issues")
    assert [row["rule"] for row in pending_issues] == ["batch_material.pending"]
    assert "已到料 2" in pending_issues[0]["evidence"]
    for material in (invalid, pending):
        fields = {row["label"]: row["value"] for row in _section(client, result, material, "fields")}
        assert fields["FREE-001 批次当前有效齐套"] == "待核对"
    assert invalid_issues[0]["target"] == pending_issues[0]["target"] == {
        "view": "batches", "context": {"entity_ref": ref_for(client)}}

    conn.execute("UPDATE BatchMaterials SET available_qty=10,ready_status='yes' WHERE material_id='MAT2'")
    conn.commit()
    result, _ = _overview(client)
    valid = next(row for row in result["data"]["rows"] if row["business_code"] == "MAT2")
    assert valid["issue_count"] == 0


def test_material_display_diagnosis_does_not_make_later_stage_release_eager():
    from core.services.material.stage_availability import MaterialAvailability

    batch = {"batch_id": "B1", "quantity": 5, "ready_status": "no"}
    tables = {
        "BatchMaterials": [{"id": 1, "batch_id": "B1", "required_qty": 5, "available_qty": 0, "ready_status": "no"}],
        "BatchMaterialReviews": [{"requirement_id": 1, "batch_quantity": 5}],
        "BatchMaterialStages": [{"requirement_id": 1, "operation_id": 2}],
        "BatchOperations": [{"id": 2, "batch_id": "B1", "seq": 2, "piece_id": None}],
        "BatchMaterialArrivals": [{"requirement_id": 1, "arrival_date": "bad-day", "quantity": 5}],
    }
    availability = MaterialAvailability(tables)
    status, problems = availability.readiness_state(batch, date.today().isoformat())
    assert status is None and [problem["code"] for problem in problems] == ["material_unknown"]
    assert availability.operation_release(batch, {"seq": 1}, "stage") == "1900-01-01"


_OVERVIEW_FORMAT = "资料总览的查询条件格式不对，请刷新页面后重试。"


@pytest.mark.parametrize("scope,message", [
    ('{"domain": "material", "domain": "part", "view": "entities"}', _OVERVIEW_FORMAT),
    *[('{"domain": "material", "view": "entities", "size": ' + literal + "}", _OVERVIEW_FORMAT)
      for literal in ("NaN", "Infinity", "-Infinity", "1e999")],
    ('{"domain": "material", "view": "entities"', _OVERVIEW_FORMAT),
    # 65536 is counted in UTF-8 bytes: 30000 Chinese characters stay under the old character count.
    (json.dumps({"view": "entities", "query": "料" * 30000}, ensure_ascii=False), "主数据筛选范围过长。"),
])
def test_overview_scope_rejects_duplicate_keys_nonfinite_numbers_and_oversized_utf8(overview_client, scope, message):
    response = overview_client.get(BASE, query_string={"scope": scope})
    body = response.get_json()
    assert response.status_code == 400 and body["ok"] is False and body["error"]["code"] == "invalid_input", body
    assert body["error"]["message"] == message
