from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.errors import ValidationError
from core.models.enums import YesNo
from core.services.common.normalization_matrix import normalize_skill_level_value, normalize_yes_no_narrow_value

_OPERATOR_PRIMARY_TRUE_ALIASES = ("主操", "主", "on")
_OPERATOR_PRIMARY_FALSE_ALIASES = ("非主操", "非主", "off")


def normalize_skill_level_optional(value: Any) -> Optional[str]:
    """规范化技能等级（可选列；空/缺失返回 None）。"""
    try:
        return normalize_skill_level_value(value, allow_none=True, unknown_policy="raise")
    except ValueError as e:
        raise ValidationError(
            "“技能等级”不正确，可填写：初级 / 普通 / 熟练。以前的 Excel 如果写过英文技能等级，系统会尽量按中文意思读取；新文件请直接填中文。",
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
            "“主操设备”不正确，可填写：是 / 否 / 主操 / 非主操。以前的 Excel 如果写过英文，系统会尽量按中文意思读取；新文件请直接填中文。",
            field=field,
        ) from e


def normalize_skill_level_stored(value: Any) -> str:
    return str(
        normalize_skill_level_value(
            value,
            allow_none=False,
            unknown_policy="default",
        )
    )


def normalize_yes_no_stored(value: Any) -> str:
    return normalize_yes_no_narrow_value(
        value,
        default=YesNo.NO.value,
        unknown_policy="default",
        true_aliases=_OPERATOR_PRIMARY_TRUE_ALIASES,
        false_aliases=_OPERATOR_PRIMARY_FALSE_ALIASES,
    )


def _readside_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _normalize_skill_field(out: Dict[str, Any], dirty_fields: List[str]) -> None:
    raw_skill = out.get("skill_level")
    raw_skill_text = _readside_text(raw_skill)
    out["skill_level"] = normalize_skill_level_stored(raw_skill)
    if raw_skill is None or raw_skill_text == "" or raw_skill_text.lower() != out["skill_level"]:
        dirty_fields.append("skill_level")


def _normalize_primary_field(out: Dict[str, Any], dirty_fields: List[str]) -> None:
    raw_primary = out.get("is_primary")
    raw_primary_text = _readside_text(raw_primary)
    out["is_primary"] = normalize_yes_no_stored(raw_primary)
    if raw_primary is None or raw_primary_text == "" or raw_primary_text.lower() != out["is_primary"].lower():
        dirty_fields.append("is_primary")


def normalize_operator_machine_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize captured personnel-machine rows for the resource workbench."""
    out = dict(row)
    dirty_fields: List[str] = []
    if "skill_level" in out:
        _normalize_skill_field(out, dirty_fields)
    if "is_primary" in out:
        _normalize_primary_field(out, dirty_fields)
    if dirty_fields:
        out["dirty_fields"] = dirty_fields
    return out
