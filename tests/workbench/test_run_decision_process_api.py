"""Saved solver sources, legacy pagination and downloads share one process selector."""

import csv
import io
import json
import sys
from copy import deepcopy
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook

from core.services.scheduler.run.optimizer.process_evidence import non_search_evidence
from core.services.scheduler.summary.optimizer_public_attempts import COMPARISON_METRIC_KEYS, project_attempts
from core.services.scheduler.summary.optimizer_public_summary import project_public_result_summary
from core.services.workbench.facts.candidate_process import COUNT_KEYS, candidate_process
from core.services.workbench.run.decision_process import normalize_process_filters, process_details
from core.services.workbench.run.decision_process_export import (
    ATTEMPT_HEADERS,
    CANDIDATE_HEADERS,
    PROCESS_CSV_HEADERS,
    PROGRESS_HEADERS,
    STAGE_HEADERS,
)
from tests.workbench.run_candidate_support import BASE, api, compute, edit_artifact, public, retained
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401
from tests.workbench.test_run_decision_api import decision
from tests.workbench.test_run_decision_impact_api import detail


def saved_artifacts(case):
    return {row[0]: json.loads(row[1]) for row in case.conn.execute(
        "SELECT candidate_ref,artifact_json FROM WorkbenchRunCandidates ORDER BY sequence")}


def expect_error(client, path, query, status, code):
    response = client.get(path, query_string=query)
    assert response.status_code == status, response.get_json()
    assert response.get_json()["error"]["code"] == code


def process_source(rows, selected=None):
    run_ref = "a" * 48
    source = SimpleNamespace(run={"run_ref": run_ref}, rows=rows, selected_ref=selected,
        scope={"run_ref": run_ref, "selected_candidate_ref": selected,
               "comparison_mode": "candidates", "reference": {"kind": "candidate", "candidate_ref": None}},
        baseline={"kind": "candidate", "candidate_ref": None, "state": "selection_required"})
    source._candidate_reference = lambda ref, require_result=True: next(row for row in rows if row["candidate_ref"] == ref)
    return source


