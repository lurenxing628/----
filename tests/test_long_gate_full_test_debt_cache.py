from __future__ import annotations

import hashlib
import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

import pytest

from tools.long_gate_cache import decide_reuse, write_success
from tools.long_gate_collect import build_collect_nodeids_payload, write_collect_nodeids
from tools.long_gate_fingerprint import fingerprint_entry
from tools.long_gate_full_test_debt import (
    NODE_CACHE_REL,
    _classify_incremental_plan,
    _load_node_cache,
    write_full_test_debt_node_cache_after_success,
)
from tools.long_gate_manifest import build_manifest_from_quality_gate_plan
from tools.long_gate_schema import stable_json_hash


def _repo_root() -> str:
    return str(Path(__file__).resolve().parents[1])


def _import_run_quality_gate():
    repo_root = _repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("scripts.run_quality_gate", None)
    return importlib.import_module("scripts.run_quality_gate")


def _full_debt_command() -> dict:
    return {
        "display": "python tools/check_full_test_debt.py",
        "args": ["python", "tools/check_full_test_debt.py"],
        "capture_output": True,
        "output_policy": "exact",
    }


def _collect_command() -> dict:
    return {
        "display": "python -m pytest --collect-only -q tests",
        "args": ["python", "-m", "pytest", "--collect-only", "-q", "tests"],
        "capture_output": True,
        "output_policy": "normalized",
    }


def _quality_gate_plan(*, include_planned: bool = False) -> list[dict]:
    plan = [_collect_command(), _full_debt_command()]
    if include_planned:
        plan.append(
            {
                "display": "python -m ruff check",
                "args": ["python", "-m", "ruff", "check"],
                "capture_output": False,
                "output_policy": "normalized",
            }
        )
    plan.extend(
        [
            {
                "display": "python -m ruff --version",
                "args": ["python", "-m", "ruff", "--version"],
                "capture_output": True,
                "output_policy": "exact",
            },
            {
                "display": "python -m pyright --version",
                "args": ["python", "-m", "pyright", "--version"],
                "capture_output": True,
                "output_policy": "normalized",
            },
        ]
    )
    return plan


