"""Pure admission and official work projections shared by saved models and details."""

from typing import Any

from .candidate_tasks import operation_labels
from .operation_effort_evidence import archived_standard_effort
from .preparation_projection import operation_allocation, preparation_summary, project_operation_effort


def admission_operation_standards(facts, operation_refs, run_ref):
    result = {}
    for ref in operation_refs:
        result[ref] = {**archived_standard_effort(facts.operation(ref), facts.execution[ref]),
                       "evidence_source": {"kind": "admission", "run_ref": run_ref}}
    return result


def project_decision_preparation_row(facts, operation_ref, task, operation_efforts, *, run_ref,
                                     available, deferred_refs, official, standards: Any):
    """Project one operation's actual allocation from its one arranged task (or None), keeping official and admission
    evidence distinct. The official plan recorded a runtime requirement only for the operations it arranged with one."""
    if official is not None:
        original = official["operation_efforts"].get(operation_ref)
        runtime, evidence_source = (original["effort"], original["evidence_source"]) if original is not None else (None, None)
        saved_standard = official["operation_standards"].get(operation_ref)
        standard = ({**archived_standard_effort(saved_standard["operation"], saved_standard["execution"]),
                     "evidence_source": saved_standard["evidence_source"]} if saved_standard is not None else None)
        original_source = runtime["source"] if runtime is not None else task["source"] if task is not None else None
    else:
        runtime = operation_efforts.get(operation_ref)
        standard = standards[operation_ref]
        evidence_source = {"kind": "run", "run_ref": run_ref}
        original_source = runtime["source"] if runtime is not None else facts.operation(operation_ref)["source"]
    row = project_operation_effort(runtime, standard,
        allocation_state=operation_allocation(runtime, arranged=task is not None, source=original_source,
                                              deferred=operation_ref in deferred_refs, available=available),
        source_available=available, source=original_source, execution=facts.execution[operation_ref],
        evidence_source=evidence_source)
    row.update(operation_ref=operation_ref, arranged=task is not None)
    return row


def project_decision_preparation(facts, operation_refs, operation_efforts, arrangements, *, run_ref,
                                 available, deferred_refs, requirements_available,
                                 official=None, standards=None):
    """Return the common per-operation rows and their full-admission summary; ``arrangements`` maps each operation
    to its one arranged task (``decision_read_models.by_operation``)."""
    refs, deferred = list(operation_refs), set(deferred_refs)
    if standards is None and official is None:
        standards = admission_operation_standards(facts, refs, run_ref)
    rows = [project_decision_preparation_row(facts, ref, arrangements.get(ref), operation_efforts,
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