def check_process_exports(client, run_ref, query, token, data, overview):
    candidate, summary, progress = (data[key] for key in ("candidate", "summary", "progress"))
    attempts = detail(client, run_ref, "process", **dict(query, record_kind="attempts", sort="rank", size=50))["data"]["items"]
    assert sorted(attempts, key=lambda row: row["saved_index"]) == sorted(data["attempts"], key=lambda row: row["saved_index"])
    points = sorted(progress["points"], key=lambda row: (
        row["elapsed_ms"] is None, row["elapsed_ms"] or 0, row["event_index"] if row["event_index"] is not None else float("inf")))
    metric_fields = {"overdue_count": "保存超期批次数", "total_tardiness_hours": "保存总拖期（小时）",
                     "weighted_tardiness_hours": "保存加权拖期（小时）", "makespan_hours": "保存工期（小时）", "changeover_count": "保存算法工种切换次数"}
    completion_fields = {"expected_operation_count": "本次参与计算工序数", "missing_operation_count": "本次计算范围缺少工序数",
                         "unexpected_result_count": "本次计算范围外结果数", "complete_batch_count": "本次计算范围内工序排齐批次数",
                         "incomplete_batch_count": "本次计算范围内工序未排齐批次数"}
    count_fields = {"evaluated": "评估数", "accepted": "接受数", "current_accepted": "当前解接受数",
                    "strict_improvements": "严格改善数", "rejected": "已记录拒绝数", "unverified_trials": "未验证数", "decoder_invocations": "实际排程调用数"}
    profile_fields = {"enabled": "优化器已启用", "seed": "优化器随机种子", "configured_time_budget_seconds": "配置求解预算（秒）",
        "effective_time_budget_seconds": "实际求解预算（秒）", "assigned_time_budget_ms": "已分配求解预算（毫秒）",
        "configured_max_iterations": "配置迭代上限", "effective_max_iterations": "实际迭代上限", "system_limit_applied": "已应用系统限制",
        "system_limit_reason": "系统限制原因", "message": "Profile说明", "candidate_strategy_families": "候选策略族",
        "configured_neighborhoods": "配置邻域", "effective_neighborhoods": "实际邻域"}
    profile = data["source"]["profile"]
    recorded = data["source"]["evidence_version"] is not None
    units = {field["index"]: field["unit"] for field in data["objective"]["score_fields"]}

    def scores(row):
        return {**{"评分分量" + str(index): row["score"][index] if index < len(row["score"]) else None for index in range(6)},
                **{"评分分量" + str(index) + "单位": units.get(index) for index in range(6)}}

    def values(row, fields):
        return {label: row[key] for key, label in fields.items()}

    def comparison_values(row):
        comparison = row["comparison"] or {}
        score = comparison.get("reference_score") or []
        labels = {"failed_ops": "失败工序数", "overdue_count": "超期批次数", "weighted_tardiness_hours": "加权拖期（小时）",
                  "total_tardiness_hours": "总拖期（小时）", "makespan_hours": "工期（小时）", "changeover_count": "算法工种切换次数"}
        return {"当时比较对象": comparison.get("kind"), "当时比较状态": comparison.get("state"), "当时比较目标": comparison.get("objective_name"),
                "当时本次评价范围": comparison.get("objective_scope"), "当时参考评价范围": comparison.get("reference_scope"),
                **{"当时参考评分分量" + str(index): score[index] if index < len(score) else None for index in range(6)},
                **{"当时参考" + label: (comparison.get("reference_metrics") or {}).get(key) for key, label in labels.items()},
                **{"相对当时对象变化" + label: (comparison.get("metric_deltas") or {}).get(key) for key, label in labels.items()},
                **{"当时参考" + label: (comparison.get("reference_completion") or {}).get(key) for key, label in completion_fields.items()}}

    expected = {"candidate_summary": [{
        "候选自身耗时（毫秒）": candidate["own_elapsed_ms"], "来源求解耗时（毫秒）": candidate["source_solver_elapsed_ms"],
        "配置派工规则": candidate["configured_dispatch_rule"], "实际采用派工规则": candidate["adopted_dispatch_rule"],
        "优化器配置类别": candidate["algorithm_profile"], "优化器Profile": profile.get("profile"), "接受准则": profile.get("acceptance"),
        **{label: "；".join(profile[key]) if type(profile.get(key)) is list else profile.get(key) for key, label in profile_fields.items()},
        "保存代表尝试数": summary["saved_attempt_count"], "原进步事件数": progress["sampling"]["event_total_count"],
        "旧版最佳更新数（含同分）": summary["legacy_best_updates"],
        "保留进步点数": len(points), "采样策略": progress["sampling"]["policy"],
        "保留首次有效": progress["coverage"]["endpoint_coverage"]["first_valid"],
        "保留首次排齐本次参与计算工序": progress["coverage"]["endpoint_coverage"]["first_expected_complete"],
        "保留最终": progress["coverage"]["endpoint_coverage"]["final"],
        **{"候选自身" + label: candidate["own_counts"][key] for key, label in count_fields.items()},
        **{"来源求解" + label: candidate["solver_counts"][key] for key, label in count_fields.items()},
        **values(candidate["final_metrics"], metric_fields), **values(candidate["completion"], completion_fields),
    }], "rejection_reason": [{
        "拒绝原因key": key, "拒绝原因数": count,
        "候选自身耗时（毫秒）": None, "来源求解耗时（毫秒）": None, "保存代表尝试数": None, "保留进步点数": None,
        **{"候选自身" + label: None for label in count_fields.values()}, **{"来源求解" + label: None for label in count_fields.values()},
        **{label: None for label in metric_fields.values()},
    } for key, count in sorted((data["source"]["rejection_summary"] or {}).items())], "progress_point": [{
        "事件序号": row["event_index"], "累计求解耗时（毫秒）": row["elapsed_ms"], "阶段": row["phase"],
        "阶段访问序号": row["phase_visit"], "连续段": row["segment"], "业务主值": row["primary_value"],
        "首次有效": "first_valid" in row["flags"] if recorded else None, "首次排齐本次参与计算工序": "first_expected_complete" in row["flags"] if recorded else None,
        "最终结果": "final" in row["flags"] if recorded else None, "目标评价范围": row["objective_scope"], "已验证": row["verified"],
        "评价范围未排齐批次编号": json.dumps(row["evaluation_scope"]["incomplete_batch_ids"], ensure_ascii=False, separators=(",", ":")) if row["evaluation_scope"] is not None else None,
        **values(row["completion"], completion_fields), **scores(row),
    } for row in points], "stage": [{
        "阶段": row["phase"], "阶段状态": row["status"], "阶段起点（毫秒）": row["start_elapsed_ms"],
        "阶段终点（毫秒）": row["end_elapsed_ms"], "阶段累计耗时（毫秒）": row["elapsed_ms"], "访问数": row["visits"],
        "评估数": row["evaluated"], "接受数": row["accepted"], "严格改善数": row["strict_improvements"],
        "已记录拒绝数": row["rejected"], "停止原因": row["stop_reason"],
    } for row in data["stages"]], "representative_attempt": [{
        "保存尝试序号": row["saved_index"], "代表排名": row["rank"], "尝试来源": row["source_label"],
        "尝试来源key": row["candidate_origin"], "权重Profile": row["weight_profile_slug"], "尝试事件序号": row["event_index"],
        "尝试策略": row["strategy"], "尝试派工模式": row["dispatch_mode"], "尝试派工规则": row["dispatch_rule"],
        "尝试失败工序数": row["failed_ops"], "尝试累计耗时（毫秒）": row["elapsed_ms"], "尝试已接受": row["accepted"],
        "尝试已验证": row["verified"], "相对当时对象严格改善": row["strict_improved"],
        "业务主值": row["primary_value"], "目标评价范围": row["objective_scope"],
        **values(row["metrics"], metric_fields), **values(row["completion"], completion_fields), **scores(row), **comparison_values(row),
    } for row in attempts]}
    common = {"排产编号": run_ref, "归档编号": run_ref, "读取编号": token,
              "保存推荐候选编号": overview["recommendation"]["candidate_ref"],
              "当前查看候选编号": query["selected_candidate_ref"], "查看基准编号": query["reference_candidate_ref"],
              "范围起点（含）": data["scope"]["range_start"], "范围终点（不含）": data["scope"]["range_end"],
              "资源视角": data["scope"]["resource_view"], "推荐版本": overview["recommendation"]["recommendation_version"],
              "推荐记录格式版本": overview["selection_basis"]["selection_evidence_version"],
              "查看过程候选编号": candidate["candidate_ref"], "求解来源候选编号": data["source"]["source_candidate_ref"],
              "过程版本": "decision-process-v1", "过程证据版本": data["source"]["evidence_version"],
              "过程证据状态": data["source"]["evidence_state"], "主指标key": "overdue_count", "主指标单位": "批次"}
    row_count = sum(map(len, expected.values()))
    export_path = BASE + "/runs/" + run_ref + "/decision/export"
    for fmt in ("csv", "xlsx"):
        response = client.get(export_path, query_string=dict(query, snapshot_ref=token, section="process", format=fmt))
        assert response.status_code == 200, response.get_json()
        assert response.headers["X-Workbench-Snapshot-Ref"] == token and response.headers["X-Workbench-Run-Ref"] == run_ref
        assert int(response.headers["X-Workbench-Row-Count"]) == row_count
        if fmt == "csv":
            reader = csv.DictReader(io.StringIO(response.data.decode("utf-8-sig")))
            actual = list(reader)
            assert reader.fieldnames == list(PROCESS_CSV_HEADERS) and len(actual) == row_count
            for kind, records in expected.items():
                rows = [row for row in actual if row["record_kind"] == kind]
                assert len(rows) == len(records)
                for row, record in zip(rows, records):
                    for label, value in {**common, **record}.items():
                        if type(value) in (int, float):
                            assert float(row[label]) == value, (kind, label, row[label], value)
                        else:
                            text = "" if value is None else str(value)
                            if type(value) is str and value.lstrip().startswith(("=", "+", "-", "@")):
                                text = "'" + value
                            assert row[label] == text, (kind, label)
        else:
            book = load_workbook(io.BytesIO(response.data), read_only=True, data_only=False)
            try:
                assert book.sheetnames == ["候选计算", "进步事件", "搜索阶段", "代表尝试", "指标计算方式", "比较范围"]
                definitions = (("候选计算", CANDIDATE_HEADERS, ("candidate_summary", "rejection_reason")), ("进步事件", PROGRESS_HEADERS, ("progress_point",)),
                               ("搜索阶段", STAGE_HEADERS, ("stage",)), ("代表尝试", ATTEMPT_HEADERS, ("representative_attempt",)))
                for title, headers, kinds in definitions:
                    cells = list(book[title].iter_rows(max_col=len(headers)))
                    assert [cell.value for cell in cells[0]] == list(headers)
                    records = [{"record_kind": kind, **record} for kind in kinds for record in expected[kind]]
                    assert len(cells) - 1 == len(records)
                    for cells_row, record in zip(cells[1:], records):
                        row = dict(zip(headers, cells_row))
                        kind = record["record_kind"]
                        assert row["record_kind"].value == kind
                        for label, value in {**common, **record}.items():
                            cell = row[label]
                            if type(value) in (int, float):
                                assert cell.value == pytest.approx(value, rel=1e-12, abs=1e-9) and cell.data_type == "n", (kind, label)
                            else:
                                assert cell.value == (None if value == "" else value), (kind, label, cell.value, value)
                                if type(value) is str and value:
                                    assert cell.data_type == "s"
                                elif type(value) is bool:
                                    assert cell.data_type == "b"
                assert sum(len(list(book[title].iter_rows())) - 1 for title, _, _ in definitions) == row_count
            finally:
                book.close()


