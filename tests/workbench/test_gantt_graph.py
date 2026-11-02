"""Frozen full-scope Gantt graph from real worker output and adopted plans."""

import csv
from datetime import datetime, timedelta
from io import StringIO

from core.models.workbench_plan_scope import PlanReadScope
from core.models.workbench_run_candidate import RunCandidateReadScope
from core.services.workbench.facts.gantt_graph import (
    build_gantt_graph,
    project_scoped_gantt_graph,
    unavailable_graph,
)
from core.services.workbench.plan.export import HEADERS, write_plan_export
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from core.services.workbench.run.candidates import WorkbenchRunCandidateQueryService
from tests.workbench.ea_zero_duration_support import adopt as adopt_points
from tests.workbench.piece_chain_support import adopt_candidate, piece_candidate, piece_layout
from tests.workbench.piece_chain_support import trial_case as trial_case  # noqa: F401
from tests.workbench.run_candidate_support import compute, public


def candidate_workspace(case, candidate_ref, **scope):
    data, _ = WorkbenchRunCandidateQueryService(case.conn).workspace(
        RunCandidateReadScope(candidate_ref, **scope), bind_snapshot=lambda scope, state: state)
    public(data)
    return data


def plan_workspace(case, plan_ref, **scope):
    service = WorkbenchPlanQueryService(case.conn)
    with service.read_snapshot():
        read_scope = PlanReadScope(plan_ref, **scope)
        data, state = service.workspace(read_scope)
        summary_graph = data["gantt_graph"]
        graph_data, graph_scope, graph_state = service.gantt_graph(read_scope)
        assert graph_scope == data["scope"] and graph_state == state
        full_graph = graph_data["gantt_graph"]
        if summary_graph["state"] == "available":
            assert summary_graph["nodes"] == []
            assert summary_graph["node_count"] == full_graph["node_count"] == len(full_graph["nodes"])
            assert summary_graph["nodes_complete"] == (summary_graph["node_count"] == 0)
            assert full_graph["nodes_complete"] is True
        else:
            assert summary_graph == full_graph
        data["gantt_graph"] = full_graph
        return data


def operation_refs(case):
    return {int(row[0]): row[1] for row in case.conn.execute(
        "SELECT source_key,ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1")}


def assert_mixed_graph(case, ids, data, *, candidate):
    graph = data["gantt_graph"]
    assert graph["state"] == "available" and graph["reason"] is None
    assert graph["scope"] == ("full_candidate" if candidate else "full_plan")
    if not candidate:
        assert set(data["projections"]["process_order"]) == {"state", "basis", "issues"}
    stored_refs = operation_refs(case)
    refs = {key: stored_refs[op_id] for key, op_id in ids.items()}
    nodes = {row["operation_ref"]: row for row in graph["nodes"]}
    assert set(nodes) == set(refs.values())
    task_refs = {row["operation_ref"]: row["row_ref" if candidate else "task_ref"] for row in data["tasks"]}
    process_labels = {row["operation_ref"]: row["process_label"] for row in data["tasks"]}
    assert {key: node["task_ref"] for key, node in nodes.items()} == task_refs
    for (piece, sequence), operation_ref in refs.items():
        assert nodes[operation_ref]["batch_id"] == "B1"
        assert nodes[operation_ref]["piece_id"] == piece
        assert nodes[operation_ref]["sequence"] == sequence
        assert nodes[operation_ref]["process_label"] == process_labels[operation_ref]
    by_task = {row["task_ref"]: row["operation_ref"] for row in graph["nodes"]}
    assert "edges" not in graph
    actual = {(parent, node["operation_ref"], "process")
              for node in graph["nodes"] for parent in node["predecessor_operation_refs"]}
    expected = set()
    for piece in ("item-A", "item-B", "item-C"):
        for previous, following in (((None, 10), (piece, 20)), ((piece, 20), (piece, 30)),
                                    ((piece, 30), (None, 40))):
            expected.add((refs[previous], refs[following], "process"))
    assert actual == expected
    assert graph["critical_task_refs"]
    assert set(graph["critical_task_refs"]) <= set(by_task)
    assert graph["critical_edges"]
    for edge in graph["critical_edges"]:
        assert edge["from_task_ref"] in graph["critical_task_refs"]
        assert edge["to_task_ref"] in graph["critical_task_refs"]
        assert edge["edge_type"] in {"process", "machine", "operator"}
    return graph


