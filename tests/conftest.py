from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

# 让 tests 可以直接 import core/data/web（不要求 pip install -e .）
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.test_debt_registry import active_xfail_entries_by_nodeid  # noqa: E402,I001


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
    except Exception as exc:
        raise RuntimeError(f"读取 regression 文件失败：{path}: {exc}") from exc
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


def _test_debt_xfail_reason(entry) -> str:
    return f"{entry['debt_id']}: {entry['reason']}"


def pytest_collection_modifyitems(items):
    entries_by_nodeid = active_xfail_entries_by_nodeid()
    for item in items:
        entry = entries_by_nodeid.get(str(item.nodeid))
        if entry is not None:
            item.add_marker(pytest.mark.xfail(reason=_test_debt_xfail_reason(entry), strict=True))


class RegressionMainFile(pytest.File):
    def collect(self):
        yield RegressionMainItem.from_parent(self, name=_node_path(self).stem)


class RegressionMainItem(pytest.Item):
    def runtest(self) -> None:
        path = _node_path(self.parent)
        runner = REPO_ROOT / "tests" / "main_style_regression_runner.py"
        completed = subprocess.run(
            [sys.executable, str(runner), str(path.resolve())],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if int(completed.returncode) != 0:
            raise AssertionError(
                "\n".join(
                    [
                        f"{path.name} 子进程执行失败",
                        f"returncode={int(completed.returncode)}",
                        f"cwd={REPO_ROOT}",
                        f"script={path.resolve()}",
                        "stdout:",
                        str(completed.stdout or "").rstrip(),
                        "stderr:",
                        str(completed.stderr or "").rstrip(),
                    ]
                )
            )

    def reportinfo(self):
        path = _node_path(self.parent)
        return path, 0, f"regression-main: {path.name}"
