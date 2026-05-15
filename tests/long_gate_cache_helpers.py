from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from tools import long_gate_fingerprint as fingerprint_mod
from tools import quality_gate_shared
from tools.long_gate_cache import evaluate_reuse, write_success
from tools.long_gate_fingerprint import fingerprint_entry
from tools.long_gate_manifest import (
    ENTRY_REQUIRED_REGRESSIONS,
    ENTRY_STARTUP_RUNTIME_REGRESSIONS,
    build_manifest_from_quality_gate_plan,
)


def _repo_root() -> str:
    return str(Path(__file__).resolve().parents[1])


def _import_run_quality_gate():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("scripts.run_quality_gate", None)
    return importlib.import_module("scripts.run_quality_gate")


def _real_quality_gate_plan() -> List[Dict[str, Any]]:
    return list(quality_gate_shared.build_quality_gate_command_plan())


def _manifest_for(command_plan: Sequence[Dict[str, Any]], repo_root: Path) -> Dict[str, Any]:
    return build_manifest_from_quality_gate_plan(command_plan, repo_root=str(repo_root))


def _entry_by_id(manifest: Dict[str, Any], entry_id: str) -> Dict[str, Any]:
    for entry in manifest["entries"]:
        if entry["entry_id"] == entry_id:
            return entry
    raise AssertionError(f"missing entry_id: {entry_id}")


def _entry_display(command_plan: Sequence[Dict[str, Any]], repo_root: Path, entry_id: str) -> str:
    return str(_entry_by_id(_manifest_for(command_plan, repo_root), entry_id)["display"])


def _fingerprint_for(command_plan: Sequence[Dict[str, Any]], repo_root: Path, entry_id: str) -> Dict[str, Any]:
    return fingerprint_entry(_entry_by_id(_manifest_for(command_plan, repo_root), entry_id), str(repo_root))


def _reuse_decision_for(command_plan: Sequence[Dict[str, Any]], repo_root: Path, entry_id: str) -> Dict[str, Any]:
    entry = _entry_by_id(_manifest_for(command_plan, repo_root), entry_id)
    fingerprint = fingerprint_entry(entry, str(repo_root), strict=True)
    return evaluate_reuse(entry, fingerprint, repo_root=str(repo_root))["decision"]


def _success_path(repo_root: Path, entry_id: str) -> Path:
    return repo_root / "evidence" / "QualityGate" / "long_gate" / "results" / f"{entry_id}.success.json"


def _summary_path(repo_root: Path) -> Path:
    return repo_root / "evidence" / "QualityGate" / "long_gate" / "summary.json"


def _load_summary(repo_root: Path) -> Dict[str, Any]:
    return json.loads(_summary_path(repo_root).read_text(encoding="utf-8"))


def _summary_entry(summary: Dict[str, Any], entry_id: str) -> Dict[str, Any]:
    for entry in summary["entries"]:
        if entry["entry_id"] == entry_id:
            return entry
    raise AssertionError(f"missing summary entry: {entry_id}")


def _write_file(repo_root: Path, rel_path: str, text: str = "changed\n") -> Path:
    path = repo_root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _patch_gate_environment(monkeypatch, module, repo_root: Path, *, statuses: Sequence[Sequence[str]] = ()) -> None:
    if not (repo_root / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    status_rows = [list(item) for item in list(statuses or [[] for _ in range(30)])]

    def next_status() -> List[str]:
        if status_rows:
            return status_rows.pop(0)
        return []

    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(
        module,
        "_repo_identity",
        lambda: {
            "checkout_root_realpath": str(repo_root.resolve()),
            "git_common_dir_realpath": str((repo_root / ".git").resolve()),
        },
    )
    monkeypatch.setattr(module, "_assert_no_active_runtime", lambda: None)
    monkeypatch.setattr(module, "_assert_guard_tests_ready", lambda: None)
    monkeypatch.setattr(module, "_git_head_sha", lambda: "deadbeef")
    monkeypatch.setattr(module, "_git_status_lines", next_status)
    monkeypatch.setattr(module, "_run_git_bytes", lambda _args: b"")
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})
    monkeypatch.setattr(module, "pytest_distribution_version", lambda strict=False: "pytest 8.3.5")
    monkeypatch.setattr(
        fingerprint_mod,
        "_chrome_executable_resolution",
        lambda strict=False, environment=None: "/stable/chrome",
    )
    monkeypatch.setattr(
        fingerprint_mod,
        "_chrome_version",
        lambda strict=False, environment=None: "Stable Chrome 120.0.0.0",
    )
    monkeypatch.setattr(
        fingerprint_mod,
        "_chrome_executable_identity",
        lambda strict=False, environment=None: "stable-chrome-identity",
    )
    monkeypatch.setattr(
        fingerprint_mod,
        "_chrome_headless_preflight",
        lambda strict=False, environment=None: "stable-headless-preflight",
    )
    monkeypatch.setattr(fingerprint_mod, "_node_executable_realpath", lambda environment=None: "/stable/node")
    monkeypatch.setattr(fingerprint_mod, "_node_version", lambda strict=False, environment=None: "v24.0.0")
    monkeypatch.setattr(
        fingerprint_mod,
        "_node_browser_runtime_capability",
        lambda strict=False, environment=None: "stable-node-browser-runtime-capability",
    )


