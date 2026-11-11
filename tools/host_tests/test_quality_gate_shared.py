"""Host-only source and receipt contracts; these tests do not enter the product gate."""

import base64
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import run_quality_gate as runner
from scripts.workbench import vendor_react
from tools import benchmark_full_test_debt_shards as shard_tool
from tools import quality_gate_shared as shared
from tools import report_full_test_debt_durations as report_tool
from tools.long_gate_manifest import build_manifest_from_quality_gate_plan
from tools.long_gate_schema import canonical_content, repo_identity
from tools.test_registry import iter_required_regression_groups, validate_test_registry


def _command(policy="exact"):
    return {
        "display": "python receipt-content-contract",
        "args": [sys.executable, "-c", "print('real output')"],
        "capture_output": True,
        "output_policy": policy,
        "env_overlay": {},
    }


def _receipt_files(root, command, stdout="real output\n", *, run_id="run-content"):
    logs = shared.QUALITY_GATE_LOGS_DIR_REL.replace("\\", "/")
    stdout_path, stderr_path = logs + "/01.stdout.log", logs + "/01.stderr.log"
    (root / logs).mkdir(parents=True, exist_ok=True)
    with (root / stdout_path).open("w", encoding="utf-8", newline="") as stream:
        stream.write(shared.sanitize_quality_gate_output(stdout))
    with (root / stderr_path).open("w", encoding="utf-8", newline="") as stream:
        stream.write("")
    receipt = shared.build_quality_gate_command_receipt(
        command, run_id=run_id, command_index=1, returncode=0, stdout=stdout,
        stdout_log_path=stdout_path, stderr_log_path=stderr_path,
    )
    path = shared.build_quality_gate_receipt_rel_path(1, command["display"])
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_text(canonical_content(receipt), encoding="utf-8")
    return receipt, {"path": path, "content": receipt}


def test_schema4_binds_original_source_and_receipt_content(tmp_path, monkeypatch):
    monkeypatch.setattr(shared, "QUALITY_GATE_SOURCE_FILES", ["source.py"])
    original = b"source\x00\xff\n"
    (tmp_path / "source.py").write_bytes(original)
    sources = shared.build_quality_gate_source_proof(tmp_path)
    assert sources == [{"path": "source.py", "exists": True, "content_base64": base64.b64encode(original).decode("ascii")}]

    command = _command()
    receipt, entry = _receipt_files(tmp_path, command)
    manifest = shared.apply_quality_gate_manifest_proof_fields(
        {"commands": [command], "command_receipts": [entry], "gate_sources": sources}, repo_root=tmp_path,
    )
    assert manifest["schema_version"] == 4
    assert shared._load_verified_quality_gate_receipt(tmp_path, entry, command, index=1) == (receipt, None)
    assert "evidence/QualityGate/v4/receipts/01_" in entry["path"]

    changed = {**receipt, "returncode": False}
    (tmp_path / entry["path"]).write_text(canonical_content(changed), encoding="utf-8")
    assert shared._load_verified_quality_gate_receipt(tmp_path, entry, command, index=1)[1].endswith("content mismatch")


def test_receipt_output_policy_sanitizes_and_checks_actual_logs(tmp_path, monkeypatch):
    secret = "private-runtime-value-for-contract"
    monkeypatch.setenv("SECRET_KEY", f"  {secret}  ")
    monkeypatch.setenv("TOKENIZERS_PARALLELISM", "false")
    monkeypatch.setenv("CUSTOM_TOKEN", "false")
    assert shared.sanitize_quality_gate_output(f"leaked={secret}\n") == "leaked=[REDACTED]\n"
    command = _command("normalized")
    stdout = "1 passed in 1.20s (token=false)\r\n" + secret + "\r\n"
    receipt, entry = _receipt_files(tmp_path, command, stdout)
    assert receipt["stdout_content"] == "1 passed in <seconds>s (token=false)\n[REDACTED]\n"
    assert secret not in canonical_content(entry)
    assert secret not in (tmp_path / receipt["stdout_log_path"]).read_text(encoding="utf-8")
    monkeypatch.setenv("SECRET_KEY", "   ")
    assert shared.sanitize_quality_gate_output("a b c\n") == "a b c\n"
    monkeypatch.setenv("SECRET_KEY", secret)
    with pytest.raises(shared.QualityGateError) as error:
        shared.normalize_quality_gate_command({**command, "env_overlay": {"SECRET_KEY": secret}})
    assert "SECRET_KEY" in str(error.value) and secret not in str(error.value)
    with pytest.raises(shared.QualityGateError, match="SECRET_KEY"):
        shared.normalize_quality_gate_command({**command, "env_overlay": {"SECRET_KEY": ""}})
    with pytest.raises(shared.QualityGateError, match="allowlist"):
        shared.normalize_quality_gate_command({**command, "env_overlay": {"TOKENIZERS_PARALLELISM": "false"}})
    with pytest.raises(ValueError, match="Unsupported quality gate output_policy"):
        shared.normalize_quality_gate_command({**command, "output_policy": "passthrough"})


