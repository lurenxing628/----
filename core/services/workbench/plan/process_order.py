"""Frozen process relations for one complete adopted plan, never current BOM."""

import threading
from collections import OrderedDict

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.models.workbench_plan_reference import WorkbenchPlanReferenceError
from core.services.workbench.facts.adoption_baseline_values import AdoptionBaselineUnavailable, require
from core.services.workbench.facts.gantt_graph import build_gantt_graph, frozen_process_relations, unavailable_graph

from .adoption_baseline_identity import _live_sources
from .projection import wire_positive_int64
from .read_context import PlanReadContext

_CACHE_LOCK = threading.RLock()
_RELATIONS_CACHE: "OrderedDict[tuple, dict]" = OrderedDict()
_GANTT_GRAPH_CACHE: "OrderedDict[tuple, dict]" = OrderedDict()


def _unavailable(code):
    message = ("此计划未记录工序顺序。" if code == "process_order_not_recorded" else
               "工序顺序数据不完整。")
    return {"state": "unavailable", "basis": None,
            "issues": [{"code": code, "message": message}]}, unavailable_graph("full_plan", message)


def _frozen_operations(conn, arranged, *, context, evidence):
    indexed_tables = evidence["indexed_tables"]
    operations = indexed_tables["BatchOperations"]
    batches = indexed_tables["Batches"]
    op_sources = indexed_tables["operation_sources"]
    wanted = {row["op_id"] for row in arranged}
    require(wanted <= set(operations), "process_order.original_operations")
    batch_ids = {operations[key]["batch_id"] for key in wanted}
    require(batch_ids <= set(batches), "process_order.original_batches")
    related = {key: row for key, row in operations.items() if row["batch_id"] in batch_ids}
    require(
        all(type(row.get("op_type_name")) is str and bool(row["op_type_name"].strip()) for row in related.values()),
        "process_order.operation_label",
    )
    keys = {str(key) for key in related}
    by_key = {key: op_sources[key] for key in keys if key in op_sources}
    require(set(by_key) == keys, "process_order.complete_operation_refs")
    extra_keys = keys - set(evidence["verified_operation_keys"])
    if extra_keys:
        _live_sources(conn, [by_key[key] for key in extra_keys], context=context)
    refs = {key: by_key[str(key)]["ref"] for key in related}
    require(len(set(refs.values())) == len(refs), "process_order.unique_operation_refs")
    return related, {key: batches[key] for key in batch_ids}, refs


def _trial_relations(trial_source, refs):
    _, _, rows = trial_source.source
    known = set(refs.values())
    relations = {}
    for row in rows:
        original = row["original"]
        op_id = original["operation"]["id"]
        require(op_id in refs and row["operation_ref"] == refs[op_id], "process_order.trial_operation_identity")
        previous = original["predecessor_operation_refs"]
        require(type(previous) is list and len(set(previous)) == len(previous) and set(previous) <= known
                and refs[op_id] not in previous, "process_order.trial_frozen_predecessors")
        require(row["operation_ref"] not in relations, "process_order.trial_duplicate_operation")
        relations[row["operation_ref"]] = previous
    return relations


def _acyclic(relations):
    counts = {key: 0 for key in relations}
    following = {key: [] for key in relations}
    for key, parents in relations.items():
        for parent in parents:
            if parent in counts:
                counts[key] += 1
                following[parent].append(key)
    ready = [key for key, count in counts.items() if not count]
    index = 0
    while index < len(ready):
        for child in following[ready[index]]:
            counts[child] -= 1
            if not counts[child]:
                ready.append(child)
        index += 1
    require(len(ready) == len(relations), "process_order.frozen_cycle")


def _task_bindings(plan_ref, rows, relations, refs, *, context, evidence):
    tasks = evidence["selected_task_refs"]
    all_refs = context.all_task_refs(plan_ref)
    require(all_refs == set(tasks.values()) and len(tasks) == len(rows), "process_order.complete_task_membership")
    for row in rows:
        operation_ref = refs[row["op_id"]]
        require(operation_ref in relations, "process_order.missing_frozen_relation")
    require(len(set(tasks.values())) == len(rows), "process_order.unique_task_refs")
    return tasks


def project_process_order(conn, *, plan_ref, context: PlanReadContext, include_nodes=True):
    """Return a complete read-only process-order projection and its gantt graph."""
    if not conn.in_transaction:
        raise RuntimeError("Process order reads require a caller-owned read transaction.")
    with context.read_scope():
        return _process_order(conn, plan_ref=plan_ref, context=context, include_nodes=include_nodes)


def _relation_tuples(operations, refs):
    return tuple(
        (op_id, op["batch_id"], op["piece_id"], op["seq"], op["op_type_name"], refs[op_id])
        for op_id, op in operations.items()
    )


