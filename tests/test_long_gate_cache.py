from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tools.long_gate_cache import decide_reuse, evaluate_reuse, write_success
from tools.long_gate_fingerprint import (
    LongGateFingerprintError,
    fingerprint_command,
    fingerprint_entry,
    fingerprint_files,
    stable_json_hash,
)
from tools.long_gate_manifest import LONG_GATE_SCHEMA_VERSION


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


def _write_reusable_success(repo_root: Path, *, entry=None, fingerprint=None):
    used_entry = entry or _entry()
    used_fingerprint = fingerprint or _fingerprint()
    output = _output_file(repo_root)
    write_success(
        used_entry,
        used_fingerprint,
        {"stdout": "ok\n", "stderr": "", "returncode": 0, "duration_s": 1.25},
        [str(output)],
        repo_root=str(repo_root),
    )
    return used_entry, used_fingerprint, output


def _success_path(repo_root: Path) -> Path:
    return repo_root / "evidence" / "QualityGate" / "long_gate" / "results" / "example_gate.success.json"


def _load_success(repo_root: Path) -> dict:
    return json.loads(_success_path(repo_root).read_text(encoding="utf-8"))


def _store_success(repo_root: Path, payload: dict) -> None:
    _success_path(repo_root).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


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


def test_fingerprint_entry_changes_when_output_result_files_change(tmp_path):
    entry = _entry()

    first = fingerprint_entry(entry, str(tmp_path))
    changed_entry = dict(entry)
    changed_entry["output_result_files"] = ["evidence/QualityGate/collect_nodeids.json"]
    changed = fingerprint_entry(changed_entry, str(tmp_path))

    assert changed["hash"] != first["hash"]


def test_fingerprint_files_marks_outside_repo_scope_without_reading_it(tmp_path):
    outside = tmp_path.parent / "outside-long-gate-source.py"
    outside.write_text("SECRET = 1\n", encoding="utf-8")

    fingerprint = fingerprint_files([str(outside)], str(tmp_path))

    assert fingerprint["files"][0]["kind"] == "outside_repo"
    assert fingerprint["files"][0]["exists"] is False
    assert fingerprint["files"][0]["sha256"] == ""


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


def test_cache_missing_required_field_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    payload.pop("fingerprint_hash")
    _store_success(tmp_path, payload)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "cache unreadable/corrupt/missing required field: fingerprint_hash"


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
    payload["schema_version"] = LONG_GATE_SCHEMA_VERSION + 1
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


def test_cache_fingerprint_hash_mismatch_is_not_reused(tmp_path):
    entry, fingerprint, _output = _write_reusable_success(tmp_path)
    payload = _load_success(tmp_path)
    payload["fingerprint"]["hash"] = "sha256:bad"
    _store_success(tmp_path, payload)

    decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "cache unreadable/corrupt: fingerprint hash mismatch"


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
