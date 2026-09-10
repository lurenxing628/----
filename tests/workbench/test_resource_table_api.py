"""Native Flask read-only POST transport and separate facet/list snapshot contracts."""

import sqlite3
from datetime import date

import pytest
from flask import g

from core.infrastructure.database import get_connection
from core.services.workbench.resource_table_facts import ResourceTableFacts
from tests.workbench.resource_table_support import (
    BASE,
    VIEWS,
    conditions,
    facet_body,
    post,
    stored_state,
    table_application,
)


@pytest.mark.parametrize("kind,category", VIEWS)
def test_new_query_keeps_existing_get_payload_and_write_context_contract(table_client, kind, category):
    body = {"category": category} if category else {}
    old = table_client.get(BASE + kind, query_string=body)
    assert old.status_code == 200
    new = post(table_client, kind, "query", body)
    old_data, new_data = old.get_json()["data"], new["data"]
    assert set(old_data) == set(new_data) == {"entities", "page", "metrics", "create_context"}
    assert old_data["page"] == new_data["page"] and old_data["metrics"] == new_data["metrics"]
    for old_row, new_row in zip(old_data["entities"], new_data["entities"]):
        assert {key: value for key, value in old_row.items() if key != "write_context"} == {key: value for key, value in new_row.items() if key != "write_context"}
        assert old_row["write_context"]["capabilities"] == new_row["write_context"]["capabilities"]
        assert new_row["write_context"]["write_token"]
    assert new["meta"]["source"] == "production" and new["schema_version"] == 1


def test_facet_search_paginates_values_not_rows_and_selects_every_search_match(table_client):
    body = facet_body(column="spec", query="", size=1)
    first = post(table_client, "material", "facets", body)
    assert first["data"]["row_count"] == 5 and first["data"]["page"]["total"] == 3
    token = first["meta"]["snapshot_ref"]
    second = post(table_client, "material", "facets", {**body, "page": 2, "snapshot_ref": token})
    selected = post(table_client, "material", "facet-selection", {**body, "snapshot_ref": token})
    assert selected["meta"] == {**selected["meta"], "snapshot_ref": token, "as_of": first["meta"]["as_of"]}
    assert selected["data"]["total"] == len(selected["data"]["keys"]) == 3
    assert set(first["data"]["options"][0]) == {"key", "label", "count"}
    assert first["data"]["options"][0]["key"] != second["data"]["options"][0]["key"]
    assert first["data"]["options"][0]["key"] in selected["data"]["keys"]
    searched = post(table_client, "material", "facets", {**body, "query": "Round"})
    choice = post(table_client, "material", "facet-selection", {**body, "query": "Round", "snapshot_ref": searched["meta"]["snapshot_ref"]})
    assert choice["data"]["keys"] == [searched["data"]["options"][0]["key"]]
    filtered = post(table_client, "material", "query", {"size": 1, "column_filters": conditions("spec", choice["data"]["keys"])})
    assert filtered["data"]["page"]["total"] == 3 and len(filtered["data"]["entities"]) == 1


def test_facet_scope_ignores_column_filters_but_does_not_mix_list_and_menu_tokens(table_client):
    query = post(table_client, "material", "query", {"size": 1})
    first = post(table_client, "material", "facets", facet_body(column="spec", size=1))
    token = first["meta"]["snapshot_ref"]
    changed = post(table_client, "material", "facets", {"scope": {"column_filters": conditions("spec", []), "sort": "spec", "direction": "desc"},
                  "column": "spec", "size": 1, "page": 2, "snapshot_ref": token})
    assert changed["data"]["row_count"] == 5
    for operation, body in (("query", {"snapshot_ref": token}),
                            ("facets", facet_body(column="spec", size=1, snapshot_ref=query["meta"]["snapshot_ref"])),
                            ("facet-selection", facet_body(column="spec", size=1, snapshot_ref=query["meta"]["snapshot_ref"]))):
        response = table_client.post(BASE + "material/" + operation, json=body)
        assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"


