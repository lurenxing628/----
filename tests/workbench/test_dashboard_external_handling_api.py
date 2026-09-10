"""Reuse the existing dashboard list/detail/history/transition/reopen routes."""

from core.infrastructure.database import get_connection
from tests.workbench.dashboard_external_handling_support import external_handling_case as _handling_case  # noqa: F401
from tests.workbench.dashboard_external_support import external_case as _external_case  # noqa: F401
from tests.workbench.dashboard_support import api, close_payload
from tests.workbench.dashboard_support import dashboard_case as _dashboard_case  # noqa: F401

ROOT = "/api/workbench/v1/dashboard"


def test_external_uses_existing_http_contract(external_handling_case, monkeypatch):
    case = external_handling_case
    case.register()
    client = api(case, monkeypatch, connect_factory=lambda path: get_connection(str(path)))
    query = {"category": "external", "size": 1}
    response = client.get(ROOT, query_string=query)
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    item = body["data"]["items"][0]
    query["snapshot_ref"] = body["meta"]["snapshot_ref"]
    url = ROOT + "/items/" + item["item_ref"]
    assert client.get(url, query_string=query).status_code == 200
    result = client.post(url + "/transition", json={"request_key": "external-handling-http-01",
                         "write_token": item["write_context"]["write_token"], "input": close_payload()})
    assert result.status_code == 200, result.get_json()
    assert client.get(url, query_string=query).get_json()["error"]["code"] == "snapshot_stale"
    body = client.get(ROOT, query_string={"category": "external", "size": 1}).get_json()
    query["snapshot_ref"] = body["meta"]["snapshot_ref"]
    history = client.get(url + "/history", query_string=query).get_json()["data"]["history"]
    assert history["page"]["total"] == 1
    assert history["items"][0]["receipt_ref"] == result.get_json()["receipt_ref"]
    current = body["data"]["items"][0]
    reopened = client.post(url + "/reopen", json={"request_key": "external-handling-http-02",
                           "write_token": current["write_context"]["write_token"], "input": {"reason": "Recheck original evidence"}})
    assert reopened.status_code == 200 and reopened.get_json()["data"]["handling"]["status"] == "following"
