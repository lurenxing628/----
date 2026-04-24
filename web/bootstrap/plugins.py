from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.infrastructure.database import get_connection
from core.infrastructure.logging import OperationLogger, safe_log
from core.plugins import PluginManager, get_plugin_status
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


def _apply_enabled_sources(
    status: Optional[Dict[str, Any]],
    *,
    enabled_source_map: Dict[str, str],
    default_source: str,
) -> Dict[str, Any]:
    base = dict(status or {}) if isinstance(status, dict) else {}
    raw_statuses = list(base.get("statuses") or [])
    statuses = []
    saw_config = False
    saw_default = False
    non_config_sources = set()

    for item in raw_statuses:
        row = dict(item or {}) if isinstance(item, dict) else {}
        plugin_id = str(row.get("plugin_id") or "").strip()
        explicit_source = str(enabled_source_map.get(plugin_id) or "").strip()
        row_source = str(row.get("enabled_source") or "").strip()
        if explicit_source:
            source = explicit_source
        elif row_source and not (row_source == "default" and str(default_source or "default") != "default"):
            source = row_source
        else:
            source = str(default_source or row_source or "default")
        row["enabled_source"] = source
        if str(row.get("error") or "").strip():
            row["error"] = "插件加载失败，请查看系统日志。"

        if source == "config":
            saw_config = True
        else:
            saw_default = True
            non_config_sources.add(source)
        statuses.append(row)

    base["statuses"] = statuses
    if saw_config and saw_default:
        base["config_source"] = "mixed"
    elif saw_config:
        base["config_source"] = "config"
    elif len(non_config_sources) == 1:
        base["config_source"] = next(iter(non_config_sources))
    elif len(non_config_sources) > 1:
        base["config_source"] = "mixed"
    else:
        base["config_source"] = str(default_source or "default")
    return base


def _build_plugin_config_reader(
    conn,
    *,
    logger: logging.Logger | None = None,
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
            message="插件配置读取器初始化失败，当前按默认开关运行。",
            sample=exc.__class__.__name__,
        )
        safe_log(logger, "warning", "插件配置读取器初始化失败，当前按默认开关运行：%s", exc)
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
                message=f"读取插件配置失败，插件 {plugin_key or '-'} 当前按默认开关运行。",
                sample=exc.__class__.__name__,
            )
            safe_log(logger, "warning", "读取插件配置失败，当前按默认开关运行：key=%s err=%s", key, exc)
            return None

        enabled_source_map[plugin_key] = "config" if value is not None else "default"
        return value

    _reader.enabled_source_map = enabled_source_map  # type: ignore[attr-defined]
    _reader.default_enabled_source = "default"  # type: ignore[attr-defined]
    return _reader


def bootstrap_plugins(base_dir: str, database_path: str, *, logger: logging.Logger | None = None):
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
            message="插件启动无法连接系统配置库，当前按默认开关运行。",
            sample=exc.__class__.__name__,
        )
        safe_log(logger, "warning", "打开数据库连接失败，插件加载将按默认开关运行：%s", exc)

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
        safe_log(logger, "error", "插件加载失败（已忽略，启动继续）：%s", exc)
        try:
            plugin_status = get_plugin_status()
        except Exception as status_exc:
            plugin_status = {}
            collector.add(
                code="plugin_bootstrap_status_snapshot_failed",
                scope="plugins.bootstrap",
                field="plugin_status",
                message="插件加载失败后读取插件状态快照异常，当前返回空状态。",
                sample=status_exc.__class__.__name__,
            )
            safe_log(logger, "error", "插件状态快照读取失败，当前返回空状态：%s", status_exc)

    plugin_status = _apply_enabled_sources(
        plugin_status,
        enabled_source_map=enabled_source_map,
        default_source=default_enabled_source,
    )

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
                    message="插件启动留痕写入 OperationLogs 失败。",
                )
        except Exception as exc:
            plugin_status["telemetry_persisted"] = False
            collector.add(
                code="plugin_bootstrap_telemetry_failed",
                scope="plugins.bootstrap",
                field="telemetry",
                message="插件启动留痕写入 OperationLogs 异常。",
                sample=exc.__class__.__name__,
            )
        finally:
            try:
                conn0.close()
            except Exception:
                pass

    plugin_status = _merge_plugin_degradation(plugin_status, collector)
    return plugin_status