def test_real_process_sources_keep_viewer_and_legacy_progress_pages_under_one_snapshot(candidate_case):
    case = candidate_case
    case.config(algo_mode="improve", dispatch_mode="sgs", dispatch_rule="slack", time_budget_seconds=1)
    run_ref, refs = compute(case)
    artifacts = saved_artifacts(case)
    client, _ = api(case)
    query = {"selected_candidate_ref": refs[-2], "reference_candidate_ref": refs[0]}
    path = BASE + "/runs/" + run_ref + "/decision/process"
    with retained(case.conn):
        overview = decision(client, run_ref, **query)["data"]
        default = detail(client, run_ref, "process", **query)["data"]
        assert default["candidate"]["candidate_ref"] == default["filters"]["process_candidate_ref"] == refs[-2]
        assert default["scope"]["selected_candidate_ref"] == refs[-2]
        assert default["scope"]["reference"]["candidate_ref"] == refs[0]
        assert {row["candidate_ref"] for row in default["candidates"]} == set(refs)
        assert default["process_version"] == "decision-process-v1"
        reused = []
        checked_sources = set()
        for ref in refs:
            response = detail(client, run_ref, "process", **dict(query, process_candidate_ref=ref))
            data = response["data"]
            public({key: value for key, value in data.items() if key != "baseline"})
            own = artifacts[ref]
            candidate, source, summary = (data[key] for key in ("candidate", "source", "summary"))
            assert candidate["candidate_ref"] == source["candidate_ref"] == ref
            assert source["role"] == "process_anchor" and source["grain"] == "saved_candidate_solver_process"
            assert data["scope"] == default["scope"] and data["baseline"] == default["baseline"]
            assert candidate["configured_dispatch_rule"] == own["dispatch_rule"] == "slack"
            assert candidate["adopted_dispatch_rule"] == own["adopted_dispatch_rule"]
            assert candidate["own_elapsed_ms"] == summary["own_elapsed_ms"] == own["elapsed_seconds"] * 1000
            assert candidate["final_metrics"] == {key: own["metrics"][key] for key in candidate["final_metrics"]}
            completed = own["metrics"]["completion"]
            assert candidate["completion"] == {key: len(completed["incomplete_batch_ids"]) if key == "incomplete_batch_count"
                                                else completed[key] for key in candidate["completion"]}
            assert source["evidence_version"] == "optimization-process-v1" and source["evidence_state"] == "complete"
            assert data["progress"]["mode"] == "curve" and 1 <= len(data["progress"]["points"]) <= 200
            assert len(data["items"]) <= 12 and data["page"]["total"] == summary["saved_attempt_count"]
            assert len(data["attempts"]) == summary["saved_attempt_count"]
            assert sorted(data["attempts"], key=lambda row: row["saved_index"]) == sorted(data["items"], key=lambda row: row["saved_index"])
            assert all("tasks" not in row and "gantt_graph" not in row for row in data["items"])
            assert set(summary["solver_counts"]) == set(COUNT_KEYS)
            assert summary["rejection_summary"] == source["rejection_summary"] == artifacts[source["source_candidate_ref"]]["process_evidence"]["rejection_summary"]
            assert all(type(value) is int for value in summary["solver_counts"].values())
            assert summary["solver_counts"]["evaluated"] >= summary["solver_counts"]["strict_improvements"]
            solver_ref = source["source_candidate_ref"]
            solver = artifacts[solver_ref]["process_evidence"]
            assert summary["solver_counts"] == solver["counts"]
            assert summary["source_solver_elapsed_ms"] == solver["elapsed_ms"]
            saved_points = {row["event_index"]: row for row in solver["points"]}
            assert all(point["evaluation_scope"] == saved_points[point["event_index"]]["evaluation_scope"] for point in data["progress"]["points"])
            assert all(row["source_candidate_ref"] == solver_ref for row in data["items"] + data["progress"]["points"])
            for item in data["items"]:
                saved = artifacts[solver_ref]["attempts"][item["saved_index"] - 1]
                assert item["source_label"] and item["candidate_origin"] == saved.get("candidate_origin", saved.get("source"))
                assert item["weight_profile_slug"] == saved.get("weight_profile_slug")
                for field in ("elapsed_ms", "event_index", "accepted", "verified", "strict_improved", "comparison"):
                    assert item[field] == saved.get(field), (ref, item["saved_index"], field)
                assert type(item["elapsed_ms"]) is int and type(item["accepted"]) is bool and type(item["verified"]) is bool
                comparison = item["comparison"]
                if comparison["state"] == "comparable":
                    assert type(item["strict_improved"]) is bool and set(comparison["metric_deltas"]) == set(COMPARISON_METRIC_KEYS)
                else:
                    assert item["strict_improved"] is None and comparison["metric_deltas"] is None
            assert data["objective"]["primary_metric_key"] == "overdue_count" and data["objective"]["unit"] == "批次"
            assert data["progress"]["coverage"]["endpoint_coverage"]["first_valid"] is True
            assert data["progress"]["coverage"]["endpoint_coverage"]["first_expected_complete"] is True
            assert data["progress"]["coverage"]["endpoint_coverage"]["final"] is True
            assert data["summary"]["sampling"]["retained_point_count"] == len(data["progress"]["points"])
            if source["kind"] == "reused":
                reused.append(ref)
                assert solver_ref != ref and summary["own_counts"] == dict.fromkeys(COUNT_KEYS, 0)
                original = detail(client, run_ref, "process", **dict(query, process_candidate_ref=solver_ref))["data"]
                assert data["progress"] == original["progress"] and data["stages"] == original["stages"]
                assert data["attempts"] == original["attempts"]
                assert data["items"] == original["items"] and summary["solver_counts"] == original["summary"]["own_counts"]
            else:
                assert source["kind"] == "own_search" and solver_ref == ref
                assert summary["own_counts"] == summary["solver_counts"]
            if source["kind"] not in checked_sources:
                check_process_exports(client, run_ref, dict(query, process_candidate_ref=ref), response["meta"]["snapshot_ref"], data, overview)
                checked_sources.add(source["kind"])
        assert reused
        assert decision(client, run_ref, **query)["data"]["selection_basis"] == overview["selection_basis"]
        for invalid in ({"record_kind": "raw"}, {"record_kind": "attempts", "sort": "event_index"},
                        {"page": 0}, {"size": 27}, {"order": "random"}):
            expect_error(client, path, dict(query, **invalid), 422, "invalid_input")
        expect_error(client, path, dict(query, process_candidate_ref="bad"), 400, "invalid_input")
        expect_error(client, path, dict(query, process_candidate_ref="f" * 48), 404, "entity_not_found")
        expect_error(client, BASE + "/runs/" + "e" * 48 + "/decision/process", {}, 404, "entity_not_found")

    # Explicit old-record fixture: 27 genuinely stored discrete rows, not 27 producer events.
    legacy = [{"elapsed_ms": index * 10, "tag": "local:swap", "strategy": "due_date_first",
               "dispatch_mode": "sgs", "dispatch_rule": "slack", "score": [0, 28 - index, 0.75],
               "metrics": {"overdue_count": 28 - index, "makespan_hours": 0.75}}
              for index in range(1, 28)]
    legacy[7]["metrics"].pop("overdue_count")

    def old_record(artifact):
        artifact.pop("process_evidence", None)
        artifact["improvement_trace"] = deepcopy(legacy)
        artifact["search_report"] = {"objective_name": "min_overdue", "best_improved_candidates": 1,
                                     "rejection_summary": {"duration_overflow": 2, "resource_guard": 1}}

    edit_artifact(case, refs[0], old_record)
    progress_query = dict(query, process_candidate_ref=refs[0], record_kind="progress", sort="elapsed_ms", order="asc")
    with retained(case.conn):
        first = detail(client, run_ref, "process", **progress_query)
        token = first["meta"]["snapshot_ref"]
        second = detail(client, run_ref, "process", **dict(progress_query, page=2, snapshot_ref=token))
        wide = detail(client, run_ref, "process", **dict(progress_query, size=50, snapshot_ref=token))
        one, two, full = (response["data"] for response in (first, second, wide))
        assert second["meta"]["snapshot_ref"] == wide["meta"]["snapshot_ref"] == token
        assert one["items"] + two["items"] == full["items"] == one["progress"]["points"]
        assert one["attempts"] == two["attempts"] == full["attempts"]
        assert len(one["attempts"]) == one["summary"]["saved_attempt_count"]
        assert one["page"] == {"number": 1, "size": 20, "total": 27, "has_more": True}
        assert two["page"] == {"number": 2, "size": 20, "total": 27, "has_more": False}
        assert len(two["items"]) == 7 and [row["event_index"] for row in full["items"]] == list(range(1, 28))
        assert [row["elapsed_ms"] for row in full["items"]] == list(range(10, 280, 10))
        assert one["scope"] == default["scope"] and one["candidate"]["candidate_ref"] == refs[0]
        assert one["progress"]["mode"] == "discrete" and one["source"]["evidence_state"] == "partial"
        assert set(one["progress"]["coverage"]["endpoint_coverage"].values()) == {None}
        assert all(row["flags"] == [] and row["verified"] is None for row in full["items"])
        assert all(row["evaluation_scope"] is None for row in full["items"])
        assert set(one["summary"]["solver_counts"].values()) == {None}
        assert one["summary"]["sampling"]["event_total_count"] is None
        assert one["items"][7]["primary_value"] is None and one["items"][7]["score"] == [0, 20, 0.75]
        empty = detail(client, run_ref, "process", **dict(progress_query, page=3, snapshot_ref=token))["data"]
        assert empty["items"] == [] and empty["page"]["total"] == 27 and empty["page"]["has_more"] is False
        assert empty["attempts"] == one["attempts"]
        for sort_order in ("asc", "desc"):
            sorted_data = detail(client, run_ref, "process", **dict(progress_query, sort="primary_value", order=sort_order, size=50))["data"]
            assert sorted_data["items"][-1]["event_index"] == 8
            values = [row["primary_value"] for row in sorted_data["items"][:-1]]
            assert values == sorted(values, reverse=sort_order == "desc")
        for changed in ({"process_candidate_ref": refs[1]}, {"record_kind": "attempts", "sort": "rank"},
                        {"sort": "event_index"}, {"order": "desc"}, {"selected_candidate_ref": refs[-1]},
                        {"reference_candidate_ref": refs[1]}):
            expect_error(client, path, dict(progress_query, snapshot_ref=token, **changed), 409, "snapshot_stale")
        check_process_exports(client, run_ref, progress_query, token, full, overview)


