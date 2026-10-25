"""Isolated route registration and real HTTP command/read snapshots."""

import csv
import json
import subprocess
from io import StringIO
from pathlib import Path

import pytest

from tests.workbench.dashboard_external_handling_support import (
    external_handling_case as external_handling_fixture,  # noqa: F401
)
from tests.workbench.dashboard_external_support import external_case as external_fixture  # noqa: F401
from tests.workbench.dashboard_support import api, follow  # noqa: F401
from tests.workbench.dashboard_support import dashboard_case as dashboard_fixture  # noqa: F401
from tests.workbench.node_runtime_support import node_runtime
from tests.workbench.point_downstream_support import ACTUAL, app_for, read
from tests.workbench.run_candidate_support import candidate_case as candidate_fixture  # noqa: F401
from tests.workbench.run_candidate_support import corrupt_update

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


def storage_invalid(response):
    body = response.get_json()
    assert response.status_code == 409, body
    assert body["error"]["code"] == "dashboard_storage_invalid", body


@pytest.mark.parametrize("origin_json", ("{not json", "[]", "null"))
def test_stored_origin_that_is_not_a_json_object_is_storage_invalid(dashboard_case, monkeypatch, origin_json):
    client = api(dashboard_case, monkeypatch)
    item = dashboard_case.item()
    assert dashboard_case.command(item, follow())["result"] == "committed"
    assert client.get(ROOT).status_code == 200
    corrupt_update(dashboard_case.conn, "WorkbenchDashboardStates",
                   "UPDATE WorkbenchDashboardStates SET origin_json=? WHERE item_ref=?", (origin_json, item["item_ref"]))
    storage_invalid(client.get(ROOT))


@pytest.mark.parametrize("source", ([], None, "outsourcing"))
def test_stored_external_origin_source_that_is_not_an_object_is_storage_invalid(external_handling_case, monkeypatch, source):
    case = external_handling_case
    case.register()
    item = case.item("external")
    assert case.command(item, follow())["result"] == "committed"
    client = api(case, monkeypatch)
    assert client.get(ROOT).status_code == 200
    table = "WorkbenchDashboardExternalStates"
    origin = json.loads(case.conn.execute("SELECT origin_json FROM " + table + " WHERE item_ref=?",
                                          (item["item_ref"],)).fetchone()[0])
    assert type(origin["source"]) is dict
    corrupt_update(case.conn, table, "UPDATE " + table + " SET origin_json=? WHERE item_ref=?",
                   (json.dumps(dict(origin, source=source)), item["item_ref"]))
    storage_invalid(client.get(ROOT))


@pytest.mark.parametrize("source", ([], None, "planned_delivery"))
def test_stored_dashboard_origin_source_that_is_not_an_object_is_storage_invalid(dashboard_case, monkeypatch, source):
    case = dashboard_case
    item = case.item()
    assert case.command(item, follow())["result"] == "committed"
    client = api(case, monkeypatch)
    assert client.get(ROOT).status_code == 200
    table = "WorkbenchDashboardStates"
    origin = json.loads(case.conn.execute("SELECT origin_json FROM " + table + " WHERE item_ref=?",
                                          (item["item_ref"],)).fetchone()[0])
    assert type(origin["source"]) is dict
    corrupt_update(case.conn, table, "UPDATE " + table + " SET origin_json=? WHERE item_ref=?",
                   (json.dumps(dict(origin, source=source)), item["item_ref"]))
    storage_invalid(client.get(ROOT))
    # 记录退出当前计划后只能靠原记录生成导航，坏 source 也必须按存储损坏拒绝而不是 500。
    case.conn.execute("UPDATE WorkbenchEntityRefs SET active=0 WHERE kind='batch' AND entity_key='DB1'")
    case.conn.commit()
    storage_invalid(client.get(ROOT))


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


def test_candidate_comparison_rejects_invalid_snapshot_before_read_admission(dashboard_case, monkeypatch):
    from contextlib import contextmanager

    from web.routes.workbench.read_budget import PLAN_READ_SLOTS

    admitted = []

    @contextmanager
    def slot():
        admitted.append(True)
        yield

    monkeypatch.setattr(PLAN_READ_SLOTS, "slot", slot)
    response = api(dashboard_case, monkeypatch).get(ROOT + "/candidates/" + "a" * 48 + "/comparison", query_string={
        "range_start": "2026-09-09T00:00:00", "range_end": "2026-09-26T00:00:00", "snapshot_ref": "invalid"})
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"
    assert admitted == []


@pytest.mark.parametrize("endpoint, reader_name", [("/analysis", "read_dashboard_analysis"),
                                                   ("/candidates/" + "a" * 48 + "/comparison", "read_candidate_comparison")])
