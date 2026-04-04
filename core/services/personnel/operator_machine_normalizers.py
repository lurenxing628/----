from __future__ import annotations

from typing import Any, Optional

from core.infrastructure.errors import ValidationError
from core.models import OperatorMachine
from core.models.enums import SkillLevel, YesNo
from core.services.common.normalization_matrix import normalize_skill_level_value, normalize_yes_no_narrow_value
from core.services.common.normalize import normalize_text

_OPERATOR_PRIMARY_TRUE_ALIASES = ("主操", "主", "on")
_OPERATOR_PRIMARY_FALSE_ALIASES = ("非主操", "非主", "off")


def normalize_operator_machine_text(value: Any) -> Optional[str]:
    return normalize_text(value)


def normalize_skill_level_optional(value: Any) -> Optional[str]:
    """规范化技能等级（可选列；空/缺失返回 None）。"""
    try:
        return normalize_skill_level_value(value, default=SkillLevel.NORMAL.value, allow_none=True, unknown_policy="raise")
    except ValueError as e:
        raise ValidationError(
            "“技能等级”不正确，可填写：初级 / 普通 / 熟练（也兼容 beginner / normal / expert）。",
            field="技能等级",
        ) from e


def normalize_yes_no_optional(value: Any, field: str) -> Optional[str]:
    """规范化 yes/no（可选列；空/缺失返回 None）。"""
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return normalize_yes_no_narrow_value(
            value,
            default=YesNo.NO.value,
            unknown_policy="raise",
            true_aliases=_OPERATOR_PRIMARY_TRUE_ALIASES,
            false_aliases=_OPERATOR_PRIMARY_FALSE_ALIASES,
        )
    except ValueError as e:
        raise ValidationError(
            "“主操设备”不正确，可填写：是 / 否 / 主操 / 非主操（也兼容 yes/no、true/false、1/0、on/off）。",
            field=field,
        ) from e


def normalize_skill_level_stored(value: Any) -> str:
    try:
        return str(
            normalize_skill_level_value(
                value,
                default=SkillLevel.NORMAL.value,
                allow_none=False,
                unknown_policy="default",
            )
        )
    except ValueError:
        return SkillLevel.NORMAL.value


def normalize_yes_no_stored(value: Any) -> str:
    try:
        return normalize_yes_no_narrow_value(
            value,
            default=YesNo.NO.value,
            unknown_policy="default",
            true_aliases=_OPERATOR_PRIMARY_TRUE_ALIASES,
            false_aliases=_OPERATOR_PRIMARY_FALSE_ALIASES,
        )
    except ValueError:
        return YesNo.NO.value


def normalize_link_record(link: OperatorMachine) -> OperatorMachine:
    link.skill_level = normalize_skill_level_stored(getattr(link, "skill_level", None))
    link.is_primary = normalize_yes_no_stored(getattr(link, "is_primary", None))
    return link
