from __future__ import annotations

from typing import Any, Dict, List, Tuple

from core.services.scheduler.config.config_field_spec import page_metadata_for

SCHEDULER_VISIBLE_CONFIG_FIELDS: Tuple[str, ...] = (
    "sort_strategy",
    "priority_weight",
    "due_weight",
    "holiday_default_efficiency",
    "enforce_ready_default",
    "prefer_primary_skill",
    "algo_mode",
    "objective",
    "dispatch_mode",
    "dispatch_rule",
    "auto_assign_enabled",
    "ortools_enabled",
    "ortools_time_limit_seconds",
    "time_budget_seconds",
    "freeze_window_enabled",
    "freeze_window_days",
)


def get_scheduler_visible_config_field_metadata() -> Dict[str, Any]:
    return page_metadata_for(list(SCHEDULER_VISIBLE_CONFIG_FIELDS))


def _format_config_display_value(field: str, value: Any, *, config_field_metadata: Dict[str, Any]) -> str:
    metadata = config_field_metadata.get(field)
    for choice in getattr(metadata, "choices", ()) or ():
        choice_value = str(choice.get("value") or "").strip()
        if choice_value and choice_value == str(value):
            return str(choice.get("label") or value)
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def build_config_degraded_display_state(
    cfg: Any,
    *,
    config_field_metadata: Dict[str, Any],
) -> Tuple[Dict[str, str], List[str], List[str]]:
    warnings: Dict[str, str] = {}
    degraded_fields: List[str] = []
    hidden_warnings: List[str] = []
    for raw_event in getattr(cfg, "degradation_events", ()) or ():
        if not isinstance(raw_event, dict):
            continue
        field = str((raw_event or {}).get("field") or "").strip()
        if not field:
            continue
        event_message = str((raw_event or {}).get("message") or "").strip()
        if field in config_field_metadata:
            if field in warnings:
                continue
            metadata = config_field_metadata.get(field)
            label = str(getattr(metadata, "label", "") or field)
            display_value = _format_config_display_value(
                field,
                getattr(cfg, field, ""),
                config_field_metadata=config_field_metadata,
            )
            fallback_note = f"当前页面暂按“{display_value}”显示兼容值，请保存修复。"
            warnings[field] = f"{event_message} {fallback_note}".strip() if event_message else f"{label} 当前配置无效，{fallback_note}"
            degraded_fields.append(field)
            continue
        hidden_warnings.append(
            event_message
            or f"内部配置项“{field}”当前无效，系统暂按兼容值“{getattr(cfg, field, '')}”运行；请保存配置完成修复。"
        )
    return warnings, degraded_fields, hidden_warnings


def build_auto_assign_persist_display_state(value: Any) -> Dict[str, Any]:
    normalized = str(value or "").strip().lower()
    if normalized == "yes":
        return {
            "enabled": True,
            "value": "yes",
            "label": "已启用",
            "description": "自动分配得到的设备/人员会回写到工序。",
        }
    if normalized == "no":
        return {
            "enabled": False,
            "value": "no",
            "label": "已关闭",
            "description": "自动分配只参与本次排产结果，不回写到工序。",
        }
    return {
        "enabled": None,
        "value": "unknown",
        "label": "未记录",
        "description": "该次排产快照未记录自动回写资源状态。",
    }