@pytest.mark.parametrize("change", [{"column": "label"}, {"query": "Round"}, {"size": 2}, {"scope": {"query": "Alpha"}}])
def test_menu_snapshot_rejects_changed_value_search_column_size_or_toolbar_scope(table_client, change):
    body = facet_body(column="spec", size=1)
    first = post(table_client, "material", "facets", body)
    response = table_client.post(BASE + "material/facet-selection", json={**body, **change, "snapshot_ref": first["meta"]["snapshot_ref"]})
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"


@pytest.mark.parametrize("kind,column,sql", [
    ("material", "spec", "UPDATE Materials SET spec='Changed' WHERE material_id='MAT5'"),
    ("machine", "group_ref", "UPDATE WorkbenchMachineGroupMembers SET group_id='G2' WHERE machine_id='A1'"),
    ("operator", "skill_refs", "DELETE FROM OperatorSkill WHERE operator_id='OK' AND op_type_id='B'"),
    ("operator", "shift_profile_ref", "UPDATE WorkbenchShiftProfiles SET name='Changed' WHERE profile_id='H1'"),
    ("supplier", "op_type_refs", "DELETE FROM WorkbenchSupplierOpTypes WHERE supplier_id='S1' AND op_type_id='Y'"),
])
def test_related_fact_changes_stale_both_filtered_pages_and_facet_selection(table_client, kind, column, sql):
    body = facet_body(column=column, size=1)
    facets = post(table_client, kind, "facets", body)
    scope = {"size": 1, "column_filters": conditions("business_code", [], "exclude")}
    page = post(table_client, kind, "query", scope)
    with sqlite3.connect(table_client.application.config["DATABASE_PATH"]) as conn:
        conn.execute(sql)
    for operation, request_body in (("facet-selection", {**body, "snapshot_ref": facets["meta"]["snapshot_ref"]}),
                                     ("query", {**scope, "page": 2, "snapshot_ref": page["meta"]["snapshot_ref"]})):
        response = table_client.post(BASE + kind + "/" + operation, json=request_body)
        assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"


@pytest.mark.parametrize("operation,body", [
    ("query", {"page": True}), ("query", {"size": 201}), ("query", {"query": "q" * 201}),
    ("query", {"sort": "entity_key"}), ("query", {"column_filters": None}), ("query", {"other": 1}),
    ("facets", {"scope": {}, "column": "revision"}), ("facets", {"scope": {}, "column": "spec", "size": 201}),
    ("facets", {"scope": {}, "column": "spec", "query": "x" * 201}),
    ("facet-selection", {"scope": {}, "column": "spec", "page": 1}),
])
def test_bad_requests_are_rejected_not_silently_normalized(table_client, operation, body):
    response = table_client.post(BASE + "material/" + operation, json=body)
    assert response.status_code == 400 and response.get_json()["committed"] is False


@pytest.mark.parametrize("operation,body", [("query", {"page": 2}), ("facets", facet_body(column="spec", page=2)),
    ("facet-selection", facet_body(column="spec"))])
def test_cross_page_and_bulk_key_reads_require_their_own_snapshot(table_client, operation, body):
    response = table_client.post(BASE + "material/" + operation, json=body)
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"


def test_body_limit_duplicate_fields_catalog_and_wrong_category_are_explicit(table_client, monkeypatch):
    monkeypatch.setattr("web.routes.workbench.resource_table_queries.MAX_TABLE_BODY_BYTES", 128)
    response = table_client.post(BASE + "material/query", data='{"query":"' + "q" * 200 + '"}', content_type="application/json")
    assert response.status_code == 413 and response.get_json()["error"]["code"] == "capacity_exceeded"
    duplicate = table_client.post(BASE + "material/query", data='{"query":"a","query":"b"}', content_type="application/json")
    assert duplicate.status_code == 400
    assert table_client.post(BASE + "machine_group/query", json={}).status_code == 404
    assert table_client.get(BASE + "machine_group").status_code == 200
    assert table_client.post(BASE + "op_type/query", json={"category": "external", "sort": "available_operators"}).status_code == 400
    assert table_client.post(BASE + "material/query", json={"category": "internal"}).status_code == 400


