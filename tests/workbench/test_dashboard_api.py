"""Isolated route registration and real HTTP command/read snapshots."""

import csv
import json
import subprocess
from datetime import datetime
from io import StringIO
from pathlib import Path

import pytest

from core.shared.local_datetime import datetime_to_us
from tests._support.node_runtime_support import node_runtime
from tests.workbench.dashboard_external_handling_support import (
    external_handling_case as external_handling_fixture,  # noqa: F401
)
from tests.workbench.dashboard_external_support import external_case as external_fixture  # noqa: F401
from tests.workbench.dashboard_support import api, follow  # noqa: F401
from tests.workbench.dashboard_support import dashboard_case as dashboard_fixture  # noqa: F401
from tests.workbench.plan_catalog_support import insert_schedule_row, update_schedule_rows
from tests.workbench.point_downstream_support import ACTUAL, app_for, read, read_body
from tests.workbench.run_candidate_support import candidate_case as candidate_fixture  # noqa: F401

ROOT = "/api/workbench/v1/dashboard"


def list_item(client):
    response = client.get(ROOT)
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    return next(row for row in body["data"]["items"] if row["category"] == "delivery"), body["meta"]["snapshot_ref"]


def test_routes_list_detail_transition_history_and_stale_snapshot(dashboard_case):
    from data.repositories.workbench_dashboard_repo import WorkbenchDashboardRepository

    client = api(dashboard_case)
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
    saved = json.loads(row["source_json"])
    assert saved["item_ref"] == item["item_ref"] and saved["category"] == "delivery"


def test_first_screen_list_and_analysis_share_one_fact_read(dashboard_case, monkeypatch, record_property):
    from core.services.workbench.dashboard.facts import DashboardFacts

    case = dashboard_case
    update_schedule_rows(case.conn, 1, end_time="2026-09-09T10:09:59.940000")
    case.conn.commit()
    case.report()
    client = api(dashboard_case)
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
    assert isinstance(contents["revisions"], dict) and contents["plan_state"] == "loaded" and "raw" not in contents
    assert set(contents) == {"revisions", "plan_state", "plan_issues", "execution_issues"}
    assert body["data"]["analysis_error"] is None
    assert body["data"]["analysis"]["plan"] == body["data"]["plan"]
    assert body["data"]["analysis"]["as_of"] == body["meta"]["as_of"]
    execution_client = app_for(case).test_client()
    plan_ref = body["data"]["plan"]["plan_ref"]
    boundary = read_body(execution_client, ACTUAL, plan_ref=plan_ref)
    deviation = boundary["data"]["items"][0]["deviation"]
    review = read(execution_client, "/api/workbench/v1/analytics", plan_ref=plan_ref)
    assert deviation["as_of"] == boundary["meta"]["as_of"]
    assert (deviation["finish_deviation_minutes"], deviation["finish_late"]) == (10, False)
    assert (review["data"]["rows"][0]["finish_deviation_minutes"], review["data"]["rows"][0]["finish_late"]) == (10, False)
    assert boundary["data"]["execution_summary"] == {"complete": 1, "reported": 0, "pending": 0,
        "average_finish_deviation_minutes": 10, "known_finish_count": 1, "scope": "full_response_cohort"}
    exported = execution_client.post(ACTUAL + "/export", json={"plan_ref": plan_ref, "format": "csv",
        "snapshot_ref": boundary["meta"]["snapshot_ref"], "late_filter": "finishLate"})
    assert exported.status_code == 200
    assert list(csv.DictReader(StringIO(exported.data.decode("utf-8-sig")))) == []
    update_schedule_rows(case.conn, 1, end_time="2026-09-09T10:09:59")
    case.conn.commit()
    item = next(row for row in body["data"]["items"] if row["category"] == "delivery")
    stale = client.get(ROOT + "/items/" + item["item_ref"], query_string={"snapshot_ref": body["meta"]["snapshot_ref"]})
    assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "snapshot_stale"
    late = read_body(execution_client, ACTUAL, plan_ref=plan_ref)
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
    response = api(dashboard_case).get(ROOT)
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["items"] and data["analysis"] is None
    assert data["analysis_error"] == "分析超过读取上限。"


