"""Select exact permanent identities for AQ; never interpret ledger protection."""

from collections import defaultdict

from core.services.scheduler.run.schedule_execution_guardrails import build_execution_guardrails_from_projections
from core.services.scheduler.run.schedule_input_contracts import ExecutionGuardState
from core.services.workbench.facts.run_input_rows import fail

from .piece_adoption_execution import _quantities


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
        _quantities(piece_scope, {op.id: facts.operation_refs[op.id] for op in operations}, projections)
    for op in operations:
        projection = projections[facts.operation_refs[op.id]]
        if piece_scope is None:
            # 分件时 _quantities 已按同一份工序逐条核对过目标数量和口径。
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
