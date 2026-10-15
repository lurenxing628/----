"""Isolated route registration and real HTTP command/read snapshots."""

import csv
import json
import subprocess
from io import StringIO
from pathlib import Path

import pytest

from tests.workbench.dashboard_support import api, follow  # noqa: F401
from tests.workbench.dashboard_support import dashboard_case as dashboard_fixture  # noqa: F401
from tests.workbench.node_runtime_support import node_runtime
from tests.workbench.point_downstream_support import ACTUAL, app_for, read
from tests.workbench.run_candidate_support import candidate_case as candidate_fixture  # noqa: F401

ROOT = "/api/workbench/v1/dashboard"


def list_item(client):
    response = client.get(ROOT)
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    return next(row for row in body["data"]["items"] if row["category"] == "delivery"), body["meta"]["snapshot_ref"]


def test_routes_list_detail_transition_history_and_stale_snapshot(dashboard_case, monkeypatch):
    from core.models.workbench_command import WorkbenchCommandRejected
    from core.services.workbench.dashboard.policy import history_contents
    from data.repositories.workbench_dashboard_repo import WorkbenchDashboardRepository

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
    row = WorkbenchDashboardRepository(dashboard_case.conn).history_rows(item["item_ref"], 1, 0)[0]
    assert row["source_hash"] is None
    saved = json.loads(row["source_facts_json"])
    assert saved["facts"] and saved["guard"]["identity"]["item_ref"] == item["item_ref"]
    assert saved["guard"]["revision"] == 0 and saved["guard"]["handling"]["status"] == "new"
    original = history_contents(row)
    legacy_hash = "a238b41ba2fb0965614fc2900a71b159051e868872a77a7d0543b05c9c5fe63e"
    historical = dict(row, source_hash=legacy_hash)
    assert history_contents(historical) == original and historical["source_hash"] == legacy_hash
    for field, value in (("receipt_action", "dashboard.reopen"), ("receipt_context_ref", "0" * 48)):
        with pytest.raises(WorkbenchCommandRejected, match="处置记录") as rejected:
            history_contents(dict(historical, **{field: value}))
        assert rejected.value.code == "dashboard_storage_invalid"
    outcome = json.loads(row["receipt_outcome_json"])
    outcome["data"]["history_ref"] = "0" * 48
    with pytest.raises(WorkbenchCommandRejected, match="处置记录") as rejected:
        history_contents(dict(historical, receipt_outcome_json=json.dumps(outcome)))
    assert rejected.value.code == "dashboard_storage_invalid"
    saved["guard"]["revision"] = False
    with pytest.raises(WorkbenchCommandRejected, match="处置记录") as rejected:
        history_contents(dict(historical, source_facts_json=json.dumps(saved)))
    assert rejected.value.code == "dashboard_storage_invalid"


