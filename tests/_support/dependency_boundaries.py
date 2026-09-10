"""Small dependency assertions shared by the remaining-cycle slices."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from tests._support.paths import REPO_ROOT


def assert_import_orders(legacy, canonical, names):
    for first, second in ((legacy, canonical), (canonical, legacy)):
        script = f"import {first} as first\nimport {second} as second\n"
        script += "\n".join(f"assert first.{name} is second.{name}" for name in names)
        completed = subprocess.run(
            [sys.executable, "-c", script], cwd=str(REPO_ROOT),
            capture_output=True, text=True, timeout=60,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr


def assert_no_import_prefixes(path, prefixes):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        modules = []
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
        for module in modules:
            assert not any(module == prefix or module.startswith(prefix + ".") for prefix in prefixes), (path, node.lineno, module)