def test_candidate_and_adopted_graph_keep_full_frozen_route_across_range_and_bom_changes(trial_case):
    case = trial_case
    ids, _, refs = piece_candidate(case)
    candidate = candidate_workspace(case, refs[0])
    candidate_graph = assert_mixed_graph(case, ids, candidate, candidate=True)
    plan_ref = adopt_candidate(case, refs[0])["data"]["official_plan"]["plan_ref"]
    plan = plan_workspace(case, plan_ref)
    plan_graph = assert_mixed_graph(case, ids, plan, candidate=False)

    from unittest.mock import Mock

    from core.services.workbench.facts import candidate_tasks

    # Only show the initial common operation; graph relations still cover its successors.
    first = min(candidate["tasks"], key=lambda row: row["start"])
    scope = {"range_start": first["start"], "range_end": first["end"]}
    original_task_dto = candidate_tasks._task_dto
    task_dto_spy = Mock(wraps=original_task_dto)
    for reader, ref, full_graph in ((candidate_workspace, refs[0], candidate_graph),
                                   (plan_workspace, plan_ref, plan_graph)):
        if reader is candidate_workspace:
            candidate_tasks._task_dto = task_dto_spy
        try:
            narrowed = reader(case, ref, **scope)
        finally:
            candidate_tasks._task_dto = original_task_dto
        assert 0 < len(narrowed["tasks"]) < len(ids)
        assert narrowed["gantt_graph"] == full_graph
    assert task_dto_spy.call_count == len(ids)
    case.conn.execute("UPDATE BatchOperations SET unit_hours=2,op_type_name='Current renamed operation'")
    case.conn.execute("UPDATE Batches SET quantity=4 WHERE batch_id='B1'")
    case.conn.commit()

    assert candidate_workspace(case, refs[0])["gantt_graph"] == candidate_graph
    assert plan_workspace(case, plan_ref)["gantt_graph"] == plan_graph

    # Changing operation identity invalidates an adopted binding instead of reconnecting it to the new BOM.
    case.conn.execute("UPDATE BatchOperations SET seq=100-seq,"
                      "piece_id=CASE WHEN piece_id IS NULL THEN NULL ELSE 'changed-'||piece_id END")
    case.conn.commit()
    assert candidate_workspace(case, refs[0])["gantt_graph"] == candidate_graph
    invalidated = plan_workspace(case, plan_ref)["gantt_graph"]
    assert invalidated["state"] == "unavailable" and invalidated["reason"]
    assert invalidated["nodes"] == invalidated["critical_task_refs"] == invalidated["critical_edges"] == []
    assert "edges" not in invalidated