def _patch_gate_environment(monkeypatch, module, repo_root: Path, *, statuses: Sequence[Sequence[str]]) -> None:
    if not (repo_root / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
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
    status_iter = iter([list(item) for item in statuses])
    monkeypatch.setattr(module, "_git_status_lines", lambda: next(status_iter))
    monkeypatch.setattr(module, "_run_git_bytes", lambda _args: b"")
    monkeypatch.setattr(module, "_runtime_state_snapshot", lambda: {"runtime_state": "absent"})


def _entry(repo_root: Path) -> dict:
    manifest = build_manifest_from_quality_gate_plan([_full_debt_command()], repo_root=str(repo_root))
    return manifest["entries"][0]


def _write_file(repo_root: Path, rel_path: str, text: str = "x\n") -> Path:
    path = repo_root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_collect_nodeids(repo_root: Path, stdout: str = "tests/test_a.py::test_a\n") -> str:
    payload = build_collect_nodeids_payload(
        stdout,
        pytest_version="pytest 8.3.5",
        collect_stdout_log_path="evidence/QualityGate/logs/collect.stdout.log",
    )
    return write_collect_nodeids(payload, repo_root=str(repo_root))


def _summary_payload(token: str = "ok") -> dict:
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


def _write_full_outputs(repo_root: Path, token: str = "ok") -> list[str]:
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
                "collected_nodeids": ["tests/test_a.py::test_a"],
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
    return [str(current), str(summary)]


def _write_node_cache_output(repo_root: Path, entry: dict, fingerprint: dict, token: str = "ok") -> str:
    stdout_text = json.dumps(_summary_payload(token), ensure_ascii=False)
    stderr_text = ""
    stdout_rel = "evidence/QualityGate/logs/full_test_debt.stdout.log"
    stderr_rel = "evidence/QualityGate/logs/full_test_debt.stderr.log"
    stdout_path = repo_root / stdout_rel
    stderr_path = repo_root / stderr_rel
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text(stdout_text, encoding="utf-8")
    stderr_path.write_text(stderr_text, encoding="utf-8")
    return write_full_test_debt_node_cache_after_success(
        repo_root=str(repo_root),
        entry=entry,
        fingerprint=fingerprint,
        result={
            "stdout": stdout_text,
            "stderr": stderr_text,
            "returncode": 0,
            "execution_mode": "executed",
            "stdout_log_path": stdout_rel,
            "stderr_log_path": stderr_rel,
        },
        cache_dir="evidence/QualityGate/long_gate",
    )


def _seed_success(repo_root: Path, *, token: str = "seed") -> tuple[dict, dict]:
    _write_file(repo_root, "tests/test_a.py", "def test_a():\n    assert True\n")
    _write_collect_nodeids(repo_root)
    outputs = _write_full_outputs(repo_root, token)
    entry = _entry(repo_root)
    fingerprint = fingerprint_entry(entry, str(repo_root))
    outputs.append(str(repo_root / _write_node_cache_output(repo_root, entry, fingerprint, token)))
    write_success(
        entry,
        fingerprint,
        {
            "stdout": json.dumps(_summary_payload(token), ensure_ascii=False),
            "stderr": "",
            "returncode": 0,
            "duration_s": 3.0,
        },
        outputs,
        repo_root=str(repo_root),
    )
    return entry, fingerprint


def _success_path(repo_root: Path, entry_id: str = "full_test_debt") -> Path:
    return repo_root / "evidence" / "QualityGate" / "long_gate" / "results" / f"{entry_id}.success.json"


def _load_success(repo_root: Path, entry_id: str = "full_test_debt") -> dict:
    return json.loads(_success_path(repo_root, entry_id).read_text(encoding="utf-8"))


def _summary_path(repo_root: Path) -> Path:
    return repo_root / "evidence" / "QualityGate" / "long_gate" / "summary.json"


def _load_summary(repo_root: Path) -> dict:
    return json.loads(_summary_path(repo_root).read_text(encoding="utf-8"))


def _summary_entry(summary: dict, entry_id: str) -> dict:
    for entry in summary["entries"]:
        if entry["entry_id"] == entry_id:
            return entry
    raise AssertionError(f"missing summary entry: {entry_id}")


def _fingerprint_from_file_hashes(file_hashes: dict[str, str]) -> dict:
    rows = [
        {
            "path": path,
            "exists": bool(value),
            "kind": "file" if value else "missing",
            "sha256": value,
        }
        for path, value in sorted(file_hashes.items())
    ]
    payload = {"schema_version": 1, "components": {"files": {"files": rows}}}
    payload["hash"] = f"sha256:{stable_json_hash(payload)}"
    return payload


def _collect_snapshot_for_tests() -> dict:
    return {
        "schema_version": 1,
        "status": "passed",
        "nodeids": [
            "tests/test_a.py::test_a",
            "tests/test_a.py::test_b",
            "tests/test_b.py::test_b",
        ],
        "nodeid_count": 3,
        "nodeid_hash": stable_json_hash(
            [
                "tests/test_a.py::test_a",
                "tests/test_a.py::test_b",
                "tests/test_b.py::test_b",
            ]
        ),
        "nodeids_by_file": {
            "tests/test_a.py": ["tests/test_a.py::test_a", "tests/test_a.py::test_b"],
            "tests/test_b.py": ["tests/test_b.py::test_b"],
        },
    }


def _empty_test_debt_ledger() -> dict:
    return {"test_debt": {"entries": []}}


def _fake_successful_command(module, repo_root: Path, calls: list[str]):
    full_debt_run_count = {"value": 0}

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        if display == "python -m pytest --collect-only -q tests":
            return {"stdout": "tests/test_a.py::test_a\n", "stderr": "", "returncode": 0}
        if display == "python tools/check_full_test_debt.py":
            full_debt_run_count["value"] += 1
            _write_full_outputs(repo_root, token=f"run-{full_debt_run_count['value']}")
            return {
                "stdout": json.dumps(_summary_payload("runner"), ensure_ascii=False),
                "stderr": "[check-full-test-debt] ok\n",
                "returncode": 0,
            }
        if display == "python -m ruff --version":
            return {"stdout": "ruff 0.15.4", "stderr": "", "returncode": 0}
        if display == "python -m pyright --version":
            return {"stdout": "pyright 1.1.406", "stderr": "", "returncode": 0}
        return {"stdout": "", "stderr": "", "returncode": 0}

    return fake_run_command


def test_manifest_enables_only_collect_and_full_test_debt():
    manifest = build_manifest_from_quality_gate_plan(_quality_gate_plan(include_planned=True), repo_root=_repo_root())

    enabled = [entry["entry_id"] for entry in manifest["entries"] if entry["reuse_allowed"]]
    planned = [entry["entry_id"] for entry in manifest["entries"] if entry["cache_status"] == "planned"]

    assert enabled == ["pytest_collect_all", "full_test_debt"]
    assert "ruff_check_full" in planned
    assert "full_test_debt_node_cache" in json.dumps(manifest, ensure_ascii=False)


def test_nodeid_incremental_plan_selects_changed_test_file_nodeids(tmp_path):
    _write_file(tmp_path, "tests/test_a.py", "before\n")
    _write_file(tmp_path, "tests/test_b.py", "same\n")
    previous = _fingerprint_from_file_hashes(
        {
            "tests/test_a.py": "old-a",
            "tests/test_b.py": hashlib.sha256(b"same\n").hexdigest(),
            "evidence/QualityGate/collect_nodeids.json": "old-collect",
        }
    )
    current = _fingerprint_from_file_hashes(
        {
            "tests/test_a.py": "new-a",
            "tests/test_b.py": hashlib.sha256(b"same\n").hexdigest(),
            "evidence/QualityGate/collect_nodeids.json": "new-collect",
        }
    )

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=previous,
        current_fingerprint=current,
        collect_snapshot=_collect_snapshot_for_tests(),
        node_cache={
            "collect_nodeids": _collect_snapshot_for_tests(),
            "test_file_hashes": {"tests/test_b.py": hashlib.sha256(b"same\n").hexdigest()},
        },
        ledger=_empty_test_debt_ledger(),
    )

    assert error == ""
    assert plan is not None
    assert plan["mode"] == "nodeid_incremental"
    assert plan["changed_test_files"] == ["tests/test_a.py"]
    assert plan["selected_nodeids"] == ["tests/test_a.py::test_a", "tests/test_a.py::test_b"]


def test_nodeid_incremental_plan_falls_back_when_non_file_fingerprint_changes(tmp_path):
    _write_file(tmp_path, "tests/test_a.py", "before\n")
    previous = _fingerprint_from_file_hashes({"tests/test_a.py": "old-a"})
    current = _fingerprint_from_file_hashes({"tests/test_a.py": "new-a"})
    previous["components"]["environment"] = {"hash": "old-env", "values": {"PYTEST_ADDOPTS": ""}}
    current["components"]["environment"] = {"hash": "new-env", "values": {"PYTEST_ADDOPTS": "-k smoke"}}
    previous["hash"] = f"sha256:{stable_json_hash(previous)}"
    current["hash"] = f"sha256:{stable_json_hash(current)}"

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=previous,
        current_fingerprint=current,
        collect_snapshot=_collect_snapshot_for_tests(),
        node_cache={
            "collect_nodeids": _collect_snapshot_for_tests(),
            "test_file_hashes": {"tests/test_b.py": hashlib.sha256(b"same\n").hexdigest()},
        },
        ledger=_empty_test_debt_ledger(),
    )

    assert plan is None
    assert error == "non-file fingerprint changed: environment"