def test_legacy_hash_only_evidence_is_rejected_without_content(tmp_path):
    command = _command()
    payload, error = shared._load_verified_quality_gate_receipt(
        tmp_path, {"path": "evidence/QualityGate/receipts/original.json", "sha256": "saved-receipt-proof"}, command, index=1,
    )
    assert payload is None and error == "UNBOUND: quality gate command receipt content missing"
    with pytest.raises(shared.QualityGateError, match="receipt content is unavailable"):
        shared.apply_quality_gate_manifest_proof_fields(
            {"command_receipts": [{"path": "evidence/QualityGate/receipts/original.json", "sha256": "saved-receipt-proof"}]},
            repo_root=tmp_path,
        )
    with pytest.raises(shared.QualityGateError, match="source content is unavailable"):
        shared.apply_quality_gate_manifest_proof_fields(
            {"gate_sources": [{"path": "source.py", "exists": True, "sha256": "saved-source-proof"}]}, repo_root=tmp_path,
        )


def test_receipt_verification_primitives_check_index_path_and_execution_fields(tmp_path):
    command = _command()
    receipt, entry = _receipt_files(tmp_path, command)
    assert "command_index mismatch" in shared._verify_receipt_header(receipt, index=2, run_id="run-content")
    assert "path mismatch" in shared._load_verified_quality_gate_receipt(
        tmp_path, {**entry, "path": entry["path"].replace("01_", "02_")}, command, index=1,
    )[1]
    assert "incomplete execution" in shared._verify_receipt_execution_fields({**receipt, "interrupted": True})
    raw_receipt, _raw_entry = _receipt_files(tmp_path, command, "real output\r\n")
    assert shared.read_text_file(str(tmp_path / raw_receipt["stdout_log_path"])) == "real output\r\n"


