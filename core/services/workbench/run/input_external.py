"""Bind scheduling to the batch contexts used by preflight and batch detail."""

from core.services.scheduler.contracts.external_context import (
    context_group_key,
    context_problem,
    member_index,
    merged_supplier_problem,
)
from core.services.workbench.facts.run_input_rows import fail


def prime_template_cache(svc, tables, batches, operations):
    contexts = {row["operation_id"]: row for row in tables.get("BatchExternalContexts", [])}
    members = member_index(contexts, tables.get("BatchOperations", []))
    for op in operations:
        if op.source != "external":
            continue
        problem = context_problem(contexts.get(op.id), operation_id=op.id,
                                  part_no=batches[op.batch_id].part_no, sequence=op.seq)
        if problem:
            fail("external_context_invalid", problem, op_id=op.id)
        row = contexts[op.id]
        problem = merged_supplier_problem(row, op.supplier_id,
            members.get((op.batch_id, context_group_key(row), getattr(op, "piece_id", None))))
        if problem:
            fail("external_context_invalid", problem, op_id=op.id)
    svc._aps_schedule_input_cache = {"batch": dict(batches), "external_contexts": contexts,
                                     "external_members": members, "external_contexts_bound": True}
