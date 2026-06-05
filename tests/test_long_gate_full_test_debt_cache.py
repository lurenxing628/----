"""回归测试：守护 long_gate full_test_debt 增量缓存与复用决策——指纹/节点缓存校验、_classify_incremental_plan 选取改动测试文件与函数体级精确 nodeid（拒绝不安全改动并记录回退原因）、声明式 helper 影响映射、previous_success 返回码校验与缓存命中复用。"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pytest

from tools import long_gate_fingerprint as fingerprint_mod
from tools import long_gate_full_test_debt as full_debt_mod
from tools.long_gate_cache import decide_reuse, write_success
from tools.long_gate_collect import build_collect_nodeids_payload, write_collect_nodeids
from tools.long_gate_fingerprint import fingerprint_entry
from tools.long_gate_full_test_debt import (
    NODE_CACHE_REL,
    _build_ledger_only_payload,
    _classify_incremental_plan,
    _load_node_cache,
    _merge_payload,
    _source_may_import_changed_test_module,
    _validated_previous_success,
    write_full_test_debt_node_cache_after_success,
)
from tools.long_gate_manifest import build_manifest_from_quality_gate_plan
from tools.long_gate_schema import stable_json_hash
from tools.long_gate_test_body_diff import select_precise_body_nodeids
from tools.quality_gate_shared import LEDGER_BEGIN, LEDGER_END
from tools.test_registry import iter_test_only_helper_impacts
from tools.test_registry import test_only_helper_impacts_for_path as helper_impacts_for_path


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


def _quality_gate_plan(*, include_planned: bool = False) -> List[Dict[str, Any]]:
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
    monkeypatch.setattr(module, "_assert_pyright_tools_coverage", lambda: None)
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
    monkeypatch.setattr(fingerprint_mod, "_git_executable_realpath", lambda environment=None: "/stable/git")
    monkeypatch.setattr(fingerprint_mod, "_git_version", lambda strict=False, environment=None: "git version 2.50.0")
    monkeypatch.setattr(fingerprint_mod, "_node_executable_realpath", lambda environment=None: "/stable/node")
    monkeypatch.setattr(fingerprint_mod, "_node_version", lambda strict=False, environment=None: "v24.0.0")
    monkeypatch.setattr(
        fingerprint_mod,
        "_node_browser_runtime_capability",
        lambda strict=False, environment=None: "stable-node-browser-runtime-capability",
    )


def _entry(repo_root: Path) -> dict:
    manifest = build_manifest_from_quality_gate_plan([_full_debt_command()], repo_root=str(repo_root))
    return manifest["entries"][0]


def _write_file(repo_root: Path, rel_path: str, text: str = "x\n") -> Path:
    path = repo_root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _git_commit_all(repo_root: Path, message: str = "seed") -> str:
    if not (repo_root / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=repo_root, check=True)
        subprocess.run(["git", "config", "user.name", "Tests"], cwd=repo_root, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo_root, check=True)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()


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


def _passed_report(nodeid: str) -> dict:
    return {
        "nodeid": nodeid,
        "when": "call",
        "outcome": "passed",
        "longrepr": "",
        "xfail_marker_present": False,
        "xfail_marker_reason": "",
        "xfail_marker_strict": False,
        "xfail_marker_run": True,
        "wasxfail_reason": "",
        "strict_xpass": False,
    }


def _failed_report(nodeid: str) -> dict:
    report = _passed_report(nodeid)
    report["outcome"] = "failed"
    report["longrepr"] = "AssertionError: selected nodeid failed"
    return report


def _current_payload_for_nodeids(nodeids: Sequence[str]) -> dict:
    reports = [_passed_report(str(nodeid)) for nodeid in nodeids]
    return {
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
        "collected_nodeids": list(nodeids),
        "collection_errors": [],
        "reports": reports,
        "summary": {
            "collected_count": len(list(nodeids)),
            "failed_nodeid_count": 0,
            "collection_error_count": 0,
            "outcome_counts": {"passed": len(reports)},
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
    }


def _write_full_outputs(repo_root: Path, token: str = "ok") -> List[str]:
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


def _seed_success(repo_root: Path, *, token: str = "seed") -> Tuple[dict, dict]:
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


def _failure_path(repo_root: Path, entry_id: str = "full_test_debt") -> Path:
    return repo_root / "evidence" / "QualityGate" / "long_gate" / "results" / f"{entry_id}.failure.json"


def _load_success(repo_root: Path, entry_id: str = "full_test_debt") -> dict:
    return json.loads(_success_path(repo_root, entry_id).read_text(encoding="utf-8"))


def _load_failure(repo_root: Path, entry_id: str = "full_test_debt") -> dict:
    return json.loads(_failure_path(repo_root, entry_id).read_text(encoding="utf-8"))


def _summary_path(repo_root: Path) -> Path:
    return repo_root / "evidence" / "QualityGate" / "long_gate" / "summary.json"


def _load_summary(repo_root: Path) -> dict:
    return json.loads(_summary_path(repo_root).read_text(encoding="utf-8"))


def _summary_entry(summary: dict, entry_id: str) -> dict:
    for entry in summary["entries"]:
        if entry["entry_id"] == entry_id:
            return entry
    raise AssertionError(f"missing summary entry: {entry_id}")


def _fingerprint_from_file_hashes(file_hashes: Dict[str, str]) -> dict:
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


def _collect_snapshot_for_mapping(nodeids_by_file: dict) -> dict:
    nodeids = []
    for path in sorted(nodeids_by_file):
        nodeids.extend(str(item) for item in list(nodeids_by_file[path]))
    return {
        "schema_version": 1,
        "status": "passed",
        "nodeids": nodeids,
        "nodeid_count": len(nodeids),
        "nodeid_hash": stable_json_hash(nodeids),
        "nodeids_by_file": {str(path): list(values) for path, values in nodeids_by_file.items()},
    }


def _empty_test_debt_ledger() -> dict:
    return {"test_debt": {"entries": []}}


def test_precise_body_selector_selects_changed_parameterized_variants() -> None:
    old_source = "\n".join(
        [
            "import pytest",
            "",
            "@pytest.mark.parametrize('value', [1, 2])",
            "def test_a(value):",
            "    local = 1",
            "    assert True",
            "",
            "def test_b():",
            "    assert True",
            "",
        ]
    )
    new_source = old_source.replace("    local = 1\n", "    local = 2\n")

    selection, error = select_precise_body_nodeids(
        path="tests/test_sample.py",
        old_source=old_source,
        new_source=new_source,
        nodeids=[
            "tests/test_sample.py::test_a[1]",
            "tests/test_sample.py::test_a[2]",
            "tests/test_sample.py::test_b",
        ],
    )

    assert error == ""
    assert selection is not None
    assert selection["selection_scope"] == "test_function_body"
    assert selection["merge_policy"] == "replace_reports_for_selected_nodeids"
    assert selection["selected_nodeids"] == [
        "tests/test_sample.py::test_a[1]",
        "tests/test_sample.py::test_a[2]",
    ]
    assert selection["changed_functions"] == [
        {
            "path": "tests/test_sample.py",
            "qualname": "test_a",
            "nodeid_prefix": "tests/test_sample.py::test_a",
        }
    ]


@pytest.mark.parametrize(
    ("old_source", "new_source", "expected_error"),
    [
        (
            "def test_a():\n    assert True\n",
            "@pytest.mark.slow\ndef test_a():\n    assert True\n",
            "outside test function bodies",
        ),
        (
            "import os\n\ndef test_a():\n    assert True\n",
            "import os\n\ndef test_a():\n    os.environ['X'] = '1'\n",
            "unsafe statement",
        ),
        (
            "import os\n\ndef test_a():\n    assert True\n",
            "import os\n\ndef test_a():\n    os.environ.update({'X': '1'})\n",
            "unsafe statement",
        ),
        (
            "CACHE = {}\n\ndef test_a():\n    assert True\n",
            "CACHE = {}\n\ndef test_a():\n    CACHE['x'] = 1\n",
            "unsafe statement",
        ),
        (
            "CACHE = []\n\ndef test_a():\n    assert True\n",
            "CACHE = []\n\ndef test_a():\n    CACHE.append(1)\n",
            "unsafe statement",
        ),
        (
            "CACHE = {}\n\ndef test_a():\n    assert True\n",
            "CACHE = {}\n\ndef test_a():\n    data = CACHE\n    data['x'] = 2\n",
            "unsafe expression",
        ),
        (
            "def test_a(fixture):\n    assert True\n",
            "def test_a(fixture):\n    obj = fixture\n    obj.value = 2\n",
            "unsafe expression",
        ),
        (
            "CACHE = {}\n\ndef test_a():\n    value = False\n    if value:\n        CACHE['x'] = 1\n    assert True\n",
            "CACHE = {}\n\ndef test_a():\n    value = True\n    if value:\n        CACHE['x'] = 1\n    assert True\n",
            "unsafe statement",
        ),
        (
            "CACHE = {}\n\ndef test_a():\n    if False:\n        CACHE['x'] = 1\n    assert True\n",
            "CACHE = {}\n\ndef test_a():\n    if True:\n        CACHE['x'] = 1\n    assert True\n",
            "unsafe statement",
        ),
        (
            "def test_a():\n    assert True\n",
            "def test_a():\n    import os\n    assert os.name\n",
            "unsafe statement",
        ),
        (
            "class Evil:\n    @property\n    def x(self):\n        return 1\nEVIL = Evil()\n\ndef test_a():\n    assert True\n",
            "class Evil:\n    @property\n    def x(self):\n        return 1\nEVIL = Evil()\n\ndef test_a():\n    assert EVIL.x == 1\n",
            "unsafe expression",
        ),
        (
            "def test_a(a, b):\n    assert True\n",
            "def test_a(a, b):\n    assert a == b\n",
            "unsafe expression",
        ),
        (
            "def test_a():\n    value = 1\n    assert True\n\ndef test_b():\n    test_a()\n",
            "def test_a():\n    value = 2\n    assert True\n\ndef test_b():\n    test_a()\n",
            "referenced by another test body",
        ),
    ],
)
def test_precise_body_selector_rejects_unsafe_body_precision(old_source, new_source, expected_error) -> None:
    selection, error = select_precise_body_nodeids(
        path="tests/test_sample.py",
        old_source=old_source,
        new_source=new_source,
        nodeids=["tests/test_sample.py::test_a", "tests/test_sample.py::test_b"],
    )

    assert selection is None
    assert expected_error in error


def test_precise_body_selector_allows_local_assignment_inside_changed_test() -> None:
    old_source = "def test_a():\n    value = 1\n    assert True\n\ndef test_b():\n    assert True\n"
    new_source = "def test_a():\n    value = 2\n    assert True\n\ndef test_b():\n    assert True\n"

    selection, error = select_precise_body_nodeids(
        path="tests/test_sample.py",
        old_source=old_source,
        new_source=new_source,
        nodeids=["tests/test_sample.py::test_a", "tests/test_sample.py::test_b"],
    )

    assert error == ""
    assert selection is not None
    assert selection["selected_nodeids"] == ["tests/test_sample.py::test_a"]


def _write_ledger_file(repo_root: Path, ledger: Optional[dict] = None) -> Path:
    payload = ledger if ledger is not None else _empty_test_debt_ledger()
    path = repo_root / "开发文档" / "技术债务治理台账.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# 技术债务治理台账",
                "",
                LEDGER_BEGIN,
                "```json",
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                "```",
                LEDGER_END,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _fake_successful_command(module, repo_root: Path, calls: List[str]):
    full_debt_run_count = {"value": 0}

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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


def test_manifest_enables_collect_full_test_debt_and_static_entries():
    manifest = build_manifest_from_quality_gate_plan(_quality_gate_plan(include_planned=True), repo_root=_repo_root())

    enabled = [entry["entry_id"] for entry in manifest["entries"] if entry["reuse_allowed"]]

    assert enabled == ["pytest_collect_all", "full_test_debt", "ruff_check_full"]
    assert "pyright_tools_full" not in enabled
    assert "full_test_debt_node_cache" in json.dumps(manifest, ensure_ascii=False)


def test_validated_previous_success_accepts_zero_returncode(tmp_path):
    _seed_success(tmp_path)

    previous, error = _validated_previous_success(
        repo_root=str(tmp_path),
        decision={"previous_result_path": "evidence/QualityGate/long_gate/results/full_test_debt.success.json"},
        evaluation={},
    )

    assert error == ""
    assert previous is not None
    assert previous["returncode"] == 0


@pytest.mark.parametrize(
    ("value", "expected_error"),
    [
        (None, "previous success cache returncode is invalid"),
        (False, "previous success cache returncode is invalid"),
        ("0", "previous success cache returncode is invalid"),
        (1, "previous success cache returncode is not zero"),
    ],
)
def test_validated_previous_success_rejects_invalid_or_nonzero_returncode(tmp_path, value, expected_error):
    _seed_success(tmp_path)
    success = _load_success(tmp_path)
    if value is None:
        success.pop("returncode", None)
    else:
        success["returncode"] = value
    _success_path(tmp_path).write_text(json.dumps(success, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    previous, error = _validated_previous_success(
        repo_root=str(tmp_path),
        decision={"previous_result_path": "evidence/QualityGate/long_gate/results/full_test_debt.success.json"},
        evaluation={},
    )

    assert previous is None
    assert error == expected_error


def test_full_test_debt_fingerprint_ignores_irrelevant_path_append(monkeypatch, tmp_path):
    entry = _entry(tmp_path)
    before = fingerprint_entry(entry, str(tmp_path))

    current_path = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", f"{current_path}{os.pathsep}/tmp/next7-transient-path")
    after = fingerprint_entry(entry, str(tmp_path))

    assert before["hash"] == after["hash"]



def test_node_cache_records_readable_diagnostic_fields(tmp_path):
    entry, fingerprint = _seed_success(tmp_path)
    cache_path = tmp_path / NODE_CACHE_REL
    payload = json.loads(cache_path.read_text(encoding="utf-8"))

    assert entry["entry_id"] == "full_test_debt"
    assert payload["result_returncode"] == 0
    assert payload["execution_mode"] == "executed"
    assert payload["collected_nodeid_count"] == 1
    assert payload["collect_nodeids_by_file_count"] == 1
    assert payload["fingerprint_hash"] == fingerprint["hash"]


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
    assert plan["safety_checks"] == {
        "collect_nodeids_valid": True,
        "node_cache_valid": True,
        "unchanged_test_hashes_valid": True,
        "unchanged_nodeid_mapping_valid": True,
        "changed_test_imported_elsewhere": False,
        "registered_debt_nodeid_in_changed_files": False,
        "declared_helper_impacts_valid": True,
        "actual_helper_imports_within_declared_impacts": True,
    }


def test_nodeid_incremental_plan_selects_only_changed_test_body_nodeids(tmp_path):
    old_source = (
        "def test_a():\n"
        "    value = 1\n"
        "    assert True\n"
        "\n"
        "def test_b():\n"
        "    assert True\n"
    )
    new_source = old_source.replace("    value = 1\n", "    value = 2\n")
    _write_file(tmp_path, "tests/test_a.py", old_source)
    old_head = _git_commit_all(tmp_path)
    _write_file(tmp_path, "tests/test_a.py", new_source)
    old_hash = hashlib.sha256(old_source.encode("utf-8")).hexdigest()
    new_hash = hashlib.sha256(new_source.encode("utf-8")).hexdigest()
    snapshot = _collect_snapshot_for_mapping(
        {
            "tests/test_a.py": ["tests/test_a.py::test_a", "tests/test_a.py::test_b"],
        }
    )

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=_fingerprint_from_file_hashes({"tests/test_a.py": old_hash}),
        current_fingerprint=_fingerprint_from_file_hashes({"tests/test_a.py": new_hash}),
        collect_snapshot=snapshot,
        node_cache={
            "head_sha": old_head,
            "collect_nodeids": snapshot,
            "test_file_hashes": {"tests/test_a.py": old_hash},
        },
        ledger=_empty_test_debt_ledger(),
    )

    assert error == ""
    assert plan is not None
    assert plan["mode"] == "nodeid_incremental"
    assert plan["safe_scope_kind"] == "test_function_body_incremental"
    assert plan["selection_scope"] == "test_function_body"
    assert plan["merge_policy"] == "replace_reports_for_selected_nodeids"
    assert plan["changed_test_files"] == ["tests/test_a.py"]
    assert plan["selected_nodeids"] == ["tests/test_a.py::test_a"]
    assert plan["changed_nodeid_prefixes"] == ["tests/test_a.py::test_a"]
    assert plan["safety_checks"]["test_function_body_precision_valid"] is True


@pytest.mark.parametrize(
    ("old_source", "new_source", "expected_reason"),
    [
        (
            "def test_a():\n    assert True\n",
            "@pytest.mark.slow\ndef test_a():\n    assert True\n",
            "outside test function bodies",
        ),
        (
            "def test_a():\n    assert True\n",
            "def test_a():\n    import os\n    assert os.name\n",
            "unsafe statement",
        ),
    ],
)
def test_nodeid_incremental_plan_records_precision_fallback_reason(tmp_path, old_source, new_source, expected_reason):
    _write_file(tmp_path, "tests/test_a.py", old_source)
    old_head = _git_commit_all(tmp_path)
    _write_file(tmp_path, "tests/test_a.py", new_source)
    old_hash = hashlib.sha256(old_source.encode("utf-8")).hexdigest()
    new_hash = hashlib.sha256(new_source.encode("utf-8")).hexdigest()
    snapshot = _collect_snapshot_for_mapping({"tests/test_a.py": ["tests/test_a.py::test_a"]})

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=_fingerprint_from_file_hashes({"tests/test_a.py": old_hash}),
        current_fingerprint=_fingerprint_from_file_hashes({"tests/test_a.py": new_hash}),
        collect_snapshot=snapshot,
        node_cache={
            "head_sha": old_head,
            "collect_nodeids": snapshot,
            "test_file_hashes": {"tests/test_a.py": old_hash},
        },
        ledger=_empty_test_debt_ledger(),
    )

    assert error == ""
    assert plan is not None
    assert plan["selection_scope"] == "test_file"
    assert expected_reason in plan["precision_fallback_reason"]


@pytest.mark.parametrize(
    ("node_cache_patch", "expected_reason"),
    [
        ({"head_sha": ""}, "node cache head_sha is missing"),
        ({"head_sha": "missing-object"}, "previous test source is unavailable"),
        ({"test_file_hashes": {"tests/test_a.py": "not-the-old-hash"}}, "previous test source hash mismatch"),
    ],
)
def test_nodeid_incremental_plan_records_previous_source_fallback_reason(
    tmp_path,
    node_cache_patch,
    expected_reason,
):
    old_source = "def test_a():\n    assert True\n"
    new_source = "def test_a():\n    assert 1 == 1\n"
    _write_file(tmp_path, "tests/test_a.py", old_source)
    old_head = _git_commit_all(tmp_path)
    _write_file(tmp_path, "tests/test_a.py", new_source)
    old_hash = hashlib.sha256(old_source.encode("utf-8")).hexdigest()
    new_hash = hashlib.sha256(new_source.encode("utf-8")).hexdigest()
    snapshot = _collect_snapshot_for_mapping({"tests/test_a.py": ["tests/test_a.py::test_a"]})
    node_cache = {
        "head_sha": old_head,
        "collect_nodeids": snapshot,
        "test_file_hashes": {"tests/test_a.py": old_hash},
    }
    node_cache.update(node_cache_patch)

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=_fingerprint_from_file_hashes({"tests/test_a.py": old_hash}),
        current_fingerprint=_fingerprint_from_file_hashes({"tests/test_a.py": new_hash}),
        collect_snapshot=snapshot,
        node_cache=node_cache,
        ledger=_empty_test_debt_ledger(),
    )

    assert error == ""
    assert plan is not None
    assert plan["selection_scope"] == "test_file"
    assert expected_reason in plan["precision_fallback_reason"]


def test_nodeid_incremental_plan_accepts_top_level_regression_test_file(tmp_path):
    _write_file(tmp_path, "tests/regression_sample_contract.py", "before\n")
    _write_file(tmp_path, "tests/test_b.py", "same\n")
    previous = _fingerprint_from_file_hashes(
        {
            "tests/regression_sample_contract.py": "old-regression",
            "tests/test_b.py": hashlib.sha256(b"same\n").hexdigest(),
            "evidence/QualityGate/collect_nodeids.json": "old-collect",
        }
    )
    current = _fingerprint_from_file_hashes(
        {
            "tests/regression_sample_contract.py": "new-regression",
            "tests/test_b.py": hashlib.sha256(b"same\n").hexdigest(),
            "evidence/QualityGate/collect_nodeids.json": "new-collect",
        }
    )
    snapshot = build_collect_nodeids_payload(
        "tests/regression_sample_contract.py::test_regression_sample\ntests/test_b.py::test_b\n",
        pytest_version="pytest 8.3.5",
    )

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=previous,
        current_fingerprint=current,
        collect_snapshot=snapshot,
        node_cache={
            "collect_nodeids": snapshot,
            "test_file_hashes": {"tests/test_b.py": hashlib.sha256(b"same\n").hexdigest()},
        },
        ledger=_empty_test_debt_ledger(),
    )

    assert error == ""
    assert plan is not None
    assert plan["mode"] == "nodeid_incremental"
    assert plan["changed_test_files"] == ["tests/regression_sample_contract.py"]
    assert plan["selected_nodeids"] == ["tests/regression_sample_contract.py::test_regression_sample"]


def test_nodeid_incremental_plan_accepts_nested_test_and_regression_files(tmp_path):
    _write_file(tmp_path, "tests/scheduler/test_nested_contract.py", "before\n")
    _write_file(tmp_path, "tests/scheduler/regression_nested_contract.py", "before\n")
    _write_file(tmp_path, "tests/test_b.py", "same\n")
    previous = _fingerprint_from_file_hashes(
        {
            "tests/scheduler/test_nested_contract.py": "old-test",
            "tests/scheduler/regression_nested_contract.py": "old-regression",
            "tests/test_b.py": hashlib.sha256(b"same\n").hexdigest(),
            "evidence/QualityGate/collect_nodeids.json": "old-collect",
        }
    )
    current = _fingerprint_from_file_hashes(
        {
            "tests/scheduler/test_nested_contract.py": "new-test",
            "tests/scheduler/regression_nested_contract.py": "new-regression",
            "tests/test_b.py": hashlib.sha256(b"same\n").hexdigest(),
            "evidence/QualityGate/collect_nodeids.json": "new-collect",
        }
    )
    snapshot = _collect_snapshot_for_mapping(
        {
            "tests/scheduler/regression_nested_contract.py": [
                "tests/scheduler/regression_nested_contract.py::test_regression_nested"
            ],
            "tests/scheduler/test_nested_contract.py": [
                "tests/scheduler/test_nested_contract.py::test_nested"
            ],
            "tests/test_b.py": ["tests/test_b.py::test_b"],
        }
    )

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=previous,
        current_fingerprint=current,
        collect_snapshot=snapshot,
        node_cache={
            "collect_nodeids": snapshot,
            "test_file_hashes": {"tests/test_b.py": hashlib.sha256(b"same\n").hexdigest()},
        },
        ledger=_empty_test_debt_ledger(),
    )

    assert error == ""
    assert plan is not None
    assert plan["mode"] == "nodeid_incremental"
    assert plan["safe_scope_kind"] == "test_file_incremental"
    assert plan["changed_files_classification"] == {
        "collect_nodeids": ["evidence/QualityGate/collect_nodeids.json"],
        "regular_test": [
            "tests/scheduler/regression_nested_contract.py",
            "tests/scheduler/test_nested_contract.py",
        ],
    }
    assert plan["changed_test_files"] == [
        "tests/scheduler/regression_nested_contract.py",
        "tests/scheduler/test_nested_contract.py",
    ]
    assert plan["selected_nodeids"] == [
        "tests/scheduler/regression_nested_contract.py::test_regression_nested",
        "tests/scheduler/test_nested_contract.py::test_nested",
    ]


def test_test_only_helper_impact_registry_is_normalized_and_defensive() -> None:
    impacts = iter_test_only_helper_impacts()

    assert impacts["tests/long_gate_cache_helpers.py"] == [
        "tests/test_long_gate_debt_ledger_cache.py",
        "tests/test_long_gate_required_regression_cache.py",
        "tests/test_long_gate_startup_regression_cache.py",
    ]
    assert helper_impacts_for_path("tests\\long_gate_cache_helpers.py") == [
        "tests/test_long_gate_debt_ledger_cache.py",
        "tests/test_long_gate_required_regression_cache.py",
        "tests/test_long_gate_startup_regression_cache.py",
    ]
    assert helper_impacts_for_path("tests/unknown_helpers.py") == []

    returned = helper_impacts_for_path("tests/long_gate_cache_helpers.py")
    returned.append("tests/test_extra.py")
    assert helper_impacts_for_path("tests/long_gate_cache_helpers.py") == [
        "tests/test_long_gate_debt_ledger_cache.py",
        "tests/test_long_gate_required_regression_cache.py",
        "tests/test_long_gate_startup_regression_cache.py",
    ]


@pytest.mark.parametrize(
    ("helper_impacts", "message"),
    [
        ({"tests/not_a_helper.py": ("tests/test_a.py",)}, r"tests/\*_helpers\.py"),
        ({"tests/other_helpers.py": ()}, "targets are empty"),
        ({"tests/other_helpers.py": ("tests/target_helpers.py",)}, "target must be a top-level test file"),
        ({"tests/other_helpers.py": ("tests/conftest.py",)}, "target must be a top-level test file"),
        ({"tests/other_helpers.py": ("tests/sub/test_target.py",)}, "target must be a top-level test file"),
        ({"tests/other_helpers.py": ("tests/smoke_target.py",)}, "target must be a top-level test file"),
        ({"tests/other_helpers.py": ("tests/target_test.py",)}, "target must be a top-level test file"),
    ],
)
def test_test_only_helper_impact_registry_rejects_unsafe_rows(helper_impacts, message) -> None:
    with pytest.raises(ValueError, match=message):
        iter_test_only_helper_impacts(helper_impacts)


def test_long_gate_helper_impact_registry_accepts_subdirectory_helpers() -> None:
    impacts = full_debt_mod._iter_test_only_helper_impacts(  # noqa: SLF001
        {
            "tests/support/cache_helpers.py": (
                "tests/support/test_cache_contract.py",
                "tests/support/regression_cache_contract.py",
            )
        }
    )

    assert impacts == {
        "tests/support/cache_helpers.py": [
            "tests/support/test_cache_contract.py",
            "tests/support/regression_cache_contract.py",
        ]
    }


def test_long_gate_helper_impact_registry_rejects_subdirectory_non_tests() -> None:
    with pytest.raises(ValueError, match=r"tests/\*\*/test_\*\.py or regression_\*\.py"):
        full_debt_mod._iter_test_only_helper_impacts(  # noqa: SLF001
            {"tests/support/cache_helpers.py": ("tests/support/cache_contract.py",)}
        )


def test_declared_helper_change_uses_nodeid_incremental(tmp_path):
    helper_text = "def helper():\n    return 1\n"
    debt_text = "from tests.long_gate_cache_helpers import helper\n"
    required_text = "from tests.long_gate_cache_helpers import helper\n"
    startup_text = "from tests.long_gate_cache_helpers import helper\n"
    _write_file(tmp_path, "tests/long_gate_cache_helpers.py", helper_text)
    _write_file(tmp_path, "tests/test_long_gate_debt_ledger_cache.py", debt_text)
    _write_file(tmp_path, "tests/test_long_gate_required_regression_cache.py", required_text)
    _write_file(tmp_path, "tests/test_long_gate_startup_regression_cache.py", startup_text)
    previous = _fingerprint_from_file_hashes(
        {
            "tests/long_gate_cache_helpers.py": "old-helper",
            "tests/test_long_gate_debt_ledger_cache.py": hashlib.sha256(debt_text.encode("utf-8")).hexdigest(),
            "tests/test_long_gate_required_regression_cache.py": hashlib.sha256(required_text.encode("utf-8")).hexdigest(),
            "tests/test_long_gate_startup_regression_cache.py": hashlib.sha256(startup_text.encode("utf-8")).hexdigest(),
            "evidence/QualityGate/collect_nodeids.json": "old-collect",
        }
    )
    current = _fingerprint_from_file_hashes(
        {
            "tests/long_gate_cache_helpers.py": "new-helper",
            "tests/test_long_gate_debt_ledger_cache.py": hashlib.sha256(debt_text.encode("utf-8")).hexdigest(),
            "tests/test_long_gate_required_regression_cache.py": hashlib.sha256(required_text.encode("utf-8")).hexdigest(),
            "tests/test_long_gate_startup_regression_cache.py": hashlib.sha256(startup_text.encode("utf-8")).hexdigest(),
            "evidence/QualityGate/collect_nodeids.json": "new-collect",
        }
    )
    snapshot = _collect_snapshot_for_mapping(
        {
            "tests/test_long_gate_debt_ledger_cache.py": [
                "tests/test_long_gate_debt_ledger_cache.py::test_debt"
            ],
            "tests/test_long_gate_required_regression_cache.py": [
                "tests/test_long_gate_required_regression_cache.py::test_required"
            ],
            "tests/test_long_gate_startup_regression_cache.py": [
                "tests/test_long_gate_startup_regression_cache.py::test_startup"
            ],
        }
    )

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=previous,
        current_fingerprint=current,
        collect_snapshot=snapshot,
        node_cache={
            "collect_nodeids": snapshot,
            "test_file_hashes": {
                "tests/test_long_gate_debt_ledger_cache.py": hashlib.sha256(
                    debt_text.encode("utf-8")
                ).hexdigest(),
                "tests/test_long_gate_required_regression_cache.py": hashlib.sha256(
                    required_text.encode("utf-8")
                ).hexdigest(),
                "tests/test_long_gate_startup_regression_cache.py": hashlib.sha256(
                    startup_text.encode("utf-8")
                ).hexdigest(),
            },
        },
        ledger=_empty_test_debt_ledger(),
    )

    assert error == ""
    assert plan is not None
    assert plan["mode"] == "nodeid_incremental"
    assert plan["changed_helpers"] == ["tests/long_gate_cache_helpers.py"]
    assert plan["declared_helper_impacts"] == {
        "tests/long_gate_cache_helpers.py": [
            "tests/test_long_gate_debt_ledger_cache.py",
            "tests/test_long_gate_required_regression_cache.py",
            "tests/test_long_gate_startup_regression_cache.py",
        ]
    }
    assert plan["actual_importing_test_files"] == [
        "tests/test_long_gate_debt_ledger_cache.py",
        "tests/test_long_gate_required_regression_cache.py",
        "tests/test_long_gate_startup_regression_cache.py",
    ]
    assert plan["affected_test_files"] == [
        "tests/test_long_gate_debt_ledger_cache.py",
        "tests/test_long_gate_required_regression_cache.py",
        "tests/test_long_gate_startup_regression_cache.py",
    ]
    assert plan["changed_test_files"] == plan["affected_test_files"]
    assert plan["selected_nodeids"] == [
        "tests/test_long_gate_debt_ledger_cache.py::test_debt",
        "tests/test_long_gate_required_regression_cache.py::test_required",
        "tests/test_long_gate_startup_regression_cache.py::test_startup",
    ]


def test_declared_subdirectory_helper_change_uses_nodeid_incremental(monkeypatch, tmp_path):
    helper_text = "def helper():\n    return 1\n"
    test_text = "from tests.support.cache_helpers import helper\n"
    regression_text = "from tests.support import cache_helpers\n"
    _write_file(tmp_path, "tests/support/cache_helpers.py", helper_text)
    _write_file(tmp_path, "tests/support/test_cache_contract.py", test_text)
    _write_file(tmp_path, "tests/support/regression_cache_contract.py", regression_text)
    monkeypatch.setattr(
        full_debt_mod,
        "TEST_ONLY_HELPER_IMPACT",
        {
            "tests/support/cache_helpers.py": (
                "tests/support/regression_cache_contract.py",
                "tests/support/test_cache_contract.py",
            )
        },
    )
    previous = _fingerprint_from_file_hashes(
        {
            "tests/support/cache_helpers.py": "old-helper",
            "tests/support/regression_cache_contract.py": hashlib.sha256(
                regression_text.encode("utf-8")
            ).hexdigest(),
            "tests/support/test_cache_contract.py": hashlib.sha256(test_text.encode("utf-8")).hexdigest(),
        }
    )
    current = _fingerprint_from_file_hashes(
        {
            "tests/support/cache_helpers.py": "new-helper",
            "tests/support/regression_cache_contract.py": hashlib.sha256(
                regression_text.encode("utf-8")
            ).hexdigest(),
            "tests/support/test_cache_contract.py": hashlib.sha256(test_text.encode("utf-8")).hexdigest(),
        }
    )
    snapshot = _collect_snapshot_for_mapping(
        {
            "tests/support/regression_cache_contract.py": [
                "tests/support/regression_cache_contract.py::test_regression_cache"
            ],
            "tests/support/test_cache_contract.py": [
                "tests/support/test_cache_contract.py::test_cache"
            ],
        }
    )

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=previous,
        current_fingerprint=current,
        collect_snapshot=snapshot,
        node_cache={"collect_nodeids": snapshot, "test_file_hashes": {}},
        ledger=_empty_test_debt_ledger(),
    )

    assert error == ""
    assert plan is not None
    assert plan["safe_scope_kind"] == "test_file_incremental"
    assert plan["changed_files_classification"] == {"test_helper": ["tests/support/cache_helpers.py"]}
    assert plan["changed_helpers"] == ["tests/support/cache_helpers.py"]
    assert plan["declared_helper_impacts"] == {
        "tests/support/cache_helpers.py": [
            "tests/support/regression_cache_contract.py",
            "tests/support/test_cache_contract.py",
        ]
    }
    assert plan["actual_importing_test_files"] == [
        "tests/support/regression_cache_contract.py",
        "tests/support/test_cache_contract.py",
    ]
    assert plan["selected_nodeids"] == [
        "tests/support/regression_cache_contract.py::test_regression_cache",
        "tests/support/test_cache_contract.py::test_cache",
    ]


@pytest.mark.parametrize(
    "source",
    [
        "from tests.long_gate_cache_helpers import helper\n",
        "from long_gate_cache_helpers import helper\n",
        "import tests.long_gate_cache_helpers as helpers\n",
        "import long_gate_cache_helpers as helpers\n",
        "from tests import long_gate_cache_helpers\n",
        "from .long_gate_cache_helpers import helper\n",
        "from . import long_gate_cache_helpers\n",
    ],
)
def test_test_files_importing_helper_detects_static_import_forms(tmp_path, source):
    _write_file(tmp_path, "tests/long_gate_cache_helpers.py", "def helper():\n    return 1\n")
    _write_file(tmp_path, "tests/test_importer.py", source)

    importers, error = full_debt_mod._test_files_importing_helper(  # noqa: SLF001
        str(tmp_path),
        "tests/long_gate_cache_helpers.py",
    )

    assert error == ""
    assert importers == ["tests/test_importer.py"]


def test_declared_helper_extra_importer_fallback(tmp_path):
    helper_text = "def helper():\n    return 1\n"
    required_text = "from tests.long_gate_cache_helpers import helper\n"
    startup_text = "from tests.long_gate_cache_helpers import helper\n"
    extra_text = "from tests.long_gate_cache_helpers import helper\n"
    _write_file(tmp_path, "tests/long_gate_cache_helpers.py", helper_text)
    _write_file(tmp_path, "tests/test_long_gate_required_regression_cache.py", required_text)
    _write_file(tmp_path, "tests/test_long_gate_startup_regression_cache.py", startup_text)
    _write_file(tmp_path, "tests/test_extra_importer.py", extra_text)
    previous = _fingerprint_from_file_hashes({"tests/long_gate_cache_helpers.py": "old-helper"})
    current = _fingerprint_from_file_hashes({"tests/long_gate_cache_helpers.py": "new-helper"})
    snapshot = _collect_snapshot_for_mapping(
        {
            "tests/test_long_gate_required_regression_cache.py": [
                "tests/test_long_gate_required_regression_cache.py::test_required"
            ],
            "tests/test_long_gate_startup_regression_cache.py": [
                "tests/test_long_gate_startup_regression_cache.py::test_startup"
            ],
            "tests/test_extra_importer.py": ["tests/test_extra_importer.py::test_extra"],
        }
    )

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=previous,
        current_fingerprint=current,
        collect_snapshot=snapshot,
        node_cache={"collect_nodeids": snapshot, "test_file_hashes": {}},
        ledger=_empty_test_debt_ledger(),
    )

    assert plan is None
    assert error == "test helper has undeclared importer: tests/long_gate_cache_helpers.py -> tests/test_extra_importer.py"


def test_declared_helper_dynamic_import_fallback(tmp_path):
    helper_text = "def helper():\n    return 1\n"
    dynamic_text = 'import importlib\nhelper = importlib.import_module("tests.long_gate_cache_helpers").helper\n'
    startup_text = "from tests.long_gate_cache_helpers import helper\n"
    _write_file(tmp_path, "tests/long_gate_cache_helpers.py", helper_text)
    _write_file(tmp_path, "tests/test_long_gate_required_regression_cache.py", dynamic_text)
    _write_file(tmp_path, "tests/test_long_gate_startup_regression_cache.py", startup_text)
    previous = _fingerprint_from_file_hashes({"tests/long_gate_cache_helpers.py": "old-helper"})
    current = _fingerprint_from_file_hashes({"tests/long_gate_cache_helpers.py": "new-helper"})
    snapshot = _collect_snapshot_for_mapping(
        {
            "tests/test_long_gate_required_regression_cache.py": [
                "tests/test_long_gate_required_regression_cache.py::test_required"
            ],
            "tests/test_long_gate_startup_regression_cache.py": [
                "tests/test_long_gate_startup_regression_cache.py::test_startup"
            ],
        }
    )

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=previous,
        current_fingerprint=current,
        collect_snapshot=snapshot,
        node_cache={"collect_nodeids": snapshot, "test_file_hashes": {}},
        ledger=_empty_test_debt_ledger(),
    )

    assert plan is None
    assert error == "dynamic test helper import cannot be proven safe: tests/test_long_gate_required_regression_cache.py"


@pytest.mark.parametrize(
    "dynamic_text",
    [
        'import importlib\ntarget = "tests.long_gate_cache_helpers"\nhelper = importlib.import_module(target).helper\n',
        'import importlib\ntarget = "tests." + "long_gate_" + "cache_helpers"\nhelper = importlib.import_module(target).helper\n',
        'target = "long_gate_" + "cache_helpers"\nhelper = __import__("tests", globals(), locals(), [target]).long_gate_cache_helpers.helper\n',
    ],
)
def test_declared_helper_dynamic_import_via_variable_fallback(tmp_path, dynamic_text):
    helper_text = "def helper():\n    return 1\n"
    startup_text = "from tests.long_gate_cache_helpers import helper\n"
    _write_file(tmp_path, "tests/long_gate_cache_helpers.py", helper_text)
    _write_file(tmp_path, "tests/test_long_gate_required_regression_cache.py", dynamic_text)
    _write_file(tmp_path, "tests/test_long_gate_startup_regression_cache.py", startup_text)
    previous = _fingerprint_from_file_hashes({"tests/long_gate_cache_helpers.py": "old-helper"})
    current = _fingerprint_from_file_hashes({"tests/long_gate_cache_helpers.py": "new-helper"})
    snapshot = _collect_snapshot_for_mapping(
        {
            "tests/test_long_gate_required_regression_cache.py": [
                "tests/test_long_gate_required_regression_cache.py::test_required"
            ],
            "tests/test_long_gate_startup_regression_cache.py": [
                "tests/test_long_gate_startup_regression_cache.py::test_startup"
            ],
        }
    )

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=previous,
        current_fingerprint=current,
        collect_snapshot=snapshot,
        node_cache={"collect_nodeids": snapshot, "test_file_hashes": {}},
        ledger=_empty_test_debt_ledger(),
    )

    assert plan is None
    assert error == "dynamic test helper import cannot be proven safe: tests/test_long_gate_required_regression_cache.py"


def test_declared_helper_ignores_unrelated_dynamic_import(tmp_path):
    helper_text = "def helper():\n    return 1\n"
    debt_text = "from tests.long_gate_cache_helpers import helper\n"
    required_text = "from tests.long_gate_cache_helpers import helper\nimport importlib\napp_mod = importlib.import_module('app')\n"
    startup_text = "from tests.long_gate_cache_helpers import helper\n"
    _write_file(tmp_path, "tests/long_gate_cache_helpers.py", helper_text)
    _write_file(tmp_path, "tests/test_long_gate_debt_ledger_cache.py", debt_text)
    _write_file(tmp_path, "tests/test_long_gate_required_regression_cache.py", required_text)
    _write_file(tmp_path, "tests/test_long_gate_startup_regression_cache.py", startup_text)
    previous = _fingerprint_from_file_hashes({"tests/long_gate_cache_helpers.py": "old-helper"})
    current = _fingerprint_from_file_hashes({"tests/long_gate_cache_helpers.py": "new-helper"})
    snapshot = _collect_snapshot_for_mapping(
        {
            "tests/test_long_gate_debt_ledger_cache.py": [
                "tests/test_long_gate_debt_ledger_cache.py::test_debt"
            ],
            "tests/test_long_gate_required_regression_cache.py": [
                "tests/test_long_gate_required_regression_cache.py::test_required"
            ],
            "tests/test_long_gate_startup_regression_cache.py": [
                "tests/test_long_gate_startup_regression_cache.py::test_startup"
            ],
        }
    )

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=previous,
        current_fingerprint=current,
        collect_snapshot=snapshot,
        node_cache={"collect_nodeids": snapshot, "test_file_hashes": {}},
        ledger=_empty_test_debt_ledger(),
    )

    assert error == ""
    assert plan is not None
    assert plan["changed_helpers"] == ["tests/long_gate_cache_helpers.py"]


def test_declared_helper_imported_by_another_helper_fallback(tmp_path):
    _write_file(tmp_path, "tests/long_gate_cache_helpers.py", "def helper():\n    return 1\n")
    _write_file(tmp_path, "tests/other_helpers.py", "from tests.long_gate_cache_helpers import helper\n")

    importers, error = full_debt_mod._test_files_importing_helper(  # noqa: SLF001
        str(tmp_path),
        "tests/long_gate_cache_helpers.py",
    )

    assert importers == []
    assert error == "test helper is imported by another helper: tests/other_helpers.py"


def test_declared_helper_impacted_file_missing_collect_mapping_fallback(tmp_path):
    helper_text = "def helper():\n    return 1\n"
    debt_text = "from tests.long_gate_cache_helpers import helper\n"
    required_text = "from tests.long_gate_cache_helpers import helper\n"
    startup_text = "from tests.long_gate_cache_helpers import helper\n"
    _write_file(tmp_path, "tests/long_gate_cache_helpers.py", helper_text)
    _write_file(tmp_path, "tests/test_long_gate_debt_ledger_cache.py", debt_text)
    _write_file(tmp_path, "tests/test_long_gate_required_regression_cache.py", required_text)
    _write_file(tmp_path, "tests/test_long_gate_startup_regression_cache.py", startup_text)
    previous = _fingerprint_from_file_hashes({"tests/long_gate_cache_helpers.py": "old-helper"})
    current = _fingerprint_from_file_hashes({"tests/long_gate_cache_helpers.py": "new-helper"})
    snapshot = _collect_snapshot_for_mapping(
        {
            "tests/test_long_gate_debt_ledger_cache.py": [
                "tests/test_long_gate_debt_ledger_cache.py::test_debt"
            ],
            "tests/test_long_gate_required_regression_cache.py": [
                "tests/test_long_gate_required_regression_cache.py::test_required"
            ],
        }
    )

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=previous,
        current_fingerprint=current,
        collect_snapshot=snapshot,
        node_cache={"collect_nodeids": snapshot, "test_file_hashes": {}},
        ledger=_empty_test_debt_ledger(),
    )

    assert plan is None
    assert error == "helper impact target has no trusted nodeid mapping: tests/test_long_gate_startup_regression_cache.py"


def test_declared_helper_impacted_file_with_registered_debt_fallback(tmp_path):
    helper_text = "def helper():\n    return 1\n"
    debt_text = "from tests.long_gate_cache_helpers import helper\n"
    required_text = "from tests.long_gate_cache_helpers import helper\n"
    startup_text = "from tests.long_gate_cache_helpers import helper\n"
    _write_file(tmp_path, "tests/long_gate_cache_helpers.py", helper_text)
    _write_file(tmp_path, "tests/test_long_gate_debt_ledger_cache.py", debt_text)
    _write_file(tmp_path, "tests/test_long_gate_required_regression_cache.py", required_text)
    _write_file(tmp_path, "tests/test_long_gate_startup_regression_cache.py", startup_text)
    previous = _fingerprint_from_file_hashes({"tests/long_gate_cache_helpers.py": "old-helper"})
    current = _fingerprint_from_file_hashes({"tests/long_gate_cache_helpers.py": "new-helper"})
    snapshot = _collect_snapshot_for_mapping(
        {
            "tests/test_long_gate_debt_ledger_cache.py": [
                "tests/test_long_gate_debt_ledger_cache.py::test_debt"
            ],
            "tests/test_long_gate_required_regression_cache.py": [
                "tests/test_long_gate_required_regression_cache.py::test_required"
            ],
            "tests/test_long_gate_startup_regression_cache.py": [
                "tests/test_long_gate_startup_regression_cache.py::test_startup"
            ],
        }
    )

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=previous,
        current_fingerprint=current,
        collect_snapshot=snapshot,
        node_cache={"collect_nodeids": snapshot, "test_file_hashes": {}},
        ledger={
            "test_debt": {
                "entries": [
                    {"nodeid": "tests/test_long_gate_startup_regression_cache.py::test_startup"}
                ]
            }
        },
    )

    assert plan is None
    assert error == "helper impact target contains registered full-test-debt nodeid: tests/test_long_gate_startup_regression_cache.py"


def test_helper_plus_regular_test_file_incremental_union(tmp_path):
    helper_text = "def helper():\n    return 1\n"
    debt_text = "from tests.long_gate_cache_helpers import helper\n"
    required_text = "from tests.long_gate_cache_helpers import helper\n"
    startup_text = "from tests.long_gate_cache_helpers import helper\n"
    regular_text = "def test_regular():\n    assert True\n"
    _write_file(tmp_path, "tests/long_gate_cache_helpers.py", helper_text)
    _write_file(tmp_path, "tests/test_long_gate_debt_ledger_cache.py", debt_text)
    _write_file(tmp_path, "tests/test_long_gate_required_regression_cache.py", required_text)
    _write_file(tmp_path, "tests/test_long_gate_startup_regression_cache.py", startup_text)
    _write_file(tmp_path, "tests/test_regular_change.py", regular_text)
    previous = _fingerprint_from_file_hashes(
        {
            "tests/long_gate_cache_helpers.py": "old-helper",
            "tests/test_long_gate_debt_ledger_cache.py": hashlib.sha256(debt_text.encode("utf-8")).hexdigest(),
            "tests/test_regular_change.py": "old-regular",
        }
    )
    current = _fingerprint_from_file_hashes(
        {
            "tests/long_gate_cache_helpers.py": "new-helper",
            "tests/test_long_gate_debt_ledger_cache.py": hashlib.sha256(debt_text.encode("utf-8")).hexdigest(),
            "tests/test_regular_change.py": "new-regular",
        }
    )
    snapshot = _collect_snapshot_for_mapping(
        {
            "tests/test_long_gate_debt_ledger_cache.py": [
                "tests/test_long_gate_debt_ledger_cache.py::test_debt"
            ],
            "tests/test_long_gate_required_regression_cache.py": [
                "tests/test_long_gate_required_regression_cache.py::test_required"
            ],
            "tests/test_long_gate_startup_regression_cache.py": [
                "tests/test_long_gate_startup_regression_cache.py::test_startup"
            ],
            "tests/test_regular_change.py": ["tests/test_regular_change.py::test_regular"],
        }
    )

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=previous,
        current_fingerprint=current,
        collect_snapshot=snapshot,
        node_cache={"collect_nodeids": snapshot, "test_file_hashes": {}},
        ledger=_empty_test_debt_ledger(),
    )

    assert error == ""
    assert plan is not None
    assert plan["changed_helpers"] == ["tests/long_gate_cache_helpers.py"]
    assert plan["changed_test_files"] == [
        "tests/test_regular_change.py",
        "tests/test_long_gate_debt_ledger_cache.py",
        "tests/test_long_gate_required_regression_cache.py",
        "tests/test_long_gate_startup_regression_cache.py",
    ]
    assert plan["selected_nodeids"] == [
        "tests/test_regular_change.py::test_regular",
        "tests/test_long_gate_debt_ledger_cache.py::test_debt",
        "tests/test_long_gate_required_regression_cache.py::test_required",
        "tests/test_long_gate_startup_regression_cache.py::test_startup",
    ]


def test_helper_plus_tools_change_fallback(tmp_path):
    previous = _fingerprint_from_file_hashes(
        {
            "tests/long_gate_cache_helpers.py": "old-helper",
            "tools/check_full_test_debt.py": "old-tool",
        }
    )
    current = _fingerprint_from_file_hashes(
        {
            "tests/long_gate_cache_helpers.py": "new-helper",
            "tools/check_full_test_debt.py": "new-tool",
        }
    )

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


def test_nodeid_incremental_plan_selects_multiple_changed_test_files(tmp_path):
    _write_file(tmp_path, "tests/test_a.py", "before-a\n")
    _write_file(tmp_path, "tests/test_b.py", "before-b\n")
    _write_file(tmp_path, "tests/test_c.py", "same-c\n")
    previous = _fingerprint_from_file_hashes(
        {
            "tests/test_a.py": "old-a",
            "tests/test_b.py": "old-b",
            "tests/test_c.py": hashlib.sha256(b"same-c\n").hexdigest(),
            "evidence/QualityGate/collect_nodeids.json": "old-collect",
        }
    )
    current = _fingerprint_from_file_hashes(
        {
            "tests/test_a.py": "new-a",
            "tests/test_b.py": "new-b",
            "tests/test_c.py": hashlib.sha256(b"same-c\n").hexdigest(),
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
            "test_file_hashes": {"tests/test_c.py": hashlib.sha256(b"same-c\n").hexdigest()},
        },
        ledger=_empty_test_debt_ledger(),
    )

    assert error == ""
    assert plan is not None
    assert plan["mode"] == "nodeid_incremental"
    assert plan["changed_test_files"] == ["tests/test_a.py", "tests/test_b.py"]
    assert plan["selected_nodeids"] == [
        "tests/test_a.py::test_a",
        "tests/test_a.py::test_b",
        "tests/test_b.py::test_b",
    ]


def test_nodeid_incremental_plan_falls_back_for_registered_debt_nodeid(tmp_path):
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
        ledger={"test_debt": {"entries": [{"nodeid": "tests/test_a.py::test_a"}]}},
    )

    assert plan is None
    assert error == "changed test file contains registered full-test-debt nodeid: tests/test_a.py"


def test_nodeid_incremental_plan_falls_back_when_any_changed_file_has_registered_debt_nodeid(tmp_path):
    _write_file(tmp_path, "tests/test_a.py", "before-a\n")
    _write_file(tmp_path, "tests/test_b.py", "before-b\n")
    _write_file(tmp_path, "tests/test_c.py", "same-c\n")
    previous = _fingerprint_from_file_hashes(
        {
            "tests/test_a.py": "old-a",
            "tests/test_b.py": "old-b",
            "tests/test_c.py": hashlib.sha256(b"same-c\n").hexdigest(),
            "evidence/QualityGate/collect_nodeids.json": "old-collect",
        }
    )
    current = _fingerprint_from_file_hashes(
        {
            "tests/test_a.py": "new-a",
            "tests/test_b.py": "new-b",
            "tests/test_c.py": hashlib.sha256(b"same-c\n").hexdigest(),
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
            "test_file_hashes": {"tests/test_c.py": hashlib.sha256(b"same-c\n").hexdigest()},
        },
        ledger={"test_debt": {"entries": [{"nodeid": "tests/test_b.py::test_b"}]}},
    )

    assert plan is None
    assert error == "changed test file contains registered full-test-debt nodeid: tests/test_b.py"


def test_nodeid_incremental_plan_selects_new_regular_test_file_with_collect_mapping(tmp_path):
    _write_file(tmp_path, "tests/test_new.py", "def test_new():\n    assert True\n")
    _write_file(tmp_path, "tests/test_existing.py", "same\n")
    previous = _fingerprint_from_file_hashes(
        {
            "tests/test_new.py": "",
            "tests/test_existing.py": hashlib.sha256(b"same\n").hexdigest(),
            "evidence/QualityGate/collect_nodeids.json": "old-collect",
        }
    )
    current = _fingerprint_from_file_hashes(
        {
            "tests/test_new.py": "new-file",
            "tests/test_existing.py": hashlib.sha256(b"same\n").hexdigest(),
            "evidence/QualityGate/collect_nodeids.json": "new-collect",
        }
    )
    snapshot = build_collect_nodeids_payload(
        "tests/test_new.py::test_new\ntests/test_existing.py::test_existing\n",
        pytest_version="pytest 8.3.5",
    )

    plan, error = _classify_incremental_plan(
        repo_root=str(tmp_path),
        previous_fingerprint=previous,
        current_fingerprint=current,
        collect_snapshot=snapshot,
        node_cache={
            "collect_nodeids": build_collect_nodeids_payload(
                "tests/test_existing.py::test_existing\n",
                pytest_version="pytest 8.3.5",
            ),
            "test_file_hashes": {"tests/test_existing.py": hashlib.sha256(b"same\n").hexdigest()},
        },
        ledger=_empty_test_debt_ledger(),
    )

    assert error == ""
    assert plan is not None
    assert plan["mode"] == "nodeid_incremental"
    assert plan["changed_test_files"] == ["tests/test_new.py"]
    assert plan["selected_nodeids"] == ["tests/test_new.py::test_new"]


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


def test_nodeid_incremental_plan_falls_back_when_dynamic_import_is_built_from_strings(tmp_path):
    _write_file(tmp_path, "tests/test_shared.py", "def helper():\n    return 1\n")
    dynamic_text = 'import importlib\ntarget = "tests." + "test_" + "shared"\nhelper = importlib.import_module(target).helper\n'
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


def test_nodeid_incremental_plan_falls_back_when_import_module_alias_is_dynamic(tmp_path):
    _write_file(tmp_path, "tests/test_shared.py", "def helper():\n    return 1\n")
    dynamic_text = 'from importlib import import_module\ntarget = "tests." + "test_" + "shared"\nhelper = import_module(target).helper\n'
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


def test_nodeid_incremental_plan_falls_back_when_import_module_renamed_alias_is_dynamic(tmp_path):
    _write_file(tmp_path, "tests/test_shared.py", "def helper():\n    return 1\n")
    dynamic_text = 'from importlib import import_module as load\ntarget = "tests." + "test_" + "shared"\nhelper = load(target).helper\n'
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


def test_nodeid_incremental_plan_falls_back_when_importlib_module_alias_is_dynamic(tmp_path):
    _write_file(tmp_path, "tests/test_shared.py", "def helper():\n    return 1\n")
    dynamic_text = 'import importlib as il\ntarget = "tests." + "test_" + "shared"\nhelper = il.import_module(target).helper\n'
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


def test_nodeid_incremental_plan_falls_back_when_dunder_import_uses_fromlist(tmp_path):
    _write_file(tmp_path, "tests/test_shared.py", "def helper():\n    return 1\n")
    dynamic_text = "helper = __import__('tests', fromlist=['test_shared']).test_shared.helper\n"
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


def test_nodeid_incremental_plan_falls_back_when_dunder_import_uses_dynamic_fromlist(tmp_path):
    _write_file(tmp_path, "tests/test_shared.py", "def helper():\n    return 1\n")
    dynamic_text = "target = 'test_' + 'shared'\nhelper = __import__('tests', globals(), locals(), [target]).test_shared.helper\n"
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


def test_changed_test_import_text_prefilter_keeps_safe_import_spelling() -> None:
    changed_modules = {"tests.test_shared", "test_shared"}

    assert _source_may_import_changed_test_module("from tests.test_shared import helper\n", changed_modules)
    assert _source_may_import_changed_test_module("from tests import test_shared\n", changed_modules)
    assert _source_may_import_changed_test_module(
        "importlib.import_module('tests.test_shared')\n",
        changed_modules,
    )
    assert _source_may_import_changed_test_module('target = "tests." + "test_" + "shared"\nimportlib.import_module(target)\n', changed_modules)
    assert _source_may_import_changed_test_module(
        'from importlib import import_module\ntarget = "tests." + "test_" + "shared"\nimport_module(target)\n',
        changed_modules,
    )
    assert _source_may_import_changed_test_module("__import__('tests.test_shared')\n", changed_modules)
    assert not _source_may_import_changed_test_module("def test_unrelated():\n    assert True\n", changed_modules)


@pytest.mark.parametrize(
    ("changed_path", "expected_error"),
    [
        ("tests/conftest.py", "outside safe test-file-only scope"),
        ("tests/helpers.py", "outside safe test-file-only scope"),
        ("tests/test_sample_helpers.py", "test helper is not declared"),
        ("tests/regression_cache_helpers.py", "test helper is not declared"),
        ("tests/excel_preview_confirm_helpers.py", "test helper is not declared"),
        ("tests/runtime_cleanup_helper.py", "outside safe test-file-only scope"),
        ("tests/some_dir/helper.py", "outside safe test-file-only scope"),
        ("tests/regression/collection_contract.py", "outside safe test-file-only scope"),
        ("conftest.py", "outside safe test-file-only scope"),
        ("core/service.py", "outside safe test-file-only scope"),
        ("web/view.py", "outside safe test-file-only scope"),
        ("data/repository.py", "outside safe test-file-only scope"),
        ("plugins/demo.py", "outside safe test-file-only scope"),
        ("pyproject.toml", "outside safe test-file-only scope"),
        ("app.py", "outside safe test-file-only scope"),
        ("config.py", "outside safe test-file-only scope"),
        ("schema.sql", "outside safe test-file-only scope"),
        ("templates/scheduler/gantt.html", "outside safe test-file-only scope"),
        ("static/js/config_manual.js", "outside safe test-file-only scope"),
        ("tools/check_full_test_debt.py", "outside safe test-file-only scope"),
        ("scripts/run_quality_gate.py", "outside safe test-file-only scope"),
    ],
)
def test_nodeid_incremental_plan_falls_back_for_unsafe_paths(tmp_path, changed_path, expected_error):
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
    assert expected_error in error


def test_source_and_template_changes_are_diagnostic_full_run_scope() -> None:
    previous = _fingerprint_from_file_hashes(
        {
            "core/service.py": "old-source",
            "templates/scheduler/gantt.html": "old-template",
        }
    )
    current = _fingerprint_from_file_hashes(
        {
            "core/service.py": "new-source",
            "templates/scheduler/gantt.html": "new-template",
        }
    )

    diagnostics = full_debt_mod._fingerprint_change_diagnostics(previous, current)  # noqa: SLF001

    assert diagnostics == {
        "safe_scope_kind": "source_or_template_full_run",
        "changed_files_classification": {
            "source": ["core/service.py"],
            "template": ["templates/scheduler/gantt.html"],
        },
        "ledger_change_kind": "none",
    }


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
    assert plan["safe_scope_kind"] == "ledger_only"
    assert plan["changed_files_classification"] == {"ledger": ["开发文档/技术债务治理台账.md"]}
    assert plan["ledger_change_kind"] == "ledger_only"


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


def test_merge_payload_records_incremental_proof_and_keeps_formal_args(tmp_path):
    old_payload = _current_payload_for_nodeids(
        ["tests/test_a.py::test_a", "tests/test_b.py::test_b"]
    )
    incremental_payload = {
        "exitstatus": 0,
        "reports": [_passed_report("tests/test_a.py::test_a")],
        "collection_errors": [],
    }
    collect_snapshot = build_collect_nodeids_payload(
        "tests/test_a.py::test_a\ntests/test_b.py::test_b\n",
        pytest_version="pytest 8.3.5",
    )

    merged = _merge_payload(
        repo_root=str(tmp_path),
        old_payload=old_payload,
        incremental_payload=incremental_payload,
        collect_snapshot=collect_snapshot,
        node_cache={"payload_hash": "sha256:node-cache"},
        changed_test_files=["tests/test_a.py"],
        selected_nodeids=["tests/test_a.py::test_a"],
        pytest_args=["tests/test_a.py::test_a", "-q", "--tb=short", "-ra", "-p", "no:cacheprovider"],
    )

    assert merged["pytest_args"] == ["tests", "-q", "--tb=short", "-ra", "-p", "no:cacheprovider"]
    assert merged["collected_nodeids"] == ["tests/test_a.py::test_a", "tests/test_b.py::test_b"]
    assert [report["nodeid"] for report in merged["reports"]] == [
        "tests/test_a.py::test_a",
        "tests/test_b.py::test_b",
    ]
    assert merged["incremental_proof"] == {
        "mode": "nodeid_incremental",
        "safe_scope_kind": "test_file_incremental",
        "changed_files_classification": {},
        "ledger_change_kind": "none",
        "selected_nodeids": ["tests/test_a.py::test_a"],
        "changed_test_files": ["tests/test_a.py"],
        "changed_helpers": [],
        "declared_helper_impacts": {},
        "actual_importing_test_files": [],
        "affected_test_files": ["tests/test_a.py"],
        "previous_payload_hash": f"sha256:{stable_json_hash(old_payload)}",
        "node_cache_hash": "sha256:node-cache",
        "collect_nodeids_hash": collect_snapshot["nodeid_hash"],
        "merge_policy": "replace_reports_for_changed_test_files",
        "selection_scope": "test_file",
        "changed_nodeid_prefixes": [],
        "changed_functions": [],
        "selected_nodeid_count": 1,
        "selected_nodeids_hash": stable_json_hash(["tests/test_a.py::test_a"]),
        "selected_nodeids_sample": ["tests/test_a.py::test_a"],
        "scope_basis": [],
    }


def test_merge_payload_can_replace_only_selected_nodeids_in_same_file(tmp_path):
    old_payload = _current_payload_for_nodeids(
        ["tests/test_a.py::test_a", "tests/test_a.py::test_b"]
    )
    incremental_payload = {
        "exitstatus": 1,
        "reports": [_failed_report("tests/test_a.py::test_a")],
        "collection_errors": [],
    }
    collect_snapshot = build_collect_nodeids_payload(
        "tests/test_a.py::test_a\ntests/test_a.py::test_b\n",
        pytest_version="pytest 8.3.5",
    )

    merged = _merge_payload(
        repo_root=str(tmp_path),
        old_payload=old_payload,
        incremental_payload=incremental_payload,
        collect_snapshot=collect_snapshot,
        node_cache={"payload_hash": "sha256:node-cache"},
        changed_test_files=["tests/test_a.py"],
        selected_nodeids=["tests/test_a.py::test_a"],
        pytest_args=["tests/test_a.py::test_a", "-q", "--tb=short", "-ra", "-p", "no:cacheprovider"],
        incremental_plan={
            "safe_scope_kind": "test_function_body_incremental",
            "selection_scope": "test_function_body",
            "merge_policy": "replace_reports_for_selected_nodeids",
            "changed_nodeid_prefixes": ["tests/test_a.py::test_a"],
            "changed_functions": [
                {
                    "path": "tests/test_a.py",
                    "qualname": "test_a",
                    "nodeid_prefix": "tests/test_a.py::test_a",
                }
            ],
        },
    )

    reports_by_nodeid = {report["nodeid"]: report for report in merged["reports"]}
    assert reports_by_nodeid["tests/test_a.py::test_a"]["outcome"] == "failed"
    assert reports_by_nodeid["tests/test_a.py::test_b"]["outcome"] == "passed"
    assert merged["incremental_proof"]["merge_policy"] == "replace_reports_for_selected_nodeids"
    assert merged["incremental_proof"]["selection_scope"] == "test_function_body"


def test_merge_payload_rejects_unknown_merge_policy(tmp_path):
    old_payload = _current_payload_for_nodeids(["tests/test_a.py::test_a"])
    collect_snapshot = build_collect_nodeids_payload("tests/test_a.py::test_a\n", pytest_version="pytest 8.3.5")

    with pytest.raises(full_debt_mod.QualityGateError, match="unknown full_test_debt incremental merge policy"):
        _merge_payload(
            repo_root=str(tmp_path),
            old_payload=old_payload,
            incremental_payload={
                "exitstatus": 0,
                "reports": [_passed_report("tests/test_a.py::test_a")],
                "collection_errors": [],
            },
            collect_snapshot=collect_snapshot,
            node_cache={"payload_hash": "sha256:node-cache"},
            changed_test_files=["tests/test_a.py"],
            selected_nodeids=["tests/test_a.py::test_a"],
            pytest_args=["tests/test_a.py::test_a", "-q", "--tb=short", "-ra", "-p", "no:cacheprovider"],
            incremental_plan={"merge_policy": "typo-policy"},
        )


def test_incremental_collector_must_report_exact_selected_nodeids() -> None:
    assert (
        full_debt_mod._validate_incremental_payload_contract(  # noqa: SLF001
            {
                "exitstatus": 0,
                "collected_nodeids": ["tests/test_a.py::test_a"],
                "reports": [_passed_report("tests/test_a.py::test_a")],
                "collection_errors": [],
            },
            ["tests/test_a.py::test_a"],
            returncode=0,
        )
        == ""
    )
    assert (
        full_debt_mod._validate_incremental_payload_contract(  # noqa: SLF001
            {
                "exitstatus": 0,
                "collected_nodeids": ["tests/test_a.py::test_b"],
                "reports": [_passed_report("tests/test_a.py::test_b")],
                "collection_errors": [],
            },
            ["tests/test_a.py::test_a"],
            returncode=0,
        )
        == "incremental collector collected_nodeids does not match selected nodeids"
    )
    assert (
        full_debt_mod._validate_incremental_payload_contract(  # noqa: SLF001
            {
                "exitstatus": 0,
                "collected_nodeids": ["tests/test_a.py::test_a"],
                "reports": [_passed_report("tests/test_a.py::test_b")],
                "collection_errors": [],
            },
            ["tests/test_a.py::test_a"],
            returncode=0,
        )
        == "incremental collector payload reports[0].nodeid is outside selected nodeids"
    )
    assert (
        full_debt_mod._validate_incremental_payload_contract(  # noqa: SLF001
            {
                "exitstatus": 0,
                "collected_nodeids": ["tests/test_a.py::test_a"],
                "reports": [],
                "collection_errors": [],
            },
            ["tests/test_a.py::test_a"],
            returncode=0,
        )
        == "incremental collector payload missing report for selected nodeid: tests/test_a.py::test_a"
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"exitstatus": 0, "reports": [], "collection_errors": []},
        {"exitstatus": 0, "collected_nodeids": ["tests/test_a.py::test_b"], "reports": [], "collection_errors": []},
        {"exitstatus": 0, "collected_nodeids": ["tests/test_a.py::test_b", "tests/test_a.py::test_a"], "reports": [], "collection_errors": []},
        {"exitstatus": 0, "collected_nodeids": [1], "reports": [], "collection_errors": []},
        {"exitstatus": 0, "collected_nodeids": ["tests/test_a.py::test_a"], "reports": [], "collection_errors": []},
    ],
)
def test_special_nodeid_incremental_rejects_collected_nodeid_mismatch(monkeypatch, tmp_path, payload):
    selected = ["tests/test_a.py::test_a"]
    collect_snapshot = _collect_snapshot_for_mapping({"tests/test_a.py": selected})
    node_cache = {
        "current_payload": _current_payload_for_nodeids(selected),
        "payload_hash": "sha256:node-cache",
    }
    plan = {
        "mode": "nodeid_incremental",
        "changed_paths": ["tests/test_a.py"],
        "changed_test_files": ["tests/test_a.py"],
        "selected_nodeids": selected,
    }
    stale_current = tmp_path / "evidence" / "QualityGate" / "current_full_test_debt.json"
    stale_summary = tmp_path / "evidence" / "QualityGate" / "full_test_debt_summary.json"
    stale_node_cache = tmp_path / NODE_CACHE_REL
    stale_current.parent.mkdir(parents=True, exist_ok=True)
    stale_current.write_text("stale-current\n", encoding="utf-8")
    stale_summary.write_text("stale-summary\n", encoding="utf-8")
    stale_node_cache.write_text("stale-node-cache\n", encoding="utf-8")

    monkeypatch.setattr(
        full_debt_mod,
        "_validated_previous_success",
        lambda **_kwargs: (
            {
                "status": "passed",
                "returncode": 0,
                "fingerprint": {"hash": "sha256:previous"},
                "fingerprint_hash": "sha256:previous",
            },
            "",
        ),
    )
    monkeypatch.setattr(full_debt_mod, "_load_node_cache", lambda *_args, **_kwargs: (node_cache, ""))
    monkeypatch.setattr(full_debt_mod, "_load_collect_snapshot", lambda *_args, **_kwargs: (collect_snapshot, ""))
    monkeypatch.setattr(full_debt_mod, "_load_ledger_for_repo", lambda *_args, **_kwargs: _empty_test_debt_ledger())
    monkeypatch.setattr(full_debt_mod, "_classify_incremental_plan", lambda **_kwargs: (plan, ""))
    monkeypatch.setattr(
        full_debt_mod,
        "_run_incremental_collector",
        lambda *_args, **_kwargs: {
            "stdout": "selected passed\n",
            "stderr": "",
            "returncode": 0,
            "payload": dict(payload),
            "pytest_args": ["tests/test_a.py::test_a", "-q", "--tb=short", "-ra", "-p", "no:cacheprovider"],
            "collector_contract_error": False,
        },
    )

    def fail_checker(*_args, **_kwargs):
        raise AssertionError("checker must not run after collected_nodeids contract mismatch")

    monkeypatch.setattr(full_debt_mod.check_full_test_debt, "run_check_from_existing_payload", fail_checker)

    result = full_debt_mod.try_run_special_full_test_debt_mode(
        repo_root=str(tmp_path),
        entry={"entry_id": "full_test_debt"},
        current_fingerprint={"hash": "sha256:current"},
        decision={
            "decision": "run",
            "reason": "input fingerprint changed",
            "previous_result_path": "evidence/QualityGate/long_gate/results/full_test_debt.success.json",
        },
        evaluation={},
        cache_dir="evidence/QualityGate/long_gate",
    )

    assert result is not None
    assert result["returncode"] == 2
    assert "incremental collector" in result["stderr"]
    assert stale_current.read_text(encoding="utf-8") == "stale-current\n"
    assert stale_summary.read_text(encoding="utf-8") == "stale-summary\n"
    assert stale_node_cache.read_text(encoding="utf-8") == "stale-node-cache\n"


def test_build_ledger_only_payload_records_current_proof_metadata(monkeypatch, tmp_path):
    old_payload = _current_payload_for_nodeids(["tests/test_a.py::test_a"])
    old_payload["generated_at"] = "old-time"
    old_payload["head_sha"] = "old-head"
    ledger_path = _write_ledger_file(tmp_path)
    current_fingerprint = {"hash": "sha256:current"}

    monkeypatch.setattr(full_debt_mod, "_git_head", lambda *_args, **_kwargs: "new-head")
    monkeypatch.setattr(full_debt_mod, "_git_status", lambda *_args, **_kwargs: [])

    payload = _build_ledger_only_payload(
        repo_root=str(tmp_path),
        old_payload=old_payload,
        node_cache={
            "payload_hash": "sha256:node-cache",
            "fingerprint_hash": "sha256:previous",
            "fingerprint": {"hash": "sha256:previous"},
        },
        current_fingerprint=current_fingerprint,
        ledger=_empty_test_debt_ledger(),
        plan={"mode": "ledger_only", "changed_paths": ["开发文档/技术债务治理台账.md"]},
    )

    assert payload["head_sha"] == "new-head"
    assert payload["generated_at"] != "old-time"
    assert payload["git_status_short_before"] == []
    assert payload["worktree_clean_before"] is True
    assert payload["pytest_args"] == ["tests", "-q", "--tb=short", "-ra", "-p", "no:cacheprovider"]
    assert payload["collected_nodeids"] == old_payload["collected_nodeids"]
    assert payload["reports"] == old_payload["reports"]
    assert payload["collection_errors"] == old_payload["collection_errors"]
    assert payload["classifications"] == old_payload["classifications"]
    assert payload["incremental_proof"] == {
        "mode": "ledger_only",
        "safe_scope_kind": "ledger_only",
        "changed_files_classification": {},
        "ledger_change_kind": "ledger_only",
        "changed_paths": ["开发文档/技术债务治理台账.md"],
        "previous_payload_hash": f"sha256:{stable_json_hash(old_payload)}",
        "previous_head_sha": "old-head",
        "previous_generated_at": "old-time",
        "node_cache_hash": "sha256:node-cache",
        "previous_fingerprint_hash": "sha256:previous",
        "current_fingerprint_hash": "sha256:current",
        "ledger_sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
        "merge_policy": "reuse_previous_test_observations_with_current_ledger",
    }
    assert payload["incremental_source"] == {
        "mode": "ledger_only",
        "safe_scope_kind": "ledger_only",
        "changed_files_classification": {},
        "ledger_change_kind": "ledger_only",
        "changed_paths": ["开发文档/技术债务治理台账.md"],
    }


def test_special_ledger_only_success_writes_current_payload_and_node_cache(monkeypatch, tmp_path):
    entry, _old_fingerprint = _seed_success(tmp_path)
    success = _load_success(tmp_path)
    ledger_path = _write_ledger_file(tmp_path)
    current_fingerprint = fingerprint_entry(entry, str(tmp_path))
    seen_payloads = []

    monkeypatch.setattr(full_debt_mod, "_load_ledger_for_repo", lambda *_args, **_kwargs: _empty_test_debt_ledger())
    monkeypatch.setattr(full_debt_mod, "_git_status", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(full_debt_mod, "_git_head", lambda *_args, **_kwargs: "new-head")

    def fake_run_check_from_existing_payload(payload, *, ledger=None, require_clean_worktree_proof=True):
        seen_payloads.append(dict(payload))
        return _summary_payload("ledger-only")

    monkeypatch.setattr(
        full_debt_mod.check_full_test_debt,
        "run_check_from_existing_payload",
        fake_run_check_from_existing_payload,
    )

    result = full_debt_mod.try_run_special_full_test_debt_mode(
        repo_root=str(tmp_path),
        entry=entry,
        current_fingerprint=current_fingerprint,
        decision={
            "decision": "run",
            "reason": "input fingerprint changed",
            "previous_result_path": "evidence/QualityGate/long_gate/results/full_test_debt.success.json",
        },
        evaluation={"validated_success": success},
        cache_dir="evidence/QualityGate/long_gate",
    )

    assert result is not None
    assert result["returncode"] == 0
    assert result["execution_mode"] == "ledger_only"
    assert seen_payloads
    assert seen_payloads[0]["incremental_proof"]["mode"] == "ledger_only"
    assert seen_payloads[0]["head_sha"] == "new-head"
    current_payload = json.loads(
        (tmp_path / "evidence" / "QualityGate" / "current_full_test_debt.json").read_text(encoding="utf-8")
    )
    node_cache = json.loads((tmp_path / NODE_CACHE_REL).read_text(encoding="utf-8"))
    assert current_payload["head_sha"] == "new-head"
    assert current_payload["incremental_proof"]["mode"] == "ledger_only"
    assert current_payload["incremental_proof"]["previous_payload_hash"]
    assert current_payload["incremental_proof"]["current_fingerprint_hash"] == current_fingerprint["hash"]
    assert current_payload["incremental_proof"]["ledger_sha256"] == hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    assert node_cache["execution_mode"] == "ledger_only"
    assert node_cache["ledger_sha256"] == hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    assert node_cache["current_payload_hash"] == f"sha256:{stable_json_hash(current_payload)}"
    assert node_cache["current_payload"] == current_payload


def test_special_ledger_only_checker_failure_does_not_fallback_or_write_outputs(monkeypatch, tmp_path):
    entry, _old_fingerprint = _seed_success(tmp_path)
    success = _load_success(tmp_path)
    _write_ledger_file(tmp_path)
    current_fingerprint = fingerprint_entry(entry, str(tmp_path))
    stale_current = tmp_path / "evidence" / "QualityGate" / "current_full_test_debt.json"
    stale_summary = tmp_path / "evidence" / "QualityGate" / "full_test_debt_summary.json"
    node_cache_path = tmp_path / NODE_CACHE_REL
    stale_current.write_text("stale-current\n", encoding="utf-8")
    stale_summary.write_text("stale-summary\n", encoding="utf-8")
    node_cache_before = node_cache_path.read_text(encoding="utf-8")
    seen_payloads = []

    monkeypatch.setattr(full_debt_mod, "_load_ledger_for_repo", lambda *_args, **_kwargs: _empty_test_debt_ledger())
    monkeypatch.setattr(full_debt_mod, "_git_status", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(full_debt_mod, "_git_head", lambda *_args, **_kwargs: "new-head")

    def fake_run_check_from_existing_payload(payload, *, ledger=None, require_clean_worktree_proof=True):
        seen_payloads.append(dict(payload))
        raise full_debt_mod.QualityGateError("checker rejected ledger-only payload")

    monkeypatch.setattr(
        full_debt_mod.check_full_test_debt,
        "run_check_from_existing_payload",
        fake_run_check_from_existing_payload,
    )

    result = full_debt_mod.try_run_special_full_test_debt_mode(
        repo_root=str(tmp_path),
        entry=entry,
        current_fingerprint=current_fingerprint,
        decision={
            "decision": "run",
            "reason": "input fingerprint changed",
            "previous_result_path": "evidence/QualityGate/long_gate/results/full_test_debt.success.json",
        },
        evaluation={"validated_success": success},
        cache_dir="evidence/QualityGate/long_gate",
    )

    assert seen_payloads
    assert seen_payloads[0]["incremental_proof"]["mode"] == "ledger_only"
    assert seen_payloads[0]["head_sha"] == "new-head"
    assert result is not None
    assert result["returncode"] == 2
    assert result["execution_mode"] == "ledger_only"
    assert "checker rejected ledger-only payload" in result["stderr"]
    assert stale_current.read_text(encoding="utf-8") == "stale-current\n"
    assert stale_summary.read_text(encoding="utf-8") == "stale-summary\n"
    assert node_cache_path.read_text(encoding="utf-8") == node_cache_before


def test_special_nodeid_incremental_failure_is_checked_against_merged_payload(monkeypatch, tmp_path):
    collect_snapshot = build_collect_nodeids_payload(
        "tests/test_a.py::test_a\ntests/test_b.py::test_b\n",
        pytest_version="pytest 8.3.5",
    )
    old_payload = _current_payload_for_nodeids(
        ["tests/test_a.py::test_a", "tests/test_b.py::test_b"]
    )
    node_cache = {
        "current_payload": old_payload,
        "payload_hash": "sha256:node-cache",
    }
    stale_current = tmp_path / "evidence" / "QualityGate" / "current_full_test_debt.json"
    stale_summary = tmp_path / "evidence" / "QualityGate" / "full_test_debt_summary.json"
    stale_node_cache = tmp_path / NODE_CACHE_REL
    stale_current.parent.mkdir(parents=True, exist_ok=True)
    stale_current.write_text("stale-current\n", encoding="utf-8")
    stale_summary.write_text("stale-summary\n", encoding="utf-8")
    stale_node_cache.write_text("stale-node-cache\n", encoding="utf-8")
    plan = {
        "mode": "nodeid_incremental",
        "changed_paths": ["tests/test_a.py"],
        "changed_test_files": ["tests/test_a.py"],
        "selected_nodeids": ["tests/test_a.py::test_a"],
    }
    seen_payloads = []

    monkeypatch.setattr(
        full_debt_mod,
        "_validated_previous_success",
        lambda **_kwargs: (
            {
                "status": "passed",
                "returncode": 0,
                "fingerprint": {"hash": "sha256:previous"},
                "fingerprint_hash": "sha256:previous",
            },
            "",
        ),
    )
    monkeypatch.setattr(full_debt_mod, "_load_node_cache", lambda *_args, **_kwargs: (node_cache, ""))
    monkeypatch.setattr(full_debt_mod, "_load_collect_snapshot", lambda *_args, **_kwargs: (collect_snapshot, ""))
    monkeypatch.setattr(full_debt_mod, "_load_ledger_for_repo", lambda *_args, **_kwargs: _empty_test_debt_ledger())
    monkeypatch.setattr(full_debt_mod, "_classify_incremental_plan", lambda **_kwargs: (plan, ""))
    monkeypatch.setattr(
        full_debt_mod,
        "_run_incremental_collector",
        lambda *_args, **_kwargs: {
            "stdout": "selected failed\n",
            "stderr": "",
            "returncode": 1,
            "payload": {
                "exitstatus": 1,
                "collected_nodeids": ["tests/test_a.py::test_a"],
                "reports": [_failed_report("tests/test_a.py::test_a")],
                "collection_errors": [],
            },
            "pytest_args": ["tests/test_a.py::test_a", "-q", "--tb=short", "-ra", "-p", "no:cacheprovider"],
            "collector_contract_error": False,
        },
    )

    def fake_run_check_from_existing_payload(payload, *, ledger=None, require_clean_worktree_proof=True):
        seen_payloads.append(dict(payload))
        raise full_debt_mod.QualityGateError("checker rejected merged payload")

    monkeypatch.setattr(
        full_debt_mod.check_full_test_debt,
        "run_check_from_existing_payload",
        fake_run_check_from_existing_payload,
    )

    result = full_debt_mod.try_run_special_full_test_debt_mode(
        repo_root=str(tmp_path),
        entry={"entry_id": "full_test_debt"},
        current_fingerprint={"hash": "sha256:current"},
        decision={
            "decision": "run",
            "reason": "input fingerprint changed",
            "previous_result_path": "evidence/QualityGate/long_gate/results/full_test_debt.success.json",
        },
        evaluation={},
        cache_dir="evidence/QualityGate/long_gate",
    )

    assert seen_payloads
    assert seen_payloads[0]["incremental_proof"]["selected_nodeids"] == ["tests/test_a.py::test_a"]
    assert seen_payloads[0]["pytest_args"] == ["tests", "-q", "--tb=short", "-ra", "-p", "no:cacheprovider"]
    assert seen_payloads[0]["exitstatus"] == 1
    assert seen_payloads[0]["summary"]["failed_nodeid_count"] == 1
    assert seen_payloads[0]["summary"]["classification_counts"]["candidate_test_debt"] == 1
    assert seen_payloads[0]["classifications"]["candidate_test_debt"] == ["tests/test_a.py::test_a"]
    reports_by_nodeid = {report["nodeid"]: report for report in seen_payloads[0]["reports"]}
    assert reports_by_nodeid["tests/test_a.py::test_a"]["outcome"] == "failed"
    assert reports_by_nodeid["tests/test_b.py::test_b"]["outcome"] == "passed"
    assert result is not None
    assert result["returncode"] == 2
    assert result["execution_mode"] == "nodeid_incremental"
    assert "checker rejected merged payload" in result["stderr"]
    assert stale_current.read_text(encoding="utf-8") == "stale-current\n"
    assert stale_summary.read_text(encoding="utf-8") == "stale-summary\n"
    assert stale_node_cache.read_text(encoding="utf-8") == "stale-node-cache\n"


def test_special_nodeid_incremental_success_writes_merged_outputs(monkeypatch, tmp_path):
    entry, _old_fingerprint = _seed_success(tmp_path)
    success = _load_success(tmp_path)
    _write_file(tmp_path, "tests/test_a.py", "def test_a():\n    assert 1 == 1\n# changed\n")
    current_fingerprint = fingerprint_entry(entry, str(tmp_path))
    seen_env_overlays = []
    seen_check_env = []

    monkeypatch.setattr(full_debt_mod, "_load_ledger_for_repo", lambda *_args, **_kwargs: _empty_test_debt_ledger())
    monkeypatch.setattr(full_debt_mod, "_git_status", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(full_debt_mod, "_git_head", lambda *_args, **_kwargs: "deadbeef")
    def fake_run_check_from_existing_payload(*_args, **_kwargs):
        seen_check_env.append(os.environ.get("APS_BROWSER_SMOKE_REQUIRED"))
        return _summary_payload("incremental")

    monkeypatch.setattr(
        full_debt_mod.check_full_test_debt,
        "run_check_from_existing_payload",
        fake_run_check_from_existing_payload,
    )
    def fake_run_incremental_collector(*_args, **kwargs):
        seen_env_overlays.append(dict(kwargs.get("env_overlay") or {}))
        return {
            "stdout": "selected passed\n",
            "stderr": "",
            "returncode": 0,
            "payload": {
                "exitstatus": 0,
                "collected_nodeids": ["tests/test_a.py::test_a"],
                "reports": [_passed_report("tests/test_a.py::test_a")],
                "collection_errors": [],
            },
            "pytest_args": ["tests/test_a.py::test_a", "-q", "--tb=short", "-ra", "-p", "no:cacheprovider"],
            "collector_contract_error": False,
        }

    monkeypatch.setattr(full_debt_mod, "_run_incremental_collector", fake_run_incremental_collector)

    result = full_debt_mod.try_run_special_full_test_debt_mode(
        repo_root=str(tmp_path),
        entry=entry,
        current_fingerprint=current_fingerprint,
        decision={
            "decision": "run",
            "reason": "input fingerprint changed",
            "previous_result_path": "evidence/QualityGate/long_gate/results/full_test_debt.success.json",
        },
        evaluation={"validated_success": success},
        cache_dir="evidence/QualityGate/long_gate",
        env_overlay={"APS_BROWSER_SMOKE_REQUIRED": "1"},
    )

    assert result is not None
    assert seen_env_overlays == [{"APS_BROWSER_SMOKE_REQUIRED": "1"}]
    assert seen_check_env == ["1"]
    assert result["returncode"] == 0
    assert result["execution_mode"] == "nodeid_incremental"
    assert result["reused_from"]["changed_test_files"] == ["tests/test_a.py"]
    assert result["reused_from"]["selected_nodeids"] == ["tests/test_a.py::test_a"]
    current_payload = json.loads(
        (tmp_path / "evidence" / "QualityGate" / "current_full_test_debt.json").read_text(encoding="utf-8")
    )
    assert current_payload["incremental_proof"]["mode"] == "nodeid_incremental"
    assert current_payload["incremental_proof"]["merge_policy"] == "replace_reports_for_changed_test_files"
    assert current_payload["pytest_args"] == ["tests", "-q", "--tb=short", "-ra", "-p", "no:cacheprovider"]
    assert (tmp_path / "evidence" / "QualityGate" / "full_test_debt_summary.json").exists()
    assert (tmp_path / NODE_CACHE_REL).exists()


def test_special_nodeid_incremental_success_records_helper_dependency_proof(monkeypatch, tmp_path):
    selected = [
        "tests/test_long_gate_required_regression_cache.py::test_required",
        "tests/test_long_gate_startup_regression_cache.py::test_startup",
    ]
    all_nodeids = [*selected, "tests/test_unaffected.py::test_unaffected"]
    collect_snapshot = _collect_snapshot_for_mapping(
        {
            "tests/test_long_gate_required_regression_cache.py": [selected[0]],
            "tests/test_long_gate_startup_regression_cache.py": [selected[1]],
            "tests/test_unaffected.py": ["tests/test_unaffected.py::test_unaffected"],
        }
    )
    old_payload = _current_payload_for_nodeids(all_nodeids)
    node_cache = {
        "current_payload": old_payload,
        "payload_hash": "sha256:node-cache",
    }
    plan = {
        "mode": "nodeid_incremental",
        "changed_paths": ["tests/long_gate_cache_helpers.py"],
        "changed_test_files": [
            "tests/test_long_gate_required_regression_cache.py",
            "tests/test_long_gate_startup_regression_cache.py",
        ],
        "changed_helpers": ["tests/long_gate_cache_helpers.py"],
        "declared_helper_impacts": {
            "tests/long_gate_cache_helpers.py": [
                "tests/test_long_gate_required_regression_cache.py",
                "tests/test_long_gate_startup_regression_cache.py",
            ]
        },
        "actual_importing_test_files": [
            "tests/test_long_gate_required_regression_cache.py",
            "tests/test_long_gate_startup_regression_cache.py",
        ],
        "affected_test_files": [
            "tests/test_long_gate_required_regression_cache.py",
            "tests/test_long_gate_startup_regression_cache.py",
        ],
        "selected_nodeids": selected,
    }
    seen_payloads = []

    monkeypatch.setattr(
        full_debt_mod,
        "_validated_previous_success",
        lambda **_kwargs: (
            {
                "status": "passed",
                "returncode": 0,
                "fingerprint": {"hash": "sha256:previous"},
                "fingerprint_hash": "sha256:previous",
            },
            "",
        ),
    )
    monkeypatch.setattr(full_debt_mod, "_load_node_cache", lambda *_args, **_kwargs: (node_cache, ""))
    monkeypatch.setattr(full_debt_mod, "_load_collect_snapshot", lambda *_args, **_kwargs: (collect_snapshot, ""))
    monkeypatch.setattr(full_debt_mod, "_load_ledger_for_repo", lambda *_args, **_kwargs: _empty_test_debt_ledger())
    monkeypatch.setattr(full_debt_mod, "_classify_incremental_plan", lambda **_kwargs: (plan, ""))
    monkeypatch.setattr(full_debt_mod, "_git_status", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(full_debt_mod, "_git_head", lambda *_args, **_kwargs: "deadbeef")
    monkeypatch.setattr(
        full_debt_mod,
        "_run_incremental_collector",
        lambda *_args, **_kwargs: {
            "stdout": "selected passed\n",
            "stderr": "",
            "returncode": 0,
            "payload": {
                "exitstatus": 0,
                "collected_nodeids": list(selected),
                "reports": [_passed_report(nodeid) for nodeid in selected],
                "collection_errors": [],
            },
            "pytest_args": [*selected, "-q", "--tb=short", "-ra", "-p", "no:cacheprovider"],
            "collector_contract_error": False,
        },
    )

    def fake_run_check_from_existing_payload(payload, *, ledger=None, require_clean_worktree_proof=True):
        seen_payloads.append(dict(payload))
        return _summary_payload("helper-incremental")

    monkeypatch.setattr(
        full_debt_mod.check_full_test_debt,
        "run_check_from_existing_payload",
        fake_run_check_from_existing_payload,
    )

    result = full_debt_mod.try_run_special_full_test_debt_mode(
        repo_root=str(tmp_path),
        entry={"entry_id": "full_test_debt"},
        current_fingerprint={"hash": "sha256:current"},
        decision={
            "decision": "run",
            "reason": "input fingerprint changed",
            "previous_result_path": "evidence/QualityGate/long_gate/results/full_test_debt.success.json",
        },
        evaluation={},
        cache_dir="evidence/QualityGate/long_gate",
    )

    assert result is not None
    assert result["returncode"] == 0
    assert result["reused_from"]["changed_helpers"] == ["tests/long_gate_cache_helpers.py"]
    assert result["reused_from"]["affected_test_files"] == [
        "tests/test_long_gate_required_regression_cache.py",
        "tests/test_long_gate_startup_regression_cache.py",
    ]
    assert seen_payloads[0]["incremental_proof"]["changed_helpers"] == ["tests/long_gate_cache_helpers.py"]
    assert seen_payloads[0]["incremental_proof"]["declared_helper_impacts"] == plan["declared_helper_impacts"]
    assert seen_payloads[0]["incremental_proof"]["actual_importing_test_files"] == plan[
        "actual_importing_test_files"
    ]
    current_payload = json.loads(
        (tmp_path / "evidence" / "QualityGate" / "current_full_test_debt.json").read_text(encoding="utf-8")
    )
    assert current_payload["incremental_proof"]["affected_test_files"] == [
        "tests/test_long_gate_required_regression_cache.py",
        "tests/test_long_gate_startup_regression_cache.py",
    ]
    assert (tmp_path / NODE_CACHE_REL).exists()


def test_helper_incremental_still_rejects_selected_failure(monkeypatch, tmp_path):
    selected = [
        "tests/test_long_gate_required_regression_cache.py::test_required",
        "tests/test_long_gate_startup_regression_cache.py::test_startup",
    ]
    collect_snapshot = _collect_snapshot_for_mapping(
        {
            "tests/test_long_gate_required_regression_cache.py": [selected[0]],
            "tests/test_long_gate_startup_regression_cache.py": [selected[1]],
        }
    )
    old_payload = _current_payload_for_nodeids(selected)
    node_cache = {
        "current_payload": old_payload,
        "payload_hash": "sha256:node-cache",
    }
    plan = {
        "mode": "nodeid_incremental",
        "changed_paths": ["tests/long_gate_cache_helpers.py"],
        "changed_test_files": [
            "tests/test_long_gate_required_regression_cache.py",
            "tests/test_long_gate_startup_regression_cache.py",
        ],
        "changed_helpers": ["tests/long_gate_cache_helpers.py"],
        "declared_helper_impacts": {
            "tests/long_gate_cache_helpers.py": [
                "tests/test_long_gate_required_regression_cache.py",
                "tests/test_long_gate_startup_regression_cache.py",
            ]
        },
        "actual_importing_test_files": [
            "tests/test_long_gate_required_regression_cache.py",
            "tests/test_long_gate_startup_regression_cache.py",
        ],
        "affected_test_files": [
            "tests/test_long_gate_required_regression_cache.py",
            "tests/test_long_gate_startup_regression_cache.py",
        ],
        "selected_nodeids": selected,
    }
    stale_current = tmp_path / "evidence" / "QualityGate" / "current_full_test_debt.json"
    stale_summary = tmp_path / "evidence" / "QualityGate" / "full_test_debt_summary.json"
    stale_node_cache = tmp_path / NODE_CACHE_REL
    stale_current.parent.mkdir(parents=True, exist_ok=True)
    stale_current.write_text("stale-current\n", encoding="utf-8")
    stale_summary.write_text("stale-summary\n", encoding="utf-8")
    stale_node_cache.write_text("stale-node-cache\n", encoding="utf-8")
    seen_payloads = []

    monkeypatch.setattr(
        full_debt_mod,
        "_validated_previous_success",
        lambda **_kwargs: (
            {
                "status": "passed",
                "returncode": 0,
                "fingerprint": {"hash": "sha256:previous"},
                "fingerprint_hash": "sha256:previous",
            },
            "",
        ),
    )
    monkeypatch.setattr(full_debt_mod, "_load_node_cache", lambda *_args, **_kwargs: (node_cache, ""))
    monkeypatch.setattr(full_debt_mod, "_load_collect_snapshot", lambda *_args, **_kwargs: (collect_snapshot, ""))
    monkeypatch.setattr(full_debt_mod, "_load_ledger_for_repo", lambda *_args, **_kwargs: _empty_test_debt_ledger())
    monkeypatch.setattr(full_debt_mod, "_classify_incremental_plan", lambda **_kwargs: (plan, ""))
    monkeypatch.setattr(
        full_debt_mod,
        "_run_incremental_collector",
        lambda *_args, **_kwargs: {
            "stdout": "selected failed\n",
            "stderr": "",
            "returncode": 1,
            "payload": {
                "exitstatus": 1,
                "collected_nodeids": list(selected),
                "reports": [_failed_report(selected[0]), _passed_report(selected[1])],
                "collection_errors": [],
            },
            "pytest_args": [*selected, "-q", "--tb=short", "-ra", "-p", "no:cacheprovider"],
            "collector_contract_error": False,
        },
    )

    def fake_run_check_from_existing_payload(payload, *, ledger=None, require_clean_worktree_proof=True):
        seen_payloads.append(dict(payload))
        raise full_debt_mod.QualityGateError("checker rejected helper merged payload")

    monkeypatch.setattr(
        full_debt_mod.check_full_test_debt,
        "run_check_from_existing_payload",
        fake_run_check_from_existing_payload,
    )

    result = full_debt_mod.try_run_special_full_test_debt_mode(
        repo_root=str(tmp_path),
        entry={"entry_id": "full_test_debt"},
        current_fingerprint={"hash": "sha256:current"},
        decision={
            "decision": "run",
            "reason": "input fingerprint changed",
            "previous_result_path": "evidence/QualityGate/long_gate/results/full_test_debt.success.json",
        },
        evaluation={},
        cache_dir="evidence/QualityGate/long_gate",
    )

    assert result is not None
    assert result["returncode"] == 2
    assert "checker rejected helper merged payload" in result["stderr"]
    assert seen_payloads[0]["incremental_proof"]["changed_helpers"] == ["tests/long_gate_cache_helpers.py"]
    assert stale_current.read_text(encoding="utf-8") == "stale-current\n"
    assert stale_summary.read_text(encoding="utf-8") == "stale-summary\n"
    assert stale_node_cache.read_text(encoding="utf-8") == "stale-node-cache\n"


def test_runner_writes_and_reuses_full_test_debt_success_cache(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], [], [], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    calls: List[str] = []
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
        ".codestable/tools/validate-yaml.py",
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
        NODE_CACHE_REL,
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


def test_explain_full_test_debt_reports_direct_check_outputs_do_not_warm_cache(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    _write_full_outputs(repo_root, token="direct-check")
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: _quality_gate_plan())

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("explain must not execute commands")

    monkeypatch.setattr(module, "_run_command", fail_if_called)

    assert module.main(["--long-gate-cache-explain"]) == 0

    output = capsys.readouterr().out
    assert "- full_test_debt: RUN" in output
    assert "cache_state: missing" in output
    assert "direct_check_outputs:" in output
    assert "tools/check_full_test_debt.py writes current/summary proof" in output
    assert "scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache" in output
    assert not _success_path(repo_root).exists()


def test_explain_full_test_debt_reports_special_fallback_diagnostics(monkeypatch, tmp_path, capsys):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], [], [], []])
    monkeypatch.setattr(module, "REPO_ROOT", str(repo_root))
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    calls: List[str] = []
    monkeypatch.setattr(module, "_run_command", _fake_successful_command(module, repo_root, calls))
    assert module.main(["--long-gate-cache"]) == 0

    _write_file(repo_root, "tests/test_a.py", "def test_a():\n    assert True\n# changed\n")
    capsys.readouterr()

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("explain must not execute commands")

    monkeypatch.setattr(module, "_run_command", fail_if_called)

    assert module.main(["--long-gate-cache-explain"]) == 0

    output = capsys.readouterr().out
    assert "- full_test_debt: RUN" in output
    assert "fingerprint_changed_components:" in output
    assert "files: added input file path=tests/test_a.py" in output
    assert "full_test_debt_incremental:" in output
    assert "previous_success_path: evidence/QualityGate/long_gate/results/full_test_debt.success.json" in output
    assert "previous_success_returncode: 0" in output
    assert f"node_cache_path: {NODE_CACHE_REL}" in output
    assert "node_cache_collect_nodeid_count: 1" in output
    assert "fallback_reason:" in output


def test_force_rerun_full_test_debt_refreshes_only_that_enabled_entry(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _quality_gate_plan(include_planned=True)
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], [], [], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    calls: List[str] = []
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
    ruff = _summary_entry(summary, "ruff_check_full")
    assert "python -m pytest --collect-only -q tests" not in calls
    assert "python tools/check_full_test_debt.py" in calls
    assert "python -m ruff check" not in calls
    assert collect["execution_mode"] == "reused_success_cache"
    assert full_debt["execution_mode"] == "executed"
    assert full_debt["reason"] == "forced by --long-gate-force-rerun full_test_debt"
    assert [row["sha256"] for row in _load_success(repo_root)["output_files"]] != first_output_hashes
    assert ruff["decision"] == "reuse"
    assert ruff["cache_status"] == "enabled"
    assert ruff["execution_mode"] == "reused_success_cache"
    assert _success_path(repo_root, "ruff_check_full").exists()
    assert (repo_root / "evidence" / "QualityGate" / "full_test_debt_node_cache.json").exists()


def test_force_rerun_all_refreshes_full_test_debt_and_static_entries(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _quality_gate_plan(include_planned=True)
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], [], [], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    calls: List[str] = []
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
    ruff = _summary_entry(summary, "ruff_check_full")
    assert "python -m pytest --collect-only -q tests" in calls
    assert "python tools/check_full_test_debt.py" in calls
    assert "python -m ruff check" in calls
    assert collect["reason"] == "forced by --long-gate-force-rerun-all"
    assert full_debt["reason"] == "forced by --long-gate-force-rerun-all"
    assert full_debt["execution_mode"] == "executed"
    assert [row["sha256"] for row in _load_success(repo_root)["output_files"]] != first_output_hashes
    assert ruff["decision"] == "run"
    assert ruff["cache_status"] == "enabled"
    assert ruff["reason"] == "forced by --long-gate-force-rerun-all"
    assert ruff["execution_mode"] == "executed"
    assert _success_path(repo_root, "ruff_check_full").exists()


def test_full_test_debt_rechecks_collect_hash_after_collect_rerun(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], [], [], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    calls: List[str] = []
    collect_stdout = {"text": "tests/test_a.py::test_a\n"}

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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
    calls: List[str] = []
    monkeypatch.setattr(module, "_run_command", _fake_successful_command(module, repo_root, calls))

    assert module.main(["--long-gate-cache"]) == 0
    _write_file(repo_root, "tests/test_a.py", "def test_a():\n    assert 1 == 1\n# changed\n")
    calls.clear()
    special_calls: List[Dict[str, Any]] = []

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

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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
    calls: List[str] = []
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

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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
    assert not _failure_path(repo_root).exists()


def test_runner_reuses_strict_full_test_debt_failure_cache(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[] for _ in range(12)])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    calls: List[str] = []

    def first_run_command(display, args, capture_output=False, env_overlay=None):
        calls.append(display)
        if display == "python -m pytest --collect-only -q tests":
            return {"stdout": "tests/test_a.py::test_a\n", "stderr": "", "returncode": 0}
        if display == "python tools/check_full_test_debt.py":
            _write_full_outputs(repo_root, token="failed-before-exit")
            return {"stdout": "full debt failed\n", "stderr": "AssertionError: debt\n", "returncode": 1}
        return {"stdout": "", "stderr": "", "returncode": 0}

    monkeypatch.setattr(module, "_run_command", first_run_command)

    with pytest.raises(module.QualityGateError):
        module.main(["--long-gate-cache"])

    failure = _load_failure(repo_root)
    first_summary = _load_summary(repo_root)
    full_debt = _summary_entry(first_summary, "full_test_debt")
    assert failure["status"] == "failed"
    assert failure["returncode"] == 1
    assert failure["output_files"] == []
    assert (repo_root / failure["stdout_log_path"]).exists()
    assert full_debt["failed"] is True
    assert full_debt["execution_mode"] == "executed"
    assert not _success_path(repo_root).exists()
    assert not (repo_root / "evidence" / "QualityGate" / "current_full_test_debt.json").exists()
    assert not (repo_root / "evidence" / "QualityGate" / "full_test_debt_summary.json").exists()
    assert not (repo_root / NODE_CACHE_REL).exists()

    calls.clear()

    def second_run_command(display, args, capture_output=False, env_overlay=None):
        calls.append(display)
        if display == "python -m pytest --collect-only -q tests":
            return {"stdout": "tests/test_a.py::test_a\n", "stderr": "", "returncode": 0}
        if display == "python tools/check_full_test_debt.py":
            raise AssertionError("full_test_debt should reuse cached failure instead of rerunning")
        return {"stdout": "", "stderr": "", "returncode": 0}

    monkeypatch.setattr(module, "_run_command", second_run_command)

    with pytest.raises(module.QualityGateError):
        module.main(["--long-gate-cache"])

    second_summary = _load_summary(repo_root)
    full_debt = _summary_entry(second_summary, "full_test_debt")
    assert "python tools/check_full_test_debt.py" not in calls
    assert full_debt["failed"] is True
    assert full_debt["execution_mode"] == "cached_failure"
    assert second_summary["counts"]["failed"] == 1
    assert second_summary["counts"]["reused"] == 0


def test_runner_does_not_reuse_or_write_failure_cache_for_dirty_worktree(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[" M tests/test_a.py"], [" M tests/test_a.py"]])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    calls: List[str] = []
    failure_path = _failure_path(repo_root)
    failure_path.parent.mkdir(parents=True, exist_ok=True)
    failure_path.write_text("seeded-dirty-failure-cache\n", encoding="utf-8")

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
        calls.append(display)
        if display == "python -m pytest --collect-only -q tests":
            return {"stdout": "tests/test_a.py::test_a\n", "stderr": "", "returncode": 0}
        if display.startswith("python tools/check_full_test_debt.py"):
            _write_full_outputs(repo_root, token="dirty-failure")
            return {"stdout": "full debt failed\n", "stderr": "dirty failure\n", "returncode": 1}
        return {"stdout": "", "stderr": "", "returncode": 0}

    monkeypatch.setattr(module, "_run_command", fake_run_command)

    with pytest.raises(module.QualityGateError):
        module.main(["--allow-dirty-worktree", "--no-resume", "--long-gate-cache"])

    assert any(display.startswith("python tools/check_full_test_debt.py") for display in calls)
    assert failure_path.read_text(encoding="utf-8") == "seeded-dirty-failure-cache\n"


@pytest.mark.parametrize("force_args", [["--long-gate-force-rerun", "full_test_debt"], ["--long-gate-force-rerun-all"]])
def test_runner_does_not_reuse_failure_cache_when_forced(monkeypatch, tmp_path, force_args):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[] for _ in range(12)])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    calls: List[str] = []

    def first_run_command(display, args, capture_output=False, env_overlay=None):
        if display == "python -m pytest --collect-only -q tests":
            return {"stdout": "tests/test_a.py::test_a\n", "stderr": "", "returncode": 0}
        if display == "python tools/check_full_test_debt.py":
            _write_full_outputs(repo_root, token="forced-seed-failure")
            return {"stdout": "full debt failed\n", "stderr": "seed failure\n", "returncode": 1}
        return {"stdout": "", "stderr": "", "returncode": 0}

    monkeypatch.setattr(module, "_run_command", first_run_command)
    with pytest.raises(module.QualityGateError):
        module.main(["--long-gate-cache"])
    assert _failure_path(repo_root).exists()
    seeded_failure_cache = _failure_path(repo_root).read_text(encoding="utf-8")

    def forced_run_command(display, args, capture_output=False, env_overlay=None):
        calls.append(display)
        if display == "python -m pytest --collect-only -q tests":
            return {"stdout": "tests/test_a.py::test_a\n", "stderr": "", "returncode": 0}
        if display == "python tools/check_full_test_debt.py":
            _write_full_outputs(repo_root, token="forced-reran")
            return {"stdout": "full debt failed again\n", "stderr": "forced failure\n", "returncode": 1}
        return {"stdout": "", "stderr": "", "returncode": 0}

    monkeypatch.setattr(module, "_run_command", forced_run_command)

    with pytest.raises(module.QualityGateError):
        module.main(["--long-gate-cache", *force_args])

    full_debt = _summary_entry(_load_summary(repo_root), "full_test_debt")
    assert "python tools/check_full_test_debt.py" in calls
    assert full_debt["execution_mode"] == "executed"
    assert full_debt["reason"].startswith("forced by --long-gate-force-rerun")
    assert _failure_path(repo_root).read_text(encoding="utf-8") == seeded_failure_cache


def test_runner_fails_when_ledger_only_checker_fails_without_full_fallback(monkeypatch, tmp_path):
    module = _import_run_quality_gate()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    command_plan = _quality_gate_plan()
    _patch_gate_environment(monkeypatch, module, repo_root, statuses=[[], [], [], [], [], []])
    monkeypatch.setattr(module, "build_quality_gate_command_plan", lambda: list(command_plan))
    calls: List[str] = []
    monkeypatch.setattr(module, "_run_command", _fake_successful_command(module, repo_root, calls))

    assert module.main(["--long-gate-cache"]) == 0
    _write_ledger_file(repo_root)
    calls.clear()

    def fake_special(**kwargs):
        return {
            "stdout": "",
            "stderr": "ledger-only checker rejected payload\n",
            "returncode": 2,
            "execution_mode": "ledger_only",
            "reused_from": {
                "node_cache_path": NODE_CACHE_REL,
                "previous_result_path": kwargs["decision"].get("previous_result_path") or "",
                "fingerprint_hash": kwargs["decision"].get("current_fingerprint_hash") or "sha256:previous",
            },
        }

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
        calls.append(display)
        if display == "python -m pytest --collect-only -q tests":
            return {"stdout": "tests/test_a.py::test_a\n", "stderr": "", "returncode": 0}
        if display == "python tools/check_full_test_debt.py":
            raise AssertionError("whole full_test_debt command must not hide ledger-only failure")
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
    assert full_debt["execution_mode"] == "ledger_only"
    assert "python tools/check_full_test_debt.py" not in calls
    assert not _failure_path(repo_root).exists()


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
    calls: List[str] = []
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
    fingerprint = fingerprint_entry(entry, str(repo_root), strict=True)
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
    calls: List[str] = []

    def fake_run_command(display, args, capture_output=False, env_overlay=None):
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
