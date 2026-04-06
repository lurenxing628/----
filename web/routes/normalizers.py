from __future__ import annotations

from typing import Any

from core.models.enums import BatchPriority, CalendarDayType, ReadyStatus, YesNo
from core.services.common.normalization_matrix import (
    normalize_batch_priority_value,
    normalize_calendar_day_type_value,
    normalize_ready_status_value,
    normalize_yes_no_narrow_value,
)


def _normalize_batch_priority(value: Any) -> str:
    """
    批次优先级标准化（Route 层宽松 normalize：未知值原样返回，供上层显式校验时报错展示）。
    """
    return normalize_batch_priority_value(
        value,
        default=BatchPriority.NORMAL.value,
        unknown_policy="passthrough",
    )


def _normalize_ready_status(value: Any) -> str:
    """
    齐套状态标准化（Route 层宽松 normalize：未知值原样返回，供上层显式校验时报错展示）。

    约定：
    - 兼容中文：齐套/未齐套/部分齐套、是/否
    - 缺省：按 V1.1 规则视为 yes
    """
    return normalize_ready_status_value(
        value,
        default=ReadyStatus.YES.value,
        unknown_policy="passthrough",
    )


def _normalize_day_type(value: Any) -> str:
    """
    日历类型标准化（Route 层宽松 normalize：未知值原样返回，供上层显式校验时报错展示）。

    - weekend/周末 -> holiday（统一口径）
    """
    return normalize_calendar_day_type_value(
        value,
        default=CalendarDayType.WORKDAY.value,
        unknown_policy="passthrough",
    )


def _normalize_operator_calendar_day_type(value: Any) -> str:
    """
    人员专属日历类型标准化：与 `_normalize_day_type` 同口径。
    """
    return _normalize_day_type(value)


def _normalize_yesno(value: Any) -> str:
    """
    yes/no 标准化（Route 层宽松 normalize：未知值原样返回，供上层显式校验时报错展示）。

    约定：
    - 兼容中文：是/否
    - 缺省：yes
    """
    return normalize_yes_no_narrow_value(
        value,
        default=YesNo.YES.value,
        unknown_policy="passthrough",
    )


def normalize_version_or_latest(value: Any, *, latest_version: int) -> int:
    """
    版本号入口统一口径：空值、非整数、0、负数统一回退到最新版本。
    """
    latest = int(latest_version or 0)
    if value is None:
        return latest
    text = str(value).strip()
    if not text:
        return latest
    try:
        version = int(text)
    except Exception:
        return latest
    return version if version > 0 else latest
