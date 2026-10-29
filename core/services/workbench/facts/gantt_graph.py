"""One display graph over captured process relations and the complete schedule."""

from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.services.scheduler.gantt.critical_chain import compute_critical_chain_from_dependencies

from .piece_scope import build_piece_adoption_scope
from .stored_algo_inputs import stored_batch_operation


def frozen_process_relations(operations, batches, refs):
    scope = build_piece_adoption_scope([stored_batch_operation(row) for row in operations.values()],
                                       {key: row["quantity"] for key, row in batches.items()})
    return {refs[row.op_id]: [refs[key] for key in row.predecessor_op_ids] for row in scope.operations}


def unavailable_graph(scope, reason):
    return {"state": "unavailable", "reason": reason, "scope": scope, "nodes": [],
            "critical_task_refs": [], "critical_edges": []}


def build_gantt_graph(tasks, relations, *, scope, task_intervals):
    by_operation = {task["operation_ref"]: task["task_ref"] for task in tasks}
    previous = {task["task_ref"]: [by_operation[parent] for parent in relations[task["operation_ref"]]
                                 if parent in by_operation] for task in tasks}
    rows = [{"op_code": task["task_ref"], "operation_ref": task["operation_ref"],
             "start_time": task_intervals[task["task_ref"]][0],
             "end_time": task_intervals[task["task_ref"]][1],
             "machine_id": task.get("machine_ref"), "operator_id": task.get("operator_ref")}
            for task in tasks]
    critical = compute_critical_chain_from_dependencies(rows, previous)
    return {"state": "available", "reason": None, "scope": scope,
            "nodes": [{**{key: task[key] for key in ("task_ref", "operation_ref", "batch_id", "piece_id", "sequence", "process_label", "start", "end")},
                       "predecessor_operation_refs": list(relations[task["operation_ref"]])}
                      for task in tasks],
            "critical_task_refs": critical["ids"],
            "critical_edges": [{"from_task_ref": edge["from"], "to_task_ref": edge["to"], "edge_type": edge["edge_type"]}
                               for edge in critical["edges"]]}


def project_scoped_gantt_graph(full_graph, scoped_batch_ids):
    if full_graph.get("state") != "available":
        return full_graph
    critical_refs = set(full_graph.get("critical_task_refs", ()))
    batches = set(scoped_batch_ids) | {
        node["batch_id"] for node in full_graph["nodes"] if node["task_ref"] in critical_refs
    }
    nodes = [
        dict(node, predecessor_operation_refs=list(node["predecessor_operation_refs"]))
        for node in full_graph["nodes"]
        if node["batch_id"] in batches
    ]
    return dict(
        full_graph,
        nodes=nodes,
        critical_task_refs=list(full_graph["critical_task_refs"]),
        critical_edges=[dict(edge) for edge in full_graph["critical_edges"]],
    )


def candidate_gantt_graph(tasks, facts, raw_tasks, *, task_intervals):
    if not tasks:
        return build_gantt_graph([], {}, scope="full_candidate", task_intervals={})
    try:
        batch_ids = {facts.tables["BatchOperations"][facts.operations[task["operation_ref"]]]["batch_id"] for task in tasks}
        operations = {key: row for key, row in facts.tables["BatchOperations"].items() if row["batch_id"] in batch_ids}
        batches = {key: facts.tables["Batches"][key] for key in batch_ids}
        refs = {key: ref for ref, key in facts.operations.items() if key in operations}
        relations = frozen_process_relations(operations, batches, refs)
        arrangements = {row["operation_ref"]: row["payload"] for row in raw_tasks}
        nodes = []
        for task in tasks:
            operation = operations[facts.operations[task["operation_ref"]]]
            arrangement = arrangements[task["operation_ref"]]
            # Resource dependencies use captured assignments even when their display directory is missing.
            nodes.append({"task_ref": task["row_ref"], "operation_ref": task["operation_ref"],
                          "batch_id": operation["batch_id"], "piece_id": operation["piece_id"],
                          "sequence": task["sequence"], "process_label": task["process_label"],
                          "start": task["start"], "end": task["end"],
                          "machine_ref": arrangement["machine_id"], "operator_ref": arrangement["operator_id"]})
        return build_gantt_graph(nodes, relations, scope="full_candidate", task_intervals=task_intervals)
    except (PieceAdoptionBlocked, KeyError):
        return unavailable_graph("full_candidate", "此候选方案未保存完整的工艺前后关系，暂时无法显示关联线和关键链。")
