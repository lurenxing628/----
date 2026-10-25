from __future__ import annotations

from dataclasses import dataclass
from typing import List, Mapping, Optional

from core.algorithm_contracts.types import OpForScheduleAlgo
from core.algorithm_contracts.value_domains import INTERNAL, MERGED
from core.errors import ValidationError
from core.models.batch_operation import BatchOperation
from core.shared.strict_parse import parse_required_float

from .schedule_template_lookup import FrozenExternalContext


@dataclass
class _ExternalMergeContext:
    ext_days: Optional[float] = None
    ext_group_id: Optional[str] = None
    ext_merge_mode: Optional[str] = None
    ext_group_total_days: Optional[float] = None


_EMPTY_EXTERNAL_CONTEXT = _ExternalMergeContext()


def _external_days(raw_value: Optional[float]) -> float:
    try:
        return parse_required_float(raw_value, field="外协周期", min_value=0.0, min_inclusive=False)
    except ValidationError as exc:
        raise ValidationError(exc.message, field="ext_days") from exc


def _build_external_merge_context(facts: FrozenExternalContext, op: BatchOperation) -> _ExternalMergeContext:
    merge_mode = facts.row["merge_mode"]
    # The preparation-time context_problem check already proved a merged total is a finite positive native number.
    total_days = float(facts.row["total_days"]) if merge_mode == MERGED else None
    ext_days = None if merge_mode == MERGED else _external_days(op.ext_days)

    return _ExternalMergeContext(
        ext_days=ext_days,
        ext_group_id=facts.group_key,
        ext_merge_mode=merge_mode,
        ext_group_total_days=total_days,
    )


def _internal_work_hour(
    raw_value: Optional[float],
    *,
    field: str,
    field_label: str,
) -> float:
    try:
        return parse_required_float(raw_value, field=field_label, min_value=0.0)
    except ValidationError as exc:
        raise ValidationError(f"自制工序的{field_label}必须是大于等于 0 的数字。", field=field) from exc


def _make_algo_operation(
    op: BatchOperation,
    *,
    setup_hours: float,
    unit_hours: float,
    external_context: _ExternalMergeContext,
) -> OpForScheduleAlgo:
    # operation_model 已在读取边界把编号、文本与来源校验成规范值，这里原样搬运。
    return OpForScheduleAlgo(
        id=op.id,
        op_code=op.op_code,
        batch_id=op.batch_id,
        piece_id=op.piece_id,
        seq=op.seq,
        op_type_id=op.op_type_id,
        op_type_name=op.op_type_name,
        source=op.source,
        machine_id=op.machine_id,
        operator_id=op.operator_id,
        supplier_id=op.supplier_id,
        setup_hours=setup_hours,
        unit_hours=unit_hours,
        ext_days=external_context.ext_days,
        ext_group_id=external_context.ext_group_id,
        ext_merge_mode=external_context.ext_merge_mode,
        ext_group_total_days=external_context.ext_group_total_days,
    )


def build_algo_operations(
    reschedulable_operations: List[BatchOperation],
    *,
    external_contexts: Mapping[int, FrozenExternalContext],
) -> List[OpForScheduleAlgo]:
    """
    把已收口的可重排工序（BatchOperation）转换为算法输入。

    约定：
    - 可重排范围由工作台输入准备的处置记录统一确定；
    - 本层只消费调用方传入的 `reschedulable_operations`，不再自行扩散状态语义；
    - 来源只会是 internal/external：读取边界 operation_model 已按算法值域校验过，本层不再归一化；
    - 外协工序的冻结周期记录由输入准备阶段一次核对后经 `external_contexts` 传入，本层不回库；
    - 工时与外协周期只有严格口径：填得不对抛 ValidationError，不按默认值兜底。
    """
    algo_ops: List[OpForScheduleAlgo] = []
    for op in reschedulable_operations:
        if op.source == INTERNAL:
            setup_hours = _internal_work_hour(op.setup_hours, field="setup_hours", field_label="换型时间")
            unit_hours = _internal_work_hour(op.unit_hours, field="unit_hours", field_label="单件工时")
            external_context = _EMPTY_EXTERNAL_CONTEXT
        else:
            # External work uses its calendar cycle and has no internal workload.
            # Keep the raw template's NULL hours intact; these are algorithm fields.
            setup_hours = unit_hours = 0.0
            external_context = _build_external_merge_context(external_contexts[op.id], op)
        algo_ops.append(
            _make_algo_operation(
                op,
                setup_hours=setup_hours,
                unit_hours=unit_hours,
                external_context=external_context,
            )
        )
    return algo_ops
