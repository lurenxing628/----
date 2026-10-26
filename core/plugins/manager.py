from __future__ import annotations

import importlib.util
import os
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from core.models.enums import YesNo
from core.shared.boolean_normalize import normalize_yes_no_wide

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
    enabled_source: str
    error: Optional[str] = None
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
            "capabilities": self.capabilities,
            "conflicted_capabilities": self.conflicted_capabilities,
        }


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
    def load_from_base_dir(
        cls,
        base_dir: str,
        *,
        config_reader: Optional[PluginConfigReader],
        enabled_source_map: Dict[str, str],
        default_enabled_source: str,
        logger,
    ) -> Dict[str, Any]:
        base = os.path.abspath(base_dir or ".")
        vendor_paths = bootstrap_vendor_paths(base)

        plugins_dir = os.path.join(base, "plugins")
        plugins_dir_real = os.path.normcase(os.path.realpath(plugins_dir))
        statuses: List[PluginStatus] = []
        registry = PluginRegistry()

        plugin_files = sorted(os.listdir(plugins_dir)) if os.path.isdir(plugins_dir) else []

        for fn in plugin_files:
            if not fn.endswith(".py") or fn.startswith("_"):
                continue
            path0 = os.path.join(plugins_dir, fn)
            try:
                real = os.path.normcase(os.path.realpath(path0))
                if not real.startswith(plugins_dir_real + os.sep):
                    logger.error(f"插件路径非法（已跳过）：{path0}")
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
                if config_reader is not None:
                    try:
                        raw_enabled = config_reader(plugin_id)
                    except Exception as exc:
                        raw_enabled = None
                        logger.error(f"读取插件配置失败：{plugin_id} err={exc}")
                    if raw_enabled is not None:
                        enabled = _normalize_yes_no(raw_enabled, default=default_enabled)

                loaded = "no"
                err = None
                cap_keys: List[str] = []
                conflict_keys: List[str] = []

                if enabled == YesNo.YES.value:
                    try:
                        if hasattr(mod, "register"):
                            # register 前对 registry 三个可变面做快照：register() 中途失败时
                            # 必须整体回滚本次增量——loaded=no 的插件不得以半初始化 provider
                            # 残留 registry 接管能力路由，也不得以
                            # first_loaded_wins 残留 key 挡住后续同名健康插件。
                            before_capabilities = dict(registry.capabilities)
                            before_owners = dict(registry.capability_owners)
                            before_conflict_records = list(registry.conflicted_capabilities)
                            before = set(before_capabilities.keys())
                            before_conflicts = len(before_conflict_records)
                            registry.bind_plugin(plugin_id)
                            try:
                                mod.register(registry)  # type: ignore[misc]
                            except Exception:
                                registry.capabilities = before_capabilities
                                registry.capability_owners = before_owners
                                registry.conflicted_capabilities = before_conflict_records
                                raise
                            finally:
                                registry.clear_bound_plugin()
                            after = set(registry.capabilities.keys())
                            cap_keys = sorted(after - before)
                            new_conflicts = registry.conflicted_capabilities[before_conflicts:]
                            conflict_keys = [
                                item["capability"]
                                for item in new_conflicts
                                if str(item.get("rejected_plugin_id") or "") == plugin_id
                            ]
                        loaded = "yes"
                    except Exception as e:
                        loaded = "no"
                        tb = traceback.format_exc(limit=5)
                        err = f"{e}\n{tb}"
                        logger.error(f"插件注册失败：{plugin_id} err={e}", exc_info=True)

                statuses.append(
                    PluginStatus(
                        plugin_id=plugin_id,
                        name=plugin_name,
                        version=str(plugin_ver) if plugin_ver is not None else None,
                        enabled=enabled,
                        loaded=loaded,
                        error=err,
                        enabled_source=enabled_source_map.get(plugin_id, default_enabled_source),
                        capabilities=cap_keys,
                        conflicted_capabilities=conflict_keys,
                    )
                )
            except Exception as e:
                tb = traceback.format_exc(limit=5)
                enabled = "no"
                if config_reader is not None:
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
                        enabled_source=enabled_source_map.get(guessed_id, default_enabled_source),
                        capabilities=[],
                        conflicted_capabilities=[],
                    )
                )
                logger.error(f"插件加载失败：{fn} err={e}", exc_info=True)

        registry_status = registry.to_dict()
        return {
            "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "vendor_paths": vendor_paths,
            "plugins_dir": plugins_dir,
            "statuses": [status.to_dict() for status in statuses],
            "registry": registry_status,
            "conflicted_capabilities": registry_status["conflicted_capabilities"],
            "conflict_policy": registry_status["conflict_policy"],
        }
