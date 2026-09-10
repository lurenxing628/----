"""FE-01 nullable table facts and service-owned snapshot-bound export selection."""

import ast
import sqlite3
from pathlib import Path

import pytest
from flask import Blueprint, Flask, g

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_resource_file import ResourceFileDownload
from core.models.workbench_resource_query import ResourcePageRequest
from core.models.workbench_resource_table_query import table_columns
from core.services.workbench.resource_files import WorkbenchResourceFileService
from core.services.workbench.resource_queries import WorkbenchResourceQueryService
from tests.workbench.resource_table_support import VIEWS, stored_state, table_database
from tests.workbench.test_resource_file_support import decode
from web.routes.workbench.resource_file_exports import resource_export, resource_export_preview
from web.routes.workbench.resource_table_queries import register_resource_table_routes

BASE = "/api/workbench/v1"


@pytest.fixture
def readonly_tables(table_conn):
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
        yield table_conn
    finally:
        table_conn.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
        assert denied == [] and stored_state(table_conn) == before
        assert not table_conn.in_transaction


@pytest.fixture
def export_client(readonly_tables):
    app = Flask(__name__)
    bp = Blueprint("fe01_resource_export", __name__)
    register_resource_table_routes(bp)
    bp.add_url_rule(BASE + "/exports/<kind>/preview", view_func=resource_export_preview, methods=["POST"])
    bp.add_url_rule(BASE + "/exports/<kind>", view_func=resource_export)
    app.register_blueprint(bp)

    @app.before_request
    def bind_database():
        g.db = readonly_tables

    return app.test_client()


@pytest.mark.parametrize("category,extra", [(None, ()), ("internal", ("available_machines", "available_operators")),
                                          ("external", ("default_merge_mode",)), ("unregistered", ())])
def test_table_columns_preserve_none_and_category_boundary(category, extra):
    assert table_columns("op_type", category) == ("business_code", "label") + extra + ("remark",)
    assert table_columns("unknown", category) == ()
    if category == "unregistered":
        with pytest.raises(WorkbenchCommandRejected) as error:
            ResourcePageRequest("op_type", category=category)
        assert error.value.code == "invalid_input"


@pytest.mark.parametrize("mode,label", [(None, "未设置"), ("separate", "分别设置"), ("merged", "合并设置"), ("legacy-mode", "legacy-mode")])
def test_policy_labels_keep_missing_known_and_legacy_values(readonly_tables, monkeypatch, mode, label):
    service = WorkbenchResourceQueryService(readonly_tables, "op_type")
    with service.read_snapshot():
        facts = service._table_reader()
        monkeypatch.setattr(facts, "mapped", lambda *args: {"X": {"default_merge_mode": mode}})
        cell = facts._op_type_cells("X", {"remark": None}, "external")["default_merge_mode"]
        assert cell.label == label


def test_optional_unbound_relation_stays_empty_but_null_label_member_fails_closed(readonly_tables, monkeypatch):
    service = WorkbenchResourceQueryService(readonly_tables, "machine")
    with service.read_snapshot():
        facts = service._table_reader()
        assert facts.related("op_type", None) is None
        assert facts.cells("machine", "FREE", None)["op_type_ref"].label == "未绑定"
        monkeypatch.setattr(facts, "_relation_labels", lambda *args: {"op_type_ref": ("op_type", [None])})
        with pytest.raises(WorkbenchCommandRejected) as error:
            facts.cells("machine", "FREE", None)
        assert error.value.code == "storage_failure" and error.value.status == 500


def _query(client, kind, scope):
    response = client.post(BASE + "/entities/" + kind + "/query", json={**scope, "size": 200})
    assert response.status_code == 200, response.get_json()
    return response.get_json()