@dataclass(frozen=True)
class GateRunContext:
    module: Any
    repo_root: Path
    command_plan: Sequence[Dict[str, Any]]


def _prepare_gate_run_context(
    monkeypatch,
    tmp_path: Path,
    *,
    command_plan: Optional[Sequence[Dict[str, Any]]] = None,
    statuses: Sequence[Sequence[str]] = (),
) -> GateRunContext:
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    resolved_plan = list(command_plan) if command_plan is not None else _real_quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=statuses)
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(resolved_plan))
    return GateRunContext(module=module, repo_root=repo_root, command_plan=resolved_plan)


def _proof_path_for_entry(repo_root: Path, entry_id: str) -> Path:
    if entry_id == ENTRY_REQUIRED_REGRESSIONS:
        return repo_root / "evidence" / "QualityGate" / "required_regressions.json"
    if entry_id == ENTRY_STARTUP_RUNTIME_REGRESSIONS:
        return repo_root / "evidence" / "QualityGate" / "startup_runtime_regressions.json"
    raise AssertionError(f"unsupported proof entry_id: {entry_id}")


def _success_log_path_for_entry(repo_root: Path, entry_id: str, stream: str) -> Path:
    success = json.loads(_success_path(repo_root, entry_id).read_text(encoding="utf-8"))
    return repo_root / str(success[f"{stream}_log_path"]).replace("/", "/")


def _summary_payload(token: str = "ok") -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "passed",
        "active_xfail_count": 0,
        "collected_count": 1,
        "collection_error_count": 0,
        "fixed_count": 0,
        "max_registered_xfail": 0,
        "unexpected_failure_count": 0,
        "active_xfail_entries": [],
        "token": token,
    }


