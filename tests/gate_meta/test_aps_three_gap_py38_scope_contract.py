"""回归测试：APS Python 3.8 门禁不扫描宿主 Python 3.14 工具。"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

from tools import scan_aps_three_gap_py38_scope as scope_scan


def test_py38_scope_excludes_codestable_and_limcode_host_tools() -> None:
    assert scope_scan.is_aps_py38_scope_path(".codestable/checkup/scripts/codemap_extract.py") is False
    assert scope_scan.is_aps_py38_scope_path(".codestable/tools/search-yaml.py") is False
    assert scope_scan.is_aps_py38_scope_path(".limcode/skills/cs-onboard/tools/search-yaml.py") is False
    assert scope_scan.is_aps_py38_scope_path(".limcode/hooks/check_complexity.py") is False


def test_py38_scope_keeps_aps_product_tests_and_gate_tools() -> None:
    assert scope_scan.is_aps_py38_scope_path("core/services/scheduler/run/optimizer/graph/ready.py") is True
    assert scope_scan.is_aps_py38_scope_path("web/bootstrap/launcher.py") is True
    assert scope_scan.is_aps_py38_scope_path("tests/algorithm/test_optimizer_graph_ready_candidate_contract.py") is True
    assert scope_scan.is_aps_py38_scope_path("tools/scan_aps_three_gap_py38_scope.py") is True
    assert scope_scan.is_aps_py38_scope_path("docs/example.md") is False


def test_changed_file_collection_applies_host_tool_boundary(tmp_path, monkeypatch) -> None:
    changed = "\0".join(
        (
            ".codestable/checkup/scripts/codemap_extract.py",
            ".limcode/skills/cs-onboard/tools/validate-yaml.py",
            ".limcode/hooks/check_complexity.py",
            "core/services/scheduler/run/optimizer/graph/ready.py",
            "tests/gate_meta/test_example.py",
        )
    )
    monkeypatch.setattr(
        scope_scan.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=changed, stderr=""),
    )
    monkeypatch.setattr(scope_scan.os.path, "isfile", lambda _path: True)

    assert scope_scan._git_changed_python_files("base", str(tmp_path)) == [
        "core/services/scheduler/run/optimizer/graph/ready.py",
        "tests/gate_meta/test_example.py",
    ]


def test_deleted_but_locally_retained_file_is_not_scanned(tmp_path) -> None:
    """Exercise Git's deletion status, not only a mocked filename list."""
    def git(*args):
        return subprocess.run(
            ["git", "-c", "core.hooksPath=" + str(tmp_path / "disabled-hooks"), "-c", "user.name=Scope Test",
             "-c", "user.email=scope@example.invalid", *args],
            cwd=str(tmp_path), check=True, capture_output=True, text=True,
        )

    git("init")
    retained = tmp_path / "retained.py"
    retained.write_text("value = 1\n", encoding="utf-8")
    changed = tmp_path / "中文 文件.py"
    changed.write_text("value = 1\n", encoding="utf-8")
    git("add", ".")
    git("commit", "--no-gpg-sign", "-m", "scope fixture")
    git("rm", "--cached", "retained.py")
    changed.write_text("value = 2\n", encoding="utf-8")
    assert retained.is_file()
    assert scope_scan._git_changed_python_files("HEAD", str(tmp_path)) == ["中文 文件.py"]


def test_empty_changed_scope_does_not_expand_to_the_whole_repository(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(scope_scan, "_git_changed_python_files", lambda *args: [])

    def unexpected_scan(*args, **kwargs):
        raise AssertionError("empty scope must not become a whole-repository scan")

    monkeypatch.setattr(scope_scan.scan_py38plus_syntax, "scan_paths", unexpected_scan)
    assert scope_scan.main(["--root", str(tmp_path)]) == 0


def test_scope_exit_status_distinguishes_deferred_and_eager_annotations(tmp_path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    monkeypatch.setattr(scope_scan, "_git_changed_python_files", lambda *args: [source.name])
    source.write_text("from __future__ import annotations\ndef f() -> set[str]:\n    return set()\n", encoding="utf-8")
    assert scope_scan.main(["--root", str(tmp_path)]) == 0
    source.write_text("def f() -> set[str]:\n    return set()\n", encoding="utf-8")
    assert scope_scan.main(["--root", str(tmp_path)]) == 1
