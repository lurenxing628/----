"""排产服务包子包层次适应度：子包之间只能按下表方向依赖；根目录模块（门面与叶子助手）暂不约束。"""

import ast
from pathlib import Path
from typing import Dict, Iterator, List, Set, Tuple

from tests._support.paths import REPO_ROOT

PACKAGE = REPO_ROOT / "core/services/scheduler"
PREFIX = "core.services.scheduler"
SUBPACKAGES = ("calendar", "config", "contracts", "execution", "gantt", "graph", "resource_dispatch", "run", "summary")
ALLOWED: Dict[str, Set[str]] = {
    "contracts": set(),
    "config": set(),
    "execution": set(),
    "graph": set(),
    "calendar": {"config"},
    "resource_dispatch": {"execution"},
    "run/optimizer": {"config", "contracts"},
    "run/optimizer/graph": {"run/optimizer", "config", "contracts"},
    "run": {"config", "contracts", "execution", "graph", "run/optimizer", "run/optimizer/graph"},
    "gantt": {"calendar", "execution", "run"},
    "summary": {"config", "contracts", "run", "run/optimizer"},
}


def _cluster(parts: Tuple[str, ...]) -> str:
    if len(parts) < 2 or parts[0] not in SUBPACKAGES:
        return "root"
    if parts[0] == "run" and len(parts) > 2 and parts[1] == "optimizer":
        return "run/optimizer/graph" if len(parts) > 3 and parts[2] == "graph" else "run/optimizer"
    return parts[0]


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
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                candidate = alias.name[len(PREFIX):].lstrip(".") if alias.name.startswith(PREFIX + ".") else ""
                if candidate in known:
                    yield node.lineno, candidate
            continue
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
        if source == "root":
            continue
        for line, target in _targets(path, module, known):
            destination = _cluster(tuple(target.split(".")))
            if destination in ("root", source) or destination in ALLOWED[source]:
                continue
            problems.append(f"{path.relative_to(REPO_ROOT)}:{line} {source}→{destination} ({module} → {target})")
    return problems


def test_every_subpackage_is_declared_in_the_layering_table():
    clusters = {_cluster(tuple(module.split("."))) for module in _modules()} - {"root"}
    assert clusters == set(ALLOWED), sorted(clusters ^ set(ALLOWED))


def test_every_cross_subpackage_import_follows_the_allowed_direction():
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


def test_targets_resolve_relative_plain_and_symbol_imports(tmp_path):
    source = tmp_path / "probe.py"
    source.write_text(
        "import core.services.scheduler.contracts.alpha as alpha\n"
        "from core.services.scheduler.config import beta\n"
        "from ...execution import gamma\n"
        "from . import delta\n",
        encoding="utf-8",
    )
    known = {"contracts.alpha", "config.beta", "execution.gamma", "run.optimizer.delta"}
    assert sorted(_targets(source, "run.optimizer.probe", known)) == [
        (1, "contracts.alpha"), (2, "config.beta"), (3, "execution.gamma"), (4, "run.optimizer.delta")]
