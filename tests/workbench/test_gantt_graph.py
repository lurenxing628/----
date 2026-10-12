"""Frozen full-scope Gantt graph from real worker output and adopted plans."""

from core.models.workbench_plan_scope import PlanReadScope
from core.models.workbench_run_candidate import RunCandidateReadScope
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from core.services.workbench.run.candidates import WorkbenchRunCandidateQueryService
from tests.workbench.ea_zero_duration_support import adopt as adopt_points
from tests.workbench.piece_chain_support import adopt_candidate, piece_candidate, piece_layout
from tests.workbench.piece_chain_support import trial_case as trial_case  # noqa: F401
from tests.workbench.run_candidate_support import compute, edit_capture, public


def candidate_workspace(case, candidate_ref, **scope):
    data, _ = WorkbenchRunCandidateQueryService(case.conn).workspace(
        RunCandidateReadScope(candidate_ref, **scope))
    public(data)
    return data


def plan_workspace(case, plan_ref, **scope):
    service = WorkbenchPlanQueryService(case.conn)
    with service.read_snapshot():
        return service.workspace(PlanReadScope(plan_ref, **scope))[0]


def operation_refs(case):
    return {int(row[0]): row[1] for row in case.conn.execute(
        "SELECT source_key,ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1")}


def assert_mixed_graph(case, ids, data, *, candidate):
    graph = data["gantt_graph"]
    assert graph["state"] == "available" and graph["reason"] is None
    assert graph["scope"] == ("full_candidate" if candidate else "full_plan")
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
    actual = {(by_task[edge["from_task_ref"]], by_task[edge["to_task_ref"]], edge["edge_type"])
              for edge in graph["edges"]}
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

    # Only show the initial common operation; graph relations still cover its successors.
    first = min(candidate["tasks"], key=lambda row: row["start"])
    scope = {"range_start": first["start"], "range_end": first["end"]}
    for reader, ref, full_graph in ((candidate_workspace, refs[0], candidate_graph),
                                   (plan_workspace, plan_ref, plan_graph)):
        narrowed = reader(case, ref, **scope)
        assert 0 < len(narrowed["tasks"]) < len(ids)
        assert narrowed["gantt_graph"] == full_graph
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
    assert invalidated["nodes"] == invalidated["edges"] == invalidated["critical_task_refs"] == invalidated["critical_edges"] == []


def test_zero_duration_split_and_join_are_graph_nodes_after_adoption(trial_case):
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
    graph = assert_mixed_graph(case, ids, plan_workspace(case, plan_ref), candidate=False)
    assert {row["operation_ref"] for row in graph["nodes"] if row["start"] == row["end"]} == point_refs


def test_candidate_resource_chain_uses_assignments_when_frozen_display_records_are_missing(trial_case):
    case = trial_case
    case.batch("B2")
    case.operation(batch="B2")
    case.conn.commit()
    _, refs = compute(case, case.settings("B1", "B2"))
    before = candidate_workspace(case, refs[0])["gantt_graph"]
    assert len(before["critical_task_refs"]) == 2
    assert len(before["critical_edges"]) == 1 and before["critical_edges"][0]["edge_type"] in ("machine", "operator")

    def remove_resource_refs(facts):
        facts["tables"]["WorkbenchEntityRefs"] = [row for row in facts["tables"]["WorkbenchEntityRefs"]
                                                   if row[1] not in ("machine", "operator")]

    edit_capture(case, "facts_json", remove_resource_refs)
    missing_refs = candidate_workspace(case, refs[0])
    assert all(task[kind]["ref"] is None for task in missing_refs["tasks"] for kind in ("machine", "operator"))
    assert missing_refs["gantt_graph"] == before

    def remove_resource_directory(facts):
        for name in ("Machines", "Operators"):
            facts["tables"][name] = []

    edit_capture(case, "facts_json", remove_resource_directory)
    missing_directory = candidate_workspace(case, refs[0])
    assert all(task[kind] == {"ref": None, "label": None}
               for task in missing_directory["tasks"] for kind in ("machine", "operator"))
    assert all(any(gap["field"] == kind and gap["code"] == "source_missing" for gap in task["data_gaps"])
               for task in missing_directory["tasks"] for kind in ("machine", "operator"))
    assert missing_directory["gantt_graph"] == before
