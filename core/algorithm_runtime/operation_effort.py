"""One standard-work formula shared by input accounting and internal slots."""

import math
from typing import Any, Optional, Tuple

from core.algorithm_contracts.operation_effort import OperationEffort
from core.algorithm_contracts.types import OpForScheduleAlgo
from core.models.batch import Batch
from core.models.enums import MergeMode, OperationQuantityBasis, OperationSetupState, SourceType

from .piece_input import operation_batch


def _coerce_hours_value(raw_value: Any, *, field: str) -> float:
    if isinstance(raw_value, bool):
        raise ValueError(f"工时字段不能是布尔值：{field}={raw_value!r}")
    try:
        number = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"工时字段不合法：{field}={raw_value!r}") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"工时字段必须是非负有限数字：{field}={raw_value!r}")
    return number


def internal_requirement_parts(op: OpForScheduleAlgo, batch: Batch) -> Tuple[float, float, float, float]:
    """Consume the dispatcher's already operation-local quantity unchanged."""
    setup_raw, unit_raw, quantity_raw = op.setup_hours, op.unit_hours, batch.quantity
    setup = _coerce_hours_value(setup_raw, field="setup_hours")
    unit = _coerce_hours_value(unit_raw, field="unit_hours")
    quantity = _coerce_hours_value(quantity_raw, field="quantity")
    processing = unit * quantity
    required = setup + processing
    if not math.isfinite(required) or required < 0:
        raise ValueError("工时总量不合法："
                         f"setup_hours={setup_raw!r} unit_hours={unit_raw!r} quantity={quantity_raw!r} total_hours_base={required!r}")
    return setup, processing, required, quantity


def _quantity_basis(op: OpForScheduleAlgo) -> str:
    return OperationQuantityBasis.BATCH.value if op.piece_id is None else OperationQuantityBasis.PIECE.value


def internal_operation_effort(
    op: OpForScheduleAlgo, batch: Batch, *, remaining_quantity: Optional[int] = None,
) -> OperationEffort:
    """Apply the same piece quantity rule used by the actual dispatcher."""
    setup, processing, required, quantity = internal_requirement_parts(op, operation_batch(op, batch))
    return OperationEffort(
        op_id=op.id, batch_id=op.batch_id, piece_id=op.piece_id,
        source=SourceType.INTERNAL.value, target_quantity=int(quantity) if quantity.is_integer() else quantity,
        remaining_quantity=remaining_quantity,
        setup_standard_hours=setup, processing_standard_hours=processing, required_standard_hours=required,
        setup_state=OperationSetupState.PENDING.value, quantity_basis=_quantity_basis(op),
    )


def external_operation_effort(op: OpForScheduleAlgo, batch: Batch, *, remaining_quantity: Optional[int] = None) -> OperationEffort:
    """External calendar cycles remain separate from internal standard hours."""
    mode = op.ext_merge_mode
    return OperationEffort(
        op_id=op.id, batch_id=op.batch_id, piece_id=op.piece_id,
        source=SourceType.EXTERNAL.value, target_quantity=operation_batch(op, batch).quantity,
        remaining_quantity=remaining_quantity,
        setup_standard_hours=0.0, processing_standard_hours=0.0, required_standard_hours=0.0,
        setup_state=OperationSetupState.EXTERNAL.value, quantity_basis=_quantity_basis(op),
        external_cycle_days=op.ext_group_total_days if mode == MergeMode.MERGED.value else op.ext_days,
        external_group_id=op.ext_group_id, external_merge_mode=mode,
    )
