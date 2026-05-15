from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools import long_gate_fingerprint as fingerprint_mod
from tools import quality_gate_shared
from tools.long_gate_cache import decide_reuse, evaluate_reuse, resolve_cache_dir, write_success
from tools.long_gate_fingerprint import (
    LongGateFingerprintError,
    diff_fingerprint_components,
    fingerprint_command,
    fingerprint_entry,
    fingerprint_files,
)
from tools.long_gate_manifest import build_manifest_from_quality_gate_plan
from tools.long_gate_schema import (
    LONG_GATE_CACHE_SCHEMA_VERSION,
    LONG_GATE_FINGERPRINT_SCHEMA_VERSION,
    long_gate_cache_metadata,
    stable_json_hash,
    version_hash_for_paths,
    version_untrusted_paths_for_paths,
)


def _entry(scopes=None):
    command = {
        "display": "python tools/example.py",
        "args": ["python", "tools/example.py"],
        "capture_output": True,
        "output_policy": "normalized",
    }
    return {
        "entry_id": "example_gate",
        "display": command["display"],
        "args": command["args"],
        "capture_output": command["capture_output"],
        "output_policy": command["output_policy"],
        "command_hash": fingerprint_command(command),
        "input_file_scopes": list(scopes or []),
        "config_file_scopes": [],
        "tool_file_scopes": [],
        "dependency_file_scopes": [],
        "env_keys": [],
        "output_result_files": [],
        "reuse_allowed": True,
    }


def _fingerprint(value="same"):
    payload = {
        "schema_version": 1,
        "components": {
            "files": {"files": []},
            "marker": value,
            "output_result_files": {"paths": [], "hash": stable_json_hash([])},
        },
    }
    payload["hash"] = f"sha256:{stable_json_hash(payload)}"
    return payload


def _output_file(repo_root: Path) -> Path:
    output = repo_root / "evidence" / "QualityGate" / "example_output.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('{"status":"passed"}', encoding="utf-8")
    return output


def _write_reusable_success(repo_root: Path, *, entry=None, fingerprint=None, cache_dir=None):
    used_entry = entry or _entry()
    used_fingerprint = fingerprint or _fingerprint()
    output = _output_file(repo_root)
    write_success(
        used_entry,
        used_fingerprint,
        {"stdout": "ok\n", "stderr": "", "returncode": 0, "duration_s": 1.25},
        [str(output)],
        repo_root=str(repo_root),
        cache_dir=cache_dir,
    )
    return used_entry, used_fingerprint, output


def _success_path(repo_root: Path, *, cache_dir: str = "evidence/QualityGate/long_gate") -> Path:
    return repo_root / cache_dir / "results" / "example_gate.success.json"


def _load_success(repo_root: Path, *, cache_dir: str = "evidence/QualityGate/long_gate") -> dict:
    return json.loads(_success_path(repo_root, cache_dir=cache_dir).read_text(encoding="utf-8"))


def _store_success(repo_root: Path, payload: dict, *, cache_dir: str = "evidence/QualityGate/long_gate") -> None:
    _success_path(repo_root, cache_dir=cache_dir).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _long_gate_entry(entry_id: str, repo_root: Path) -> dict:
    manifest = build_manifest_from_quality_gate_plan(
        quality_gate_shared.build_quality_gate_command_plan(),
        repo_root=str(repo_root),
    )
    for entry in manifest["entries"]:
        if entry["entry_id"] == entry_id:
            return entry
    raise AssertionError(f"missing entry_id: {entry_id}")


def test_fingerprint_files_is_stable_and_changes_for_file_add_modify_delete(tmp_path):
    first = tmp_path / "a.py"
    first.write_text("print('a')\n", encoding="utf-8")

    initial = fingerprint_files(["*.py"], str(tmp_path))
    repeated = fingerprint_files(["*.py"], str(tmp_path))
    assert repeated["content_hash"] == initial["content_hash"]

    first.write_text("print('changed')\n", encoding="utf-8")
    modified = fingerprint_files(["*.py"], str(tmp_path))
    assert modified["content_hash"] != initial["content_hash"]

    second = tmp_path / "b.py"
    second.write_text("print('b')\n", encoding="utf-8")
    added = fingerprint_files(["*.py"], str(tmp_path))
    assert added["paths_hash"] != modified["paths_hash"]

    first.unlink()
    deleted = fingerprint_files(["*.py"], str(tmp_path))
    assert deleted["paths_hash"] != added["paths_hash"]


def test_fingerprint_files_preserves_dotfile_paths(tmp_path):
    workflow = tmp_path / ".github" / "workflows" / "quality.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: quality\n", encoding="utf-8")

    fingerprint = fingerprint_files([".github/workflows/quality.yml"], str(tmp_path))

    assert fingerprint["files"][0]["path"] == ".github/workflows/quality.yml"
    assert fingerprint["files"][0]["exists"] is True


