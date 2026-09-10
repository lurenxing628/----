"""Actual Flask registration, frozen scope, no-write previews and receipt replay."""

import json
from io import BytesIO

import pytest
from flask import Blueprint

from tests.workbench.material_actions_api_support import database, expire_contexts, snapshot, without_startup_logs
from tests.workbench.resource_file_support import SCOPES, decode, file_bytes

BASE = "/api/workbench/v1"


def registered(app):
    from web.routes.workbench.resource_actions import register_resource_action_routes
    if not any(rule.rule == BASE + "/imports/<kind>/preview" for rule in app.url_map.iter_rules()):
        bp = Blueprint("resource_actions_test", __name__)
        register_resource_action_routes(bp)
        app.register_blueprint(bp)
    return app.test_client()


@pytest.fixture
def client(db_env):
    from app import create_app
    return registered(create_app())


def upload(client, kind, rows, *, category=None, fmt="csv", headers=None, extra=None):
    headers = headers or (("business_code", "label", "category") if kind == "op_type" else ("business_code", "label", "status"))
    fields = {"file": (BytesIO(file_bytes(rows, fmt, headers)), "input." + fmt), "format": fmt, "mode": "upsert"}
    if category is not None:
        fields["category"] = category
    fields.update(extra or {})
    return client.post(BASE + "/imports/" + kind + "/preview", data=fields, content_type="multipart/form-data")


def command(client, kind, preview, *, key="resource-api-request-00001", operation="import", extra=None):
    body = {"request_key": key, "write_token": preview["write_context"]["write_token"], "input": {"preview_ref": preview["preview_ref"]}}
    body.update(extra or {})
    path = "/imports/" + kind + "/confirm" if operation == "import" else "/entities/" + kind + "/bulk-confirm"
    return client.post(BASE + path, json=body)


def context(client, kind, scope=None, size=1):
    scope = scope or {}
    response = client.get(BASE + "/entities/" + kind, query_string={**scope, "size": size})
    assert response.status_code == 200, response.get_data(as_text=True)
    return {"scope": scope, "page_size": size, "snapshot_ref": response.get_json()["meta"]["snapshot_ref"]}


def new_preview(client, kind, category=None):
    headers = ["business_code", "label", "category" if kind == "op_type" else "status"]
    rows = [["R1", "Resource 1", category or "active"], ["R2", "Resource 2", category or "active"]]
    if kind == "supplier":
        headers.append("default_days")
        rows = [row + [2.5] for row in rows]
    response = upload(client, kind, rows, category=category, headers=headers)
    assert response.status_code == 200, response.get_data(as_text=True)
    result = response.get_json()
    assert result["meta"]["snapshot_ref"] and result["data"]["can_confirm"]
    return result["data"]


@pytest.mark.parametrize("kind,category", SCOPES)
def test_real_registration_public_preview_and_committed_restart_replay(client, kind, category):
    before = snapshot(client)
    preview = new_preview(client, kind, category)
    assert snapshot(client) == before
    assert preview["operation"] == kind + ".import" and preview["commit_policy"] == "atomic"
    assert preview["scope"]["category"] == category
    if category:
        assert preview["category"] == category
    row = preview["rows"][0]
    assert set(row) == {"row", "business_code", "entity_ref", "action", "result", "before", "after", "changes", "errors", "requires_confirmation", "reference_count"}
    assert set(row["after"]) <= {item["key"] for item in preview["columns"]}
    assert "entity_key" not in json.dumps(preview) and "revision" not in json.dumps(preview)
    first = command(client, kind, preview)
    assert first.status_code == 200, first.get_data(as_text=True)
    expire_contexts(client)
    replay = command(client, kind, preview)
    assert replay.get_json() == {**first.get_json(), "replayed": True}
    from app import create_app
    restarted = registered(create_app())
    before = without_startup_logs(snapshot(restarted))
    replay = command(restarted, kind, preview)
    assert replay.get_json() == {**first.get_json(), "replayed": True}
    assert without_startup_logs(snapshot(restarted)) == before


