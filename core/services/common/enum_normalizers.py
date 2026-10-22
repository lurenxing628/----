from __future__ import annotations

from typing import Any

from core.models.enums import (
    BatchPriority,
    ReadyStatus,
    SupplierStatus,
)
from core.services.common.normalization_matrix import (
    normalize_batch_priority_value,
    normalize_ready_status_value,
    skill_level_rank,
)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def normalize_supplier_status(value: Any) -> str:
    """
    标准化供应商状态（Suppliers.status）。

    约定（保持既有 Excel 导入口径）：
    - 空值默认 active
    - 中文别名/英文枚举：大小写不敏感，返回标准小写
    - 其它未知值：原样透传（由调用方决定是否报错）
    """
    v = _text(value)
    if not v:
        return SupplierStatus.ACTIVE.value

    if v in ("启用", "在用", "正常"):
        return SupplierStatus.ACTIVE.value
    if v in ("停用", "禁用"):
        return SupplierStatus.INACTIVE.value

    v_lower = v.lower()
    if v_lower in (SupplierStatus.ACTIVE.value, SupplierStatus.INACTIVE.value):
        return v_lower
    return v


def skill_rank(value: Any) -> int:
    return skill_level_rank(value)


def batch_priority_label(value: Any) -> str:
    v = normalize_batch_priority_value(value, default=BatchPriority.NORMAL.value, unknown_policy="passthrough")
    if v == BatchPriority.CRITICAL.value:
        return "特急"
    if v == BatchPriority.URGENT.value:
        return "急件"
    if v == BatchPriority.NORMAL.value:
        return "普通"
    return v or "未知"


def ready_status_label(value: Any) -> str:
    v = normalize_ready_status_value(value, default=ReadyStatus.YES.value, unknown_policy="passthrough")
    if v == ReadyStatus.YES.value:
        return "齐套"
    if v == ReadyStatus.NO.value:
        return "未齐套"
    if v == ReadyStatus.PARTIAL.value:
        return "部分齐套"
    return v or "未知"
