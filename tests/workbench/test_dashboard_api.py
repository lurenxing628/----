"""Isolated route registration and real HTTP command/read snapshots."""

import json
import subprocess
from pathlib import Path

from tests.workbench.dashboard_support import api, follow  # noqa: F401
from tests.workbench.dashboard_support import dashboard_case as dashboard_case  # noqa: F401
from tests.workbench.node_runtime_support import node_runtime

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


def test_first_screen_list_and_analysis_share_one_fact_read(dashboard_case, monkeypatch):
    from core.services.workbench.dashboard.facts import DashboardFacts

    client = api(dashboard_case, monkeypatch)
    original, calls = DashboardFacts.load, []

    def load(facts):
        calls.append(facts)
        return original(facts)

    monkeypatch.setattr(DashboardFacts, "load", load)
    response = client.get(ROOT)
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert len(calls) == 1
    assert body["data"]["analysis_error"] is None
    assert body["data"]["analysis"]["plan"] == body["data"]["plan"]
    assert body["data"]["analysis"]["as_of"] == body["meta"]["as_of"]


def test_analysis_failure_does_not_hide_the_readable_list(dashboard_case, monkeypatch):
    from core.models.workbench_command import WorkbenchCommandRejected
    from core.services.workbench.dashboard.service import WorkbenchDashboardService

    def unavailable(*args):
        raise WorkbenchCommandRejected("query_too_large", "分析超过读取上限。", 413)

    monkeypatch.setattr(WorkbenchDashboardService, "analysis", unavailable)
    response = api(dashboard_case, monkeypatch).get(ROOT)
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["items"] and data["analysis"] is None
    assert data["analysis_error"] == "分析超过读取上限。"


def test_merged_response_budget_keeps_the_complete_readable_list(dashboard_case, monkeypatch):
    from core.models.workbench_dashboard import MAX_BYTES

    case = dashboard_case
    case.conn.execute("UPDATE MachineDowntimes SET reason_detail=?", ("x" * (3 * 1024 * 1024),))
    case.conn.commit()
    client = api(case, monkeypatch)

    standalone = client.get(ROOT + "/analysis")
    assert standalone.status_code == 200 and len(standalone.data) <= MAX_BYTES
    assert standalone.get_json()["data"]["overlaps"]
    response = client.get(ROOT)
    assert response.status_code == 200 and len(response.data) <= MAX_BYTES
    body = response.get_json()
    assert body["data"]["analysis"] is None
    assert "读取上限" in body["data"]["analysis_error"]
    assert body["data"]["page"]["total"] == len(body["data"]["items"]) == 4
    downtime = next(row for row in body["data"]["items"] if row["category"] == "downtime")
    assert len(downtime["source"]["downtimes"][0]["reason"]) == 3 * 1024 * 1024
    detail = client.get(ROOT + "/items/" + downtime["item_ref"], query_string={"snapshot_ref": body["meta"]["snapshot_ref"]})
    assert detail.status_code == 200 and len(detail.data) <= MAX_BYTES


def test_unavailable_plan_keeps_handling_readable_and_analysis_consistent(dashboard_case, monkeypatch):
    case = dashboard_case
    item = case.item()
    case.command(item, follow())
    client = api(case, monkeypatch)
    healthy = client.get(ROOT).get_json()
    plan_ref = healthy["data"]["plan"]["plan_ref"]
    case.conn.execute("UPDATE WorkbenchEntityRefs SET active=0 WHERE kind='batch' AND entity_key='DB1'")
    case.conn.commit()

    response = client.get(ROOT)
    assert response.status_code == 200
    unavailable = response.get_json()
    data = unavailable["data"]
    assert data["plan"] is None and data["analysis"]["plan"] is None
    assert data["analysis"]["state"] == "unavailable" and data["analysis_error"] is None
    retained = next(row for row in data["items"] if row["item_ref"] == item["item_ref"])
    assert retained["source_state"] == "not_currently_evaluated"
    assert retained["handling"]["status"] == "following"
    detail = client.get(ROOT + "/items/" + item["item_ref"], query_string={"snapshot_ref": unavailable["meta"]["snapshot_ref"]})
    assert detail.status_code == 200
    assert client.get(ROOT + "/analysis").get_json()["data"]["state"] == "unavailable"
    stale = client.get(ROOT + "/analysis", query_string={"plan_ref": plan_ref})
    assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "snapshot_stale"

    result = subprocess.run(
        [node_runtime(), str(Path(__file__).with_name("dashboard_list_probe.cjs"))],
        input=json.dumps({"healthy": healthy, "unavailable": unavailable}),
        text=True, encoding="utf-8", capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
