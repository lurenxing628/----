"""The one standard-work formula; the run's internal slots consume what it yields, never recompute it."""

from typing import Optional, Tuple

from core.algorithm_contracts.operation_effort import OperationEffort
from core.algorithm_contracts.types import OpForScheduleAlgo
from core.models.batch import Batch
from core.models.enums import MergeMode, OperationQuantityBasis, OperationSetupState, SourceType

from .piece_input import operation_quantity


def _requirement_parts_for_quantity(op: OpForScheduleAlgo, quantity: int) -> Tuple[float, float, float]:
    """(setup, processing, required) standard hours.

    Every input is a stored number already admitted at its read boundary (0..2**53-1), so the
    product and sum are finite and non-negative. ``float()`` is the representation the slot walk
    and the saved requirement ledger both use (a stored integer setup reads as ``2.0``).
    """
    setup = float(op.setup_hours)
    processing = float(op.unit_hours) * float(quantity)
    return setup, processing, setup + processing


def _quantity_basis(op: OpForScheduleAlgo) -> str:
    return OperationQuantityBasis.BATCH.value if op.piece_id is None else OperationQuantityBasis.PIECE.value


def internal_required_hours(op: OpForScheduleAlgo, batch: Batch) -> float:
    """An internal operation's required standard hours, as ``internal_operation_effort`` gives them."""
    return _requirement_parts_for_quantity(op, operation_quantity(op, batch))[2]


def internal_operation_effort(
    op: OpForScheduleAlgo, batch: Batch, *, remaining_quantity: Optional[int] = None,
) -> OperationEffort:
    """Apply the same piece quantity rule used by the actual dispatcher."""
    quantity = operation_quantity(op, batch)
    setup, processing, required = _requirement_parts_for_quantity(op, quantity)
    return OperationEffort(
        op_id=op.id, batch_id=op.batch_id, piece_id=op.piece_id,
        source=SourceType.INTERNAL.value, target_quantity=quantity,
        remaining_quantity=remaining_quantity,
        setup_standard_hours=setup, processing_standard_hours=processing, required_standard_hours=required,
        setup_state=OperationSetupState.PENDING.value, quantity_basis=_quantity_basis(op),
    )


def external_operation_effort(op: OpForScheduleAlgo, batch: Batch, *, remaining_quantity: Optional[int] = None) -> OperationEffort:
    """External calendar cycles remain separate from internal standard hours."""
    mode = op.ext_merge_mode
    return OperationEffort(
        op_id=op.id, batch_id=op.batch_id, piece_id=op.piece_id,
        source=SourceType.EXTERNAL.value, target_quantity=operation_quantity(op, batch),
        remaining_quantity=remaining_quantity,
        setup_standard_hours=0.0, processing_standard_hours=0.0, required_standard_hours=0.0,
        setup_state=OperationSetupState.EXTERNAL.value, quantity_basis=_quantity_basis(op),
        external_cycle_days=op.ext_group_total_days if mode == MergeMode.MERGED.value else op.ext_days,
        external_group_id=op.ext_group_id, external_merge_mode=mode,
    )