def test_gate_check_specs_and_registry_cover_all_production_sources(tmp_path):
    specs = shared.build_quality_gate_check_specs()
    dirty_specs = shared.build_quality_gate_check_specs(allow_dirty_worktree=True)
    check_ids = [spec.check_id for spec in specs]
    assert len(check_ids) == len(set(check_ids))
    assert "py38_syntax_check" in check_ids
    assert "roadmap_yaml_validation" in check_ids
    clean_full = next(spec for spec in specs if spec.check_id == shared.ENTRY_FULL_TEST_DEBT)
    dirty_full = next(spec for spec in dirty_specs if spec.check_id == shared.ENTRY_FULL_TEST_DEBT)
    assert "--allow-dirty-worktree-proof" not in clean_full.args
    assert "--allow-dirty-worktree-proof" in dirty_full.args
    assert "APS_FULL_TEST_DEBT_SHARD_COUNT" not in clean_full.env_keys
    assert clean_full.reuse_policy == "success_or_failure"
    assert clean_full.reuse_allowed is True
    assert {spec.check_id: spec.reuse_policy for spec in specs if not spec.reuse_allowed} == {
        "ruff_version_probe": "none",
        "pyright_version_probe": "none",
        "radon_import_probe": "none",
        shared.ENTRY_ROADMAP_YAML_VALIDATION: "none",
        shared.ENTRY_PY38_SYNTAX_CHECK: "none",
    }
    assert {spec.check_id for spec in specs if spec.reuse_policy == "success_or_failure"} == {
        shared.ENTRY_FULL_TEST_DEBT,
    }
    assert all(
        spec.reuse_policy == "success" and spec.reuse_allowed
        for spec in specs
        if spec.reuse_allowed and spec.check_id != shared.ENTRY_FULL_TEST_DEBT
    )
    manifest = build_manifest_from_quality_gate_plan(specs)
    assert [entry["reuse_policy"] for entry in manifest["entries"]] == [spec.reuse_policy for spec in specs]
    assert [entry["reuse_allowed"] for entry in manifest["entries"]] == [spec.reuse_allowed for spec in specs]
    assert manifest["quality_gate_plan"] == [
        shared.normalize_quality_gate_command(spec.to_command_dict()) for spec in specs
    ]
    base_cmd = shared.normalize_quality_gate_command(clean_full.to_command_dict())
    assert {
        key: base_cmd[key]
        for key in ("check_id", "entry_type", "proof_kind", "reuse_policy", "runner_handler")
    } == {
        "check_id": clean_full.check_id,
        "entry_type": clean_full.entry_type,
        "proof_kind": clean_full.proof_kind,
        "reuse_policy": clean_full.reuse_policy,
        "runner_handler": clean_full.runner_handler,
    }
    base_receipt, _ = _receipt_files(tmp_path, clean_full.to_command_dict())
    assert shared._verify_receipt_command_fields(base_receipt, base_cmd) is None
    for field, mutated_value in (
        ("check_id", "other_check_id"),
        ("entry_type", "other_entry_type"),
        ("proof_kind", "static_check"),
        ("reuse_policy", "success"),
        ("runner_handler", "pytest_collect_all"),
    ):
        mutated_spec = replace(clean_full, **{field: mutated_value})
        mutated_cmd = shared.normalize_quality_gate_command(mutated_spec.to_command_dict())
        assert mutated_cmd != base_cmd
        assert f"{field} mismatch" in (shared._verify_receipt_command_fields(base_receipt, mutated_cmd) or "")
    shared_type_specs = [
        replace(clean_full, check_id="custom_check_alpha", entry_type="shared_kind"),
        replace(clean_full, check_id="custom_check_beta", entry_type="shared_kind"),
    ]
    with pytest.raises(shared.QualityGateError, match="check_id: shared_kind"):
        runner._prepare_long_gate_cache_decisions(
            shared_type_specs,
            cache_enabled=False,
            cache_dir="evidence/QualityGate/long_gate",
            force_rerun_entry_ids=["shared_kind"],
        )
    assert {spec.check_id: spec.proof_kind for spec in specs if spec.proof_kind is not None} == {
        shared.ENTRY_RUFF_CHECK_FULL: "static_check",
        shared.ENTRY_PYTEST_COLLECT_ALL: "collect_nodeids",
        shared.ENTRY_PYRIGHT_GATE_FULL: "static_check",
        shared.ENTRY_PYRIGHT_TOOLS_FULL: "static_check",
        shared.ENTRY_DEBT_LEDGER_SYNC: "debt_ledger_sync",
        shared.ENTRY_FULL_TEST_DEBT: "full_test_debt",
        shared.ENTRY_REQUIRED_REGRESSIONS: "required_regressions",
    }
    expected_esbuild_scopes = {
        "scripts/workbench/esbuild-manifest.json",
        "scripts/workbench/*.cjs",
        "scripts/workbench/*.py",
        "vendor/node_modules/esbuild/package.json",
        "vendor/node_modules/esbuild/lib/main.js",
        "vendor/node_modules/esbuild/bin/esbuild",
        "vendor/node_modules/@esbuild/*/package.json",
        "vendor/node_modules/@esbuild/*/bin/esbuild*",
        "vendor/node_modules/@esbuild/*/esbuild.exe",
    }
    assert expected_esbuild_scopes <= set(clean_full.tool_file_scopes)
    assert expected_esbuild_scopes <= set(clean_full.dependency_file_scopes)
    workbench_group = next(g for g in iter_required_regression_groups() if g["group_id"] == "workbench")
    assert expected_esbuild_scopes <= set(workbench_group["tool_file_scopes"])
    assert expected_esbuild_scopes <= set(workbench_group["dependency_file_scopes"])
    verified_esbuild = vendor_react.verify_esbuild_vendor()
    assert verified_esbuild["status"] == "verified"
    assert verified_esbuild["version"] == "0.25.12"
    coverage = validate_test_registry()
    assert coverage["uncovered_sources"] == []
    with pytest.raises(FileNotFoundError):
        shared.build_quality_gate_check_specs(repo_root=str(tmp_path))
    gate_cfg = tmp_path / shared.QUALITY_GATE_PYRIGHT_GATE_CONFIG
    gate_cfg.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        shared.build_quality_gate_check_specs(repo_root=str(tmp_path))
    gate_cfg.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="include"):
        shared.build_quality_gate_check_specs(repo_root=str(tmp_path))
    with pytest.raises(RuntimeError, match="git rev-parse"):
        repo_identity(str(tmp_path))


