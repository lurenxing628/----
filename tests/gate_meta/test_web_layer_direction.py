"""web 层内部依赖方向合同（2026-09-20 web 目录环消除后锁定）。

- web/routes/** 任何位置（含函数内延迟导入）不得 import web.bootstrap；
- web/bootstrap/** 只有 factory.py 装配蓝图时可以 import web.routes；
- web 根辅助模块（web/*.py，例如 api_responses / runtime_host）不得 import routes 或 bootstrap；
- 根目录不再有 config.py：应用配置归 web/bootstrap/app_config.py，生产范围不再有目录环。
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Iterator, List, Tuple

from tests._support.paths import REPO_ROOT

_WEB = Path(REPO_ROOT) / "web"


def _python_files(base: Path) -> Iterator[Path]:
    for path in sorted(base.rglob("*.py")):
        if "__pycache__" not in path.parts:
            yield path


def _imported_modules(path: Path) -> List[Tuple[int, str]]:
    package_parts = list(path.relative_to(REPO_ROOT).with_suffix("").parts)
    if package_parts[-1] == "__init__":
        package_parts.pop()
    else:
        package_parts.pop()  # 模块所在包
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rows: List[Tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            rows.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = str(node.module or "")
            else:
                anchor = package_parts[: len(package_parts) - (node.level - 1)]
                base = ".".join(anchor + ([node.module] if node.module else []))
            rows.append((node.lineno, base))
            rows.extend((node.lineno, base + "." + alias.name) for alias in node.names)
    return rows


def _violations(files: Iterator[Path], forbidden_prefix: str) -> List[str]:
    found = []
    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        for lineno, module in _imported_modules(path):
            if module == forbidden_prefix or module.startswith(forbidden_prefix + "."):
                found.append(f"{rel}:{lineno} {module}")
    return found


def test_routes_never_import_bootstrap() -> None:
    assert not _violations(_python_files(_WEB / "routes"), "web.bootstrap"), (
        "web/routes 反向依赖 web/bootstrap（运行时能力应经 web/runtime_host 读取 app.extensions）"
    )


def test_bootstrap_imports_routes_only_from_factory() -> None:
    files = (path for path in _python_files(_WEB / "bootstrap") if path.name != "factory.py")
    assert not _violations(files, "web.routes"), "web/bootstrap 里只有 factory.py 可以装配 web/routes 蓝图"


def test_web_root_helpers_import_neither_routes_nor_bootstrap() -> None:
    files = [path for path in sorted(_WEB.glob("*.py"))]
    assert files
    for prefix in ("web.routes", "web.bootstrap"):
        assert not _violations(iter(files), prefix), f"web 根辅助模块不得依赖 {prefix}"


def test_root_config_module_retired_into_bootstrap_package() -> None:
    assert not (Path(REPO_ROOT) / "config.py").exists()
    assert (_WEB / "bootstrap" / "app_config.py").is_file()
    offenders = []
    for base in ("core", "web", "data", "tools", "scripts", "tests"):
        for path in _python_files(Path(REPO_ROOT) / base):
            if any(module == "config" or module.startswith("config.") for _lineno, module in _imported_modules(path)):
                offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert not offenders, "仍有模块 import 根目录 config：" + ", ".join(offenders)


def test_production_scope_has_no_hard_directory_cycle() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "tools.scan_import_cycles", "--json"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
    )
    report = json.loads(completed.stdout)
    assert report["hard_dir_cycles"] == [], report["hard_dir_cycles"]
