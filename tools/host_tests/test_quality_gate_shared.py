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
from tools.long_gate_fingerprint import fingerprint_environment
from tools.long_gate_manifest import explain_long_gate_impact
from tools.long_gate_paths import GateContext, resolve_repo_root
from tools.long_gate_records import (
    CommandResult,
    Receipt,
    ReceiptRow,
    Rejection,
    admit_receipt,
    build_receipt,
    gate_entries,
)
from tools.long_gate_schema import canonical_content, repo_identity
from tools.test_registry import iter_required_regression_groups, scope_matches_path, validate_test_registry

REPO_ROOT = resolve_repo_root()

def _entry(policy="exact", **spec_overrides):
    spec = shared.GateCheckSpec(
        check_id="receipt_content_contract",
        entry_type=shared.ENTRY_VERSION_OR_ENV_PROBE,
        display="python receipt-content-contract",
        args=(sys.executable, "-c", "print('real output')"),
        capture_output=True,
        output_policy=policy,
        reuse_policy="none",
    )
    return gate_entries([replace(spec, **spec_overrides)])[0]


def _receipt_files(root, entry, stdout="real output\n", *, run_id="run-content", **result_overrides):
    """按 runner 的路径规则写一步命令的日志与 receipt；返回 receipt 内容与仓库相对路径。"""
    stdout_path, stderr_path = runner._expected_command_log_rel_paths(entry.index, entry.spec.display)
    for rel_path, text in ((stdout_path, stdout), (stderr_path, "")):
        (root / rel_path).parent.mkdir(parents=True, exist_ok=True)
        with (root / rel_path).open("w", encoding="utf-8", newline="") as stream:
            stream.write(shared.sanitize_quality_gate_output(text))
    result = CommandResult(
        stdout=stdout,
        stderr="",
        returncode=0,
        stdout_log_path=stdout_path,
        stderr_log_path=stderr_path,
        execution_mode="executed",
        reused_from={},
        started_at="2026-11-16T00:00:00",
        ended_at="2026-11-16T00:00:01",
        duration_s=0.5,
        duration_kind="executed",
        original_duration_s=None,
    )
    receipt = build_receipt(
        entry.command,
        run_id=run_id,
        command_index=entry.index,
        result=replace(result, **result_overrides),
        environment=fingerprint_environment(entry.spec.env_keys, repo_root=str(root)),
    )
    path = shared.build_quality_gate_receipt_rel_path(entry.index, entry.spec.display)
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_text(canonical_content(receipt), encoding="utf-8")
    return receipt, path


def test_schema5_binds_original_source_and_receipt_content(tmp_path, monkeypatch):
    monkeypatch.setattr(shared, "QUALITY_GATE_SOURCE_FILES", ["source.py"])
    original = b"source\x00\xff\n"
    (tmp_path / "source.py").write_bytes(original)
    sources = shared.build_quality_gate_source_proof(tmp_path)
    assert sources == [{"path": "source.py", "exists": True, "content_base64": base64.b64encode(original).decode("ascii")}]

    entry = _entry()
    receipt, path = _receipt_files(tmp_path, entry)
    assert path.startswith("evidence/QualityGate/v4/receipts/01_")
    admitted = admit_receipt(str(tmp_path), path)
    assert isinstance(admitted, Receipt)
    assert admitted.payload == receipt
    assert (admitted.command, admitted.run_id, admitted.command_index) == (entry.command, "run-content", 1)

    (tmp_path / path).write_text(canonical_content({**receipt, "returncode": False}), encoding="utf-8")
    rejected = admit_receipt(str(tmp_path), path)
    assert isinstance(rejected, Rejection)
    assert rejected.reason == "UNBOUND: quality gate command receipt returncode invalid"


