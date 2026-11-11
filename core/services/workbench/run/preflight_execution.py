"""Consume the unique execution ledger for the preflight operation scope."""


def execution_projections(facts, operations, *, prepared):
    refs = [facts.operation_ref(op) for op in operations]
    projections = []
    ledger = facts.ledger
    for offset in range(0, len(refs), 10000):
        projections.extend(ledger.reader.project_operations(ledger, refs[offset:offset + 10000]))
    facts.execution_projections.update((row.operation_ref, row) for row in projections)
    result = {row.operation_ref: row.to_dict() for row in projections}
    prepared.extend(projections)
    return result


def is_protected(projection, op):
    return bool(projection["reports"]
                or projection["first_actual_start"] or projection["confirmed_finish"]
                or projection["execution_state"] != "unreported" or op["status"] in ("processing", "completed"))
