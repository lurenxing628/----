from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

from tools import long_gate_fingerprint as fingerprint_mod
from tools import long_gate_manifest as manifest_mod
from tools import quality_gate_shared
from tools.long_gate_cache import decide_reuse, write_success
from tools.long_gate_fingerprint import fingerprint_entry


def _entry_by_id(manifest, entry_id):
    for entry in list(manifest["entries"]):
        if entry["entry_id"] == entry_id:
            return entry
    raise AssertionError(f"missing entry_id: {entry_id}")


def _debt_entry(repo_root):
    manifest = manifest_mod.build_manifest_from_quality_gate_plan(
        quality_gate_shared.build_quality_gate_command_plan(),
        repo_root=str(repo_root),
    )
    return _entry_by_id(manifest, "debt_ledger_sync")


def _import_run_quality_gate():
    repo_root = str(Path(__file__).resolve().parents[1])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("scripts.run_quality_gate", None)
    return importlib.import_module("scripts.run_quality_gate")


def _write(path: Path, text: str = "marker\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_debt_ledger_sync_entry_is_reuse_enabled_with_declared_proof_output() -> None:
    entry = _debt_entry(quality_gate_shared.REPO_ROOT)

    assert entry["display"] == "python scripts/sync_debt_ledger.py check"
    assert entry["args"] == ["python", "scripts/sync_debt_ledger.py", "check"]
    assert entry["cache_status"] == "enabled"
    assert entry["reuse_allowed"] is True
    assert entry["output_result_files"] == ["evidence/QualityGate/debt_ledger_sync.json"]


def test_debt_ledger_sync_manifest_tracks_required_scopes() -> None:
    entry = _debt_entry(quality_gate_shared.REPO_ROOT)

    for scope in [
        "开发文档/技术债务治理台账.md",
        "codestable/roadmap/**/*.md",
        "codestable/features/**/*.yaml",
        "core/**/*.py",
        "web/**/*.py",
        "data/**/*.py",
        "tests/**/*.py",
        "tools/**/*.py",
        "scripts/**/*.py",
        "templates/**/*.html",
        "static/**/*",
        "docs/**/*.md",
        "audit/**/*.md",
    ]:
        assert scope in entry["input_file_scopes"]
    for scope in [
        "scripts/sync_debt_ledger.py",
        "tools/quality_gate_ledger.py",
        "tools/quality_gate_operations.py",
        "tools/quality_gate_scan.py",
        "tools/architecture_scan_cache.py",
        "tools/long_gate_manifest.py",
        "tools/long_gate_fingerprint.py",
        "scripts/run_quality_gate.py",
    ]:
        assert scope in entry["tool_file_scopes"]
    for scope in ["pyproject.toml", ".gitignore", ".github/workflows/quality.yml"]:
        assert scope in entry["config_file_scopes"]
    assert "requirements*.txt" in entry["dependency_file_scopes"]
    assert "architecture_scan_cache_metadata" in entry["env_keys"]
    assert "PYTHONUTF8" in entry["env_keys"]
    assert "evidence/QualityGate/architecture_scan_cache.json" not in entry["input_file_scopes"]


def test_debt_ledger_sync_fingerprint_tracks_ledger_script_scan_tools_and_output_path(tmp_path):
    entry = _debt_entry(tmp_path)
    before = fingerprint_entry(entry, str(tmp_path))

    _write(tmp_path / "开发文档" / "技术债务治理台账.md", "ledger one\n")
    after_ledger = fingerprint_entry(entry, str(tmp_path))
    assert after_ledger["hash"] != before["hash"]

    _write(tmp_path / "scripts" / "sync_debt_ledger.py", "print('sync')\n")
    after_script = fingerprint_entry(entry, str(tmp_path))
    assert after_script["hash"] != after_ledger["hash"]

    _write(tmp_path / "tools" / "quality_gate_scan.py", "SCAN = 1\n")
    after_scan_tool = fingerprint_entry(entry, str(tmp_path))
    assert after_scan_tool["hash"] != after_script["hash"]

    changed_entry = dict(entry)
    changed_entry["output_result_files"] = ["evidence/QualityGate/debt_ledger_sync_v2.json"]
    after_output_path = fingerprint_entry(changed_entry, str(tmp_path))
    assert after_output_path["hash"] != after_scan_tool["hash"]


def test_debt_ledger_sync_fingerprint_tracks_architecture_scan_metadata(monkeypatch, tmp_path):
    entry = _debt_entry(tmp_path)
    rows = [
        {
            "schema_version": 1,
            "scanner_version_hash": "one",
            "scanner_schema_version": 1,
            "python_version": "3.8.10",
            "radon_version_or_behavior_hash": "radon-one",
        },
        {
            "schema_version": 1,
            "scanner_version_hash": "two",
            "scanner_schema_version": 1,
            "python_version": "3.8.10",
            "radon_version_or_behavior_hash": "radon-two",
        },
    ]

    monkeypatch.setattr(
        fingerprint_mod.architecture_scan_cache,
        "architecture_scan_cache_metadata",
        lambda repo_root=None: rows.pop(0),
    )

    before = fingerprint_entry(entry, str(tmp_path))
    after = fingerprint_entry(entry, str(tmp_path))

    assert before["hash"] != after["hash"]


def test_debt_ledger_sync_fingerprint_ignores_generated_architecture_cache_file(tmp_path):
    entry = _debt_entry(tmp_path)
    before = fingerprint_entry(entry, str(tmp_path))

    _write(tmp_path / "evidence" / "QualityGate" / "architecture_scan_cache.json", '{"generated": true}\n')
    after = fingerprint_entry(entry, str(tmp_path))

    assert after["hash"] == before["hash"]


def _debt_ledger_stdout() -> str:
    payload = {
        "accepted_risk_count": 5,
        "checked_at": "2026-05-15T12:00:00+08:00",
        "complexity_count": 2,
        "oversize_count": 1,
        "samples": {"sample_count": 7, "fallback_kinds": ["observable_degrade"]},
        "schema_version": 2,
        "silent_fallback_count": 3,
        "test_debt_count": 4,
    }
    return "治理台账校验通过\n" + json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def test_debt_ledger_sync_success_proof_is_written_before_success_cache(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    monkeypatch.setattr(module, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(module, "LEDGER_PATH", str(tmp_path / "开发文档" / "技术债务治理台账.md"))
    monkeypatch.setattr(module, "_git_head_sha", lambda: "abc123")
    monkeypatch.setattr(
        module,
        "architecture_scan_cache_metadata",
        lambda repo_root=None: {
            "schema_version": 1,
            "scanner_version_hash": "scanner",
            "scanner_schema_version": 1,
            "python_version": "3.8.10",
            "radon_version_or_behavior_hash": "radon",
        },
    )
    entry = _debt_entry(tmp_path)
    fingerprint = fingerprint_entry(entry, str(tmp_path))
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    result = {
        "stdout": _debt_ledger_stdout(),
        "stderr": "",
        "returncode": 0,
        "duration_s": 1.25,
        "execution_mode": "executed",
        "timed_out": False,
        "interrupted": False,
        "partial_write": False,
    }

    output_paths = module._prepare_long_gate_success_output_files(
        entry,
        result,
        cache_dir="evidence/QualityGate/long_gate",
        run_id="run-1",
        command_index=11,
        command_plan=command_plan,
        fingerprint=fingerprint,
    )

    assert output_paths == ["evidence/QualityGate/debt_ledger_sync.json"]
    proof_path = tmp_path / "evidence" / "QualityGate" / "debt_ledger_sync.json"
    assert proof_path.is_file()
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    assert proof["entry_id"] == "debt_ledger_sync"
    assert proof["head_sha"] == "abc123"
    assert proof["ledger_path"] == "开发文档/技术债务治理台账.md"
    assert proof["ledger_schema_version"] == 2
    assert proof["ledger_counts"] == {
        "accepted_risk_count": 5,
        "complexity_count": 2,
        "oversize_count": 1,
        "silent_fallback_count": 3,
        "test_debt_count": 4,
    }
    assert proof["architecture_scan_cache"]["scanner_version_hash"] == "scanner"
    assert proof["does_not_claim"] == "clean_worktree_proof"
    assert proof["stdout_sha256"] == proof["logs"]["stdout"]["sha256"]
    assert proof["stderr_sha256"] == proof["logs"]["stderr"]["sha256"]


def test_debt_ledger_sync_reuse_rejects_missing_or_tampered_proof(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    monkeypatch.setattr(module, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(module, "LEDGER_PATH", str(tmp_path / "开发文档" / "技术债务治理台账.md"))
    monkeypatch.setattr(module, "_git_head_sha", lambda: "abc123")
    monkeypatch.setattr(
        module,
        "architecture_scan_cache_metadata",
        lambda repo_root=None: {
            "schema_version": 1,
            "scanner_version_hash": "scanner",
            "scanner_schema_version": 1,
            "python_version": "3.8.10",
            "radon_version_or_behavior_hash": "radon",
        },
    )
    entry = _debt_entry(tmp_path)
    entry["reuse_allowed"] = True
    entry["cache_status"] = "enabled"
    fingerprint = fingerprint_entry(entry, str(tmp_path))
    result = {
        "stdout": _debt_ledger_stdout(),
        "stderr": "",
        "returncode": 0,
        "duration_s": 1.25,
        "execution_mode": "executed",
        "timed_out": False,
        "interrupted": False,
        "partial_write": False,
    }
    output_paths = module._prepare_long_gate_success_output_files(
        entry,
        result,
        cache_dir="evidence/QualityGate/long_gate",
        run_id="run-1",
        command_index=11,
        command_plan=quality_gate_shared.build_quality_gate_command_plan(),
        fingerprint=fingerprint,
    )
    proof_path = tmp_path / output_paths[0]
    write_success(
        entry,
        fingerprint,
        result,
        [str(proof_path)],
        repo_root=str(tmp_path),
    )

    assert decide_reuse(entry, fingerprint, repo_root=str(tmp_path))["decision"] == "reuse"

    proof_path.unlink()
    missing_decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))
    assert missing_decision["decision"] == "run"
    assert missing_decision["reason"] == "previous output files missing or hash mismatch"

    module._prepare_long_gate_success_output_files(
        entry,
        result,
        cache_dir="evidence/QualityGate/long_gate",
        run_id="run-1",
        command_index=11,
        command_plan=quality_gate_shared.build_quality_gate_command_plan(),
        fingerprint=fingerprint,
    )
    tampered = json.loads(proof_path.read_text(encoding="utf-8"))
    tampered["status"] = "tampered"
    proof_path.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")
    tampered_decision = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))
    assert tampered_decision["decision"] == "run"
    assert tampered_decision["reason"] == "previous output files missing or hash mismatch"


def test_debt_ledger_sync_explain_decision_does_not_write_proof(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    monkeypatch.setattr(module, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(
        module,
        "_strict_long_gate_fingerprint",
        lambda entry: {"schema_version": 1, "hash": "sha256:explain-debt"},
    )
    monkeypatch.setattr(
        module,
        "evaluate_reuse",
        lambda entry, fingerprint, repo_root=None, cache_dir=None: {
            "decision": {
                "entry_id": "debt_ledger_sync",
                "decision": "run",
                "reuse_allowed": False,
                "reason": "no previous success cache",
                "invalidated_by": [],
                "previous_completed_at": "",
                "previous_result_path": "",
                "current_fingerprint_hash": fingerprint["hash"],
            },
            "validated_success": None,
            "stdout": "",
            "stderr": "",
        },
    )
    command_plan = [
        {
            "display": "python scripts/sync_debt_ledger.py check",
            "args": ["python", "scripts/sync_debt_ledger.py", "check"],
            "capture_output": False,
            "output_policy": "normalized",
        }
    ]

    summary_entries, runtime_entries = module._prepare_long_gate_cache_decisions(
        command_plan,
        cache_enabled=True,
        cache_dir="evidence/QualityGate/long_gate",
    )

    assert summary_entries[0]["entry_id"] == "debt_ledger_sync"
    assert summary_entries[0]["decision"] == "run"
    assert "python scripts/sync_debt_ledger.py check" in runtime_entries
    assert not (tmp_path / "evidence" / "QualityGate" / "debt_ledger_sync.json").exists()


def test_debt_ledger_sync_dirty_run_does_not_write_proof_or_success_cache(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    monkeypatch.setattr(module, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(module, "LEDGER_PATH", str(tmp_path / "开发文档" / "技术债务治理台账.md"))
    entry = _debt_entry(tmp_path)
    runtime_entries = {
        "python scripts/sync_debt_ledger.py check": {
            "entry": entry,
            "fingerprint": {"schema_version": 1, "hash": "sha256:dirty-debt"},
            "evaluation": {},
            "decision": {"decision": "run", "reason": "dirty worktree disables success cache writes"},
            "summary_entry": {},
        }
    }
    monkeypatch.setattr(
        module,
        "_run_command_with_env_overlay",
        lambda display, args, capture_output, env_overlay: {
            "stdout": _debt_ledger_stdout(),
            "stderr": "",
            "returncode": 0,
        },
    )
    pending_successes = []

    module._run_quality_gate_command_plan(
        [
            {
                "display": "python scripts/sync_debt_ledger.py check",
                "args": ["python", "scripts/sync_debt_ledger.py", "check"],
                "capture_output": False,
                "output_policy": "normalized",
            }
        ],
        run_id="run-1",
        commands=[],
        command_receipts=[],
        parsed_command_results={},
        long_gate_cache=True,
        long_gate_cache_write_success=False,
        long_gate_cache_dir="evidence/QualityGate/long_gate",
        long_gate_runtime_entries=runtime_entries,
        pending_long_gate_successes=pending_successes,
    )

    assert not (tmp_path / "evidence" / "QualityGate" / "debt_ledger_sync.json").exists()
    assert not (
        tmp_path / "evidence" / "QualityGate" / "long_gate" / "results" / "debt_ledger_sync.success.json"
    ).exists()
    assert pending_successes == []


def test_debt_ledger_sync_planned_entry_writes_proof_without_pending_success(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    monkeypatch.setattr(module, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(module, "LEDGER_PATH", str(tmp_path / "开发文档" / "技术债务治理台账.md"))
    monkeypatch.setattr(module, "_git_head_sha", lambda: "abc123")
    monkeypatch.setattr(
        module,
        "_strict_long_gate_fingerprint",
        lambda entry: {"schema_version": 1, "hash": "sha256:planned-debt"},
    )
    monkeypatch.setattr(
        module,
        "architecture_scan_cache_metadata",
        lambda repo_root=None: {
            "schema_version": 1,
            "scanner_version_hash": "scanner",
            "scanner_schema_version": 1,
            "python_version": "3.8.10",
            "radon_version_or_behavior_hash": "radon",
        },
    )

    command_plan = [
        {
            "display": "python scripts/sync_debt_ledger.py check",
            "args": ["python", "scripts/sync_debt_ledger.py", "check"],
            "capture_output": False,
            "output_policy": "normalized",
        }
    ]
    entry = _debt_entry(tmp_path)
    entry["reuse_allowed"] = False
    entry["cache_status"] = "planned"
    runtime_entries = {
        "python scripts/sync_debt_ledger.py check": {
            "entry": entry,
            "fingerprint": {},
            "evaluation": {},
            "decision": {"decision": "planned_only", "reason": "not enabled yet"},
            "summary_entry": {},
        }
    }
    monkeypatch.setattr(
        module,
        "_run_command_with_env_overlay",
        lambda display, args, capture_output, env_overlay: {
            "stdout": _debt_ledger_stdout(),
            "stderr": "",
            "returncode": 0,
        },
    )
    pending_successes = []

    module._run_quality_gate_command_plan(
        command_plan,
        run_id="run-1",
        commands=[],
        command_receipts=[],
        parsed_command_results={},
        long_gate_cache=True,
        long_gate_cache_write_success=True,
        long_gate_cache_dir="evidence/QualityGate/long_gate",
        long_gate_runtime_entries=runtime_entries,
        pending_long_gate_successes=pending_successes,
    )

    proof_path = tmp_path / "evidence" / "QualityGate" / "debt_ledger_sync.json"
    assert proof_path.is_file()
    assert json.loads(proof_path.read_text(encoding="utf-8"))["fingerprint_hash"] == "sha256:planned-debt"
    assert pending_successes == []
