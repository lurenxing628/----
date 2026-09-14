"""Exact split stages over existing operation identities, never invented piece rows.

A piece represents one item (the execution ledger's existing target contract).
Without another authoritative route model, partial/heterogeneous split stages
cannot prove complete coverage. Each stage is either one common operation or
one operation for every piece; common stages join and then fan out again.
"""

from collections import defaultdict
from typing import NoReturn

from core.models.workbench_piece_adoption import (
    PieceAdoptionBlocked,
    PieceAdoptionScope,
    PieceOperationWork,
)

from .preflight_checks import number


def block(code, message, *, batch_id=None) -> NoReturn:
    raise PieceAdoptionBlocked(code, message, batch_id=batch_id)


def build_piece_adoption_scope(operations, batches):
    """Pure adapter usable before computation; it does not prove DB freshness."""
    by_batch = defaultdict(list)
    ids = set()
    for op in operations:
        if (not number(op.id, integer=True, positive=True) or op.id in ids
                or not number(op.seq, integer=True, positive=True) or op.batch_id not in batches):
            block("piece_identity_invalid", "工序编号或工序顺序号无效、重复，本次没有采用。请到批次管理核对本批工序。", batch_id=op.batch_id)
        if op.piece_id is not None and (
            type(op.piece_id) is not str or not op.piece_id or op.piece_id.strip() != op.piece_id
        ):
            block("piece_identity_invalid", "分件号必须明确填写，不能留空白，本次没有采用。请到批次管理核对本批工序。", batch_id=op.batch_id)
        ids.add(op.id)
        by_batch[op.batch_id].append(op)
    if set(by_batch) != set(batches):
        block("piece_scope_incomplete", "所选批次里有批次缺工序，本次没有采用。请到批次管理核对本批工序。")
    work = []
    for batch_id, ops in sorted(by_batch.items()):
        quantity = batches[batch_id].quantity
        if not number(quantity, integer=True):
            block("piece_quantity_unknown", "批次数量必须是明确的非负整数，本次没有采用。请到批次管理补填数量。", batch_id=batch_id)
        work.extend(_batch_stages(batch_id, ops, quantity))
    return PieceAdoptionScope(tuple(sorted(work, key=lambda item: item.op_id)))


def _batch_stages(batch_id, ops, quantity):
    pieces = {op.piece_id for op in ops if op.piece_id is not None}
    if pieces and len(pieces) != quantity:
        block("piece_scope_incomplete", "分件号的个数和批次数量不一致，本次没有采用。请到批次管理核对分件和数量。", batch_id=batch_id)
    stages = defaultdict(list)
    for op in ops:
        stages[op.seq].append(op)
    frontier = {piece: None for piece in pieces} if pieces else {None: None}
    result = []
    for seq, stage in sorted(stages.items()):
        if any(op.piece_id is None for op in stage):
            work, frontier = _common_stage(batch_id, seq, stage, quantity, frontier)
        else:
            work = _split_stage(batch_id, seq, stage, frontier)
        result.extend(work)
    return result


def _common_stage(batch_id, seq, stage, quantity, frontier):
    if len(stage) != 1:
        block("piece_dependency_ambiguous", "同一个工序顺序里既有共同工序又有分件工序，分不清归属，本次没有采用。请到批次管理核对工序顺序。", batch_id=batch_id)
    op = stage[0]
    predecessors = tuple(sorted({value for value in frontier.values() if value is not None}))
    work = PieceOperationWork(op.id, batch_id, None, seq, quantity, predecessors)
    return [work], {piece: op.id for piece in frontier}


def _split_stage(batch_id, seq, stage, frontier):
    if len(stage) != len(frontier) or {op.piece_id for op in stage} != set(frontier):
        block("piece_stage_incomplete", "分件工序有缺漏或重复，系统不猜工艺路线，本次没有采用。请到批次管理核对本批工序。", batch_id=batch_id)
    result = []
    for op in stage:
        previous = frontier[op.piece_id]
        predecessors = () if previous is None else (previous,)
        result.append(PieceOperationWork(op.id, batch_id, op.piece_id, seq, 1, predecessors))
        frontier[op.piece_id] = op.id
    return result