@pytest.mark.parametrize("kind,category", [(kind, category) for kind, category in VIEWS if kind != "material"])
@pytest.mark.parametrize("selection", ["all", "filtered", "selected"])
def test_export_selection_delegates_to_service_and_keeps_source_snapshot_binding(export_client, monkeypatch, kind, category, selection):
    toolbar = {"category": category} if category else {}
    all_rows = _query(export_client, kind, toolbar)["data"]["entities"]
    scope = {**toolbar, "query": all_rows[0]["business_code"]}
    listed = _query(export_client, kind, scope)
    selected = [all_rows[-1], all_rows[0]]
    body = {"selection": selection, "scope": scope, "page_size": 200,
            "snapshot_ref": listed["meta"]["snapshot_ref"]}
    if selection == "selected":
        body["refs"] = [row["ref"] for row in selected]
    expected = all_rows if selection == "all" else selected if selection == "selected" else listed["data"]["entities"]
    calls = []
    original = WorkbenchResourceFileService.preview_export

    def preview(service, selected_mode, **kwargs):
        assert service.conn is g.db and service.conn.in_transaction
        calls.append((service.kind, selected_mode, kwargs))
        return original(service, selected_mode, **kwargs)

    monkeypatch.setattr(WorkbenchResourceFileService, "preview_export", preview)
    response = export_client.post(BASE + "/exports/" + kind + "/preview", json=body)
    assert response.status_code == 200, response.get_json()
    approved = response.get_json()
    assert len(calls) == 1 and calls[0][:2] == (kind, selection)
    assert approved["meta"]["source"] == "production"
    assert approved["meta"]["snapshot_ref"] == listed["meta"]["snapshot_ref"]
    assert approved["meta"]["as_of"] == listed["meta"]["as_of"]
    assert approved["data"]["row_count"] == len(expected)
    assert approved["data"]["scope"]["category"] == category
    result = export_client.get(BASE + "/exports/" + kind, query_string={
        "export_ref": approved["data"]["export_ref"], "format": "csv"})
    assert result.status_code == 200, result.get_json()
    assert result.headers["Cache-Control"] == "no-store"
    assert result.headers["X-Workbench-Snapshot-Ref"] == listed["meta"]["snapshot_ref"]
    assert result.headers["X-Workbench-As-Of"] == listed["meta"]["as_of"]
    download = ResourceFileDownload("file.csv", result.mimetype, result.data, int(result.headers["X-Workbench-Row-Count"]))
    assert [row[0] for row in decode(download, "csv")[1]] == [row["business_code"] for row in expected]


@pytest.mark.parametrize("selection,extra,status", [("all", {"refs": None}, 400), ("filtered", {"refs": []}, 400),
    ("selected", {}, 400), ("selected", {"refs": None}, 422), ("unknown", {}, 400)])
def test_export_transport_preserves_absent_versus_null_refs(export_client, selection, extra, status):
    listed = _query(export_client, "machine", {})
    response = export_client.post(BASE + "/exports/machine/preview", json={
        "selection": selection, "scope": {}, "page_size": 200,
        "snapshot_ref": listed["meta"]["snapshot_ref"], **extra})
    assert response.status_code == status, response.get_json()
    assert response.get_json()["committed"] is False
    assert response.get_json()["error"]["code"] == "invalid_input"


def test_service_preview_requires_snapshot_and_rejects_foreign_selected_category(readonly_tables):
    service = WorkbenchResourceFileService(readonly_tables, "op_type")
    with pytest.raises(RuntimeError):
        service.preview_export("all", scope={"category": "internal"})
    ref = readonly_tables.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='op_type' AND entity_key='X'").fetchone()[0]
    with service.reader.read_snapshot():
        with pytest.raises(WorkbenchCommandRejected) as error:
            service.preview_export("selected", scope={"category": "internal"}, selected_refs=[ref])
        assert error.value.code == "constraint_conflict"
        assert service.preview_export("selected", scope={"category": "internal"}, selected_refs=[])[1] == 0
        with pytest.raises(WorkbenchCommandRejected) as error:
            service.preview_export("unknown", scope={"category": "internal"})
        assert error.value.code == "invalid_input"


def test_export_route_has_no_repository_or_sql_dependency():
    path = Path(__file__).resolve().parents[2] / "web/routes/workbench/resource_file_exports.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(("data", "sqlite3"))
        if isinstance(node, ast.Import):
            assert all(not alias.name.startswith(("data", "sqlite3")) for alias in node.names)
        if isinstance(node, ast.Attribute):
            assert node.attr not in ("repo", "execute", "executemany", "executescript")
