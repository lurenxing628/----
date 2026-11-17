"""Real archived candidates keep comparison identity, scope and exports aligned."""

import csv
import io
import json
from copy import deepcopy
from datetime import date, datetime
from typing import Any, Dict

import pytest
from openpyxl import load_workbook

from core.services.workbench.facts.candidate_read_source import read_candidate_source
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.run.decision import CORE_COVERAGE, CORE_METRIC_KEYS
from core.services.workbench.run.decision_export import write_run_decision_export
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.decision_export_oracle_support import check_overview_export_rows
from tests.workbench.run_candidate_support import BASE, api, compute, compute_two_objectives
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401
from tests.workbench.test_material_stage_release import add_requirement
from web.routes.workbench.navigation_boot import WorkbenchNavigationInvalid, read_navigation


def decision(client, run_ref, **query):
    response = client.get(BASE + "/runs/" + run_ref + "/decision", query_string=query)
    assert response.status_code == 200, response.get_json()
    assert response.headers["Cache-Control"] == "no-store"
    return response.get_json()


def decision_summary(client, run_ref, **query):
    response = client.get(BASE + "/runs/" + run_ref + "/decision/summary", query_string=query)
    assert response.status_code == 200, response.get_json()
    assert response.headers["Cache-Control"] == "no-store"
    return response.get_json()


def _assert_summary_matches_full(summary, full):
    shared = ("run", "scope", "capture_ref", "catalog_complete", "metric_definitions", "selection_basis",
              "recommendation", "difference_summary", "resource_cohort")
    assert set(summary) == set(shared) | {"candidates", "baseline"}
    assert "completion_groups" not in full
    assert "selection_basis" not in summary["recommendation"]
    for key in shared:
        assert summary[key] == full[key], key
    assert len(summary["candidates"]) == len(full["candidates"])
    for core, complete in zip(summary["candidates"], full["candidates"]):
        assert "evaluations" not in core and "evaluations" in complete
        expected = {**{key: value for key, value in complete.items() if key != "evaluations"},
                    "metrics": {key: complete["metrics"][key] for key in CORE_METRIC_KEYS},
                    "deltas": {key: complete["deltas"][key] for key in CORE_METRIC_KEYS},
                    "coverage": {key: complete["coverage"][key] for key in CORE_COVERAGE}}
        assert core == expected
    baseline = full["baseline"]
    if baseline["state"] == "selection_required":
        metrics, coverage = {}, {"schedulable": baseline["coverage"]["schedulable"]}
    else:
        metrics = {key: baseline["metrics"][key] for key in CORE_METRIC_KEYS}
        coverage = {key: baseline["coverage"][key] for key in CORE_COVERAGE}
    assert summary["baseline"] == {**baseline, "metrics": metrics, "coverage": coverage}


