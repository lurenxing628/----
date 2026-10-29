"""Consume the unique execution ledger for the preflight operation scope."""


def execution_projections(facts, operations, *, prepared):
    from core.services.workbench.execution.ledger import ExecutionLedgerService

    refs = [facts.operation_ref(op) for op in operations]
    service = facts.execution_service or ExecutionLedgerService(facts.conn)
    facts.execution_service = service
    projections = []
    for offset in range(0, len(refs), 10000):
        projections.extend(service.project_operations(refs[offset:offset + 10000]))
    facts.execution_projections.update((row.operation_ref, row) for row in projections)
    result = {row.operation_ref: row.to_dict() for row in projections}
    if set(result) != set(refs) or len(projections) != len(refs):
        raise ValueError("ExecutionProjection did not cover the exact preflight operation scope")
    prepared.extend(projections)
    return result


def is_protected(projection, op):
    return bool(projection["reports"]
                or projection["first_actual_start"] or projection["confirmed_finish"]
                or projection["execution_state"] != "unreported" or op["status"] in ("processing", "completed"))
