from __future__ import annotations

import importlib.util
import os
import re
import sys
import uuid
from pathlib import Path

import pytest

# 让 tests 可以直接 import core/data/web（不要求 pip install -e .）
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


_MAIN_DEF_RE = re.compile(r"(?m)^\s*def\s+main\s*\(")
_TEST_DEF_RE = re.compile(r"(?m)^\s*def\s+test_")


def _as_path(raw_path) -> Path:
    raw = getattr(raw_path, "strpath", raw_path)
    return Path(str(raw))


def _is_main_style_regression(path: Path) -> bool:
    if path.suffix != ".py" or not path.name.startswith("regression_"):
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return False
    return bool(_MAIN_DEF_RE.search(text)) and not bool(_TEST_DEF_RE.search(text))


def _node_path(node) -> Path:
    raw = getattr(node, "path", None)
    if raw is not None:
        return Path(str(raw))
    return Path(str(node.fspath))


def _regression_file_from_parent(parent, path: Path, legacy_path):
    try:
        return RegressionMainFile.from_parent(parent, path=path)
    except TypeError:
        return RegressionMainFile.from_parent(parent, fspath=legacy_path)


def pytest_collect_file(file_path, parent):
    path = _as_path(file_path)
    if not _is_main_style_regression(path):
        return None
    return _regression_file_from_parent(parent, path, file_path)


class RegressionMainFile(pytest.File):
    def collect(self):
        yield RegressionMainItem.from_parent(self, name=_node_path(self).stem)


class RegressionMainItem(pytest.Item):
    def runtest(self) -> None:
        path = _node_path(self.parent)
        module_name = f"_aps_regression_{path.stem}_{uuid.uuid4().hex}"
        spec = importlib.util.spec_from_file_location(module_name, str(path))
        if spec is None or spec.loader is None:
            raise RuntimeError(f"无法为 {path.name} 创建模块加载器")
        module = importlib.util.module_from_spec(spec)

        original_env = os.environ.copy()
        original_cwd = os.getcwd()
        original_sys_path = list(sys.path)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
            main = getattr(module, "main", None)
            if not callable(main):
                raise AssertionError(f"{path.name} 缺少可调用的 main()")
            try:
                rc = main()
            except SystemExit as exc:
                code = exc.code
                if code in (None, 0):
                    return
                raise AssertionError(f"{path.name} 以非 0 退出：{code}") from exc
            if isinstance(rc, int) and not isinstance(rc, bool) and rc != 0:
                raise AssertionError(f"{path.name} 返回了非 0 状态码：{rc}")
        finally:
            os.chdir(original_cwd)
            os.environ.clear()
            os.environ.update(original_env)
            sys.path[:] = original_sys_path
            sys.modules.pop(module_name, None)

    def reportinfo(self):
        path = _node_path(self.parent)
        return path, 0, f"regression-main: {path.name}"