def test_zero_duration_split_and_join_are_graph_nodes_after_adoption(trial_case, monkeypatch):
    from core.services.capacity.plan_calendar_io import CalendarFacts
    from core.services.workbench.execution.actual_gantt import ActualGanttService
    from core.services.workbench.execution.actual_gantt_scope import ActualGanttScope

    case = trial_case
    ids = piece_layout(case)
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0 WHERE seq IN (20,40)")
    case.conn.commit()
    _, refs = compute(case)
    assert refs
    candidate = candidate_workspace(case, refs[0])
    graph = assert_mixed_graph(case, ids, candidate, candidate=True)
    stored_refs = operation_refs(case)
    point_refs = {stored_refs[op_id] for (_, seq), op_id in ids.items() if seq in (20, 40)}
    assert {row["operation_ref"] for row in graph["nodes"] if row["start"] == row["end"]} == point_refs
    plan_ref = adopt_points(case, refs[0])["plan_ref"]
    plan = plan_workspace(case, plan_ref)
    graph = assert_mixed_graph(case, ids, plan, candidate=False)
    assert {row["operation_ref"] for row in graph["nodes"] if row["start"] == row["end"]} == point_refs
    assert plan["plan_span"]["end_inclusive"] is True
    terminal = [row for row in plan["tasks"] if row["start"] == row["end"] == plan["plan_span"]["end"]]
    assert terminal
    snapshot = {"snapshot_ref": "point-plan-export", "as_of": "2026-09-10T12:00:00"}
    full = list(csv.DictReader(StringIO(write_plan_export(plan, snapshot, "csv").content.decode("utf-8-sig"))))
    assert tuple(full[0]) == HEADERS
    assert "范围终点（不含）" not in full[0] and "范围终点" in full[0]
    assert len(full) == plan["task_count"]
    assert all(row["时间计算方式"] == "'包含末端零工时工序" for row in full)
    terminal_refs = {row["task_ref"] for row in terminal}
    assert {"'" + ref for ref in terminal_refs} <= {row["任务编号"] for row in full}
    explicit = plan_workspace(case, plan_ref, range_start=plan["plan_span"]["start"], range_end=plan["plan_span"]["end"])
    assert not terminal_refs & {row["task_ref"] for row in explicit["tasks"]}
    half_open = list(csv.DictReader(StringIO(write_plan_export(explicit, snapshot, "csv").content.decode("utf-8-sig"))))
    assert len(half_open) == explicit["task_count"] == plan["task_count"] - len(terminal)
    assert all(row["时间计算方式"] == "'含起点，不含结束时刻" for row in half_open)
    assert all(row["范围终点"] == "'" + plan["plan_span"]["end"] for row in full + half_open)

    start_day = datetime.fromisoformat(plan["plan_span"]["start"]).date()
    midnight_end = datetime.combine(start_day + timedelta(days=1), datetime.min.time()).isoformat()
    calendar_ranges = []
    original_calendar = CalendarFacts.calendar

    def record_calendar(self, first_iso, last_iso, operators):
        calendar_ranges.append((first_iso, last_iso))
        return original_calendar(self, first_iso, last_iso, operators)

    monkeypatch.setattr(CalendarFacts, "calendar", record_calendar)
    plan_workspace(case, plan_ref, range_start=plan["plan_span"]["start"], range_end=midnight_end)
    actual_service = ActualGanttService(case.conn)
    with actual_service.read_snapshot():
        actual_service.workspace(
            ActualGanttScope(plan_ref, range_start=plan["plan_span"]["start"], range_end=midnight_end),
            full_workspace=True,
        )
    expected_range = ((start_day - timedelta(days=1)).isoformat(), start_day.isoformat())
    assert calendar_ranges == [expected_range, expected_range]