def test_nodeid_incremental_plan_falls_back_when_changed_test_is_imported_elsewhere(tmp_path):
    _write_file(tmp_path, "tests/test_shared.py", "def helper():\n    return 1\n")
    _write_file(tmp_path, "tests/test_uses_shared.py", "from tests.test_shared import helper\n")
    previous = _fingerprint_from_file_hashes(
        {
            "tests/test_shared.py": "old-shared",
            "tests/test_uses_shared.py": hashlib.sha256(b"from tests.test_shared import helper\n").hexdigest(),
            "evidence/QualityGate/collect_nodeids.json": "old-collect",
        }
    )
    current = _fingerprint_from_file_hashes(
        {
            "tests/test_shared.py": "new-shared",
            "tests/test_uses_shared.py": hashlib.sha256(b"from tests.test_shared import helper\n").hexdigest(),
            "evidence/QualityGate/collect_nodeids.json": "new-collect",
        }
    )
    snapshot = build_collect_nodeids_payload(
        "tests/test_shared.py::test_shared\ntests/test_uses_shared.py::test_uses_shared\n",
        pytest_version="pytest 8.3.5",
    )

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=previous,
        current_fingerprint=current,
        collect_snapshot=snapshot,
        node_cache={
            "collect_nodeids": snapshot,
            "test_file_hashes": {
                "tests/test_uses_shared.py": hashlib.sha256(b"from tests.test_shared import helper\n").hexdigest(),
            },
        },
        ledger=_empty_test_debt_ledger(),
    )

    assert plan is None
    assert error == "changed test file is imported by another test file: tests/test_uses_shared.py"


def test_nodeid_incremental_plan_falls_back_when_changed_test_is_dynamically_imported(tmp_path):
    _write_file(tmp_path, "tests/test_shared.py", "def helper():\n    return 1\n")
    dynamic_text = "import importlib\nhelper = importlib.import_module('tests.test_shared').helper\n"
    _write_file(tmp_path, "tests/test_uses_shared.py", dynamic_text)
    previous = _fingerprint_from_file_hashes(
        {
            "tests/test_shared.py": "old-shared",
            "tests/test_uses_shared.py": hashlib.sha256(dynamic_text.encode("utf-8")).hexdigest(),
            "evidence/QualityGate/collect_nodeids.json": "old-collect",
        }
    )
    current = _fingerprint_from_file_hashes(
        {
            "tests/test_shared.py": "new-shared",
            "tests/test_uses_shared.py": hashlib.sha256(dynamic_text.encode("utf-8")).hexdigest(),
            "evidence/QualityGate/collect_nodeids.json": "new-collect",
        }
    )
    snapshot = build_collect_nodeids_payload(
        "tests/test_shared.py::test_shared\ntests/test_uses_shared.py::test_uses_shared\n",
        pytest_version="pytest 8.3.5",
    )

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=previous,
        current_fingerprint=current,
        collect_snapshot=snapshot,
        node_cache={
            "collect_nodeids": snapshot,
            "test_file_hashes": {
                "tests/test_uses_shared.py": hashlib.sha256(dynamic_text.encode("utf-8")).hexdigest(),
            },
        },
        ledger=_empty_test_debt_ledger(),
    )

    assert plan is None
    assert error == "changed test file is imported by another test file: tests/test_uses_shared.py"


def test_nodeid_incremental_plan_falls_back_when_changed_test_is_dunder_imported(tmp_path):
    _write_file(tmp_path, "tests/test_shared.py", "def helper():\n    return 1\n")
    dynamic_text = "helper = __import__('tests.test_shared', fromlist=['helper']).helper\n"
    _write_file(tmp_path, "tests/test_uses_shared.py", dynamic_text)
    previous = _fingerprint_from_file_hashes(
        {
            "tests/test_shared.py": "old-shared",
            "tests/test_uses_shared.py": hashlib.sha256(dynamic_text.encode("utf-8")).hexdigest(),
            "evidence/QualityGate/collect_nodeids.json": "old-collect",
        }
    )
    current = _fingerprint_from_file_hashes(
        {
            "tests/test_shared.py": "new-shared",
            "tests/test_uses_shared.py": hashlib.sha256(dynamic_text.encode("utf-8")).hexdigest(),
            "evidence/QualityGate/collect_nodeids.json": "new-collect",
        }
    )
    snapshot = build_collect_nodeids_payload(
        "tests/test_shared.py::test_shared\ntests/test_uses_shared.py::test_uses_shared\n",
        pytest_version="pytest 8.3.5",
    )

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=previous,
        current_fingerprint=current,
        collect_snapshot=snapshot,
        node_cache={
            "collect_nodeids": snapshot,
            "test_file_hashes": {
                "tests/test_uses_shared.py": hashlib.sha256(dynamic_text.encode("utf-8")).hexdigest(),
            },
        },
        ledger=_empty_test_debt_ledger(),
    )

    assert plan is None
    assert error == "changed test file is imported by another test file: tests/test_uses_shared.py"


@pytest.mark.parametrize(
    "changed_path",
    [
        "tests/conftest.py",
        "conftest.py",
        "core/service.py",
        "web/view.py",
        "data/repository.py",
        "plugins/demo.py",
        "pyproject.toml",
        "tools/check_full_test_debt.py",
    ],
)
def test_nodeid_incremental_plan_falls_back_for_unsafe_paths(tmp_path, changed_path):
    previous = _fingerprint_from_file_hashes({changed_path: "old"})
    current = _fingerprint_from_file_hashes({changed_path: "new"})

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=previous,
        current_fingerprint=current,
        collect_snapshot=_collect_snapshot_for_tests(),
        node_cache={"collect_nodeids": _collect_snapshot_for_tests(), "test_file_hashes": {}},
        ledger=_empty_test_debt_ledger(),
    )

    assert plan is None
    assert "outside safe test-file-only scope" in error