def test_legacy_attempts_keep_saved_indices_nulls_and_safe_public_fields():
    ref = "1" * 48
    row = {"candidate_ref": ref, "status": "completed", "artifact": {
        "label": "旧候选", "objective_name": "min_overdue", "elapsed_seconds": 0.25,
        "attempts": [
            {"tag": "start:0", "strategy": "due_date_first", "dispatch_mode": "sgs", "dispatch_rule": "slack",
             "score": [0, 3, 1.25], "failed_ops": 0, "metrics": {"overdue_count": 3, "makespan_hours": 1.25}},
            {"source": "candidate_rejected", "origin": {"type": "guard", "message": "内部拒绝"}, "score": [0, 0]},
            {"tag": "local:swap", "score": [0, 1, 1.5], "failed_ops": 0,
             "metrics": {"overdue_count": 1, "makespan_hours": 1.5, "machine_id": "PRIVATE", "fingerprint": "SECRET"}},
            {"tag": "local:swap2", "score": [0, None, 1.5], "metrics": {"makespan_hours": 1.5}},
            {"tag": "multi_start_efficiency", "candidate_status": "phase_summary", "multi_start_efficiency": {"decoded_candidates": 900}},
        ], "search_report": {"objective_name": "min_overdue", "best_improved_candidates": 1,
                             "rejection_summary": {"same_score": 1},
                             "candidate_profile": {"profile": "sgs", "acceptance": "improve_only", "configured_time_budget_seconds": 3}},
        "metrics": {"overdue_count": 1},
    }}
    source = process_source([row], ref)
    result = process_details(source, normalize_process_filters())
    public(result)
    assert result["filters"]["process_candidate_ref"] == ref and result["page"]["total"] == 3
    assert [item["saved_index"] for item in result["items"]] == [3, 1, 4]
    assert [item["rank"] for item in result["items"]] == [1, 2, None]
    assert result["items"][-1]["score"] == [0, None, 1.5] and result["items"][-1]["primary_value"] is None
    assert all(item["elapsed_ms"] is None and item["accepted"] is None for item in result["items"])
    assert set(result["summary"]["solver_counts"].values()) == {None}
    assert result["summary"]["solver_counts"]["strict_improvements"] is None
    assert result["summary"]["legacy_best_updates"] == result["candidate"]["legacy_best_updates"] == 1
    assert result["source"]["rejection_summary"] == result["summary"]["rejection_summary"] == {"same_score": 1}
    assert result["source"]["profile"] == {"profile": "sgs", "acceptance": "improve_only", "configured_time_budget_seconds": 3}
    assert result["summary"]["own_elapsed_ms"] == 250 and result["summary"]["source_solver_elapsed_ms"] is None
    assert result["progress"]["mode"] == "none" and result["progress"]["points"] == []
    assert result["source"]["evidence_state"] == "partial" and result["source"]["reason"]["code"] == "legacy_process_coverage"
    assert "PRIVATE" not in json.dumps(result) and "SECRET" not in json.dumps(result)
    assert result["candidate"]["final_metrics"]["overdue_count"] == 1
    assert result["candidate"]["final_metrics"]["makespan_hours"] is None

    # Explicit unknown components are ordering sentinels; completed-subset zero is real.
    scoped = deepcopy(row)
    scoped["artifact"]["objective_name"] = "min_tardiness"
    sentinel = sys.float_info.max
    attempts = [
        {"tag": "local:unknown_scope", "score": [2, sentinel, sentinel],
         "metrics": {"total_tardiness_hours": sentinel, "completion": {"objective_scope": "unknown"}}},
        {"tag": "local:unknown_policy", "score": [1, sentinel, sentinel],
         "metrics": {"total_tardiness_hours": 0, "completion": {"objective_score_policy": "unknown_all_components"}}},
        {"tag": "local:completed_subset", "score": [1, 0, 0],
         "metrics": {"total_tardiness_hours": 0, "completion": {"objective_scope": "completed_batches_only",
                     "objective_score_policy": "completed_batches_only", "objective_defined": False,
                     "expected_operation_count": 3, "missing_operation_count": 1, "unexpected_result_count": 0,
                     "complete_batch_count": 1, "incomplete_batch_count": 1}}},
        {"tag": "local:all_batches", "score": [0, 5.5, 1.25], "metrics": {"total_tardiness_hours": 5.5,
         "completion": {"objective_scope": "all_batches", "expected_operation_count": 31, "missing_operation_count": 0,
                        "unexpected_result_count": 0, "complete_batch_count": 11, "incomplete_batch_count": 0}}},
    ]
    scoped["artifact"]["attempts"] = attempts
    scoped["artifact"]["improvement_trace"] = [{"elapsed_ms": index, **deepcopy(attempt)} for index, attempt in enumerate(attempts, 1)]
    scoped["artifact"]["metrics"] = {"total_tardiness_hours": 0, "completion": {"objective_scope": "unknown"}}
    projected = process_details(process_source([scoped], ref), normalize_process_filters())
    public(projected)
    assert projected["objective"]["unit"] == "小时"
    assert [item["saved_index"] for item in projected["items"]] == [4, 3, 1, 2]
    by_index = {item["saved_index"]: item for item in projected["items"]}
    for index, failed in ((1, 2), (2, 1)):
        assert by_index[index]["primary_value"] is None
        assert by_index[index]["score"] == [failed, None, None] and by_index[index]["rank"] is None
    assert by_index[1]["objective_scope"] == "unknown" and by_index[2]["objective_scope"] is None
    assert by_index[3]["primary_value"] == 0 and by_index[3]["score"] == [1, 0, 0]
    assert by_index[3]["objective_scope"] == "completed_batches_only"
    assert by_index[4]["primary_value"] == 5.5 and by_index[4]["score"] == [0, 5.5, 1.25]
    points = projected["progress"]["points"]
    assert [point["primary_value"] for point in points] == [None, None, 0, 5.5]
    assert [point["score"] for point in points] == [[2, None, None], [1, None, None], [1, 0, 0], [0, 5.5, 1.25]]
    assert [point["evaluation_scope"] for point in points] == [None, None, None, {"incomplete_batch_ids": []}]
    assert projected["candidate"]["final_metrics"]["total_tardiness_hours"] == 0
    ordinary = project_public_result_summary({"algo": {"attempts": attempts, "improvement_trace": scoped["artifact"]["improvement_trace"]}})
    assert [item["score"] for item in ordinary["algo"]["attempts"]] == [point["score"] for point in points]
    assert [item["score"] for item in ordinary["algo"]["improvement_trace"]] == [point["score"] for point in points]

    graph = deepcopy(row)
    origins = ("graph_ready_v2_generated", "graph_ready_v2_repaired", "graph_ready_v2_iterated_greedy")
    labels = ("按规则生成排法", "局部调整排法", "继续调整工序顺序")
    graph_attempts = [{"candidate_origin": origin, "weight_profile_slug": "profile-" + str(index),
                       "tag": "graph_ready:profile|sgs:slack", "score": [0, 1, 1.5], "metrics": {"overdue_count": 1}}
                      for index, origin in enumerate(origins, 1)]
    graph["artifact"]["attempts"] = graph_attempts
    graph_projection = candidate_process(graph, [graph])
    assert [item["source_label"] for item in graph_projection["attempts"]] == list(labels)
    assert [item["candidate_origin"] for item in graph_projection["attempts"]] == list(origins)
    assert [item["weight_profile_slug"] for item in graph_projection["attempts"]] == ["profile-1", "profile-2", "profile-3"]
    assert all(item[key] is None for item in graph_projection["attempts"] for key in ("elapsed_ms", "event_index", "accepted", "verified", "strict_improved", "comparison"))
    public_attempts, _diagnostics = project_attempts(graph_attempts)
    assert project_attempts(public_attempts)[0] == public_attempts
    summary = project_public_result_summary({"algo": {"attempts": public_attempts}})
    assert summary["algo"]["attempts"] == public_attempts

    # Freeze the recorded object and decisions; comparison is independent of representative rank.
    metrics = {"failed_ops": 0, "overdue_count": 1, "weighted_tardiness_hours": 1.5, "total_tardiness_hours": 1.5,
               "makespan_hours": 2.5, "changeover_count": 0}
    complete = {"expected_operation_count": 1, "missing_operation_count": 0, "unexpected_result_count": 0,
                "complete_batch_count": 1, "incomplete_batch_count": 0}
    comparator = {"kind": "incumbent", "state": "comparable", "objective_name": "min_overdue", "objective_scope": "all_batches",
                  "reference_scope": "all_batches", "reference_score": [0, 1, 1.5, 1.5, 2.5, 0],
                  "reference_metrics": metrics, "reference_completion": complete, "metric_deltas": dict.fromkeys(COMPARISON_METRIC_KEYS, 0)}
    for attempt in graph_attempts:
        attempt.update(score=[0, 1, 1.5, 1.5, 2.5, 0], failed_ops=0,
                       metrics={**{key: value for key, value in metrics.items() if key != "failed_ops"},
                                "completion": {**complete, "objective_scope": "all_batches"}})
    first = {**deepcopy(comparator), "kind": "none", "state": "no_reference", "reference_scope": None,
             "reference_score": None, "reference_metrics": None, "reference_completion": None, "metric_deltas": None}
    graph_attempts[0].update(elapsed_ms=10, event_index=1, accepted=True, verified=True, strict_improved=None, comparison=first)
    graph_attempts[1].update(elapsed_ms=32, event_index=7, accepted=True, verified=True, strict_improved=False, comparison=deepcopy(comparator))
    graph_attempts[1]["comparison"]["reference_completion"]["incomplete_batch_ids"] = ["PRIVATE-BATCH"]
    graph_attempts[1]["comparison"]["reference_metrics"]["machine_id"] = "PRIVATE-MACHINE"
    graph_attempts[2].update(elapsed_ms=19, event_index=4, accepted=True, verified=True, strict_improved=True, comparison=deepcopy(comparator))
    graph_attempts[2]["comparison"]["reference_metrics"]["total_tardiness_hours"] = 2.5
    graph_attempts[2]["comparison"]["reference_score"][3] = 2.5
    graph_attempts[2]["comparison"]["metric_deltas"]["total_tardiness_hours"] = -1.0
    facts = candidate_process(graph, [graph])["attempts"]
    assert facts[0]["comparison"] == first and facts[0]["strict_improved"] is None
    assert facts[1]["accepted"] is True and facts[1]["strict_improved"] is False
    assert facts[1]["elapsed_ms"] == 32 and facts[2]["elapsed_ms"] == 19
    assert facts[1]["comparison"] == comparator
    assert facts[2]["comparison"]["metric_deltas"]["total_tardiness_hours"] == -1.0
    assert "PRIVATE" not in json.dumps(facts)
    public(facts)
    ordinary = project_public_result_summary({"algo": {"attempts": graph_attempts}})
    repeated = project_public_result_summary(ordinary)
    assert ordinary == repeated
    assert ordinary["algo"]["attempts"][1]["comparison"] == comparator