def test_all_real_candidates_share_reference_and_preserve_saved_selection(candidate_case):
    case = candidate_case
    case.batch("B2", due_date="2026-09-09", priority="urgent")
    case.operation("B2", unit_hours=2)
    case.conn.commit()
    run_ref, refs = compute(case, case.settings("B1", "B2"))
    client, _ = api(case)
    initial = decision(client, run_ref)["data"]
    compared = decision(client, run_ref, reference_candidate_ref=refs[-1], selected_candidate_ref=refs[0])["data"]
    summary = decision_summary(client, run_ref, reference_candidate_ref=refs[-1], selected_candidate_ref=refs[0])["data"]
    _assert_summary_matches_full(summary, compared)
    recommended_ref = compared["recommendation"]["candidate_ref"]
    same_reference = decision(client, run_ref,
        reference_candidate_ref=recommended_ref, selected_candidate_ref=refs[0])["data"]
    _assert_summary_matches_full(decision_summary(client, run_ref,
        reference_candidate_ref=recommended_ref, selected_candidate_ref=refs[0])["data"], same_reference)
    assert {row["candidate_ref"] for row in compared["candidates"]} == set(refs)
    assert 1 <= len(compared["candidates"]) <= 3
    assert compared["scope"]["reference"]["candidate_ref"] == refs[-1]
    assert compared["scope"]["selected_candidate_ref"] == refs[0]
    assert compared["scope"]["batch_count"] == initial["scope"]["batch_count"] == 2
    assert compared["scope"]["operation_count"] == initial["scope"]["operation_count"] == 2
    assert not {"batch_refs", "operation_refs"}.intersection(compared["scope"])
    assert compared["selection_basis"] == initial["selection_basis"]
    assert compared["recommendation"]["candidate_ref"] == initial["recommendation"]["candidate_ref"]
    basis = compared["selection_basis"]
    assert basis["target_objectives"] == ["min_overdue", "min_tardiness", "min_changeover"]
    assert set(basis["objective_winners"]) == set(basis["target_objectives"])
    assert all(winner in refs for winner in basis["objective_winners"].values())
    assert basis["objective_winners"][basis["primary_objective"]] == basis["selected_candidate_ref"]
    for row in compared["candidates"]:
        assert "algorithm_baseline" not in row["selection_role"]
    for entry in basis["explanation"]["entries"]:
        assert set(entry) == {"key", "label", "text", "state", "unit", "selected_value", "source", "scope"}
        assert entry["selected_value"] is None or type(entry["selected_value"]) in (int, float)
    recommendation = compared["recommendation"]
    assert recommendation["recommendation_version"] == "decision-recommendation-v1"
    assert recommendation["recommendation_type"] == "complete"
    assert recommendation["viewed_candidate_ref"] == refs[0]
    assert recommendation["candidate_ref"] == basis["selected_candidate_ref"]
    comparison = recommendation["current_comparison"]
    assert comparison["candidate_ref"] == recommendation["candidate_ref"]
    assert comparison["viewed_candidate_ref"] == refs[0]
    assert comparison["reference"]["candidate_ref"] == refs[-1]
    assert comparison["state"] == "available"
    assert len(comparison["all_differences"]) == len(compared["metric_definitions"]) == 52
    assert len(comparison["benefits"]) <= 3 and len(comparison["costs"]) <= 3
    assert recommendation["axes"]["preflight"] == {"state": "not_checked", "source": "existing_adoption_preview"}
    saved_recommended = next(row for row in compared["candidates"] if row["candidate_ref"] == recommendation["candidate_ref"])
    definitions = {row["key"]: row for row in compared["metric_definitions"]}
    for item in comparison["all_differences"]:
        assert item["metric_version"] == definitions[item["metric_key"]]["metric_version"]
        assert len(item["sample_compared_batch_refs"]) <= 3 and len(item["supporting_refs"]) <= 3
        if item["metric_key"] not in ("overdue_count", "total_tardiness_hours"):
            expected = saved_recommended["deltas"][item["metric_key"]]
            fields = ("value", "reference_value", "selected_value", "state", "direction")
            assert {key: item[key] for key in fields} == {key: expected[key] for key in fields}
        for support in item["supporting_refs"]:
            assert support["candidate_ref"] == recommendation["candidate_ref"]
            target = (comparison["reference"]["candidate_ref"] if support.get("side", "selected") == "reference"
                      and compared["scope"]["comparison_mode"] == "candidates" else recommendation["candidate_ref"])
            assert support["drill"]["candidate_ref"] == target
            assert support["drill"]["selected_candidate_ref"] == recommendation["candidate_ref"]
            assert support["drill"]["run_ref"] == run_ref
            if support["kind"] == "operation":
                assert support["drill"]["operation_ref"] == support["ref"]
                assert "comparison_tab" not in support["drill"] and "detail_query" not in support["drill"]
    reference = next(row for row in compared["candidates"] if row["candidate_ref"] == refs[-1])
    assert all(value["value"] == 0 for value in reference["deltas"].values() if value["state"] == "comparable")
    for row in compared["candidates"]:
        delta = row["deltas"]["makespan_hours"]
        assert delta["value"] == row["metrics"]["makespan_hours"]["value"] - reference["metrics"]["makespan_hours"]["value"]
        assert row["coverage"]["schedulable"]["missing_count"] == 0


