"""工作台簇层次适应度：簇之间只能按 workbench-cluster-layering.md §2.2 的方向依赖。"""

import ast
from pathlib import Path
from typing import Dict, Iterator, List, Set, Tuple

from tests._support.paths import REPO_ROOT

PACKAGE = REPO_ROOT / "core/services/workbench"
PREFIX = "core.services.workbench"
ALLOWED: Dict[str, Set[str]] = {
    "root": set(),
    "facts": set(),
    "plan": {"facts"},
    "process": {"facts"},
    "material": {"facts"},
    "outsourcing": {"facts"},
    "system": {"facts"},
    "master": {"facts"},
    "execution": {"facts", "plan"},
    "resource": {"facts", "process"},
    "calibration": {"facts", "process", "execution", "plan"},
    "batch": {"facts", "process", "resource", "calibration", "execution", "plan"},
    "run": {"facts", "plan", "execution"},
    "trial": {"facts", "plan", "execution", "run"},
    "report": {"facts", "plan", "execution", "run", "trial"},
    "dashboard": {"facts", "plan", "execution", "run", "trial", "report", "outsourcing"},
}
ROOT_MODULES = {"commands", "messages"}
# 尚未分包的根级模块按名字判簇；全部分包后这两张表应清空。
ROOT_OVERRIDES = {
    "suppliers": "resource", "calendars": "resource", "operator_machine_permissions": "resource",
    "materials": "material", "batches": "batch",
    "official_plan_persistence": "plan", "legacy_navigation_queries": "plan",
    "execution_ledger": "execution",
}
ROOT_PREFIX_CLUSTER = {
    "field": "execution", "production": "execution", "actual": "execution",
    "template": "calibration", "piece": "run", "preflight": "run", "review": "report",
}


def _cluster(parts: Tuple[str, ...]) -> str:
    if len(parts) > 1:
        return parts[0]
    name = parts[0]
    if name in ROOT_MODULES:
        return "root"
    if name in ROOT_OVERRIDES:
        return ROOT_OVERRIDES[name]
    head = name.split("_")[0]
    return ROOT_PREFIX_CLUSTER.get(head, head)


def _modules() -> Dict[str, Path]:
    found = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        parts = path.relative_to(PACKAGE).with_suffix("").parts
        if parts[-1] == "__init__":
            continue
        found[".".join(parts)] = path
    return found


def _targets(path: Path, module: str, known: Set[str]) -> Iterator[Tuple[int, str]]:
    package = module.rpartition(".")[0]
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level == 0:
            if not (node.module or "").startswith(PREFIX):
                continue
            base = (node.module or "")[len(PREFIX):].lstrip(".")
        else:
            base = package
            for _ in range(node.level - 1):
                base = base.rpartition(".")[0]
            base = base + ("." + node.module if node.module else "") if base else (node.module or "")
        if base in known:
            yield node.lineno, base
            continue
        for alias in node.names:
            candidate = base + "." + alias.name if base else alias.name
            if candidate in known:
                yield node.lineno, candidate


def _violations() -> List[str]:
    modules = _modules()
    known = set(modules)
    problems = []
    for module, path in modules.items():
        source = _cluster(tuple(module.split(".")))
        for line, target in _targets(path, module, known):
            destination = _cluster(tuple(target.split(".")))
            if destination in ("root", source) or destination in ALLOWED[source]:
                continue
            problems.append(f"{path.relative_to(REPO_ROOT)}:{line} {source}→{destination} ({module} → {target})")
    return problems


def test_every_cluster_is_declared_in_the_layering_table():
    clusters = {_cluster(tuple(module.split("."))) for module in _modules()}
    assert clusters <= set(ALLOWED), sorted(clusters - set(ALLOWED))


def test_every_cross_cluster_import_follows_the_allowed_direction():
    assert _violations() == []


def test_allowed_directions_form_a_dag():
    order: List[str] = []
    remaining = {name: set(deps) for name, deps in ALLOWED.items()}
    while remaining:
        ready = sorted(name for name, deps in remaining.items() if not deps - set(order))
        assert ready, "允许方向表里出现环：" + ", ".join(sorted(remaining))
        order.extend(ready)
        for name in ready:
            remaining.pop(name)


def test_subpackage_facades_only_hold_a_docstring():
    for init in sorted(PACKAGE.rglob("__init__.py")):
        tree = ast.parse(init.read_text(encoding="utf-8"))
        assert all(isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) for node in tree.body), init
