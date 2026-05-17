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
    except Exception as exc:
        raise NetworkXUnavailable("缺少可选依赖 networkx==3.1；请先安装 requirements-optimizer-lite-win7.txt") from exc

    version = str(getattr(nx, "__version__", "") or "").strip()
    if version != _EXPECTED_VERSION:
        raise NetworkXUnavailable("NetworkX 版本不兼容：当前 {}，期望 {}".format(version or "unknown", _EXPECTED_VERSION))
    return nx


__all__ = ["NetworkXUnavailable", "import_networkx"]