def test_fingerprint_files_includes_git_tracked_and_untracked_paths(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "review@example.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "review"], cwd=tmp_path, check=True)
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    tracked = tests_dir / "test_tracked.py"
    tracked.write_text("def test_tracked():\n    assert True\n", encoding="utf-8")
    subprocess.run(["git", "add", "tests/test_tracked.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    untracked = tests_dir / "test_untracked.py"
    untracked.write_text("def test_untracked():\n    assert True\n", encoding="utf-8")

    fingerprint = fingerprint_files(["tests/**/*.py"], str(tmp_path))
    rows = {row["path"]: row for row in fingerprint["files"]}

    assert fingerprint["git_source_status"] == "available"
    assert rows["tests/test_tracked.py"]["source"] == "tracked"
    assert rows["tests/test_untracked.py"]["source"] == "untracked"


def test_fingerprint_files_non_strict_marks_git_unavailable(tmp_path):
    source = tmp_path / "a.py"
    source.write_text("print('a')\n", encoding="utf-8")

    fingerprint = fingerprint_files(["*.py"], str(tmp_path))

    assert fingerprint["git_source_status"] in {"available", "unavailable"}
    assert fingerprint["files"][0]["path"] == "a.py"


def test_fingerprint_files_strict_rejects_git_unavailable(tmp_path):
    source = tmp_path / "a.py"
    source.write_text("print('a')\n", encoding="utf-8")

    with pytest.raises(LongGateFingerprintError, match="git command failed"):
        fingerprint_files(["*.py"], str(tmp_path), strict=True)


def test_fingerprint_entry_combines_command_files_and_environment(tmp_path, monkeypatch):
    source = tmp_path / "tools" / "example.py"
    source.parent.mkdir()
    source.write_text("print('ok')\n", encoding="utf-8")
    entry = _entry(["tools/example.py"])
    entry["env_keys"] = ["LONG_GATE_TEST_ENV"]
    monkeypatch.setenv("LONG_GATE_TEST_ENV", "one")

    first = fingerprint_entry(entry, str(tmp_path))
    second = fingerprint_entry(entry, str(tmp_path))
    assert first["hash"] == second["hash"]

    monkeypatch.setenv("LONG_GATE_TEST_ENV", "two")
    changed = fingerprint_entry(entry, str(tmp_path))
    assert changed["hash"] != first["hash"]


def test_fingerprint_entry_uses_env_overlay_for_command_and_environment(tmp_path, monkeypatch):
    source = tmp_path / "tools" / "example.py"
    source.parent.mkdir()
    source.write_text("print('ok')\n", encoding="utf-8")
    entry = _entry(["tools/example.py"])
    entry["env_keys"] = ["LONG_GATE_TEST_ENV"]
    entry["env_overlay"] = {"LONG_GATE_TEST_ENV": "overlay-one"}
    entry["command_hash"] = fingerprint_command(entry)
    monkeypatch.setenv("LONG_GATE_TEST_ENV", "outer-value")

    first = fingerprint_entry(entry, str(tmp_path))
    changed_entry = dict(entry)
    changed_entry["env_overlay"] = {"LONG_GATE_TEST_ENV": "overlay-two"}
    changed_entry["command_hash"] = fingerprint_command(changed_entry)
    changed = fingerprint_entry(changed_entry, str(tmp_path))

    assert first["components"]["environment"]["values"]["LONG_GATE_TEST_ENV"] == "overlay-one"
    assert changed["components"]["environment"]["values"]["LONG_GATE_TEST_ENV"] == "overlay-two"
    assert changed["components"]["command_hash"] != first["components"]["command_hash"]
    assert changed["hash"] != first["hash"]


def test_fingerprint_entry_uses_env_overlay_for_chrome_resolution(tmp_path, monkeypatch):
    entry = _entry([])
    entry["env_keys"] = ["APS_CHROME_PATH", "chrome_executable_resolution", "chrome_version"]
    entry["env_overlay"] = {"APS_CHROME_PATH": sys.executable}
    entry["command_hash"] = fingerprint_command(entry)
    monkeypatch.setenv("APS_CHROME_PATH", str(tmp_path / "missing-outer-chrome"))

    fingerprint = fingerprint_entry(entry, str(tmp_path))
    values = fingerprint["components"]["environment"]["values"]

    assert values["APS_CHROME_PATH"] == sys.executable
    assert values["chrome_executable_resolution"] == os.path.realpath(sys.executable)
    assert values["chrome_version"]
    assert "missing-outer-chrome" not in values["chrome_executable_resolution"]


def test_fingerprint_entry_uses_env_overlay_path_for_node(tmp_path, monkeypatch):
    node = tmp_path / ("node.cmd" if os.name == "nt" else "node")
    if os.name == "nt":
        node.write_text(
            "@echo off\r\n"
            "if \"%1\"==\"--version\" echo v99.0.0-overlay& exit /b 0\r\n"
            "if \"%1\"==\"-e\" echo capability-overlay& exit /b 0\r\n"
            "exit /b 2\r\n",
            encoding="utf-8",
        )
    else:
        node.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = \"--version\" ]; then echo v99.0.0-overlay; exit 0; fi\n"
            "if [ \"$1\" = \"-e\" ]; then echo capability-overlay; exit 0; fi\n"
            "exit 2\n",
            encoding="utf-8",
        )
        node.chmod(0o755)
    entry = _entry([])
    entry["env_keys"] = ["PATH", "node_executable_realpath", "node_version", "node_browser_runtime_capability"]
    entry["env_overlay"] = {"PATH": str(tmp_path)}
    entry["command_hash"] = fingerprint_command(entry)

    fingerprint = fingerprint_entry(entry, str(tmp_path))
    values = fingerprint["components"]["environment"]["values"]

    assert values["PATH"] == str(tmp_path)
    assert values["node_executable_realpath"] == os.path.realpath(str(node))
    assert values["node_version"] == "v99.0.0-overlay"
    assert str(values["node_browser_runtime_capability"]).startswith("passed:")


def test_fingerprint_entry_keeps_entry_specific_file_scopes_independent(tmp_path):
    config_file = tmp_path / "web" / "routes" / "domains" / "scheduler" / "scheduler_config.py"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("CONFIG_MARKER = 1\n", encoding="utf-8")
    config_entry = _entry(["web/routes/domains/scheduler/scheduler_config*.py"])
    analysis_entry = _entry(["web/routes/domains/scheduler/scheduler_analysis.py"])

    before_config = fingerprint_entry(config_entry, str(tmp_path))
    before_analysis = fingerprint_entry(analysis_entry, str(tmp_path))
    config_file.write_text("CONFIG_MARKER = 2\n", encoding="utf-8")
    after_config = fingerprint_entry(config_entry, str(tmp_path))
    after_analysis = fingerprint_entry(analysis_entry, str(tmp_path))

    assert after_config["hash"] != before_config["hash"]
    assert after_analysis["hash"] == before_analysis["hash"]


def test_fingerprint_entry_changes_when_runtime_facts_change(tmp_path, monkeypatch):
    source = tmp_path / "tools" / "example.py"
    source.parent.mkdir()
    source.write_text("print('ok')\n", encoding="utf-8")
    entry = _entry(["tools/example.py"])
    entry["env_keys"] = ["python_executable_realpath", "python_version", "pytest_version"]

    first = fingerprint_entry(entry, str(tmp_path))
    monkeypatch.setattr("tools.long_gate_fingerprint._pytest_version", lambda *args, **kwargs: "pytest-next")
    changed = fingerprint_entry(entry, str(tmp_path))

    assert changed["hash"] != first["hash"]


def test_fingerprint_chrome_explicit_bad_path_does_not_fallback(tmp_path, monkeypatch):
    fallback = tmp_path / "google-chrome"
    fallback.write_text("fallback\n", encoding="utf-8")
    monkeypatch.setenv("APS_CHROME_PATH", str(tmp_path / "missing-chrome"))
    monkeypatch.setattr(fingerprint_mod.shutil, "which", lambda _name: str(fallback))
    entry = _entry()
    entry["env_keys"] = ["chrome_executable_resolution"]

    fingerprint = fingerprint_entry(entry, str(tmp_path))

    assert fingerprint["components"]["environment"]["values"]["chrome_executable_resolution"].startswith(
        "__bad_aps_chrome_path__"
    )
    with pytest.raises(LongGateFingerprintError, match="APS_CHROME_PATH does not exist"):
        fingerprint_mod._chrome_executable_resolution(strict=True)


def test_fingerprint_chrome_version_changes_hash(tmp_path, monkeypatch):
    source = tmp_path / "tools" / "example.py"
    source.parent.mkdir()
    source.write_text("print('ok')\n", encoding="utf-8")
    entry = _entry(["tools/example.py"])
    entry["env_keys"] = ["chrome_version"]
    monkeypatch.setattr(fingerprint_mod, "_chrome_version", lambda strict=False, environment=None: "Chrome 1")

    first = fingerprint_entry(entry, str(tmp_path))
    monkeypatch.setattr(fingerprint_mod, "_chrome_version", lambda strict=False, environment=None: "Chrome 2")
    changed = fingerprint_entry(entry, str(tmp_path))

    assert changed["hash"] != first["hash"]


def test_fingerprint_chrome_executable_identity_tracks_file_change(tmp_path, monkeypatch):
    chrome = tmp_path / "fake-chrome"
    chrome.write_text("one\n", encoding="utf-8")
    monkeypatch.setenv("APS_CHROME_PATH", str(chrome))
    entry = _entry()
    entry["env_keys"] = ["chrome_executable_identity"]

    first = fingerprint_entry(entry, str(tmp_path))
    chrome.write_text("one plus more bytes\n", encoding="utf-8")
    changed = fingerprint_entry(entry, str(tmp_path))

    assert changed["hash"] != first["hash"]


def test_fingerprint_entry_changes_when_output_result_files_change(tmp_path):
    entry = _entry()

    first = fingerprint_entry(entry, str(tmp_path))
    changed_entry = dict(entry)
    changed_entry["output_result_files"] = ["evidence/QualityGate/collect_nodeids.json"]
    changed = fingerprint_entry(changed_entry, str(tmp_path))

    assert changed["hash"] != first["hash"]


@pytest.mark.parametrize(
    "changed_path",
    [
        "app.py",
        "core/services/example.py",
        "data/repositories/example.py",
        "desktop/gantt/example.py",
        "web/routes/example.py",
        "plugins/example.py",
        "scripts/example.py",
        "tools/example.py",
        "tests/test_example.py",
        "codestable/tools/example.py",
        "audit/example.py",
        "pyproject.toml",
        "ruff.toml",
        ".ruff.toml",
        "setup.cfg",
        ".pre-commit-config.yaml",
        ".gitignore",
        "requirements-dev.txt",
        "requirements.txt",
    ],
)
def test_ruff_check_full_fingerprint_tracks_python_config_and_dependencies(tmp_path, changed_path):
    entry = _long_gate_entry("ruff_check_full", tmp_path)

    before = fingerprint_entry(entry, str(tmp_path))
    path = tmp_path / changed_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("MARKER = 1\n", encoding="utf-8")
    after = fingerprint_entry(entry, str(tmp_path))

    assert after["hash"] != before["hash"]


def test_ruff_check_full_fingerprint_tracks_ruff_version(tmp_path, monkeypatch):
    entry = _long_gate_entry("ruff_check_full", tmp_path)
    monkeypatch.setattr(fingerprint_mod, "_distribution_version", lambda distribution, strict=False: "ruff-1")
    before = fingerprint_entry(entry, str(tmp_path))

    monkeypatch.setattr(fingerprint_mod, "_distribution_version", lambda distribution, strict=False: "ruff-2")
    after = fingerprint_entry(entry, str(tmp_path))

    assert before["components"]["environment"]["values"]["ruff_version"] == "ruff-1"
    assert after["components"]["environment"]["values"]["ruff_version"] == "ruff-2"
    assert after["hash"] != before["hash"]


def test_ruff_check_full_fingerprint_tracks_declared_output_path(tmp_path):
    entry = _long_gate_entry("ruff_check_full", tmp_path)
    before = fingerprint_entry(entry, str(tmp_path))
    changed_entry = dict(entry)
    changed_entry["output_result_files"] = ["evidence/QualityGate/ruff_check_full_v2.json"]

    after = fingerprint_entry(changed_entry, str(tmp_path))

    assert after["hash"] != before["hash"]


@pytest.mark.parametrize(
    "changed_path",
    [
        "app.py",
        "app.pyi",
        "app_new_ui.py",
        "app_new_ui.pyi",
        "config.py",
        "config.pyi",
        "core/services/example.py",
        "data/repositories/example.py",
        "web/routes/example.py",
        "core/services/example.pyi",
        "data/repositories/example.pyi",
        "web/routes/example.pyi",
        "typings/example.pyi",
        "py.typed",
        "core/py.typed",
        "pyrightconfig.gate.json",
        "pyrightconfig.json",
        "pyproject.toml",
        "setup.cfg",
        "requirements-dev.txt",
        "requirements.txt",
    ],
)
def test_pyright_gate_full_fingerprint_tracks_gate_inputs_config_and_dependencies(tmp_path, changed_path):
    entry = _long_gate_entry("pyright_gate_full", tmp_path)

    before = fingerprint_entry(entry, str(tmp_path))
    path = tmp_path / changed_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("MARKER = 1\n", encoding="utf-8")
    after = fingerprint_entry(entry, str(tmp_path))

    assert after["hash"] != before["hash"]


def test_pyright_gate_full_fingerprint_follows_gate_config_include(tmp_path):
    config = tmp_path / "pyrightconfig.gate.json"
    config.write_text(
        json.dumps({"include": ["service"], "pythonVersion": "3.8"}, ensure_ascii=False),
        encoding="utf-8",
    )
    entry = _long_gate_entry("pyright_gate_full", tmp_path)

    assert "service/**/*.py" in entry["input_file_scopes"]
    assert "service/**/*.pyi" in entry["input_file_scopes"]
    before = fingerprint_entry(entry, str(tmp_path))
    service_file = tmp_path / "service" / "example.py"
    service_file.parent.mkdir(parents=True)
    service_file.write_text("VALUE = 1\n", encoding="utf-8")
    after = fingerprint_entry(entry, str(tmp_path))

    assert after["hash"] != before["hash"]


@pytest.mark.parametrize("env_key", ["PYTHONPATH", "PYTHONUTF8", "PYTHONIOENCODING"])
def test_pyright_gate_full_fingerprint_tracks_environment(tmp_path, monkeypatch, env_key):
    entry = _long_gate_entry("pyright_gate_full", tmp_path)
    monkeypatch.setenv(env_key, "before")
    before = fingerprint_entry(entry, str(tmp_path))

    monkeypatch.setenv(env_key, "after")
    after = fingerprint_entry(entry, str(tmp_path))

    assert after["hash"] != before["hash"]


def test_pyright_gate_full_fingerprint_tracks_pyright_version(tmp_path, monkeypatch):
    entry = _long_gate_entry("pyright_gate_full", tmp_path)
    monkeypatch.setattr(fingerprint_mod, "_distribution_version", lambda distribution, strict=False: "pyright-1")
    before = fingerprint_entry(entry, str(tmp_path))

    monkeypatch.setattr(fingerprint_mod, "_distribution_version", lambda distribution, strict=False: "pyright-2")
    after = fingerprint_entry(entry, str(tmp_path))

    assert before["components"]["environment"]["values"]["pyright_version"] == "pyright-1"
    assert after["components"]["environment"]["values"]["pyright_version"] == "pyright-2"
    assert after["hash"] != before["hash"]


def test_pyright_gate_full_fingerprint_tracks_declared_output_path(tmp_path):
    entry = _long_gate_entry("pyright_gate_full", tmp_path)
    before = fingerprint_entry(entry, str(tmp_path))
    changed_entry = dict(entry)
    changed_entry["output_result_files"] = ["evidence/QualityGate/pyright_gate_full_v2.json"]

    after = fingerprint_entry(changed_entry, str(tmp_path))

    assert after["hash"] != before["hash"]


@pytest.mark.parametrize(
    "changed_path",
    [
        "scripts/run_quality_gate.py",
        "tools/long_gate_manifest.py",
        "tests/conftest.py",
        "tools/__init__.py",
        "tools/full_test_debt_shards.py",
        "web/bootstrap/launcher.py",
        "core/infrastructure/logging.py",
        "core/infrastructure/transaction.py",
        "typings/tools.pyi",
        "py.typed",
        "pyrightconfig.tools.json",
        "pyrightconfig.gate.json",
        "pyrightconfig.json",
        "pyproject.toml",
        "setup.cfg",
        "requirements-dev.txt",
        "requirements.txt",
    ],
)
def test_pyright_tools_full_fingerprint_tracks_tools_inputs_config_and_dependencies(tmp_path, changed_path):
    entry = _long_gate_entry("pyright_tools_full", tmp_path)

    before = fingerprint_entry(entry, str(tmp_path))
    path = tmp_path / changed_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("MARKER = 1\n", encoding="utf-8")
    after = fingerprint_entry(entry, str(tmp_path))

    assert after["hash"] != before["hash"]


@pytest.mark.parametrize("env_key", ["PYTHONPATH", "PYTHONUTF8", "PYTHONIOENCODING"])
def test_pyright_tools_full_fingerprint_tracks_environment(tmp_path, monkeypatch, env_key):
    entry = _long_gate_entry("pyright_tools_full", tmp_path)
    monkeypatch.setenv(env_key, "before")
    before = fingerprint_entry(entry, str(tmp_path))

    monkeypatch.setenv(env_key, "after")
    after = fingerprint_entry(entry, str(tmp_path))

    assert after["hash"] != before["hash"]

def test_pyright_tools_full_fingerprint_tracks_pyright_version(tmp_path, monkeypatch):
    entry = _long_gate_entry("pyright_tools_full", tmp_path)
    monkeypatch.setattr(fingerprint_mod, "_distribution_version", lambda distribution, strict=False: "pyright-1")
    before = fingerprint_entry(entry, str(tmp_path))

    monkeypatch.setattr(fingerprint_mod, "_distribution_version", lambda distribution, strict=False: "pyright-2")
    after = fingerprint_entry(entry, str(tmp_path))

    assert before["components"]["environment"]["values"]["pyright_version"] == "pyright-1"
    assert after["components"]["environment"]["values"]["pyright_version"] == "pyright-2"
    assert after["hash"] != before["hash"]


def test_pyright_tools_full_fingerprint_tracks_declared_output_path(tmp_path):
    entry = _long_gate_entry("pyright_tools_full", tmp_path)
    before = fingerprint_entry(entry, str(tmp_path))
    changed_entry = dict(entry)
    changed_entry["output_result_files"] = ["evidence/QualityGate/pyright_tools_full_v2.json"]

    after = fingerprint_entry(changed_entry, str(tmp_path))

    assert after["hash"] != before["hash"]


def test_fingerprint_files_marks_outside_repo_scope_without_reading_it(tmp_path):
    outside = tmp_path.parent / "outside-long-gate-source.py"
    outside.write_text("SECRET = 1\n", encoding="utf-8")

    fingerprint = fingerprint_files([str(outside)], str(tmp_path))

    assert fingerprint["files"][0]["kind"] == "outside_repo"
    assert fingerprint["files"][0]["exists"] is False
    assert fingerprint["files"][0]["sha256"] == ""


def test_outside_repo_scope_is_not_reused(tmp_path):
    outside = tmp_path.parent / "outside-long-gate-source.py"
    outside.write_text("SECRET = 1\n", encoding="utf-8")
    entry = _entry([str(outside)])
    fingerprint = fingerprint_entry(entry, str(tmp_path))
    output = _output_file(tmp_path)
    write_success(
        entry,
        fingerprint,
        {"stdout": "ok\n", "stderr": "", "returncode": 0},
        [str(output)],
        repo_root=str(tmp_path),
    )

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "input fingerprint contains untrusted path"
    assert decision["invalidated_by"] == [f"input path is outside repo: {outside}"]


def test_fingerprint_files_marks_outside_repo_glob_without_reusing_cache(tmp_path):
    outside_dir = tmp_path.parent / f"{tmp_path.name}-outside-glob"
    outside_dir.mkdir()
    outside = outside_dir / "outside-long-gate-source.py"
    outside.write_text("SECRET = 1\n", encoding="utf-8")
    entry = _entry([str(outside_dir / "*.py")])
    fingerprint = fingerprint_entry(entry, str(tmp_path))
    output = _output_file(tmp_path)
    write_success(
        entry,
        fingerprint,
        {"stdout": "ok\n", "stderr": "", "returncode": 0},
        [str(output)],
        repo_root=str(tmp_path),
    )

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    file_kinds = {row["kind"] for row in fingerprint["components"]["files"]["files"]}
    assert "outside_repo" in file_kinds
    assert decision["decision"] == "run"
    assert decision["reason"] == "input fingerprint contains untrusted path"


def test_tooling_symlink_to_outside_repo_does_not_read_target_content_and_is_not_reused(tmp_path, monkeypatch):
    if not hasattr(os, "symlink"):
        pytest.skip("symlink is not available on this platform")
    outside = tmp_path.parent / "outside-long-gate-tool.py"
    outside.write_text("VERSION = 1\n", encoding="utf-8")
    try:
        os.symlink(outside, tmp_path / "tool.py")
    except OSError as exc:
        pytest.skip(f"symlink is unavailable: {exc}")

    first = version_hash_for_paths(str(tmp_path), ["tool.py"])
    outside.write_text("VERSION = 2\n", encoding="utf-8")
    second = version_hash_for_paths(str(tmp_path), ["tool.py"])
    monkeypatch.setattr("tools.long_gate_schema.LONG_GATE_TOOLING_VERSION_PATHS", ("tool.py",))
    entry, fingerprint, _output = _write_reusable_success(tmp_path)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert second == first
    assert version_untrusted_paths_for_paths(str(tmp_path), ["tool.py"]) == ["tool.py"]
    assert decision["decision"] == "run"
    assert decision["reason"] == "tooling version contains untrusted path"
    assert decision["invalidated_by"] == ["tool.py"]


def test_decide_reuse_when_previous_success_matches(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "reuse"
    assert decision["reason"] == "fingerprint matched previous successful result"


def test_evaluate_reuse_returns_verified_log_texts(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)

    evaluation = evaluate_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert evaluation["decision"]["decision"] == "reuse"
    assert evaluation["stdout"] == "ok\n"
    assert evaluation["stderr"] == ""
    assert isinstance(evaluation["validated_success"], dict)


def test_evaluate_reuse_does_not_return_payload_when_log_hash_mismatches(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    (tmp_path / payload["stdout_log_path"]).write_text("tampered\n", encoding="utf-8")

    evaluation = evaluate_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert evaluation["decision"]["decision"] == "run"
    assert evaluation["decision"]["reason"] == "previous logs missing or hash mismatch"
    assert evaluation["validated_success"] is None
    assert evaluation["stdout"] == ""


def test_reuse_disabled_entry_is_not_reused_even_when_cache_matches(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    disabled_entry = dict(entry)
    disabled_entry["reuse_allowed"] = False

    decision = decide_reuse(disabled_entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "reuse is disabled for this entry"


def test_previous_failure_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    payload["status"] = "failed"
    _store_success(tmp_path, payload)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "previous result was not successful"


def test_timeout_interrupt_and_partial_write_are_not_reused(tmp_path):
    for field_name, expected_reason in [
        ("timed_out", "previous result timed out"),
        ("interrupted", "previous result was interrupted"),
        ("partial_write", "previous result was partially written"),
    ]:
        entry, fingerprint, _output = _write_reusable_success(tmp_path)
        payload = _load_success(tmp_path)
        payload[field_name] = True
        _store_success(tmp_path, payload)

        decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

        assert decision["decision"] == "run"
        assert decision["reason"] == expected_reason
        _success_path(tmp_path).unlink()


def test_corrupt_cache_json_is_not_reused(tmp_path):
    entry = _entry()
    path = _success_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{bad json", encoding="utf-8")

    decision = decide_reuse(entry, _fingerprint(), repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert "cache unreadable/corrupt" in decision["reason"]


def test_success_cache_top_level_json_array_is_not_reused(tmp_path):
    entry = _entry()
    path = _success_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("[]", encoding="utf-8")

    decision = decide_reuse(entry, _fingerprint(), repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert "top-level value is not an object" in decision["reason"]


def test_non_utf8_cache_json_is_not_reused(tmp_path):
    entry = _entry()
    path = _success_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xff\xfe\x00")

    decision = decide_reuse(entry, _fingerprint(), repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert "cache unreadable/corrupt" in decision["reason"]


def test_cache_missing_required_field_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    payload.pop("fingerprint_hash")
    _store_success(tmp_path, payload)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "cache unreadable/corrupt/missing required field: fingerprint_hash"


def test_missing_cache_schema_version_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    payload.pop("cache_schema_version")
    _store_success(tmp_path, payload)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "cache unreadable/corrupt/missing required field: cache_schema_version"


def test_missing_integrity_field_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    payload.pop("timed_out")
    _store_success(tmp_path, payload)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "cache unreadable/corrupt/missing required field: timed_out"


def test_invalid_numeric_fields_are_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    payload["schema_version"] = "bad"
    _store_success(tmp_path, payload)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert "cache unreadable/corrupt" in decision["reason"]


@pytest.mark.parametrize("field", ["schema_version", "cache_schema_version", "fingerprint_schema_version", "returncode"])
def test_bool_numeric_fields_are_not_reused(tmp_path, field):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    payload[field] = False
    _store_success(tmp_path, payload)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "cache unreadable/corrupt: numeric field has invalid type"


def test_bad_duration_s_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    payload["duration_s"] = "bad"
    _store_success(tmp_path, payload)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "cache unreadable/corrupt: numeric field has invalid type"


def test_missing_stdout_log_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    (tmp_path / payload["stdout_log_path"]).unlink()

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "previous logs missing or hash mismatch"


def test_stdout_log_hash_mismatch_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    (tmp_path / payload["stdout_log_path"]).write_text("changed\n", encoding="utf-8")

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "previous logs missing or hash mismatch"


def test_stderr_log_hash_mismatch_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    (tmp_path / payload["stderr_log_path"]).write_text("changed stderr\n", encoding="utf-8")

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "previous logs missing or hash mismatch"


def test_non_utf8_success_log_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    stderr_path = tmp_path / payload["stderr_log_path"]
    stderr_path.write_bytes(b"\xff")
    payload["stderr_sha256"] = hashlib.sha256(b"\xff").hexdigest()
    _store_success(tmp_path, payload)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert "previous logs unreadable as utf-8" in decision["reason"]


def test_custom_cache_dir_rejects_success_logs_from_other_cache_dir(tmp_path):
    cache_dir = "evidence/QualityGate/long_gate/manual"
    entry, fingerprint, _output = _write_reusable_success(tmp_path, cache_dir=cache_dir)
    payload = _load_success(tmp_path, cache_dir=cache_dir)
    default_stdout = tmp_path / "evidence" / "QualityGate" / "long_gate" / "logs" / "example_gate.stdout.log"
    default_stdout.parent.mkdir(parents=True, exist_ok=True)
    default_stdout.write_text("ok\n", encoding="utf-8")
    payload["stdout_log_path"] = "evidence/QualityGate/long_gate/logs/example_gate.stdout.log"
    _store_success(tmp_path, payload, cache_dir=cache_dir)

    evaluation = evaluate_reuse(entry, fingerprint, repo_root=str(tmp_path), cache_dir=cache_dir)

    assert evaluation["decision"]["decision"] == "run"
    assert "outside current cache logs dir" in evaluation["decision"]["reason"]
    assert evaluation["validated_success"] is None


def test_symlink_repo_root_keeps_cache_paths_repo_relative(tmp_path):
    real_repo = tmp_path / "real-repo"
    link_repo = tmp_path / "link-repo"
    real_repo.mkdir()
    try:
        os.symlink(real_repo, link_repo, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink is unavailable: {exc}")
    cache_dir = "evidence/QualityGate/long_gate/manual"

    assert resolve_cache_dir(str(link_repo), cache_dir) == cache_dir
    _write_reusable_success(link_repo, cache_dir=cache_dir)

    payload = json.loads(
        (real_repo / cache_dir / "results" / "example_gate.success.json").read_text(encoding="utf-8")
    )
    assert payload["stdout_log_path"] == f"{cache_dir}/logs/example_gate.stdout.log"
    assert payload["stderr_log_path"] == f"{cache_dir}/logs/example_gate.stderr.log"


def test_symlink_to_outside_repo_does_not_hash_target_content(tmp_path):
    if not hasattr(os, "symlink"):
        pytest.skip("symlink is not available on this platform")
    outside = tmp_path.parent / "outside-long-gate-target.txt"
    outside.write_text("secret one\n", encoding="utf-8")
    link_path = tmp_path / "linked.txt"
    try:
        os.symlink(outside, link_path)
    except OSError as exc:
        pytest.skip(f"symlink is unavailable: {exc}")

    first = fingerprint_files(["linked.txt"], str(tmp_path))
    outside.write_text("secret two\n", encoding="utf-8")
    second = fingerprint_files(["linked.txt"], str(tmp_path))

    assert first["files"][0]["kind"] == "symlink_outside_repo"
    assert first["files"][0]["sha256"] == second["files"][0]["sha256"]
    assert first["content_hash"] == second["content_hash"]


def test_symlink_to_outside_repo_is_not_reused(tmp_path):
    if not hasattr(os, "symlink"):
        pytest.skip("symlink is not available on this platform")
    outside = tmp_path.parent / "outside-long-gate-source.py"
    outside.write_text("SECRET = 1\n", encoding="utf-8")
    try:
        os.symlink(outside, tmp_path / "linked.py")
    except OSError as exc:
        pytest.skip(f"symlink is unavailable: {exc}")
    entry = _entry(["linked.py"])
    fingerprint = fingerprint_entry(entry, str(tmp_path))
    output = _output_file(tmp_path)
    write_success(
        entry,
        fingerprint,
        {"stdout": "ok\n", "stderr": "", "returncode": 0},
        [str(output)],
        repo_root=str(tmp_path),
    )

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "input fingerprint contains untrusted path"
    assert decision["invalidated_by"] == ["input symlink points outside repo: linked.py"]


def test_missing_output_file_is_not_reused(tmp_path):
    entry, fingerprint, output = _write_reusable_success(tmp_path)
    output.unlink()

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "previous output files missing or hash mismatch"


def test_output_file_hash_mismatch_is_not_reused(tmp_path):
    entry, fingerprint, output = _write_reusable_success(tmp_path)
    output.write_text('{"status":"changed"}', encoding="utf-8")

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "previous output files missing or hash mismatch"


def test_missing_declared_output_file_in_cache_is_not_reused(tmp_path):
    entry, _fingerprint_before, _output = _write_reusable_success(tmp_path)
    entry = dict(entry)
    entry["output_result_files"] = ["evidence/QualityGate/example_output.json"]
    fingerprint = fingerprint_entry(entry, str(tmp_path))
    payload = _load_success(tmp_path)
    payload["fingerprint_hash"] = fingerprint["hash"]
    payload["fingerprint"] = fingerprint
    payload["output_files"] = []
    _store_success(tmp_path, payload)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "previous output files missing required path: evidence/QualityGate/example_output.json"


def test_cache_path_escape_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    outside = tmp_path.parent / "outside-long-gate.log"
    outside.write_text("ok\n", encoding="utf-8")
    payload["stdout_log_path"] = "../outside-long-gate.log"
    _store_success(tmp_path, payload)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert "cache path escapes repo root" in decision["reason"]


def test_absolute_inside_repo_output_path_is_normalized_and_absolute_outside_is_rejected(tmp_path):
    entry = _entry()
    output = _output_file(tmp_path)

    write_success(
        entry,
        _fingerprint(),
        {"stdout": "ok", "stderr": "", "returncode": 0},
        [str(output.resolve())],
        repo_root=str(tmp_path),
    )

    payload = _load_success(tmp_path)
    assert payload["output_files"][0]["path"] == "evidence/QualityGate/example_output.json"

    outside = tmp_path.parent / "outside-long-gate-output.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="cache path escapes repo root"):
        write_success(
            entry,
            _fingerprint(),
            {"stdout": "ok", "stderr": "", "returncode": 0},
            [str(outside.resolve())],
            repo_root=str(tmp_path),
        )


def test_entry_id_mismatch_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    payload["entry_id"] = "other_gate"
    _store_success(tmp_path, payload)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "cache entry_id changed"


def test_command_args_change_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    changed_entry = dict(entry)
    changed_entry["args"] = ["python", "tools/changed.py"]
    changed_entry["command_hash"] = fingerprint_command(changed_entry)

    decision = decide_reuse(changed_entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "command identity changed"


def test_schema_version_change_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    payload["schema_version"] = LONG_GATE_CACHE_SCHEMA_VERSION + 1
    _store_success(tmp_path, payload)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "cache schema changed"


def test_cache_schema_version_change_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    payload["cache_schema_version"] = LONG_GATE_CACHE_SCHEMA_VERSION + 1
    _store_success(tmp_path, payload)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "cache schema changed"


def test_fingerprint_schema_change_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    changed = dict(fingerprint)
    changed["schema_version"] = 2

    decision = decide_reuse(entry, changed, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["invalidated_by"] == ["fingerprint schema changed"]


def test_cached_fingerprint_schema_version_change_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    payload["fingerprint_schema_version"] = LONG_GATE_FINGERPRINT_SCHEMA_VERSION + 1
    _store_success(tmp_path, payload)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["invalidated_by"] == ["fingerprint schema changed"]


def test_cache_fingerprint_hash_mismatch_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    payload["fingerprint"]["hash"] = "sha256:bad"
    _store_success(tmp_path, payload)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "cache unreadable/corrupt: fingerprint hash mismatch"


def test_cached_fingerprint_with_bad_shape_is_not_reused(tmp_path):
    entry, _fingerprint_before, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    bad_fingerprint = {
        "schema_version": LONG_GATE_FINGERPRINT_SCHEMA_VERSION,
        "components": {
            "files": {"files": "not-a-list"},
            "output_result_files": {"paths": [], "hash": stable_json_hash([])},
        },
    }
    bad_fingerprint["hash"] = f"sha256:{stable_json_hash(bad_fingerprint)}"
    payload["fingerprint"] = bad_fingerprint
    payload["fingerprint_hash"] = bad_fingerprint["hash"]
    _store_success(tmp_path, payload)

    decision = decide_reuse(entry, bad_fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "cache unreadable/corrupt: fingerprint files must be a list"


def test_runner_version_hash_change_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    payload["runner_version_hash"] = "sha256:old"
    _store_success(tmp_path, payload)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "runner version changed"


def test_tooling_version_hash_change_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    payload["tooling_version_hash"] = "sha256:old"
    _store_success(tmp_path, payload)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "tooling version changed"


def test_repo_identity_mismatch_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    payload["repo_root_realpath"] = str(tmp_path / "other-checkout")
    _store_success(tmp_path, payload)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "repo identity changed"


def test_write_success_records_common_safety_fields(tmp_path):
    _entry_used, _fingerprint_used, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    expected = long_gate_cache_metadata(str(tmp_path))

    for field in (
        "cache_schema_version",
        "fingerprint_schema_version",
        "runner_version_hash",
        "tooling_version_hash",
        "runner_version_untrusted_paths",
        "tooling_version_untrusted_paths",
        "cache_dir",
        "repo_root_realpath",
        "git_common_dir_realpath",
    ):
        assert payload[field] == expected[field]


def test_write_success_rejects_missing_output_file(tmp_path):
    entry = _entry()
    missing = tmp_path / "missing.json"

    with pytest.raises(ValueError, match="long gate output file does not exist"):
        write_success(
            entry,
            _fingerprint(),
            {"stdout": "ok", "stderr": "", "returncode": 0},
            [str(missing)],
            repo_root=str(tmp_path),
        )


def test_write_success_rejects_nonzero_returncode(tmp_path):
    entry = _entry()
    output = _output_file(tmp_path)

    with pytest.raises(ValueError, match="requires returncode == 0"):
        write_success(
            entry,
            _fingerprint(),
            {"stdout": "bad", "stderr": "", "returncode": 1},
            [str(output)],
            repo_root=str(tmp_path),
        )


@pytest.mark.parametrize(
    "fingerprint, error",
    [
        ({}, "requires fingerprint hash"),
        ({"hash": ""}, "requires fingerprint hash"),
        ({"hash": "not-prefixed", "schema_version": 1, "components": {}}, "requires sha256 fingerprint hash"),
        ({"hash": "sha256:test", "components": {}}, "requires fingerprint schema_version"),
        ({"hash": "sha256:test", "schema_version": 1}, "requires fingerprint components"),
    ],
)
def test_write_success_rejects_missing_or_invalid_fingerprint(tmp_path, fingerprint, error):
    entry = _entry()
    output = _output_file(tmp_path)

    with pytest.raises(ValueError, match=error):
        write_success(
            entry,
            fingerprint,
            {"stdout": "ok", "stderr": "", "returncode": 0},
            [str(output)],
            repo_root=str(tmp_path),
        )
    assert not _success_path(tmp_path).exists()


@pytest.mark.parametrize(
    "command_result, error",
    [
        ({"stdout": "ok", "stderr": "", "returncode": False}, "requires numeric returncode"),
        ({"stdout": "ok", "stderr": "", "returncode": 0, "duration_s": False}, "requires numeric duration_s"),
        ({"stdout": "ok", "stderr": "", "returncode": 0, "duration_s": "bad"}, "requires numeric duration_s"),
    ],
)
def test_write_success_rejects_bool_or_bad_numeric_fields(tmp_path, command_result, error):
    entry = _entry()
    output = _output_file(tmp_path)

    with pytest.raises(ValueError, match=error):
        write_success(
            entry,
            _fingerprint(),
            command_result,
            [str(output)],
            repo_root=str(tmp_path),
        )


@pytest.mark.parametrize("field", ["timed_out", "interrupted", "partial_write"])
def test_write_success_rejects_unclean_success_flags(tmp_path, field):
    entry = _entry()
    output = _output_file(tmp_path)
    command_result = {"stdout": "ok", "stderr": "", "returncode": 0, field: True}

    with pytest.raises(ValueError, match=f"requires {field} == False"):
        write_success(
            entry,
            _fingerprint(),
            command_result,
            [str(output)],
            repo_root=str(tmp_path),
        )


def test_write_success_requires_declared_output_file(tmp_path):
    entry = _entry()
    entry["output_result_files"] = ["evidence/QualityGate/example_output.json"]
    other = tmp_path / "evidence" / "QualityGate" / "other_output.json"
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="long gate output file was not provided"):
        write_success(
            entry,
            _fingerprint(),
            {"stdout": "ok", "stderr": "", "returncode": 0},
            [str(other)],
            repo_root=str(tmp_path),
        )


def test_fingerprint_change_reports_invalidated_files(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    changed = {
        "schema_version": 1,
        "hash": "changed",
        "components": {
            "files": {
                "files": [
                    {
                        "path": "tests/test_new.py",
                        "exists": True,
                        "kind": "file",
                        "sha256": "abc",
                    }
                ]
            }
        },
    }

    decision = decide_reuse(entry, changed, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "input fingerprint changed"
    assert "added input file: tests/test_new.py" in decision["invalidated_by"]
    assert decision["fingerprint_diff"][0]["component"] == "files"
    assert decision["fingerprint_diff"][0]["path"] == "tests/test_new.py"


def test_fingerprint_component_diff_explains_non_file_changes():
    previous = {
        "schema_version": 1,
        "hash": "old",
        "components": {
            "command_hash": "old-command",
            "files": {"files": []},
            "environment": {"values": {"PYTHONUTF8": "1"}, "hash": "old-env"},
            "collect_nodeids": {"nodeid_hash": "old-nodeids", "nodeid_count": 1},
            "output_result_files": {"paths": ["old.json"], "hash": "old-outputs"},
        },
    }
    current = {
        "schema_version": 1,
        "hash": "new",
        "components": {
            "command_hash": "new-command",
            "files": {"files": []},
            "environment": {"values": {"PYTHONUTF8": None}, "hash": "new-env"},
            "collect_nodeids": {"nodeid_hash": "new-nodeids", "nodeid_count": 2},
            "output_result_files": {"paths": ["old.json", "new.json"], "hash": "new-outputs"},
        },
    }

    diff = diff_fingerprint_components(previous, current)
    changes = list(diff["components"])

    assert diff["changed"] is True
    assert {"component": "command_hash", "reason": "command hash changed", "previous": "old-command", "current": "new-command"} in changes
    assert any(
        change.get("component") == "environment"
        and change.get("key") == "PYTHONUTF8"
        and change.get("previous") == "1"
        and change.get("current") is None
        for change in changes
    )
    assert any(
        change.get("component") == "collect_nodeids"
        and change.get("field") == "nodeid_hash"
        and change.get("previous") == "old-nodeids"
        and change.get("current") == "new-nodeids"
        for change in changes
    )
    assert any(
        change.get("component") == "output_result_files"
        and change.get("reason") == "added output result file"
        and change.get("path") == "new.json"
        for change in changes
    )
