from __future__ import annotations

import importlib
from typing import Any

_EXPECTED_VERSION = "3.1"


class NetworkXUnavailable(RuntimeError):
    pass


def import_networkx() -> Any:
    """Lazily import NetworkX so graph_analysis=off does not require it."""
    try:
        nx = importlib.import_module("networkx")
    except ImportError as exc:
        raise NetworkXUnavailable("缺少可选依赖 networkx==3.1；请先安装 requirements-optimizer-lite-win7.txt") from exc

    # 外部库边界：安装残缺（如只剩没有 __init__ 的命名空间包）时没有版本号，按不可用降级而不是抛 AttributeError。
    version = getattr(nx, "__version__", None)
    if version != _EXPECTED_VERSION:
        raise NetworkXUnavailable("NetworkX 版本不兼容：当前 {}，期望 {}".format(version or "unknown", _EXPECTED_VERSION))
    return nx


__all__ = ["NetworkXUnavailable", "import_networkx"]