def test_candidate_scope_and_window_errors_are_rejected_before_comparison(candidate_case):
    case = candidate_case
    first_ref, first_candidates = compute(case)
    accepted = case.accept(key="decision-second-run-0001")
    client, _ = api(case)
    pending = decision(client, accepted["run_ref"])["data"]
    pending_document = decision_summary(client, accepted["run_ref"])
    pending_summary = pending_document["data"]
    pending_snapshot = pending_document["meta"]["snapshot_ref"]
    _assert_summary_matches_full(pending_summary, pending)
    assert pending_summary["recommendation"]["state"] == "unavailable"
    assert pending_summary["baseline"]["state"] == "selection_required"
    assert pending_summary["baseline"]["metrics"] == {} and pending_summary["candidates"] == []
    explanation = pending_summary["selection_basis"]["explanation"]
    assert explanation["headline"] == "本次排产尚未保存推荐方案。"
    assert explanation["issues"] == []
    second = WorkbenchRunWorker(case.conn, clock=datetime.now).execute(accepted["run_ref"])
    second_candidate = second["candidates"][0]["candidate_ref"]
    completed_path = BASE + "/runs/" + second["run_ref"] + "/decision"
    stale = client.get(completed_path, query_string={"snapshot_ref": pending_snapshot})
    assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "snapshot_stale"
    refreshed = decision_summary(client, second["run_ref"])
    refreshed_snapshot = refreshed["meta"]["snapshot_ref"]
    full = decision(client, second["run_ref"], snapshot_ref=refreshed_snapshot)
    assert full["meta"]["snapshot_ref"] == refreshed_snapshot
    assert full["meta"]["as_of"] == refreshed["meta"]["as_of"]
    _assert_summary_matches_full(refreshed["data"], full["data"])
    path = BASE + "/runs/" + first_ref + "/decision"
    for query in ({"reference_candidate_ref": second_candidate}, {"selected_candidate_ref": second_candidate},
                  {"range_start": "2026-09-09T08:00:00"},
                  {"range_start": "2026-09-10T08:00:00", "range_end": "2026-09-09T08:00:00"}):
        for endpoint in (path, path + "/summary"):
            response = client.get(endpoint, query_string=query)
            assert response.status_code == 422, response.get_json()
            assert response.get_json()["ok"] is False
    valid = decision(client, first_ref, reference_candidate_ref=first_candidates[0],
                     range_start="2026-09-09T00:00:00", range_end="2026-09-12T00:00:00")["data"]
    assert valid["scope"]["range_start"] == "2026-09-09T00:00:00"
    assert valid["scope"]["range_end"] == "2026-09-12T00:00:00"


def test_overview_exports_require_the_screen_reference_snapshot(candidate_case):
    # Two real representatives keep the viewer and the screen reference distinct.
    run_ref, refs = compute_two_objectives(candidate_case)
    client, _ = api(candidate_case)

    document = decision(client, run_ref, reference_candidate_ref=refs[-1], selected_candidate_ref=refs[0])
    summary = decision_summary(client, run_ref, reference_candidate_ref=refs[-1], selected_candidate_ref=refs[0])
    data, snapshot = document["data"], summary["meta"]["snapshot_ref"]
    _assert_summary_matches_full(summary["data"], data)
    query = {"reference_candidate_ref": refs[-1], "selected_candidate_ref": refs[0], "snapshot_ref": snapshot}
    path = BASE + "/runs/" + run_ref + "/decision/export"
    count = len(data["candidates"]) * len(data["metric_definitions"])
    for fmt in ("csv", "xlsx"):
        response = client.get(path, query_string=dict(query, format=fmt, section="overview"))
        assert response.status_code == 200, response.get_data(as_text=True) if fmt == "csv" else response.status_code
        assert response.headers["X-Workbench-Run-Ref"] == run_ref
        assert response.headers["X-Workbench-Snapshot-Ref"] == snapshot
        assert int(response.headers["X-Workbench-Row-Count"]) == count
        if fmt == "csv":
            rows = list(csv.DictReader(io.StringIO(response.data.decode("utf-8-sig"))))
            assert len(rows) == count
            check_overview_export_rows(data, rows, fmt)
            assert all(ref in response.data.decode("utf-8-sig") for ref in refs)
        else:
            book = load_workbook(io.BytesIO(response.data), read_only=True, data_only=True)
            try:
                assert book.sheetnames == ["方案总览", "指标计算方式", "比较范围"]
                sheet = book["方案总览"]
                headers = next(sheet.iter_rows(max_row=1, values_only=True))
                # Read-only rows stop at their last filled cell; read every row at the header width.
                rows = [dict(zip(headers, row)) for row in sheet.iter_rows(min_row=2, max_col=len(headers), values_only=True)]
                assert len(rows) == count
                check_overview_export_rows(data, rows, fmt)
            finally:
                book.close()
    boundaries = deepcopy(data)
    numeric_ref = "0" * 47 + "1"
    boundaries["candidates"][0].update(candidate_ref=numeric_ref, label="=1+1")
    boundaries["candidates"][1]["label"] = r"方案'甲\N"
    for fmt in ("csv", "xlsx"):
        download = write_run_decision_export(boundaries, document["meta"], fmt)
        if fmt == "csv":
            rows = list(csv.DictReader(io.StringIO(download.content.decode("utf-8-sig"))))
            assert rows[0]["候选编号"] == "'" + numeric_ref and rows[0]["候选名称"] == "'=1+1"
            assert rows[len(data["metric_definitions"])]["候选名称"] == r"方案'甲\N"
        else:
            book = load_workbook(io.BytesIO(download.content), read_only=True, data_only=False)
            try:
                rows = list(book["方案总览"].iter_rows())
                identity, label, number = rows[1][8], rows[1][9], rows[1][19]
                assert identity.value == numeric_ref and identity.data_type == "s"
                assert label.value == "=1+1" and label.data_type == "s"
                assert type(number.value) in (int, float) and number.data_type == "n"
                assert rows[1 + len(data["metric_definitions"])][9].value == r"方案'甲\N"
            finally:
                book.close()
    stale = client.get(path, query_string=dict(query, reference_candidate_ref=refs[0], format="csv"))
    assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "snapshot_stale"