def test_failed_not_started_and_missing_reuse_sources_keep_availability_explicit():
    failed, skipped, reused, old_skipped, budget_skipped = (format(index, "048x") for index in range(1, 6))
    rows = [
        {"candidate_ref": failed, "status": "failed", "artifact": {"label": "失败候选", "failure_reason": "测试失败原因"}},
        {"candidate_ref": skipped, "status": "skipped", "artifact": {"label": "未启动候选",
            "failure_reason": "candidate_time_budget_reached", "process_evidence": non_search_evidence(
                "min_overdue", kind="not_started", reason="candidate_time_budget_reached", known_not_started=True)}},
        {"candidate_ref": reused, "status": "completed", "artifact": {"label": "缺来源复用候选",
            "reused_from_candidate_key": "old-missing-source", "elapsed_seconds": 0.001}},
        {"candidate_ref": old_skipped, "status": "skipped", "artifact": {"label": "旧跳过候选", "failure_reason": "历史预算结束"}},
        {"candidate_ref": budget_skipped, "status": "skipped", "artifact": {"label": "预算中断候选",
            "failure_reason": "candidate_time_budget_reached", "process_evidence": non_search_evidence(
                "min_overdue", kind="budget_skipped", reason="candidate_time_budget_reached")}},
    ]
    source = process_source(rows[:2])
    result = process_details(source, normalize_process_filters())
    assert result["candidate"]["candidate_ref"] == failed and result["scope"]["selected_candidate_ref"] is None
    assert result["source"]["kind"] == "failed" and result["source"]["available"] is False
    assert result["candidate"]["stop_reason"]["message"] == "测试失败原因"
    assert result["items"] == [] and result["progress"]["mode"] == "none"
    assert set(result["summary"]["own_counts"].values()) == {None}
    not_started = candidate_process(rows[1], rows)
    assert not_started["source"]["kind"] == "not_started" and not_started["source"]["available"] is True
    assert not_started["source"]["evidence_state"] == "complete" and not_started["progress"]["mode"] == "none"
    assert not_started["summary"]["own_counts"] == dict.fromkeys(COUNT_KEYS, 0)
    assert not_started["candidate"]["stop_reason"]["code"] == "candidate_time_budget_reached"
    missing = candidate_process(rows[2], rows)
    assert missing["source"]["kind"] == "reused" and missing["source"]["available"] is False
    assert missing["source"]["source_candidate_ref"] is None
    assert missing["summary"]["own_counts"] == dict.fromkeys(COUNT_KEYS, 0)
    assert set(missing["summary"]["solver_counts"].values()) == {None}
    assert missing["progress"]["points"] == missing["attempts"] == []
    legacy_skip = candidate_process(rows[3], rows)
    assert legacy_skip["source"]["available"] is False and legacy_skip["source"]["evidence_state"] == "unavailable"
    assert set(legacy_skip["summary"]["own_counts"].values()) == {None}
    interrupted = candidate_process(rows[4], rows)
    assert interrupted["source"]["kind"] == "budget_skipped" and interrupted["source"]["available"] is False
    assert interrupted["source"]["evidence_state"] == "unavailable" and interrupted["progress"]["points"] == []
    assert interrupted["candidate"]["stop_reason"]["message"] == "本轮计算时间预算已用完"
    assert set(interrupted["summary"]["own_counts"].values()) == {None}
    assert interrupted["summary"]["source_solver_elapsed_ms"] is None
