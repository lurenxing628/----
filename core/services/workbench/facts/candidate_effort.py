"""Project one candidate's saved requirement onto its workspace operations."""

from core.models.enums import OperationRequirementRole, SourceType

from .operation_effort_evidence import archived_standard_effort, saved_operation_efforts
from .preflight_dependencies import material_deferred_ids
from .preparation_projection import project_operation_effort


def candidate_operation_effort_projection(source):
    runtime = saved_operation_efforts(source.receipt.get("operation_effort"), identities=source.facts.operations)
    arranged = {row["operation_ref"]: row for row in source.tasks}
    refs = set(arranged) | {row["operation_ref"] for row in source.unplanned}
    deferred = material_deferred_ids(source.disposition.values(), source.capture["input"])
    roles = {OperationRequirementRole.NEW_SCHEDULE.value, OperationRequirementRole.RETAINED.value,
             OperationRequirementRole.EXECUTION.value, OperationRequirementRole.COMPLETED.value}
    result = {}
    for ref in sorted(refs):
        operation = source.facts.tables["BatchOperations"].get(source.facts.operations[ref], {})
        execution = source.facts.execution[ref]
        saved = runtime.get(ref)
        original_source = saved.get("source") if saved is not None else arranged.get(ref, operation).get("source")
        if ref not in arranged:
            allocation = "deferred" if source.facts.operations[ref] in deferred else "unplanned"
        elif original_source == SourceType.EXTERNAL.value:
            allocation = "external"
        else:
            role = (saved or {}).get("requirement_role")
            allocation = role if role in roles else "unknown"
        standard = {**archived_standard_effort(operation, execution),
                    "evidence_source": {"kind": "admission", "run_ref": source.run["run_ref"]}}
        result[ref] = project_operation_effort(saved, standard, allocation_state=allocation, source_available=True,
                                             source=original_source, execution=execution,
                                             evidence_source={"kind": "run", "run_ref": source.run["run_ref"]})
    return result
