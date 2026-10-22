"""Normalize captured personnel-machine rows for the resource workbench."""

from __future__ import annotations

from typing import Any, Dict, List

from core.models.enums import YesNo
from core.services.common.normalization_matrix import normalize_skill_level_value
from core.shared.boolean_normalize import normalize_yes_no_wide


def _readside_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _normalize_skill_field(out: Dict[str, Any], dirty_fields: List[str]) -> None:
    raw_skill = out.get("skill_level")
    raw_skill_text = _readside_text(raw_skill)
    try:
        out["skill_level"] = normalize_skill_level_value(raw_skill, allow_none=False, unknown_policy="raise")
    except ValueError:
        out["skill_level"] = "normal"
        dirty_fields.append("skill_level")
    else:
        if raw_skill is None or raw_skill_text == "" or raw_skill_text.lower() != out["skill_level"]:
            dirty_fields.append("skill_level")


def _normalize_primary_field(out: Dict[str, Any], dirty_fields: List[str]) -> None:
    raw_primary = out.get("is_primary")
    raw_primary_text = _readside_text(raw_primary)
    out["is_primary"] = normalize_yes_no_wide(raw_primary, default=YesNo.NO.value, unknown_policy="no")
    if raw_primary is None or raw_primary_text == "" or raw_primary_text.lower() != out["is_primary"].lower():
        dirty_fields.append("is_primary")


class OperatorMachineQueryService:
    """Shared normalization for captured rows; reads belong to the repository."""

    @staticmethod
    def _normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(row)
        dirty_fields: List[str] = []
        if "skill_level" in out:
            _normalize_skill_field(out, dirty_fields)
        if "is_primary" in out:
            _normalize_primary_field(out, dirty_fields)
        if dirty_fields:
            out["dirty_fields"] = dirty_fields
        return out

    @classmethod
    def _normalize_rows(cls, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [cls._normalize_row(row) for row in rows]
