from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    repo_root = REPO_ROOT
    module_path = repo_root / ".limcode" / "skills" / "aps-full-selftest" / "scripts" / "run_full_selftest.py"
    spec = importlib.util.spec_from_file_location("aps_run_full_selftest", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_shared_module():
    repo_root = REPO_ROOT
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
    return __import__("tools.quality_gate_shared", fromlist=["QUALITY_GATE_REQUIRED_TESTS"])


def test_legacy_full_selftest_root_report_is_not_current_artifact() -> None:
    assert not (REPO_ROOT / "evidence" / "FullSelfTest" / "full_selftest_report.md").exists()


def _write_verified_manifest(
    repo_root: Path,
    *,
    head_sha: str = "deadbeef",
    status: str = "passed",
    git_status_short_before: Optional[List[str]] = None,
    git_status_short_after: Optional[List[str]] = None,
    overrides: Optional[Dict[str, object]] = None,
) -> Path:
    shared = _load_shared_module()
    for rel_path in shared.QUALITY_GATE_SOURCE_FILES:
        source_path = repo_root / rel_path
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(f"# proof source for {rel_path}\n", encoding="utf-8")
    manifest_path = repo_root / "evidence" / "QualityGate" / "quality_gate_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    git_status_short_before = list(git_status_short_before or [])
    git_status_short_after = list(git_status_short_after or [])
    commands = shared.build_quality_gate_command_plan()
    required_tests = shared.iter_quality_gate_required_tests()
    run_id = f"{head_sha}:test-run"
    for rel_path in required_tests:
        test_path = repo_root / rel_path
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text("def test_bound():\n    assert True\n", encoding="utf-8")
    collect_proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    collection_proof = shared.build_quality_gate_collection_proof(
        shared.parse_pytest_collect_nodeids(collect_proc.stdout),
        required_tests=required_tests,
    )
    command_receipts = []
    for index, command in enumerate(commands, start=1):
        receipt_rel = shared.build_quality_gate_receipt_rel_path(index, command["display"])
        receipt_path = repo_root / receipt_rel
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        is_collect_command = command["display"] == "python -m pytest --collect-only -q tests"
        receipt_payload = shared.build_quality_gate_command_receipt(
            command,
            run_id=run_id,
            command_index=index,
            returncode=int(collect_proc.returncode) if is_collect_command else 0,
            stdout=collect_proc.stdout if is_collect_command else (f"{command['display']} ok\n" if command.get("capture_output") else ""),
            stderr=collect_proc.stderr if is_collect_command else "",
        )
        receipt_path.write_text(json.dumps(receipt_payload, ensure_ascii=False), encoding="utf-8")
        command_receipts.append(
            {
                "path": receipt_rel,
                "sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
            }
        )
    gate_sources = shared.build_quality_gate_source_proof(repo_root)
    manifest = {
        "status": status,
        "schema_version": shared.QUALITY_GATE_PROOF_SCHEMA_VERSION,
        "run_id": run_id,
        "head_sha": head_sha,
        "checkout_root_realpath": str(repo_root.resolve()),
        "git_common_dir_realpath": str((repo_root / ".git").resolve()),
        "git_status_short_before": git_status_short_before,
        "git_status_short_after": git_status_short_after,
        "is_dirty_before": bool(git_status_short_before),
        "is_dirty_after": bool(git_status_short_after),
        "tracked_drift_detected": git_status_short_before != git_status_short_after,
        "proof_scope": dict(shared.QUALITY_GATE_PROOF_SCOPE),
        "required_tests": required_tests,
        "required_tests_hash": shared.hash_required_tests_registry(required_tests),
        "commands": commands,
        "commands_hash": shared.hash_quality_gate_commands(commands),
        "collection_proof": collection_proof,
        "collection_proof_hash": shared.hash_quality_gate_collection_proof(collection_proof),
        "command_receipts": command_receipts,
        "command_receipts_hash": shared.hash_quality_gate_command_receipts(command_receipts),
        "gate_sources": gate_sources,
        "gate_sources_hash": shared.hash_quality_gate_source_proof(gate_sources),
    }
    if overrides:
        manifest.update(overrides)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return manifest_path


def test_full_selftest_report_header_includes_revision_and_gate_manifest_metadata() -> None:
    module = _load_module()

    lines = module._report_header_lines(
        repo_root=Path("D:/Github/APS Test"),
        fail_fast=False,
        complex_repeat=1,
        step_timeout_s=900,
        head_sha="deadbeef",
        git_status_lines=[" M web/routes/domains/scheduler/scheduler_config.py"],
        quality_gate_manifest_rel="evidence/QualityGate/quality_gate_manifest.json",
    )

    joined = "\n".join(lines)
    assert "head_sha" in joined
    assert "deadbeef" in joined
    assert "git status --short" in joined
    assert "quality_gate_manifest" in joined


def test_tracked_regression_discovery_ignores_untracked_files(monkeypatch, tmp_path) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    tests_dir = repo_root / "tests"
    tests_dir.mkdir(parents=True)

    def fake_run(args, cwd=None, capture_output=False, text=False, errors=None, timeout=None):
        class _Proc:
            returncode = 0
            stdout = "tests/regression_tracked_one.py\ntests/regression_tracked_two.py\n"
            stderr = ""

        return _Proc()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    tracked = module._tracked_regression_files(repo_root)

    assert tracked == [
        repo_root / "tests" / "regression_tracked_one.py",
        repo_root / "tests" / "regression_tracked_two.py",
    ]


def test_run_full_selftest_fails_when_quality_gate_manifest_is_unbound(monkeypatch, tmp_path) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    (repo_root / "evidence" / "FullSelfTest").mkdir(parents=True)

    monkeypatch.setattr(module, "_build_steps", lambda repo_root, complex_repeat: [])
    monkeypatch.setattr(module, "_git_head_sha", lambda repo_root: "deadbeef")
    monkeypatch.setattr(module, "_git_status_lines", lambda repo_root: [])
    monkeypatch.setattr(module, "_quality_gate_binding_status", lambda repo_root, head_sha, git_status_lines: (False, "UNBOUND", None))

    ok, results, report_rel = module.run_full_selftest(
        repo_root=repo_root,
        fail_fast=False,
        complex_repeat=1,
        step_timeout_s=30,
    )

    assert ok is False
    assert results[0].name == "quality_gate_binding"
    assert results[0].effective_pass is False
    assert "UNBOUND" in results[0].note
    assert report_rel == "evidence/FullSelfTest/logs/full_selftest_report.md"


def test_quality_gate_binding_status_accepts_clean_proof_manifest(monkeypatch, tmp_path) -> None:
    module = _load_module()
    shared = _load_shared_module()
    repo_root = tmp_path / "repo"
    _write_verified_manifest(repo_root)
    replayed = []
    monkeypatch.setattr(
        shared,
        "replay_quality_gate_command_plan",
        lambda repo_root, commands, **_kwargs: replayed.append([command["display"] for command in commands]) or None,
    )
    monkeypatch.setattr(shared, "git_status_short_lines", lambda repo_root: [])

    ok, note, manifest_rel = module._quality_gate_binding_status(repo_root, "deadbeef", [])

    assert ok is True
    assert note == "BOUND"
    assert manifest_rel == "evidence/QualityGate/quality_gate_manifest.json"
    assert replayed == [[command["display"] for command in shared.build_quality_gate_command_plan()]]


def test_quality_gate_binding_status_replays_full_test_debt_proof_command(monkeypatch, tmp_path) -> None:
    module = _load_module()
    shared = _load_shared_module()
    repo_root = tmp_path / "repo"
    _write_verified_manifest(repo_root)
    replayed = []
    monkeypatch.setattr(
        shared,
        "replay_quality_gate_command_plan",
        lambda repo_root, commands, **_kwargs: replayed.append([command["display"] for command in commands]) or None,
    )
    monkeypatch.setattr(shared, "git_status_short_lines", lambda repo_root: [])

    ok, note, _manifest_rel = module._quality_gate_binding_status(repo_root, "deadbeef", [])

    assert ok is True
    assert note == "BOUND"
    assert "python tools/check_full_test_debt.py" in replayed[0]


def test_quality_gate_binding_status_rejects_missing_full_test_debt_receipt(monkeypatch, tmp_path) -> None:
    module = _load_module()
    shared = _load_shared_module()
    repo_root = tmp_path / "repo"
    manifest_path = _write_verified_manifest(repo_root)
    monkeypatch.setattr(shared, "replay_quality_gate_command_plan", lambda repo_root, commands, **_kwargs: None)
    monkeypatch.setattr(shared, "git_status_short_lines", lambda repo_root: [])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    display_to_receipt = {
        command["display"]: receipt
        for command, receipt in zip(manifest["commands"], manifest["command_receipts"])
    }
    receipt_path = repo_root / display_to_receipt["python tools/check_full_test_debt.py"]["path"]
    receipt_path.unlink()

    ok, note, _manifest_rel = module._quality_gate_binding_status(repo_root, "deadbeef", [])

    assert ok is False
    assert "command receipt missing" in note


def test_quality_gate_binding_status_rejects_tampered_full_test_debt_receipt_hash(
    monkeypatch,
    tmp_path,
) -> None:
    module = _load_module()
    shared = _load_shared_module()
    repo_root = tmp_path / "repo"
    manifest_path = _write_verified_manifest(repo_root)
    monkeypatch.setattr(shared, "replay_quality_gate_command_plan", lambda repo_root, commands, **_kwargs: None)
    monkeypatch.setattr(shared, "git_status_short_lines", lambda repo_root: [])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    display_to_receipt = {
        command["display"]: receipt
        for command, receipt in zip(manifest["commands"], manifest["command_receipts"])
    }
    receipt_path = repo_root / display_to_receipt["python tools/check_full_test_debt.py"]["path"]
    receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_payload["stdout_sha256"] = "0" * 64
    receipt_path.write_text(json.dumps(receipt_payload, ensure_ascii=False), encoding="utf-8")

    ok, note, _manifest_rel = module._quality_gate_binding_status(repo_root, "deadbeef", [])

    assert ok is False
    assert "command receipt hash mismatch" in note


def test_quality_gate_manifest_replay_rechecks_clean_worktree(monkeypatch, tmp_path) -> None:
    shared = _load_shared_module()
    repo_root = tmp_path / "repo"
    manifest_path = _write_verified_manifest(repo_root)
    monkeypatch.setattr(shared, "replay_quality_gate_command_plan", lambda repo_root, commands, **_kwargs: None)
    monkeypatch.setattr(
        shared,
        "git_status_short_lines",
        lambda repo_root: [" M evidence/FullSelfTest/full_selftest_report.md"],
    )

    ok, note = shared.verify_quality_gate_manifest(
        repo_root=repo_root,
        manifest=json.loads(manifest_path.read_text(encoding="utf-8")),
        head_sha="deadbeef",
        git_status_lines=[],
        replay_commands=True,
    )

    assert ok is False
    assert "replay left dirty worktree" in note
    assert "evidence/FullSelfTest/full_selftest_report.md" in note


def test_quality_gate_binding_status_rejects_command_replay_failure(monkeypatch, tmp_path) -> None:
    module = _load_module()
    shared = _load_shared_module()
    repo_root = tmp_path / "repo"
    _write_verified_manifest(repo_root)
    monkeypatch.setattr(
        shared,
        "replay_quality_gate_command_plan",
        lambda repo_root, commands, **_kwargs: "UNBOUND: quality gate command replay failed: python -m ruff check",
    )

    ok, note, _manifest_rel = module._quality_gate_binding_status(repo_root, "deadbeef", [])

    assert ok is False
    assert "command replay failed" in note


def test_quality_gate_binding_status_replay_disabled_is_structural_only(tmp_path) -> None:
    shared = _load_shared_module()
    repo_root = tmp_path / "repo"
    _write_verified_manifest(repo_root)

    ok, note = shared.verify_quality_gate_manifest(
        repo_root=repo_root,
        manifest=json.loads((repo_root / "evidence" / "QualityGate" / "quality_gate_manifest.json").read_text(encoding="utf-8")),
        head_sha="deadbeef",
        git_status_lines=[],
        replay_commands=False,
    )

    assert ok is False
    assert "STRUCTURAL_ONLY" in note


def test_quality_gate_replay_rejects_forged_non_collect_receipt_output(tmp_path) -> None:
    shared = _load_shared_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command = {
        "display": "python -c print-quality-gate-proof",
        "args": ["python", "-c", "print('real-output')"],
        "capture_output": True,
        "output_policy": "exact",
    }
    receipt_rel = shared.build_quality_gate_receipt_rel_path(1, command["display"])
    receipt_path = repo_root / receipt_rel
    receipt_path.parent.mkdir(parents=True)
    receipt_payload = shared.build_quality_gate_command_receipt(
        command,
        run_id="test-run",
        command_index=1,
        returncode=0,
        stdout="forged-output\n",
        stderr="",
    )
    receipt_path.write_text(json.dumps(receipt_payload, ensure_ascii=False), encoding="utf-8")

    note = shared.replay_quality_gate_command_plan(repo_root, [command], timeout_s=30, compare_receipts=True)

    assert note is not None
    assert "stdout replay mismatch" in note


def test_quality_gate_normalized_output_ignores_volatile_iso_timestamp() -> None:
    shared = _load_shared_module()
    before = (
        '治理台账校验通过\n{"checked_at": "2026-04-25T00:45:25+08:00"}\n'
        "2026-04-25 00:51:36 [INFO] 已写入：/tmp/aps_quickref_check_abc123/logs/aps_secret_key.txt\n"
    )
    after = (
        '治理台账校验通过\n{"checked_at": "2026-04-25T00:47:54+08:00"}\n'
        "2026-04-25 00:51:37 [INFO] 已写入：/tmp/aps_quickref_check_xyz789/logs/aps_secret_key.txt\n"
    )

    assert shared._hash_command_output(before, policy="normalized") == shared._hash_command_output(after, policy="normalized")


def test_quality_gate_normalized_output_ignores_pyright_update_notice() -> None:
    shared = _load_shared_module()
    before = "pyright 1.1.406\n"
    after = (
        "pyright 1.1.406\n"
        "WARNING: there is a new pyright version available (v1.1.406 -> v1.1.409).\n"
        "Please install the new version or set PYRIGHT_PYTHON_FORCE_VERSION to `latest`\n\n"
    )

    assert shared._hash_command_output(before, policy="normalized") == shared._hash_command_output(after, policy="normalized")


def test_quality_gate_binding_status_rejects_dirty_and_drifted_manifest(tmp_path) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    _write_verified_manifest(
        repo_root,
        status="passed_but_unbound",
        git_status_short_before=[" M scripts/run_quality_gate.py"],
        git_status_short_after=[" M scripts/run_quality_gate.py"],
    )
    ok, note, _manifest_rel = module._quality_gate_binding_status(
        repo_root,
        "deadbeef",
        [" M scripts/run_quality_gate.py"],
    )
    assert ok is False
    assert "status=passed_but_unbound" in note

    _write_verified_manifest(
        repo_root,
        git_status_short_before=[],
        git_status_short_after=[" M scripts/run_quality_gate.py"],
        overrides={"tracked_drift_detected": True},
    )
    ok, note, _manifest_rel = module._quality_gate_binding_status(
        repo_root,
        "deadbeef",
        [" M scripts/run_quality_gate.py"],
    )
    assert ok is False
    assert "tracked drift" in note


def test_quality_gate_binding_status_reports_failed_manifest_reason(tmp_path) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    _write_verified_manifest(
        repo_root,
        status="failed",
        overrides={
            "failure_kind": "dirty_worktree",
            "failure_message": "tracked changes exist before quality gate",
        },
    )

    ok, note, _manifest_rel = module._quality_gate_binding_status(repo_root, "deadbeef", [" M app.py"])

    assert ok is False
    assert "status=failed" in note
    assert "dirty_worktree" in note
    assert "tracked changes exist before quality gate" in note


def test_quality_gate_binding_status_rejects_head_mismatch_and_checkout_identity_mismatch(tmp_path) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    _write_verified_manifest(repo_root, head_sha="not-deadbeef")
    ok, note, _manifest_rel = module._quality_gate_binding_status(repo_root, "deadbeef", [])
    assert ok is False
    assert "head_sha" in note

    _write_verified_manifest(
        repo_root,
        overrides={
            "checkout_root_realpath": str((repo_root / "other-checkout").resolve()),
            "git_common_dir_realpath": str((repo_root / "other-git").resolve()),
        },
    )
    ok, note, _manifest_rel = module._quality_gate_binding_status(repo_root, "deadbeef", [])
    assert ok is False
    assert "checkout root mismatch" in note


def test_quality_gate_binding_status_rejects_missing_or_wrong_proof_scope(tmp_path) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    _write_verified_manifest(repo_root, overrides={"proof_scope": None})

    ok, note, _manifest_rel = module._quality_gate_binding_status(repo_root, "deadbeef", [])

    assert ok is False
    assert "proof_scope" in note

    _write_verified_manifest(
        repo_root,
        overrides={"proof_scope": {"claim": "risk_coverage_complete", "does_not_claim": ""}},
    )
    ok, note, _manifest_rel = module._quality_gate_binding_status(repo_root, "deadbeef", [])

    assert ok is False
    assert "proof_scope" in note


def test_quality_gate_binding_status_rejects_hash_mismatch(tmp_path) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    manifest_path = _write_verified_manifest(repo_root)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["required_tests_hash"] = "mismatch"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    ok, note, _manifest_rel = module._quality_gate_binding_status(repo_root, "deadbeef", [])
    assert ok is False
    assert "required_tests_hash" in note

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["required_tests_hash"] = _load_shared_module().hash_required_tests_registry(manifest["required_tests"])
    manifest["commands_hash"] = "mismatch"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    ok, note, _manifest_rel = module._quality_gate_binding_status(repo_root, "deadbeef", [])
    assert ok is False
    assert "commands_hash" in note

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["commands_hash"] = _load_shared_module().hash_quality_gate_commands(manifest["commands"])
    manifest["command_receipts_hash"] = "mismatch"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    ok, note, _manifest_rel = module._quality_gate_binding_status(repo_root, "deadbeef", [])
    assert ok is False
    assert "command_receipts_hash" in note

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["command_receipts_hash"] = _load_shared_module().hash_quality_gate_command_receipts(
        manifest["command_receipts"]
    )
    manifest["collection_proof_hash"] = "mismatch"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    ok, note, _manifest_rel = module._quality_gate_binding_status(repo_root, "deadbeef", [])
    assert ok is False
    assert "collection_proof_hash" in note

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["collection_proof_hash"] = _load_shared_module().hash_quality_gate_collection_proof(
        manifest["collection_proof"]
    )
    manifest["gate_sources_hash"] = "mismatch"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    ok, note, _manifest_rel = module._quality_gate_binding_status(repo_root, "deadbeef", [])
    assert ok is False
    assert "gate_sources_hash" in note


def test_quality_gate_binding_status_rejects_missing_command_receipt_file(tmp_path) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    manifest_path = _write_verified_manifest(repo_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    first_receipt = repo_root / manifest["command_receipts"][0]["path"]
    first_receipt.unlink()

    ok, note, _manifest_rel = module._quality_gate_binding_status(repo_root, "deadbeef", [])
    assert ok is False
    assert "command receipt missing" in note


def test_quality_gate_binding_status_rejects_fabricated_collection_proof(tmp_path) -> None:
    module = _load_module()
    shared = _load_shared_module()
    repo_root = tmp_path / "repo"
    manifest_path = _write_verified_manifest(repo_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["collection_proof"] = shared.build_quality_gate_collection_proof(
        ["tests/not_collected.py::test_forged"],
        required_tests=manifest["required_tests"],
    )
    manifest["collection_proof_hash"] = shared.hash_quality_gate_collection_proof(manifest["collection_proof"])
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    ok, note, _manifest_rel = module._quality_gate_binding_status(repo_root, "deadbeef", [])

    assert ok is False
    assert "collection proof mismatch" in note


def test_quality_gate_binding_status_rejects_fabricated_collect_receipt(tmp_path) -> None:
    module = _load_module()
    shared = _load_shared_module()
    repo_root = tmp_path / "repo"
    manifest_path = _write_verified_manifest(repo_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt_rel = manifest["command_receipts"][0]["path"]
    receipt_path = repo_root / receipt_rel
    receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_payload["stdout_sha256"] = "0" * 64
    receipt_path.write_text(json.dumps(receipt_payload, ensure_ascii=False), encoding="utf-8")
    manifest["command_receipts"][0]["sha256"] = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    manifest["command_receipts_hash"] = shared.hash_quality_gate_command_receipts(manifest["command_receipts"])
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    ok, note, _manifest_rel = module._quality_gate_binding_status(repo_root, "deadbeef", [])

    assert ok is False
    assert "collect receipt stdout hash mismatch" in note


def test_full_selftest_explicit_guard_subset_comes_from_shared_registry() -> None:
    module = _load_module()
    shared = _load_shared_module()

    assert tuple(module._explicit_guard_tests()) == tuple(shared.iter_quality_gate_required_tests())
    assert "tests/test_run_full_selftest_report_metadata.py" in module._explicit_guard_tests()
