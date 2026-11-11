from __future__ import annotations

import logging
import os
import sqlite3
from typing import Dict, List

from core.infrastructure.logging import OperationLogger, safe_log
from core.models.scheduler_degradation_messages import public_degradation_events
from core.plugins.manager import PluginManager
from core.plugins.registry import PluginRegistry
from core.shared.degradation import DegradationCollector, degradation_events_to_dicts
from data.repositories import SystemConfigRepository


def _config_source_summary(sources: List[str]) -> str:
    source_set = set(sources)
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
    return "default"


def _build_plugin_config_reader(
    conn: sqlite3.Connection,
    *,
    logger: logging.Logger,
    collector: DegradationCollector,
):
    enabled_source_map: Dict[str, str] = {}
    repo = SystemConfigRepository(conn, logger=logger)

    def _reader(plugin_id: str):
        plugin_key = plugin_id.strip()
        key = f"plugin.{plugin_key}.enabled"
        try:
            value = repo.get_value(key)
        except Exception as exc:
            enabled_source_map[plugin_id] = "default_due_to_config_read_failed"
            collector.add(
                code="plugin_bootstrap_config_read_failed",
                scope="plugins.bootstrap",
                field=key,
                message=f"读取扩展功能设置失败，扩展功能 {plugin_key or '-'} 当前按默认开关运行。",
                sample=exc.__class__.__name__,
            )
            safe_log(logger, "warning", "读取扩展功能设置失败，当前按默认开关运行：key=%s err=%s", key, exc)
            return None

        enabled_source_map[plugin_id] = "config" if value is not None else "default"
        return value

    return _reader, enabled_source_map


def bootstrap_plugins(base_dir: str, conn: sqlite3.Connection, *, logger: logging.Logger):
    """加载可选插件并记录运行留痕；失败不阻断启动，返回可观测状态用于系统页展示。"""
    if conn.in_transaction:
        raise RuntimeError("bootstrap_plugins requires a clean connection outside any transaction")
    collector = DegradationCollector()
    config_reader, enabled_source_map = _build_plugin_config_reader(
        conn, logger=logger, collector=collector,
    )

    try:
        plugin_status = PluginManager.load_from_base_dir(
            base_dir,
            config_reader=config_reader,
            enabled_source_map=enabled_source_map,
            default_enabled_source="default",
            logger=logger,
        )
    except Exception as exc:
        collector.add(
            code="plugin_bootstrap_load_failed",
            scope="plugins.bootstrap",
            field="plugins",
            message="插件加载失败，请联系维护人员检查系统运行记录。",
            sample=exc.__class__.__name__,
        )
        safe_log(logger, "error", "扩展功能加载失败（已忽略，启动继续）：%s", exc)
        registry = PluginRegistry().to_dict()
        plugin_status = {
            "loaded_at": None, "vendor_paths": [],
            "plugins_dir": os.path.join(os.path.abspath(base_dir), "plugins"),
            "statuses": [], "registry": registry,
            "conflicted_capabilities": registry["conflicted_capabilities"],
            "conflict_policy": registry["conflict_policy"],
        }

    plugin_status["config_source"] = _config_source_summary(
        [row["enabled_source"] for row in plugin_status["statuses"]],
    )
    plugin_status["telemetry_persisted"] = None
    for row in plugin_status["statuses"]:
        if not row["error"]:
            continue
        row["error"] = "插件加载失败，请联系维护人员检查系统运行记录。"
        collector.add(
            code="plugin_bootstrap_load_failed", scope="plugins.bootstrap",
            field=f"plugin.{row['plugin_id']}", message=row["error"],
        )

    logged = OperationLogger(conn, logger=logger).info(
        "plugins", "load", target_type="runtime", target_id="plugins", detail=plugin_status,
    )
    plugin_status["telemetry_persisted"] = logged
    if not logged:
        collector.add(
            code="plugin_bootstrap_telemetry_failed", scope="plugins.bootstrap",
            field="telemetry", message="扩展功能启动记录写入操作日志失败。",
        )

    plugin_status["degraded"] = bool(collector)
    plugin_status["degradation_events"] = public_degradation_events(degradation_events_to_dicts(collector.to_list()))
    plugin_status["degradation_counters"] = collector.to_counters()
    return plugin_status