def test_stage_material_wait_has_complete_schedulable_scope_and_deferred_delivery(candidate_case):
    case = candidate_case
    second = case.operation(seq=2)
    add_requirement(case, second, [])
    run_ref, _ = compute(case, case.settings(material_strategy="stage"))
    client, _ = api(case)
    data = decision(client, run_ref)["data"]
    _assert_summary_matches_full(decision_summary(client, run_ref)["data"], data)
    for row in data["candidates"]:
        coverage = row["coverage"]
        assert coverage["schedulable"]["state"] == "complete"
        assert coverage["schedulable"]["scheduled_count"] == coverage["schedulable"]["expected_count"] == 1
        assert coverage["schedulable"]["missing_count"] == 0 and coverage["schedulable"]["deferred_count"] == 1
        assert coverage["delivery"]["state"] == "partial" and coverage["delivery"]["deferred_batch_count"] == 1
        assert row["metrics"]["unplanned_operation_count"]["value"] == 0
        assert row["metrics"]["deferred_operation_count"]["value"] == 1
    recommendation = data["recommendation"]
    assert recommendation["recommendation_type"] == "schedulable_scope"
    scope = recommendation["completion_scope"]
    assert scope["state"] == "partial" and scope["deferred_batch_count"] == 1
    assert scope["ordinary_incomplete_batch_count"] == scope["unplanned_operation_count"] == 0
    assert scope["deferred_operation_count"] == 1
    assert scope["remaining_work"]["operation_count"] == scope["remaining_work"]["deferred_operation_count"] == 1
    assert scope["drill"]["candidate_ref"] == recommendation["candidate_ref"]
    assert scope["drill"]["detail_query"]["work_scope"] == "remaining"
    path = BASE + "/runs/" + run_ref + "/decision/preparation"
    query = {"selected_candidate_ref": recommendation["candidate_ref"]}
    full = client.get(path, query_string=query).get_json()["data"]
    response = client.get(path, query_string=dict(query, work_scope="remaining"))
    assert response.status_code == 200, response.get_json()
    remaining = response.get_json()["data"]
    assert len(full["items"]) == 2 and remaining["page"]["total"] == len(remaining["items"]) == 1
    assert remaining["summary"] == full["summary"]
    row = remaining["items"][0]
    assert row["operation_ref"] == case.conn.execute(
        "SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? AND active=1", (str(second),),
    ).fetchone()[0]
    candidate_ref = recommendation["candidate_ref"]
    source = read_candidate_source(CandidateStore(case.conn), candidate_ref)
    stored = source.disposition[row["operation_ref"]]
    assert stored["status"] == "skipped" and {issue["code"] for issue in stored["issues"]} == {"material_not_ready"}
    workspace_response = client.get(BASE + "/candidates/" + candidate_ref)
    assert workspace_response.status_code == 200, workspace_response.get_json()
    unplanned = workspace_response.get_json()["data"]["unplanned_operations"]
    assert len(unplanned) == 1 and unplanned[0]["operation_ref"] == row["operation_ref"]
    assert unplanned[0]["status"] == "skipped" and unplanned[0]["reason"]["code"] == "input_operation_skipped"
    assert unplanned[0]["operation_effort"]["allocation_state"] == "deferred"
    assert unplanned[0]["reason"]["message"].startswith("缺料未安排")
    assert all(issue["message"] in unplanned[0]["reason"]["message"] for issue in stored["issues"])
    assert row["after"]["allocation_state"] == "deferred" and row["after"]["required_standard_hours"] is None
    assert row["after"]["standard"]["standard_total_hours"] == 0.75
    for allocation, count in (("deferred", 1), ("unplanned", 0), ("new_schedule", 0)):
        filtered = client.get(path, query_string=dict(query, work_scope="remaining", allocation_state=allocation,
                                                      batch_ref=case.ref("batch", "B1"), machine_ref=case.ref("machine", "M1")))
        assert filtered.status_code == 200, filtered.get_json()
        assert filtered.get_json()["data"]["page"]["total"] == len(filtered.get_json()["data"]["items"]) == count


