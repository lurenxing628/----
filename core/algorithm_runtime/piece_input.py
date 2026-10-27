"""Operation-local work and graph progress; original batches remain untouched."""

from copy import copy
from datetime import datetime
from typing import Any, Dict, Tuple, cast

from core.algorithm_contracts.types import OpForScheduleAlgo
from core.errors import ValidationError
from core.models.batch import Batch
from core.shared.strict_parse import parse_optional_date


def operation_batch(op: OpForScheduleAlgo, batch: Batch) -> Batch:
    piece = op.piece_id
    if piece is None:
        return batch
    if type(piece) is not str or not piece or piece.strip() != piece:
        raise ValidationError("Piece identity must be canonical.", field="piece_id")
    quantity = batch.quantity
    if type(quantity) is not int or not 0 < quantity < (1 << 53):
        raise ValidationError("A piece requires an explicit positive batch quantity.", field="quantity")
    work = copy(batch)
    work.quantity = 1
    return work


def external_group_key(op: OpForScheduleAlgo) -> Tuple[str, ...]:
    """Identity of a merged external group; callers pass only merged operations, whose group id is set."""
    key = (op.batch_id, cast(str, op.ext_group_id))
    return key if op.piece_id is None else key + (op.piece_id,)


class _OperationDispatchState:
    """Override one ready operation's release floor; every live counter still reads its run state."""

    __slots__ = ("_state", "batch_progress")

    def __init__(self, state: Any, batch_id: str, earliest: datetime) -> None:
        self._state = state
        self.batch_progress: Dict[str, datetime] = {batch_id: earliest}

    def prev_end(self, batch_id: str) -> datetime:
        return self.batch_progress[batch_id]

    def __getattr__(self, name: str) -> Any:
        return getattr(self._state, name)


def operation_dispatch_state(state, graph_state, op: OpForScheduleAlgo, batch: Batch) -> Any:
    if graph_state is None or "end_time_by_op_id" not in graph_state:
        return state
    states = graph_state.setdefault("operation_dispatch_states", {})
    if op.id in states:
        return states[op.id]
    ends = graph_state["end_time_by_op_id"]
    predecessors = graph_state["predecessor_op_ids_by_op_id"][op.id]
    if any(key not in ends for key in predecessors):
        raise ValidationError("A ready operation lacks predecessor completion evidence.", field="graph_ready_context")
    earliest = max([state.base_time] + [ends[key] for key in predecessors])
    if state.readiness_gate_enabled:
        ready = parse_optional_date(batch.ready_date, field="ready_date")
        if ready is not None:
            earliest = max(earliest, datetime.combine(ready, datetime.min.time()))
    local = _OperationDispatchState(state, op.batch_id, earliest)
    states[op.id] = local
    return local
