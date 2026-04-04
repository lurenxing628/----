from __future__ import annotations

import importlib.util
import os
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from core.models.enums import YesNo
from core.services.common.enum_normalizers import normalize_yes_no_wide

from .registry import PluginRegistry
from .runtime import bootstrap_vendor_paths

PluginConfigReader = Callable[[str], Optional[Any]]


def _normalize_yes_no(value: Any, default: str = "no") -> str:
    return normalize_yes_no_wide(value, default=default, unknown_policy="default")


@dataclass
class PluginStatus:
    plugin_id: str
    name: str
    version: Optional[str]
    enabled: str  # yes/no
    loaded: str  # yes/no
    error: Optional[str] = None
    enabled_source: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)  # registered capability keys
    conflicted_capabilities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "enabled": self.enabled,
            "loaded": self.loaded,
            "error": self.error,
            "enabled_source": self.enabled_source,
            "capabilities": self.capabilities or [],
            "conflicted_capabilities": self.conflicted_capabilities or [],
        }


# 进程内全局状态（用于系统页展示）
_STATE: Dict[str, Any] = {
    "loaded_at": None,
    "vendor_paths": [],
    "plugins_dir": None,
    "statuses": [],
    "registry": PluginRegistry(),
    "conflicted_capabilities": [],
    "conflict_policy": PluginRegistry().conflict_policy,
}


def get_plugin_status() -> Dict[str, Any]:
    registry = _STATE.get("registry") or PluginRegistry()
    registry_dict = registry.to_dict() if hasattr(registry, "to_dict") else PluginRegistry().to_dict()
    return {
        "loaded_at": _STATE.get("loaded_at"),
        "vendor_paths": list(_STATE.get("vendor_paths") or []),
        "plugins_dir": _STATE.get("plugins_dir"),
        "statuses": [s.to_dict() if hasattr(s, "to_dict") else s for s in (_STATE.get("statuses") or [])],
        "registry": registry_dict,
        "conflicted_capabilities": list(_STATE.get("conflicted_capabilities") or registry_dict.get("conflicted_capabilities") or []),
        "conflict_policy": _STATE.get("conflict_policy") or registry_dict.get("conflict_policy") or PluginRegistry().conflict_policy,
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
    - conn 参数仅为兼容保留，管理器本身不再直接依赖仓储层读取配置。
    """

    @classmethod
    def load_from_base_dir(
        cls,
        base_dir: str,
        *,
        config_reader: Optional[PluginConfigReader] = None,
        conn=None,
        logger=None,
    ) -> Dict[str, Any]:
        base = os.path.abspath(base_dir or ".")
        vendor_paths = bootstrap_vendor_paths(base)

        plugins_dir = os.path.join(base, "plugins")
        plugins_dir_real = os.path.normcase(os.path.realpath(plugins_dir))
        statuses: List[PluginStatus] = []
        registry = PluginRegistry()

        enabled_source_map = getattr(config_reader, "enabled_source_map", {}) if callable(config_reader) else {}
        if not isinstance(enabled_source_map, dict):
            enabled_source_map = {}
        default_enabled_source = str(getattr(config_reader, "default_enabled_source", "default") or "default")
        if not default_enabled_source:
            default_enabled_source = "default"

        if not os.path.isdir(plugins_dir):
            _STATE.update(
                {
                    "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "vendor_paths": vendor_paths,
                    "plugins_dir": plugins_dir,
                    "statuses": statuses,
                    "registry": registry,
                    "conflicted_capabilities": list(registry.conflicted_capabilities),
                    "conflict_policy": registry.conflict_policy,
                }
            )
            return get_plugin_status()

        for fn in sorted(os.listdir(plugins_dir)):
            if not fn.endswith(".py") or fn.startswith("_"):
                continue
            path0 = os.path.join(plugins_dir, fn)
            try:
                real = os.path.normcase(os.path.realpath(path0))
                if not real.startswith(plugins_dir_real + os.sep):
                    if logger:
                        try:
                            logger.error(f"插件路径非法（已跳过）：{path0}")
                        except Exception:
                            pass
                    continue
                if not os.path.isfile(real):
                    continue
                path = real
            except Exception:
                continue

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
                if callable(config_reader):
                    try:
                        raw_enabled = config_reader(plugin_id)
                    except Exception as exc:
                        raw_enabled = None
                        if logger is not None:
                            try:
                                logger.error(f"读取插件配置失败：{plugin_id} err={exc}")
                            except Exception:
                                pass
                    if raw_enabled is not None:
                        enabled = _normalize_yes_no(raw_enabled, default=default_enabled)

                loaded = "no"
                err = None
                cap_keys: List[str] = []
                conflict_keys: List[str] = []

                if enabled == YesNo.YES.value:
                    try:
                        if hasattr(mod, "register"):
                            before = set(registry.capabilities.keys())
                            before_conflicts = len(registry.conflicted_capabilities)
                            registry.bind_plugin(plugin_id)
                            try:
                                mod.register(registry)  # type: ignore[misc]
                            finally:
                                registry.clear_bound_plugin()
                            after = set(registry.capabilities.keys())
                            cap_keys = sorted(list(after - before))
                            new_conflicts = registry.conflicted_capabilities[before_conflicts:]
                            conflict_keys = [
                                str(item.get("capability") or "")
                                for item in new_conflicts
                                if str(item.get("rejected_plugin_id") or "") == plugin_id
                            ]
                        loaded = "yes"
                    except Exception as e:
                        loaded = "no"
                        tb = traceback.format_exc(limit=5)
                        err = f"{e}\n{tb}"
                        if logger:
                            try:
                                try:
                                    logger.error(f"插件注册失败：{plugin_id} err={e}", exc_info=True)
                                except TypeError:
                                    logger.error(f"插件注册失败：{plugin_id} err={e}\n{tb}")
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
                        enabled_source=str(enabled_source_map.get(plugin_id) or default_enabled_source),
                        capabilities=cap_keys,
                        conflicted_capabilities=conflict_keys,
                    )
                )
            except Exception as e:
                tb = traceback.format_exc(limit=5)
                enabled = "no"
                if callable(config_reader):
                    try:
                        raw_enabled = config_reader(guessed_id)
                    except Exception:
                        raw_enabled = None
                    if raw_enabled is not None:
                        enabled = _normalize_yes_no(raw_enabled, default="no")
                statuses.append(
                    PluginStatus(
                        plugin_id=guessed_id,
                        name=guessed_id,
                        version=None,
                        enabled=enabled,
                        loaded="no",
                        error=f"{e}\n{tb}",
                        enabled_source=str(enabled_source_map.get(guessed_id) or default_enabled_source),
                        capabilities=[],
                        conflicted_capabilities=[],
                    )
                )
                if logger:
                    try:
                        try:
                            logger.error(f"插件加载失败：{fn} err={e}", exc_info=True)
                        except TypeError:
                            logger.error(f"插件加载失败：{fn} err={e}\n{tb}")
                    except Exception:
                        pass

        _STATE.update(
            {
                "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "vendor_paths": vendor_paths,
                "plugins_dir": plugins_dir,
                "statuses": statuses,
                "registry": registry,
                "conflicted_capabilities": list(registry.conflicted_capabilities),
                "conflict_policy": registry.conflict_policy,
            }
        )

        return get_plugin_status()
