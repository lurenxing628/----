from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from core.errors import ValidationError
from core.models.batch import Batch
from core.shared.strict_parse import parse_optional_date, parse_optional_datetime

from .date_parsers import parse_datetime
from .sort_strategies import BatchForSort, SortStrategy
from .types import OpForScheduleAlgo


def normalize_text_id(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def resolve_batch_sort_batch_id(batch_key: str, batch: Batch) -> str:
    normalized_key = normalize_text_id(batch_key)
    if normalized_key:
        return normalized_key
    return batch.batch_id


def build_normalized_batches_map(batches: Mapping[str, Batch]) -> Dict[str, Batch]:
    normalized: Dict[str, Batch] = {}
    for raw_key, batch in batches.items():
        batch_id = resolve_batch_sort_batch_id(raw_key, batch)
        if not batch_id:
            raise ValidationError(f"批次号不能为空：来源值={raw_key!r}", field="batch_id")
        if batch_id in normalized:
            raise ValidationError(f"批次号重复：{batch_id!r}", field="batch_id")
        normalized[batch_id] = batch
    return normalized


def normalize_batch_order_override(
    batch_order_override: Optional[Sequence[str]], batches: Mapping[str, Batch],
) -> List[str]:
    if not batch_order_override:
        return []
    seen = set()
    override_order: List[str] = []
    for item in batch_order_override:
        batch_id = normalize_text_id(item)
        if not batch_id:
            raise ValidationError("批次顺序里存在空的批次号", field="batch_order_override")
        if batch_id not in batches:
            raise ValidationError(f"批次顺序覆盖引用了不存在的批次：{batch_id}", field="batch_order_override")
        if batch_id in seen:
            raise ValidationError(f"批次顺序覆盖存在重复批次：{batch_id}", field="batch_order_override")
        seen.add(batch_id)
        override_order.append(batch_id)
    return override_order


def _parse_created_at_for_sort(value: Any, *, strategy: SortStrategy) -> Optional[datetime]:
    # 只有 FIFO 按创建时间排序，才把它当必须合法的输入。
    if strategy == SortStrategy.FIFO:
        return parse_optional_datetime(value, field="created_at")
    return parse_datetime(value)


def build_batch_sort_inputs(
    batches: Mapping[str, Batch],
    *,
    strategy: SortStrategy,
    readiness_gate_enabled: bool = False,
) -> List[BatchForSort]:
    batch_for_sort: List[BatchForSort] = []
    for batch_key, batch in batches.items():
        batch_id = resolve_batch_sort_batch_id(batch_key, batch)
        if not batch_id:
            raise ValidationError(f"批次号不能为空：来源值={batch_key!r}", field="batch_id")
        batch_for_sort.append(
            BatchForSort(
                batch_id=batch_id,
                priority=batch.priority,
                due_date=parse_optional_date(batch.due_date, field="due_date"),
                ready_date=parse_optional_date(batch.ready_date, field="ready_date") if readiness_gate_enabled else None,
                created_at=_parse_created_at_for_sort(batch.created_at, strategy=strategy),
            )
        )
    return batch_for_sort


def operation_sort_key(op: OpForScheduleAlgo, batch_order: Mapping[str, int]) -> Tuple[int, str, int, int]:
    return batch_order.get(op.batch_id, 999999), op.batch_id, op.seq, op.id
