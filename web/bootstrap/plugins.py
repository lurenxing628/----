from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from core.infrastructure.database import get_connection
from core.infrastructure.logging import OperationLogger, safe_log
from core.plugins import PluginManager, reset_plugin_state
from core.plugins.registry import PluginRegistry
from core.services.common.degradation import DegradationCollector
from core.services.scheduler.degradation_messages import public_degradation_events
from data.repositories import SystemConfigRepository


def _status_degradation_collector(status: Optional[Dict[str, Any]]) -> DegradationCollector:
    collector = DegradationCollector()
    base = dict(status or {}) if isinstance(status, dict) else {}
    for event in list(base.get("degradation_events") or []):
        if not isinstance(event, dict):
            continue
        code = str(event.get("code") or "").strip()
        message = str(event.get("message") or "").strip()
        if not code or not message:
            continue
        try:
            count = max(1, int(event.get("count") or 1))
        except Exception:
            count = 1
        collector.add(
            code=code,
            scope="plugins.bootstrap",
            field=None,
            message=message,
            count=count,
            sample=None,
        )
    return collector


def _merge_plugin_degradation(status: Optional[Dict[str, Any]], collector: DegradationCollector) -> Dict[str, Any]:
    base = dict(status or {}) if isinstance(status, dict) else {}
    merged = _status_degradation_collector(base)
    merged.extend(collector.to_list())
    base["degraded"] = bool(merged)
    base["degradation_events"] = public_degradation_events(merged.to_list())
    base["degradation_counters"] = merged.to_counters()
    return base


def _ensure_plugin_status_shape(status: Optional[Dict[str, Any]], *, base_dir: str) -> Dict[str, Any]:
    base = dict(status or {}) if isinstance(status, dict) else {}
    registry = base.get("registry")
    if not isinstance(registry, dict):
        registry = PluginRegistry().to_dict()
    base["registry"] = registry
    base.setdefault("loaded_at", None)
    base.setdefault("vendor_paths", [])
    base.setdefault("plugins_dir", os.path.join(os.path.abspath(str(base_dir or ".")), "plugins"))
    base.setdefault("statuses", [])
    base.setdefault("conflicted_capabilities", list(registry.get("conflicted_capabilities") or []))
    base.setdefault("conflict_policy", registry.get("conflict_policy") or PluginRegistry().conflict_policy)
    base.setdefault("telemetry_persisted", None)
    return base


def _record_plugin_status_failures(status: Optional[Dict[str, Any]], collector: DegradationCollector) -> None:
    base = dict(status or {}) if isinstance(status, dict) else {}
    for item in list(base.get("statuses") or []):
        row = dict(item or {}) if isinstance(item, dict) else {}
        if not str(row.get("error") or "").strip():
            continue
        plugin_id = str(row.get("plugin_id") or "").strip() or "-"
        collector.add(
            code="plugin_bootstrap_load_failed",
            scope="plugins.bootstrap",
            field=f"plugin.{plugin_id}",
            message="扩展功能加载失败，请查看系统日志。",
        )


def _resolve_enabled_source(
    plugin_id: str,
    row_source: str,
    *,
    enabled_source_map: Dict[str, str],
    default_source: str,
) -> str:
    explicit_source = str(enabled_source_map.get(plugin_id) or "").strip()
    if explicit_source:
        return explicit_source
    row_source_s = str(row_source or "").strip()
    if row_source_s and not (row_source_s == "default" and str(default_source or "default") != "default"):
        return row_source_s
    return str(default_source or row_source_s or "default")


def _public_plugin_status_row(row: Dict[str, Any], source: str) -> Dict[str, Any]:
    public_row = dict(row or {})
    public_row["enabled_source"] = source
    if str(public_row.get("error") or "").strip():
        public_row["error"] = "扩展功能加载失败，请查看系统日志。"
    return public_row


def _config_source_summary(sources: List[str], default_source: str) -> str:
    source_set = {str(source or "").strip() for source in sources if str(source or "").strip()}
    has_config = "config" in source_set
    non_config_sources = {source for source in source_set if source != "config"}
    if has_config and non_config_sources:
        return "mixed"
    if has_config:
        return "config"
    if len(non_config_sources) == 1:
        return next(iter(non_config_sources))
    if len(non_config_sources) > 1:
        return "mixed"
    return str(default_source or "default")


def _apply_enabled_sources(
    status: Optional[Dict[str, Any]],
    *,
    enabled_source_map: Dict[str, str],
    default_source: str,
) -> Dict[str, Any]:
    base = dict(status or {}) if isinstance(status, dict) else {}
    raw_statuses = list(base.get("statuses") or [])
    statuses = []
    sources: List[str] = []

    for item in raw_statuses:
        row = dict(item or {}) if isinstance(item, dict) else {}
        plugin_id = str(row.get("plugin_id") or "").strip()
        source = _resolve_enabled_source(
            plugin_id,
            str(row.get("enabled_source") or "").strip(),
            enabled_source_map=enabled_source_map,
            default_source=default_source,
        )
        sources.append(source)
        statuses.append(_public_plugin_status_row(row, source))

    base["statuses"] = statuses
    base["config_source"] = _config_source_summary(sources, default_source)
    return base


