from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE

from .schedule_result_view_context import serialize_plan_role_options

_HISTORICAL_ADOPTED_LABEL = "历史正式方案（已被新版本替代）"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _plan_resolution_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        nested = value.get("plan_resolution")
        return dict(nested) if isinstance(nested, dict) else dict(value)
    plan_resolution = getattr(value, "plan_resolution", None)
    return dict(plan_resolution) if isinstance(plan_resolution, dict) else {}


def _option_source_table(option: Dict[str, Any]) -> str:
    return _text(option.get("source_table"))


def _resolution_source_table(plan_resolution: Dict[str, Any]) -> str:
    plan_identity = plan_resolution.get("plan_identity")
    identity = plan_identity if isinstance(plan_identity, dict) else {}
    return _text(plan_resolution.get("source_table") or identity.get("source_table"))


def _is_schedule_source_or_unspecified(option: Dict[str, Any], plan_resolution: Dict[str, Any]) -> bool:
    source_table = _option_source_table(option) or _resolution_source_table(plan_resolution)
    return not source_table or source_table == SOURCE_SCHEDULE


def _is_historical_adopted_option(option: Dict[str, Any], plan_resolution: Dict[str, Any]) -> bool:
    plan_identity = plan_resolution.get("plan_identity")
    identity = plan_identity if isinstance(plan_identity, dict) else {}
    is_superseded = bool(
        plan_resolution.get("is_superseded_by_newer_version")
        or identity.get("is_superseded_by_newer_version")
    )
    return bool(
        is_superseded
        and _text(option.get("role")) == ROLE_ADOPTED
        and _is_schedule_source_or_unspecified(option, plan_resolution)
    )


def _display_label(option: Dict[str, Any], plan_resolution: Dict[str, Any]) -> str:
    if _is_historical_adopted_option(option, plan_resolution):
        return _HISTORICAL_ADOPTED_LABEL
    return _text(option.get("label"))


def _display_candidate_label(option: Dict[str, Any], label: str) -> str:
    candidate = _text(option.get("candidate_label"))
    raw_label = _text(option.get("label"))
    return "" if not candidate or candidate in (label, raw_label) else candidate


def _with_display_text(option: Dict[str, Any], plan_resolution: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(option)
    label = _display_label(item, plan_resolution)
    candidate = _display_candidate_label(item, label)
    item["display_label"] = label
    item["display_candidate_label"] = candidate
    item["display_text"] = f"{label} · {candidate}" if candidate else label
    return item


def public_plan_role_options(plan_resolution_or_context: Any = None, options: Optional[Any] = None) -> List[Dict[str, Any]]:
    plan_resolution = _plan_resolution_dict(plan_resolution_or_context)
    source_options = options if options is not None else plan_resolution.get("available_roles")
    return [_with_display_text(item, plan_resolution) for item in serialize_plan_role_options(source_options)]


__all__ = ["public_plan_role_options"]
