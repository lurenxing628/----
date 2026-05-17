from __future__ import annotations

import ast
from pathlib import Path

GRAPH_DIR = Path(__file__).resolve().parents[2] / "core" / "services" / "scheduler" / "graph"


def test_graph_module_skeleton_exists() -> None:
    expected = {
        "__init__.py",
        "id_policy.py",
        "nx_runtime.py",
        "types.py",
    }
    assert expected.issubset({path.name for path in GRAPH_DIR.glob("*.py")})


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
