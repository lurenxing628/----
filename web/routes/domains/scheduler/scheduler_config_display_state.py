from __future__ import annotations

from typing import Any, Dict, List, Tuple

from core.services.scheduler.config import ConfigService
from web.viewmodels.scheduler_batches_page import build_scheduler_config_panel_state

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
    return ConfigService.get_page_metadata(list(SCHEDULER_VISIBLE_CONFIG_FIELDS))


def _format_config_display_value(field: str, value: Any, *, config_field_metadata: Dict[str, Any]) -> str:
    metadata = config_field_metadata.get(field)
    for choice in getattr(metadata, "choices", ()) or ():
        choice_value = str(choice.get("value") or "").strip()
        if choice_value and choice_value == str(value):
            return str(choice.get("label") or value)
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def public_hidden_config_warning(field: str) -> str:
    label = ConfigService.public_config_field_label(field)
    return f"后台设置“{label}”当前需要保存修复；系统已按兼容配置继续运行。"


def public_hidden_repair_notice(fields: List[str], *, blocked: bool) -> str:
    labels = ConfigService.public_config_field_labels(fields) or ["隐藏配置"]
    label_text = "、".join(labels)
    if blocked:
        return f"检测到后台设置“{label_text}”需要保存修复，但因来源缺失未自动修复。"
    return f"后台设置“{label_text}”已按当前表单值回写。"


def public_meta_parse_warning() -> str:
    return "方案来源记录暂时无法解析，已按历史来源信息继续显示。"


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
            warnings[field] = f"{label} 当前配置无效，{fallback_note}"
            degraded_fields.append(field)
            continue
        hidden_warnings.append(public_hidden_config_warning(field))
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


def build_scheduler_batches_config_panel_state(cfg_svc: Any) -> Any:
    cfg = cfg_svc.get_snapshot()
    strategies = cfg_svc.get_available_strategies()
    config_field_metadata = get_scheduler_visible_config_field_metadata()
    config_field_warnings, config_degraded_fields, config_hidden_warnings = build_config_degraded_display_state(
        cfg,
        config_field_metadata=config_field_metadata,
    )
    preset_display_state = cfg_svc.get_preset_display_state(readonly=True, current_snapshot=cfg)
    builtin_presets = [
        ConfigService.BUILTIN_PRESET_DEFAULT,
        ConfigService.BUILTIN_PRESET_DUE_FIRST,
        ConfigService.BUILTIN_PRESET_MIN_CHANGEOVER,
        ConfigService.BUILTIN_PRESET_IMPROVE_SLOW,
    ]
    return build_scheduler_config_panel_state(
        cfg=cfg,
        strategies=strategies,
        config_field_metadata=config_field_metadata,
        config_field_warnings=config_field_warnings,
        config_degraded_fields=config_degraded_fields,
        config_hidden_warnings=config_hidden_warnings,
        preset_display_state=preset_display_state,
        builtin_presets=builtin_presets,
        auto_assign_persist_display_builder=build_auto_assign_persist_display_state,
    )
