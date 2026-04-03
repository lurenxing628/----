from __future__ import annotations

import logging

from core.infrastructure.database import get_connection
from core.infrastructure.logging import OperationLogger
from core.plugins import PluginManager, get_plugin_status


def _append_plugin_degradation(status, *, code: str, message: str, sample: str | None = None):
    base = dict(status or {}) if isinstance(status, dict) else {}
    events = list(base.get("degradation_events") or [])
    counters = dict(base.get("degradation_counters") or {})
    events.append(
        {
            "code": str(code),
            "scope": "plugins.bootstrap",
            "field": "telemetry",
            "message": str(message),
            "count": 1,
            "sample": sample,
        }
    )
    counters[str(code)] = int(counters.get(str(code), 0) or 0) + 1
    base["degraded"] = True
    base["degradation_events"] = events
    base["degradation_counters"] = counters
    return base


def bootstrap_plugins(base_dir: str, database_path: str, *, logger: logging.Logger | None = None):
    """
    加载可选插件并记录运行留痕。

    失败不阻断启动，返回可观测状态用于系统页展示。
    """
    plugin_status = None
    conn0 = None
    try:
        conn0 = get_connection(database_path)
    except Exception as e:
        conn0 = None
        if logger is not None:
            try:
                logger.warning(f"打开数据库连接失败，插件加载将跳过配置落库：{e}")
            except Exception:
                pass

    try:
        plugin_status = PluginManager.load_from_base_dir(base_dir, conn=conn0, logger=logger)
    except Exception as e:
        if logger is not None:
            try:
                logger.error(f"插件加载失败（已忽略，启动继续）：{e}")
            except Exception:
                pass
        try:
            plugin_status = get_plugin_status()
        except Exception:
            plugin_status = None

    if isinstance(plugin_status, dict):
        plugin_status.setdefault("degraded", False)
        plugin_status.setdefault("degradation_events", [])
        plugin_status.setdefault("degradation_counters", {})

    if conn0 is not None:
        try:
            logged = OperationLogger(conn0, logger=logger).info(
                "plugins",
                "load",
                target_type="runtime",
                target_id="plugins",
                detail=plugin_status,
            )
            if isinstance(plugin_status, dict):
                plugin_status["telemetry_persisted"] = bool(logged)
            if logged is False:
                plugin_status = _append_plugin_degradation(plugin_status, code="plugin_bootstrap_telemetry_failed", message="插件启动留痕写入 OperationLogs 失败。")
        except Exception as exc:
            if isinstance(plugin_status, dict):
                plugin_status["telemetry_persisted"] = False
            plugin_status = _append_plugin_degradation(
                plugin_status, code="plugin_bootstrap_telemetry_failed", message="插件启动留痕写入 OperationLogs 异常。", sample=exc.__class__.__name__
            )
        finally:
            try:
                conn0.close()
            except Exception:
                pass

    return plugin_status