@pytest.mark.parametrize("kind,category", SCOPES)
def test_uncommitted_preview_expiry_and_strict_command_shape(client, kind, category):
    preview = new_preview(client, kind, category)
    before = snapshot(client)
    for extra in ({"acknowledge_warnings": True}, {"input": {"preview_ref": preview["preview_ref"], "ack": True}},
                  {"input": {"preview_ref": preview["preview_ref"], "category": category}}):
        response = command(client, kind, preview, extra=extra)
        assert response.status_code == 400 and response.get_json()["committed"] is False
    expire_contexts(client)
    response = command(client, kind, preview)
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "stale_write"
    assert snapshot(client) == before


@pytest.mark.parametrize("kind,category", SCOPES)
def test_export_all_filtered_selected_scopes_and_bulk_cross_page(client, kind, category):
    preview = new_preview(client, kind, category)
    saved = command(client, kind, preview).get_json()
    refs = [row["entity_ref"] for row in saved["data"]["rows"]]
    scope = {"query": "R1", **({"category": category} if category else {})}
    if kind == "op_type":
        with database(client) as conn:
            conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('OTHER','other category',?)", ("external" if category == "internal" else "internal",))
            conn.commit()
    for selection, expected in (("all", ["R1", "R2"]), ("filtered", ["R1"]), ("selected", ["R2", "R1"])):
        body = {"selection": selection, **context(client, kind, scope)}
        if selection == "selected":
            body["refs"] = list(reversed(refs))
        before = snapshot(client)
        approved = client.post(BASE + "/exports/" + kind + "/preview", json=body)
        assert approved.status_code == 200, approved.get_data(as_text=True)
        data = approved.get_json()["data"]
        assert data["row_count"] == len(expected) and data["scope"]["category"] == category
        for fmt in ("csv", "xlsx"):
            result = client.get(BASE + "/exports/" + kind, query_string={"export_ref": data["export_ref"], "format": fmt})
            assert result.status_code == 200, result.get_data(as_text=True) if result.status_code != 200 else ""
            from core.models.workbench_resource_file import ResourceFileDownload
            download = ResourceFileDownload("file." + fmt, result.mimetype, result.data, int(result.headers["X-Workbench-Row-Count"]))
            assert [row[0] for row in decode(download, fmt)[1]] == expected
            assert result.headers["Cache-Control"] == "no-store"
        assert snapshot(client) == before
    body = {"action": "delete", "refs": list(reversed(refs)), **context(client, kind, scope)}
    preview = client.post(BASE + "/entities/" + kind + "/bulk-preview", json=body).get_json()["data"]
    assert [row["entity_ref"] for row in preview["rows"]] == list(reversed(refs))
    response = command(client, kind, preview, key="resource-api-delete-0001", operation="bulk")
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()["data"]["deleted_count"] == 2


def test_upload_category_is_mandatory_only_for_op_type(client):
    assert upload(client, "op_type", [["X", "x", "internal"]]).status_code == 400
    for kind in ("machine", "operator", "supplier"):
        assert upload(client, kind, [["X", "x", "active"]], category="internal").status_code == 400
    assert upload(client, "op_type", [["X", "x", "internal"]], category="invalid").status_code == 400


