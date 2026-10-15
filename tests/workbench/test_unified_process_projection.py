"""Shared saved facts keep objective units, origins and full scopes in one export."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from core.models.objective import best_score_schema
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.scheduler.run.optimizer.shared_process import UNIFIED_PROCESS_VERSION, build_shared_process
from core.services.scheduler.run.schedule_shared_optimizer import _SharedSearch
from core.services.workbench.facts.candidate_process import candidate_process
from core.services.workbench.facts.unified_process import project_unified_process
from core.services.workbench.run.decision_process import (
    normalize_process_filters,
    process_details,
    process_export_records,
)
from core.services.workbench.run.decision_process_export import (
    ATTEMPT_HEADERS,
    CANDIDATE_HEADERS,
    PROCESS_CSV_HEADERS,
    PROGRESS_HEADERS,
    STAGE_HEADERS,
    process_csv,
    process_export_tables,
)
from tests._support.shared_schedule_archive import _archive, _candidate, _failure, _observe_decoded, _result


def test_shared_process_projection_and_export_keep_actual_objectives_and_one_run():
    targets = ["min_overdue", "min_tardiness", "min_changeover"]
    reference = lambda value: format(value, "048x")
    run_ref, first_ref, viewer_ref = reference(900), reference(901), reference(902)
    full_operations = [reference(index) for index in range(1, 701)]
    scopes = {"1": {"scheduled_operation_refs": full_operations[:1], "complete_batch_refs": [reference(800)],
                    "objective_scope": "completed_batches_only", "components_known": False, "is_complete": False},
              "2": {"scheduled_operation_refs": full_operations, "complete_batch_refs": [reference(800), reference(801)],
                    "objective_scope": "all_batches", "components_known": True, "is_complete": True}}
    events = [{"event_id": index, "event_type": "archive_observation", "elapsed_ms": elapsed,
               "search_objective": "min_overdue", "phase": phase, "verified": verified,
               "entry_id": index, "scope_ref": scope_ref, "origin": "actual-test-construction"}
              for index, elapsed, phase, verified, scope_ref in (
                  (1, 10, "initial_construct", False, "2"), (2, 20, "initial_construct", True, "1"),
                  (3, 35, "improve", True, "2"))]
    actions = [{"action_id": index, "search_objective": objective, "phase": phase,
                "initial_construction": initial, "started_elapsed_ms": start, "finished_elapsed_ms": end,
                "elapsed_ms": end - start, "evaluation_count": evaluations, "verified_evaluation_count": verified,
                "new_decisions": decisions, "reused_decisions": reuses, "skip_reason": reason,
                "improved_objectives": targets if index == 2 else []}
               for index, objective, phase, initial, start, end, evaluations, verified, decisions, reuses, reason in (
                   (1, "min_overdue", "initial_construct", True, 0, 25, 2, 1, 2, 0, None),
                   (2, "min_overdue", "improve", False, 25, 100, 1, 1, 1, 1, None),
                   (3, "min_changeover", "improve", False, 100, 100, 0, 0, 0, 0, "time_budget"))]
    goal_budgets = {name: {"objective_status": "searched" if name == "min_overdue" else "not_searched_budget",
        "weight": 0.6 if name == "min_overdue" else 0.2, "elapsed_seconds": 0.1 if name == "min_overdue" else 0,
        "charged_seconds": 0.11 if name == "min_overdue" else 0, "preparation_seconds": 0.01 if name == "min_overdue" else 0,
        "action_count": sum(action["search_objective"] == name for action in actions),
        "new_decisions": sum(action["new_decisions"] for action in actions if action["search_objective"] == name),
        "reused_decisions": sum(action["reused_decisions"] for action in actions if action["search_objective"] == name),
        "probe_decisions": 1 if name == "min_overdue" else 0, "minimum_opportunity": name == "min_overdue",
        "improvement_action_count": 1 if name == "min_overdue" else 0, "has_gain": name == "min_overdue",
        "feedback_rate": 1 if name == "min_overdue" else 0, "feedback_bonus": 0, "unavailable_reason": None,
        "budget_reason": None if name == "min_overdue" else "time_budget",
        "phase_elapsed_seconds": {"prepare_view": 0.01, "initial_construct": 0.025, "improve": 0.075} if name == "min_overdue"
                                  else {"improve": 0} if name == "min_changeover" else {}}
        for name in targets}
    metric_values = {"failed_ops": 0, "overdue_count": 2, "total_tardiness_hours": 5.5,
                     "weighted_tardiness_hours": 7.75, "makespan_hours": 3, "changeover_count": 4}
    trajectories = {}
    for name in targets:
        order = [field["key"] for field in best_score_schema(name)]
        points = [{"elapsed_ms": elapsed, "entry_id": entry_id, "source_event_id": entry_id,
                   "search_objective": "min_overdue", "origin": "actual-test-construction", "field_order": order,
                   "score": [699] + [None] * (len(order) - 1) if scope_ref == "1" else [metric_values[key] for key in order],
                   "scope_ref": scope_ref, "segment": segment, "flags": flags}
                  for elapsed, entry_id, scope_ref, segment, flags in (
                      (20, 2, "1", 0, []), (35, 3, "2", 1, ["first_valid", "first_expected_complete"]),
                      (100, 3, "2", 1, ["final"]))]
        trajectories[name] = {**goal_budgets[name], "archive_improvement_count": 1, "best_entry_id": 3,
            "first_improvement_elapsed_ms": 35, "last_improvement_elapsed_ms": 35,
            "points": points, "sampling": {"policy": "elapsed_bucket_min", "point_budget": 200,
                "event_total_count": 3, "retained_point_count": 3, "bucket_count": 1, "bucket_width_ms": 0.5,
                "mandatory": ["first_valid", "first_expected_complete", "final"]}}
    bridge = {"search_objective": "min_overdue", "phase": "controlled_reference_order", "before_entry_id": 2,
        "after_entry_id": 3, "elapsed_ms": 2.5, "started_elapsed_ms": 33, "finished_elapsed_ms": 35,
        "same_arrangement": False, "decoder_executed": True, "reference_kind": "controlled_reference_order", "source_event_id": 4}
    events.append({**bridge, "event_id": 4, "event_type": "reference_capture", "elapsed_ms": 35, "verified": False})
    process = {"version": UNIFIED_PROCESS_VERSION, "clock": "shared_monotonic", "elapsed_ms": 100,
        "stop_reason": "time_budget", "primary_objective": "min_overdue", "target_objectives": targets,
        "counts": {"actual_decoder_calls": 3, "new_decisions": 3, "decision_reuses": 1, "skipped_requests": 1,
                   "failed_decoder_calls": 0, "request_count": 4, "execution_counts": {"decoder_executed": 3, "local_reuse": 1}},
        "budget": {"configured_seconds": 10, "elapsed_seconds": 0.1, "actual_decoder_count": 3,
                   "first_complete_elapsed_seconds": 0.01, "objectives": goal_budgets},
        "events": events, "actions": actions, "bridges": [bridge], "targets": trajectories, "scopes": scopes}
    candidates = [{"candidate_ref": ref, "label": label, "status": "completed", "representative_objectives": goals,
                   "origin": "actual-test-construction", "first_found_elapsed_ms": 35,
                   "search_evidence_ref": {"run_ref": run_ref, "source_event_id": 3}}
                  for ref, label, goals in ((first_ref, "交期优先", targets[:2]), (viewer_ref, "切换更少", targets[2:]))]
    original = deepcopy(process)
    projected = project_unified_process(process, candidate=candidates[1], candidates=candidates)
    assert projected["summary"] == {"elapsed_ms": 100, "first_complete_elapsed_ms": 35,
                                    "first_improvement_elapsed_ms": 35, "last_improvement_elapsed_ms": 35}
    assert projected["selected_objective"]["name"] == "min_overdue"
    assert projected["candidate"]["candidate_ref"] == viewer_ref and projected["source_event"] == events[2]
    assert projected["counts"] == process["counts"] and projected["budget"] == process["budget"]
    assert projected["scopes"] == scopes and "score_scope" not in projected["progress"]["points"][0]
    assert [point["primary_value"] for point in projected["progress"]["points"]] == [None, 2, 2]
    assert [point["segment"] for point in projected["progress"]["points"]] == [0, 1, 1]
    assert projected["progress"]["sampling"] == trajectories["min_overdue"]["sampling"]
    assert projected["actions"] == actions[:2]
    stages = {row["phase"]: row for row in projected["stages"]}
    assert stages["prepare_view"]["start_elapsed_ms"] is None and stages["prepare_view"]["elapsed_ms"] == 10
    assert stages["improve"]["evaluation_count"] == stages["improve"]["verified_evaluation_count"] == 1
    assert stages["improve"]["elapsed_ms"] == 75 and stages["improve"]["reused_decisions"] == 1
    tardiness = project_unified_process(process, objective="min_tardiness")
    changeover = project_unified_process(process, objective="min_changeover")
    assert tardiness["selected_objective"]["unit"] == "小时" and tardiness["progress"]["points"][-1]["primary_value"] == 5.5
    assert changeover["selected_objective"]["unit"] == "次" and changeover["progress"]["points"][-1]["primary_value"] == 4
    assert tardiness["actions"] == [] and tardiness["budget"]["objectives"]["min_tardiness"]["objective_status"] == "not_searched_budget"
    for direction in (projected, tardiness, changeover):
        assert direction["summary"]["first_improvement_elapsed_ms"] == direction["summary"]["last_improvement_elapsed_ms"] == 35
    with pytest.raises(WorkbenchCommandRejected) as caught:
        project_unified_process(process, objective="min_weighted_tardiness")
    assert caught.value.code == "invalid_input" and caught.value.status == 422

    source = SimpleNamespace(run={"run_ref": run_ref}, rows=[{"candidate_ref": row["candidate_ref"]} for row in candidates],
        saved_process=process, selected_ref=first_ref, scope={"selected_candidate_ref": first_ref,
        "reference": {"candidate_ref": viewer_ref}}, baseline={"candidate_ref": viewer_ref})
    source._candidate_reference = lambda ref, require_result=True: next(row for row in candidates if row["candidate_ref"] == ref)
    source.saved_candidate_catalog = lambda ref, fields=None: {key: value for key, value in next(
        row for row in candidates if row["candidate_ref"] == ref).items() if fields is None or key in fields}
    initial_scope = deepcopy(source.scope)
    details = process_details(source, normalize_process_filters(process_candidate_ref=viewer_ref), size=20, page=2)
    assert details["candidate"]["candidate_ref"] == viewer_ref and details["source_event"] == events[2]
    assert details["selected_objective"]["name"] == details["filters"]["objective"] == "min_overdue"
    assert details["items"] == [] and details["page"] == {"number": 2, "size": 20, "total": 2, "has_more": False}
    assert details["actions"] == actions[:2] and all("rank" not in action and "primary_value" not in action for action in details["actions"])
    progress = process_details(source, normalize_process_filters(objective="min_tardiness", record_kind="progress",
        sort="primary_value", order="desc"), size=20)
    assert progress["selected_objective"]["unit"] == "小时" and progress["items"][0]["primary_value"] == 5.5
    assert progress["actions"] == [] and progress["page"]["total"] == 3
    assert source.scope == initial_scope and progress["scope"] == details["scope"]
    for filters in (normalize_process_filters(objective="min_weighted_tardiness"),
                    normalize_process_filters(record_kind="attempts", sort="primary_value")):
        with pytest.raises(WorkbenchCommandRejected) as caught:
            process_details(source, filters)
        assert caught.value.code == "invalid_input" and caught.value.status == 422
    exports = process_export_records(source)
    assert len(exports) == 1 and exports[0]["process"] is process and exports[0]["export_objectives"] == targets
    reversed_exports = process_export_records(source, normalize_process_filters(record_kind="progress", order="desc"))
    assert [row["elapsed_ms"] for row in reversed_exports[0]["projected"]["progress"]["points"]] == [100, 35, 20]
    assert [row["action_id"] for row in reversed_exports[0]["projected"]["actions"]] == [2, 1]
    filtered_filters = normalize_process_filters(process_candidate_ref=viewer_ref, objective="min_tardiness",
        record_kind="progress", sort="elapsed_ms", order="desc")
    filtered_exports = process_export_records(source, filtered_filters)
    assert len(filtered_exports) == 1 and filtered_exports[0]["export_objectives"] == ["min_tardiness"]
    all_filtered_exports = process_export_records(source, filtered_filters, include_all_objectives=True)
    assert len(all_filtered_exports) == 1 and all_filtered_exports[0]["export_objectives"] == targets
    assert all_filtered_exports[0]["projected"] == filtered_exports[0]["projected"]
    assert all_filtered_exports[0]["projected"]["candidate"]["candidate_ref"] == viewer_ref
    assert all_filtered_exports[0]["projected"]["selected_objective"]["name"] == "min_tardiness"
    assert all_filtered_exports[0]["projected"]["scope"] == initial_scope

    data = {"run": {"run_ref": run_ref}, "capture_ref": run_ref,
        "scope": {"selected_candidate_ref": first_ref, "comparison_mode": "candidates", "range_start": None, "range_end": None,
                  "resource_view": "selected_batches"}, "baseline": {"kind": "candidate", "candidate_ref": viewer_ref},
        "selection_basis": {"selection_evidence_version": "business_objectives_v1"},
        "recommendation": {"candidate_ref": first_ref, "recommendation_version": "decision-recommendation-v1"},
        "export_process": [{"process_version": UNIFIED_PROCESS_VERSION, "process": process,
                            "export_objectives": targets, "projected": projected}]}
    snapshot = {"snapshot_ref": "s" * 32, "as_of": "2026-10-15T01:30:00"}
    tables = process_export_tables(data, snapshot)
    rows = lambda title: [dict(zip(tables[title][0], row)) for row in tables[title][1]]
    assert len(rows("共同计算")) == len(rows("真实桥接")) == 1
    assert rows("共同计算")[0]["共同跳过执行次数"] == process["counts"]["skipped_requests"]
    assert rows("共同计算")[0]["共同不同决策请求数"] == process["counts"]["request_count"]
    assert "共同跳过请求数" not in tables["共同计算"][0] and "共同决策请求数" not in tables["共同计算"][0]
    assert rows("共同计算")[0]["保存推荐候选编号"] == first_ref and rows("共同计算")[0]["查看基准编号"] == viewer_ref
    assert len(rows("目标预算")) == 3 and len(rows("评价范围")) == 2
    all_filtered_tables = process_export_tables({**data, "export_process": all_filtered_exports}, snapshot)
    all_filtered_rows = lambda title: [dict(zip(all_filtered_tables[title][0], row)) for row in all_filtered_tables[title][1]]
    assert [row["优化方向"] for row in all_filtered_rows("目标预算")] == targets
    assert len(all_filtered_rows("共同计算")) == 1
    assert all_filtered_rows("共同计算")[0]["查看过程候选编号"] == viewer_ref
    assert all_filtered_rows("共同计算")[0]["查看过程来源事件编号"] == events[2]["event_id"]
    assert [row["累计共同耗时（毫秒）"] for row in all_filtered_rows("进步事件")
            if row["优化方向"] == "min_tardiness"] == [100, 35, 20]
    assert len(all_filtered_tables["范围成员"][1]) == len(tables["范围成员"][1])
    for target in rows("目标预算"):
        assert target["首次真实评分改善（毫秒）"] == target["最后真实评分改善（毫秒）"] == 35
    members = rows("范围成员")
    assert len(members) == sum(len(scope[key]) for scope in scopes.values() for key in ("scheduled_operation_refs", "complete_batch_refs"))
    assert [row["成员永久编号"] for row in members if row["评价范围编号"] == "2" and row["成员类型"] == "scheduled_operation"] == full_operations
    assert [row["来源事件编号"] for row in rows("进步事件")[:3]] == [2, 3, 3]
    assert rows("真实桥接")[0]["桥接实际耗时（毫秒）"] == 2.5
    assert all("代表排名" not in row and "业务主值" not in row for row in rows("搜索动作"))
    headers, flat = process_csv(data, snapshot)
    flat = [dict(zip(headers, row)) for row in flat]
    assert sum(row["record_kind"] == "run_process_summary" for row in flat) == 1
    assert len(flat) == sum(len(table[1]) for table in tables.values())
    csv_rows = iter(flat)
    for title in tables:
        for row in rows(title):
            item = next(csv_rows)
            assert all(item[key] == value for key, value in row.items())
    last_changeover = next(row for row in flat if row["record_kind"] == "progress_point" and row["优化方向"] == "min_changeover" and row["累计共同耗时（毫秒）"] == 100)
    assert last_changeover["业务主值"] == 4 and last_changeover["评分分量1单位"] == "次" and last_changeover["评分分量1指标key"] == "changeover_count"
    data["export_process"][0]["export_objectives"] = ["min_tardiness"]
    filtered = process_export_tables(data, snapshot)
    assert len(filtered["目标预算"][1]) == 1 and len(filtered["共同计算"][1]) == 1 and len(filtered["范围成员"][1]) == len(members)
    assert process == original

    legacy = {"candidate_ref": first_ref, "status": "completed", "artifact": {"label": "旧候选", "kind": "baseline",
        "objective_name": "min_overdue", "elapsed_seconds": 0.25, "metrics": {"overdue_count": 1},
        "attempts": [{"tag": "start:0", "score": [0, 1, 2], "metrics": {"overdue_count": 1, "makespan_hours": 2}}]}}
    data["export_process"] = [candidate_process(legacy, [legacy])]
    legacy_tables = process_export_tables(data, snapshot)
    assert {title: table[0] for title, table in legacy_tables.items()} == {
        "候选计算": CANDIDATE_HEADERS, "进步事件": PROGRESS_HEADERS, "搜索阶段": STAGE_HEADERS, "代表尝试": ATTEMPT_HEADERS}
    assert process_csv(data, snapshot)[0] == PROCESS_CSV_HEADERS
    legacy_row = dict(zip(ATTEMPT_HEADERS, legacy_tables["代表尝试"][1][0]))
    assert legacy_row["业务主值"] == 1 and legacy_row["评分分量1单位"] == "批次" and legacy_row["评分分量5"] is None


    # Actual arrangements and metric computation feed the collector; finding an initial best is not improvement.
    worse = _candidate([_result(1, 5), _result(2, 7), _result(3, 9)], objective="min_overdue")
    better = _candidate([_result(1, 0), _result(3, 1), _result(2, 2)], objective="min_overdue")
    shared = _SharedSearch(archive=_archive("min_overdue"), clock=lambda: 0, started_at=0)
    shared.phase = "initial_construct"
    _observe_decoded(shared, "min_overdue", candidate=deepcopy(worse), origin="real_arrangement", verified=True, elapsed_ms=10)
    initial = build_shared_process(shared, runtime_ms=100, stop_reason="completed", decode_stats={}, budget_stats=process["budget"])
    assert shared.events[0]["initialized_objectives"] == targets and shared.events[0]["improved_objectives"] == []
    for target in initial["targets"].values():
        assert target["first_improvement_elapsed_ms"] is target["last_improvement_elapsed_ms"] is None
        assert all("strict_improvement" not in point["flags"] for point in target["points"])
    shared.phase = "improve"
    _observe_decoded(shared, "min_overdue", candidate=deepcopy(better), origin="real_arrangement", verified=True, elapsed_ms=15)
    _observe_decoded(shared, "min_overdue", candidate=deepcopy(better), origin="real_duplicate", verified=True, elapsed_ms=20)
    assert shared.events[1]["improved_objectives"] == targets
    assert shared.events[2]["content_reused"] and shared.events[2]["improved_objectives"] == []
    actual = build_shared_process(shared, runtime_ms=100, stop_reason="completed", decode_stats={}, budget_stats=process["budget"])
    for target in actual["targets"].values():
        assert target["first_improvement_elapsed_ms"] == target["last_improvement_elapsed_ms"] == 15
        assert [(point["elapsed_ms"], point["source_event_id"]) for point in target["points"]
                if "strict_improvement" in point["flags"]] == [(15, 2)]
        assert "strict_improvement" not in target["points"][0]["flags"]
        assert target["points"][-1]["elapsed_ms"] == 100 and target["points"][-1]["flags"] == ["final"]

    # The same real collector at the last bucket boundary loses its 999ms point while keeping the saved time.
    sampled = _SharedSearch(archive=_archive("min_overdue"), clock=lambda: 0, started_at=0)
    _observe_decoded(sampled, "min_overdue", candidate=deepcopy(worse), origin="real_arrangement", verified=True, elapsed_ms=10)
    _observe_decoded(sampled, "min_overdue", candidate=deepcopy(better), origin="real_arrangement", verified=True, elapsed_ms=999)
    sampled_process = build_shared_process(sampled, runtime_ms=1000, stop_reason="completed", decode_stats={}, budget_stats=process["budget"])
    for target in sampled_process["targets"].values():
        assert target["first_improvement_elapsed_ms"] == target["last_improvement_elapsed_ms"] == 999
        assert target["sampling"]["event_total_count"] == 3 and target["sampling"]["retained_point_count"] == 2
        assert [point["elapsed_ms"] for point in target["points"]] == [10, 1000]
        assert all("strict_improvement" not in point["flags"] for point in target["points"])
        assert target["points"][-1]["flags"] == ["final"]

    # Only strict changes within the same known partial scope count; new and unknown scopes initialize separately.
    partial = _SharedSearch(archive=_archive("min_overdue"), clock=lambda: 0, started_at=0)
    _observe_decoded(partial, "min_overdue", candidate=_candidate([_result(1, 5), _result(2, 7)], failures=(_failure(3),)),
                    origin="known_partial", verified=True, elapsed_ms=10)
    _observe_decoded(partial, "min_overdue", candidate=_candidate([_result(1, 0), _result(2, 2)], failures=(_failure(3),)),
                    origin="known_partial", verified=True, elapsed_ms=15)
    _observe_decoded(partial, "min_overdue", candidate=_candidate([_result(1, 0)]),
                    origin="unknown_partial", verified=True, elapsed_ms=25)
    _observe_decoded(partial, "min_overdue", candidate=_candidate([_result(1, 0), _result(3, 1)], failures=(_failure(2),)),
                    origin="other_partial_scope", verified=True, elapsed_ms=30)
    assert partial.events[0]["partial_group_improved_objectives"] == []
    assert partial.events[1]["improved_objectives"] == [] and partial.events[1]["partial_group_improved_objectives"] == targets
    assert partial.events[2]["partial_group_improved_objectives"] == partial.events[3]["partial_group_improved_objectives"] == []
    assert not partial.events[2]["score_scope"].components_known
    partial_process = build_shared_process(partial, runtime_ms=100, stop_reason="completed", decode_stats={}, budget_stats=process["budget"])
    for target in partial_process["targets"].values():
        assert target["first_improvement_elapsed_ms"] == target["last_improvement_elapsed_ms"] == 15
        assert [point["elapsed_ms"] for point in target["points"] if "strict_improvement" in point["flags"]] == [15]
        assert target["points"][-1]["flags"] == ["final"]

    # Point provenance must match the actual improving event, even when its score is unchanged.
    for mismatch in ({"elapsed_ms": 16}, {"entry_id": partial.events[0]["entry_id"]},
                     {"score_scope": partial.events[2]["score_scope"]}, {"score_scope": partial.events[3]["score_scope"]}):
        inconsistent = SimpleNamespace(archive=partial.archive, events=partial.events, actions=partial.actions,
            bridges=partial.bridges, evidence_event_ids=partial.evidence_event_ids, selected_entry=partial.selected_entry,
            trajectories={name: [{**partial.trajectories[name][1], **mismatch}] for name in targets})
        invalid = build_shared_process(inconsistent, runtime_ms=100, stop_reason="completed", decode_stats={}, budget_stats=process["budget"])
        for target in invalid["targets"].values():
            assert target["first_improvement_elapsed_ms"] is target["last_improvement_elapsed_ms"] is None
            assert all("strict_improvement" not in point["flags"] for point in target["points"])
