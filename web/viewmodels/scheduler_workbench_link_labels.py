from __future__ import annotations

from typing import Any

from core.models.schedule_plan_role import ROLE_ADOPTED
from core.models.schedule_plan_role import plan_role_label as _core_plan_role_label

_GUARDRAIL_REASON_LABELS = {
    "plan_not_writable": "当前方案不可写",
    "task_state_blocked": "当前任务状态不可写",
    "action_unavailable": "后端暂未开放这个动作",
    "data_gap": "数据不足，暂时不能判断",
}

_RESOURCE_TYPE_LABELS = {
    "operator": "人员视角",
    "machine": "设备视角",
    "team": "班组视角",
}

_PERIOD_PRESET_LABELS = {
    "week": "按周",
    "month": "按月",
    "custom": "自定义",
}

_VIEW_LABELS = {
    "machine": "设备甘特",
    "operator": "人员甘特",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def plan_role_label(value: Any, *, is_preview: bool = False, scenario_display_label: str = "") -> str:
    if is_preview:
        return _text(scenario_display_label) or "模拟预览（未命名）"
    text = _text(value) or ROLE_ADOPTED
    return _core_plan_role_label(text)


def guardrail_reason_label(value: Any) -> str:
    text = _text(value)
    return _GUARDRAIL_REASON_LABELS.get(text, "未知限制原因")


def resource_type_label(value: Any) -> str:
    text = _text(value)
    return _RESOURCE_TYPE_LABELS.get(text, "未知资源视角")


def period_preset_label(value: Any) -> str:
    text = _text(value)
    return _PERIOD_PRESET_LABELS.get(text, "未知日期范围")


def gantt_view_label(value: Any) -> str:
    text = _text(value)
    return _VIEW_LABELS.get(text, "未知甘特视图")


__all__ = [
    "gantt_view_label",
    "guardrail_reason_label",
    "period_preset_label",
    "plan_role_label",
    "resource_type_label",
]
