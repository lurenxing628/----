from __future__ import annotations

from typing import Any, Dict

from core.models.schedule_plan_role import COMPLETED_RESULT_STATUSES
from core.services.scheduler.schedule_plan_option_display import public_plan_role_options
from web.viewmodels.scheduler_plan_guardrail_messages import result_status_label, summary_unavailable_guardrail_text

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


def _result_status_label(value: Any) -> str:
    return result_status_label(value)


def _not_executable_text(data: Dict[str, Any], label: str) -> str:
    if data.get("is_current_executable_official_version") is not False:
        return ""
    if data.get("is_comparison") or data.get("is_preview") or data.get("is_scenario_preview"):
        return ""
    if data.get("is_superseded_by_newer_version") or data.get("result_summary_parse_failed"):
        return ""
    status = _text(data.get("schedule_result_status")).lower()
    if status in COMPLETED_RESULT_STATUSES:
        return ""
    return f"当前排产结果状态是“{_result_status_label(status)}”，不能当作当前可执行正式方案。当前方案：{label}"


def report_plan_status(plan_resolution: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(plan_resolution or {})
    label = _plan_label(data)
    fallback_message = _text(data.get("message")) if data.get("is_fallback") else ""
    source_text = f"当前方案：{label}"
    not_executable_text = _not_executable_text(data, label)
    if not_executable_text:
        source_text = not_executable_text
    if data.get("result_summary_parse_failed"):
        source_text = (
            f"{summary_unavailable_guardrail_text(data.get('result_summary_parse_reason'), blocked_action='不能写现场事实')}"
            f"当前方案：{label}。"
        )
    if data.get("is_superseded_by_newer_version"):
        source_text = f"{source_text} 这个历史版本已被更新的正式排产替代，只能查看，不能写现场事实。"
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
        "plan_options": public_plan_role_options(data),
        "selected_plan_role": _text(data.get("selected_role")) or ROLE_ADOPTED,
        "requested_plan_role": _text(data.get("requested_role")) or ROLE_ADOPTED,
        "report_plan_status": report_plan_status(data),
        "scenario_id": scenario_id,
    }


__all__ = ["report_plan_status", "report_plan_template_fields"]
