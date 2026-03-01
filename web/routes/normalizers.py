from __future__ import annotations

from typing import Any

from core.models.enums import BatchPriority, CalendarDayType, ReadyStatus, YesNo
from core.services.common.enum_normalizers import normalize_yesno_narrow


def _normalize_batch_priority(value: Any) -> str:
    """
    批次优先级标准化（Route 层宽松 normalize：未知值原样返回，供上层显式校验时报错展示）。
    """
    v = "" if value is None else str(value).strip()
    v_lower = v.lower()
    if v == "普通" or v_lower == BatchPriority.NORMAL.value:
        return BatchPriority.NORMAL.value
    if v in ("急", "急件") or v_lower == BatchPriority.URGENT.value:
        return BatchPriority.URGENT.value
    if v == "特急" or v_lower == BatchPriority.CRITICAL.value:
        return BatchPriority.CRITICAL.value
    return v or BatchPriority.NORMAL.value


def _normalize_ready_status(value: Any) -> str:
    """
    齐套状态标准化（Route 层宽松 normalize：未知值原样返回，供上层显式校验时报错展示）。

    约定：
    - 兼容中文：齐套/未齐套/部分齐套、是/否
    - 缺省：按 V1.1 规则视为 yes
    """
    v = "" if value is None else str(value).strip()
    v_lower = v.lower()
    if v in ("齐套", "是") or v_lower == ReadyStatus.YES.value:
        return ReadyStatus.YES.value
    if v == "部分齐套" or v_lower == ReadyStatus.PARTIAL.value:
        return ReadyStatus.PARTIAL.value
    if v in ("未齐套", "否") or v_lower == ReadyStatus.NO.value:
        return ReadyStatus.NO.value
    return v or ReadyStatus.YES.value


def _normalize_day_type(value: Any) -> str:
    """
    日历类型标准化（Route 层宽松 normalize：未知值原样返回，供上层显式校验时报错展示）。

    - weekend/周末 -> holiday（统一口径）
    """
    v = "" if value is None else str(value).strip()
    v_lower = v.lower()
    if v == "工作日" or v_lower == CalendarDayType.WORKDAY.value:
        return CalendarDayType.WORKDAY.value
    if v == "周末" or v_lower == CalendarDayType.WEEKEND.value:
        return CalendarDayType.HOLIDAY.value
    if v in ("节假日", "假期") or v_lower == CalendarDayType.HOLIDAY.value:
        return CalendarDayType.HOLIDAY.value
    return v or CalendarDayType.WORKDAY.value


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
    return normalize_yesno_narrow(value, default=YesNo.YES.value, unknown_policy="passthrough")

