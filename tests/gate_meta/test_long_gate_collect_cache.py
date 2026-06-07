"""守护 long-gate collect 缓存：build_collect_nodeids_payload 按文件分组 nodeids 并保留带空格的参数化用例名、规整日志路径分隔符；decide_reuse 在指纹与产物一致时复用，在新增/删除/改动测试文件、conftest、pyproject、依赖清单或 PYTEST_ADDOPTS 环境变化时判定重跑并给出 invalidated_by 原因。"""

from __future__ import annotations

from pathlib import Path

from tools.long_gate_cache import decide_reuse, write_success
from tools.long_gate_collect import COLLECT_NODEIDS_REL, build_collect_nodeids_payload, write_collect_nodeids
from tools.long_gate_fingerprint import fingerprint_entry
from tools.long_gate_manifest import build_manifest_from_quality_gate_plan


def _collect_command():
    return {
        "display": "python -m pytest --collect-only -q tests",
        "args": ["python", "-m", "pytest", "--collect-only", "-q", "tests"],
        "capture_output": True,
        "output_policy": "normalized",
    }


def _collect_entry(repo_root: Path) -> dict:
    manifest = build_manifest_from_quality_gate_plan([_collect_command()], repo_root=str(repo_root))
    return manifest["entries"][0]


def _write_test_file(repo_root: Path, rel_path: str, text: str = "def test_ok():\n    assert True\n") -> Path:
    path = repo_root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_collect_success(repo_root: Path, entry: dict, fingerprint: dict) -> None:
    stdout = "\n".join(
        [
            "tests/test_a.py::test_a",
            "tests/sub/test_b.py::TestB::test_b",
        ]
    )
    payload = build_collect_nodeids_payload(
        stdout,
        pytest_version="pytest 8.3.5",
        collect_stdout_log_path="evidence/QualityGate/long_gate/logs/pytest_collect_all.stdout.log",
    )
    rel_path = write_collect_nodeids(payload, repo_root=str(repo_root))
    write_success(
        entry,
        fingerprint,
        {"stdout": stdout, "stderr": "", "returncode": 0, "duration_s": 2.5},
        [str(repo_root / rel_path)],
        repo_root=str(repo_root),
    )


def test_collect_nodeids_payload_groups_nodeids_by_file():
    stdout = "\n".join(
        [
            "tests/test_a.py::test_one",
            "tests/test_a.py::test_two",
            "tests/sub/test_b.py::TestB::test_three",
            "3 tests collected in 0.01s",
        ]
    )

    payload = build_collect_nodeids_payload(
        stdout,
        pytest_version="pytest 8.3.5",
        collect_stdout_log_path="evidence\\QualityGate\\logs\\stdout.log",
    )

    assert payload["nodeids"] == [
        "tests/test_a.py::test_one",
        "tests/test_a.py::test_two",
        "tests/sub/test_b.py::TestB::test_three",
    ]
    assert payload["nodeid_count"] == 3
    assert payload["nodeid_hash"]
    assert payload["nodeids_by_file"] == {
        "tests/sub/test_b.py": ["tests/sub/test_b.py::TestB::test_three"],
        "tests/test_a.py": ["tests/test_a.py::test_one", "tests/test_a.py::test_two"],
    }
    assert payload["pytest_version"] == "pytest 8.3.5"
    assert payload["collect_stdout_log_path"] == "evidence/QualityGate/logs/stdout.log"


def test_collect_nodeids_payload_preserves_parameterized_nodeids_with_spaces():
    stdout = "\n".join(
        [
            "tests/test_a.py::test_name[value with spaces]",
            "tests/test_a.py::test_collected_word[already collected text]",
            "2 tests collected in 0.01s",
        ]
    )

    payload = build_collect_nodeids_payload(stdout, pytest_version="pytest 8.3.5")

    assert payload["nodeids"] == [
        "tests/test_a.py::test_name[value with spaces]",
        "tests/test_a.py::test_collected_word[already collected text]",
    ]


def test_collect_cache_reuses_when_inputs_and_output_match(tmp_path):
    _write_test_file(tmp_path, "tests/test_a.py")
    entry = _collect_entry(tmp_path)
    fingerprint = fingerprint_entry(entry, str(tmp_path))
    _write_collect_success(tmp_path, entry, fingerprint)

    decision = decide_reuse(entry, fingerprint_entry(entry, str(tmp_path)), repo_root=str(tmp_path))

    assert decision["decision"] == "reuse"
    assert (tmp_path / COLLECT_NODEIDS_REL).exists()


