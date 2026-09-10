"""Isolated route registration and real HTTP command/read snapshots."""

import pytest

from core.services.workbench.commands import WorkbenchCommandService
from tests.workbench.dashboard_support import api, follow  # noqa: F401
from tests.workbench.dashboard_support import dashboard_case as _dashboard_case

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


@pytest.mark.parametrize("query", ["size=0", "size=101", "page=2", "source=demo", "source=x", "category=fake",
                                  "sort=owner", "query=x&query=y", "unknown=x", "page=1.5", "page=true", "history_page=0"])
def test_query_contract_rejects_unknown_duplicate_or_missing_snapshot(dashboard_case, monkeypatch, query):
    client = api(dashboard_case, monkeypatch)
    response = client.get(ROOT + "?" + query)
    assert response.status_code == 400
    assert response.get_json()["committed"] is False


def test_failure_uncertain_supplies_original_receipt_target(dashboard_case, monkeypatch):
    case = dashboard_case
    client = api(case, monkeypatch)
    item, _ = list_item(client)
    case.conn.execute("CREATE TRIGGER dashboard_http_abort BEFORE INSERT ON WorkbenchCommandReceipts BEGIN SELECT RAISE(ABORT,'injected'); END")
    body = {"request_key": "dashboard-http-uncertain-01", "write_token": item["write_context"]["write_token"], "input": follow()}
    response = client.post(ROOT + "/items/" + item["item_ref"] + "/transition", json=body)
    result = response.get_json()
    assert response.status_code == 500 and result["committed"] == "unknown"
    assert body["request_key"] in result["error"]["result_target"]
    assert client.get(result["error"]["result_target"]).get_json()["state"] == "not_observed"
    assert WorkbenchCommandService(case.conn).lookup(body["request_key"]) is None


def test_business_validation_has_field_path(dashboard_case, monkeypatch):
    client = api(dashboard_case, monkeypatch)
    item, _ = list_item(client)
    response = client.post(ROOT + "/items/" + item["item_ref"] + "/transition", json={
        "request_key": "dashboard-http-invalid-01", "write_token": item["write_context"]["write_token"], "input": follow(owner=None)})
    assert response.status_code == 422
    assert response.get_json()["error"]["fields"][0]["path"] == "owner"


def test_snapshot_scope_and_raw_facts_drift_rejected(dashboard_case, monkeypatch):
    case = dashboard_case
    client = api(case, monkeypatch)
    _, token = list_item(client)
    response = client.get(ROOT, query_string={"snapshot_ref": token, "category": "material"})
    assert response.status_code == 409
    case.conn.execute("UPDATE Batches SET remark=?", (b"raw-drift",))
    case.conn.commit()
    assert client.get(ROOT, query_string={"snapshot_ref": token}).get_json()["error"]["code"] == "snapshot_stale"


def test_public_wire_has_no_database_keys_or_private_snapshots(dashboard_case, monkeypatch):
    client = api(dashboard_case, monkeypatch)

    def check(value):
        if isinstance(value, dict):
            assert not set(value) & {"op_id", "schedule_id", "candidate_id", "source_key", "entity_key", "revision", "source_facts_json", "_snapshot", "_facts"}
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)

    check(client.get(ROOT).get_json())