def test_explicit_comparison_navigation_preserves_identity_and_complete_window():
    from werkzeug.datastructures import MultiDict

    context = {"run_ref": "a" * 48, "candidate_ref": "b" * 48, "reference_candidate_ref": "c" * 48,
               "comparison_mode": "candidates", "range_start": "2026-09-09T00:00:00", "range_end": "2026-09-12T00:00:00"}
    for view in ("analysis", "gantt"):
        navigation = {"version": 1, "view": view, "context": context}
        assert read_navigation(view, MultiDict({"nav": json.dumps(navigation)})) == navigation
    formal: Dict[str, Any] = {key: value for key, value in context.items() if key != "reference_candidate_ref"}
    formal.update(comparison_mode="admission_official", reference_view=True, plan_ref="d" * 48,
                  operation_ref="e" * 48, comparison_tab="differences")
    navigation = {"version": 1, "view": "gantt", "context": formal}
    assert read_navigation("gantt", MultiDict({"nav": json.dumps(navigation)})) == navigation
    resources = dict(formal, comparison_tab="resources", resource_view="full_candidate", resource_kind="operator", resource_ref="f" * 48)
    for view in ("analysis", "gantt"):
        navigation = {"version": 1, "view": view, "context": resources}
        assert read_navigation(view, MultiDict({"nav": json.dumps(navigation)})) == navigation
        for tab in ("preparation", "changeovers"):
            scoped = {"version": 1, "view": view, "context": dict(resources, comparison_tab=tab, resource_kind="machine")}
            assert read_navigation(view, MultiDict({"nav": json.dumps(scoped)})) == scoped
    reading = dict(context, selected_batch_ref="1" * 48, range_start="2026-09-09T00:00:00.123456")
    for tab in ("delivery", "differences", "process", "metrics", "completion"):
        navigation = {"version": 1, "view": "analysis", "context": dict(reading, comparison_tab=tab)}
        assert read_navigation("analysis", MultiDict({"nav": json.dumps(navigation)})) == navigation
    mixed = dict(context, plan_ref="d" * 48)
    incomplete = {key: value for key, value in context.items() if key != "range_end"}
    for invalid in (mixed, incomplete, dict(formal, reference_candidate_ref="c" * 48),
                    {key: value for key, value in formal.items() if key != "plan_ref"},
                    {key: value for key, value in formal.items() if key != "candidate_ref"},
                    dict(formal, reference_view="true"), dict(formal, comparison_tab="invalid"),
                    # 页签白名单与前端实际页签一致；已不存在的旧页签按无效导航拒绝。
                    dict(formal, comparison_tab="overview"), dict(formal, comparison_tab="batches"),
                    dict(formal, comparison_tab="operations"),
                    # 白名单外的键整体拒绝，不按旧字段逐个适配。
                    dict(formal, unsupported_key="x"), dict(formal, operation_ref="invalid"), dict(reading, selected_batch_ref="invalid"),
                    dict(resources, resource_view="invalid"), dict(resources, resource_kind="invalid"), dict(resources, resource_ref="invalid")):
        with pytest.raises(WorkbenchNavigationInvalid):
            read_navigation("analysis", MultiDict({"nav": json.dumps({"version": 1, "view": "analysis", "context": invalid})}))
    history_state = {"query": {"timeline": "official", "comparison": "same_conditions", "reference_run_ref": "a" * 48,
        "metric_keys": ["overdue_count", "makespan_hours"], "date_from": "2026-09-09", "date_to": "2026-09-12",
        "range_start": "2026-09-09T08:00:00.123456", "range_end": "2026-09-12T16:00:00.654321",
        "resource_window_days": 3, "state": "committed", "sort": "occurred_at", "order": "asc", "page": 2, "size": 50,
        "condition_page": 2, "condition_size": 50, "selected_entry_ref": "adoption:" + "9" * 32},
        "selected_entry_ref": "adoption:" + "9" * 32, "reference_entry_ref": "run:" + "a" * 48,
        "metric_key": "makespan_hours", "detail_queries": {"conditions": {"state": "different", "family": "calendar"}}}
    target = {"source": "run_history", "history_topic": "decision_history", "decision_history_context": history_state,
              "history_query": {"state": "complete", "page": 3, "size": 50}}
    for view in ("analysis", "gantt"):
        navigation = {"version": 1, "view": view, "context": target}
        assert read_navigation(view, MultiDict({"nav": json.dumps(navigation)})) == navigation
    # 返回上下文只有 return_to 一种：历史走势页状态整份作为返回链接；旧返回键按不支持的定位拒绝（400）。
    for view, source in (("analysis", context), ("gantt", {"plan_ref": "d" * 48}),
                         ("run", {"run_ref": "a" * 48}), ("trial", {"scenario_ref": "b" * 48})):
        navigation = {"version": 1, "view": view, "context": dict(source, return_to={"view": "analysis", "context": target})}
        assert read_navigation(view, MultiDict({"nav": json.dumps(navigation)})) == navigation
        legacy = {"version": 1, "view": view, "context": dict(source, return_decision_history_context=history_state)}
        with pytest.raises(WorkbenchNavigationInvalid):
            read_navigation(view, MultiDict({"nav": json.dumps(legacy)}))
    for patch in ({"timeline": "invalid"}, {"comparison": "invalid"}, {"reference_run_ref": "invalid"},
                  {"metric_keys": ["overdue_count", "overdue_count"]}, {"range_end": None}, {"state": "invalid"},
                  {"sort": "invalid"}, {"order": "invalid"}, {"page": 0}, {"size": 25}):
        invalid_state = dict(history_state, query=dict(history_state["query"], **patch))
        invalid = dict(target, decision_history_context=invalid_state)
        with pytest.raises(WorkbenchNavigationInvalid):
            read_navigation("analysis", MultiDict({"nav": json.dumps({"version": 1, "view": "analysis", "context": invalid})}))
    for patch in ({"selected_entry_ref": "invalid"}, {"reference_entry_ref": "invalid"},
                  {"metric_key": "elapsed_seconds"}, {"detail_queries": []}):
        invalid = dict(target, decision_history_context=dict(history_state, **patch))
        with pytest.raises(WorkbenchNavigationInvalid):
            read_navigation("analysis", MultiDict({"nav": json.dumps({"version": 1, "view": "analysis", "context": invalid})}))