def test_ledger_only_plan_reuses_payload_without_nodeids(tmp_path):
    _write_file(tmp_path, "tests/test_a.py", "same\n")
    previous = _fingerprint_from_file_hashes({"开发文档/技术债务治理台账.md": "old"})
    current = _fingerprint_from_file_hashes({"开发文档/技术债务治理台账.md": "new"})
    snapshot = build_collect_nodeids_payload("tests/test_a.py::test_a\n", pytest_version="pytest 8.3.5")

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=previous,
        current_fingerprint=current,
        collect_snapshot=snapshot,
        node_cache={
            "collect_nodeids": snapshot,
            "test_file_hashes": {"tests/test_a.py": hashlib.sha256(b"same\n").hexdigest()},
        },
        ledger=_empty_test_debt_ledger(),
    )

    assert error == ""
    assert plan is not None
    assert plan["mode"] == "ledger_only"


def test_ledger_only_plan_rejects_bad_test_file_hashes(tmp_path):
    _write_file(tmp_path, "tests/test_a.py", "actual\n")
    previous = _fingerprint_from_file_hashes({"开发文档/技术债务治理台账.md": "old"})
    current = _fingerprint_from_file_hashes({"开发文档/技术债务治理台账.md": "new"})
    snapshot = build_collect_nodeids_payload("tests/test_a.py::test_a\n", pytest_version="pytest 8.3.5")

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=previous,
        current_fingerprint=current,
        collect_snapshot=snapshot,
        node_cache={"collect_nodeids": snapshot, "test_file_hashes": {"tests/test_a.py": "not-the-real-hash"}},
        ledger=_empty_test_debt_ledger(),
    )

    assert plan is None
    assert error == "node cache test file hash mismatch outside changed files: tests/test_a.py"


def test_nodeid_incremental_plan_falls_back_when_other_file_mapping_changes(tmp_path):
    _write_file(tmp_path, "tests/test_a.py", "before\n")
    _write_file(tmp_path, "tests/test_b.py", "same\n")
    previous = _fingerprint_from_file_hashes(
        {
            "tests/test_a.py": "old-a",
            "tests/test_b.py": hashlib.sha256(b"same\n").hexdigest(),
            "evidence/QualityGate/collect_nodeids.json": "old-collect",
        }
    )
    current = _fingerprint_from_file_hashes(
        {
            "tests/test_a.py": "new-a",
            "tests/test_b.py": hashlib.sha256(b"same\n").hexdigest(),
            "evidence/QualityGate/collect_nodeids.json": "new-collect",
        }
    )
    changed_collect = _collect_snapshot_for_tests()
    changed_collect["nodeids_by_file"] = {
        **changed_collect["nodeids_by_file"],
        "tests/test_b.py": ["tests/test_b.py::test_b[new param]"],
    }

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=previous,
        current_fingerprint=current,
        collect_snapshot=changed_collect,
        node_cache={
            "collect_nodeids": _collect_snapshot_for_tests(),
            "test_file_hashes": {"tests/test_b.py": hashlib.sha256(b"same\n").hexdigest()},
        },
        ledger=_empty_test_debt_ledger(),
    )

    assert plan is None
    assert error == "nodeid mapping changed outside changed test files: tests/test_b.py"


def test_corrupt_node_cache_is_not_trusted(tmp_path):
    cache_path = tmp_path / NODE_CACHE_REL
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps({"schema_version": 1, "payload_hash": "sha256:not-real"}, ensure_ascii=False),
        encoding="utf-8",
    )
    previous_success = {
        "fingerprint_hash": "sha256:old",
        "output_files": [{"path": NODE_CACHE_REL, "sha256": hashlib.sha256(cache_path.read_bytes()).hexdigest()}],
    }

    payload, error = _load_node_cache(str(tmp_path), previous_success)

    assert payload is None
    assert error == "node cache payload_hash mismatch"


def test_node_cache_must_cover_all_collect_files(tmp_path):
    entry, fingerprint = _seed_success(tmp_path)
    success = _load_success(tmp_path)
    cache_path = tmp_path / NODE_CACHE_REL
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    payload["test_file_hashes"] = {}
    payload["payload_hash"] = "sha256:" + stable_json_hash({key: value for key, value in payload.items() if key != "payload_hash"})
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    success["output_files"] = [
        {**row, "sha256": hashlib.sha256(cache_path.read_bytes()).hexdigest()}
        if row["path"] == NODE_CACHE_REL
        else row
        for row in success["output_files"]
    ]

    loaded, error = _load_node_cache(str(tmp_path), success)

    assert loaded is None
    assert error == "node cache test_file_hashes does not cover collect_nodeids files"


def test_node_cache_current_payload_nodeids_must_match_collect_nodeids(tmp_path):
    entry, fingerprint = _seed_success(tmp_path)
    success = _load_success(tmp_path)
    cache_path = tmp_path / NODE_CACHE_REL
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    payload["current_payload"] = {
        "schema_version": 2,
        "collected_nodeids": ["tests/test_other.py::test_other"],
    }
    payload["current_payload_hash"] = f"sha256:{stable_json_hash(payload['current_payload'])}"
    payload["payload_hash"] = "sha256:" + stable_json_hash({key: value for key, value in payload.items() if key != "payload_hash"})
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    success["output_files"] = [
        {**row, "sha256": hashlib.sha256(cache_path.read_bytes()).hexdigest()}
        if row["path"] == NODE_CACHE_REL
        else row
        for row in success["output_files"]
    ]

    loaded, error = _load_node_cache(str(tmp_path), success)

    assert loaded is None
    assert error == "node cache current payload collected_nodeids does not match collect_nodeids"