def test_dashboard_analysis_envelopes_never_return_nonfinite_json(dashboard_case, monkeypatch, endpoint, reader_name):
    import web.routes.workbench.dashboard_analysis as module

    monkeypatch.setattr(module, reader_name, lambda *args, **kwargs: (
        {"as_of": "2026-09-10T12:00:00", "unserializable_number": float("nan")}, "fault-snapshot"))
    response = api(dashboard_case, monkeypatch).get(ROOT + endpoint)
    assert response.status_code == 500
    body = response.get_json()
    assert body["ok"] is False and body["committed"] is False
    assert body["error"]["code"] == "storage_failure"
    assert b"NaN" not in response.data


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
    client = api(dashboard_case, monkeypatch)
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

    reader = service.WorkbenchDashboardService(dashboard_case.conn, clock=lambda: NOW)
    with reader.read_snapshot():
        sources = reader.load()
    original, calls = service.typed, []

    def typed(value):
        calls.append(value)
        return original(value)

    monkeypatch.setattr(service, "typed", typed)
    data = reader.project(sources)
    assert len(data["items"]) > 1 and all("_snapshot" not in item for item in data["items"])
    assert len(calls) == len(data["items"]) and all("facts" not in value for value in calls)
    legacy_guards = []
    for item in data["items"]:
        snapshot = original({"facts": original(item["_facts"]), "source_state": item["source_state"],
            "identity": item["_guard"]["identity"], "revision": item["_guard"]["revision"],
            "source": item["source"], "risk": item["risk"], "handling": item["_handling"]})
        legacy_guards.append((item["item_ref"], {key: value for key, value in snapshot.items() if key != "facts"}))
    expected = sources.facts.snapshot_contents(view={"stored": sources.stored,
        "external_stored": sources.external[2], "items": legacy_guards})
    assert data["snapshot_contents"] == expected
    guard_calls = len(calls)
    public = reader.workspace(data, DashboardQuery(size=1))
    assert len(public["items"]) == 1 and len(calls) == guard_calls + 1
    item = next(item for item in data["items"] if "_snapshot" in item)
    snapshot = item["_snapshot"]
    assert snapshot["facts"] is item["_facts"] and snapshot["source"] is item["_guard"]["source"]
    reader.public_item(item)
    assert item["_snapshot"] is snapshot and len(calls) == guard_calls + 1
    untouched = next(item for item in data["items"] if "_snapshot" not in item)
    detail = reader.detail(data, untouched["item_ref"])
    assert detail is untouched and "_snapshot" in detail and len(calls) == guard_calls + 2
    assert data["snapshot_contents"] == expected


def test_dashboard_analysis_reuses_streamed_pressure_without_retaining_calendar_geometry(dashboard_case, monkeypatch):
    from collections import Counter

    from core.models.workbench_dashboard import DashboardAnalysisQuery
    from core.services.workbench.dashboard import analysis_projection, calendar_capture
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
    monkeypatch.setattr(calendar_capture, "ResourceTaskIndex", resource_task_index)
    monkeypatch.setattr(analysis_projection, "ResourceTaskIndex", resource_task_index)
    reader = WorkbenchDashboardService(case.conn, clock=lambda: NOW)
    with reader.read_snapshot():
        sources = reader.load()
    facts = sources.facts.project()
    captured = facts.snapshot_contents()
    assert len(calls) == len(facts._resource_pressure_cache) == 2 and set(calls.values()) == {1}
    assert len(indexes) == 1 and indexes[0] is facts._resource_pressure_index
    index = indexes[0]
    assert index.retain_statistics_values is False
    assert index._measurements == {}
    assert facts.raw["resource_pressure"]["calendar"]["resources"] is None
    assert facts.raw["resource_pressure"]["occupancy"] is None
    assert "_resource_pressure_cache" not in facts.raw

    def no_geometry(value):
        if isinstance(value, dict):
            assert not value.get("days") and "windows" not in value
            for nested in value.values():
                no_geometry(nested)
        elif isinstance(value, (list, tuple)):
            for nested in value:
                no_geometry(nested)

    no_geometry(facts._resource_pressure_cache)
    overview = reader.analysis(sources, DashboardAnalysisQuery("pressure", size=100))
    assert set(calls.values()) == {1}
    missed = next(iter(facts._resource_pressure_cache))
    facts._resource_pressure_cache.pop(missed)
    repeated = reader.analysis(sources, DashboardAnalysisQuery("pressure", size=100))
    assert repeated == overview and calls[missed[:2]] == 2
    assert all(count == (2 if key == missed[:2] else 1) for key, count in calls.items())
    resource = next(row for row in overview["resources"] if row["resource_ref"] == missed[1])
    detailed = reader.analysis(sources, DashboardAnalysisQuery("resource_days", resource_ref=missed[1], size=100))
    assert detailed["resources"][0]["window_metrics"] == resource["window_metrics"]
    assert detailed["resources"][0]["days"] and calls[missed[:2]] == 3
    assert len(indexes) == 1 and indexes[0] is facts._resource_pressure_index
    assert index.retain_statistics_values is False
    assert index._measurements == {}
    no_geometry(facts._resource_pressure_cache)
    assert facts.snapshot_contents() == captured
