"""守护 graph 调度模块骨架契约：core/services/scheduler/graph 下必须存在 __init__.py/id_policy.py/nx_runtime.py/types.py，且这些 .py 一律不得静态 import networkx（networkx 须留给运行时惰性加载）。"""

from __future__ import annotations

import ast

from tests._support.paths import REPO_ROOT

GRAPH_DIR = REPO_ROOT / "core" / "services" / "scheduler" / "graph"


def test_graph_modules_do_not_static_import_networkx() -> None:
    offenders = []
    for path in GRAPH_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name == "networkx" or alias.name.startswith("networkx.") for alias in node.names):
                    offenders.append(str(path.relative_to(GRAPH_DIR)))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "networkx" or module.startswith("networkx."):
                    offenders.append(str(path.relative_to(GRAPH_DIR)))
    assert offenders == []
