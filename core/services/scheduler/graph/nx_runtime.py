from __future__ import annotations

import importlib
from typing import Any


class NetworkXUnavailable(RuntimeError):
    pass


def import_networkx() -> Any:
    """Lazily import NetworkX so graph_analysis=off does not require it."""
    try:
        return importlib.import_module("networkx")
    except ImportError as exc:
        raise NetworkXUnavailable("缺少可选依赖 networkx==3.1；请先安装 requirements-optimizer-lite-win7.txt") from exc


__all__ = ["NetworkXUnavailable", "import_networkx"]
