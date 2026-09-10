"""Preserve exact common/split predecessors in original and saved trial work."""

from types import SimpleNamespace

from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.models.workbench_trial import issue

from .piece_adoption_scope import build_piece_adoption_scope


def trial_piece_predecessors(rows, all_ops, operation_refs):
    batches = {row["original"]["batch"]["batch_id"]: SimpleNamespace(**row["original"]["batch"]) for row in rows}
    operations = [SimpleNamespace(**op) for op in all_ops.values() if op["batch_id"] in batches]
    scope = build_piece_adoption_scope(operations, batches)
    by_id = {}
    for work in scope.operations:
        if work.op_id not in operation_refs or any(key not in operation_refs for key in work.predecessor_op_ids):
            raise PieceAdoptionBlocked("dependency_identity_missing", "Original piece predecessor identity is missing.")
        by_id[work.op_id] = [operation_refs[key] for key in work.predecessor_op_ids]
    return by_id


def trial_piece_issues(rows, live):
    if not any(row["original"]["operation"]["piece_id"] is not None for row in rows):
        return []
    tables = live["facts"]["tables"]
    operations = {op["id"]: op for op in tables["BatchOperations"]}
    refs = {int(row["source_key"]): row["ref"] for row in tables["WorkbenchPlanSourceRefs"]
            if row["active"] == 1 and row["kind"] == "operation"}
    try:
        expected = trial_piece_predecessors(rows, operations, refs)
    except PieceAdoptionBlocked as exc:
        return [issue(exc.code, str(exc))]
    if len(rows) != len(expected) or {row["original"]["operation"]["id"] for row in rows} != set(expected):
        return [issue("piece_scope_incomplete", "Trial must retain the entire common and piece operation scope.")]
    issues = []
    for row in rows:
        original = row["original"]
        if original["predecessor_operation_refs"] != expected[original["operation"]["id"]]:
            issues.append(issue("piece_dependency_mismatch", "Original common/piece predecessors disagree with the complete scope.", row["task_ref"]))
    return issues