def test_node_cache_uses_persistent_success_logs_after_run_log_cleanup(tmp_path):
    entry, fingerprint = _seed_success(tmp_path)
    success = _load_success(tmp_path)
    shutil.rmtree(tmp_path / "evidence" / "QualityGate" / "logs")

    loaded, error = _load_node_cache(str(tmp_path), success)

    assert error == ""
    assert loaded is not None
    assert loaded["stdout_log_path"] == "evidence/QualityGate/long_gate/logs/full_test_debt.stdout.log"


def test_runner_writes_and_reuses_full_test_debt_success_cache(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], [], [], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    calls: list[str] = []
    monkeypatch.setattr(module, "_run_command", _fake_successful_command(module, repo_root, calls))

    assert module.main(["--long-gate-cache"]) == 0
    first_success = _load_success(repo_root)
    assert [row["path"] for row in first_success["output_files"]] == [
        "evidence/QualityGate/current_full_test_debt.json",
        "evidence/QualityGate/full_test_debt_summary.json",
        NODE_CACHE_REL,
    ]
    assert first_success["fingerprint"]["components"]["collect_nodeids"]["nodeid_hash"]
    assert "python tools/check_full_test_debt.py" in calls

    calls.clear()
    assert module.main(["--long-gate-cache"]) == 0

    assert "python tools/check_full_test_debt.py" not in calls
    summary = _load_summary(repo_root)
    full_debt = _summary_entry(summary, "full_test_debt")
    assert full_debt["execution_mode"] == "reused_success_cache"
    assert full_debt["previous_result_path"].endswith("full_test_debt.success.json")
    assert (repo_root / "evidence" / "QualityGate" / "current_full_test_debt.json").exists()
    assert (repo_root / "evidence" / "QualityGate" / "full_test_debt_summary.json").exists()
    assert "[long-gate-reuse]" in capsys.readouterr().out


@pytest.mark.parametrize(
    "rel_path",
    [
        "tests/test_a.py",
        "core/service.py",
        "web/view.py",
        "data/repository.py",
        "plugins/demo.py",
        "app.py",
        "config.py",
        "schema.sql",
        "assets/启动_排产系统_Chrome.bat",
        "installer/aps_win7.iss",
        "build_win7_onedir.bat",
        ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
        ".limcode/plans/2026-05-01-05_后续结构债治理与文档同步.plan.md",
        "templates/scheduler/gantt.html",
        "web_new_test/templates/scheduler/gantt.html",
        "templates_excel/转换输出/供应商配置.xlsx",
        "static/js/config_manual.js",
        "web_new_test/static/docs/scheduler_manual.md",
        "audit/README.md",
        "audit/2026-05/README.md",
        "docs/frontend_manual_audit_and_rewrite_blueprint.md",
        "evidence/README.md",
        "evidence/current/README.md",
        ".github/workflows/quality.yml",
        ".gitignore",
        "开发文档/技术债务治理台账.md",
        "pyproject.toml",
        "requirements-dev.txt",
        "tools/check_full_test_debt.py",
        "tools/collect_full_test_debt.py",
        "tools/test_debt_registry.py",
        "codestable/tools/validate-yaml.py",
    ],
)
def test_full_test_debt_cache_invalidates_when_declared_input_changes(tmp_path, rel_path):
    path = _write_file(tmp_path, rel_path, "before\n")
    entry, _fingerprint = _seed_success(tmp_path)

    path.write_text("after\n", encoding="utf-8")
    decision = decide_reuse(entry, fingerprint_entry(entry, str(tmp_path)), repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "input fingerprint changed"


def test_collect_nodeids_missing_or_bad_payload_is_not_reused(tmp_path):
    entry, _fingerprint = _seed_success(tmp_path)
    collect_path = tmp_path / "evidence" / "QualityGate" / "collect_nodeids.json"

    collect_path.unlink()
    decision = decide_reuse(entry, fingerprint_entry(entry, str(tmp_path)), repo_root=str(tmp_path))
    assert decision["decision"] == "run"
    assert decision["reason"] == "collect nodeids proof is invalid"

    collect_path.write_text(
        json.dumps({"status": "passed", "nodeid_hash": "abc", "nodeid_count": 1}),
        encoding="utf-8",
    )
    schema_bad_fingerprint = fingerprint_entry(entry, str(tmp_path))
    decision = decide_reuse(entry, schema_bad_fingerprint, repo_root=str(tmp_path))
    assert decision["decision"] == "run"
    assert decision["invalidated_by"] == [
        "collect_nodeids payload is invalid: collect_nodeids schema_version is invalid"
    ]

    collect_path.write_text(
        json.dumps({"schema_version": 1, "status": "passed", "nodeid_hash": "abc", "nodeid_count": 1}),
        encoding="utf-8",
    )
    no_nodeids_fingerprint = fingerprint_entry(entry, str(tmp_path))
    decision = decide_reuse(entry, no_nodeids_fingerprint, repo_root=str(tmp_path))
    assert decision["decision"] == "run"
    assert decision["invalidated_by"] == [
        "collect_nodeids payload is invalid: collect_nodeids nodeids must be a list of strings"
    ]

    collect_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "passed",
                "nodeids": [],
                "nodeid_count": 0,
                "nodeids_by_file": {},
            }
        ),
        encoding="utf-8",
    )
    bad_fingerprint = fingerprint_entry(entry, str(tmp_path))
    decision = decide_reuse(entry, bad_fingerprint, repo_root=str(tmp_path))
    assert decision["decision"] == "run"
    assert decision["invalidated_by"] == ["collect_nodeids payload is invalid: collect_nodeids nodeid_hash is missing"]
    with pytest.raises(ValueError, match="valid collect_nodeids proof"):
        write_success(
            entry,
            bad_fingerprint,
            {"stdout": "{}", "stderr": "", "returncode": 0},
            _write_full_outputs(tmp_path, "bad"),
            repo_root=str(tmp_path),
        )


