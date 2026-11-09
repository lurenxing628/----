from __future__ import annotations

from typing import Any, List, Mapping, Optional, Sequence, Tuple

from core.errors import ValidationError
from core.models.batch import Batch

from .types import OpForScheduleAlgo


def clean_resource_id(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    return text if text.strip() else ""


def normalize_batch_order_override(
    batch_order_override: Optional[Sequence[str]], batches: Mapping[str, Batch],
) -> List[str]:
    if not batch_order_override:
        return []
    seen = set()
    override_order: List[str] = []
    for batch_id in batch_order_override:
        if batch_id not in batches:
            raise ValidationError(f"批次顺序覆盖引用了不存在的批次：{batch_id}", field="batch_order_override")
        if batch_id in seen:
            raise ValidationError(f"批次顺序覆盖存在重复批次：{batch_id}", field="batch_order_override")
        seen.add(batch_id)
        override_order.append(batch_id)
    return override_order


def operation_sort_key(op: OpForScheduleAlgo, batch_order: Mapping[str, int]) -> Tuple[int, str, int, int]:
    return batch_order.get(op.batch_id, 999999), op.batch_id, op.seq, op.id
