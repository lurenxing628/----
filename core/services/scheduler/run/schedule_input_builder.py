from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Union, overload

try:
    from typing import Literal
except ImportError:  # pragma: no cover
    from typing_extensions import Literal

from core.errors import ValidationError
from core.models.enums import MergeMode, SourceType
from core.services.common.build_outcome import BuildOutcome
from core.services.scheduler.contracts.schedule_input_op import OpForScheduleAlgo
from core.shared.degradation import DegradationCollector
from core.shared.field_parse import parse_field_float
from core.shared.strict_parse import parse_required_float

from .schedule_template_lookup import verified_external_context_for_op


@dataclass
class _ExternalMergeContext:
    ext_days: Optional[float] = None
    ext_group_id: Optional[str] = None
    ext_merge_mode: Optional[str] = None
    ext_group_total_days: Optional[float] = None


def _build_scope(op: Any) -> str:
    op_id = getattr(op, "id", None)
    if op_id not in (None, ""):
        return f"schedule_input.op[{op_id}]"
    batch_id = str(getattr(op, "batch_id", "") or "").strip() or "?"
    seq = int(getattr(op, "seq", 0) or 0)
    return f"schedule_input.batch[{batch_id}].seq[{seq}]"


def _build_external_merge_context(
    svc,
    op: Any,
    *,
    strict_mode: bool,
    scope: str,
    collector: DegradationCollector,
) -> _ExternalMergeContext:
    facts = verified_external_context_for_op(svc, op)
    merge_mode = facts.row["merge_mode"]
    # require_context already proved a merged total is a finite positive native number.
    total_days = float(facts.row["total_days"]) if merge_mode == MergeMode.MERGED.value else None

    ext_days: Optional[float] = None
    if merge_mode != MergeMode.MERGED.value:
        ext_days = parse_field_float(
            getattr(op, "ext_days", None),
            field="ext_days",
            field_label="外协周期",
            strict_mode=bool(strict_mode),
            scope=scope,
            fallback=1.0,
            collector=collector,
            min_value=0.0,
            min_inclusive=False,
        )

    return _ExternalMergeContext(
        ext_days=ext_days,
        ext_group_id=facts.group_key,
        ext_merge_mode=merge_mode,
        ext_group_total_days=total_days,
    )


def _internal_work_hour(
    raw_value: Any,
    *,
    field: str,
    field_label: str,
) -> float:
    try:
        return float(parse_required_float(raw_value, field=field_label, min_value=0.0))
    except ValidationError as exc:
        raise ValidationError(f"自制工序的{field_label}必须是大于等于 0 的数字。", field=field) from exc


def _make_algo_operation(
    op: Any,
    *,
    setup_hours: float,
    unit_hours: float,
    external_context: _ExternalMergeContext,
) -> OpForScheduleAlgo:
    return OpForScheduleAlgo(
        id=int(getattr(op, "id", 0) or 0),
        op_code=str(getattr(op, "op_code", "") or ""),
        batch_id=str(getattr(op, "batch_id", "") or ""),
        piece_id=getattr(op, "piece_id", None),
        seq=int(getattr(op, "seq", 0) or 0),
        op_type_id=getattr(op, "op_type_id", None),
        op_type_name=getattr(op, "op_type_name", None),
        source=str(getattr(op, "source", "") or ""),
        machine_id=getattr(op, "machine_id", None),
        operator_id=getattr(op, "operator_id", None),
        supplier_id=getattr(op, "supplier_id", None),
        setup_hours=float(setup_hours),
        unit_hours=float(unit_hours),
        ext_days=external_context.ext_days,
        ext_group_id=external_context.ext_group_id,
        ext_merge_mode=external_context.ext_merge_mode,
        ext_group_total_days=external_context.ext_group_total_days,
    )


def _build_algo_operations_outcome(
    svc,
    reschedulable_operations: List[Any],
    *,
    strict_mode: bool = False,
) -> BuildOutcome[List[OpForScheduleAlgo]]:
    """
    把已收口的可重排工序（BatchOperation）转换为算法输入。

    约定：
    - `completed/skipped` 之类的终态过滤由 `ScheduleService` 统一负责；
    - 本层只消费调用方传入的 `reschedulable_operations`，不再自行扩散状态语义。
    """
    cache = getattr(svc, "_aps_schedule_input_cache", None)
    if isinstance(cache, dict) and not cache.get("external_contexts_bound"):
        cache.pop("external_members", None)
    collector = DegradationCollector()
    algo_ops: List[OpForScheduleAlgo] = []
    for op in reschedulable_operations:
        scope = _build_scope(op)
        source_key = str(getattr(op, "source", "") or "").strip().lower()

        if source_key == SourceType.INTERNAL.value:
            setup_hours = _internal_work_hour(
                getattr(op, "setup_hours", None),
                field="setup_hours",
                field_label="换型时间",
            )
            unit_hours = _internal_work_hour(
                getattr(op, "unit_hours", None),
                field="unit_hours",
                field_label="单件工时",
            )
        else:
            setup_hours = parse_field_float(
                getattr(op, "setup_hours", None),
                field="setup_hours",
                field_label="换型时间",
                strict_mode=bool(strict_mode),
                scope=scope,
                fallback=0.0,
                collector=collector,
                min_value=0.0,
            )
            unit_hours = parse_field_float(
                getattr(op, "unit_hours", None),
                field="unit_hours",
                field_label="单件工时",
                strict_mode=bool(strict_mode),
                scope=scope,
                fallback=0.0,
                collector=collector,
                min_value=0.0,
            )

        external_context = _ExternalMergeContext()
        if source_key == SourceType.EXTERNAL.value:
            external_context = _build_external_merge_context(
                svc,
                op,
                strict_mode=bool(strict_mode),
                scope=scope,
                collector=collector,
            )
        algo_ops.append(
            _make_algo_operation(
                op,
                setup_hours=float(setup_hours),
                unit_hours=float(unit_hours),
                external_context=external_context,
            )
        )
    return BuildOutcome.from_collector(algo_ops, collector)


@overload
def build_algo_operations(
    svc,
    reschedulable_operations: List[Any],
    *,
    strict_mode: bool = False,
    return_outcome: Literal[True],
) -> BuildOutcome[List[OpForScheduleAlgo]]:
    ...


@overload
def build_algo_operations(
    svc,
    reschedulable_operations: List[Any],
    *,
    strict_mode: bool = False,
    return_outcome: Literal[False] = False,
) -> List[OpForScheduleAlgo]:
    ...


def build_algo_operations(
    svc,
    reschedulable_operations: List[Any],
    *,
    strict_mode: bool = False,
    return_outcome: bool = False,
) -> Union[BuildOutcome[List[OpForScheduleAlgo]], List[OpForScheduleAlgo]]:
    outcome = _build_algo_operations_outcome(svc, reschedulable_operations, strict_mode=bool(strict_mode))
    if return_outcome:
        return outcome
    return outcome.value
