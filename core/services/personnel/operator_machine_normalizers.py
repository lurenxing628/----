from __future__ import annotations

from typing import Any, Dict, List

from core.models.enums import YesNo
from core.services.common.normalization_matrix import normalize_skill_level_value, normalize_yes_no_narrow_value

_OPERATOR_PRIMARY_TRUE_ALIASES = ("主操", "主", "on")
_OPERATOR_PRIMARY_FALSE_ALIASES = ("非主操", "非主", "off")


def _require_stored_text(value: Any, field: str) -> str:
    if value is None or isinstance(value, bool):
        raise ValueError(f"Invalid stored {field}: {value!r}")
    text = str(value).strip()
    if not text:
        raise ValueError(f"Invalid stored {field}: {value!r}")
    return text


def normalize_skill_level_stored(value: Any) -> str:
    text = _require_stored_text(value, "skill_level")
    return normalize_skill_level_value(text)


def normalize_yes_no_stored(value: Any) -> str:
    text = _require_stored_text(value, "is_primary")
    return normalize_yes_no_narrow_value(
        text,
        default=YesNo.NO.value,
        true_aliases=_OPERATOR_PRIMARY_TRUE_ALIASES,
        false_aliases=_OPERATOR_PRIMARY_FALSE_ALIASES,
    )


def _normalize_skill_field(out: Dict[str, Any], dirty_fields: List[str]) -> None:
    raw_skill = out["skill_level"]
    normalized = normalize_skill_level_stored(raw_skill)
    out["skill_level"] = normalized
    if str(raw_skill).strip().lower() != normalized:
        dirty_fields.append("skill_level")


def _normalize_primary_field(out: Dict[str, Any], dirty_fields: List[str]) -> None:
    raw_primary = out["is_primary"]
    normalized = normalize_yes_no_stored(raw_primary)
    out["is_primary"] = normalized
    if str(raw_primary).strip().lower() != normalized:
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