def _write_full_test_debt_outputs(repo_root: Path, token: str = "ok") -> None:
    current = repo_root / "evidence" / "QualityGate" / "current_full_test_debt.json"
    summary = repo_root / "evidence" / "QualityGate" / "full_test_debt_summary.json"
    current.parent.mkdir(parents=True, exist_ok=True)
    current.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "baseline_kind": "after_main_style_isolation",
                "importable": False,
                "importable_blockers": [],
                "generated_at": "2026-05-13T00:00:00+08:00",
                "head_sha": "deadbeef",
                "collector_argv": ["--baseline-kind", "after_main_style_isolation", "--", "tests"],
                "git_status_short_before": [],
                "worktree_clean_before": True,
                "python_executable": sys.executable,
                "python_version": sys.version.splitlines()[0],
                "pytest_version": "8.3.5",
                "pytest_args": ["tests", "-q", "--tb=short", "-ra", "-p", "no:cacheprovider"],
                "exitstatus": 0,
                "collected_nodeids": ["tests/test_cached_collect.py::test_cached_collect"],
                "collection_errors": [],
                "reports": [],
                "summary": {
                    "collected_count": 1,
                    "failed_nodeid_count": 0,
                    "collection_error_count": 0,
                    "outcome_counts": {},
                    "classification_counts": {
                        "candidate_test_debt": 0,
                        "main_style_isolation_candidate": 0,
                        "required_or_quality_gate_self_failure": 0,
                    },
                },
                "classifications": {
                    "candidate_test_debt": [],
                    "main_style_isolation_candidate": [],
                    "required_or_quality_gate_self_failure": [],
                },
                "token": token,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    summary.write_text(json.dumps(_summary_payload(token), ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _fake_successful_command(
    command_plan: Sequence[Dict[str, Any]],
    repo_root: Path,
    calls: List[Dict[str, Any]],
    *,
    fail_entry_ids: Sequence[str] = (),
) -> Callable[..., dict]:
    manifest = _manifest_for(command_plan, repo_root)
    required_entry = _entry_by_id(manifest, ENTRY_REQUIRED_REGRESSIONS)
    required_display = str(required_entry["display"])
    startup_display = _entry_display(command_plan, repo_root, ENTRY_STARTUP_RUNTIME_REGRESSIONS)
    fail_ids = set(fail_entry_ids)
    full_debt_runs = {"count": 0}

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
        calls.append(
            {
                "display": str(display),
                "args": [str(arg) for arg in list(args or [])],
                "capture_output": bool(capture_output),
                "env_overlay": dict(env_overlay or {}),
            }
        )
        if display == "python -m pytest --collect-only -q tests":
            return {
                "stdout": "tests/test_cached_collect.py::test_cached_collect\n",
                "stderr": "",
                "returncode": 0,
            }
        if display == "python tools/check_full_test_debt.py":
            full_debt_runs["count"] += 1
            _write_full_test_debt_outputs(repo_root, token=f"run-{full_debt_runs['count']}")
            return {
                "stdout": json.dumps(_summary_payload("runner"), ensure_ascii=False),
                "stderr": "[check-full-test-debt] ok\n",
                "returncode": 0,
            }
        if display == "python -m ruff --version":
            return {"stdout": "ruff 0.15.4", "stderr": "", "returncode": 0}
        if display == "python -m pyright --version":
            return {"stdout": "pyright 1.1.406", "stderr": "", "returncode": 0}
        if display == required_display:
            if ENTRY_REQUIRED_REGRESSIONS in fail_ids:
                return {"stdout": "required failed\n", "stderr": "boom\n", "returncode": 1}
            return {"stdout": "127 files passed in 2.34s\n", "stderr": "", "returncode": 0}
        if display == startup_display:
            if ENTRY_STARTUP_RUNTIME_REGRESSIONS in fail_ids:
                return {"stdout": "startup failed\n", "stderr": "boom\n", "returncode": 1}
            return {"stdout": "16 passed in 1.23s\n", "stderr": "", "returncode": 0}
        return {"stdout": "", "stderr": "", "returncode": 0}

    return fake_run_command


def _seed_required_or_startup_success_cache(
    module,
    repo_root: Path,
    command_plan: Sequence[Dict[str, Any]],
    entry_id: str,
    *,
    stdout_text: str = "",
    stderr_text: str = "",
    proof_payload_overrides: Optional[Mapping[str, Any]] = None,
) -> None:
    if entry_id not in {
        ENTRY_REQUIRED_REGRESSIONS,
        ENTRY_STARTUP_RUNTIME_REGRESSIONS,
    }:
        raise AssertionError(f"unsupported proof entry_id: {entry_id}")

    manifest = _manifest_for(command_plan, repo_root)
    entry = _entry_by_id(manifest, entry_id)
    fingerprint = fingerprint_entry(entry, str(repo_root), strict=True)
    command_index = next(
        index for index, row in enumerate(manifest["entries"], start=1) if row["entry_id"] == entry_id
    )

    if not stdout_text:
        if entry_id == ENTRY_REQUIRED_REGRESSIONS:
            stdout_text = "127 files passed in 2.34s\n"
        else:
            stdout_text = "16 passed in 1.23s\n"

    proof_path = _proof_path_for_entry(repo_root, entry_id)
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_rel = f"evidence/QualityGate/long_gate/logs/{entry_id}.stdout.log"
    stderr_rel = f"evidence/QualityGate/long_gate/logs/{entry_id}.stderr.log"
    stdout_sha = hashlib.sha256(stdout_text.encode("utf-8")).hexdigest()
    stderr_sha = hashlib.sha256(stderr_text.encode("utf-8")).hexdigest()

    schema_version = (
        module.REQUIRED_REGRESSIONS_PROOF_SCHEMA_VERSION
        if entry_id == ENTRY_REQUIRED_REGRESSIONS
        else module.STARTUP_RUNTIME_REGRESSIONS_PROOF_SCHEMA_VERSION
    )
    proof_payload = {
        "schema_version": schema_version,
        "status": "passed",
        "entry_id": entry_id,
        "quality_gate_plan_hash": quality_gate_shared.hash_quality_gate_commands(command_plan),
        "command_index": command_index,
        "display": entry["display"],
        "args": entry["args"],
        "command_hash": entry["command_hash"],
        "fingerprint_schema_version": entry["fingerprint_schema_version"],
        "fingerprint_hash": fingerprint["hash"],
        "returncode": 0,
        "pytest_exit_code": 0,
        "execution_mode": "executed",
        "test_count": len(entry["args"][4:]),
        "stdout_log_path": stdout_rel,
        "stderr_log_path": stderr_rel,
        "logs": {
            "stdout": {"path": stdout_rel, "sha256": stdout_sha},
            "stderr": {"path": stderr_rel, "sha256": stderr_sha},
        },
        "stdout_sha256": stdout_sha,
        "stderr_sha256": stderr_sha,
    }
    if entry_id == ENTRY_REQUIRED_REGRESSIONS:
        proof_payload["required_target_count"] = len(entry["args"][4:])
        proof_payload["required_target_paths"] = entry["args"][4:]
    if entry_id == ENTRY_STARTUP_RUNTIME_REGRESSIONS:
        proof_payload["startup_target_count"] = len(entry["args"][4:])
        proof_payload["startup_target_paths"] = entry["args"][4:]
    if proof_payload_overrides:
        proof_payload.update(dict(proof_payload_overrides))

    with open(proof_path, "w", encoding="utf-8") as handle:
        json.dump(proof_payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    write_success(
        entry,
        fingerprint,
        {
            "stdout": stdout_text,
            "stderr": stderr_text,
            "returncode": 0,
            "duration_s": 3.0,
        },
        [str(proof_path)],
        repo_root=str(repo_root),
    )
    assert proof_path.exists()
    assert _success_path(repo_root, entry_id).exists()


def _run_gate_with_fake_commands(
    module,
    monkeypatch,
    repo_root: Path,
    command_plan: Sequence[Dict[str, Any]],
    args: Sequence[str],
    *,
    fail_entry_ids: Sequence[str] = (),
) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    monkeypatch.setattr(
        module,
        "_run_command",
        _fake_successful_command(command_plan, repo_root, calls, fail_entry_ids=fail_entry_ids),
    )
    assert module.main(list(args)) == 0
    return calls
