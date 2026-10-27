"""Piece-scope execution quantity verification."""

from core.services.workbench.facts.piece_scope import block


def _quantities(scope, refs, projections):
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