def test_collect_nodeids_corrupt_payload_is_not_reused(tmp_path):
    entry, _fingerprint = _seed_success(tmp_path)
    collect_path = tmp_path / "evidence" / "QualityGate" / "collect_nodeids.json"

    corrupt_payloads = [
        lambda: collect_path.write_text("not json", encoding="utf-8"),
        lambda: collect_path.write_bytes(b"\xff"),
        lambda: collect_path.write_text("[]", encoding="utf-8"),
    ]
    for write_payload in corrupt_payloads:
        write_payload()
        decision = decide_reuse(entry, fingerprint_entry(entry, str(tmp_path)), repo_root=str(tmp_path))
        assert decision["decision"] == "run"
        assert decision["reason"] == "collect nodeids proof is invalid"
        assert decision["invalidated_by"][0].startswith("collect_nodeids payload is invalid:")


@pytest.mark.parametrize(
    ("patch", "expected_reason"),
    [
        ({"status": "failed"}, "collect_nodeids payload status is not passed"),
        ({"nodeid_count": 99}, "collect_nodeids payload is invalid: collect_nodeids nodeid_count does not match nodeids"),
        ({"nodeid_hash": "fake"}, "collect_nodeids payload is invalid: collect_nodeids nodeid_hash does not match nodeids"),
        (
            {"nodeids_by_file": {"other.py": ["other.py::test_other"]}},
            "collect_nodeids payload is invalid: collect_nodeids nodeids_by_file does not match nodeids",
        ),
    ],
)
def test_collect_nodeids_inconsistent_payload_is_not_reused(tmp_path, patch, expected_reason):
    entry, _fingerprint = _seed_success(tmp_path)
    collect_path = tmp_path / "evidence" / "QualityGate" / "collect_nodeids.json"
    payload = json.loads(collect_path.read_text(encoding="utf-8"))
    payload.update(patch)
    collect_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    decision = decide_reuse(entry, fingerprint_entry(entry, str(tmp_path)), repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == "collect nodeids proof is invalid"
    assert decision["invalidated_by"] == [expected_reason]


def test_collect_nodeids_nodeid_hash_change_invalidates_full_test_debt(tmp_path):
    entry, old_fingerprint = _seed_success(tmp_path)
    _write_collect_nodeids(tmp_path, "tests/test_a.py::test_a\ntests/test_b.py::test_b\n")
    changed = fingerprint_entry(entry, str(tmp_path))

    decision = decide_reuse(entry, changed, repo_root=str(tmp_path))

    assert changed["components"]["collect_nodeids"]["nodeid_hash"] != old_fingerprint["components"]["collect_nodeids"]["nodeid_hash"]
    assert decision["decision"] == "run"


@pytest.mark.parametrize(
    "rel_path",
    [
        "evidence/QualityGate/current_full_test_debt.json",
        "evidence/QualityGate/full_test_debt_summary.json",
    ],
)
def test_full_test_debt_output_missing_or_hash_mismatch_is_not_reused(tmp_path, rel_path):
    entry, _fingerprint = _seed_success(tmp_path)
    target = tmp_path / rel_path

    target.unlink()
    decision = decide_reuse(entry, fingerprint_entry(entry, str(tmp_path)), repo_root=str(tmp_path))
    assert decision["decision"] == "run"
    assert decision["reason"] == "previous output files missing or hash mismatch"

    _seed_success(tmp_path, token="fresh")
    target.write_text("tampered\n", encoding="utf-8")
    decision = decide_reuse(entry, fingerprint_entry(entry, str(tmp_path)), repo_root=str(tmp_path))
    assert decision["decision"] == "run"
    assert decision["reason"] == "previous output files missing or hash mismatch"


@pytest.mark.parametrize(
    ("field", "reason"),
    [
        ("timed_out", "previous result timed out"),
        ("interrupted", "previous result was interrupted"),
        ("partial_write", "previous result was partially written"),
    ],
)
def test_full_test_debt_timeout_interrupted_or_partial_success_is_not_reused(tmp_path, field, reason):
    entry, _fingerprint = _seed_success(tmp_path)
    success = _load_success(tmp_path)
    success[field] = True
    _success_path(tmp_path).write_text(json.dumps(success), encoding="utf-8")

    decision = decide_reuse(entry, fingerprint_entry(entry, str(tmp_path)), repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"] == reason


def test_full_test_debt_non_utf8_log_is_not_reused(tmp_path):
    entry, _fingerprint = _seed_success(tmp_path)
    success = _load_success(tmp_path)
    stdout_log = tmp_path / success["stdout_log_path"]
    stdout_log.write_bytes(b"\xff")
    success["stdout_sha256"] = hashlib.sha256(b"\xff").hexdigest()
    _success_path(tmp_path).write_text(json.dumps(success), encoding="utf-8")

    decision = decide_reuse(entry, fingerprint_entry(entry, str(tmp_path)), repo_root=str(tmp_path))

    assert decision["decision"] == "run"
    assert decision["reason"].startswith("previous logs unreadable as utf-8")


def test_explain_full_test_debt_writes_no_proof_files(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: _quality_gate_plan())

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("explain must not execute commands")

    monkeypatch.setattr(module, "_run_command", fail_if_called)

    assert module.main(["--long-gate-cache-explain", "--long-gate-force-rerun", "full_test_debt"]) == 0
    assert not _summary_path(repo_root).exists()
    assert not _success_path(repo_root).exists()
    assert not (repo_root / "evidence" / "QualityGate" / "quality_gate_manifest.json").exists()
    assert not (repo_root / "evidence" / "QualityGate" / "current_full_test_debt.json").exists()
    assert not (repo_root / "evidence" / "QualityGate" / "full_test_debt_summary.json").exists()


def test_force_rerun_full_test_debt_refreshes_only_that_enabled_entry(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _quality_gate_plan(include_planned=True)
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], [], [], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    calls: list[str] = []
    monkeypatch.setattr(module, "_run_command", _fake_successful_command(module, repo_root, calls))
    assert module.main(["--long-gate-cache"]) == 0
    first_success = _load_success(repo_root)
    first_output_hashes = [row["sha256"] for row in first_success["output_files"]]
    monkeypatch.setattr(
        module,
        "try_run_special_full_test_debt_mode",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("force rerun must not call nodeid incremental")),
    )

    calls.clear()
    assert module.main(["--long-gate-cache", "--long-gate-force-rerun", "full_test_debt"]) == 0

    summary = _load_summary(repo_root)
    collect = _summary_entry(summary, "pytest_collect_all")
    full_debt = _summary_entry(summary, "full_test_debt")
    planned = _summary_entry(summary, "ruff_check_full")
    assert "python -m pytest --collect-only -q tests" not in calls
    assert "python tools/check_full_test_debt.py" in calls
    assert collect["execution_mode"] == "reused_success_cache"
    assert full_debt["execution_mode"] == "executed"
    assert full_debt["reason"] == "forced by --long-gate-force-rerun full_test_debt"
    assert [row["sha256"] for row in _load_success(repo_root)["output_files"]] != first_output_hashes
    assert planned["decision"] == "planned_only"
    assert planned["cache_status"] == "planned"
    assert not _success_path(repo_root, "ruff_check_full").exists()
    assert (repo_root / "evidence" / "QualityGate" / "full_test_debt_node_cache.json").exists()


def test_force_rerun_all_refreshes_full_test_debt_and_keeps_planned_entries(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _quality_gate_plan(include_planned=True)
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], [], [], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    calls: list[str] = []
    monkeypatch.setattr(module, "_run_command", _fake_successful_command(module, repo_root, calls))
    assert module.main(["--long-gate-cache"]) == 0
    first_success = _load_success(repo_root)
    first_output_hashes = [row["sha256"] for row in first_success["output_files"]]
    monkeypatch.setattr(
        module,
        "try_run_special_full_test_debt_mode",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("force rerun all must not call nodeid incremental")),
    )

    calls.clear()
    assert module.main(["--long-gate-cache", "--long-gate-force-rerun-all"]) == 0

    summary = _load_summary(repo_root)
    collect = _summary_entry(summary, "pytest_collect_all")
    full_debt = _summary_entry(summary, "full_test_debt")
    planned = _summary_entry(summary, "ruff_check_full")
    assert "python -m pytest --collect-only -q tests" in calls
    assert "python tools/check_full_test_debt.py" in calls
    assert collect["reason"] == "forced by --long-gate-force-rerun-all"
    assert full_debt["reason"] == "forced by --long-gate-force-rerun-all"
    assert full_debt["execution_mode"] == "executed"
    assert [row["sha256"] for row in _load_success(repo_root)["output_files"]] != first_output_hashes
    assert planned["decision"] == "planned_only"
    assert planned["cache_status"] == "planned"
    assert not _success_path(repo_root, "ruff_check_full").exists()