def test_merged_response_budget_keeps_the_complete_readable_list(dashboard_case):
    from core.models.workbench_dashboard import MAX_BYTES

    case = dashboard_case
    case.conn.execute("UPDATE MachineDowntimes SET reason_detail=?", ("x" * (3 * 1024 * 1024),))
    case.conn.commit()
    client = api(case)

    standalone = client.get(ROOT + "/analysis", query_string={"section": "downtime"})
    assert standalone.status_code == 200 and len(standalone.data) <= MAX_BYTES
    assert standalone.get_json()["data"]["overlaps"]
    response = client.get(ROOT)
    assert response.status_code == 200 and len(response.data) <= MAX_BYTES
    body = response.get_json()
    assert body["data"]["analysis"]["pagination"]["section"] == "overview"
    assert body["data"]["analysis_error"] is None
    assert body["data"]["page"]["total"] == len(body["data"]["items"]) == 4
    downtime = next(row for row in body["data"]["items"] if row["category"] == "downtime")
    assert len(downtime["source"]["downtimes"][0]["reason"]) == 3 * 1024 * 1024
    detail = client.get(ROOT + "/items/" + downtime["item_ref"], query_string={"snapshot_ref": body["meta"]["snapshot_ref"]})
    assert detail.status_code == 200 and len(detail.data) <= MAX_BYTES


def test_unavailable_plan_keeps_handling_readable_and_analysis_consistent(dashboard_case):
    case = dashboard_case
    item = case.item()
    case.command(item, follow())
    client = api(case)
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


