from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import ValidationError
from core.shared.strict_parse import parse_optional_date, parse_optional_datetime, parse_required_int

from .greedy.date_parsers import parse_date, parse_datetime
from .sort_strategies import BatchForSort, SortStrategy


def normalize_text_id(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception as exc:
        raise ValidationError("文本标识无法转换为字符串", field="id") from exc


def resolve_batch_sort_batch_id(batch_key: Any, batch: Any) -> str:
    normalized_key = normalize_text_id(batch_key)
    if normalized_key:
        return normalized_key
    return normalize_text_id(getattr(batch, "batch_id", None))


def build_normalized_batches_map(batches: Optional[Dict[str, Any]], *, warnings: Optional[List[str]] = None) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for raw_key, batch in (batches or {}).items():
        batch_id = resolve_batch_sort_batch_id(raw_key, batch)
        if not batch_id:
            raise ValidationError(f"批次号不能为空：来源值={raw_key!r}", field="batch_id")
        if batch_id in normalized:
            raise ValidationError(f"批次号重复：{batch_id!r}", field="batch_id")
        normalized[batch_id] = batch
    return normalized


def normalize_batch_order_override(batch_order_override: Optional[List[Any]], batches: Dict[str, Any]) -> List[str]:
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


def _parse_due_date_for_sort(value: Any, *, strict_mode: bool) -> Optional[Any]:
    return parse_optional_date(value, field="due_date") if strict_mode else parse_date(value)


def _parse_ready_date_for_sort(value: Any, *, strict_mode: bool) -> Optional[Any]:
    return parse_optional_date(value, field="ready_date") if strict_mode else parse_date(value)


def parse_ready_date_for_sort(value: Any, *, strict_mode: bool) -> Optional[Any]:
    return _parse_ready_date_for_sort(value, strict_mode=bool(strict_mode))


def _parse_created_at_for_sort(value: Any, *, strict_mode: bool, strategy: SortStrategy) -> Optional[datetime]:
    if strict_mode and strategy == SortStrategy.FIFO:
        return parse_optional_datetime(value, field="created_at")
    return parse_datetime(value)


def build_batch_sort_inputs(
    batches: Dict[str, Any],
    *,
    strict_mode: bool,
    strategy: SortStrategy,
) -> List[BatchForSort]:
    batch_for_sort: List[BatchForSort] = []
    for batch_key, batch in (batches or {}).items():
        batch_id = resolve_batch_sort_batch_id(batch_key, batch)
        if not batch_id:
            raise ValidationError(f"批次号不能为空：来源值={batch_key!r}", field="batch_id")
        batch_for_sort.append(
            BatchForSort(
                batch_id=batch_id,
                priority=str(getattr(batch, "priority", "") or "normal"),
                due_date=_parse_due_date_for_sort(getattr(batch, "due_date", None), strict_mode=bool(strict_mode)),
                ready_status=str(getattr(batch, "ready_status", "") or "yes"),
                ready_date=_parse_ready_date_for_sort(getattr(batch, "ready_date", None), strict_mode=bool(strict_mode)),
                created_at=_parse_created_at_for_sort(
                    getattr(batch, "created_at", None), strict_mode=bool(strict_mode), strategy=strategy
                ),
            )
        )
    return batch_for_sort


def operation_sort_key(op: Any, batch_order: Dict[str, int]) -> Tuple[int, str, int, int]:
    batch_id = normalize_text_id(getattr(op, "batch_id", ""))
    return (
        int(batch_order.get(batch_id, 999999)),
        batch_id,
        parse_required_int(getattr(op, "seq", 0), field="seq"),
        parse_required_int(getattr(op, "id", 0), field="id"),
    )