def _cached_candidate_relations(operations, batches, refs):
    rel_key = (
        _relation_tuples(operations, refs),
        tuple((bid, b["quantity"]) for bid, b in batches.items()),
    )
    with _CACHE_LOCK:
        cached = _RELATIONS_CACHE.get(rel_key)
        if cached is not None:
            _RELATIONS_CACHE.move_to_end(rel_key)
            return rel_key, cached
    relations = frozen_process_relations(operations, batches, refs)
    _acyclic(relations)
    with _CACHE_LOCK:
        _RELATIONS_CACHE[rel_key] = relations
        while len(_RELATIONS_CACHE) > 16:
            _RELATIONS_CACHE.popitem(last=False)
    return rel_key, relations


def load_frozen_plan_process_order(conn, *, plan_ref, context: PlanReadContext):
    if plan_ref in context._process_orders:
        return context._process_orders[plan_ref]
    evidence = context.adopted_source(plan_ref)
    if evidence is None:
        context._process_orders[plan_ref] = None
        return None
    basis, arranged, selected = (
        evidence[key] for key in ("basis", "arranged", "selected")
    )
    operations, batches, refs = _frozen_operations(conn, arranged, context=context, evidence=evidence)
    rel_key = None
    if basis == "candidate_adoption":
        rel_key, relations = _cached_candidate_relations(operations, batches, refs)
    else:
        relations = _trial_relations(evidence["trial_source"], refs)
        _acyclic(relations)
    task_refs = _task_bindings(plan_ref, selected, relations, refs, context=context, evidence=evidence)
    frozen = {
        "basis": basis,
        "selected": selected,
        "operations": operations,
        "refs": refs,
        "relations": relations,
        "task_refs": task_refs,
        "rel_key": rel_key,
    }
    context._process_orders[plan_ref] = frozen
    return frozen


def _process_order(conn, *, plan_ref, context, include_nodes=True):
    try:
        frozen = load_frozen_plan_process_order(conn, plan_ref=plan_ref, context=context)
        if frozen is None:
            return _unavailable("process_order_not_recorded")
        basis = frozen["basis"]
        selected = frozen["selected"]
        operations = frozen["operations"]
        refs = frozen["refs"]
        relations = frozen["relations"]
        task_refs = frozen["task_refs"]
        rel_key = frozen["rel_key"]
        data = {"state": "available", "basis": "run_admission" if basis == "candidate_adoption" else "trial_creation",
                "issues": []}
        if not include_nodes:
            count = len(selected)
            return data, {
                "state": "available",
                "reason": None,
                "scope": "full_plan",
                "nodes": [],
                "node_count": count,
                "nodes_complete": count == 0,
                "critical_task_refs": [],
                "critical_edges": [],
            }
        _, entry, _ = context.selected(plan_ref)
        ops_key = rel_key[0] if rel_key is not None else _relation_tuples(operations, refs)
        rels_tuple = rel_key[1] if rel_key is not None else tuple((key, tuple(value)) for key, value in relations.items())
        graph_key = (
            plan_ref,
            entry.locator.version,
            basis,
            ops_key,
            rels_tuple,
            tuple(
                (
                    row["id"],
                    row["op_id"],
                    row["machine_id"],
                    row["operator_id"],
                    row["start_time"],
                    row["end_time"],
                    task_refs[row["id"]],
                )
                for row in selected
            ),
        )
        with _CACHE_LOCK:
            cached_graph = _GANTT_GRAPH_CACHE.get(graph_key)
            if cached_graph is not None:
                _GANTT_GRAPH_CACHE.move_to_end(graph_key)
                return data, cached_graph
        times = context.intervals(entry)
        dt_intervals = context.datetime_intervals(entry)
        tasks = _graph_tasks(selected, task_refs, operations, refs, times=times)
        task_intervals = {task_refs[row["id"]]: dt_intervals[row["id"]] for row in selected}
        graph = build_gantt_graph(tasks, relations, scope="full_plan", task_intervals=task_intervals)
        with _CACHE_LOCK:
            _GANTT_GRAPH_CACHE[graph_key] = graph
            while len(_GANTT_GRAPH_CACHE) > 32:
                _GANTT_GRAPH_CACHE.popitem(last=False)
        return data, graph
    except (AdoptionBaselineUnavailable, WorkbenchPlanReferenceError, PieceAdoptionBlocked):
        return _unavailable("process_order_unavailable")
    except WorkbenchCommandRejected as exc:
        if exc.status == 413:
            raise
        return _unavailable("process_order_unavailable")


def _graph_tasks(rows, task_refs, operations, refs, *, times):
    result = []
    for row in rows:
        low, high = times[row["id"]]
        result.append({
            "task_ref": task_refs[row["id"]], "operation_ref": refs[row["op_id"]],
            "batch_id": operations[row["op_id"]]["batch_id"], "piece_id": operations[row["op_id"]]["piece_id"],
            "sequence": wire_positive_int64(operations[row["op_id"]]["seq"]),
            "process_label": operations[row["op_id"]]["op_type_name"],
            "start": low, "end": high,
            "machine_ref": row["machine_id"], "operator_ref": row["operator_id"],
        })
    return result