def test_standalone_analysis_over_budget_preserves_complete_list(dashboard_case):
    from core.models.workbench_dashboard import MAX_BYTES

    case = dashboard_case
    reason = "x" * (MAX_BYTES * 9 // 16)
    case.conn.execute("UPDATE MachineDowntimes SET reason_detail=?", (reason,))
    case.conn.commit()
    client = api(case)
    analysis = client.get(ROOT + "/analysis", query_string={"section": "downtime"})
    assert analysis.status_code == 413
    assert analysis.get_json()["error"]["code"] == "query_too_large"
    merged = client.get(ROOT)
    assert merged.status_code == 200
    body = merged.get_json()
    assert len(merged.data) <= MAX_BYTES
    assert body["data"]["analysis"]["pagination"]["section"] == "overview"
    assert body["data"]["analysis_error"] is None
    assert body["data"]["page"]["total"] == len(body["data"]["items"]) == 4
    downtime = next(row for row in body["data"]["items"] if row["category"] == "downtime")
    assert downtime["source"]["downtimes"][0]["reason"] == reason


def test_candidate_comparison_uses_dashboard_envelope_budget(candidate_case):
    from core.models.workbench_dashboard import MAX_BYTES
    from tests.workbench.run_candidate_support import compute

    case = candidate_case
    case.conn.execute("UPDATE Batches SET part_name=?", ("x" * (MAX_BYTES * 9 // 16),))
    case.conn.commit()
    _, candidates = compute(case)
    response = api(case).get(ROOT + "/candidates/" + candidates[0] + "/comparison", query_string={
        "range_start": "2026-09-09T00:00:00", "range_end": "2026-09-26T00:00:00"})
    assert response.status_code == 413, response.get_json()
    assert response.get_json()["error"]["code"] == "query_too_large"


def test_candidate_comparison_rejects_invalid_snapshot_before_read_admission(dashboard_case, monkeypatch):
    from contextlib import contextmanager

    from web.routes.workbench.read_budget import PLAN_READ_SLOTS

    admitted = []

    @contextmanager
    def slot():
        admitted.append(True)
        yield

    monkeypatch.setattr(PLAN_READ_SLOTS, "slot", slot)
    response = api(dashboard_case).get(ROOT + "/candidates/" + "a" * 48 + "/comparison", query_string={
        "range_start": "2026-09-09T00:00:00", "range_end": "2026-09-26T00:00:00", "snapshot_ref": "invalid"})
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"
    assert admitted == []


def test_read_budget_replaces_only_queued_requests_from_the_same_nonempty_lane():
    from concurrent.futures import ThreadPoolExecutor

    from core.models.workbench_command import WorkbenchCommandRejected
    from web.routes.workbench.read_budget import ReadBudget

    budget, acquired = ReadBudget(1), []

    def read(name, lane):
        with budget.slot(lane=lane):
            acquired.append(name)

    def queued(lanes):
        with budget._condition:
            assert budget._condition.wait_for(lambda: [waiter.lane for waiter in budget._waiting] == lanes, timeout=5)

    with ThreadPoolExecutor(max_workers=5) as workers:
        with budget.slot(lane="page-a"):
            old = workers.submit(read, "old", "page-a")
            queued(["page-a"])
            other = workers.submit(read, "other", "page-b")
            queued(["page-a", "page-b"])
            untagged = workers.submit(read, "untagged", None)
            queued(["page-a", "page-b", None])
            empty = workers.submit(read, "empty", "")
            queued(["page-a", "page-b", None, ""])
            latest = workers.submit(read, "latest", "page-a")
            queued(["page-b", None, "", "page-a"])
            with pytest.raises(WorkbenchCommandRejected) as rejected:
                old.result(timeout=5)
            assert rejected.value.code == "request_superseded" and rejected.value.status == 499
            assert acquired == [] and budget._available == 0
        for future in (other, untagged, empty, latest):
            future.result(timeout=5)
    assert acquired == ["other", "untagged", "empty", "latest"]
    assert budget._available == 1 and not budget._waiting


def test_dashboard_read_lane_is_used_only_for_list_admission(dashboard_case, monkeypatch):
    from contextlib import contextmanager

    from web.routes.workbench.read_budget import PLAN_READ_SLOTS

    original, lanes = PLAN_READ_SLOTS.slot, []

    @contextmanager
    def slot(lane=None):
        lanes.append(lane)
        with original(lane=lane):
            yield

    monkeypatch.setattr(PLAN_READ_SLOTS, "slot", slot)
    client = api(dashboard_case)
    listed = client.get(ROOT, headers={"X-Workbench-Read-Lane": "dashboard-page-a"})
    assert listed.status_code == 200
    body = listed.get_json()
    item = body["data"]["items"][0]
    path = ROOT + "/items/" + item["item_ref"]
    detail = client.get(path, query_string={"snapshot_ref": body["meta"]["snapshot_ref"]},
                        headers={"X-Workbench-Read-Lane": "dashboard-page-a"})
    assert detail.status_code == 200 and lanes == ["dashboard-page-a", None]
    response = client.post(path + "/transition", json={"request_key": "dashboard-lane-command-01",
        "write_token": item["write_context"]["write_token"], "input": follow()},
        headers={"X-Workbench-Read-Lane": "dashboard-page-a"})
    assert response.status_code == 200, response.get_json()
    assert len(lanes) > 2 and all(lane is None for lane in lanes[2:])


def test_dashboard_materializes_only_page_and_detail_facts_without_changing_snapshot(dashboard_case, monkeypatch):
    from core.models.workbench_dashboard import DashboardQuery
    from core.services.workbench.dashboard import service
    from tests.workbench.dashboard_support import NOW

    reader = service.WorkbenchDashboardService(dashboard_case.conn)
    with reader.read_snapshot():
        sources = reader.load(NOW)
    calls = []
    original_decorate = service.WorkbenchDashboardService._decorate
    original_materialize = service.WorkbenchDashboardService._materialize_item

    def decorate(self, item, saved, identity, now):
        result = original_decorate(self, item, saved, identity, now)
        calls.append(set(result["_guard"]))
        return result

    def materialize_item(item):
        is_new = "_snapshot" not in item
        original_materialize(item)
        if is_new:
            calls.append(set(item["_snapshot"]))

    monkeypatch.setattr(service.WorkbenchDashboardService, "_decorate", decorate)
    monkeypatch.setattr(service.WorkbenchDashboardService, "_materialize_item", staticmethod(materialize_item))
    data = reader.project(sources)
    assert len(data["items"]) > 1 and all("_facts" not in item and "_snapshot" not in item for item in data["items"])
    assert len(calls) == len(data["items"]) and all("facts" not in value and "source_revision" in value for value in calls)
    for item in data["items"]:
        expected = {
            "source_state": item["source_state"],
            "source_revision": item["_guard"]["source_revision"],
            "identity": item["_guard"]["identity"],
            "revision": item["_guard"]["revision"],
            "source": item["source"],
            "risk": item["risk"],
            "handling": item["_handling"],
        }
        assert item["_guard"] == expected
    guard_calls = len(calls)
    public = reader.workspace(data, DashboardQuery(size=1))
    assert len(public["items"]) == 1 and len(calls) == guard_calls + 1
    item = next(item for item in data["items"] if "_snapshot" in item)
    snapshot = item["_snapshot"]
    assert snapshot is item["_guard"] and snapshot["source"] is item["_guard"]["source"]
    reader.public_item(item)
    assert item["_snapshot"] is snapshot and len(calls) == guard_calls + 1
    untouched = next(item for item in data["items"] if "_snapshot" not in item)
    detail = reader.detail(data, untouched["item_ref"])
    assert detail is untouched and "_snapshot" in detail and len(calls) == guard_calls + 2


def test_dashboard_analysis_reuses_streamed_pressure_without_retaining_calendar_geometry(dashboard_case, monkeypatch):
    from collections import Counter

    from core.models.workbench_dashboard import DashboardAnalysisQuery
    from core.services.workbench.dashboard import calendar_capture
    from core.services.workbench.dashboard.service import WorkbenchDashboardService
    from tests.workbench.dashboard_support import NOW

    case = dashboard_case
    case.conn.execute("UPDATE SchemaVersion SET version=33 WHERE id=1")
    case.conn.commit()
    original, calls = calendar_capture.calendar_from_sources, Counter()
    index_type, indexes = calendar_capture.ResourceTaskIndex, []

    def resource_task_index(*args, **kwargs):
        index = index_type(*args, **kwargs)
        indexes.append(index)
        return index

    def calendar_factory(*args, **kwargs):
        factory = original(*args, **kwargs)
        assert factory is not None
        stream = factory.iter_resources

        def tracked(resources, start, end):
            for resource in resources:
                calls[resource["kind"], resource["ref"]] += 1
            yield from stream(resources, start, end)

        monkeypatch.setattr(factory, "iter_resources", tracked)
        return factory

    monkeypatch.setattr(calendar_capture, "calendar_from_sources", calendar_factory)
    # Capture and analysis share one metrics object; the only index constructor is in calendar_capture.
    monkeypatch.setattr(calendar_capture, "ResourceTaskIndex", resource_task_index)
    reader = WorkbenchDashboardService(case.conn)
    with reader.read_snapshot():
        sources = reader.load(NOW)
    facts = sources.facts.project()
    metrics = facts.pressure_metrics
    assert metrics is not None
    captured = facts.snapshot_contents()
    assert len(calls) == len(metrics.summaries) == 2 and set(calls.values()) == {1}
    assert len(indexes) == 1 and indexes[0] is metrics.index
    index = indexes[0]
    assert index.retain_statistics_values is False
    assert index._measurements == {}
    assert "resource_pressure" not in facts.raw
    assert "resources" not in facts.pressure
    assert facts.pressure["state"] == facts.pressure["calendar_state"] == "available"
    assert metrics.factory is not None and metrics.factory.source["schema_version"] == 33

    def no_geometry(value):
        if isinstance(value, dict):
            assert not value.get("days") and "windows" not in value
            for nested in value.values():
                no_geometry(nested)
        elif isinstance(value, (list, tuple)):
            for nested in value:
                no_geometry(nested)

    no_geometry(metrics.summaries)
    overview = reader.analysis(sources, DashboardAnalysisQuery("pressure", size=100))
    assert set(calls.values()) == {1}
    # A resource the capture stream did not summarize is projected once on demand.
    missed = next(iter(metrics.summaries))
    monkeypatch.delitem(metrics.summaries, missed)
    repeated = reader.analysis(sources, DashboardAnalysisQuery("pressure", size=100))
    assert repeated == overview and calls[missed] == 2
    assert all(count == (2 if key == missed else 1) for key, count in calls.items())
    resource = next(row for row in overview["resources"] if row["resource_ref"] == missed[1])
    detailed = reader.analysis(sources, DashboardAnalysisQuery("resource_days", resource_ref=missed[1], size=100))
    assert detailed["resources"][0]["window_metrics"] == resource["window_metrics"]
    assert detailed["resources"][0]["days"] and calls[missed] == 3
    assert len(indexes) == 1 and indexes[0] is metrics.index
    assert index.retain_statistics_values is False
    assert index._measurements == {}
    no_geometry(metrics.summaries)
    assert facts.snapshot_contents() == captured


@pytest.mark.parametrize("early_source", ["external", "internal"])
def test_plan_without_resource_cohort_beyond_calendar_window_keeps_analysis_readable(dashboard_case, early_source):
    from core.models.workbench_dashboard import DashboardAnalysisQuery
    from core.services.workbench.dashboard.service import WorkbenchDashboardService
    from tests.workbench.dashboard_support import NOW

    case = dashboard_case
    case.conn.execute("UPDATE BatchOperations SET source='external', op_type_id=NULL, op_type_name='Plating' WHERE id=?", (case.op,))
    early = case.conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name,source,unit_hours,setup_hours) "
                              "VALUES ('DOP0','DB1',2,'Plating',?,0,0)", (early_source,)).lastrowid
    case.conn.execute(
        "UPDATE Schedule SET source='external', op_type_ref=NULL, op_type_label='Plating', op_type_name='Plating' "
        "WHERE version=1 AND op_id=?",
        (case.op,),
    )
    update_schedule_rows(
        case.conn, 1, machine_id=None, operator_id=None,
        start_time="2026-09-09T08:00:00", end_time="2026-09-11T08:00:00", sync_history=False,
    )
    insert_schedule_row(
        case.conn, 1, early, "2010-01-04T08:00:00", "2010-01-06T08:00:00",
        machine_id=None, operator_id=None,
    )
    case.conn.commit()
    reader = WorkbenchDashboardService(case.conn)
    with reader.read_snapshot():
        sources = reader.load(NOW)
    assert sources.facts.pressure["calendar_state"] == "unavailable"
    assert sources.facts.pressure_metrics is not None and sources.facts.pressure_metrics.factory is None
    first = reader.analysis(sources, DashboardAnalysisQuery("overview"))
    # The over-wide window only bounds per-resource calendar geometry. Without a resource
    # cohort nothing is projected, yet an internal task missing both identities still counts.
    assert first["state"] == "available" and first["resource_common"]["cohort"] == []
    assert sources.facts.pressure_metrics is not None and sources.facts.pressure_metrics._index is None
    gaps = 1 if early_source == "internal" else 0
    for kind in ("machine", "operator"):
        assert first["resource_common"][kind]["unknown_workload_count"] == gaps
    assert reader.analysis(sources, DashboardAnalysisQuery("overview")) == first


def test_material_item_keeps_the_admitted_daily_total_beyond_one_entry_bound(dashboard_case):
    # 需求量、库存、到料各自是单条存储值（上界 2^53-1）；当日可用量是合计，不再套单条上界被洗成未知。
    case = dashboard_case
    largest = (1 << 53) - 1
    requirement = case.conn.execute("SELECT id FROM BatchMaterials WHERE batch_id='DB1'").fetchone()[0]
    case.conn.execute("UPDATE BatchMaterials SET required_qty=1, available_qty=? WHERE id=?", (largest, requirement))
    case.conn.execute("INSERT INTO BatchMaterialReviews(requirement_id,batch_quantity) VALUES (?,2)", (requirement,))
    case.conn.execute("INSERT INTO BatchMaterialArrivals(requirement_id,arrival_date,quantity) VALUES (?,?,?)",
                      (requirement, "2026-09-10", largest))
    case.conn.commit()
    response = api(case).get(ROOT)
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    material = data["categories"]["material"]
    # 齐套无缺口不是风险，不进列表；合计被洗成未知时这里会是 unknown_count=1、risk_count=None、readiness_unknown。
    assert (material["assessed_count"], material["unknown_count"], material["risk_count"], material["evaluation_gaps"]) == (1, 0, 0, [])
    assert "material" not in {row["category"] for row in data["items"]}


def test_reviewed_batch_quantity_change_reports_material_review_required_issue(dashboard_case):
    dashboard_case.command(dashboard_case.item("material"), follow())
    req_id = dashboard_case.conn.execute("SELECT id FROM BatchMaterials WHERE batch_id='DB1'").fetchone()[0]
    dashboard_case.conn.execute(
        "INSERT INTO BatchMaterialReviews(requirement_id,batch_quantity) VALUES (?,2)",
        (req_id,),
    )
    dashboard_case.conn.execute("UPDATE Batches SET quantity=5, ready_status='yes' WHERE batch_id='DB1'")
    dashboard_case.conn.commit()
    item = dashboard_case.item("material")
    assert [row["code"] for row in item["source"]["readiness_issues"]] == ["material_review_required"]


def test_per_item_source_revision_guards_remark_review_and_downtime_mutations(dashboard_case):
    from core.models.workbench_command import WorkbenchCommandRejected
    from core.services.workbench.execution.production_report import WorkbenchProductionReportService
    from tests.workbench.dashboard_support import NOW

    case = dashboard_case
    created = case.report()["data"]["rows"][0]
    items = {row["category"]: row for row in case.read()[0]["items"]}

    # 1. Modifying only a production report's remark invalidates the actual item's write_token,
    #    while unrelated categories (e.g. material) stay unaffected.
    WorkbenchProductionReportService(case.conn, clock=lambda: NOW).execute(
        "correct",
        created["report_ref"],
        {
            "remark": "remark-only update",
            "original_revision_ref": created["revision_ref"],
            "reason": "Clarify operator note",
            "declared_operator": "Foreman",
        },
        request_key="dashboard-report-remark-only-01",
        validate_context=lambda *_: None,
    )
    with pytest.raises(WorkbenchCommandRejected) as stale_actual:
        case.command(items["actual"], follow(), key="dashboard-stale-actual-remark-01")
    assert stale_actual.value.code == "stale_write"
    assert case.command(items["material"], follow(), key="dashboard-material-unaffected-01")["result"] == "committed"

    # 2. Adjusting a material review row invalidates the material item's write_token.
    material_item = case.item("material")
    req_id = case.conn.execute("SELECT id FROM BatchMaterials WHERE batch_id='DB1'").fetchone()[0]
    case.conn.execute("INSERT INTO BatchMaterialReviews(requirement_id,batch_quantity) VALUES (?,2)", (req_id,))
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as stale_material:
        case.command(material_item, follow(remark="After review tweak"), key="dashboard-stale-material-review-01")
    assert stale_material.value.code == "stale_write"

    # 3. Updating a non-overlapping downtime on the same machine invalidates the downtime item's write_token.
    afternoon = (datetime_to_us(datetime(2026, 9, 9, 15)), datetime_to_us(datetime(2026, 9, 9, 16)))
    case.conn.execute(
        "INSERT INTO MachineDowntimes(machine_id,start_time,end_time,start_us,end_us,reason_code,reason_detail) "
        "VALUES ('DM1','2026-09-09 15:00:00','2026-09-09 16:00:00',?,?,'maintenance','Initial note')",
        afternoon,
    )
    case.conn.commit()
    downtime_item = case.item("downtime")
    case.conn.execute("UPDATE MachineDowntimes SET reason_detail='Updated note' WHERE start_us=?", (afternoon[0],))
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as stale_downtime:
        case.command(downtime_item, follow(), key="dashboard-stale-downtime-update-01")
    assert stale_downtime.value.code == "stale_write"


def test_transition_reads_only_single_item_closure_across_all_five_categories(external_handling_case, monkeypatch):
    from core.services.workbench.dashboard import facts as facts_module
    from core.services.workbench.execution.ledger import ExecutionLedgerService
    from tests.workbench.dashboard_support import connect

    case = external_handling_case
    # Add an unrelated scheduled internal operation so any whole-plan execution load would read >1 operations.
    extra_op = case.conn.execute(
        "INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,unit_hours,setup_hours) "
        "VALUES ('DOP2','DB1',2,'DT1','Turning','internal',1.0,0)"
    ).lastrowid
    assert extra_op is not None
    insert_schedule_row(
        case.conn,
        1,
        extra_op,
        "2026-09-09T13:00:00",
        "2026-09-09T14:00:00",
        machine_id="DM1",
        operator_id="DO1",
    )
    case.conn.commit()
    case.register(index=1)

    sql_log = []

    def traced_connect(path):
        conn = connect(path)
        conn.set_trace_callback(sql_log.append)
        return conn

    client = api(case, connect_factory=traced_connect)
    listed = client.get(ROOT)
    assert listed.status_code == 200, listed.get_json()
    by_category = {}
    for row in listed.get_json()["data"]["items"]:
        by_category.setdefault(row["category"], row)
    assert set(by_category) == {"delivery", "material", "actual", "downtime", "external"}

    loaded_op_counts = []
    orig_ledger_load = ExecutionLedgerService.load

    def tracked_ledger_load(self, scope, operation_refs, **kwargs):
        loaded_op_counts.append(len(list(operation_refs)))
        return orig_ledger_load(self, scope, operation_refs, **kwargs)

    def patch_command_only(mp):
        mp.setattr(
            facts_module,
            "capture_resource_pressure",
            lambda *args, **kwargs: pytest.fail("Command unexpectedly captured resource pressure"),
        )
        mp.setattr(
            facts_module,
            "candidate_catalog",
            lambda *args, **kwargs: pytest.fail("Command unexpectedly loaded candidate catalog"),
        )
        mp.setattr(
            facts_module.DashboardFacts,
            "_load_sources",
            lambda *args, **kwargs: pytest.fail("Command unexpectedly loaded the full dashboard sources"),
        )
        mp.setattr(ExecutionLedgerService, "load", tracked_ledger_load)

    queries_by_category = {}
    with monkeypatch.context() as cmd_patch:
        patch_command_only(cmd_patch)
        for idx, category_name in enumerate(("delivery", "material", "actual", "downtime", "external"), start=1):
            item = by_category[category_name]
            sql_log.clear()
            resp = client.post(
                ROOT + "/items/" + item["item_ref"] + "/transition",
                json={
                    "request_key": f"dashboard-scoped-transition-{category_name}-{idx:02d}",
                    "write_token": item["write_context"]["write_token"],
                    "input": follow(),
                },
            )
            assert resp.status_code == 200, (category_name, resp.get_json())
            assert resp.get_json()["result"] == "committed"
            queries_by_category[category_name] = [
                " ".join(stmt.upper().replace('"', "").split())
                for stmt in sql_log
                if stmt.lstrip().upper().startswith("SELECT")
            ]

    for category_name in ("material", "external"):
        selects = queries_by_category[category_name]
        assert not any("FROM SCHEDULE " in stmt or stmt.endswith("FROM SCHEDULE") for stmt in selects), (
            category_name,
            selects,
        )
        assert not any("WORKBENCHPRODUCTIONREPORTS" in stmt for stmt in selects), (category_name, selects)
        assert not any("WORKCALENDAR" in stmt for stmt in selects), (category_name, selects)

    assert loaded_op_counts == [1]

    # Retained items under unavailable batch identity also commit cleanly with 0 stale_write false positives.
    case.conn.execute("UPDATE WorkbenchEntityRefs SET active=0 WHERE kind='batch' AND entity_key='DB1'")
    case.conn.commit()
    degraded = client.get(ROOT)
    assert degraded.status_code == 200, degraded.get_json()
    degraded_items = {row["item_ref"]: row for row in degraded.get_json()["data"]["items"]}
    with monkeypatch.context() as cmd_patch:
        patch_command_only(cmd_patch)
        for category_name in ("delivery", "material", "actual", "downtime"):
            retained = degraded_items[by_category[category_name]["item_ref"]]
            assert retained["source_state"] == "not_currently_evaluated"
            resp = client.post(
                ROOT + "/items/" + retained["item_ref"] + "/transition",
                json={
                    "request_key": f"dashboard-degraded-transition-{category_name}",
                    "write_token": retained["write_context"]["write_token"],
                    "input": follow(remark="Retained after identity_missing"),
                },
            )
            assert resp.status_code == 200, (category_name, resp.get_json())
            assert resp.get_json()["result"] == "committed"


def test_sibling_batch_invalidation_keeps_healthy_items_current_and_retained_delivery_avoids_other_batches(
    dashboard_case, monkeypatch
):
    from tests.workbench.dashboard_support import connect
    from tests.workbench.execution_ledger_support import publish_official_plan

    case = dashboard_case
    case.conn.execute(
        "INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date,ready_status) "
        "VALUES ('DB2','DP1','Part 2',2,'2026-09-08','no')"
    )
    db2_op = case.conn.execute(
        "INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,unit_hours,setup_hours) "
        "VALUES ('DOP-DB2-1','DB2',1,'DT1','Turning','internal',1.0,0)"
    ).lastrowid
    db2_deferred_op = case.conn.execute(
        "INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,unit_hours,setup_hours) "
        "VALUES ('DOP-DB2-2','DB2',2,'DT1','Turning','internal',1.0,0)"
    ).lastrowid
    assert db2_op is not None and db2_deferred_op is not None
    case.conn.execute(
        "INSERT INTO BatchMaterials(batch_id,material_id,required_qty,available_qty,ready_status) "
        "VALUES ('DB2','DMAT',5,1,'no')"
    )
    insert_schedule_row(
        case.conn,
        1,
        db2_op,
        "2026-09-09T13:00:00",
        "2026-09-09T15:00:00",
        machine_id="DM1",
        operator_id="DO1",
    )
    case.conn.commit()

    sql_log = []

    def traced_connect(path):
        conn = connect(path)
        conn.set_trace_callback(sql_log.append)
        return conn

    client = api(case, connect_factory=traced_connect)
    initial = client.get(ROOT)
    assert initial.status_code == 200, initial.get_json()
    db1_items = {
        row["category"]: row
        for row in initial.get_json()["data"]["items"]
        if row["subject"].startswith("DB1 · ")
    }
    assert set(db1_items) == {"delivery", "material", "actual", "downtime"}

    for idx, category_name in enumerate(("delivery", "material", "actual", "downtime"), start=1):
        item = db1_items[category_name]
        resp = client.post(
            ROOT + "/items/" + item["item_ref"] + "/transition",
            json={
                "request_key": f"dashboard-db1-initial-{category_name}-{idx:02d}",
                "write_token": item["write_context"]["write_token"],
                "input": follow(),
            },
        )
        assert resp.status_code == 200, (category_name, resp.get_json())
        assert resp.get_json()["result"] == "committed"

    # Invalidate sibling batch DB2: top-level plan becomes None/unavailable,
    # while DB1's four items remain "current" in both GET /dashboard and POST /transition.
    case.conn.execute("UPDATE WorkbenchEntityRefs SET active=0 WHERE kind='batch' AND entity_key='DB2'")
    case.conn.commit()

    listed = client.get(ROOT)
    assert listed.status_code == 200, listed.get_json()
    data = listed.get_json()["data"]
    assert data["plan"] is None
    assert data["analysis"]["plan"] is None and data["analysis"]["state"] == "unavailable"
    for category_name in ("delivery", "material", "actual", "downtime"):
        assert data["categories"][category_name]["state"] == "unavailable"

    listed_by_ref = {row["item_ref"]: row for row in data["items"]}
    for idx, category_name in enumerate(("delivery", "material", "actual", "downtime"), start=1):
        current_item = listed_by_ref[db1_items[category_name]["item_ref"]]
        assert current_item["source_state"] == "current", (category_name, current_item)
        resp = client.post(
            ROOT + "/items/" + current_item["item_ref"] + "/transition",
            json={
                "request_key": f"dashboard-db1-sibling-dead-{category_name}-{idx:02d}",
                "write_token": current_item["write_context"]["write_token"],
                "input": follow(remark=f"Updated while DB2 inactive ({category_name})"),
            },
        )
        assert resp.status_code == 200, (category_name, resp.get_json())
        assert resp.get_json()["result"] == "committed"

    # Restore DB2 and publish plan v2 containing only DB2 (plus a deferred DB2 operation),
    # leaving DB1's handled delivery item retained outside the current official plan.
    case.conn.execute("UPDATE WorkbenchEntityRefs SET active=1 WHERE kind='batch' AND entity_key='DB2'")
    publish_official_plan(
        case.conn,
        2,
        [
            {
                "op_id": db2_op,
                "machine_id": "DM1",
                "operator_id": "DO1",
                "start_time": "2026-09-09T13:00:00",
                "end_time": "2026-09-09T15:00:00",
            }
        ],
        adopted_at="2026-09-08T18:00:00",
    )
    case.conn.execute(
        "UPDATE ScheduleHistory SET deferred_operation_ids_json=? WHERE version=2",
        (json.dumps([db2_deferred_op]),),
    )
    case.conn.commit()

    after_v2 = client.get(ROOT)
    assert after_v2.status_code == 200, after_v2.get_json()
    retained_delivery = next(
        row
        for row in after_v2.get_json()["data"]["items"]
        if row["item_ref"] == db1_items["delivery"]["item_ref"]
    )
    assert retained_delivery["source_state"] == "not_currently_evaluated"

    sql_log.clear()
    resp = client.post(
        ROOT + "/items/" + retained_delivery["item_ref"] + "/transition",
        json={
            "request_key": "dashboard-db1-retained-delivery-no-db2-01",
            "write_token": retained_delivery["write_context"]["write_token"],
            "input": follow(remark="Retained delivery outside v2 without touching DB2"),
        },
    )
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["result"] == "committed"

    select_trace = [
        " ".join(stmt.replace('"', "").split())
        for stmt in sql_log
        if stmt.lstrip().upper().startswith("SELECT")
    ]
    assert select_trace
    assert all("DB2" not in stmt for stmt in select_trace), select_trace
    assert not any("FROM BATCHES" in stmt.upper() for stmt in select_trace), select_trace
    assert all(
        "DB1" in stmt
        for stmt in select_trace
        if "FROM BATCHOPERATIONS" in stmt.upper()
    ), select_trace