def test_explicit_navigation_return_to_admits_target_restore_state():
    from werkzeug.datastructures import MultiDict

    def read(view, context):
        navigation = {"version": 1, "view": view, "context": context}
        assert read_navigation(view, MultiDict({"nav": json.dumps(navigation)})) == navigation

    def rejected(view, context):
        with pytest.raises(WorkbenchNavigationInvalid):
            read_navigation(view, MultiDict({"nav": json.dumps({"version": 1, "view": view, "context": context})}))

    plan = {"plan_ref": "d" * 48}
    # 嵌套 context 按目标页可恢复状态准入：值班台不接受地址定位，但它记住的页面状态可以作为返回链接。
    dashboard = {"view": "dashboard", "context": {"scope": {"category": "all"}, "tab": "records", "item_ref": "e" * 48, "history_page": 2}}
    read("gantt", dict(plan, return_to=dashboard))
    rejected("dashboard", {"return_to": {"view": "gantt", "context": plan}})
    # 不带 context 的返回链接原样保留，表示回去恢复目标页自己记住的状态，不补成 {}。
    read("batches", {"focus": "gaps", "batchIds": ["B1"], "return_to": {"view": "run"}})
    # 返回链可以多层：候选甘特 → 方案对比 → 排产记录列表，每一层按各自目标页准入。
    catalog = {"source": "run_history", "history_topic": "run_catalog", "history_query": {"state": "complete", "page": 2}}
    comparison = {"run_ref": "a" * 48, "candidate_ref": "b" * 48, "comparison_tab": "resources", "detail_queries": {},
                  "return_to": {"view": "analysis", "context": catalog}}
    read("gantt", {"run_ref": "a" * 48, "candidate_ref": "b" * 48, "return_to": {"view": "analysis", "context": comparison}})
    for back in ({"view": "analysis", "context": dict(catalog, unknown_key=1)},
                 {"view": "analysis", "context": dict(comparison, return_decision_context=catalog)},
                 {"view": "analysis", "context": dict(comparison, return_to={"view": "analysis", "context": dict(catalog, return_history_context={})})},
                 {"view": "missing", "context": {}}, {"view": "analysis", "context": []}, {"context": catalog},
                 {"view": "analysis", "context": catalog, "label": "返回"},
                 # 目标页状态里的互斥同样生效：恢复浏览位置不能再带单条定位。
                 {"view": "process", "context": {"source": "production", "kind": "part", "read_view": {}, "entity_ref": "c" * 48}},
                 {"view": "analysis", "context": {"plan_ref": "d" * 48, "selected_task_side": "before"}}):
        rejected("gantt", dict(plan, return_to=back))