def test_shared_graph_keeps_20k_nodes_all_predecessors_and_complete_critical_facts():
    start = datetime(2026, 1, 1, 8)
    tasks, relations, task_intervals = [], {}, {}
    missing = format(40001, "048x")
    for index in range(20000):
        task_ref = format(index + 1, "048x")
        operation_ref = format(20001 + index, "048x")
        sequence = index % 100
        start_dt = start + timedelta(hours=sequence)
        end_dt = start + timedelta(hours=sequence + 1)
        tasks.append({"task_ref": task_ref, "operation_ref": operation_ref,
            "batch_id": "B" + str(index // 100), "piece_id": "piece-a", "sequence": sequence + 1,
            "process_label": "Operation " + str(sequence + 1),
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "machine_ref": None, "operator_ref": None})
        task_intervals[task_ref] = (start_dt, end_dt)
        relations[operation_ref] = [format(20000 + index, "048x")] if sequence else []
    relations[tasks[0]["operation_ref"]] = [missing]
    graph = build_gantt_graph(tasks, relations, scope="full_plan", task_intervals=task_intervals)
    assert set(graph) == {"state", "reason", "scope", "nodes", "critical_task_refs", "critical_edges"}
    assert graph["state"] == "available" and len(graph["nodes"]) == 20000
    assert {node["operation_ref"]: node["predecessor_operation_refs"] for node in graph["nodes"]} == relations
    assert graph["nodes"][0]["predecessor_operation_refs"] == [missing]
    assert all(node["piece_id"] == "piece-a" for node in graph["nodes"])
    assert len(graph["critical_task_refs"]) == 100 and len(graph["critical_edges"]) == 99
    assert all(edge["edge_type"] == "process" for edge in graph["critical_edges"])


def test_plan_and_candidate_public_dtos_isolate_in_process_caches_on_mutation(trial_case, monkeypatch):
    from copy import deepcopy

    import pytest

    from core.services.workbench.execution.actual_gantt import ActualGanttService
    from core.services.workbench.execution.actual_gantt_scope import ActualGanttScope
    from core.services.workbench.facts import resource_intervals
    from core.services.workbench.facts.candidate_store import CandidateStore
    from core.services.workbench.run import decision_source
    from core.services.workbench.run.candidate_baseline import (
        WorkbenchRunCandidateBaselineQueryService,
    )
    from core.services.workbench.run.decision_impact import operation_impacts
    from core.services.workbench.run.decision_preparation import DecisionPreparation
    from core.services.workbench.run.decision_source import DecisionSource
    from data.repositories.workbench_run_repo import WorkbenchRunRepository

    case = trial_case
    _, run_ref, refs = piece_candidate(case)
    candidate_ref = refs[0]

    official_saved = DecisionSource(CandidateStore(case.conn), run_ref, comparison_mode="admission_official")
    assert official_saved.official_changed is False
    with monkeypatch.context() as official_reread_scope:
        official_reread_scope.setattr(WorkbenchRunRepository, "dependencies_match", lambda _self, _expected: False)
        official_reread_scope.setattr(
            resource_intervals,
            "task_interval",
            lambda _row: pytest.fail("resource_cohort should reuse prepared reference task_intervals"),
        )
        official_reread_scope.setattr(
            decision_source,
            "task_interval",
            lambda _row: pytest.fail("DecisionSource should reuse official_details task_intervals"),
        )
        official_reread = DecisionSource(CandidateStore(case.conn), run_ref, comparison_mode="admission_official")
        assert official_reread.official_changed is True
        assert official_reread.resource_cohort == official_saved.resource_cohort

    cand_first, _ = WorkbenchRunCandidateQueryService(case.conn).workspace(RunCandidateReadScope(candidate_ref), bind_snapshot=lambda scope, state: state)
    cand_expected = deepcopy(cand_first)
    cand_first["candidate"]["representative_objectives"].append("polluted-objective")
    cand_first["candidate"]["evaluations"]["polluted"] = {"value": 999}
    cand_first["candidate"]["origin"]["polluted"] = True
    cand_first["generation"]["algorithm"]["evaluations"]["polluted"] = {"value": 999}
    cand_first["generation"]["algorithm"]["origin"]["polluted"] = True
    cand_first["generation"]["algorithm"]["target_objectives"].append("polluted-target")

    cand_second, _ = WorkbenchRunCandidateQueryService(case.conn).workspace(RunCandidateReadScope(candidate_ref), bind_snapshot=lambda scope, state: state)
    assert cand_second == cand_expected

    plan_ref = adopt_candidate(case, candidate_ref)["data"]["official_plan"]["plan_ref"]

    service_one = WorkbenchPlanQueryService(case.conn)
    with service_one.read_snapshot():
        graph_first, _, _ = service_one.gantt_graph(PlanReadScope(plan_ref))
    graph_expected = deepcopy(graph_first)
    graph_first["gantt_graph"]["nodes"][0]["process_label"] = "POLLUTED"
    graph_first["gantt_graph"]["nodes"][0]["predecessor_operation_refs"].append("d" * 48)
    graph_first["gantt_graph"]["critical_task_refs"].append("c" * 48)
    graph_first["gantt_graph"]["critical_edges"][0]["edge_type"] = "polluted"
    graph_first["gantt_graph"]["nodes"].clear()

    service_two = WorkbenchPlanQueryService(case.conn)
    with service_two.read_snapshot():
        graph_second, _, _ = service_two.gantt_graph(PlanReadScope(plan_ref))
    assert graph_second == graph_expected

    actual_one = ActualGanttService(case.conn)
    with actual_one.read_snapshot():
        actual_first, _ = actual_one.workspace(ActualGanttScope(plan_ref), full_workspace=True)
    actual_expected = deepcopy(actual_first)
    actual_first["gantt_graph"]["nodes"][0]["process_label"] = "POLLUTED"
    actual_first["gantt_graph"]["nodes"][0]["predecessor_operation_refs"].append("d" * 48)
    actual_first["gantt_graph"]["critical_task_refs"].append("c" * 48)
    actual_first["gantt_graph"]["critical_edges"][0]["edge_type"] = "polluted"
    actual_first["gantt_graph"]["nodes"].clear()

    actual_two = ActualGanttService(case.conn)
    with actual_two.read_snapshot():
        actual_second, _ = actual_two.workspace(ActualGanttScope(plan_ref), full_workspace=True)
    assert actual_second == actual_expected

    service_three = WorkbenchPlanQueryService(case.conn)
    with service_three.read_snapshot():
        graph_third, _, _ = service_three.gantt_graph(PlanReadScope(plan_ref))
    assert graph_third == graph_expected

    base_first, _ = WorkbenchRunCandidateBaselineQueryService(case.conn).baseline(RunCandidateReadScope(candidate_ref), bind_snapshot=lambda scope, state: state)
    base_expected = deepcopy(base_first)
    base_first["generation"]["input"]["batch_refs"].append("polluted")
    base_first["generation"]["input"]["polluted"] = True
    base_second, _ = WorkbenchRunCandidateBaselineQueryService(case.conn).baseline(RunCandidateReadScope(candidate_ref), bind_snapshot=lambda scope, state: state)
    assert base_second == base_expected

    decision_one = DecisionSource(CandidateStore(case.conn), run_ref)
    prep_refs = decision_one.scope["operation_refs"]
    prep_impacts_first = DecisionPreparation(decision_one).impacts(prep_refs)
    prep_impacts_expected = deepcopy(prep_impacts_first)
    prep_impacts_first[0]["after"]["evidence_source"]["run_ref"] = "POLLUTED"
    prep_impacts_first[0]["after"]["data_gaps"].append({"field": "runtime_requirement", "code": "polluted", "message": "POLLUTED"})
    prep_impacts_first[0]["after"]["standard"]["evidence_source"]["run_ref"] = "POLLUTED"
    assert DecisionPreparation(DecisionSource(CandidateStore(case.conn), run_ref)).impacts(prep_refs) == prep_impacts_expected

    impacts_first = operation_impacts(decision_one)
    impacts_expected = deepcopy(impacts_first)
    impacts_first[0]["constraints"]["reasons"].append({"code": "polluted"})

    decision_two = DecisionSource(CandidateStore(case.conn), run_ref)
    assert operation_impacts(decision_two) == impacts_expected

    first_op_ref = decision_two.scope["operation_refs"][0]
    decision_two.disposition[first_op_ref] = {
        **decision_two.disposition[first_op_ref],
        "issues": [{"code": "protected_issue", "message": "original"}],
    }
    disposition_expected = deepcopy(decision_two.disposition[first_op_ref])
    impacts_with_issue = operation_impacts(decision_two, [first_op_ref])
    impacts_with_issue_expected = deepcopy(impacts_with_issue)
    impacts_with_issue[0]["constraints"]["reasons"][0]["message"] = "POLLUTED"
    impacts_with_issue[0]["constraints"]["reasons"].append({"code": "polluted"})
    assert decision_two.disposition[first_op_ref] == disposition_expected
    assert operation_impacts(decision_two, [first_op_ref]) == impacts_with_issue_expected

    cached_unavailable = unavailable_graph("full_plan", "工序顺序数据不完整。")
    scoped_unavailable = project_scoped_gantt_graph(cached_unavailable, {"B1"}, include_nodes=True)
    scoped_unavailable["nodes"].append({"task_ref": "polluted"})
    scoped_unavailable["critical_task_refs"].append("polluted")
    scoped_unavailable["critical_edges"].append({"from_task_ref": "polluted"})
    assert cached_unavailable["nodes"] == []
    assert cached_unavailable["critical_task_refs"] == []
    assert cached_unavailable["critical_edges"] == []
