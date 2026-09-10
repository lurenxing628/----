"""Select exact permanent identities for AQ; never interpret ledger protection."""

from core.services.scheduler.run.schedule_execution_guardrails import build_execution_guardrails_from_projections
from core.services.scheduler.run.schedule_execution_resource_facts import _latest_plan_rows

from .piece_adoption_execution import _quantities
from .run_input_rows import fail


def _prior_operation_refs(facts, plan_rows):
    prior_refs = set()
    for op_id in plan_rows:
        ref = facts.operation_refs.get(op_id)
        if ref is None:
            fail("execution_scope_missing", "A last-official operation has no active permanent identity.", op_id=op_id)
        prior_refs.add(ref)
    return prior_refs


def _validate_execution_target(op, batches, projection):
    quantity = 1 if op.piece_id is not None else batches[op.batch_id].quantity
    basis = "piece" if op.piece_id is not None else "batch"
    if projection.target_quantity != quantity or projection.target_basis != basis:
        fail("execution_target_changed", "Execution target differs from the original operation work.", op_id=op.id)


def _validate_execution_origin(op_id, projection, prior_refs):
    if projection.operation_ref not in prior_refs and (
        projection.execution_state != "unreported" or projection.reports or projection.legacy_facts
        or projection.first_actual_start is not None or projection.confirmed_finish is not None
        or projection.known_completed_quantity != 0
    ):
        fail("execution_scope_missing", "Execution exists without a valid last-official scope.", op_id=op_id)


def execution_guards(svc, facts, operations, batches, projections, prev_version, *, piece_scope=None):
    plan_rows = _latest_plan_rows(svc, prev_version)
    prior_refs = _prior_operation_refs(facts, plan_rows)
    selected_refs = {facts.operation_refs[op.id] for op in operations}
    if set(projections) != selected_refs | prior_refs:
        fail("execution_projection_scope_mismatch", "Supply selected operations plus every last-official operation, exactly.")
    if piece_scope is not None:
        _quantities(piece_scope, {op.id: facts.operation_refs[op.id] for op in operations}, projections)
    for op in operations:
        projection = projections[facts.operation_refs[op.id]]
        _validate_execution_target(op, batches, projection)
        _validate_execution_origin(op.id, projection, prior_refs)
    return build_execution_guardrails_from_projections(
        svc, operations, prev_version=prev_version,
        execution_projections=[projections[ref] for ref in sorted(prior_refs)],
    )
