"""Bind one complete split scope before resource selection or computation."""

from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.services.scheduler.run.schedule_input_seed_metadata import (
    merged_external_group_identity,
    protected_interval_problem,
)
from core.services.workbench.facts.piece_scope import build_piece_adoption_scope
from core.services.workbench.facts.run_input_rows import fail


def input_piece_scope(operations, batches):
    if not any(op.piece_id is not None for op in operations):
        return None
    try:
        scope = build_piece_adoption_scope(operations, batches)
    except PieceAdoptionBlocked as exc:
        fail(exc.code, str(exc), batch_id=exc.batch_id)
    return scope


def validate_piece_seed_precedence(*, scope, algo_ops, seed_results, operations, execution_completed_op_ids):
    seeds = {row["op_id"]: row for row in seed_results}
    if len(seeds) != len(seed_results):
        fail("piece_protected_seed_missing", "要保持原安排的工序出现了重复记录，这次排产没有开始。请刷新重试；仍不行请联系维护人员。")
    if not execution_completed_op_ids <= set(seeds):
        fail("piece_protected_seed_missing", "已完工的单件工序缺少准确的实际起止时间，这次排产没有开始。请到现场记录补齐后重试。")
    by_id = {op.id: op for op in algo_ops}
    for work in scope.operations:
        if work.op_id not in seeds:
            continue
        for predecessor in work.predecessor_op_ids:
            if predecessor in seeds:
                _validate_seed_pair(by_id[predecessor], by_id[work.op_id], seeds[predecessor], seeds[work.op_id])


def _validate_seed_pair(left, right, previous, current):
    problem = protected_interval_problem(previous, current,
        previous_group=merged_external_group_identity(left), current_group=merged_external_group_identity(right))
    if problem == "merged_group_split":
        fail("piece_merged_group_split", "同一个外协合并分组里，保持原安排的工序时段不一致，这次排产没有开始。请到现场记录核对后重试。")
    if problem == "precedence_violation":
        fail("piece_protected_precedence_violation", "保持原安排的工序和它的前道工序时间冲突，这次排产没有开始。请到现场记录核对后重试。")