def test_scoped_refs_and_snapshots_cannot_switch_kind_or_category(client):
    preview = new_preview(client, "op_type", "internal")
    assert command(client, "op_type", preview).status_code == 200
    with database(client) as conn:
        conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('EXT','external','external')")
        conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('M','machine')")
        conn.commit()
        refs = [row[0] for row in conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE (kind='op_type' AND entity_key='EXT') OR kind='machine'")]
    bound = context(client, "op_type", {"category": "internal"})
    for ref in refs:
        response = client.post(BASE + "/exports/op_type/preview", json={"selection": "selected", "refs": [ref], **bound})
        assert response.status_code >= 400
    response = client.post(BASE + "/exports/op_type/preview", json={"selection": "all", **bound, "scope": {"category": "external"}})
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"


def test_templates_metadata_and_bytes_only_read(client):
    before = snapshot(client)
    for kind, category in SCOPES:
        for fmt in ("csv", "xlsx"):
            response = client.get(BASE + "/templates/" + kind, query_string={"format": fmt, **({"category": category} if category else {})})
            assert response.status_code == 200 and response.headers["X-Workbench-Row-Count"] == "0"
            assert (response.data.startswith(b"PK") if fmt == "xlsx" else response.data.startswith(b"\xef\xbb\xbf"))
    assert snapshot(client) == before


def test_confirm_must_bind_current_server_preview_not_foreign_write_context(client):
    first = new_preview(client, "machine")
    response = upload(client, "machine", [["OTHER", "other", "active"]])
    second = response.get_json()["data"]
    before = snapshot(client)
    rejected = command(client, "machine", first, extra={"write_token": second["write_context"]["write_token"]})
    assert rejected.status_code == 409 and rejected.get_json()["error"]["code"] == "stale_write"
    assert snapshot(client) == before
    assert command(client, "machine", first).status_code == 200
    conflict = command(client, "machine", second)
    assert conflict.status_code == 409 and conflict.get_json()["error"]["code"] == "request_key_conflict"


def test_10000_selected_export_keeps_server_refs_out_of_short_token_binding(client):
    from tests.workbench.resource_file_support import seed_many
    from web import public_token_registry
    from web.routes.workbench.resource_action_context import EXPORT_SCOPE, EXTENSION, PREVIEW_SCOPE
    with database(client) as conn:
        refs = seed_many(conn, "machine", 10000)
    bound = context(client, "machine", {"query": "FILE00000"})
    body = {"selection": "selected", "refs": refs, **bound}
    approved = client.post(BASE + "/exports/machine/preview", json=body)
    assert approved.status_code == 200, approved.get_data(as_text=True)
    data = approved.get_json()["data"]
    assert data["row_count"] == 10000
    with client.application.app_context():
        value = public_token_registry.resolve_public_token(EXPORT_SCOPE, data["export_ref"], message="test export", field="export_ref")
        assert len(value) < 200 and "FILE00000" not in value and refs[0] not in value
        assert any(refs[-1] in entry.document for entry in client.application.extensions[EXTENSION].values())
    downloaded = client.get(BASE + "/exports/machine", query_string={"export_ref": data["export_ref"], "format": "csv"})
    assert downloaded.status_code == 200 and downloaded.headers["X-Workbench-Row-Count"] == "10000"
    assert b"FILE09999" in downloaded.data
    bulk = client.post(BASE + "/entities/machine/bulk-preview", json={"action": "delete", "refs": refs, **bound})
    assert bulk.status_code == 200
    preview = bulk.get_json()["data"]
    assert len(preview["rows"]) == 10000
    with client.application.app_context():
        value = public_token_registry.resolve_public_token(PREVIEW_SCOPE, preview["preview_ref"], message="test preview", field="preview_ref")
        assert len(value) < 200 and refs[0] not in value


def test_export_is_rejected_after_bound_facts_change(client):
    preview = new_preview(client, "machine")
    assert command(client, "machine", preview).status_code == 200
    approved = client.post(BASE + "/exports/machine/preview", json={"selection": "all", **context(client, "machine")}).get_json()["data"]
    with database(client) as conn:
        conn.execute("UPDATE Machines SET name='concurrent' WHERE machine_id='R2'")
        conn.commit()
    before = snapshot(client)
    result = client.get(BASE + "/exports/machine", query_string={"export_ref": approved["export_ref"], "format": "csv"})
    assert result.status_code == 409 and result.get_json()["error"]["code"] == "snapshot_stale"
    assert snapshot(client) == before
