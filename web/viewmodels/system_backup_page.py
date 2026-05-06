from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Optional, Sequence

from .ui_presenters import UiDetailsNotice, UiEmptyState, UiSummaryItem, UiToggleRow, checked_attr

PLUGIN_CONFIG_SOURCE_LABELS = {
    "config": "全部来自系统配置",
    "mixed": "部分来自系统配置，部分按默认开关运行",
    "default_due_to_db_unavailable": "扩展功能设置暂时读取不到，系统已先按默认设置运行",
    "default_due_to_config_reader_failed": "扩展功能设置暂时读取不到，系统已先按默认设置运行",
    "default_due_to_config_read_failed": "扩展功能设置暂时读取不到，系统已先按默认设置运行",
    "default": "当前按默认开关运行",
}

PLUGIN_TELEMETRY_STATES = {
    True: ("已记录", "success"),
    False: ("记录失败", "danger"),
    None: ("-", "neutral"),
}

PLUGIN_ENABLED_SOURCE_LABELS = {
    "config": "系统配置",
    "default_due_to_db_unavailable": "默认开关（扩展功能设置暂时读取不到）",
    "default_due_to_config_reader_failed": "默认开关（扩展功能设置暂时读取不到）",
    "default_due_to_config_read_failed": "默认开关（扩展功能设置暂时读取不到）",
    "default": "默认开关",
}

PLUGIN_LOADED_LABELS = {
    "yes": "已加载",
    "no": "未加载",
}


@dataclass(frozen=True)
class PluginStatusRow:
    plugin_id: str
    name: str
    version: str
    enabled_checked_attr: str
    enabled_toggle: UiToggleRow
    loaded_label: str
    enabled_source_label: str
    error: str
    capability_count: int
    has_capabilities: bool


@dataclass(frozen=True)
class PluginDegradationEventRow:
    message: str


@dataclass(frozen=True)
class PluginConflictRow:
    message: str = "有两个扩展功能想处理同一类事情，系统已保留一个，另一个没有启用。"


class PluginStatusDisplayContractError(ValueError):
    """插件状态展示数据不符合 UI 合同。"""

    def __init__(self, *, field: str, value: Any, source: str, message: str) -> None:
        self.field = field
        self.value = value
        self.source = source
        self.message = message
        super().__init__(f"{message}：{source}.{field}={value!r}")

    def detail_text(self) -> str:
        return f"{self.message}；字段：{self.source}.{self.field}；原始值：{self.value!r}"


@dataclass(frozen=True)
class SystemBackupPageState:
    backup_empty_state: UiEmptyState
    plugin_empty_state: UiEmptyState
    plugin_unloaded_empty_state: UiEmptyState
    auto_backup_toggle: UiToggleRow
    auto_backup_cleanup_toggle: UiToggleRow
    plugin_summary_items: Sequence[UiSummaryItem]
    plugin_status_rows: Sequence[PluginStatusRow]
    plugin_status_loaded: bool
    plugin_degraded: bool
    plugin_degradation_count: int
    plugin_degradation_events: Sequence[PluginDegradationEventRow]
    plugin_conflict_count: int
    plugin_conflict_rows: Sequence[PluginConflictRow]
    plugin_status_error_notice: Optional[UiDetailsNotice] = None


