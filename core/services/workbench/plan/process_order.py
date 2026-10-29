"""Frozen process relations for one complete adopted plan, never current BOM."""

import threading
from collections import OrderedDict

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.models.workbench_plan_reference import WorkbenchPlanReferenceError
from core.services.workbench.facts.adoption_baseline_values import AdoptionBaselineUnavailable, indexed, require
from core.services.workbench.facts.gantt_graph import build_gantt_graph, frozen_process_relations, unavailable_graph

from .adoption_baseline_identity import _live_sources
from .projection import wire_positive_int64
from .read_context import PlanReadContext

_DEFAULT_BUILD_GANTT_GRAPH = build_gantt_graph
_DEFAULT_FROZEN_RELATIONS = frozen_process_relations
_CACHE_LOCK = threading.RLock()
_RELATIONS_CACHE: "OrderedDict[tuple, dict]" = OrderedDict()
_GANTT_GRAPH_CACHE: "OrderedDict[tuple, dict]" = OrderedDict()


def _unavailable(facts, code, gap):
    message = ("此计划未记录工序顺序。" if code == "process_order_not_recorded" else
               "工序顺序数据不完整。")
    facts.update(outcome=code, evidence_gap=gap)
    return {"state": "unavailable", "basis": None,
            "issues": [{"code": code, "message": message}]}, facts, unavailable_graph("full_plan", message)


def _frozen_operations(conn, tables, arranged, *, context, evidence=None):
    indexed_tables = evidence.get("indexed_tables") if type(evidence) is dict else None
    same_sources = (
        indexed_tables is not None
        and indexed_tables.get("source_refs_id") == id(tables["WorkbenchPlanSourceRefs"])
        and indexed_tables.get("batch_operations_id") == id(tables["BatchOperations"])
        and indexed_tables.get("batches_id") == id(tables["Batches"])
    )
    if indexed_tables is not None and same_sources and "BatchOperations" in indexed_tables and "Batches" in indexed_tables:
        operations = indexed_tables["BatchOperations"]
        batches = indexed_tables["Batches"]
        op_sources = indexed_tables.get("operation_sources")
    else:
        operations = indexed(tables["BatchOperations"], "id")
        batches = indexed(tables["Batches"], "batch_id")
        op_sources = None
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
    if op_sources is not None:
        by_key = {key: op_sources[key] for key in keys if key in op_sources}
    else:
        sources = [row for row in tables["WorkbenchPlanSourceRefs"]
                   if row["kind"] == "operation" and row["active"] == 1 and row["source_key"] in keys]
        by_key = indexed(sources, "source_key")
    require(set(by_key) == keys, "process_order.complete_operation_refs")
    verified_keys = (
        evidence.get("verified_operation_keys")
        if context is not None and type(evidence) is dict and (indexed_tables is None or same_sources)
        else None
    )
    if verified_keys is not None:
        extra_keys = keys - set(verified_keys)
        if extra_keys:
            _live_sources(conn, [by_key[key] for key in extra_keys], context=context)
    else:
        _live_sources(conn, list(by_key.values()), context=context)
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


def _task_bindings(plan_ref, rows, relations, refs, *, context, evidence=None):
    selected_task_refs = evidence.get("selected_task_refs") if type(evidence) is dict else None
    if selected_task_refs is not None and len(selected_task_refs) == len(rows):
        tasks = selected_task_refs
    else:
        tasks = context.references.get_task_refs(plan_ref, ((row["id"], row["op_id"], row["version"]) for row in rows))
    all_refs = context.all_task_refs(plan_ref)
    require(all_refs == set(tasks.values()) and len(tasks) == len(rows), "process_order.complete_task_membership")
    for row in rows:
        operation_ref = refs[row["op_id"]]
        require(operation_ref in relations, "process_order.missing_frozen_relation")
    require(len(set(tasks.values())) == len(rows), "process_order.unique_task_refs")
    return tasks


def project_process_order(conn, *, plan_ref, context: PlanReadContext):
    """Return a complete read-only projection and the facts used by its fingerprint."""
    if not conn.in_transaction:
        raise RuntimeError("Process order reads require a caller-owned read transaction.")
    with context.read_scope():
        return _process_order(conn, plan_ref=plan_ref, context=context)