def test_new_post_read_errors_cannot_claim_uncertain_writes(table_client, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("injected readonly failure")

    monkeypatch.setattr(ResourceTableFacts, "index", broken)
    response = table_client.post(BASE + "operator/facets", json=facet_body(column="skill_refs"))
    assert response.status_code == 500 and response.get_json()["committed"] is False
    assert response.get_json()["error"]["code"] == "storage_failure"


def test_real_http_selects_ten_thousand_search_values_in_one_request(table_client):
    with sqlite3.connect(table_client.application.config["DATABASE_PATH"]) as conn:
        conn.executemany("INSERT INTO Materials(material_id,name,spec,stock_qty,unit) VALUES (?,? ,?,?,'kg')", [
            (f"HTTP{index:05d}", "Scale material", f"Distinct {index:05d}", index) for index in range(10000)])
        conn.commit()
        before = stored_state(conn)
        body = {"scope": {"query": "Scale material"}, "column": "spec", "query": "Distinct 0", "size": 100}
        facets = post(table_client, "material", "facets", body)
        selected = post(table_client, "material", "facet-selection", {**body, "snapshot_ref": facets["meta"]["snapshot_ref"]})
        assert facets["data"]["page"]["total"] == 10000 and len(facets["data"]["options"]) == 100
        assert selected["data"]["total"] == len(selected["data"]["keys"]) == 10000
        scope = {"query": "Scale material", "size": 200, "column_filters": conditions("spec", selected["data"]["keys"])}
        first = post(table_client, "material", "query", scope)
        last = post(table_client, "material", "query", {**scope, "page": 50, "snapshot_ref": first["meta"]["snapshot_ref"]})
        assert first["data"]["page"]["total"] == last["data"]["page"]["total"] == 10000
        assert len(last["data"]["entities"]) == 200
        assert first["data"]["metrics"]["counts"]["total"] == 10000
        assert stored_state(conn) == before


def test_native_flask_dates_and_read_authorizer_preserve_every_table(table_client, monkeypatch):
    import web.routes.workbench.resource_table_queries as routes

    conn = get_connection(table_client.application.config["DATABASE_PATH"])
    conn.execute("INSERT INTO WorkCalendar(date,day_type,shift_hours) VALUES ('2026-09-09','restday',0)")
    conn.execute("INSERT INTO OperatorCalendar(operator_id,date,shift_start,shift_end,shift_hours) VALUES ('OK','2026-09-09','23:15','07:45',8.5)")
    conn.commit()
    before = stored_state(conn)
    original = routes._reader
    seen = []

    def guarded(kind):
        service = original(kind)
        assert type(g.db.execute("SELECT date FROM OperatorCalendar").fetchone()[0]) is date

        def authorize(action, arg1, arg2, database, source):
            seen.append(action)
            allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_SAVEPOINT}
            return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY

        g.db.set_authorizer(authorize)
        return service

    monkeypatch.setattr(routes, "_reader", guarded)
    try:
        for kind, category in VIEWS:
            scope = {"category": category} if category else {}
            facet = post(table_client, kind, "facets", {"scope": scope, "column": "business_code", "size": 1})
            choice = post(table_client, kind, "facet-selection", {"scope": scope, "column": "business_code", "size": 1, "snapshot_ref": facet["meta"]["snapshot_ref"]})
            filtered = {**scope, "column_filters": conditions("business_code", choice["data"]["keys"]), "size": 2}
            page = post(table_client, kind, "query", filtered)
            post(table_client, kind, "query", {**filtered, "page": 2, "snapshot_ref": page["meta"]["snapshot_ref"]})
        assert seen and stored_state(conn) == before
    finally:
        conn.close()
