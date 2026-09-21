"""回归测试：APS Python 3.8 门禁不扫描宿主 Python 3.14 工具。"""

from __future__ import annotations

from types import SimpleNamespace

from tools import scan_aps_three_gap_py38_scope as scope_scan


def test_py38_scope_excludes_codestable_and_limcode_host_tools() -> None:
    assert scope_scan.HOST_TOOL_PYTHON_PREFIXES == (".codestable/", ".limcode/skills/")
    for prefix in scope_scan.HOST_TOOL_PYTHON_PREFIXES:
        assert scope_scan.is_aps_py38_scope_path(prefix + "sample.py") is False


def test_py38_scope_keeps_aps_product_tests_and_gate_tools() -> None:
    assert scope_scan.is_aps_py38_scope_path("core/services/scheduler/run/optimizer/graph/ready.py") is True
    assert scope_scan.is_aps_py38_scope_path("web/bootstrap/launcher.py") is True
    assert scope_scan.is_aps_py38_scope_path("tests/algorithm/test_optimizer_graph_ready_candidate_contract.py") is True
    assert scope_scan.is_aps_py38_scope_path("tools/scan_aps_three_gap_py38_scope.py") is True
    assert scope_scan.is_aps_py38_scope_path("docs/example.md") is False


def test_changed_file_collection_applies_host_tool_boundary(tmp_path, monkeypatch) -> None:
    changed = "\n".join(
        [prefix + "sample.py" for prefix in scope_scan.HOST_TOOL_PYTHON_PREFIXES]
        + ["core/services/scheduler/run/optimizer/graph/ready.py", "tests/gate_meta/test_example.py"]
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
