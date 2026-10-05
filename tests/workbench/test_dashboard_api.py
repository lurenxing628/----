"""Isolated route registration and real HTTP command/read snapshots."""


from tests.workbench.dashboard_support import api, follow  # noqa: F401
from tests.workbench.dashboard_support import dashboard_case as dashboard_case  # noqa: F401

ROOT = "/api/workbench/v1/dashboard"


def list_item(client):
    response = client.get(ROOT)
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    return next(row for row in body["data"]["items"] if row["category"] == "delivery"), body["meta"]["snapshot_ref"]


def test_routes_list_detail_transition_history_and_stale_snapshot(dashboard_case, monkeypatch):
    client = api(dashboard_case, monkeypatch)
    item, snapshot = list_item(client)
    url = ROOT + "/items/" + item["item_ref"]
    assert client.get(url).status_code == 400
    assert client.get(url, query_string={"snapshot_ref": snapshot}).status_code == 200
    body = {"request_key": "dashboard-http-command-01", "write_token": item["write_context"]["write_token"], "input": follow()}
    response = client.post(url + "/transition", json=body)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["result"] == "committed"
    assert client.post(url + "/transition", json=body).get_json()["replayed"]
    stale = client.get(url, query_string={"snapshot_ref": snapshot})
    assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "snapshot_stale"
    _, fresh = list_item(client)
    history = client.get(url + "/history", query_string={"snapshot_ref": fresh}).get_json()
    assert history["data"]["history"]["page"]["total"] == 1
    assert history["data"]["history"]["items"][0]["receipt_ref"] == response.get_json()["receipt_ref"]
