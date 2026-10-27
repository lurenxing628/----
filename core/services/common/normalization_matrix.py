from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from core.models.enums import BatchPriority, CalendarDayType, ReadyStatus, SkillLevel, YesNo

_BATCH_PRIORITY_ALIAS_MAP: Dict[str, str] = {
    BatchPriority.NORMAL.value: BatchPriority.NORMAL.value,
    BatchPriority.URGENT.value: BatchPriority.URGENT.value,
    BatchPriority.CRITICAL.value: BatchPriority.CRITICAL.value,
    "普通": BatchPriority.NORMAL.value,
    "急": BatchPriority.URGENT.value,
    "急件": BatchPriority.URGENT.value,
    "特急": BatchPriority.CRITICAL.value,
}

_READY_STATUS_ALIAS_MAP: Dict[str, str] = {
    ReadyStatus.YES.value: ReadyStatus.YES.value,
    ReadyStatus.NO.value: ReadyStatus.NO.value,
    ReadyStatus.PARTIAL.value: ReadyStatus.PARTIAL.value,
    "齐套": ReadyStatus.YES.value,
    "未齐套": ReadyStatus.NO.value,
    "部分齐套": ReadyStatus.PARTIAL.value,
    "是": ReadyStatus.YES.value,
    "否": ReadyStatus.NO.value,
}

_CALENDAR_DAY_TYPE_ALIAS_MAP: Dict[str, str] = {
    CalendarDayType.WORKDAY.value: CalendarDayType.WORKDAY.value,
    CalendarDayType.WEEKEND.value: CalendarDayType.HOLIDAY.value,
    CalendarDayType.HOLIDAY.value: CalendarDayType.HOLIDAY.value,
    "工作日": CalendarDayType.WORKDAY.value,
    "周末": CalendarDayType.HOLIDAY.value,
    "节假日": CalendarDayType.HOLIDAY.value,
    "假期": CalendarDayType.HOLIDAY.value,
}

_YES_NO_TRUE_NARROW = ("y", YesNo.YES.value, "true", "1")
_YES_NO_FALSE_NARROW = ("n", YesNo.NO.value, "false", "0")

_SKILL_LEVEL_ALIAS_MAP: Dict[str, str] = {
    SkillLevel.BEGINNER.value: SkillLevel.BEGINNER.value,
    SkillLevel.NORMAL.value: SkillLevel.NORMAL.value,
    SkillLevel.EXPERT.value: SkillLevel.EXPERT.value,
    "low": SkillLevel.BEGINNER.value,
    "high": SkillLevel.EXPERT.value,
    "初级": SkillLevel.BEGINNER.value,
    "新手": SkillLevel.BEGINNER.value,
    "普通": SkillLevel.NORMAL.value,
    "一般": SkillLevel.NORMAL.value,
    "中级": SkillLevel.NORMAL.value,
    "熟练": SkillLevel.EXPERT.value,
    "高级": SkillLevel.EXPERT.value,
    "专家": SkillLevel.EXPERT.value,
}

_SKILL_LEVEL_RANK = {SkillLevel.EXPERT.value: 0, SkillLevel.NORMAL.value: 1, SkillLevel.BEGINNER.value: 2}


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _lookup_alias(alias_map: Dict[str, str], text: str) -> Optional[str]:
    return alias_map.get(text) or alias_map.get(text.lower())


def normalize_batch_priority_value(
    value: Any,
    *,
    default: str,
) -> str:
    text = _text(value)
    if not text:
        return default
    mapped = _lookup_alias(_BATCH_PRIORITY_ALIAS_MAP, text)
    return mapped if mapped is not None else text


def normalize_ready_status_value(
    value: Any,
    *,
    default: str,
) -> str:
    text = _text(value)
    if not text:
        return default
    mapped = _lookup_alias(_READY_STATUS_ALIAS_MAP, text)
    return mapped if mapped is not None else text


def normalize_calendar_day_type_value(
    value: Any,
    *,
    default: str,
) -> str:
    text = _text(value)
    if not text:
        return default
    mapped = _lookup_alias(_CALENDAR_DAY_TYPE_ALIAS_MAP, text)
    if mapped is not None:
        return mapped
    raise ValueError(text)


def normalize_yes_no_narrow_value(
    value: Any,
    *,
    default: str,
    true_aliases: Optional[Sequence[str]] = None,
    false_aliases: Optional[Sequence[str]] = None,
) -> str:
    text = _text(value)
    if not text:
        return default

    lowered = text.lower()
    if text == "是" or lowered in _YES_NO_TRUE_NARROW or lowered in {alias.lower() for item in (true_aliases or ()) if (alias := _text(item))}:
        return YesNo.YES.value
    if text == "否" or lowered in _YES_NO_FALSE_NARROW or lowered in {alias.lower() for item in (false_aliases or ()) if (alias := _text(item))}:
        return YesNo.NO.value
    raise ValueError(text)


def normalize_skill_level_value(
    value: Any,
) -> str:
    text = _text(value)
    if not text:
        raise ValueError(f"Invalid skill_level: {value!r}")
    mapped = _lookup_alias(_SKILL_LEVEL_ALIAS_MAP, text)
    if mapped is not None:
        return mapped
    raise ValueError(text)


def skill_level_rank(value: Any) -> int:
    text = _text(value)
    normalized = _lookup_alias(_SKILL_LEVEL_ALIAS_MAP, text)
    # 不认识的等级排在所有已知等级之后。
    return 9 if normalized is None else _SKILL_LEVEL_RANK[normalized]
