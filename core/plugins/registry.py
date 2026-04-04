from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PluginRegistry:
    """
    插件能力注册表（key -> provider）。

    约定：
    - key 使用 namespace 风格，例如：
      - excel_backend.openpyxl
      - excel_backend.pandas
      - solver.greedy
      - solver.ortools
    - 冲突策略：首个成功注册者保留，后续冲突者不得静默覆盖。
    """

    capabilities: Dict[str, Any] = field(default_factory=dict)
    capability_owners: Dict[str, str] = field(default_factory=dict)
    conflicted_capabilities: List[Dict[str, Any]] = field(default_factory=list)
    conflict_policy: str = "first_loaded_wins"
    _active_plugin_id: Optional[str] = field(default=None, repr=False)

    def bind_plugin(self, plugin_id: Optional[str]) -> None:
        self._active_plugin_id = str(plugin_id or "").strip() or None

    def clear_bound_plugin(self) -> None:
        self._active_plugin_id = None

    def register(self, key: str, provider: Any, *, plugin_id: Optional[str] = None) -> bool:
        capability = str(key)
        owner = str(plugin_id or self._active_plugin_id or "").strip() or None
        if capability not in self.capabilities:
            self.capabilities[capability] = provider
            if owner:
                self.capability_owners[capability] = owner
            return True

        kept_plugin_id = self.capability_owners.get(capability)
        self.conflicted_capabilities.append(
            {
                "capability": capability,
                "kept_plugin_id": kept_plugin_id,
                "rejected_plugin_id": owner,
                "policy": self.conflict_policy,
            }
        )
        return False

    def get(self, key: str, default: Any = None) -> Any:
        return self.capabilities.get(str(key), default)

    def to_dict(self) -> Dict[str, Any]:
        # provider 可能不可序列化，这里只暴露 key 列表与冲突摘要
        return {
            "capabilities": sorted(list(self.capabilities.keys())),
            "conflicted_capabilities": list(self.conflicted_capabilities),
            "conflict_policy": self.conflict_policy,
        }
