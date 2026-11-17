"""Consume the unique execution ledger for the preflight operation scope."""


def execution_projections(facts, operations):
    """Project ``operations`` once: (each projection as a dict by operation ref, the projections themselves)."""
    ledger = facts.ledger
    projections = ledger.reader.project_operations(ledger, [facts.operation_ref(op) for op in operations])
    facts.execution_projections.update((row.operation_ref, row) for row in projections)
    return {row.operation_ref: row.to_dict() for row in projections}, tuple(projections)


def is_protected(projection, op):
    return bool(projection["reports"]
                or projection["first_actual_start"] or projection["confirmed_finish"]
                or projection["execution_state"] != "unreported" or op["status"] in ("processing", "completed"))
