from __future__ import annotations

from typing import Any

from core.models.enums import (
    BatchPriority,
    ReadyStatus,
)
from core.services.common.normalization_matrix import (
    normalize_batch_priority_value,
    normalize_ready_status_value,
)


def batch_priority_label(value: Any) -> str:
    v = normalize_batch_priority_value(value, default=BatchPriority.NORMAL.value)
    if v == BatchPriority.CRITICAL.value:
        return "特急"
    if v == BatchPriority.URGENT.value:
        return "急件"
    if v == BatchPriority.NORMAL.value:
        return "普通"
    return v


def ready_status_label(value: Any) -> str:
    v = normalize_ready_status_value(value, default=ReadyStatus.YES.value)
    if v == ReadyStatus.YES.value:
        return "齐套"
    if v == ReadyStatus.NO.value:
        return "未齐套"
    if v == ReadyStatus.PARTIAL.value:
        return "部分齐套"
    return v
