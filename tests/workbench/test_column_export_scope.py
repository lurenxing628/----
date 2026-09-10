"""Column scope remains exact through real list, file preview and download APIs."""

import sqlite3
from contextlib import closing
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from tests.workbench.test_resource_file_support import decode

BASE = "/api/workbench/v1"
VIEWS = [("material", None), ("op_type", "internal"), ("op_type", "external"),
         ("machine", None), ("operator", None), ("supplier", None)]
TABLES = {"material": ("Materials", "material_id"), "op_type": ("OpTypes", "op_type_id"),
          "machine": ("Machines", "machine_id"), "operator": ("Operators", "operator_id"),
          "supplier": ("Suppliers", "supplier_id")}


def database(client):
    return closing(sqlite3.connect(client.application.config["DATABASE_PATH"]))


def seed(client, kind, category):
    table, key = TABLES[kind]
    with database(client) as conn:
        columns = [key, "name", "category" if kind == "op_type" else "status"]
        rows = [(f"SCOPE{index:03d}", f"Column scope {index}", category or "active") for index in range(25)]
        conn.executemany(f"INSERT INTO {table} ({','.join(columns)}) VALUES (?,?,?)", rows)
        if kind == "material":
            conn.execute("UPDATE Materials SET spec='Round',unit='kg',stock_qty=2.75,remark='keep hidden note'")
        if kind == "supplier":
            conn.execute("UPDATE Suppliers SET default_days=2.75,remark='keep hidden note'")
        conn.commit()
        return dict(conn.execute("SELECT entity_key,ref FROM WorkbenchEntityRefs WHERE kind=? AND active=1", (kind,)))


def post(client, path, body):
    response = client.post(BASE + path, json=body)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


def state(client):
    with database(client) as conn:
        return list(conn.iterdump())


def filtered_context(client, kind, category):
    scope: Dict[str, Any] = {"query": "SCOPE", "sort": "business_code", "direction": "desc"}
    if category:
        scope["category"] = category
    values = post(client, "/entities/" + kind + "/facets", {"scope": scope, "column": "business_code", "size": 100})
    keys = {item["label"]: item["key"] for item in values["data"]["options"]}
    assert len(keys) == 25
    scope["column_filters"] = {"business_code": {"mode": "include", "values": [keys["SCOPE000"], keys["SCOPE024"]]}}
    first = post(client, "/entities/" + kind + "/query", {**scope, "size": 1})
    assert first["data"]["page"]["total"] == 2 and first["data"]["page"]["pages"] == 2
    assert [item["business_code"] for item in first["data"]["entities"]] == ["SCOPE024"]
    second = post(client, "/entities/" + kind + "/query", {**scope, "page": 2, "size": 1, "snapshot_ref": first["meta"]["snapshot_ref"]})
    assert [item["business_code"] for item in second["data"]["entities"]] == ["SCOPE000"]
    return {"scope": scope, "page_size": 1, "snapshot_ref": first["meta"]["snapshot_ref"]}


def export_rows(client, kind, context, selection, fmt, refs=None):
    body = {**context, "selection": selection}
    if refs is not None:
        body["refs"] = refs
    preview = post(client, "/exports/" + kind + "/preview", body)["data"]
    response = client.get(BASE + "/exports/" + kind, query_string={"export_ref": preview["export_ref"], "format": fmt})
    assert response.status_code == 200, response.get_data(as_text=True)
    _, rows = decode(SimpleNamespace(content=response.data), fmt)
    assert len(rows) == preview["row_count"]
    return [row[0] for row in rows]


@pytest.mark.parametrize("kind,category", VIEWS)
@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_column_filter_and_order_apply_to_entire_export_not_current_page(app_client, kind, category, fmt):
    refs = seed(app_client, kind, category)
    before = state(app_client)
    context = filtered_context(app_client, kind, category)
    assert export_rows(app_client, kind, context, "filtered", fmt) == ["SCOPE024", "SCOPE000"]
    assert export_rows(app_client, kind, context, "all", fmt) == [f"SCOPE{index:03d}" for index in range(25)]
    assert export_rows(app_client, kind, context, "selected", fmt, [refs["SCOPE005"], refs["SCOPE024"]]) == ["SCOPE005", "SCOPE024"]
    preview = post(app_client, "/entities/" + kind + "/bulk-preview", {
        **context, "action": "delete", "refs": [refs["SCOPE005"], refs["SCOPE024"]]})["data"]
    assert [row["business_code"] for row in preview["rows"]] == ["SCOPE005", "SCOPE024"]
    assert state(app_client) == before


@pytest.mark.parametrize("kind,category", VIEWS)
def test_column_scope_change_does_not_reuse_old_export_or_bulk_snapshot(app_client, kind, category):
    refs = seed(app_client, kind, category)
    context = filtered_context(app_client, kind, category)
    before = state(app_client)
    changed = {**context, "scope": {**context["scope"], "column_filters": {"business_code": {"mode": "include", "values": []}}}}
    for path, extra in (("/exports/" + kind + "/preview", {"selection": "filtered"}),
                        ("/entities/" + kind + "/bulk-preview", {"action": "delete", "refs": [refs["SCOPE024"]]})):
        response = app_client.post(BASE + path, json={**changed, **extra})
        assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"
    assert state(app_client) == before


@pytest.mark.parametrize("kind,category", VIEWS)
def test_explicit_empty_column_selection_never_exports_full_collection(app_client, kind, category):
    seed(app_client, kind, category)
    before = state(app_client)
    scope: Dict[str, Any] = {"column_filters": {"business_code": {"mode": "include", "values": []}}}
    if category:
        scope["category"] = category
    listed = post(app_client, "/entities/" + kind + "/query", scope)
    assert listed["data"]["page"]["total"] == 0
    context = {"scope": scope, "page_size": 20, "snapshot_ref": listed["meta"]["snapshot_ref"]}
    assert export_rows(app_client, kind, context, "filtered", "csv") == []
    assert state(app_client) == before