def test_unsaved_recommendation_does_not_invent_missing_saved_selection_evidence():
    from core.services.workbench.facts.decision_selection import selection_basis

    # 排队、计算中、失败的运行没有候选，也没有保存推荐。
    basis = selection_basis(None, [])
    assert basis["selected_candidate_ref"] is None and basis["evidence_state"] == "unavailable"
    assert basis["explanation"]["headline"] == "本次排产尚未保存推荐方案。"
    assert basis["explanation"]["issues"] == []


def test_decision_queries_preparation_pagination_and_recommendation_export_truth(candidate_case, monkeypatch):
    from core.infrastructure.transaction import TransactionManager
    from core.models.workbench_batch_material import normalize_material_changes
    from core.services.workbench.batch.facts import BatchFacts
    from core.services.workbench.batch.materials import WorkbenchBatchMaterialService
    from core.services.workbench.batch.scope import BatchFactScope

    case = candidate_case
    case.conn.execute("UPDATE Batches SET quantity=1,due_date='2026-09-09' WHERE batch_id='B1'")
    case.conn.execute("UPDATE BatchOperations SET unit_hours=2 WHERE id=?", (case.op_id,))
    op_b1_2 = case.operation("B1", seq=2, unit_hours=2)

    case.batch("B2", quantity=1, due_date="2026-09-10")
    op_b2_1 = case.operation("B2", seq=1, unit_hours=1)
    op_b2_2 = case.operation("B2", seq=2, unit_hours=1)
    op_b2_3 = case.operation("B2", seq=3, unit_hours=1)
    b2_material_rows = []
    for idx, deferred_op in enumerate((op_b2_1, op_b2_2, op_b2_3), start=1):
        mat_code = f"MAT_B2_{idx}"
        case.conn.execute("INSERT INTO Materials(material_id,name,unit) VALUES (?,?,'件')", (mat_code, mat_code))
        op_ref = case.conn.execute(
            "SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? AND active=1",
            (str(deferred_op),),
        ).fetchone()[0]
        b2_material_rows.append(
            {
                "row_key": None,
                "material_ref": case.ref("material", mat_code),
                "required_quantity": 2,
                "available_quantity": 0,
                "operation_ref": op_ref,
                "arrivals": [],
            }
        )
    case.conn.commit()
    with TransactionManager(case.conn).transaction():
        batch_ref = case.ref("batch", "B2")
        scope = BatchFactScope(BatchFacts(case.conn, material_day=date.today().isoformat()), command=True, mode="single_instance", target_ref=batch_ref)
        WorkbenchBatchMaterialService(case.conn).apply_normalized(
            scope,
            batch_ref,
            normalize_material_changes({"removed_keys": [], "rows": b2_material_rows}),
        )

    case.batch("B3", quantity=1, due_date="2026-09-10")
    op_b3_1 = case.operation("B3", seq=1, unit_hours=6)

    case.config(dispatch_mode="batch_order", sort_strategy="due_date_first")
    seq_overrides = {
        case.op_id: 10,
        op_b1_2: 10_000_000_000_000_000,
        op_b2_1: 1 << 53,
        op_b2_2: 2,
        op_b2_3: None,
        op_b3_1: 5,
    }
    from core.services.workbench.facts.candidate_facts import GenerationFacts
    from core.services.workbench.run.worker import WorkbenchRunWorker

    accepted = case.accept(settings=case.settings("B1", "B2", "B3", end_date="2026-09-09", material_strategy="stage"))
    run_ref = accepted["run_ref"]
    original_facts_init = GenerationFacts.__init__

    def init_with_large_sequences(facts_self, capture, **kwargs):
        original_facts_init(facts_self, capture, **kwargs)
        if capture.get("run_ref") == run_ref:
            for op_id, seq_val in seq_overrides.items():
                if op_id in facts_self.tables["BatchOperations"]:
                    facts_self.tables["BatchOperations"][op_id] = {
                        **facts_self.tables["BatchOperations"][op_id],
                        "seq": seq_val,
                    }

    with monkeypatch.context() as worker_patch:
        worker_patch.setattr(GenerationFacts, "__init__", init_with_large_sequences)
        executed = WorkbenchRunWorker(case.conn, clock=datetime.now).execute(run_ref)
    cand_ref = executed["candidates"][0]["candidate_ref"]
    client, _ = api(case)

    expected_asc = [2, 5, 10, str(1 << 53), "10000000000000000", None]
    expected_desc = ["10000000000000000", str(1 << 53), 10, 5, 2, None]
    for endpoint in ("operations", "preparation"):
        asc_resp = client.get(
            f"{BASE}/runs/{run_ref}/decision/{endpoint}",
            query_string={"selected_candidate_ref": cand_ref, "sort": "sequence", "order": "asc"},
        )
        assert asc_resp.status_code == 200, asc_resp.get_json()
        assert [row["sequence"] for row in asc_resp.get_json()["data"]["items"]] == expected_asc

        desc_resp = client.get(
            f"{BASE}/runs/{run_ref}/decision/{endpoint}",
            query_string={"selected_candidate_ref": cand_ref, "sort": "sequence", "order": "desc"},
        )
        assert desc_resp.status_code == 200, desc_resp.get_json()
        assert [row["sequence"] for row in desc_resp.get_json()["data"]["items"]] == expected_desc

    summary_doc = decision_summary(
        client, run_ref, selected_candidate_ref=cand_ref, comparison_mode="admission_official"
    )
    export_resp = client.get(
        f"{BASE}/runs/{run_ref}/decision/export",
        query_string={
            "selected_candidate_ref": cand_ref,
            "comparison_mode": "admission_official",
            "snapshot_ref": summary_doc["meta"]["snapshot_ref"],
            "section": "recommendation",
            "format": "csv",
        },
    )
    assert export_resp.status_code == 200, export_resp.get_data(as_text=True)
    csv_rows = list(csv.DictReader(io.StringIO(export_resp.data.decode("utf-8-sig"))))
    completion_rows = [row for row in csv_rows if row["record_kind"] == "completion_set"]
    cand_categories = {
        row["批次编号"]: row["安排分类"] for row in completion_rows if row["安排来源类型"] == "candidate"
    }
    ref_categories = {
        row["批次编号"]: row["安排分类"] for row in completion_rows if row["安排来源类型"] == "admission_official"
    }
    assert cand_categories == {"B1": "complete", "B2": "deferred", "B3": "incomplete"}
    assert ref_categories == {"B1": "unknown", "B2": "unknown", "B3": "unknown"}

    ops_path = f"{BASE}/runs/{run_ref}/decision/operations"
    for bad_query in (
        {"page": "0"},
        {"page": "01"},
        {"page": "１"},
        {"page": "-1"},
        {"page": str(1 << 53)},
        {"page": "9" * 6000},
        {"size": "7"},
        {"size": "020"},
        {"size": "２０"},
        {"size": "9" * 6000},
    ):
        bad_resp = client.get(ops_path, query_string={"selected_candidate_ref": cand_ref, **bad_query})
        assert bad_resp.status_code == 422 and bad_resp.get_json()["error"]["code"] == "invalid_input"

    beyond_resp = client.get(
        ops_path,
        query_string={"selected_candidate_ref": cand_ref, "page": str((1 << 53) - 1)},
    )
    assert beyond_resp.status_code == 200, beyond_resp.get_json()
    beyond_data = beyond_resp.get_json()["data"]
    assert beyond_data["items"] == [] and beyond_data["page"]["has_more"] is False

    res_path = f"{BASE}/runs/{run_ref}/decision/resources"
    for valid_heatmap_size in (7, 14, 31):
        ok_res = client.get(
            res_path,
            query_string={"selected_candidate_ref": cand_ref, "heatmap_size": str(valid_heatmap_size)},
        )
        assert ok_res.status_code == 200, ok_res.get_json()
    for bad_heatmap in ("07", "７", "15", "9" * 6000):
        bad_res = client.get(
            res_path,
            query_string={"selected_candidate_ref": cand_ref, "heatmap_size": bad_heatmap},
        )
        assert bad_res.status_code == 422 and bad_res.get_json()["error"]["code"] == "invalid_input"