def test_receipt_output_policy_sanitizes_and_checks_actual_logs(tmp_path, monkeypatch):
    secret = "private-runtime-value-for-contract"
    monkeypatch.setenv("SECRET_KEY", f"  {secret}  ")
    monkeypatch.setenv("TOKENIZERS_PARALLELISM", "false")
    monkeypatch.setenv("CUSTOM_TOKEN", "false")
    assert shared.sanitize_quality_gate_output(f"leaked={secret}\n") == "leaked=[REDACTED]\n"
    entry = _entry("normalized")
    stdout = "1 passed in 1.20s (token=false)\r\n" + secret + "\r\n"
    receipt, path = _receipt_files(tmp_path, entry, stdout)
    assert receipt["stdout_content"] == "1 passed in <seconds>s (token=false)\n[REDACTED]\n"
    assert secret not in (tmp_path / path).read_text(encoding="utf-8")
    assert secret not in (tmp_path / receipt["stdout_log_path"]).read_text(encoding="utf-8")
    monkeypatch.setenv("SECRET_KEY", "   ")
    assert shared.sanitize_quality_gate_output("a b c\n") == "a b c\n"
    monkeypatch.setenv("SECRET_KEY", secret)
    command = entry.command
    with pytest.raises(shared.QualityGateError) as error:
        shared.normalize_quality_gate_command({**command, "env_overlay": {"SECRET_KEY": secret}})
    assert "SECRET_KEY" in str(error.value) and secret not in str(error.value)
    with pytest.raises(shared.QualityGateError, match="SECRET_KEY"):
        shared.normalize_quality_gate_command({**command, "env_overlay": {"SECRET_KEY": ""}})
    with pytest.raises(shared.QualityGateError, match="allowlist"):
        shared.normalize_quality_gate_command({**command, "env_overlay": {"TOKENIZERS_PARALLELISM": "false"}})
    with pytest.raises(ValueError, match="Unsupported quality gate output_policy"):
        shared.normalize_quality_gate_command({**command, "output_policy": "passthrough"})


def test_receipt_admission_checks_path_execution_mode_and_reused_from(tmp_path):
    entry = _entry()
    receipt, path = _receipt_files(tmp_path, entry)
    outside = "evidence/QualityGate/v4/01_outside.json"
    (tmp_path / outside).write_text(canonical_content(receipt), encoding="utf-8")
    assert admit_receipt(str(tmp_path), outside).reason == "UNBOUND: quality gate command receipt path mismatch"
    for overrides, reason in (
        ({"execution_mode": "cached_failure"}, "execution_mode mismatch"),
        ({"execution_mode": "resumed_success_prefix"}, "execution_mode mismatch"),
        ({"execution_mode": "resumed_success", "reused_from": {"run_id": "older"}}, "reused_from receipt_path missing"),
        ({"execution_mode": "reused_success_cache", "reused_from": {"result_path": "r.json"}}, "reused_from completed_at missing"),
    ):
        (tmp_path / path).write_text(canonical_content({**receipt, **overrides}), encoding="utf-8")
        assert admit_receipt(str(tmp_path), path).reason == "UNBOUND: quality gate command receipt " + reason
    (tmp_path / path).unlink()
    missing = admit_receipt(str(tmp_path), path)
    assert missing.reason == "UNBOUND: quality gate command receipt missing"
    raw_receipt, _raw_path = _receipt_files(tmp_path, entry, "real output\r\n")
    assert shared.read_text_file(str(tmp_path / raw_receipt["stdout_log_path"])) == "real output\r\n"


def _link_directory(target, link):
    """目录链接：POSIX 用符号链接，Windows 用不需要管理员权限的目录联接；两者 realpath 都解析到 target。"""
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


def test_receipt_admission_rejects_receipts_directory_linked_outside_repo(tmp_path):
    repo, outside = tmp_path / "repo", tmp_path / "outside_receipts"
    outside.mkdir()
    receipts_dir = repo / shared.QUALITY_GATE_RECEIPTS_DIR_REL
    receipts_dir.parent.mkdir(parents=True)
    _link_directory(outside, receipts_dir)
    entry = _entry()
    receipt, path = _receipt_files(repo, entry)
    assert (outside / Path(path).name).is_file()
    # 单文件与整个 receipts 目录链到仓库外是同一件事：都按真实位置先限定在仓库内，续跑绑定随之拒绝。
    assert admit_receipt(str(repo), path).reason == "UNBOUND: quality gate command receipt path mismatch"
    assert runner._bind_previous_receipt(
        GateContext(str(repo)), ReceiptRow(path, receipt), entry, previous_run_id="run-content"
    ) == "UNBOUND: quality gate command receipt path mismatch"


