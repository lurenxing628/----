from __future__ import annotations

import importlib.util
import os
import traceback
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from data.repositories import SystemConfigRepository

from .registry import PluginRegistry
from .runtime import bootstrap_vendor_paths


def _normalize_yes_no(value: Any, default: str = "no") -> str:
    if value is None:
        return default
    v = str(value).strip().lower()
    if v in ("yes", "y", "true", "1", "on"):
        return "yes"
    if v in ("no", "n", "false", "0", "off", ""):
        return "no"
    return default


@dataclass
class PluginStatus:
    plugin_id: str
    name: str
    version: Optional[str]
    enabled: str  # yes/no
    loaded: str  # yes/no
    error: Optional[str] = None
    capabilities: List[str] = None  # registered capability keys

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "enabled": self.enabled,
            "loaded": self.loaded,
            "error": self.error,
            "capabilities": self.capabilities or [],
        }


# 进程内全局状态（用于系统页展示）
_STATE: Dict[str, Any] = {
    "loaded_at": None,
    "vendor_paths": [],
    "plugins_dir": None,
    "statuses": [],
    "registry": PluginRegistry(),
}


def get_plugin_status() -> Dict[str, Any]:
    return {
        "loaded_at": _STATE.get("loaded_at"),
        "vendor_paths": list(_STATE.get("vendor_paths") or []),
        "plugins_dir": _STATE.get("plugins_dir"),
        "statuses": [s.to_dict() if hasattr(s, "to_dict") else s for s in (_STATE.get("statuses") or [])],
        "registry": (_STATE.get("registry") or PluginRegistry()).to_dict(),
    }


def get_plugin_registry() -> PluginRegistry:
    reg = _STATE.get("registry")
    return reg if isinstance(reg, PluginRegistry) else PluginRegistry()


class PluginManager:
    """
    插件管理器（动态加载 plugins/ 下的 *.py 模块）。

    插件模块约定（最小）：
    - PLUGIN_ID: str（可选；缺省为文件名）
    - PLUGIN_NAME: str（可选）
    - PLUGIN_VERSION: str（可选）
    - PLUGIN_DEFAULT_ENABLED: "yes"/"no"（可选；缺省 no）
    - register(registry: PluginRegistry) -> None（可选；若存在则在 enabled=yes 时调用）

    注意：
    - 插件文件应尽量避免在 import 顶层引入重依赖（pandas/ortools 等），建议在 register 内再 import，
      以便在“禁用/缺失依赖”时也能被管理器读取元信息并展示状态。
    """

    @classmethod
    def load_from_base_dir(cls, base_dir: str, *, conn=None, logger=None) -> Dict[str, Any]:
        base = os.path.abspath(base_dir or ".")
        vendor_paths = bootstrap_vendor_paths(base)

        plugins_dir = os.path.join(base, "plugins")
        statuses: List[PluginStatus] = []
        registry = PluginRegistry()

        # 读取/落库默认开关
        cfg_repo = SystemConfigRepository(conn, logger=logger) if conn is not None else None

        if not os.path.isdir(plugins_dir):
            _STATE.update(
                {
                    "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "vendor_paths": vendor_paths,
                    "plugins_dir": plugins_dir,
                    "statuses": statuses,
                    "registry": registry,
                }
            )
            return get_plugin_status()

        for fn in sorted(os.listdir(plugins_dir)):
            if not fn.endswith(".py"):
                continue
            if fn.startswith("_"):
                continue
            path = os.path.join(plugins_dir, fn)
            module_name = f"aps_plugins.{os.path.splitext(fn)[0]}"

            guessed_id = os.path.splitext(fn)[0]
            try:
                spec = importlib.util.spec_from_file_location(module_name, path)
                if not spec or not spec.loader:
                    raise RuntimeError("spec/load 失败")
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)  # type: ignore[attr-defined]

                plugin_id = str(getattr(mod, "PLUGIN_ID", None) or guessed_id)
                plugin_name = str(getattr(mod, "PLUGIN_NAME", None) or plugin_id)
                plugin_ver = getattr(mod, "PLUGIN_VERSION", None)
                default_enabled = _normalize_yes_no(getattr(mod, "PLUGIN_DEFAULT_ENABLED", None), default="no")

                enabled = default_enabled
                if cfg_repo is not None:
                    key = f"plugin.{plugin_id}.enabled"
                    val = cfg_repo.get_value(key, default=None)
                    if val is None:
                        cfg_repo.set(key, default_enabled, description=f"插件开关：{plugin_name}（yes/no；修改后需重启生效）")
                        try:
                            conn.commit()
                        except Exception:
                            pass
                        enabled = default_enabled
                    else:
                        enabled = _normalize_yes_no(val, default=default_enabled)

                loaded = "no"
                err = None
                cap_keys: List[str] = []

                if enabled == "yes":
                    try:
                        # 注册能力
                        if hasattr(mod, "register"):
                            before = set(registry.capabilities.keys())
                            mod.register(registry)  # type: ignore[misc]
                            after = set(registry.capabilities.keys())
                            cap_keys = sorted(list(after - before))
                        loaded = "yes"
                    except Exception as e:
                        loaded = "no"
                        tb = traceback.format_exc(limit=5)
                        err = f"{e}\n{tb}"
                        if logger:
                            try:
                                logger.error(f"插件注册失败：{plugin_id} err={e}")
                            except Exception:
                                pass

                statuses.append(
                    PluginStatus(
                        plugin_id=plugin_id,
                        name=plugin_name,
                        version=str(plugin_ver) if plugin_ver is not None else None,
                        enabled=enabled,
                        loaded=loaded,
                        error=err,
                        capabilities=cap_keys,
                    )
                )
            except Exception as e:
                tb = traceback.format_exc(limit=5)
                enabled = "no"
                if cfg_repo is not None:
                    try:
                        enabled = _normalize_yes_no(cfg_repo.get_value(f"plugin.{guessed_id}.enabled", default="no"), default="no")
                    except Exception:
                        enabled = "no"
                statuses.append(
                    PluginStatus(
                        plugin_id=guessed_id,
                        name=guessed_id,
                        version=None,
                        enabled=enabled,
                        loaded="no",
                        error=f"{e}\n{tb}",
                        capabilities=[],
                    )
                )
                if logger:
                    try:
                        logger.error(f"插件加载失败：{fn} err={e}")
                    except Exception:
                        pass

        _STATE.update(
            {
                "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "vendor_paths": vendor_paths,
                "plugins_dir": plugins_dir,
                "statuses": statuses,
                "registry": registry,
            }
        )

        return get_plugin_status()

