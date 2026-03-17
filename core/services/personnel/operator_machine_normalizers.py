from __future__ import annotations

from typing import Any, Optional

from core.infrastructure.errors import ValidationError
from core.models import OperatorMachine
from core.models.enums import YesNo
from core.services.common.enum_normalizers import normalize_skill_level
from core.services.common.normalize import normalize_text


def normalize_operator_machine_text(value: Any) -> Optional[str]:
    return normalize_text(value)


def normalize_skill_level_optional(value: Any) -> Optional[str]:
    """规范化技能等级（可选列；空/缺失返回 None）。"""
    try:
        return normalize_skill_level(value, default="normal", allow_none=True)
    except ValueError as e:
        raise ValidationError(
            "“技能等级”不正确，可填写：初级 / 普通 / 熟练（也兼容 beginner / normal / expert）。",
            field="技能等级",
        ) from e


def normalize_yes_no_optional(value: Any, field: str) -> Optional[str]:
    """规范化 yes/no（可选列；空/缺失返回 None）。"""
    if value is None:
        return None
    s = str(value).strip()
    if s == "":
        return None
    low = s.lower()
    if low in ("yes", "y", "true", "1", "on") or s in ("是", "主操", "主"):
        return YesNo.YES.value
    if low in ("no", "n", "false", "0", "off") or s in ("否", "非主操", "非主"):
        return YesNo.NO.value
    raise ValidationError(
        "“主操设备”不正确，可填写：是 / 否 / 主操 / 非主操（也兼容 yes/no、true/false、1/0、on/off）。",
        field=field,
    )


def normalize_skill_level_stored(value: Any) -> str:
    try:
        return normalize_skill_level(value, default="normal", allow_none=False)
    except ValueError:
        return "normal"


def normalize_yes_no_stored(value: Any) -> str:
    if value is None:
        return YesNo.NO.value
    s = str(value).strip()
    if s == "":
        return YesNo.NO.value
    low = s.lower()
    if low in ("yes", "y", "true", "1", "on") or s in ("是", "主操", "主"):
        return YesNo.YES.value
    if low in ("no", "n", "false", "0", "off") or s in ("否", "非主操", "非主"):
        return YesNo.NO.value
    return YesNo.NO.value


def normalize_link_record(link: OperatorMachine) -> OperatorMachine:
    link.skill_level = normalize_skill_level_stored(getattr(link, "skill_level", None))
    link.is_primary = normalize_yes_no_stored(getattr(link, "is_primary", None))
    return link