def _value(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        return source[key]
    return getattr(source, key)


def _optional_value(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def _sequence_value(source: Any, key: str) -> Sequence[Any]:
    value = _optional_value(source, key)
    if value is None:
        return ()
    return tuple(value)


def _text_or_dash(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "-"


def _yes_no(value: Any, *, field: str) -> str:
    normalized = str(value or "").strip()
    if normalized not in {"yes", "no"}:
        raise PluginStatusDisplayContractError(
            field=field,
            value=value,
            source="plugin_status",
            message="扩展功能状态字段只能是 yes/no",
        )
    return normalized


def _plugin_config_source_label(value: Any) -> str:
    normalized = str(value or "").strip()
    if normalized not in PLUGIN_CONFIG_SOURCE_LABELS:
        raise PluginStatusDisplayContractError(
            field="config_source",
            value=value,
            source="plugin_status",
            message="扩展功能配置来源未登记",
        )
    return PLUGIN_CONFIG_SOURCE_LABELS[normalized]


def _plugin_telemetry_state(value: Any) -> tuple[str, str]:
    if value not in PLUGIN_TELEMETRY_STATES:
        raise PluginStatusDisplayContractError(
            field="telemetry_persisted",
            value=value,
            source="plugin_status",
            message="扩展功能留痕状态未登记",
        )
    return PLUGIN_TELEMETRY_STATES[value]


def _plugin_enabled_source_label(value: Any) -> str:
    normalized = str(value or "").strip()
    if normalized not in PLUGIN_ENABLED_SOURCE_LABELS:
        raise PluginStatusDisplayContractError(
            field="enabled_source",
            value=value,
            source="plugin_status.statuses",
            message="扩展功能开关来源未登记",
        )
    return PLUGIN_ENABLED_SOURCE_LABELS[normalized]


def _safe_dom_id_suffix(value: Any) -> str:
    text = str(value or "")
    readable = "".join(ch if ch.isalnum() else "_" for ch in text).strip("_") or "plugin"
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return f"{readable}_{digest}"


def build_backup_empty_state() -> UiEmptyState:
    return UiEmptyState(
        title="暂无备份文件",
        desc="你可以先点击“手动备份”，生成一份当前数据备份。",
    )


def build_plugin_empty_state() -> UiEmptyState:
    return UiEmptyState(
        title="未发现扩展功能文件",
        desc="系统没有发现随包交付的扩展功能文件。",
    )


def build_plugin_unloaded_empty_state() -> UiEmptyState:
    return UiEmptyState(
        title="扩展功能状态未加载",
        desc="系统启动时还没有拿到扩展功能状态。",
    )


def build_backup_toggle_rows(settings: Any) -> tuple[UiToggleRow, UiToggleRow]:
    return (
        UiToggleRow(
            id="backupAutoBackupEnabled",
            name="auto_backup_enabled",
            title="自动备份",
            desc="系统会在有人访问时按间隔检查是否需要备份；程序正常退出时也会按同一个开关生成退出备份。",
            checked_attr=checked_attr(_value(settings, "auto_backup_enabled") == "yes"),
        ),
        UiToggleRow(
            id="backupAutoCleanupEnabled",
            name="auto_backup_cleanup_enabled",
            title="自动清理备份",
            desc="系统会按保留天数清理旧备份；只会按你设置的间隔检查，不会每次访问都删除。",
            checked_attr=checked_attr(_value(settings, "auto_backup_cleanup_enabled") == "yes"),
        ),
    )


def build_plugin_summary_items(plugin_status: Any) -> Sequence[UiSummaryItem]:
    if plugin_status is None:
        return ()

    registry = _optional_value(plugin_status, "registry") or {}
    capabilities = _sequence_value(registry, "capabilities") if isinstance(registry, dict) else ()
    degradation_events = _sequence_value(plugin_status, "degradation_events")
    conflicted_capabilities = _sequence_value(plugin_status, "conflicted_capabilities")
    telemetry_label, telemetry_tone = _plugin_telemetry_state(_value(plugin_status, "telemetry_persisted"))
    degraded = bool(_optional_value(plugin_status, "degraded"))
    conflict_count = len(conflicted_capabilities)

    return (
        UiSummaryItem("加载时间", _text_or_dash(_optional_value(plugin_status, "loaded_at"))),
        UiSummaryItem("配置来源", _plugin_config_source_label(_value(plugin_status, "config_source")), tone="info"),
        UiSummaryItem("已发现的可用功能", f"{len(capabilities)} 项"),
        UiSummaryItem("留痕状态", telemetry_label, tone=telemetry_tone),
        UiSummaryItem("启动问题", f"{len(degradation_events)} 条", tone="danger" if degraded else "success"),
        UiSummaryItem("冲突能力", f"{conflict_count} 条", tone="warning" if conflict_count > 0 else "success"),
    )


def build_plugin_status_rows(plugin_status: Any) -> Sequence[PluginStatusRow]:
    if plugin_status is None:
        return ()

    rows = []
    for raw_row in _sequence_value(plugin_status, "statuses"):
        row = dict(raw_row or {}) if isinstance(raw_row, dict) else raw_row
        enabled = _yes_no(_value(row, "enabled"), field="plugin.enabled")
        loaded = _yes_no(_value(row, "loaded"), field="plugin.loaded")
        capabilities = _sequence_value(row, "capabilities")
        plugin_id = str(_value(row, "plugin_id"))
        plugin_name = str(_optional_value(row, "name") or "未命名扩展功能")
        toggle_id_suffix = _safe_dom_id_suffix(plugin_id)
        rows.append(
            PluginStatusRow(
                plugin_id=plugin_id,
                name=plugin_name,
                version=_text_or_dash(_optional_value(row, "version")),
                enabled_checked_attr=checked_attr(enabled == "yes"),
                enabled_toggle=UiToggleRow(
                    id=f"pluginEnabledToggle_{toggle_id_suffix}",
                    name="enabled",
                    title="启用",
                    desc=f"控制“{plugin_name}”下次启动时是否启用。",
                    checked_attr=checked_attr(enabled == "yes"),
                ),
                loaded_label=PLUGIN_LOADED_LABELS[loaded],
                enabled_source_label=_plugin_enabled_source_label(_value(row, "enabled_source")),
                error=str(_optional_value(row, "error") or ""),
                capability_count=len(capabilities),
                has_capabilities=bool(capabilities),
            )
        )
    return tuple(rows)


def build_plugin_degradation_events(plugin_status: Any) -> Sequence[PluginDegradationEventRow]:
    if plugin_status is None:
        return ()

    rows = []
    for raw_event in _sequence_value(plugin_status, "degradation_events"):
        event = dict(raw_event or {}) if isinstance(raw_event, dict) else raw_event
        message = str(_optional_value(event, "message") or "").strip() or "扩展功能启动时出现问题。"
        rows.append(PluginDegradationEventRow(message=message))
    return tuple(rows)


def build_plugin_conflict_rows(plugin_status: Any) -> Sequence[PluginConflictRow]:
    if plugin_status is None:
        return ()

    return tuple(PluginConflictRow() for _item in _sequence_value(plugin_status, "conflicted_capabilities"))


def build_system_backup_page_view_model(settings: Any, plugin_status: Any) -> SystemBackupPageState:
    auto_backup_toggle, auto_backup_cleanup_toggle = build_backup_toggle_rows(settings)
    try:
        plugin_summary_items = build_plugin_summary_items(plugin_status)
        plugin_status_rows = build_plugin_status_rows(plugin_status)
        degradation_events = build_plugin_degradation_events(plugin_status)
        conflict_rows = build_plugin_conflict_rows(plugin_status)
        plugin_error_notice = None
        plugin_degraded = bool(_optional_value(plugin_status, "degraded")) if plugin_status is not None else False
    except PluginStatusDisplayContractError as exc:
        plugin_summary_items = ()
        plugin_status_rows = ()
        degradation_events = ()
        conflict_rows = ()
        plugin_degraded = True
        plugin_error_notice = UiDetailsNotice(
            title="扩展功能状态记录异常",
            body="系统拿到的扩展功能状态里有不认识的字段值。备份、恢复和自动备份设置仍可继续使用；扩展功能状态请让维护人员查看。",
            tone="warning",
            detail_label="查看异常字段",
            detail_items=(exc.detail_text(),),
        )
    return SystemBackupPageState(
        backup_empty_state=build_backup_empty_state(),
        plugin_empty_state=build_plugin_empty_state(),
        plugin_unloaded_empty_state=build_plugin_unloaded_empty_state(),
        auto_backup_toggle=auto_backup_toggle,
        auto_backup_cleanup_toggle=auto_backup_cleanup_toggle,
        plugin_summary_items=plugin_summary_items,
        plugin_status_rows=plugin_status_rows,
        plugin_status_loaded=plugin_status is not None,
        plugin_degraded=plugin_degraded,
        plugin_degradation_count=len(degradation_events),
        plugin_degradation_events=degradation_events,
        plugin_conflict_count=len(conflict_rows),
        plugin_conflict_rows=conflict_rows,
        plugin_status_error_notice=plugin_error_notice,
    )


__all__ = [
    "PLUGIN_CONFIG_SOURCE_LABELS",
    "PLUGIN_ENABLED_SOURCE_LABELS",
    "PLUGIN_LOADED_LABELS",
    "PLUGIN_TELEMETRY_STATES",
    "PluginStatusDisplayContractError",
    "PluginConflictRow",
    "PluginDegradationEventRow",
    "PluginStatusRow",
    "SystemBackupPageState",
    "build_backup_empty_state",
    "build_backup_toggle_rows",
    "build_plugin_empty_state",
    "build_plugin_conflict_rows",
    "build_plugin_degradation_events",
    "build_plugin_status_rows",
    "build_plugin_summary_items",
    "build_plugin_unloaded_empty_state",
    "build_system_backup_page_view_model",
]
