from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Sequence, Tuple

from .scheduler_batches_notices import build_config_notice_items
from .ui_presenters import UiDetailsNotice, UiSummaryItem

_AutoAssignPersistDisplayBuilder = Callable[[Any], Dict[str, Any]]


@dataclass(frozen=True)
class SchedulerConfigPanelState:
    cfg: Any
    strategies: Sequence[Any]
    config_field_metadata: Dict[str, Any]
    config_field_warnings: Dict[str, str]
    config_degraded_fields: Sequence[str]
    config_degraded_field_labels: Tuple[str, ...]
    config_hidden_warnings: Sequence[str]
    presets: Sequence[Any]
    active_preset: Any
    builtin_presets: Sequence[str]
    current_config_state: Dict[str, Any]
    current_auto_assign_persist_state: Dict[str, Any]
    notice_items: Sequence[UiDetailsNotice]
    current_config_summary_items: Sequence[UiSummaryItem]
    current_config_notice_items: Sequence[UiDetailsNotice]
    current_auto_assign_persist_item: UiSummaryItem
    current_config_display_items: Sequence[UiSummaryItem]


def _display_text(value: Any, *, fallback: str = "-") -> str:
    text = str(value or "").strip()
    return text if text else fallback


def _selected_preset_label(current_config_state: Dict[str, Any], active_preset: Any) -> str:
    baseline = str(current_config_state.get("baseline_label") or "").strip()
    if baseline:
        return baseline
    preset = str(active_preset or "").strip()
    if not preset or preset == "custom":
        return "自定义"
    return preset


def _current_config_summary_items(
    *,
    current_config_state: Dict[str, Any],
    active_preset: Any,
) -> Tuple[UiSummaryItem, ...]:
    items = [
        UiSummaryItem(
            "已选方案",
            _selected_preset_label(current_config_state, active_preset),
            "这是当前设置对照的方案。",
        )
    ]
    if current_config_state:
        items.append(
            UiSummaryItem(
                "当前运行配置",
                _display_text(current_config_state.get("status_label")),
                _display_text(current_config_state.get("label")),
            )
        )
    return tuple(items)


def _repair_notice_items(current_config_state: Dict[str, Any]) -> Tuple[UiDetailsNotice, ...]:
    notices = []
    default_body = _display_text(current_config_state.get("label"), fallback="")
    for raw_notice in current_config_state.get("repair_notices") or ():
        if isinstance(raw_notice, dict):
            message = raw_notice.get("message")
            field_labels = raw_notice.get("field_labels")
        else:
            message = getattr(raw_notice, "message", "")
            field_labels = getattr(raw_notice, "field_labels", ())
        body = _display_text(message, fallback=default_body)
        if not body:
            continue
        detail_items = tuple(str(item) for item in (field_labels or ()) if str(item).strip())
        notices.append(
            UiDetailsNotice(
                "配置修正提示",
                body,
                tone="warning",
                detail_label="查看涉及字段",
                detail_items=detail_items,
                role="status",
                aria_live="polite",
            )
        )
    return tuple(notices)


def _current_auto_assign_persist_item(state: Dict[str, Any]) -> UiSummaryItem:
    return UiSummaryItem(
        "保存补齐资源",
        _display_text(state.get("label")),
        _display_text(state.get("description"), fallback=""),
        details_summary="查看说明",
    )


def _current_auto_assign_enabled_item(cfg: Any) -> UiSummaryItem:
    normalized = str(getattr(cfg, "auto_assign_enabled", "") or "").strip().lower()
    if normalized == "yes":
        return UiSummaryItem(
            "自动补设备人员",
            "已启用",
            "自制工序没填设备或人员时，系统会尝试自动补上。",
            details_summary="查看说明",
        )
    if normalized == "no":
        return UiSummaryItem(
            "自动补设备人员",
            "已关闭",
            "自制工序没填设备或人员时，系统不会自动补；请先补齐后再排产。",
            details_summary="查看说明",
        )
    if not normalized:
        return UiSummaryItem(
            "自动补设备人员",
            "未记录",
            "当前配置没有记录是否自动补设备和人员，请到高级设置检查后保存一次。",
            tone="warning",
            details_summary="查看说明",
        )
    return UiSummaryItem(
        "自动补设备人员",
        "记录异常",
        "当前配置里的自动补设备人员取值不正确，请到高级设置检查后保存一次。",
        tone="warning",
        details_summary="查看说明",
    )


def build_scheduler_config_panel_state(
    *,
    cfg: Any,
    strategies: Sequence[Any],
    config_field_metadata: Dict[str, Any],
    config_field_warnings: Dict[str, str],
    config_degraded_fields: Sequence[str],
    config_hidden_warnings: Sequence[str],
    preset_display_state: Dict[str, Any],
    builtin_presets: Sequence[str],
    auto_assign_persist_display_builder: _AutoAssignPersistDisplayBuilder,
) -> SchedulerConfigPanelState:
    config_degraded_field_labels = tuple(
        str(getattr(config_field_metadata.get(field), "label", "") or field)
        for field in config_degraded_fields
    )
    notice_items = build_config_notice_items(
        config_degraded_field_labels=config_degraded_field_labels,
        config_hidden_warnings=config_hidden_warnings,
    )
    current_config_state = dict(preset_display_state.get("current_config_state") or {})
    current_auto_assign_persist_state = auto_assign_persist_display_builder(
        getattr(cfg, "auto_assign_persist", None)
    )
    active_preset = preset_display_state.get("active_preset")
    current_config_notice_items = (
        *_repair_notice_items(current_config_state),
        *notice_items,
    )
    current_config_summary_items = _current_config_summary_items(
        current_config_state=current_config_state,
        active_preset=active_preset,
    )
    current_auto_assign_enabled_item = _current_auto_assign_enabled_item(cfg)
    current_auto_assign_persist_item = _current_auto_assign_persist_item(current_auto_assign_persist_state)
    return SchedulerConfigPanelState(
        cfg=cfg,
        strategies=strategies,
        config_field_metadata=config_field_metadata,
        config_field_warnings=config_field_warnings,
        config_degraded_fields=config_degraded_fields,
        config_degraded_field_labels=config_degraded_field_labels,
        config_hidden_warnings=config_hidden_warnings,
        presets=list(preset_display_state.get("presets") or []),
        active_preset=active_preset,
        builtin_presets=builtin_presets,
        current_config_state=current_config_state,
        current_auto_assign_persist_state=current_auto_assign_persist_state,
        notice_items=notice_items,
        current_config_summary_items=current_config_summary_items,
        current_config_notice_items=current_config_notice_items,
        current_auto_assign_persist_item=current_auto_assign_persist_item,
        current_config_display_items=(
            *current_config_summary_items,
            current_auto_assign_enabled_item,
            current_auto_assign_persist_item,
        ),
    )


__all__ = [
    "SchedulerConfigPanelState",
    "build_scheduler_config_panel_state",
]
