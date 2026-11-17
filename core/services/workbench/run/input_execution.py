"""Select exact permanent identities for AQ; never interpret ledger protection."""

from collections import defaultdict

from core.services.scheduler.run.schedule_execution_guardrails import build_execution_guardrails_from_projections
from core.services.scheduler.run.schedule_input_contracts import ExecutionGuardState
from core.services.workbench.facts.piece_scope import block
from core.services.workbench.facts.run_input_rows import fail


def _prior_operation_refs(facts, plan_rows):
    prior_refs = set()
    for op_id in plan_rows:
        ref = facts.operation_refs.get(op_id)
        if ref is None:
            fail("execution_scope_missing", "正式计划里有工序在资料里查不到编号，这次排产没有开始。请到批次管理核对后重试。", op_id=op_id)
        prior_refs.add(ref)
    return prior_refs


def _validate_execution_target(op, batches, projection):
    quantity = 1 if op.piece_id is not None else batches[op.batch_id].quantity
    basis = "piece" if op.piece_id is not None else "batch"
    if projection.target_quantity != quantity or projection.target_basis != basis:
        fail("execution_target_changed", "这道工序的报工目标数量和当前批次数量对不上，这次排产没有开始。请到现场记录核对后重试。", op_id=op.id)


def verify_piece_quantities(scope, refs, projections):
    for work in scope.operations:
        item = projections[refs[work.op_id]]
        basis = "batch" if work.piece_id is None else "piece"
        if item.target_basis != basis or item.target_quantity != work.target_quantity:
            block("piece_quantity_unknown", "报工记录的目标数量和共同工序或分件工序对不上，本次没有采用。请到现场记录核对后重新排产。")
        if (item.data_quality == "invalid" or item.unknown_record_count
                or item.known_completed_quantity > work.target_quantity or item.remaining_quantity is None
                or item.remaining_quantity != work.target_quantity - item.known_completed_quantity):
            block("piece_execution_quantity_unproven", "报工数量缺失、互相矛盾或超过目标量，本次没有采用。请到现场记录核对后重新排产。")
        if item.execution_state == "complete" and (
            not item.quantity_complete or item.known_completed_quantity != work.target_quantity
        ):
            block("piece_execution_quantity_unproven", "有工序报了完工却没有确切完工数量，证明不了分件全部做完，本次没有采用。请到现场记录补齐完工数量。")


def _validate_execution_origin(op_id, projection, prior_refs):
    if projection.operation_ref not in prior_refs and (
        projection.execution_state != "unreported" or projection.reports
        or projection.first_actual_start is not None or projection.confirmed_finish is not None
        or projection.known_completed_quantity != 0
    ):
        fail("execution_scope_missing", "这道工序有报工记录，但不在正式计划范围里，这次排产没有开始。请到现场记录核对后重试。", op_id=op_id)


def _execution_resource_segments(execution_facts, completed):
    timelines = defaultdict(list)
    for op_id in sorted(completed):
        fact = execution_facts[op_id]
        for start, end, machine, operator in fact.execution_resource_segments:
            timelines["machine_id", machine].append((start, end, op_id))
            timelines["operator_id", operator].append((start, end, op_id))
    return {key: tuple(sorted(intervals)) for key, intervals in timelines.items()}


def execution_guards(facts, operations, batches, projections, prev_version, *, piece_scope=None) -> ExecutionGuardState:
    plan_rows = facts.latest_plan_rows(prev_version)
    prior_refs = _prior_operation_refs(facts, plan_rows)
    selected_refs = {facts.operation_refs[op.id] for op in operations}
    if set(projections) != selected_refs | prior_refs:
        fail("execution_projection_scope_mismatch", "Supply selected operations plus every last-official operation, exactly.")
    if piece_scope is not None:
        verify_piece_quantities(piece_scope, {op.id: facts.operation_refs[op.id] for op in operations}, projections)
    for op in operations:
        projection = projections[facts.operation_refs[op.id]]
        if piece_scope is None:
            # 分件时 verify_piece_quantities 已按同一份工序逐条核对过目标数量和口径。
            _validate_execution_target(op, batches, projection)
        _validate_execution_origin(op.id, projection, prior_refs)
    execution_facts, completed, execution_seeds, snapshot = build_execution_guardrails_from_projections(
        operations, prev_version=prev_version,
        execution_projections=[projections[ref] for ref in sorted(prior_refs)],
        facts=facts,
    )
    return ExecutionGuardState(
        execution_facts=execution_facts,
        execution_resource_segments=_execution_resource_segments(execution_facts, completed),
        execution_completed_op_ids=completed,
        execution_seed_results=execution_seeds,
        execution_snapshot_revision=snapshot.revision,
        execution_snapshot_op_ids=tuple(snapshot.op_ids),
        execution_snapshot_op_count=snapshot.op_count,
    )
