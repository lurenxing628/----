"""Actual Flask resource contracts, with parent and related records in isolated SQLite."""

import sqlite3

import pytest

BASE = "/api/workbench/v1/entities/"


def _list(client, kind, **query):
    response = client.get(BASE + kind, query_string=query)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


def _detail(client, kind, ref):
    response = client.get(BASE + kind + "/" + ref)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]


def _create(client, kind, code, *, fields=None, relationships=None):
    token = _list(client, kind)["data"]["create_context"]["write_token"]
    payload = {"business_code": code, "label": "Name-" + code, "fields": fields or {}}
    if relationships is not None:
        payload["relationships"] = relationships
    body = {"request_key": "resource-create-" + kind + "-" + code, "write_token": token, "input": payload}
    response = client.post(BASE + kind + "/create", json=body)
    assert response.status_code == 200, response.get_data(as_text=True)
    ref = response.get_json()["data"]["entity_ref"]
    return ref, body


def _command(client, kind, ref, action, payload, *, context=None, key="resource-command-000001"):
    if context is None:
        context = _detail(client, kind, ref)["write_context"]
    return client.post(BASE + kind + "/" + ref + "/" + action,
                       json={"request_key": key, "write_token": context["write_token"], "input": payload})


def test_real_resources_use_distinct_relations_and_explicit_statuses(app_client):
    internal, _ = _create(app_client, "op_type", "OT-IN", fields={"category": "internal"})
    external, _ = _create(app_client, "op_type", "OT-EXT", fields={"category": "external", "default_merge_mode": "merged"})
    group, _ = _create(app_client, "machine_group", "GROUP")
    shift, _ = _create(app_client, "shift_profile", "SHIFT", fields={"anchor_date": "2026-09-09", "cycle_days": 1,
                                                                  "pattern": [{"day_offset": 0, "is_rest": False, "shift_start": "22:00", "shift_end": "06:00"}]})
    machine, _ = _create(app_client, "machine", "M", relationships={"op_type_ref": internal, "group_ref": group})
    operator, _ = _create(app_client, "operator", "O", fields={"status": "leave"}, relationships={"skill_refs": [internal], "shift_profile_ref": shift})
    supplier, _ = _create(app_client, "supplier", "S", fields={"default_days": 3, "status": "pending_review"}, relationships={"op_type_refs": [external]})
    assert _detail(app_client, "machine", machine)["relationships"]["group_ref"] == group
    person = _detail(app_client, "operator", operator)
    assert person["status"] == "leave" and person["relationships"]["skill_refs"] == [internal]
    assert person["relationships"]["machine_authorization_count"] == 0
    assert person["relationships"]["shift_profile_ref"] == shift
    assert _detail(app_client, "supplier", supplier)["status"] == "pending_review"
    assert _detail(app_client, "shift_profile", shift)["fields"]["pattern"][0]["is_rest"] is False
    assert _list(app_client, "operator", status="leave")["data"]["page"]["total"] == 1
    assert _list(app_client, "supplier", status="pending_review")["data"]["page"]["total"] == 1
    with sqlite3.connect(app_client.application.config["DATABASE_PATH"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM OperatorMachine").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM ResourceTeams").fetchone()[0] == 0
        assert conn.execute("SELECT status FROM Operators WHERE operator_id='O'").fetchone()[0] == "inactive"
    summary = app_client.get("/api/workbench/v1/resources/summary").get_json()["data"]["counts"]
    assert summary["internal_op_types"] == summary["external_op_types"] == 1
    assert summary["machine"] == summary["operator"] == summary["supplier"] == 1


@pytest.mark.parametrize("kind", ("op_type", "machine", "operator", "supplier", "machine_group", "shift_profile"))
def test_update_delete_and_replay_are_real_for_each_kind(app_client, kind):
    fields = {"default_days": 3} if kind == "supplier" else {}
    if kind == "shift_profile":
        fields = {"anchor_date": "2026-09-09", "cycle_days": 1,
                  "pattern": [{"day_offset": 0, "is_rest": False, "shift_start": "08:00", "shift_end": "16:00"}]}
    ref, create = _create(app_client, kind, "ROW", fields=fields)
    before = _detail(app_client, kind, ref)
    changed = _command(app_client, kind, ref, "update", {"label": "Changed"}, context=before["write_context"], key="resource-update-000001")
    assert changed.status_code == 200 and changed.get_json()["result"] == "committed"
    assert _detail(app_client, kind, ref)["label"] == "Changed"
    stale = _command(app_client, kind, ref, "update", {"label": "Stale"}, context=before["write_context"], key="resource-stale-000001")
    assert stale.status_code == 409 and stale.get_json()["committed"] is False
    replay = app_client.post(BASE + kind + "/create", json=create)
    assert replay.status_code == 200 and replay.get_json()["replayed"] is True
    deleted = _command(app_client, kind, ref, "delete", {}, key="resource-delete-000001")
    assert deleted.status_code == 200 and deleted.get_json()["result"] == "committed"
    assert app_client.get(BASE + kind + "/" + ref).status_code == 404


def test_shared_references_disable_delete_and_snapshot_pages_detect_changes(app_client):
    op, _ = _create(app_client, "op_type", "OT", fields={"category": "internal"})
    group, _ = _create(app_client, "machine_group", "GROUP")
    machine, _ = _create(app_client, "machine", "M", relationships={"op_type_ref": op, "group_ref": group})
    for kind, ref in (("op_type", op), ("machine_group", group)):
        entity = _detail(app_client, kind, ref)
        assert entity["write_context"]["capabilities"][kind + ".delete"] is False
        assert _command(app_client, kind, ref, "delete", {}, context=entity["write_context"]).status_code == 409
    page = _list(app_client, "machine", size=1)
    assert _command(app_client, "machine", machine, "update", {"label": "After"}).status_code == 200
    stale = app_client.get(BASE + "machine", query_string={"size": 1, "page": 2, "snapshot_ref": page["meta"]["snapshot_ref"]})
    assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "snapshot_stale"


def test_legacy_inactive_reason_is_visible_without_guessing(app_client):
    with sqlite3.connect(app_client.application.config["DATABASE_PATH"]) as conn:
        conn.execute("INSERT INTO Operators(operator_id,name,status) VALUES ('OLD-O','Old','inactive')")
        conn.execute("INSERT INTO Suppliers(supplier_id,name,status,default_days) VALUES ('OLD-S','Old','inactive',4)")
    for kind in ("operator", "supplier"):
        page = _list(app_client, kind, status="unknown")
        entity = page["data"]["entities"][0]
        assert entity["status"] == "unknown" and entity["fields"]["legacy_status"] == "inactive"
        assert entity["issues"]
        assert _command(app_client, kind, entity["ref"], "update", {"label": "Renamed"}, key="legacy-rename-" + kind).status_code == 200
        assert _detail(app_client, kind, entity["ref"])["status"] == "unknown"


def test_resource_search_filter_and_choice_refs_are_not_names(app_client):
    external, _ = _create(app_client, "op_type", "EX", fields={"category": "external"})
    _create(app_client, "op_type", "IN", fields={"category": "internal"})
    rows = _list(app_client, "op_type", category="external")["data"]["entities"]
    assert len(rows) == 1 and rows[0]["ref"] == external
    assert _list(app_client, "op_type", query="Name-EX")["data"]["page"]["total"] == 1
    token = _list(app_client, "machine")["data"]["create_context"]["write_token"]
    response = app_client.post(BASE + "machine/create", json={"request_key": "bad-machine-relation-0001", "write_token": token,
                              "input": {"business_code": "M", "label": "Bad", "relationships": {"op_type_ref": external}}})
    assert response.status_code == 409 and response.get_json()["committed"] is False
    assert _list(app_client, "machine")["data"]["page"]["total"] == 0


@pytest.mark.parametrize("query", ({"size": "201"}, {"page": "-1"}, {"source": "demo"}, {"status": "leave"}, {"sort": "revision"}))
def test_bad_resource_query_is_not_an_internal_error(app_client, query):
    response = app_client.get(BASE + "machine", query_string=query)
    assert response.status_code == 400 and response.get_json()["error"]["code"] == "invalid_input"
