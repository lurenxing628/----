from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


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
    """

    capabilities: Dict[str, Any] = field(default_factory=dict)

    def register(self, key: str, provider: Any) -> None:
        self.capabilities[str(key)] = provider

    def get(self, key: str, default: Any = None) -> Any:
        return self.capabilities.get(str(key), default)

    def to_dict(self) -> Dict[str, Any]:
        # provider 可能不可序列化，这里只暴露 key 列表
        return {"capabilities": sorted(list(self.capabilities.keys()))}

