"""Preserve exact common/split predecessors in original and saved trial work."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.models.workbench_trial import issue
from core.services.workbench.facts.piece_scope import build_piece_adoption_scope
from core.services.workbench.facts.preflight_dependencies import material_deferred_ids
from core.services.workbench.facts.stored_algo_inputs import stored_batch_operation

if TYPE_CHECKING:
    from core.services.workbench.facts.preflight_checks import PreflightChecks

    from .preflight_facts import PreflightFacts


def trial_piece_predecessors(rows, all_ops, operation_refs):
    quantities = {row["original"]["batch"]["batch_id"]: row["original"]["batch"]["quantity"] for row in rows}
    operations = [stored_batch_operation(op) for op in all_ops.values() if op["batch_id"] in quantities]
    scope = build_piece_adoption_scope(operations, quantities)
    by_id = {}
    for work in scope.operations:
        if work.op_id not in operation_refs or any(key not in operation_refs for key in work.predecessor_op_ids):
            raise PieceAdoptionBlocked("dependency_identity_missing", "原分件工序的前道工序编号缺失，试调结果不完整。请点「刷新当前试调」重新试调。")
        by_id[work.op_id] = [operation_refs[key] for key in work.predecessor_op_ids]
    return by_id


def trial_piece_issues(rows, live, settings):
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
    if not _complete_or_deferred_scope(rows, expected, live, operations, settings):
        return [issue("piece_scope_incomplete", "试调要包含全部共同工序和分件工序，现在有缺漏。请点「刷新当前试调」重新试调。")]
    issues = []
    for row in rows:
        original = row["original"]
        if original["predecessor_operation_refs"] != expected[original["operation"]["id"]]:
            issues.append(issue("piece_dependency_mismatch", "原共同工序或分件工序的前后关系和完整范围对不上。请点「刷新当前试调」重新试调。", row["task_ref"]))
    return issues


def _complete_or_deferred_scope(rows, expected, live, operations, settings):
    present = {row["original"]["operation"]["id"] for row in rows}
    if len(rows) != len(present) or present - set(expected):
        return False
    missing = set(expected) - present
    if not missing:
        return True
    if settings.get("material_strategy") != "stage":
        return False
    facts: PreflightFacts = live["preflight_facts"]
    checks: PreflightChecks = facts.checks()
    batches = {row["batch_id"]: row for row in live["facts"]["tables"]["Batches"]}
    deferred = []
    for op_id in missing:
        op = operations[op_id]
        problems, _day = checks.operation_readiness(batches[op["batch_id"]], op, settings)
        deferred.append({"op_id": op_id, "status": "skipped", "issues": problems})
    return missing == material_deferred_ids(deferred, settings)
