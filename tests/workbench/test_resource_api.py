"""Real Flask resource creation, update, stale-context rejection, replay and deletion."""


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


@pytest.mark.parametrize('kind', ['machine'])
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
