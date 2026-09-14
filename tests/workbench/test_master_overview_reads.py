"""Whole-scope, real-SQLite contracts for all eight overview domains."""

import csv
import io
import json

import pytest

from tests.workbench.master_overview_support import BASE, args, detail, query, ref_for, stored
from tests.workbench.master_overview_support import overview_client as _overview_client


def test_eight_domains_are_real_counts_and_get_is_readonly(overview_client):
    client = overview_client
    before = stored(client)
    traces = []
    client.conn.set_trace_callback(traces.append)
    client.conn.execute("PRAGMA query_only=ON")
    result = query(client)
    overview = result["data"]["overview"]
    assert {row["id"]: row["count"] for row in overview["domains"]} == {
        "part": 65, "route": 1, "opType": 2, "equipment": 31, "personnel": 1, "material": 2, "supplier": 1, "calendar": 1}
    assert overview["stats"]["entities"] == 104
    assert overview["complete"] is True
    assert overview["stats"]["relations"] > 50
    assert "不代表可以排产" in overview["basis"]
    assert client.get(BASE + "/export", query_string=args(result)).status_code == 200
    assert before == stored(client)
    assert not any(line.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER")) for line in traces)


def test_filtered_pages_detail_and_export_share_snapshot(overview_client):
    client = overview_client
    scope = {"view": "entities", "domain": "part", "sort": "business_code", "direction": "asc", "column_filters": {"business_code": "P0"}}
    first = query(client, scope)
    second = query(client, first["data"]["scope"], first["meta"]["snapshot_ref"], 2)
    assert first["data"]["page"]["total"] == 65
    assert second["data"]["rows"][0]["business_code"] == "P020"
    assert second["meta"]["snapshot_ref"] == first["meta"]["snapshot_ref"]
    entity = detail(client, first, "part", ref_for(client, "part", "P060"))
    assert entity["data"]["entity"]["business_code"] == "P060"
    assert entity["meta"]["snapshot_ref"] == first["meta"]["snapshot_ref"]
    response = client.get(BASE + "/export", query_string=args(second))
    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"))))
    assert len(rows) == 66 and rows[-1][1] == "P064"
    assert response.headers["X-Workbench-Snapshot-Ref"] == first["meta"]["snapshot_ref"]
    assert response.headers["X-Workbench-Row-Count"] == "65"
    assert response.headers["Cache-Control"] == "no-store"


def test_zero_unknown_and_existing_confirmation_are_not_conflated(overview_client):
    client = overview_client
    first = query(client)
    zero = detail(client, first, "material", ref_for(client, "material", "MAT0"))
    unknown = detail(client, first, "material", ref_for(client, "material", "MAT-UNKNOWN"))
    stock = lambda result: next(field for field in result["data"]["rows"] if field["label"] == "库存数量")
    assert stock(zero)["value"] == 0 and stock(zero)["state"] == "known"
    assert stock(unknown)["value"] is None and stock(unknown)["state"] == "missing"
    route = detail(client, first, "route", ref_for(client, "part", "P000"), "issues")
    rules = {row["rule"] for row in route["data"]["rows"]}
    assert "operation.zero_review" in rules and "workflow.pending" in rules
    assert "operation.days" not in rules
    zero_issue = next(row for row in route["data"]["rows"] if row["rule"] == "operation.zero_review")
    assert zero_issue["target"]["context"]["template_operation_ref"] == ref_for(client, "template_operation", 1)
    assert zero_issue["target"]["context"]["stage"] == "hours"


def test_relations_are_paginated_real_refs_and_exact_locate(overview_client):
    client = overview_client
    result = query(client, {"view": "entities", "domain": "opType"})
    op = ref_for(client, "op_type", "IN")
    relation = detail(client, result, "opType", op, "relations", 3)
    assert relation["data"]["page"]["total"] == 33
    assert len(relation["data"]["rows"]) == 10
    machine_ref = ref_for(client, "machine", "M030")
    located = client.get(BASE + "/locate/equipment/" + machine_ref, query_string=args(result)).get_json()
    assert located["ok"] is True and located["data"]["page"]["number"] == 2
    assert located["data"]["selected"]["entity_ref"] == machine_ref
    assert any(row["ref"] == machine_ref for row in located["data"]["rows"])
    assert located["data"]["scope"]["domain"] == "equipment"
    assert detail(client, located, "equipment", machine_ref)["data"]["entity"]["ref"] == machine_ref


def test_material_batch_relationships_use_batch_ref_and_not_stock(overview_client):
    client = overview_client
    result = query(client)
    ref = ref_for(client, "material", "MAT0")
    relation = detail(client, result, "material", ref, "relations")
    batch = next(row for row in relation["data"]["rows"] if row["domain"] == "batch")
    assert batch["ref"] == ref_for(client, "batch", batch["business_code"])
    assert batch["target"] == {"view": "batches", "context": {"entity_ref": batch["ref"]}}
    issues = detail(client, result, "material", ref, "issues")
    assert issues["data"]["page"]["total"] == 23
    assert all(row["target"]["view"] == "batches" for row in issues["data"]["rows"])


@pytest.mark.parametrize("mutation", ["UPDATE Materials SET stock_qty=5 WHERE material_id='MAT0'",
    "DELETE FROM OperatorMachine", "UPDATE WorkCalendar SET efficiency=.8", "UPDATE Parts SET part_name='改变' WHERE part_no='P064'"])
def test_any_fact_change_rejects_old_list_detail_and_export(overview_client, mutation):
    client = overview_client
    first = query(client)
    client.conn.execute(mutation)
    client.conn.commit()
    for path, extra in ((BASE, {"page": 2}), (BASE + "/export", {}),
                        (BASE + "/entities/part/" + ref_for(client, "part", "P000"), {})):
        response = client.get(path, query_string={**args(first), **extra})
        assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"


def test_no_internal_row_ids_or_revisions_in_public_payload(overview_client):
    client = overview_client
    result = query(client, {"view": "entities", "size": 100})
    route = detail(client, result, "route", ref_for(client, "part", "P000"), "issues")
    def walk(value):
        if isinstance(value, dict):
            assert not {"id", "entity_key", "revision", "part_no", "op_id", "supplier_id", "machine_id", "group_id"} & set(value)
            for item in value.values():
                walk(item)
        if isinstance(value, list):
            for item in value:
                walk(item)
    # Domain catalog 'id' is an enum, never a raw internal row id.
    for row in result["data"]["overview"]["domains"]:
        assert row.pop("id") in ("part", "route", "opType", "equipment", "personnel", "material", "supplier", "calendar")
    walk([result, route])


def test_deleted_recreated_same_code_never_retargets_old_ref(overview_client):
    client = overview_client
    old = ref_for(client, "part", "P064")
    client.conn.execute("DELETE FROM Parts WHERE part_no='P064'")
    client.conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P064','同号新零件')")
    client.conn.commit()
    current = query(client)
    assert old != ref_for(client, "part", "P064")
    response = client.get(BASE + "/locate/part/" + old, query_string=args(current))
    assert response.status_code == 404 and response.get_json()["error"]["code"] == "entity_not_found"


def test_missing_identity_fails_without_repair(overview_client):
    client = overview_client
    client.conn.execute("DELETE FROM WorkbenchEntityRefs WHERE kind='material'")
    client.conn.commit()
    before = stored(client)
    response = client.get(BASE)
    assert response.status_code == 500
    assert response.get_json()["error"]["code"] == "storage_failure"
    assert stored(client) == before


def test_unloaded_calendar_is_not_zero_or_healthy(overview_client):
    client = overview_client
    client.conn.execute("DROP TABLE WorkCalendar")
    client.conn.commit()
    first = query(client)
    domain = next(row for row in first["data"]["overview"]["domains"] if row["id"] == "calendar")
    assert domain["loaded"] is False and domain["count"] is None
    assert first["data"]["overview"]["complete"] is False
    assert any(row["source"] == "WorkCalendar" for row in first["data"]["overview"]["gaps"])


def test_csv_formula_protection_full_long_chinese_and_newlines(overview_client):
    client = overview_client
    label = "=SUM(A1)\n" + "很长中文" * 300
    client.conn.execute("UPDATE Parts SET part_name=? WHERE part_no='P064'", (label,))
    client.conn.commit()
    result = query(client, {"view": "entities", "domain": "part", "column_filters": {"business_code": "P064"}})
    response = client.get(BASE + "/export", query_string=args(result))
    rows = list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"))))
    assert len(rows) == 2 and rows[1][2] == "'" + label


@pytest.mark.parametrize("scope", ["{\"view\":\"issues\",\"view\":\"entities\"}", "[]", '{"page":2}',
    '{"size":true}', '{"column_filters":{"id":"1"}}', '{"column_filters":{"label":null}}', '{"domain":"batch"}'])
def test_strict_scope_rejects_ambiguous_or_unknown_fields(overview_client, scope):
    response = overview_client.get(BASE, query_string={"scope": scope})
    assert response.status_code == 400 and response.get_json()["error"]["code"] == "invalid_input"


def test_scope_changes_cannot_reuse_old_snapshot(overview_client):
    first = query(overview_client)
    response = overview_client.get(BASE, query_string={**args(first), "scope": json.dumps({"view": "issues"})})
    assert response.status_code == 409
    assert overview_client.get(BASE, query_string={"page": 2}).status_code == 409
    assert overview_client.get(BASE + "/export").status_code == 409
