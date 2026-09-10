"""Operation-local work and graph progress; original batches remain untouched."""

from copy import copy
from dataclasses import replace
from datetime import datetime
from typing import Tuple

from core.infrastructure.errors import ValidationError
from core.shared.strict_parse import parse_optional_date


def operation_batch(op, batch):
    piece = getattr(op, "piece_id", None)
    if piece is None:
        return batch
    if type(piece) is not str or not piece or piece.strip() != piece:
        raise ValidationError("Piece identity must be canonical.", field="piece_id")
    quantity = getattr(batch, "quantity", None)
    if type(quantity) is not int or not 0 < quantity < (1 << 53):
        raise ValidationError("A piece requires an explicit positive batch quantity.", field="quantity")
    work = copy(batch)
    work.quantity = 1
    return work


def external_group_key(op) -> Tuple[str, ...]:
    key = (str(op.batch_id).strip(), str(op.ext_group_id).strip())
    piece = getattr(op, "piece_id", None)
    return key if piece is None else key + (piece,)


def operation_dispatch_state(state, graph_state, op, batch):
    if graph_state is None or "end_time_by_op_id" not in graph_state:
        return state
    ends = graph_state["end_time_by_op_id"]
    predecessors = graph_state["predecessor_op_ids_by_op_id"].get(op.id, set())
    if any(key not in ends for key in predecessors):
        raise ValidationError("A ready operation lacks predecessor completion evidence.", field="graph_ready_context")
    earliest = max([state.base_time] + [ends[key] for key in predecessors])
    ready = parse_optional_date(getattr(batch, "ready_date", None), field="ready_date")
    if ready is not None:
        earliest = max(earliest, datetime.combine(ready, datetime.min.time()))
    return replace(state, batch_progress={op.batch_id: earliest})
