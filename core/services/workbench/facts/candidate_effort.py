"""Project one candidate's saved requirement onto its workspace operations."""

from .operation_effort_evidence import archived_standard_effort, saved_operation_efforts
from .preflight_dependencies import material_deferred_ids
from .preparation_projection import operation_allocation, project_operation_effort


def candidate_operation_effort_projection(source):
    facts = source.facts
    runtime = saved_operation_efforts(source.receipt.operation_effort, identities=facts.operations)
    arranged = {row["operation_ref"]: row for row in source.raw_tasks}
    deferred = material_deferred_ids(source.disposition.values(), source.capture["input"])
    result = {}
    for ref in sorted(set(arranged) | set(source.disposition)):
        operation, execution = facts.operation(ref), facts.execution[ref]
        saved, task = runtime.get(ref), arranged.get(ref)
        original_source = saved["source"] if saved is not None else (task if task is not None else operation)["source"]
        standard = {**archived_standard_effort(operation, execution),
                    "evidence_source": {"kind": "admission", "run_ref": source.run["run_ref"]}}
        result[ref] = project_operation_effort(
            saved, standard,
            allocation_state=operation_allocation(saved, arranged=task is not None, source=original_source,
                                                  deferred=facts.operations[ref] in deferred, available=True),
            source_available=True, source=original_source, execution=execution,
            evidence_source={"kind": "run", "run_ref": source.run["run_ref"]})
    return result
