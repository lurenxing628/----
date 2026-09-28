"""Preserve exact common/split predecessors in original and saved trial work."""

from types import SimpleNamespace

from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.models.workbench_trial import issue
from core.services.workbench.facts.piece_scope import build_piece_adoption_scope
from core.services.workbench.facts.preflight_checks import PreflightChecks
from core.services.workbench.facts.preflight_dependencies import material_deferred_ids


def trial_piece_predecessors(rows, all_ops, operation_refs):
    batches = {row["original"]["batch"]["batch_id"]: SimpleNamespace(**row["original"]["batch"]) for row in rows}
    operations = [SimpleNamespace(**op) for op in all_ops.values() if op["batch_id"] in batches]
    scope = build_piece_adoption_scope(operations, batches)
    by_id = {}
    for work in scope.operations:
        if work.op_id not in operation_refs or any(key not in operation_refs for key in work.predecessor_op_ids):
            raise PieceAdoptionBlocked("dependency_identity_missing", "原分件工序的前道工序编号缺失，试调结果不完整。请点「刷新当前试调」重新试调。")
        by_id[work.op_id] = [operation_refs[key] for key in work.predecessor_op_ids]
    return by_id


def trial_piece_issues(rows, live, policy=None):
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
    settings = dict(policy or {}, end_date=max(row["current"]["end"][:10] for row in rows))
    if not _complete_or_deferred_scope(rows, expected, tables, operations, settings):
        return [issue("piece_scope_incomplete", "试调要包含全部共同工序和分件工序，现在有缺漏。请点「刷新当前试调」重新试调。")]
    issues = []
    for row in rows:
        original = row["original"]
        if original["predecessor_operation_refs"] != expected[original["operation"]["id"]]:
            issues.append(issue("piece_dependency_mismatch", "原共同工序或分件工序的前后关系和完整范围对不上。请点「刷新当前试调」重新试调。", row["task_ref"]))
    return issues


def _complete_or_deferred_scope(rows, expected, tables, operations, settings):
    present = {row["original"]["operation"]["id"] for row in rows}
    if len(rows) != len(present) or present - set(expected):
        return False
    missing = set(expected) - present
    if not missing:
        return True
    if settings.get("material_strategy") != "stage":
        return False
    checks = PreflightChecks(tables)
    batches = {row["batch_id"]: row for row in tables["Batches"]}
    deferred = []
    for op_id in missing:
        op = operations[op_id]
        problems, _day = checks.operation_readiness(batches[op["batch_id"]], op, settings)
        deferred.append({"op_id": op_id, "status": "skipped", "issues": problems})
    return missing == material_deferred_ids(deferred, settings)
