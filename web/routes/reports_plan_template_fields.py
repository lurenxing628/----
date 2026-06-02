from __future__ import annotations

from typing import Any, Dict

ROLE_ADOPTED = "adopted"
DEFAULT_PLAN_LABEL = "正式采用方案"
DEFAULT_PREVIEW_LABEL = "模拟预览（未命名）"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _plan_label(plan_resolution: Dict[str, Any]) -> str:
    return (
        _text(plan_resolution.get("scenario_display_name"))
        or _text(plan_resolution.get("scenario_name"))
        or _text(plan_resolution.get("user_label"))
        or _text(plan_resolution.get("selected_label"))
        or DEFAULT_PLAN_LABEL
    )


def _preview_label(plan_resolution: Dict[str, Any]) -> str:
    return (
        _text(plan_resolution.get("scenario_display_name"))
        or _text(plan_resolution.get("scenario_name"))
        or DEFAULT_PREVIEW_LABEL
    )


def report_plan_status(plan_resolution: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(plan_resolution or {})
    label = _plan_label(data)
    fallback_message = _text(data.get("message")) if data.get("is_fallback") else ""
    source_text = f"当前方案：{label}"
    if data.get("is_superseded_by_newer_version"):
        source_text = f"当前查看：{label}。这个历史版本已被更新的正式排产替代，只能查看，不能写现场事实。"
    if fallback_message:
        source_text = f"{source_text}。{fallback_message}"
    return {
        "label": label,
        "source_text": source_text,
        "is_preview": bool(data.get("is_scenario_preview")),
        "is_superseded": bool(data.get("is_superseded_by_newer_version")),
        "preview_label": _preview_label(data),
    }


def report_plan_template_fields(plan_resolution: Dict[str, Any], scenario_id: Any) -> Dict[str, Any]:
    data = dict(plan_resolution or {})
    return {
        "plan_options": data.get("available_roles") or [],
        "selected_plan_role": _text(data.get("selected_role")) or ROLE_ADOPTED,
        "requested_plan_role": _text(data.get("requested_role")) or ROLE_ADOPTED,
        "report_plan_status": report_plan_status(data),
        "scenario_id": scenario_id,
    }


__all__ = ["report_plan_status", "report_plan_template_fields"]
