"""One standard-work formula shared by input accounting and internal slots."""

import inspect
import math
from typing import Any, Optional, Tuple

from core.algorithm_contracts.operation_effort import OperationEffort
from core.models.enums import MergeMode, OperationQuantityBasis, OperationSetupState, SourceType

from .piece_input import operation_batch

_MISSING = object()


def _read_legacy_field(obj: Any, field: str) -> Any:
    try:
        inspect.getattr_static(obj, field)
    except AttributeError:
        return _MISSING
    return getattr(obj, field)


def _coerce_legacy_hours_value(raw_value: Any, *, field: str) -> float:
    if raw_value is _MISSING:
        return 0.0
    if raw_value is True:
        return 1.0
    if raw_value is False:
        return 0.0
    if not raw_value:
        return 0.0
    try:
        return float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"工时字段不合法：{field}={raw_value!r}") from exc


def internal_requirement_parts(op: Any, batch: Any) -> Tuple[float, float, float, float]:
    """Consume the dispatcher's already operation-local quantity unchanged."""
    setup_raw, unit_raw = _read_legacy_field(op, "setup_hours"), _read_legacy_field(op, "unit_hours")
    quantity_raw = _read_legacy_field(batch, "quantity")
    setup = _coerce_legacy_hours_value(setup_raw, field="setup_hours")
    unit = _coerce_legacy_hours_value(unit_raw, field="unit_hours")
    quantity = _coerce_legacy_hours_value(quantity_raw, field="quantity")
    processing = unit * quantity
    required = setup + processing
    if not math.isfinite(required) or required < 0:
        raise ValueError("工时总量不合法："
                         f"setup_hours={setup_raw!r} unit_hours={unit_raw!r} quantity={quantity_raw!r} total_hours_base={required!r}")
    return setup, processing, required, quantity


def internal_operation_effort(op: Any, batch: Any, *, remaining_quantity: Optional[int] = None) -> OperationEffort:
    """Apply the same piece quantity rule used by the actual dispatcher."""
    setup, processing, required, quantity = internal_requirement_parts(op, operation_batch(op, batch))
    piece = getattr(op, "piece_id", None)
    return OperationEffort(
        op_id=getattr(op, "id", None), batch_id=getattr(op, "batch_id", None), piece_id=piece,
        source=SourceType.INTERNAL.value, target_quantity=int(quantity) if quantity.is_integer() else quantity,
        remaining_quantity=remaining_quantity,
        setup_standard_hours=setup, processing_standard_hours=processing, required_standard_hours=required,
        setup_state=OperationSetupState.PENDING.value,
        quantity_basis=OperationQuantityBasis.PIECE.value if piece is not None else OperationQuantityBasis.BATCH.value,
    )


def external_operation_effort(op: Any, batch: Any, *, remaining_quantity: Optional[int] = None) -> OperationEffort:
    """External calendar cycles remain separate from internal standard hours."""
    local = operation_batch(op, batch)
    mode = getattr(op, "ext_merge_mode", None)
    cycle = getattr(op, "ext_group_total_days", None) if mode == MergeMode.MERGED.value else getattr(op, "ext_days", None)
    piece = getattr(op, "piece_id", None)
    return OperationEffort(
        op_id=getattr(op, "id", None), batch_id=getattr(op, "batch_id", None), piece_id=piece,
        source=SourceType.EXTERNAL.value, target_quantity=getattr(local, "quantity", None), remaining_quantity=remaining_quantity,
        setup_standard_hours=0.0, processing_standard_hours=0.0, required_standard_hours=0.0,
        setup_state=OperationSetupState.EXTERNAL.value,
        quantity_basis=OperationQuantityBasis.PIECE.value if piece is not None else OperationQuantityBasis.BATCH.value,
        external_cycle_days=cycle, external_group_id=getattr(op, "ext_group_id", None), external_merge_mode=mode,
    )
