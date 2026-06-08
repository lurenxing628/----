"""契约测试：P7 防回潮门禁(tools/scan_anti_regression_gate.py)——验证三条新增文件约束
(main-style 须有 def test_ / 测试文件须有模块 docstring / 新生产源须有 scope 覆盖)的判定逻辑,
并以 tmp git 仓库铁证 B-兼容铁律:门禁只看 --diff-filter=A 新增文件,删除既有文件(R51 续命测试等)
永不入门禁视野、绝不被阻断;最后锁定实仓当前 0 违规(固化态)。"""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests._support.paths import REPO_ROOT
from tools import scan_anti_regression_gate as gate


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_path_classification() -> None:
    assert gate.is_collected_test_path("tests/web_pages/test_x.py")
    assert gate.is_collected_test_path("tests/regression_x.py")
    assert not gate.is_collected_test_path("tests/_scripts_e2e/smoke_phase2.py")
    assert not gate.is_collected_test_path("tools/foo.py")
    assert gate.is_production_source_path("core/services/x.py")
    assert gate.is_production_source_path("app.py")
    assert not gate.is_production_source_path("tools/foo.py")
    assert not gate.is_production_source_path("tests/test_x.py")


def test_missing_test_function_flags_all_zero_collect_shells(tmp_path: Path) -> None:
    """规则① 须含 test 函数:main-style/纯 import 空壳/async-main 三类伪回归(pytest 收集 0 用例)全拦;
    模块级 def test_ 与类内 test_ 方法(unittest 风格)均放行。补 docstring 也救不了空壳。"""
    cases = {
        "tests/test_main_only.py": '"""d."""\ndef main():\n    return 0\n',
        "tests/test_empty_shell.py": '"""d."""\nimport os\n\nprint(os)\n',
        "tests/test_async_main.py": '"""d."""\nasync def main():\n    return 0\n',
        "tests/test_func_ok.py": '"""d."""\ndef test_ok():\n    assert True\n',
        "tests/test_class_ok.py": '"""d."""\nimport unittest\n\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        assert True\n',
    }
    for rel, body in cases.items():
        _write(tmp_path / rel, body)
    flagged = gate.scan_missing_test_function(str(tmp_path), list(cases))
    assert flagged == ["tests/test_main_only.py", "tests/test_empty_shell.py", "tests/test_async_main.py"]


def test_missing_docstring_flags_only_undocumented(tmp_path: Path) -> None:
    no_doc = tmp_path / "tests" / "test_no_doc.py"
    with_doc = tmp_path / "tests" / "test_doc.py"
    _write(no_doc, "def test_x():\n    assert True\n")
    _write(with_doc, '"""有 docstring。"""\ndef test_x():\n    assert True\n')
    flagged = gate.scan_missing_docstring(str(tmp_path), ["tests/test_no_doc.py", "tests/test_doc.py"])
    assert flagged == ["tests/test_no_doc.py"]


def test_uncovered_source_flags_files_outside_scope_globs() -> None:
    scopes = {"core/services/scheduler/**/*.py"}
    paths = ["core/services/scheduler/schedule_service.py", "core/services/personnel/operator.py"]
    assert gate.scan_uncovered_source(paths, scopes) == ["core/services/personnel/operator.py"]


def test_added_set_excludes_deletions(tmp_path: Path) -> None:
    """B-兼容铁律:删除既有测试只进 diff-filter=D,绝不进 --diff-filter=A,故门禁永不阻断删除。"""
    def _git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True, text=True)

    _git("init", "-q")
    _git("config", "user.email", "t@example.com")
    _git("config", "user.name", "t")
    legacy = tmp_path / "tests" / "algorithm" / "test_sort_strategy_case_insensitive.py"
    _write(legacy, '"""R51 续命测试。"""\ndef test_legacy():\n    assert True\n')
    _git("add", "-A")
    _git("commit", "-qm", "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True).stdout.strip()

    legacy.unlink()
    _write(tmp_path / "tests" / "test_new_feature.py", '"""新增。"""\ndef test_new():\n    assert True\n')
    _git("add", "-A")
    _git("commit", "-qm", "B 删 R51 续命测试 + 加新测试")

    added = gate._git_added_python_files(base, str(tmp_path))
    assert "tests/test_new_feature.py" in added
    assert "tests/algorithm/test_sort_strategy_case_insensitive.py" not in added
    # 整轮门禁对「删既有 + 加合规新文件」返回 0:删除不阻断,新文件合规
    result = gate.scan_added(base, str(tmp_path))
    assert not any(result.values())


def test_live_repo_is_currently_clean() -> None:
    """固化锁:P7 落地时实仓自 d4589d77 以来的新增文件零违规,锁住治理成果不回潮。"""
    result = gate.scan_added(gate.DEFAULT_BASE_REF, str(REPO_ROOT))
    assert result == {"missing_test_function": [], "missing_docstring": [], "uncovered_source": []}
