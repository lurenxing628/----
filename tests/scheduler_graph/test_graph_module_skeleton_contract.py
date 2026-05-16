from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GRAPH_DIR = REPO_ROOT / "core" / "services" / "scheduler" / "graph"

EXPECTED_GRAPH_MODULES = (
    "__init__.py",
    "nx_runtime.py",
    "types.py",
    "id_policy.py",
    "input_adapter.py",
    "precedence_builder.py",
    "validators.py",
    "metrics.py",
    "ready_queue.py",
    "scoring.py",
    "resource_matching.py",
    "exporter.py",
    "analysis_service.py",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_graph_module_skeleton_files_exist() -> None:
    assert GRAPH_DIR.is_dir()
    missing = [name for name in EXPECTED_GRAPH_MODULES if not (GRAPH_DIR / name).is_file()]
    assert missing == []


def test_graph_package_init_stays_passive() -> None:
    source = _read(GRAPH_DIR / "__init__.py")
    tree = ast.parse(source, filename="core/services/scheduler/graph/__init__.py")
    imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert imports == []


def test_graph_modules_do_not_use_static_networkx_imports() -> None:
    violations = []
    for path in sorted(GRAPH_DIR.glob("*.py")):
        tree = ast.parse(_read(path), filename=str(path.relative_to(REPO_ROOT)))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "networkx" or alias.name.startswith("networkx."):
                        violations.append(f"{path.name}:{node.lineno}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = str(node.module or "")
                if module == "networkx" or module.startswith("networkx."):
                    violations.append(f"{path.name}:{node.lineno}: from {module} import ...")
    assert violations == []
