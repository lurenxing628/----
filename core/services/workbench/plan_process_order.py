"""Frozen process relations for one complete adopted plan, never current BOM."""

from types import SimpleNamespace

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.models.workbench_plan_reference import WorkbenchPlanReferenceError
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .piece_adoption_scope import build_piece_adoption_scope
from .plan_adoption_baseline_identity import _live_sources
from .plan_adoption_baseline_values import AdoptionBaselineUnavailable, indexed, require
from .plan_projection import check_payload_size, read_adopted_source
from .trial_adoption_storage import load_saved_scenario


def _unavailable(facts, code, gap):
    message = ("此计划未记录工序顺序。" if code == "process_order_not_recorded" else
               "工序顺序数据不完整。")
    facts.update(outcome=code, evidence_gap=gap)
    return {"state": "unavailable", "basis": None, "items": [],
            "issues": [{"code": code, "message": message}]}, facts


def _frozen_operations(conn, tables, arranged):
    operations = indexed(tables["BatchOperations"], "id")
    batches = indexed(tables["Batches"], "batch_id")
    wanted = {row["op_id"] for row in arranged}
    require(wanted <= set(operations), "process_order.original_operations")
    batch_ids = {operations[key]["batch_id"] for key in wanted}
    require(batch_ids <= set(batches), "process_order.original_batches")
    related = {key: row for key, row in operations.items() if row["batch_id"] in batch_ids}
    keys = {str(key) for key in related}
    sources = [row for row in tables["WorkbenchPlanSourceRefs"]
               if row["kind"] == "operation" and row["active"] == 1 and row["source_key"] in keys]
    by_key = indexed(sources, "source_key")
    require(set(by_key) == keys, "process_order.complete_operation_refs")
    _live_sources(conn, sources)
    refs = {key: by_key[str(key)]["ref"] for key in related}
    require(len(set(refs.values())) == len(refs), "process_order.unique_operation_refs")
    return related, {key: batches[key] for key in batch_ids}, refs


def _candidate_relations(operations, batches, refs):
    scope = build_piece_adoption_scope([SimpleNamespace(**row) for row in operations.values()],
                                      {key: SimpleNamespace(**row) for key, row in batches.items()})
    return {refs[row.op_id]: [refs[key] for key in row.predecessor_op_ids] for row in scope.operations}


def _trial_relations(conn, audit, refs):
    _, _, rows = load_saved_scenario(conn, audit["scenario_ref"])
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


def _project(conn, plan_ref, rows, relations, refs):
    repository = WorkbenchPlanIdentityRepository(conn)
    tasks = repository.get_task_refs(plan_ref, [dict(row, schedule_id=row["id"]) for row in rows])
    all_refs = {row[0] for row in conn.execute("SELECT ref FROM WorkbenchTaskRefs WHERE plan_ref=?", (plan_ref,))}
    require(all_refs == set(tasks.values()) and len(tasks) == len(rows), "process_order.complete_task_membership")
    items = []
    for row in rows:
        operation_ref = refs[row["op_id"]]
        require(operation_ref in relations, "process_order.missing_frozen_relation")
        items.append({"task_ref": tasks[row["id"]], "operation_ref": operation_ref,
                      "predecessor_operation_refs": list(relations[operation_ref])})
    require(len({item["task_ref"] for item in items}) == len(items), "process_order.unique_task_refs")
    return items


def project_process_order(conn, *, plan_ref):
    """Return a complete read-only projection and the facts used by its fingerprint."""
    if not conn.in_transaction:
        raise RuntimeError("Process order reads require a caller-owned read transaction.")
    facts = {"plan_ref": plan_ref}
    try:
        evidence = read_adopted_source(conn, plan_ref)
        if evidence is None:
            return _unavailable(facts, "process_order_not_recorded", "no_audited_frozen_source")
        basis, audit, tables, arranged, selected = evidence
        facts.update(adoption=audit, selected_rows=selected)
        operations, batches, refs = _frozen_operations(conn, tables, arranged)
        if basis == "candidate_adoption":
            relations = _candidate_relations(operations, batches, refs)
        else:
            relations = _trial_relations(conn, audit, refs)
        _acyclic(relations)
        items = _project(conn, plan_ref, selected, relations, refs)
        data = {"state": "available", "basis": "run_admission" if basis == "candidate_adoption" else "trial_creation",
                "items": items, "issues": []}
        check_payload_size(data)
        facts.update(relations=relations, items=items)
        return data, facts
    except AdoptionBaselineUnavailable as exc:
        return _unavailable(facts, "process_order_unavailable", exc.code + ":" + exc.gap)
    except (WorkbenchPlanReferenceError, PieceAdoptionBlocked) as exc:
        return _unavailable(facts, "process_order_unavailable", exc.code)
    except WorkbenchCommandRejected as exc:
        if exc.status == 413:
            raise
        return _unavailable(facts, "process_order_unavailable", exc.code)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _unavailable(facts, "process_order_unavailable", "frozen_shape:" + type(exc).__name__)