def test_full_test_debt_rechecks_collect_hash_after_collect_rerun(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], [], [], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    calls: list[str] = []
    collect_stdout = {"text": "tests/test_a.py::test_a\n"}

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        if display == "python -m pytest --collect-only -q tests":
            return {"stdout": collect_stdout["text"], "stderr": "", "returncode": 0}
        if display == "python tools/check_full_test_debt.py":
            _write_full_outputs(repo_root, token=f"full-{calls.count(display)}")
            return {"stdout": json.dumps(_summary_payload("full"), ensure_ascii=False), "stderr": "", "returncode": 0}
        if display == "python -m ruff --version":
            return {"stdout": "ruff 0.15.4", "stderr": "", "returncode": 0}
        if display == "python -m pyright --version":
            return {"stdout": "pyright 1.1.406", "stderr": "", "returncode": 0}
        return {"stdout": "", "stderr": "", "returncode": 0}

    monkeypatch.setattr(module, "_run_command", fake_run_command)
    assert module.main(["--long-gate-cache"]) == 0

    collect_stdout["text"] = "tests/test_a.py::test_a\ntests/test_b.py::test_b\n"
    calls.clear()
    assert module.main(["--long-gate-cache", "--long-gate-force-rerun", "pytest_collect_all"]) == 0

    summary = _load_summary(repo_root)
    full_debt = _summary_entry(summary, "full_test_debt")
    success = _load_success(repo_root)
    assert "python -m pytest --collect-only -q tests" in calls
    assert "python tools/check_full_test_debt.py" in calls
    assert full_debt["decision"] == "run"
    assert full_debt["reason"] == "input fingerprint changed"
    assert full_debt["execution_mode"] == "executed"
    assert success["fingerprint"]["components"]["collect_nodeids"]["nodeid_count"] == 2


def test_runner_records_nodeid_incremental_mode_without_running_whole_entry(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], [], [], [], [], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    calls: list[str] = []
    monkeypatch.setattr(module, "_run_command", _fake_successful_command(module, repo_root, calls))

    assert module.main(["--long-gate-cache"]) == 0
    _write_file(repo_root, "tests/test_a.py", "def test_a():\n    assert 1 == 1\n# changed\n")
    calls.clear()
    special_calls: list[dict] = []

    def fake_special(**kwargs):
        special_calls.append(dict(kwargs.get("decision") or {}))
        _write_full_outputs(repo_root, token="incremental")
        return {
            "stdout": json.dumps(_summary_payload("incremental"), ensure_ascii=False),
            "stderr": "[long-gate-full-test-debt] nodeid incremental ok\n",
            "returncode": 0,
            "execution_mode": "nodeid_incremental",
            "reused_from": {
                "node_cache_path": NODE_CACHE_REL,
                "previous_result_path": kwargs["decision"].get("previous_result_path") or "",
                "fingerprint_hash": kwargs["decision"].get("current_fingerprint_hash") or "sha256:previous",
            },
        }

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        if display == "python -m pytest --collect-only -q tests":
            return {"stdout": "tests/test_a.py::test_a\n", "stderr": "", "returncode": 0}
        if display == "python tools/check_full_test_debt.py":
            raise AssertionError("whole full_test_debt command should not run during nodeid incremental mode")
        if display == "python -m ruff --version":
            return {"stdout": "ruff 0.15.4", "stderr": "", "returncode": 0}
        if display == "python -m pyright --version":
            return {"stdout": "pyright 1.1.406", "stderr": "", "returncode": 0}
        return {"stdout": "", "stderr": "", "returncode": 0}

    monkeypatch.setattr(module, "try_run_special_full_test_debt_mode", fake_special)
    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--long-gate-cache"]) == 0

    summary = _load_summary(repo_root)
    full_debt = _summary_entry(summary, "full_test_debt")
    assert special_calls
    assert "python tools/check_full_test_debt.py" not in calls
    assert full_debt["execution_mode"] == "nodeid_incremental"
    assert summary["counts"]["executed"] >= 1
    assert NODE_CACHE_REL in [row["path"] for row in _load_success(repo_root)["output_files"]]