def test_first_screen_list_and_analysis_share_one_fact_read(dashboard_case, monkeypatch, record_property):
    from core.services.workbench.dashboard.facts import DashboardFacts

    case = dashboard_case
    case.conn.execute("UPDATE Schedule SET end_time='2026-09-09T10:09:59.940000' WHERE version=1")
    case.conn.commit()
    case.report()
    client = api(dashboard_case, monkeypatch)
    original, calls = DashboardFacts.load, []
    original_contents, snapshots = DashboardFacts.snapshot_contents, []

    def load(facts):
        calls.append(facts)
        return original(facts)

    def snapshot_contents(facts, **kwargs):
        state = original_contents(facts, **kwargs)
        snapshots.append(state)
        return state

    monkeypatch.setattr(DashboardFacts, "load", load)
    monkeypatch.setattr(DashboardFacts, "snapshot_contents", snapshot_contents)
    restored = client.get(ROOT, query_string={"page": 2, "size": 1})
    assert restored.status_code == 200, restored.get_json()
    direct = restored.get_json()
    assert len(calls) == len(snapshots) == 1 and direct["data"]["page"]["number"] == 2
    assert len(direct["data"]["items"]) == 1
    record_property("direct_page", 2)
    record_property("fact_query_calls", len(calls))
    record_property("data_fields", sorted(direct["data"]))
    repeated = client.get(ROOT, query_string={"page": 2, "size": 1, "snapshot_ref": direct["meta"]["snapshot_ref"]}).get_json()
    assert repeated["data"] == direct["data"] and repeated["meta"].keys() == direct["meta"].keys()
    assert repeated["meta"]["request_ref"] != direct["meta"]["request_ref"]
    assert all(repeated["meta"][key] == value for key, value in direct["meta"].items() if key != "request_ref")
    calls.clear()
    snapshots.clear()
    response = client.get(ROOT)
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert len(calls) == 1
    assert len(snapshots) == 1
    contents = json.loads(snapshots[0])
    assert type(contents["raw"]["external"]) is dict and type(contents["raw"]["candidate_catalog"]) is dict
    assert all("facts" not in guard for ref, guard in contents["view"]["items"])
    assert body["data"]["analysis_error"] is None
    assert body["data"]["analysis"]["plan"] == body["data"]["plan"]
    assert body["data"]["analysis"]["as_of"] == body["meta"]["as_of"]
    execution_client = app_for(case).test_client()
    plan_ref = body["data"]["plan"]["plan_ref"]
    boundary = read(execution_client, ACTUAL, plan_ref=plan_ref)
    deviation = boundary["data"]["items"][0]["deviation"]
    review = read(execution_client, "/api/workbench/v1/analytics", plan_ref=plan_ref)
    assert deviation["as_of"] == boundary["meta"]["as_of"]
    assert (deviation["finish_deviation_minutes"], deviation["finish_late"]) == (10, False)
    assert (review["data"]["rows"][0]["finish_deviation_minutes"], review["data"]["rows"][0]["finish_late"]) == (10, False)
    assert boundary["data"]["execution_summary"] == {"complete": 1, "reported": 0, "pending": 0,
        "average_finish_deviation_minutes": 10, "known_finish_count": 1, "scope": "full_response_cohort"}
    exported = execution_client.get(ACTUAL + "/export", query_string={"plan_ref": plan_ref, "format": "csv",
        "snapshot_ref": boundary["meta"]["snapshot_ref"], "late_filter": "finishLate"})
    assert exported.status_code == 200
    assert list(csv.DictReader(StringIO(exported.data.decode("utf-8-sig")))) == []
    case.conn.execute("UPDATE Schedule SET end_time='2026-09-09T10:09:59' WHERE version=1")
    case.conn.commit()
    item = next(row for row in body["data"]["items"] if row["category"] == "delivery")
    stale = client.get(ROOT + "/items/" + item["item_ref"], query_string={"snapshot_ref": body["meta"]["snapshot_ref"]})
    assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "snapshot_stale"
    late = read(execution_client, ACTUAL, plan_ref=plan_ref)
    review = read(execution_client, "/api/workbench/v1/analytics", plan_ref=plan_ref)
    assert (late["data"]["items"][0]["deviation"]["finish_deviation_minutes"],
            late["data"]["items"][0]["deviation"]["finish_late"]) == (10.02, True)
    assert (review["data"]["rows"][0]["finish_deviation_minutes"], review["data"]["rows"][0]["finish_late"]) == (10.02, True)


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


def test_standalone_analysis_over_budget_preserves_complete_list(dashboard_case, monkeypatch):
    from core.models.workbench_dashboard import MAX_BYTES

    case = dashboard_case
    reason = "x" * (MAX_BYTES * 9 // 16)
    case.conn.execute("UPDATE MachineDowntimes SET reason_detail=?", (reason,))
    case.conn.commit()
    client = api(case, monkeypatch)
    analysis = client.get(ROOT + "/analysis")
    assert analysis.status_code == 413
    assert analysis.get_json()["error"]["code"] == "query_too_large"
    merged = client.get(ROOT)
    assert merged.status_code == 200
    body = merged.get_json()
    assert len(merged.data) <= MAX_BYTES
    assert body["data"]["analysis"] is None and "读取上限" in body["data"]["analysis_error"]
    assert body["data"]["page"]["total"] == len(body["data"]["items"]) == 4
    downtime = next(row for row in body["data"]["items"] if row["category"] == "downtime")
    assert downtime["source"]["downtimes"][0]["reason"] == reason


def test_candidate_comparison_uses_dashboard_envelope_budget(candidate_case, monkeypatch):
    from core.models.workbench_dashboard import MAX_BYTES
    from tests.workbench.run_candidate_support import compute

    case = candidate_case
    case.conn.execute("UPDATE Batches SET part_name=?", ("x" * (MAX_BYTES * 9 // 16),))
    case.conn.commit()
    _, candidates = compute(case)
    response = api(case, monkeypatch).get(ROOT + "/candidates/" + candidates[0] + "/comparison", query_string={
        "range_start": "2026-09-09T00:00:00", "range_end": "2026-09-26T00:00:00"})
    assert response.status_code == 413, response.get_json()
    assert response.get_json()["error"]["code"] == "query_too_large"


@pytest.mark.parametrize("endpoint, reader_name", [("/analysis", "read_dashboard_analysis"),
                                                   ("/candidates/" + "a" * 48 + "/comparison", "read_candidate_comparison")])
def test_dashboard_analysis_envelopes_never_return_nonfinite_json(dashboard_case, monkeypatch, endpoint, reader_name):
    import web.routes.workbench.dashboard_analysis as module

    monkeypatch.setattr(module, reader_name, lambda *args: ({"unserializable_number": float("nan")}, "fault-snapshot"))
    response = api(dashboard_case, monkeypatch).get(ROOT + endpoint)
    assert response.status_code == 500
    body = response.get_json()
    assert body["ok"] is False and body["committed"] is False
    assert body["error"]["code"] == "storage_failure"
    assert b"NaN" not in response.data