def test_gate_check_specs_and_registry_cover_all_production_sources(tmp_path, monkeypatch):
    specs = shared.build_quality_gate_check_specs(REPO_ROOT)
    dirty_specs = shared.build_quality_gate_check_specs(REPO_ROOT, allow_dirty_worktree=True)
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
        shared.ENTRY_DEAD_PATH_LITERALS: "none",
    }
    assert {spec.check_id for spec in specs if spec.reuse_policy == "success_or_failure"} == {
        shared.ENTRY_FULL_TEST_DEBT,
    }
    assert all(
        spec.reuse_policy == "success" and spec.reuse_allowed
        for spec in specs
        if spec.reuse_allowed and spec.check_id != shared.ENTRY_FULL_TEST_DEBT
    )
    plan = gate_entries(specs)
    assert [entry.index for entry in plan] == list(range(1, len(specs) + 1))
    assert [entry.command for entry in plan] == [
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
    ctx = GateContext(str(tmp_path))
    base_entry = gate_entries([clean_full])[0]
    base_receipt, base_path = _receipt_files(tmp_path, base_entry)
    bound = runner._bind_previous_receipt(ctx, ReceiptRow(base_path, base_receipt), base_entry, previous_run_id="run-content")
    assert not isinstance(bound, str) and bound.receipt.command == base_cmd
    for field, mutated_value in (
        ("check_id", "other_check_id"),
        ("entry_type", "other_entry_type"),
        ("proof_kind", "static_check"),
        ("reuse_policy", "success"),
        ("runner_handler", "pytest_collect_all"),
    ):
        mutated_entry = gate_entries([replace(clean_full, **{field: mutated_value})])[0]
        assert mutated_entry.command != base_cmd
        assert runner._bind_previous_receipt(
            ctx, ReceiptRow(base_path, base_receipt), mutated_entry, previous_run_id="run-content"
        ) == f"UNBOUND: quality gate command receipt {field} mismatch"
    shared_type_specs = [
        replace(clean_full, check_id="custom_check_alpha", entry_type="shared_kind"),
        replace(clean_full, check_id="custom_check_beta", entry_type="shared_kind"),
    ]
    with pytest.raises(shared.QualityGateError, match="check_id: shared_kind"):
        runner._prepare_long_gate_cache_decisions(
            ctx,
            gate_entries(shared_type_specs),
            cache_enabled=False,
            cache_dir="evidence/QualityGate/long_gate",
            write_success=False,
            force_rerun_entry_ids=["shared_kind"],
            force_rerun_all=False,
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
    host_platform = vendor_react.current_esbuild_platform_key()
    verified_esbuild = vendor_react.verify_esbuild_vendor(
        Path(REPO_ROOT),
        vendor_react.load_esbuild_manifest(),
        host_platform=host_platform,
        target_platform=host_platform,
    )
    assert verified_esbuild["status"] == "verified"
    assert verified_esbuild["version"] == "0.25.12"
    coverage = validate_test_registry(REPO_ROOT)
    assert coverage["uncovered_sources"] == []
    with pytest.raises(FileNotFoundError):
        shared.build_quality_gate_check_specs(str(tmp_path))
    gate_cfg = tmp_path / shared.QUALITY_GATE_PYRIGHT_GATE_CONFIG
    gate_cfg.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        shared.build_quality_gate_check_specs(str(tmp_path))
    gate_cfg.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="include"):
        shared.build_quality_gate_check_specs(str(tmp_path))
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
    monkeypatch.chdir(tmp_path / "cwd")
    return current, legacy


def test_duration_report_defaults_to_shared_current_and_keeps_explicit_history(analysis_repo, tmp_path, capsys):
    current, legacy = analysis_repo
    root = ["--repo-root", str(tmp_path)]
    assert report_tool.main(root) == 0
    output = capsys.readouterr().out
    assert FRESH_NODEID in output and "tests/old/" not in output

    assert report_tool.main([*root, str(legacy)]) == 0
    assert RETIRED_NODEID in capsys.readouterr().out

    current.unlink()
    with pytest.raises(FileNotFoundError):
        report_tool.main(root)


def test_shard_estimate_defaults_to_shared_current_and_keeps_explicit_history(analysis_repo, tmp_path, capsys):
    current, legacy = analysis_repo
    root = ["--repo-root", str(tmp_path)]
    assert shard_tool.main([*root, "--counts", "2"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["total_count"] == 1
    assert result["distributions"][0]["estimated_report_s"] == 1.0
    assert result["source_payload"] == shared.QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL

    assert shard_tool.main([*root, "--counts", "2", "--payload", str(legacy)]) == 0
    assert json.loads(capsys.readouterr().out)["distributions"][0]["estimated_report_s"] == 9.0

    current.unlink()
    with pytest.raises(FileNotFoundError):
        shard_tool.main([*root, "--counts", "2"])


_LOADED_TOOLS_MODULES = (
    "import importlib, sys\n"
    "importlib.import_module(sys.argv[1])\n"
    "print('\\n'.join(sys.modules[name].__file__ for name in sorted(sys.modules) if name.startswith('tools.')))\n"
)


def test_scanner_specs_fingerprint_every_tools_module_the_scanner_loads():
    # 扫描器加载的 tools 模块都要落在规格的工具文件范围里，否则改了它门禁仍会复用旧结果。
    specs = {spec.check_id: spec for spec in shared.build_quality_gate_check_specs(REPO_ROOT)}
    for check_id in (*shared.BOUNDARY_RATCHET_CHECK_IDS, *shared.IMPORT_CYCLE_CHECK_IDS):
        spec = specs[check_id]
        module = spec.args[spec.args.index("-m") + 1]
        completed = subprocess.run(
            [sys.executable, "-c", _LOADED_TOOLS_MODULES, module],
            cwd=REPO_ROOT, capture_output=True, text=True, check=False,
        )
        assert completed.returncode == 0, completed.stderr
        loaded = [os.path.relpath(path, REPO_ROOT).replace(os.sep, "/") for path in completed.stdout.splitlines()]
        unbound = [path for path in loaded if not any(scope_matches_path(path, scope) for scope in spec.tool_file_scopes)]
        assert unbound == [], (check_id, unbound)
    # 声明范围与 git 路径共用 scope_matches_path：`./` 前缀只认仓库根，`*` 与 `**` 保留 fnmatch 的跨目录语义。
    assert scope_matches_path("pyproject.toml", "./*.toml")
    assert not scope_matches_path(".venv/x/pyproject.toml", "./*.toml")
    assert scope_matches_path("tools/host_tests/test_quality_gate_shared.py", "*.py")
    assert scope_matches_path("tools/quality_gate_shared.py", "tools/**/*.py")


def test_only_dead_code_scan_reruns_when_dependency_declarations_change():
    # 死代码扫描从已安装的库读外部继承链与 pytest 钩子名，依赖声明或 pytest 版本变了要重跑；其余棘轮只读仓库源码。
    specs = shared.build_quality_gate_check_specs(REPO_ROOT)
    ratchets = {spec.check_id: spec for spec in specs if spec.check_id in shared.BOUNDARY_RATCHET_CHECK_IDS}
    assert {check_id: spec.dependency_file_scopes for check_id, spec in ratchets.items()} == {
        shared.ENTRY_SQL_BOUNDARY: (),
        shared.ENTRY_PRIVATE_IMPORTS: (),
        shared.ENTRY_DEAD_PATH_LITERALS: (),
        shared.ENTRY_OVER_DEFENSE: (),
        shared.ENTRY_DEAD_CODE_ISLANDS: shared._COMMON_DEPENDENCY_SCOPES,
    }
    impact = explain_long_gate_impact(specs, ["requirements.txt"], repo_root=REPO_ROOT)
    affected = {entry["entry_id"]: entry["matched_categories"] for entry in impact["entries"] if entry["affected"]}
    assert affected[shared.ENTRY_DEAD_CODE_ISLANDS] == ["dependency"]
    assert not (set(ratchets) - {shared.ENTRY_DEAD_CODE_ISLANDS}) & set(affected)
    # 已安装 pytest 的版本与 pytest 类步骤一样由 pytest_version 记录；其余棘轮不读 pytest。
    assert {check_id for check_id, spec in ratchets.items() if "pytest_version" in spec.env_keys} == {
        shared.ENTRY_DEAD_CODE_ISLANDS,
    }
    dead_code_environment = fingerprint_environment(ratchets[shared.ENTRY_DEAD_CODE_ISLANDS].env_keys, repo_root=REPO_ROOT)
    assert dead_code_environment["values"]["pytest_version"] == pytest.__version__


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
