"""Pure admission and official work projections shared by saved models and details."""

from collections import defaultdict
from typing import Any

from core.models.enums import OperationRequirementRole, SourceType

from .candidate_tasks import operation_labels
from .operation_effort_evidence import archived_standard_effort
from .preparation_projection import preparation_summary, project_operation_effort

_RUNTIME_ALLOCATIONS = (
    OperationRequirementRole.NEW_SCHEDULE.value,
    OperationRequirementRole.RETAINED.value,
    OperationRequirementRole.EXECUTION.value,
    OperationRequirementRole.COMPLETED.value,
)


def admission_operation_standards(facts, operation_refs, run_ref):
    result = {}
    for ref in operation_refs:
        operation = facts.tables["BatchOperations"].get(facts.operations[ref], {})
        execution = facts.execution.get(ref, {})
        result[ref] = {**archived_standard_effort(operation, execution),
                       "evidence_source": {"kind": "admission", "run_ref": run_ref}}
    return result


def _allocation_state(ref, runtime, tasks, *, available, deferred_refs):
    if not available:
        return "unknown"
    if not tasks:
        return "deferred" if ref in deferred_refs else "unplanned"
    source = runtime.get("source") if runtime is not None else tasks[0]["source"]
    if source == SourceType.EXTERNAL.value:
        return "external"
    role = (runtime or {}).get("requirement_role")
    return role if role in _RUNTIME_ALLOCATIONS else "unknown"


def project_decision_preparation_row(facts, operation_ref, tasks, operation_efforts, *, run_ref,
                                     available, deferred_refs, official, standards: Any):
    """Project one actual allocation, keeping official and admission evidence distinct."""
    formal = official is not None
    operation = facts.tables["BatchOperations"].get(facts.operations.get(operation_ref), {})
    if formal:
        original = official["operation_efforts"].get(operation_ref) or {}
        saved_standard = official["operation_standards"].get(operation_ref)
        standard = ({**archived_standard_effort(saved_standard["operation"], saved_standard["execution"]),
                     "evidence_source": saved_standard["evidence_source"]} if saved_standard is not None else None)
        runtime, evidence_source = original.get("effort"), original.get("evidence_source")
    else:
        runtime = operation_efforts.get(operation_ref)
        standard = standards[operation_ref]
        evidence_source = {"kind": "run", "run_ref": run_ref}
    original_source = runtime.get("source") if runtime is not None else (
        tasks[0]["source"] if formal and tasks else operation.get("source") if not formal else None)
    row = project_operation_effort(runtime, standard,
        allocation_state=_allocation_state(operation_ref, runtime, tasks, available=available, deferred_refs=deferred_refs),
        source_available=available, source=original_source, execution=facts.execution[operation_ref],
        evidence_source=evidence_source)
    row.update(operation_ref=operation_ref, arranged=bool(tasks))
    return row


def project_decision_preparation(facts, operation_refs, operation_efforts, tasks, *, run_ref,
                                 available, deferred_refs, requirements_available,
                                 official=None, standards=None, task_groups=None):
    """Return the common per-operation rows and their full-admission summary."""
    refs, deferred = list(operation_refs), set(deferred_refs)
    if task_groups is None:
        task_groups = defaultdict(list)
        for task in tasks:
            task_groups[task["operation_ref"]].append(task)
    if standards is None and official is None:
        standards = admission_operation_standards(facts, refs, run_ref)
    rows = [project_decision_preparation_row(facts, ref, task_groups.get(ref, []), operation_efforts,
        run_ref=run_ref, available=available, deferred_refs=deferred, official=official, standards=standards) for ref in refs]
    return {"rows": rows, "summary": preparation_summary(rows, available=available,
            requirements_available=requirements_available)}


def preparation_work_items(facts, rows, disposition, *, available=True, labels=None):
    """Join only unarranged preparation rows to their archived batch labels and reasons."""
    if not available:
        return []
    result = []
    for row in rows:
        if row["arranged"]:
            continue
        ref = row["operation_ref"]
        identity = labels[ref] if labels is not None else operation_labels(facts, ref)[0]
        result.append({**identity, **row, "disposition": disposition[ref]})
    return result