FRESH_NODEID = "tests/new/test_fresh.py::test_fresh"
RETIRED_NODEID = "tests/old/test_retired.py::test_retired"


def _write_debt_payload(path, nodeid, duration):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "collected_nodeids": [nodeid],
        "reports": [{"nodeid": nodeid, "when": "call", "outcome": "passed", "duration": duration}],
        "summary": {"collected_count": 1},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture
def analysis_repo(tmp_path, monkeypatch):
    """以 tmp_path 作仓库根：v4 current 是新数据，旧根 current 是迁移前的历史数据；cwd 是空目录。"""
    current = _write_debt_payload(tmp_path / shared.QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL, FRESH_NODEID, 1.0)
    legacy = _write_debt_payload(
        tmp_path / shared.QUALITY_GATE_LEGACY_ROOT_REL / "current_full_test_debt.json", RETIRED_NODEID, 9.0
    )
    (tmp_path / "cwd").mkdir()
    monkeypatch.setattr(report_tool, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(shard_tool, "REPO_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path / "cwd")
    return current, legacy


def test_duration_report_defaults_to_shared_current_and_keeps_explicit_history(analysis_repo, capsys):
    current, legacy = analysis_repo
    assert report_tool.main([]) == 0
    output = capsys.readouterr().out
    assert FRESH_NODEID in output and "tests/old/" not in output

    assert report_tool.main([str(legacy)]) == 0
    assert RETIRED_NODEID in capsys.readouterr().out

    current.unlink()
    with pytest.raises(FileNotFoundError):
        report_tool.main([])


def test_shard_estimate_defaults_to_shared_current_and_keeps_explicit_history(analysis_repo, capsys):
    current, legacy = analysis_repo
    assert shard_tool.main(["--counts", "2"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["total_count"] == 1
    assert result["distributions"][0]["estimated_report_s"] == 1.0
    assert result["source_payload"] == shared.QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL

    assert shard_tool.main(["--counts", "2", "--payload", str(legacy)]) == 0
    assert json.loads(capsys.readouterr().out)["distributions"][0]["estimated_report_s"] == 9.0

    current.unlink()
    with pytest.raises(FileNotFoundError):
        shard_tool.main(["--counts", "2"])


def test_direct_script_entries_bootstrap_outside_repo_root(analysis_repo, tmp_path):
    current, _legacy = analysis_repo
    tools_dir = Path(report_tool.__file__).resolve().parent
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    commands = {
        FRESH_NODEID: [sys.executable, str(tools_dir / "report_full_test_debt_durations.py"), str(current)],
        '"estimated_report_s": 1.0': [
            sys.executable, str(tools_dir / "benchmark_full_test_debt_shards.py"),
            "--payload", str(current), "--counts", "2",
        ],
    }
    for expected, command in commands.items():
        completed = subprocess.run(command, cwd=str(tmp_path), env=env, capture_output=True, text=True, check=False)
        assert completed.returncode == 0, completed.stderr
        assert expected in completed.stdout