def _cached_candidate_relations(operations, batches, refs):
    if frozen_process_relations is not _DEFAULT_FROZEN_RELATIONS:
        relations = frozen_process_relations(operations, batches, refs)
        _acyclic(relations)
        return None, relations
    rel_key = (
        tuple(
            (op_id, op.get("batch_id"), op.get("piece_id"), op.get("seq"), op.get("op_type_name"), refs[op_id])
            for op_id, op in operations.items()
        ),
        tuple((bid, b.get("quantity")) for bid, b in batches.items()),
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


def _copy_graph(graph):
    return dict(
        graph,
        nodes=[
            dict(node, predecessor_operation_refs=list(node["predecessor_operation_refs"]))
            for node in graph["nodes"]
        ],
        critical_task_refs=list(graph["critical_task_refs"]),
        critical_edges=[dict(edge) for edge in graph["critical_edges"]],
    )


def _process_order(conn, *, plan_ref, context):
    facts = {"plan_ref": plan_ref}
    try:
        evidence = context.adopted_source(plan_ref)
        if evidence is None:
            return _unavailable(facts, "process_order_not_recorded", "no_audited_frozen_source")
        basis, audit, tables, arranged, selected = (
            evidence[key] for key in ("basis", "audit", "tables", "arranged", "selected")
        )
        facts.update(adoption=audit, selected_rows=selected)
        operations, batches, refs = _frozen_operations(conn, tables, arranged, context=context, evidence=evidence)
        rel_key = None
        if basis == "candidate_adoption":
            rel_key, relations = _cached_candidate_relations(operations, batches, refs)
        else:
            relations = _trial_relations(evidence["trial_source"], refs)
            _acyclic(relations)
        task_refs = _task_bindings(plan_ref, selected, relations, refs, context=context, evidence=evidence)
        data = {"state": "available", "basis": "run_admission" if basis == "candidate_adoption" else "trial_creation",
                "issues": []}
        facts.update(relations=relations)
        _, entry, _ = context.selected(plan_ref)
        if build_gantt_graph is _DEFAULT_BUILD_GANTT_GRAPH:
            ops_key = (
                rel_key[0]
                if rel_key is not None
                else tuple(
                    (op_id, op.get("batch_id"), op.get("piece_id"), op.get("seq"), op.get("op_type_name"), refs.get(op_id))
                    for op_id, op in operations.items()
                )
            )
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
                    return data, facts, _copy_graph(cached_graph)
        else:
            graph_key = None
        times = context.intervals(entry)
        dt_intervals = context.datetime_intervals(entry)
        tasks = _graph_tasks(selected, task_refs, operations, refs, times=times)
        task_intervals = {task_refs[row["id"]]: dt_intervals[row["id"]] for row in selected}
        graph = build_gantt_graph(tasks, relations, scope="full_plan", task_intervals=task_intervals)
        if graph_key is not None:
            with _CACHE_LOCK:
                _GANTT_GRAPH_CACHE[graph_key] = graph
                while len(_GANTT_GRAPH_CACHE) > 32:
                    _GANTT_GRAPH_CACHE.popitem(last=False)
            return data, facts, _copy_graph(graph)
        return data, facts, graph
    except AdoptionBaselineUnavailable as exc:
        return _unavailable(facts, "process_order_unavailable", exc.code + ":" + exc.gap)
    except (WorkbenchPlanReferenceError, PieceAdoptionBlocked) as exc:
        return _unavailable(facts, "process_order_unavailable", exc.code)
    except WorkbenchCommandRejected as exc:
        if exc.status == 413:
            raise
        return _unavailable(facts, "process_order_unavailable", exc.code)


def _graph_tasks(rows, task_refs, operations, refs, *, times):
    result = []
    for row in rows:
        low, high = times[row["id"]]
        result.append({
            "task_ref": task_refs[row["id"]], "operation_ref": refs[row["op_id"]],
            "batch_id": operations[row["op_id"]]["batch_id"], "piece_id": operations[row["op_id"]]["piece_id"],
            "sequence": wire_positive_int64(operations[row["op_id"]]["seq"]),
            "process_label": operations[row["op_id"]]["op_type_name"],
            "start": low.replace(" ", "T"), "end": high.replace(" ", "T"),
            "machine_ref": row["machine_id"], "operator_ref": row["operator_id"],
        })
    return result