def _build_plugin_config_reader(
    conn,
    *,
    logger: Optional[logging.Logger] = None,
    collector: DegradationCollector,
):
    if conn is None:
        return None

    try:
        repo = SystemConfigRepository(conn, logger=logger)
    except Exception as exc:
        collector.add(
            code="plugin_bootstrap_config_reader_failed",
            scope="plugins.bootstrap",
            field="plugin.enabled",
            message="扩展功能设置读取器初始化失败，当前按默认开关运行。",
            sample=exc.__class__.__name__,
        )
        safe_log(logger, "warning", "扩展功能设置读取器初始化失败，当前按默认开关运行：%s", exc)
        return None

    enabled_source_map: Dict[str, str] = {}

    def _reader(plugin_id: str):
        plugin_key = str(plugin_id or "").strip()
        key = f"plugin.{plugin_key}.enabled"
        try:
            value = repo.get_value(key, default=None)
        except Exception as exc:
            enabled_source_map[plugin_key] = "default_due_to_config_read_failed"
            collector.add(
                code="plugin_bootstrap_config_read_failed",
                scope="plugins.bootstrap",
                field=key,
                message=f"读取扩展功能设置失败，扩展功能 {plugin_key or '-'} 当前按默认开关运行。",
                sample=exc.__class__.__name__,
            )
            safe_log(logger, "warning", "读取扩展功能设置失败，当前按默认开关运行：key=%s err=%s", key, exc)
            return None

        enabled_source_map[plugin_key] = "config" if value is not None else "default"
        return value

    _reader.enabled_source_map = enabled_source_map  # type: ignore[attr-defined]
    _reader.default_enabled_source = "default"  # type: ignore[attr-defined]
    return _reader


def bootstrap_plugins(base_dir: str, database_path: str, *, logger: Optional[logging.Logger] = None):
    """
    加载可选插件并记录运行留痕。

    失败不阻断启动，返回可观测状态用于系统页展示。
    """
    collector = DegradationCollector()
    plugin_status: Optional[Dict[str, Any]] = None
    conn0 = None
    default_enabled_source = "default"

    try:
        conn0 = get_connection(database_path)
    except Exception as exc:
        default_enabled_source = "default_due_to_db_unavailable"
        collector.add(
            code="plugin_bootstrap_db_unavailable",
            scope="plugins.bootstrap",
            field="database_path",
            message="扩展功能启动时无法连接系统配置库，当前按默认开关运行。",
            sample=exc.__class__.__name__,
        )
        safe_log(logger, "warning", "打开数据库连接失败，扩展功能加载将按默认开关运行：%s", exc)

    config_reader = _build_plugin_config_reader(conn0, logger=logger, collector=collector)
    if config_reader is None and default_enabled_source == "default":
        if int(collector.to_counters().get("plugin_bootstrap_config_reader_failed") or 0) > 0:
            default_enabled_source = "default_due_to_config_reader_failed"

    enabled_source_map = getattr(config_reader, "enabled_source_map", {}) if callable(config_reader) else {}
    if not isinstance(enabled_source_map, dict):
        enabled_source_map = {}

    try:
        plugin_status = PluginManager.load_from_base_dir(base_dir, config_reader=config_reader, logger=logger)
    except Exception as exc:
        collector.add(
            code="plugin_bootstrap_load_failed",
            scope="plugins.bootstrap",
            field="plugins",
            message="扩展功能加载失败，请查看系统日志。",
            sample=exc.__class__.__name__,
        )
        safe_log(logger, "error", "扩展功能加载失败（已忽略，启动继续）：%s", exc)
        plugin_status = reset_plugin_state(base_dir)

    plugin_status = _apply_enabled_sources(
        plugin_status,
        enabled_source_map=enabled_source_map,
        default_source=default_enabled_source,
    )
    plugin_status = _ensure_plugin_status_shape(plugin_status, base_dir=base_dir)
    _record_plugin_status_failures(plugin_status, collector)

    if conn0 is not None:
        try:
            logged = OperationLogger(conn0, logger=logger).info(
                "plugins",
                "load",
                target_type="runtime",
                target_id="plugins",
                detail=plugin_status,
            )
            plugin_status["telemetry_persisted"] = bool(logged)
            if logged is False:
                collector.add(
                    code="plugin_bootstrap_telemetry_failed",
                    scope="plugins.bootstrap",
                    field="telemetry",
                    message="扩展功能启动记录写入操作日志失败。",
                )
        except Exception as exc:
            plugin_status["telemetry_persisted"] = False
            collector.add(
                code="plugin_bootstrap_telemetry_failed",
                scope="plugins.bootstrap",
                field="telemetry",
                message="扩展功能启动记录写入操作日志异常。",
                sample=exc.__class__.__name__,
            )
        finally:
            try:
                conn0.close()
            except Exception:
                pass

    plugin_status = _merge_plugin_degradation(plugin_status, collector)
    plugin_status = _ensure_plugin_status_shape(plugin_status, base_dir=base_dir)
    return plugin_status
