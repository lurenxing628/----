from __future__ import annotations

from typing import Any, Dict, List

from core.models.enums import YesNo
from core.services.common.normalization_matrix import normalize_skill_level_value, normalize_yes_no_narrow_value

_OPERATOR_PRIMARY_TRUE_ALIASES = ("主操", "主", "on")
_OPERATOR_PRIMARY_FALSE_ALIASES = ("非主操", "非主", "off")


def normalize_skill_level_stored(value: Any) -> str:
    return normalize_skill_level_value(value, unknown_policy="default")


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
