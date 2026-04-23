from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / ".limcode" / "skills" / "aps-full-selftest" / "scripts" / "run_full_selftest.py"
    spec = importlib.util.spec_from_file_location("aps_run_full_selftest", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_shared_module():
    repo_root = Path(__file__).resolve().parents[1]
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
    return __import__("tools.quality_gate_shared", fromlist=["QUALITY_GATE_GUARD_TESTS"])


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
    assert report_rel == "evidence/FullSelfTest/full_selftest_report.md"


def test_quality_gate_binding_status_accepts_clean_proof_manifest(tmp_path) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    manifest_path = repo_root / "evidence" / "QualityGate" / "quality_gate_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    checkout_root = str(repo_root.resolve())
    git_common_dir = str((repo_root / ".git").resolve())
    manifest_path.write_text(
        json.dumps(
            {
                "status": "passed",
                "head_sha": "deadbeef",
                "checkout_root_realpath": checkout_root,
                "git_common_dir_realpath": git_common_dir,
                "git_status_short_before": [],
                "git_status_short_after": [],
                "is_dirty_before": False,
                "is_dirty_after": False,
                "tracked_drift_detected": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    ok, note, manifest_rel = module._quality_gate_binding_status(repo_root, "deadbeef", [])

    assert ok is True
    assert note == "BOUND"
    assert manifest_rel == "evidence/QualityGate/quality_gate_manifest.json"


def test_quality_gate_binding_status_rejects_dirty_and_drifted_manifest(tmp_path) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    manifest_path = repo_root / "evidence" / "QualityGate" / "quality_gate_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    checkout_root = str(repo_root.resolve())
    git_common_dir = str((repo_root / ".git").resolve())

    manifest_path.write_text(
        json.dumps(
            {
                "status": "passed_but_unbound",
                "head_sha": "deadbeef",
                "checkout_root_realpath": checkout_root,
                "git_common_dir_realpath": git_common_dir,
                "git_status_short_before": [" M scripts/run_quality_gate.py"],
                "git_status_short_after": [" M scripts/run_quality_gate.py"],
                "is_dirty_before": True,
                "is_dirty_after": True,
                "tracked_drift_detected": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    ok, note, _manifest_rel = module._quality_gate_binding_status(
        repo_root,
        "deadbeef",
        [" M scripts/run_quality_gate.py"],
    )
    assert ok is False
    assert "status=passed_but_unbound" in note

    manifest_path.write_text(
        json.dumps(
            {
                "status": "passed",
                "head_sha": "deadbeef",
                "checkout_root_realpath": checkout_root,
                "git_common_dir_realpath": git_common_dir,
                "git_status_short_before": [],
                "git_status_short_after": [" M scripts/run_quality_gate.py"],
                "is_dirty_before": False,
                "is_dirty_after": True,
                "tracked_drift_detected": True,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    ok, note, _manifest_rel = module._quality_gate_binding_status(
        repo_root,
        "deadbeef",
        [" M scripts/run_quality_gate.py"],
    )
    assert ok is False
    assert "tracked drift" in note


def test_quality_gate_binding_status_rejects_head_mismatch_and_checkout_identity_mismatch(tmp_path) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    manifest_path = repo_root / "evidence" / "QualityGate" / "quality_gate_manifest.json"
    manifest_path.parent.mkdir(parents=True)

    manifest_path.write_text(
        json.dumps(
            {
                "status": "passed",
                "head_sha": "not-deadbeef",
                "checkout_root_realpath": str(repo_root.resolve()),
                "git_common_dir_realpath": str((repo_root / ".git").resolve()),
                "git_status_short_before": [],
                "git_status_short_after": [],
                "is_dirty_before": False,
                "is_dirty_after": False,
                "tracked_drift_detected": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    ok, note, _manifest_rel = module._quality_gate_binding_status(repo_root, "deadbeef", [])
    assert ok is False
    assert "head_sha" in note

    manifest_path.write_text(
        json.dumps(
            {
                "status": "passed",
                "head_sha": "deadbeef",
                "checkout_root_realpath": str((repo_root / "other-checkout").resolve()),
                "git_common_dir_realpath": str((repo_root / "other-git").resolve()),
                "git_status_short_before": [],
                "git_status_short_after": [],
                "is_dirty_before": False,
                "is_dirty_after": False,
                "tracked_drift_detected": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    ok, note, _manifest_rel = module._quality_gate_binding_status(repo_root, "deadbeef", [])
    assert ok is False
    assert "checkout root mismatch" in note


def test_full_selftest_explicit_guard_subset_comes_from_shared_registry() -> None:
    module = _load_module()
    shared = _load_shared_module()

    assert tuple(module._explicit_guard_tests()) == tuple(shared.iter_non_regression_guard_tests())
    assert "tests/test_run_full_selftest_report_metadata.py" in module._explicit_guard_tests()