def test_collect_cache_invalidates_when_test_file_is_added(tmp_path):
    _write_test_file(tmp_path, "tests/test_a.py")
    entry = _collect_entry(tmp_path)
    fingerprint = fingerprint_entry(entry, str(tmp_path))
    _write_collect_success(tmp_path, entry, fingerprint)

    _write_test_file(tmp_path, "tests/test_new_feature.py")
    decision = decide_reuse(entry, fingerprint_entry(entry, str(tmp_path)), repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert "added input file: tests/test_new_feature.py" in decision["invalidated_by"]


def test_collect_cache_invalidates_when_test_file_is_deleted(tmp_path):
    first = _write_test_file(tmp_path, "tests/test_a.py")
    _write_test_file(tmp_path, "tests/test_b.py")
    entry = _collect_entry(tmp_path)
    fingerprint = fingerprint_entry(entry, str(tmp_path))
    _write_collect_success(tmp_path, entry, fingerprint)

    first.unlink()
    decision = decide_reuse(entry, fingerprint_entry(entry, str(tmp_path)), repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert "removed input file: tests/test_a.py" in decision["invalidated_by"]


def test_collect_cache_invalidates_when_conftest_changes(tmp_path):
    _write_test_file(tmp_path, "tests/test_a.py")
    conftest = _write_test_file(tmp_path, "tests/conftest.py", "VALUE = 1\n")
    entry = _collect_entry(tmp_path)
    fingerprint = fingerprint_entry(entry, str(tmp_path))
    _write_collect_success(tmp_path, entry, fingerprint)

    conftest.write_text("VALUE = 2\n", encoding="utf-8")
    decision = decide_reuse(entry, fingerprint_entry(entry, str(tmp_path)), repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert "modified input file: tests/conftest.py" in decision["invalidated_by"]


def test_collect_cache_invalidates_when_test_file_content_changes(tmp_path):
    test_file = _write_test_file(tmp_path, "tests/test_a.py")
    entry = _collect_entry(tmp_path)
    fingerprint = fingerprint_entry(entry, str(tmp_path))
    _write_collect_success(tmp_path, entry, fingerprint)

    test_file.write_text("def test_ok():\n    assert 1 == 1\n", encoding="utf-8")
    decision = decide_reuse(entry, fingerprint_entry(entry, str(tmp_path)), repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert "modified input file: tests/test_a.py" in decision["invalidated_by"]


def test_collect_cache_invalidates_when_pyproject_changes(tmp_path):
    _write_test_file(tmp_path, "tests/test_a.py")
    pyproject = _write_test_file(tmp_path, "pyproject.toml", "[tool.pytest.ini_options]\n")
    entry = _collect_entry(tmp_path)
    fingerprint = fingerprint_entry(entry, str(tmp_path))
    _write_collect_success(tmp_path, entry, fingerprint)

    pyproject.write_text("[tool.pytest.ini_options]\naddopts = '-q'\n", encoding="utf-8")
    decision = decide_reuse(entry, fingerprint_entry(entry, str(tmp_path)), repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert "modified input file: pyproject.toml" in decision["invalidated_by"]


def test_collect_cache_invalidates_when_dependency_file_changes(tmp_path):
    _write_test_file(tmp_path, "tests/test_a.py")
    requirements = _write_test_file(tmp_path, "requirements-dev.txt", "pytest==8.3.5\n")
    entry = _collect_entry(tmp_path)
    fingerprint = fingerprint_entry(entry, str(tmp_path))
    _write_collect_success(tmp_path, entry, fingerprint)

    requirements.write_text("pytest==8.3.6\n", encoding="utf-8")
    decision = decide_reuse(entry, fingerprint_entry(entry, str(tmp_path)), repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert "modified input file: requirements-dev.txt" in decision["invalidated_by"]


def test_collect_cache_invalidates_when_pytest_environment_changes(tmp_path, monkeypatch):
    _write_test_file(tmp_path, "tests/test_a.py")
    monkeypatch.setenv("PYTEST_ADDOPTS", "-q")
    entry = _collect_entry(tmp_path)
    fingerprint = fingerprint_entry(entry, str(tmp_path))
    _write_collect_success(tmp_path, entry, fingerprint)

    monkeypatch.setenv("PYTEST_ADDOPTS", "-q -k smoke")
    changed = fingerprint_entry(entry, str(tmp_path))
    decision = decide_reuse(entry, changed, repo_root=str(tmp_path))

    assert changed["hash"] != fingerprint["hash"]
    assert decision["decision"] == "run"
