"""Concrete query/reader pairing, snapshot continuity and zero-write POST reads."""

import sqlite3

import pytest
from flask import Blueprint, Flask, g

from core.models.workbench_material_query import MaterialPageRequest
from core.models.workbench_resource_query import ResourcePageRequest
from core.services.workbench.material_queries import WorkbenchMaterialQueryService
from core.services.workbench.resource_queries import WorkbenchResourceQueryService
from tests.workbench.resource_table_support import BASE, VIEWS, conditions, stored_state, table_database
from web.routes.workbench.resource_table_queries import register_resource_table_routes


@pytest.fixture
def domain_client(table_conn):
    app = Flask(__name__)
    bp = Blueprint("resource_table_domain_pairing", __name__)
    register_resource_table_routes(bp)
    app.register_blueprint(bp)

    @app.before_request
    def bind_database():
        g.db = table_conn

    before = stored_state(table_conn)
    denied = []
    allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION,
               sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_SAVEPOINT}

    def authorize(action, table, field, database, trigger):
        if action not in allowed:
            denied.append((action, table))
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    table_conn.set_authorizer(authorize)
    try:
        yield app.test_client()
    finally:
        table_conn.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
        assert denied == []
        assert stored_state(table_conn) == before
        assert not table_conn.in_transaction


def _post(client, kind, operation, body, status=200, code=None):
    response = client.post(BASE + kind + "/" + operation, json=body)
    payload = response.get_json()
    assert response.status_code == status, payload
    assert response.headers["Cache-Control"] == "no-store"
    if status != 200:
        assert payload["ok"] is False and payload["committed"] is False
        assert payload["error"]["code"] == code and "data" not in payload
    return payload


@pytest.mark.parametrize("kind,category", VIEWS)
def test_concrete_domain_pair_keeps_filtered_pages_metrics_and_snapshot(domain_client, monkeypatch, kind, category):
    expected_type = MaterialPageRequest if kind == "material" else ResourcePageRequest
    service_type = WorkbenchMaterialQueryService if kind == "material" else WorkbenchResourceQueryService
    original_page, original_metrics = service_type.page, service_type.metrics
    pages, metrics = [], []

    def page(service, query):
        assert type(query) is expected_type and service.conn.in_transaction
        if isinstance(query, ResourcePageRequest):
            assert query.kind == service.kind == kind
        pages.append((service, query))
        return original_page(service, query)

    def metric_query(service, query):
        assert kind == "material", "Resource metrics must come from the original page result"
        assert type(query) is MaterialPageRequest and service.conn.in_transaction
        assert service is pages[-1][0] and query is pages[-1][1]
        metrics.append(query)
        return original_metrics(service, query)

    monkeypatch.setattr(service_type, "page", page)
    monkeypatch.setattr(service_type, "metrics", metric_query)
    toolbar = {"category": category} if category else {}
    menu_body = {"scope": toolbar, "column": "business_code", "size": 1}
    menu = _post(domain_client, kind, "facets", menu_body)
    selection = _post(domain_client, kind, "facet-selection", {
        **menu_body, "snapshot_ref": menu["meta"]["snapshot_ref"]})
    keys = selection["data"]["keys"][-2:]
    scope = {**toolbar, "size": 1, "sort": "business_code", "direction": "desc",
             "column_filters": conditions("business_code", keys)}
    first = _post(domain_client, kind, "query", scope)
    token = first["meta"]["snapshot_ref"]
    second = _post(domain_client, kind, "query", {**scope, "page": 2, "snapshot_ref": token})
    assert len(pages) == 2 and len(metrics) == (2 if kind == "material" else 0)
    assert pages[0][1].number == 1 and pages[1][1].number == 2
    for result in (first, second):
        data = result["data"]
        assert set(data) == {"entities", "page", "metrics", "create_context"}
        assert len(data["entities"]) == 1 and data["page"]["total"] == data["page"]["pages"] == 2
        assert data["metrics"]["counts"]["total"] == 2 and "metrics" not in data["page"]
        assert data["create_context"]["capabilities"] == {kind + ".create": True}
        assert data["entities"][0]["write_context"]["write_token"]
        assert result["meta"]["source"] == "production" and result["schema_version"] == 1
    assert first["data"]["metrics"] == second["data"]["metrics"]
    assert first["data"]["entities"][0]["business_code"] > second["data"]["entities"][0]["business_code"]
    assert second["meta"]["snapshot_ref"] == token and second["meta"]["as_of"] == first["meta"]["as_of"]
    _post(domain_client, kind, "query", {**scope, "page": 2}, 409, "snapshot_stale")
    _post(domain_client, kind, "query", {**scope, "page": 3, "snapshot_ref": token}, 409, "snapshot_stale")
    _post(domain_client, kind, "query", {**scope, "query": "changed", "snapshot_ref": token}, 409, "snapshot_stale")
    _post(domain_client, kind, "query", {**scope, "snapshot_ref": menu["meta"]["snapshot_ref"]}, 409, "snapshot_stale")


@pytest.mark.parametrize("kind,method", [("material", "page"), ("material", "metrics"), ("machine", "page")])
def test_domain_read_failures_remain_visible_and_never_uncertain(domain_client, monkeypatch, kind, method):
    service_type = WorkbenchMaterialQueryService if kind == "material" else WorkbenchResourceQueryService

    def broken(service, query):
        assert service.conn.in_transaction
        raise RuntimeError("private domain read failure")

    monkeypatch.setattr(service_type, method, broken)
    result = _post(domain_client, kind, "query", {}, 500, "storage_failure")
    assert "private domain read failure" not in result["error"]["message"]


@pytest.mark.parametrize("kind", ["machine_group", "shift_profile", "unknown", "Material"])
@pytest.mark.parametrize("operation,body", [("query", {}), ("facets", {"scope": {}, "column": "business_code"}),
                                           ("facet-selection", {"scope": {}, "column": "business_code"})])
def test_unknown_and_catalog_kinds_keep_original_rejection_boundary(domain_client, kind, operation, body):
    _post(domain_client, kind, operation, body, 404, "entity_not_found")
