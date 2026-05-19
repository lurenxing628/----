from __future__ import annotations

from typing import Any, Dict, List, Tuple

from core.services.scheduler.config import ConfigService
from web.viewmodels.scheduler_config_panel import build_scheduler_config_panel_state
from web.viewmodels.ui_presenters import UiToggleRow, checked_attr

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
    "graph_analysis_mode",
    "graph_block_on_cycle",
    "graph_critical_weight",
    "graph_impact_weight",
    "graph_candidate_weight_count",
    "graph_selection_policy",
    "graph_overdue_tolerance_count",
    "graph_tardiness_tolerance_ratio",
    "graph_debug_export",
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
    return f"平时不直接显示的设置“{label}”需要重新确认；系统暂时按当前可用配置继续运行。"


def public_hidden_repair_notice(fields: List[str], *, blocked: bool) -> str:
    labels = ConfigService.public_config_field_labels(fields) or ["未命名设置项"]
    label_text = "、".join(labels)
    if blocked:
        return f"检测到平时不直接显示的设置“{label_text}”需要重新确认，但系统不知道它原来来自哪里，不能自动帮你改。请检查后手动保存一次。"
    return f"平时不直接显示的设置“{label_text}”已按当前页面内容一起保存。"


def public_meta_parse_warning() -> str:
    return "系统看不懂这份方案的来源记录，暂时按旧记录继续显示；建议检查后重新保存。"


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
            fallback_note = f"当前页面先按“{display_value}”展示，请检查后保存一次。"
            warnings[field] = f"{label} 这项设置现在不能直接用，{fallback_note}"
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
            "description": "系统帮你补上的设备和人员会保存回这道工序，下次排产还能继续用。",
        }
    if normalized == "no":
        return {
            "enabled": False,
            "value": "no",
            "label": "已关闭",
            "description": "系统帮你补上的设备和人员只用于本次结果，不改工序原来的资料。",
        }
    if not normalized:
        return {
            "enabled": None,
            "value": "missing",
            "label": "旧历史未记录",
            "description": "旧版本排产没有记录是否保存系统补上的设备和人员。",
        }
    return {
        "enabled": None,
        "value": "invalid",
        "label": "记录异常",
        "description": "这条记录里的保存补齐资源取值不正确，请到系统管理里的排产历史查看这次排产的详细提醒。",
    }


def _config_field_label(config_field_metadata: Dict[str, Any], field: str) -> str:
    metadata = config_field_metadata[field]
    return str(getattr(metadata, "label", "") or field)


def _config_field_hint(config_field_metadata: Dict[str, Any], field: str, *, default: str = "") -> str:
    metadata = config_field_metadata[field]
    return str(getattr(metadata, "hint", "") or default)


def build_scheduler_config_toggles(cfg: Any, *, config_field_metadata: Dict[str, Any]) -> Dict[str, UiToggleRow]:
    ortools_desc = (
        _config_field_hint(
            config_field_metadata,
            "ortools_enabled",
            default="只在精细计算时生效；系统会多花几秒尝试找更好的排法，优化目标就是当前页面选择的目标。",
        )
        + " 不保证每次一定更好，但会在限定秒数内停下。"
    )
    return {
        "freeze_window_enabled": UiToggleRow(
            id="freezeWindowEnabled",
            name="freeze_window_enabled",
            title=_config_field_label(config_field_metadata, "freeze_window_enabled"),
            desc=_config_field_hint(config_field_metadata, "freeze_window_enabled"),
            checked_attr=checked_attr(str(getattr(cfg, "freeze_window_enabled", "")).strip() == "yes"),
        ),
        "prefer_primary_skill": UiToggleRow(
            id="preferPrimarySkill",
            name="prefer_primary_skill",
            title=_config_field_label(config_field_metadata, "prefer_primary_skill"),
            desc=_config_field_hint(
                config_field_metadata,
                "prefer_primary_skill",
                default="编辑工序选人时，下拉框把主操和高技能人员排在最前面。",
            ),
            checked_attr=checked_attr(str(getattr(cfg, "prefer_primary_skill", "")).strip() == "yes"),
        ),
        "enforce_ready_default": UiToggleRow(
            id="enforceReadyDefault",
            name="enforce_ready_default",
            title=_config_field_label(config_field_metadata, "enforce_ready_default"),
            desc=_config_field_hint(config_field_metadata, "enforce_ready_default", default="默认关闭。启用后，只要所选批次里有未齐套或部分齐套，本次排产会报错并停止；系统不会自动跳过这些批次继续排其它批次，齐套日期只对齐套批次作为最早开工日。"),
            checked_attr=checked_attr(str(getattr(cfg, "enforce_ready_default", "")).strip() == "yes"),
        ),
        "auto_assign_enabled": UiToggleRow(
            id="autoAssignEnabled",
            name="auto_assign_enabled",
            title=_config_field_label(config_field_metadata, "auto_assign_enabled"),
            desc=_config_field_hint(
                config_field_metadata,
                "auto_assign_enabled",
                default="排产时自动为空白工序补设备和人员。",
            ),
            checked_attr=checked_attr(str(getattr(cfg, "auto_assign_enabled", "")).strip() == "yes"),
        ),
        "ortools_enabled": UiToggleRow(
            id="orToolsEnabled",
            name="ortools_enabled",
            title=_config_field_label(config_field_metadata, "ortools_enabled"),
            desc=ortools_desc,
            checked_attr=checked_attr(str(getattr(cfg, "ortools_enabled", "")).strip() == "yes"),
        ),
        "graph_block_on_cycle": UiToggleRow(
            id="graphBlockOnCycle",
            name="graph_block_on_cycle",
            title=_config_field_label(config_field_metadata, "graph_block_on_cycle"),
            desc=_config_field_hint(
                config_field_metadata,
                "graph_block_on_cycle",
            ),
            checked_attr=checked_attr(str(getattr(cfg, "graph_block_on_cycle", "")).strip() == "yes"),
        ),
        "graph_debug_export": UiToggleRow(
            id="graphDebugExport",
            name="graph_debug_export",
            title=_config_field_label(config_field_metadata, "graph_debug_export"),
            desc=_config_field_hint(config_field_metadata, "graph_debug_export"),
            checked_attr=checked_attr(str(getattr(cfg, "graph_debug_export", "")).strip() == "yes"),
        ),
    }


def build_scheduler_config_panel_state_from_service(cfg_svc: Any) -> Any:
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


def build_scheduler_batches_config_panel_state(cfg_svc: Any) -> Any:
    return build_scheduler_config_panel_state_from_service(cfg_svc)
