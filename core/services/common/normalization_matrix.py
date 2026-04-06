from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

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
_YES_NO_TRUE_WIDE = _YES_NO_TRUE_NARROW + ("on",)
_YES_NO_FALSE_WIDE = _YES_NO_FALSE_NARROW + ("off", "")

_SKILL_LEVEL_ALIAS_MAP: Dict[str, str] = {
    SkillLevel.BEGINNER.value: SkillLevel.BEGINNER.value,
    SkillLevel.NORMAL.value: SkillLevel.NORMAL.value,
    SkillLevel.EXPERT.value: SkillLevel.EXPERT.value,
    SkillLevel.SKILLED.value: SkillLevel.EXPERT.value,
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

SKILL_LEVEL_CANONICAL_VALUES: Tuple[str, ...] = (
    SkillLevel.BEGINNER.value,
    SkillLevel.NORMAL.value,
    SkillLevel.EXPERT.value,
)
SKILL_LEVEL_OPTION_LABELS: Dict[str, str] = {
    SkillLevel.BEGINNER.value: "初级",
    SkillLevel.NORMAL.value: "普通",
    SkillLevel.EXPERT.value: "熟练",
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_default_yes_no(default: str) -> str:
    text = _text(default).lower()
    return YesNo.YES.value if text in ("y", YesNo.YES.value, "true", "1", "on") else YesNo.NO.value


def _unknown_result(text: str, *, default: str, unknown_policy: str) -> str:
    policy = str(unknown_policy or "passthrough").strip().lower()
    if policy == "default":
        return str(default)
    if policy == "raise":
        raise ValueError(text)
    return text


def _enum_alias_lookup(
    value: Any,
    *,
    alias_map: Dict[str, str],
    default: str,
    unknown_policy: str,
) -> str:
    text = _text(value)
    if text == "":
        return str(default)
    mapped = alias_map.get(text)
    if mapped is not None:
        return mapped
    mapped = alias_map.get(text.lower())
    if mapped is not None:
        return mapped
    return _unknown_result(text, default=str(default), unknown_policy=unknown_policy)


def normalize_batch_priority_value(
    value: Any,
    *,
    default: str = BatchPriority.NORMAL.value,
    unknown_policy: str = "passthrough",
) -> str:
    return _enum_alias_lookup(value, alias_map=_BATCH_PRIORITY_ALIAS_MAP, default=default, unknown_policy=unknown_policy)


def normalize_ready_status_value(
    value: Any,
    *,
    default: str = ReadyStatus.YES.value,
    unknown_policy: str = "passthrough",
) -> str:
    return _enum_alias_lookup(value, alias_map=_READY_STATUS_ALIAS_MAP, default=default, unknown_policy=unknown_policy)


def normalize_calendar_day_type_value(
    value: Any,
    *,
    default: str = CalendarDayType.WORKDAY.value,
    unknown_policy: str = "passthrough",
) -> str:
    return _enum_alias_lookup(value, alias_map=_CALENDAR_DAY_TYPE_ALIAS_MAP, default=default, unknown_policy=unknown_policy)


def _merge_aliases(values: Optional[Sequence[str]]) -> Tuple[str, ...]:
    out = []
    for item in list(values or ()):
        text = _text(item)
        if text:
            out.append(text)
    return tuple(out)


def normalize_yes_no_narrow_value(
    value: Any,
    *,
    default: str = YesNo.YES.value,
    unknown_policy: str = "passthrough",
    true_aliases: Optional[Sequence[str]] = None,
    false_aliases: Optional[Sequence[str]] = None,
) -> str:
    default_norm = _normalize_default_yes_no(default)
    text = _text(value)
    if text == "":
        return default_norm

    lowered = text.lower()
    if text == "是" or lowered in _YES_NO_TRUE_NARROW or lowered in {item.lower() for item in _merge_aliases(true_aliases)}:
        return YesNo.YES.value
    if text == "否" or lowered in _YES_NO_FALSE_NARROW or lowered in {item.lower() for item in _merge_aliases(false_aliases)}:
        return YesNo.NO.value
    return _unknown_result(text, default=default_norm, unknown_policy=unknown_policy)


def normalize_yes_no_wide_value(
    value: Any,
    *,
    default: str = YesNo.NO.value,
    unknown_policy: str = "no",
    true_aliases: Optional[Sequence[str]] = None,
    false_aliases: Optional[Sequence[str]] = None,
) -> str:
    default_norm = _normalize_default_yes_no(default)
    if value is None:
        return default_norm
    text = _text(value)
    lowered = text.lower()
    if text == "":
        return YesNo.NO.value
    if text == "是" or lowered in _YES_NO_TRUE_WIDE or lowered in {item.lower() for item in _merge_aliases(true_aliases)}:
        return YesNo.YES.value
    if text == "否" or lowered in _YES_NO_FALSE_WIDE or lowered in {item.lower() for item in _merge_aliases(false_aliases)}:
        return YesNo.NO.value

    policy = str(unknown_policy or "no").strip().lower()
    if policy == "default":
        return default_norm
    if policy == "passthrough":
        return text
    if policy == "raise":
        raise ValueError(text)
    return YesNo.NO.value


def normalize_skill_level_value(
    value: Any,
    *,
    default: str = SkillLevel.NORMAL.value,
    allow_none: bool = False,
    unknown_policy: str = "raise",
) -> Optional[str]:
    text = _text(value)
    if text == "":
        if allow_none:
            return None
        return normalize_skill_level_value(default, default=SkillLevel.NORMAL.value, allow_none=False, unknown_policy="raise")

    mapped = _SKILL_LEVEL_ALIAS_MAP.get(text)
    if mapped is not None:
        return mapped
    mapped = _SKILL_LEVEL_ALIAS_MAP.get(text.lower())
    if mapped is not None:
        return mapped

    policy = str(unknown_policy or "raise").strip().lower()
    if policy == "default":
        return normalize_skill_level_value(default, default=SkillLevel.NORMAL.value, allow_none=False, unknown_policy="raise")
    if policy == "passthrough":
        return text.lower()
    raise ValueError(f"invalid skill_level: {text!r}")


def skill_level_rank(value: Any) -> int:
    try:
        normalized = normalize_skill_level_value(
            value,
            default=SkillLevel.NORMAL.value,
            allow_none=True,
            unknown_policy="raise",
        )
    except Exception:
        return 9
    if normalized is None:
        return 9
    if normalized == SkillLevel.EXPERT.value:
        return 0
    if normalized == SkillLevel.NORMAL.value:
        return 1
    if normalized == SkillLevel.BEGINNER.value:
        return 2
    return 9


def skill_level_options() -> Tuple[Tuple[str, str], ...]:
    return tuple((value, SKILL_LEVEL_OPTION_LABELS[value]) for value in SKILL_LEVEL_CANONICAL_VALUES)


def iter_skill_level_values() -> Iterable[str]:
    return tuple(SKILL_LEVEL_CANONICAL_VALUES)
