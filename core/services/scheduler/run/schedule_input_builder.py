from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, overload

try:
    from typing import Literal
except ImportError:  # pragma: no cover
    from typing_extensions import Literal

from core.infrastructure.errors import ValidationError
from core.models.enums import MergeMode, SourceType
from core.services.common.build_outcome import BuildOutcome
from core.services.common.degradation import DegradationCollector, degradation_events_to_dicts
from core.services.common.field_parse import parse_field_float
from core.services.common.strict_parse import parse_required_float

from .schedule_template_lookup import TemplateGroupLookupOutcome, lookup_template_group_context_for_op


@dataclass
class OpForScheduleAlgo:
    """算法输入工序（补充 merged 外部组信息）。"""

    id: int
    op_code: str
    batch_id: str
    seq: int
    op_type_id: Optional[str]
    op_type_name: Optional[str]
    source: str
    machine_id: Optional[str]
    operator_id: Optional[str]
    supplier_id: Optional[str]
    setup_hours: float
    unit_hours: float
    ext_days: Optional[float]
    # 外部组信息（来自 PartOperations + ExternalGroups）
    ext_group_id: Optional[str]
    ext_merge_mode: Optional[str]
    ext_group_total_days: Optional[float]
    merge_context_degraded: bool = False
    merge_context_events: List[Dict[str, Any]] = field(default_factory=list)


def _build_scope(op: Any) -> str:
    op_id = getattr(op, "id", None)
    if op_id not in (None, ""):
        return f"schedule_input.op[{op_id}]"
    batch_id = str(getattr(op, "batch_id", "") or "").strip() or "?"
    seq = int(getattr(op, "seq", 0) or 0)
    return f"schedule_input.batch[{batch_id}].seq[{seq}]"


def _merged_total_days(
    raw_value: Any,
    *,
    strict_mode: bool,
    scope: str,
    collector: DegradationCollector,
    op_code: str,
) -> Optional[float]:
    try:
        return float(
            parse_required_float(
                raw_value,
                field="ext_group_total_days",
                min_value=0.0,
                min_inclusive=False,
            )
        )
    except ValidationError:
        if strict_mode:
            raise
        collector.add(
            code="invalid_number",
            scope=scope,
            field="ext_group_total_days",
            message=f"外协工序 {op_code} 的组合并周期无效，组合并语义已退化为逐道外协周期。",
            sample=repr(raw_value),
        )
        return None


def _lookup_template_group_context(svc, op: Any, *, strict_mode: bool, scope: str) -> TemplateGroupLookupOutcome:
    return lookup_template_group_context_for_op(svc, op, strict_mode=bool(strict_mode), scope=scope)


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
    collector = DegradationCollector()
    algo_ops: List[OpForScheduleAlgo] = []
    for op in reschedulable_operations:
        scope = _build_scope(op)
        op_code = str(getattr(op, "op_code", "") or "").strip() or "-"
        source_key = str(getattr(op, "source", "") or "").strip().lower()

        setup_hours = parse_field_float(
            getattr(op, "setup_hours", None),
            field="setup_hours",
            strict_mode=bool(strict_mode),
            scope=scope,
            fallback=0.0,
            collector=collector,
            min_value=0.0,
        )
        unit_hours = parse_field_float(
            getattr(op, "unit_hours", None),
            field="unit_hours",
            strict_mode=bool(strict_mode),
            scope=scope,
            fallback=0.0,
            collector=collector,
            min_value=0.0,
        )

        ext_days: Optional[float] = None
        ext_group_id: Optional[str] = None
        merge_mode: Optional[str] = None
        total_days: Optional[float] = None
        merge_context_degraded = False
        merge_event_collector = DegradationCollector()

        if source_key == SourceType.EXTERNAL.value:
            lookup = _lookup_template_group_context(svc, op, strict_mode=bool(strict_mode), scope=scope)
            merge_event_collector.extend(lookup.events)
            collector.extend(lookup.events)
            merge_context_degraded = bool(lookup.merge_context_degraded)
            tmpl = lookup.template
            grp = lookup.group

            if (not merge_context_degraded) and tmpl is not None:
                ext_group_id = str(getattr(tmpl, "ext_group_id", None) or "").strip() or None
            if (not merge_context_degraded) and grp is not None:
                merge_mode = str(getattr(grp, "merge_mode", None) or "").strip().lower() or None
                if merge_mode == MergeMode.MERGED.value:
                    merge_event_count_before = len(merge_event_collector)
                    total_days = _merged_total_days(
                        getattr(grp, "total_days", None),
                        strict_mode=bool(strict_mode),
                        scope=scope,
                        collector=merge_event_collector,
                        op_code=op_code,
                    )
                    if total_days is None:
                        merge_context_degraded = True
                        collector.extend(merge_event_collector.to_list()[merge_event_count_before:])
                        ext_group_id = None
                        merge_mode = None
                else:
                    total_days = None

            needs_ext_days = merge_context_degraded or merge_mode != MergeMode.MERGED.value or total_days is None
            if needs_ext_days:
                ext_days = parse_field_float(
                    getattr(op, "ext_days", None),
                    field="ext_days",
                    strict_mode=bool(strict_mode),
                    scope=scope,
                    fallback=1.0,
                    collector=collector,
                    min_value=0.0,
                    min_inclusive=False,
                )

        algo_ops.append(
            OpForScheduleAlgo(
                id=int(getattr(op, "id", 0) or 0),
                op_code=str(getattr(op, "op_code", "") or ""),
                batch_id=str(getattr(op, "batch_id", "") or ""),
                seq=int(getattr(op, "seq", 0) or 0),
                op_type_id=getattr(op, "op_type_id", None),
                op_type_name=getattr(op, "op_type_name", None),
                source=str(getattr(op, "source", "") or ""),
                machine_id=getattr(op, "machine_id", None),
                operator_id=getattr(op, "operator_id", None),
                supplier_id=getattr(op, "supplier_id", None),
                setup_hours=float(setup_hours),
                unit_hours=float(unit_hours),
                ext_days=ext_days,
                ext_group_id=ext_group_id,
                ext_merge_mode=merge_mode,
                ext_group_total_days=total_days,
                merge_context_degraded=bool(merge_context_degraded),
                merge_context_events=degradation_events_to_dicts(merge_event_collector.to_list()),
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
) -> BuildOutcome[List[OpForScheduleAlgo]] | List[OpForScheduleAlgo]:
    outcome = _build_algo_operations_outcome(svc, reschedulable_operations, strict_mode=bool(strict_mode))
    if return_outcome:
        return outcome
    return outcome.value