def test_runner_fails_when_nodeid_incremental_fails(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], [], [], [], [], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    calls: list[str] = []
    monkeypatch.setattr(module, "_run_command", _fake_successful_command(module, repo_root, calls))

    assert module.main(["--long-gate-cache"]) == 0
    _write_file(repo_root, "tests/test_a.py", "def test_a():\n    assert False\n")
    calls.clear()

    def fake_special(**kwargs):
        return {
            "stdout": "incremental failed\n",
            "stderr": "nodeid failed\n",
            "returncode": 1,
            "execution_mode": "nodeid_incremental",
            "reused_from": {
                "node_cache_path": NODE_CACHE_REL,
                "previous_result_path": kwargs["decision"].get("previous_result_path") or "",
                "fingerprint_hash": kwargs["decision"].get("current_fingerprint_hash") or "sha256:previous",
            },
        }

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        if display == "python -m pytest --collect-only -q tests":
            return {"stdout": "tests/test_a.py::test_a\n", "stderr": "", "returncode": 0}
        if display == "python tools/check_full_test_debt.py":
            raise AssertionError("whole full_test_debt command must not hide incremental failure")
        if display == "python -m ruff --version":
            return {"stdout": "ruff 0.15.4", "stderr": "", "returncode": 0}
        if display == "python -m pyright --version":
            return {"stdout": "pyright 1.1.406", "stderr": "", "returncode": 0}
        return {"stdout": "", "stderr": "", "returncode": 0}

    monkeypatch.setattr(module, "try_run_special_full_test_debt_mode", fake_special)
    monkeypatch.setattr(module, "_run_command", fake_run_command)

    with pytest.raises(module.QualityGateError):
        module.main(["--long-gate-cache"])

    full_debt = _summary_entry(_load_summary(repo_root), "full_test_debt")
    assert full_debt["failed"] is True
    assert full_debt["execution_mode"] == "nodeid_incremental"
    assert "python tools/check_full_test_debt.py" not in calls


def test_no_long_gate_cache_does_not_call_nodeid_incremental(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    monkeypatch.setattr(
        module,
        "try_run_special_full_test_debt_mode",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("--no-long-gate-cache must not call nodeid mode")),
    )
    calls: list[str] = []
    monkeypatch.setattr(module, "_run_command", _fake_successful_command(module, repo_root, calls))

    assert module.main(["--no-long-gate-cache"]) == 0

    assert "python tools/check_full_test_debt.py" in calls
    assert not _summary_path(repo_root).exists()
    assert not _success_path(repo_root).exists()


def test_full_test_debt_can_reuse_after_collect_repairs_missing_nodeids(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    collect_stdout = "tests/test_a.py::test_a\n"
    _write_file(repo_root, "tests/test_a.py", "def test_a():\n    assert True\n")
    write_collect_nodeids(
        build_collect_nodeids_payload(
            collect_stdout,
            pytest_version=module.pytest_distribution_version(strict=True),
            collect_stdout_log_path=module._expected_command_log_rel_paths(
                1, "python -m pytest --collect-only -q tests"
            )["stdout_log_path"],
        ),
        repo_root=str(repo_root),
    )
    outputs = _write_full_outputs(repo_root, token="seed")
    entry = _entry(repo_root)
    fingerprint = fingerprint_entry(entry, str(repo_root))
    outputs.append(str(repo_root / _write_node_cache_output(repo_root, entry, fingerprint, "seed")))
    write_success(
        entry,
        fingerprint,
        {
            "stdout": json.dumps(_summary_payload("seed"), ensure_ascii=False),
            "stderr": "",
            "returncode": 0,
            "duration_s": 3.0,
        },
        outputs,
        repo_root=str(repo_root),
    )
    (repo_root / "evidence" / "QualityGate" / "collect_nodeids.json").unlink()
    calls: list[str] = []

    def fake_run_command(display, args, capture_output=False):
        calls.append(display)
        if display == "python -m pytest --collect-only -q tests":
            return {"stdout": collect_stdout, "stderr": "", "returncode": 0}
        if display == "python tools/check_full_test_debt.py":
            raise AssertionError("full_test_debt should reuse after collect repairs nodeids")
        if display == "python -m ruff --version":
            return {"stdout": "ruff 0.15.4", "stderr": "", "returncode": 0}
        if display == "python -m pyright --version":
            return {"stdout": "pyright 1.1.406", "stderr": "", "returncode": 0}
        return {"stdout": "", "stderr": "", "returncode": 0}

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    assert module.main(["--long-gate-cache"]) == 0

    full_debt = _summary_entry(_load_summary(repo_root), "full_test_debt")
    assert "python -m pytest --collect-only -q tests" in calls
    assert "python tools/check_full_test_debt.py" not in calls
    assert full_debt["execution_mode"] == "reused_success_cache"
    assert full_debt["decision"] == "reuse"
