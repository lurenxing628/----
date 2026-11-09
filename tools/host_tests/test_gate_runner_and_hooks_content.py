"""Host-only source, receipt and hook-cache contracts; not a product gate run."""

import copy
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import venv
from pathlib import Path

import pytest

from scripts import run_daily_quality_gate as daily
from scripts import run_quality_gate as runner
from tools import fast_static_precheck as precheck
from tools import git_hook_cache as hooks
from tools import git_hook_checks as checks
from tools import quality_gate_shared as shared
from tools.long_gate_schema import SensitiveSourceError, content_equal


def test_runner_binds_dirty_source_and_resume_receipt_to_original_content(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(runner, "_run_git_bytes", lambda _args: b"actual diff\n")
    source = tmp_path / "input.bin"
    source.write_bytes(b"\x00same\xff")
    status = ["?? input.bin"]
    original = runner._dirty_worktree_content(status)
    source.write_bytes(b"\x00SAME\xff")
    assert not content_equal(original, runner._dirty_worktree_content(status))
    source.write_bytes(b"\x00same\xff")
    assert content_equal(original, runner._dirty_worktree_content(status))
    monkeypatch.setattr(runner, "REQUIRED_TEST_ARGS", ["input.bin"])
    monkeypatch.setattr(runner, "_guard_test_tracked", lambda _path: False)
    runner._assert_guard_tests_ready(require_tracked=False)
    with pytest.raises(runner.QualityGateError, match="untracked"):
        runner._assert_guard_tests_ready()
    source.unlink()
    with pytest.raises(runner.QualityGateError, match="missing"):
        runner._assert_guard_tests_ready(require_tracked=False)
    monkeypatch.setattr(runner, "REQUIRED_TEST_ARGS", ["tests/test_a.py", "tests/test_b.py"])
    collect = {"stdout": "tests/test_a.py::test_a\n", "stderr": "", "returncode": 0}
    with pytest.raises(runner.QualityGateError, match="actual collect|实际 collect"):
        runner._handle_collect_quality_gate_command("", collect)
    collect["stdout"] += "tests/test_b.py::test_b\n"
    proof = runner._handle_collect_quality_gate_command("", collect)
    assert proof["collection_proof"]["default_collect_nodeids"] == [
        "tests/test_a.py::test_a", "tests/test_b.py::test_b",
    ]

    command = {"display": "host contract", "args": ["python", "host_check.py"], "capture_output": True}
    monkeypatch.setenv("SECRET_KEY", "fixture-private-only")
    result = {"stdout": "fixture-private-only\r\nchecked\n", "stderr": "", "returncode": 0}
    entry = runner._write_command_receipt(command, run_id="saved-run", index=1, result=result)
    assert {key: result[key] for key in ("receipt_path", "run_id", "command_index")} == {
        "receipt_path": entry["path"], "run_id": "saved-run", "command_index": 1,
    }
    assert entry["content"]["stdout_content"] == "[REDACTED]\r\nchecked\n"
    assert "fixture-private-only" not in (tmp_path / result["stdout_log_path"]).read_text()
    accepted, error, log_texts = runner._load_resume_receipt_payload(entry, command, index=1, previous_run_id="saved-run")
    assert accepted is not None and not error
    assert log_texts == {"stdout": "[REDACTED]\r\nchecked\n", "stderr": ""}
    assert runner._load_resume_receipt_payload(entry, command, index=1, previous_run_id="other-run")[1]
    changed = copy.deepcopy(entry)
    changed["content"]["returncode"] = 1
    assert runner._load_resume_receipt_payload(changed, command, index=1, previous_run_id="saved-run")[1]
    stderr = tmp_path / result["stderr_log_path"]
    stderr.write_text("different output")
    assert runner._load_resume_receipt_payload(entry, command, index=1, previous_run_id="saved-run")[1]
    (tmp_path / result["stdout_log_path"]).write_text("tampered stdout")
    assert runner._result_from_receipt_logs(accepted, log_texts) == {
        "stdout": "[REDACTED]\r\nchecked\n",
        "stderr": "",
        "returncode": 0,
    }
    resumed_commands, resumed_receipts, resumed_parsed = [], [], {}
    runner._run_quality_gate_command_plan(
        [command],
        run_id="resumed-run",
        commands=resumed_commands,
        command_receipts=resumed_receipts,
        parsed_command_results=resumed_parsed,
        resume_decision=runner.ResumeDecision(
            True,
            "ok",
            skip_count=1,
            reusable_receipts=(entry,),
            reusable_receipt_payloads=(accepted,),
            reusable_log_texts=(log_texts,),
        ),
    )
    assert resumed_receipts[0]["content"]["stdout_content"] == "[REDACTED]\r\nchecked\n"
    assert resumed_receipts[0]["content"]["stderr_content"] == ""
    legacy = {"path": "evidence/QualityGate/receipts/original.json", "sha256": "historical"}
    assert runner._load_resume_receipt_payload(legacy, command, index=1, previous_run_id="saved-run")[1]


def test_hook_cache_and_daily_scope_compare_full_content_and_preserve_old_record(tmp_path, monkeypatch):
    monkeypatch.setattr(hooks, "REPO_ROOT", tmp_path)
    source = tmp_path / "config.bin"
    source.write_bytes(b"\x00first\xff")
    key = {"files": hooks._file_contents(["config.bin"]), "enabled": True}
    path = tmp_path / "cache.v2.json"
    hooks._write_pass_cache(path, key_payload=key, extra={})
    assert hooks._cache_matches(path, key)
    assert not hooks._cache_matches(path, {**key, "enabled": 1})
    source.write_bytes(b"\x00FIRST\xff")
    assert not hooks._cache_matches(path, {**key, "files": hooks._file_contents(["config.bin"])})
    old = tmp_path / "cache.json"
    historical = b'{"schema_version":1,"status":"passed","key_hash":"old","key_payload":{}}\n'
    old.write_bytes(historical)
    assert not hooks._cache_matches(old, {})
    assert old.read_bytes() == historical
    assert "key_hash" not in json.loads(path.read_text())

    scope = daily.DailyGateScope(
        daily.ChangedPathSet(["core/a.py"], True, "actual paths"),
        daily.ImpactPlan(["tests/test_a.py"], ["domain"], False, "actual targets"),
        daily.RuffPlan(["core/a.py"], False, "actual ruff targets"),
    )
    content = daily.daily_gate_scope_payload(scope)
    extra = hooks._daily_scope_cache_extra(content)
    assert extra["changed_paths"] == ["core/a.py"]
    assert extra["impact_pytest_target_paths"] == ["tests/test_a.py"]
    assert extra["ruff_target_paths"] == ["core/a.py"]
    assert not any("hash" in key for key in extra)

    ref_contexts = [{"local_ref": "refs/heads/main", "local_sha": "a" * 40, "remote_ref": "refs/heads/main", "remote_sha": "b" * 40}]
    base_key = hooks.daily_gate_cache_key(sys.executable, scope_payload=content, ref_contexts=ref_contexts)
    assert "pytest.ini" in base_key["watched_files"] and "pyproject.toml" in base_key["watched_files"]
    assert base_key["extra"]["pytest_plugins"]
    (tmp_path / "pytest.ini").write_text("[pytest]\naddopts = -q\n", encoding="utf-8")
    assert not content_equal(base_key, hooks.daily_gate_cache_key(sys.executable, scope_payload=content, ref_contexts=ref_contexts))
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k sample")
    env_key = hooks.daily_gate_cache_key(sys.executable, scope_payload=content, ref_contexts=ref_contexts)
    assert env_key["extra"]["pytest_env"]["PYTEST_ADDOPTS"] == "-k sample"

    for env_name, env_value, expected_probe_key, expected_probe_prefix in (
        ("WORKBENCH_NODE", "missing-node-runtime", "node_executable_realpath", "__missing_node__:missing-node-runtime"),
        ("NODE_OPTIONS", "--max-old-space-size=512", None, None),
        ("APS_TEST_POWERSHELL", "missing-pwsh-runtime", "powershell_executable_realpath", "__missing_powershell__:missing-pwsh-runtime"),
    ):
        before = hooks.daily_gate_cache_key(sys.executable, scope_payload=content, ref_contexts=ref_contexts)
        monkeypatch.setenv(env_name, env_value)
        after = hooks.daily_gate_cache_key(sys.executable, scope_payload=content, ref_contexts=ref_contexts)
        assert after["extra"]["pytest_env"][env_name] == env_value
        if expected_probe_key is not None:
            assert after["extra"]["pytest_env"][expected_probe_key] == expected_probe_prefix
        assert not content_equal(before, after)


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink venv probe regression")
def test_daily_gate_cache_key_tracks_symlink_venv_pytest_plugin_versions(tmp_path, monkeypatch):
    monkeypatch.setattr(hooks, "REPO_ROOT", tmp_path)
    venv_dir = tmp_path / "symlink-venv"
    venv.EnvBuilder(with_pip=False, symlinks=True).create(str(venv_dir))
    venv_python = venv_dir / "bin" / "python"
    site_packages = next(venv_dir.rglob("site-packages"))
    dist_info = site_packages / "audit_hook_plugin-1.0.dist-info"
    dist_info.mkdir(parents=True, exist_ok=True)
    (dist_info / "entry_points.txt").write_text("[pytest11]\naudit_hook = audit_hook_plugin\n", encoding="utf-8")
    metadata_file = dist_info / "METADATA"
    metadata_file.write_text(
        "Metadata-Version: 2.1\nName: audit-hook-plugin\nVersion: 1.0\n",
        encoding="utf-8",
    )

    scope = daily.DailyGateScope(
        daily.ChangedPathSet(["app.py"], True, "actual paths"),
        daily.ImpactPlan(["tools/host_tests/test_gate_runner_and_hooks_content.py"], ["domain"], False, "actual targets"),
        daily.RuffPlan(["app.py"], False, "actual ruff targets"),
    )
    content = daily.daily_gate_scope_payload(scope)
    local_ref = "/".join(("refs", "heads", "main"))
    ref_contexts = [{"local_ref": local_ref, "local_sha": "a" * 40, "remote_ref": local_ref, "remote_sha": "b" * 40}]

    hooks._PYTEST_PLUGIN_VERSIONS_CACHE.clear()
    key_v1 = hooks.daily_gate_cache_key(str(venv_python), scope_payload=content, ref_contexts=ref_contexts)
    assert key_v1["python"]["executable_abspath"] == os.path.abspath(str(venv_python))
    assert {"name": "audit-hook-plugin", "version": "1.0", "plugins": ["audit_hook"]} in key_v1["extra"]["pytest_plugins"]
    cache_file = tmp_path / "daily-cache.v2.json"
    hooks._write_pass_cache(cache_file, key_payload=key_v1, extra={})
    assert hooks._cache_matches(cache_file, key_v1)

    metadata_file.write_text(
        "Metadata-Version: 2.1\nName: audit-hook-plugin\nVersion: 2.0\n",
        encoding="utf-8",
    )
    hooks._PYTEST_PLUGIN_VERSIONS_CACHE.clear()
    key_v2 = hooks.daily_gate_cache_key(str(venv_python), scope_payload=content, ref_contexts=ref_contexts)
    assert {"name": "audit-hook-plugin", "version": "2.0", "plugins": ["audit_hook"]} in key_v2["extra"]["pytest_plugins"]
    assert not content_equal(key_v1, key_v2)
    assert not hooks._cache_matches(cache_file, key_v2)


def test_daily_gate_runs_boundary_scanners_after_ruff_only_when_ruff_runs():
    scanners = ["sql boundary check", "private imports check", "dead path literals check"]
    for plan in (
        daily.RuffPlan(["app.py"], False, "changed", daily.ALL_BOUNDARY_SCANNER_LABELS),
        daily.RuffPlan([], True, "full", daily.ALL_BOUNDARY_SCANNER_LABELS),
    ):
        commands = daily._commands([], plan)
        assert [label for label, _command in commands][2:5] == scanners
        assert all(command[-2:] == ["--fail-on-new", "--quiet-when-clean"] for _label, command in commands[2:5])
    skipped = daily._commands([], daily.RuffPlan([], False, "docs only"))
    assert not set(scanners) & {label for label, _command in skipped}


def test_daily_gate_routes_boundary_baselines_to_matching_scanners_without_full_pytest(monkeypatch):
    monkeypatch.setattr(daily, "_git_name_only", lambda _args: [])
    expected_map = {
        ".codestable/checkup/sql_boundary_baseline.json": (
            "sql boundary check",
            [sys.executable, "-m", "tools.scan_sql_boundary", "--rule", "all", "--fail-on-new", "--quiet-when-clean"],
        ),
        ".codestable/checkup/data_policy_baseline.json": (
            "sql boundary check",
            [sys.executable, "-m", "tools.scan_sql_boundary", "--rule", "all", "--fail-on-new", "--quiet-when-clean"],
        ),
        ".codestable/checkup/private_import_baseline.json": (
            "private imports check",
            [sys.executable, "-m", "tools.scan_private_imports", "--fail-on-new", "--quiet-when-clean"],
        ),
        ".codestable/checkup/dead_path_literal_baseline.json": (
            "dead path literals check",
            [sys.executable, "-m", "tools.scan_dead_path_literals", "--fail-on-new", "--quiet-when-clean"],
        ),
        ".codestable/checkup/import_cycles_production_baseline.json": (
            "import cycles check",
            [sys.executable, "-m", "tools.scan_import_cycles", "--fail-on-new-cycle", "--quiet-when-clean"],
        ),
        ".codestable/checkup/import_cycles_with_tests_baseline.json": (
            "import cycles with tests check",
            [
                sys.executable,
                "-m",
                "tools.scan_import_cycles",
                "--include-tests",
                "--fail-on-new-cycle",
                "--quiet-when-clean",
            ],
        ),
    }
    for baseline_path, (expected_scanner, expected_cmd) in expected_map.items():
        assert not daily._is_docs_only_path(baseline_path)
        scope = daily.build_daily_gate_scope(
            pre_push_changed_paths=[baseline_path],
            pre_push_scope_known=True,
        )
        assert scope.impact_plan.target_paths == []
        assert scope.impact_plan.selected_group_ids == []
        assert not scope.impact_plan.all_required_groups
        assert scope.impact_plan.reason == "boundary baseline changed (static check only)"
        assert scope.ruff_plan.target_paths == []
        assert not scope.ruff_plan.all_files
        assert scope.ruff_plan.boundary_scanners == (expected_scanner,)
        payload = daily.daily_gate_scope_payload(scope)
        assert payload["ruff"]["boundary_scanners"] == [expected_scanner]
        commands = daily._commands(scope.impact_plan.target_paths, scope.ruff_plan)
        assert [label for label, _cmd in commands] == [
            "block staged runtime artifacts",
            expected_scanner,
            "focused pytest",
        ]
        assert commands[1] == (expected_scanner, expected_cmd)

    # 多份基线 + 普通文档混合：去重保序触发对应边界扫描器，仍不升级全量 pytest
    combo_scope = daily.build_daily_gate_scope(
        pre_push_changed_paths=[
            ".codestable/checkup/import_cycles_with_tests_baseline.json",
            ".codestable/checkup/dead_path_literal_baseline.json",
            ".codestable/checkup/sql_boundary_baseline.json",
            ".codestable/checkup/data_policy_baseline.json",
            ".codestable/checkup/import_cycles_production_baseline.json",
            "README.md",
            ".codestable/attention.md",
        ],
        pre_push_scope_known=True,
    )
    assert combo_scope.impact_plan.target_paths == []
    assert not combo_scope.impact_plan.all_required_groups
    assert combo_scope.ruff_plan.boundary_scanners == (
        "sql boundary check",
        "dead path literals check",
        "import cycles check",
        "import cycles with tests check",
    )
    assert [label for label, _cmd in daily._commands(combo_scope.impact_plan.target_paths, combo_scope.ruff_plan)] == [
        "block staged runtime artifacts",
        "sql boundary check",
        "dead path literals check",
        "import cycles check",
        "import cycles with tests check",
        "focused pytest",
    ]

    # Python 文件 + 循环依赖基线混合改动：同时跑 3 个快速边界扫描器与命中的循环依赖扫描器
    py_and_cycle_scope = daily.build_daily_gate_scope(
        pre_push_changed_paths=[
            "core/models/machine.py",
            ".codestable/checkup/import_cycles_with_tests_baseline.json",
        ],
        pre_push_scope_known=True,
    )
    assert py_and_cycle_scope.ruff_plan.target_paths == ["core/models/machine.py"]
    assert py_and_cycle_scope.ruff_plan.boundary_scanners == (
        *daily.ALL_BOUNDARY_SCANNER_LABELS,
        "import cycles with tests check",
    )
    py_and_cycle_cmds = daily._commands(py_and_cycle_scope.impact_plan.target_paths, py_and_cycle_scope.ruff_plan)
    assert [label for label, _cmd in py_and_cycle_cmds][2:6] == [
        *daily.ALL_BOUNDARY_SCANNER_LABELS,
        "import cycles with tests check",
    ]

    # 普通文档单改仍走轻量通道
    doc_scope = daily.build_daily_gate_scope(
        pre_push_changed_paths=["README.md", ".codestable/attention.md"],
        pre_push_scope_known=True,
    )
    assert doc_scope.impact_plan.reason == "documentation-only changed paths"
    assert doc_scope.ruff_plan.boundary_scanners == ()
    assert [label for label, _cmd in daily._commands(doc_scope.impact_plan.target_paths, doc_scope.ruff_plan)] == [
        "block staged runtime artifacts",
        "focused pytest",
    ]


def test_git_hook_cli_help_imports_from_outside_repository(tmp_path):
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    script = Path(__file__).resolve().parents[1] / "git_hook_checks.py"
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "check-staged-artifacts" in result.stdout
    assert "run-quality-gate" in result.stdout


def _native_hook_fixture(tmp_path):
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "带 空格仓库"
    root.mkdir()
    environment = checks._quality_gate_env()
    for key in list(environment):
        if key.startswith("PRE_COMMIT_") or key == "APS_PRE_PUSH_INPUT_FILE":
            environment.pop(key)
    environment["PATH"] = str(source_root / ".venv" / "bin") + os.pathsep + environment.get("PATH", "")
    environment["PRE_COMMIT_HOME"] = str(tmp_path / "pre-commit-cache")
    environment["APS_HOOK_TEST_LOG"] = str(tmp_path / "target-runs.jsonl")
    environment["APS_HOOK_TEST_STDIN"] = str(tmp_path / "legacy-stdin")
    environment["APS_HOOK_TEST_INPUT_PATH"] = str(tmp_path / "input-file-path")
    for relative in (
        "tools/__init__.py", "tools/git_hook_checks.py", "tools/git_hook_cache.py",
        "tools/git_hook_blocked_paths.py", "tools/long_gate_schema.py", "tools/long_gate_paths.py",
        "tools/long_gate_fingerprint.py", "tools/quality_gate_shared.py",
        "tools/install_git_hooks.py", "tools/native_pre_push.py", "tools/test_registry.py",
        "tools/test_registry_data.py", "scripts/__init__.py",
    ):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_root / relative, destination)
    (root / ".venv").symlink_to(source_root / ".venv", target_is_directory=True)
    (root / ".gitignore").write_text(".venv\n__pycache__/\n", encoding="utf-8")
    (root / ".pre-commit-config.yaml").write_text(
        "default_install_hook_types: [pre-commit, commit-msg, pre-push]\n"
        "repos:\n  - repo: local\n    hooks:\n"
        "      - id: aps-quality-gate\n"
        "        name: APS fixture daily gate\n"
        "        entry: python tools/git_hook_checks.py run-quality-gate\n"
        "        language: system\n        pass_filenames: false\n"
        "        always_run: true\n        verbose: true\n        stages: [pre-push]\n",
        encoding="utf-8",
    )
    source = (source_root / "scripts/run_daily_quality_gate.py").read_text(encoding="utf-8")
    fixture_main = '''
FIXTURE_MARKER = "base"
FIXTURE_EXIT = 0
if __name__ == "__main__":
    args = _parse_args(sys.argv[1:])
    scope = build_daily_gate_scope(
        pre_push_changed_paths=args.pre_push_changed_path,
        pre_push_scope_reason=args.pre_push_scope_reason,
        pre_push_scope_known=args.pre_push_scope_known,
    )
    standard_check = subprocess.call([sys.executable, "tools/git_hook_checks.py", "check-staged-artifacts"])
    row = {"marker": FIXTURE_MARKER, "cwd": os.getcwd(), "python": sys.executable,
           "scope": daily_gate_scope_payload(scope), "standard_check": standard_check,
           "target_has_venv": os.path.exists(".venv")}
    with open(os.environ["APS_HOOK_TEST_LOG"], "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\\n")
    print("fixture target: " + FIXTURE_MARKER, flush=True)
    raise SystemExit(FIXTURE_EXIT or standard_check)
'''
    (root / "scripts/run_daily_quality_gate.py").write_text(
        source.rsplit('if __name__ == "__main__":', 1)[0] + fixture_main, encoding="utf-8",
    )

    def git(*args):
        result = subprocess.run(
            ["git", *args], cwd=root, env=environment, capture_output=True, text=True, encoding="utf-8",
        )
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    git("init")
    git("config", "user.email", "fixture@example.invalid")
    git("config", "user.name", "Hook Fixture")
    git("add", ".")
    git("commit", "-m", "Create native hook fixture")
    return root, environment, git


@pytest.mark.skipif(os.name == "nt", reason="Windows hook execution deferred_by_user")
def test_native_pre_push_checks_committed_targets_and_preserves_complete_chain(tmp_path):
    root, environment, git = _native_hook_fixture(tmp_path)
    base = git("rev-parse", "HEAD")
    script = root / "scripts/run_daily_quality_gate.py"
    original = script.read_text(encoding="utf-8")
    script.write_text(original.replace('FIXTURE_MARKER = "base"', 'FIXTURE_MARKER = "pass"'), encoding="utf-8")
    git("add", str(script.relative_to(root)))
    git("commit", "-m", "Passing target fixture")
    passed = git("rev-parse", "HEAD")
    git("branch", "good")
    git("checkout", "--detach", base)
    script.write_text(
        original.replace('FIXTURE_MARKER = "base"', 'FIXTURE_MARKER = "fail"').replace(
            "FIXTURE_EXIT = 0", "FIXTURE_EXIT = 9",
        ), encoding="utf-8",
    )
    git("add", str(script.relative_to(root)))
    git("commit", "-m", "Failing target fixture")
    failed = git("rev-parse", "HEAD")
    git("branch", "bad")
    git("checkout", "--detach", base)

    installer = [str(root / ".venv/bin/python"), "tools/install_git_hooks.py"]
    for _ in range(2):
        install = subprocess.run(installer, cwd=root, env=environment, capture_output=True, text=True)
        assert install.returncode == 0, install.stderr
    hooks_dir = root / ".git/hooks"
    native_hook = hooks_dir / "pre-push"
    assert "APS native pre-push input wrapper" in native_hook.read_text()
    assert "File generated by pre-commit" in (hooks_dir / "pre-push.pre-commit").read_text()
    assert not (hooks_dir / "pre-push.legacy").exists()
    assert "File generated by pre-commit" in (hooks_dir / "pre-commit").read_text()
    assert "File generated by pre-commit" in (hooks_dir / "commit-msg").read_text()

    legacy_source = hooks_dir / "capture_legacy.py"
    legacy_source.write_text(
        "import os, sys\nfrom pathlib import Path\n"
        'Path(os.environ["APS_HOOK_TEST_STDIN"]).write_bytes(sys.stdin.buffer.read())\n'
        'Path(os.environ["APS_HOOK_TEST_INPUT_PATH"]).write_text(os.environ["APS_PRE_PUSH_INPUT_FILE"])\n'
        'raise SystemExit(int(os.environ.get("APS_HOOK_LEGACY_EXIT", "0")))\n', encoding="utf-8",
    )
    legacy_hook = hooks_dir / "pre-push.legacy"
    legacy_hook.write_text(
        f"#!/bin/sh\nexec {shlex.quote(str(root / '.venv/bin/python'))} {shlex.quote(str(legacy_source))}\n",
        encoding="utf-8",
    )
    legacy_hook.chmod(0o755)

    def push(raw, *, env=None):
        result = subprocess.run(
            [str(native_hook), "origin", "fixture-remote"], cwd=root, env=env or environment,
            input=raw.encode(), capture_output=True,
        )
        assert Path(environment["APS_HOOK_TEST_STDIN"]).read_bytes() == raw.encode()
        assert not Path(Path(environment["APS_HOOK_TEST_INPUT_PATH"]).read_text()).exists()
        assert git("worktree", "list", "--porcelain").count("worktree ") == 1
        return result

    good_line = f"refs/heads/good {passed} refs/heads/review {base}\n"
    good_result = push(good_line)
    assert good_result.returncode == 0, good_result.stdout.decode() + good_result.stderr.decode()
    rows = [json.loads(line) for line in Path(environment["APS_HOOK_TEST_LOG"]).read_text().splitlines()]
    assert rows[-1]["marker"] == "pass"
    assert rows[-1]["cwd"] != str(root)
    assert rows[-1]["scope"]["changed_paths"] == ["scripts/run_daily_quality_gate.py"]
    assert rows[-1]["standard_check"] == 0 and not rows[-1]["target_has_venv"]
    cache = root / ".git/aps-hook-cache" / hooks.PRE_PUSH_DAILY_CACHE_NAME
    passed_cache = cache.read_bytes()
    assert json.loads(passed_cache)["key_payload"]["extra"]["ref_contexts"][0]["local_sha"] == passed
    assert push(good_line).returncode == 0
    assert len(Path(environment["APS_HOOK_TEST_LOG"]).read_text().splitlines()) == len(rows)

    # 已验证目标不随当前 checkout 的无关改动或提交失效。
    readme = root / "README.md"
    readme.write_text("Unrelated checkout notes\n", encoding="utf-8")
    dirty_push = push(good_line)
    assert dirty_push.returncode == 0
    before_key, after_key = json.loads(passed_cache)["key_payload"], json.loads(cache.read_bytes())["key_payload"]
    assert len(Path(environment["APS_HOOK_TEST_LOG"]).read_text().splitlines()) == len(rows), (
        dirty_push.stdout.decode() + dirty_push.stderr.decode(),
        [key for key in before_key if before_key[key] != after_key[key]],
        {name: (version, after_key["tool_versions"].get(name))
         for name, version in before_key["tool_versions"].items()
         if version != after_key["tool_versions"].get(name)},
    )
    git("add", "README.md")
    git("commit", "-m", "Unrelated checkout documentation")
    committed_push = push(good_line)
    assert committed_push.returncode == 0
    after_key = json.loads(cache.read_bytes())["key_payload"]
    assert len(Path(environment["APS_HOOK_TEST_LOG"]).read_text().splitlines()) == len(rows), (
        committed_push.stdout.decode() + committed_push.stderr.decode(),
        [key for key in before_key if before_key[key] != after_key[key]],
        {name: (version, after_key["tool_versions"].get(name))
         for name, version in before_key["tool_versions"].items()
         if version != after_key["tool_versions"].get(name)},
    )
    git("checkout", "--detach", base)

    # 相同 ref 和范围只改 local_sha，旧 aggregate pass 必须失效。
    failure = push(good_line.replace(passed, failed))
    assert failure.returncode != 0
    assert b"fixture target: fail" in failure.stdout
    assert b"refs/heads/review" in failure.stdout and b"exit=9" in failure.stdout
    assert cache.read_bytes() == passed_cache
    multi = push(good_line + f"refs/heads/bad {failed} refs/heads/second {base}\n")
    assert multi.returncode != 0 and b"refs/heads/second" in multi.stdout

    # 同一提交的不同 ref 只执行一次，再覆盖首次分支与删除原始输入。
    before = len(Path(environment["APS_HOOK_TEST_LOG"]).read_text().splitlines())
    assert push(good_line + f"refs/heads/good {passed} refs/heads/alias {base}\n").returncode == 0
    assert len(Path(environment["APS_HOOK_TEST_LOG"]).read_text().splitlines()) == before + 1
    assert push(f"refs/heads/good {passed} refs/heads/new {checks.ZERO_SHA}\n").returncode == 0
    # HEAD 也从已提交 worktree 执行，保留并隔离当前 dirty gate 文件。
    dirty = original.replace('FIXTURE_MARKER = "base"', 'FIXTURE_MARKER = "dirty"').replace(
        "FIXTURE_EXIT = 0", "FIXTURE_EXIT = 21",
    )
    script.write_text(dirty, encoding="utf-8")
    assert push(f"HEAD {base} refs/heads/current {base}\n").returncode == 0
    head_row = json.loads(Path(environment["APS_HOOK_TEST_LOG"]).read_text().splitlines()[-1])
    assert head_row["marker"] == "base" and head_row["scope"]["changed_paths"] == []
    assert script.read_text(encoding="utf-8") == dirty
    before = len(Path(environment["APS_HOOK_TEST_LOG"]).read_text().splitlines())
    assert push(f"HEAD {base} refs/heads/current {base}\n").returncode == 0
    assert len(Path(environment["APS_HOOK_TEST_LOG"]).read_text().splitlines()) == before
    assert script.read_text(encoding="utf-8") == dirty
    script.write_text(original, encoding="utf-8")
    before = len(Path(environment["APS_HOOK_TEST_LOG"]).read_text().splitlines())
    deletion = f"(delete) {checks.ZERO_SHA} refs/heads/obsolete {base}\n"
    assert push(deletion).returncode == 0
    assert len(Path(environment["APS_HOOK_TEST_LOG"]).read_text().splitlines()) == before
    assert push(deletion, env={**environment, "APS_HOOK_LEGACY_EXIT": "7"}).returncode == 7
    assert git("rev-parse", "HEAD") == base and git("status", "--short") == ""


@pytest.mark.skipif(os.name == "nt", reason="Windows hook execution deferred_by_user")
def test_project_hook_installation_preserves_user_hook_conflict(tmp_path):
    root, environment, git = _native_hook_fixture(tmp_path)
    hook = root / ".git/hooks/pre-push"
    user_script = b"#!/bin/sh\necho user hook\n"
    hook.write_bytes(user_script)
    hook.chmod(0o755)
    result = subprocess.run(
        [str(root / ".venv/bin/python"), "tools/install_git_hooks.py"],
        cwd=root, env=environment, capture_output=True, text=True,
    )
    assert result.returncode != 0 and "安装冲突" in result.stderr
    assert hook.read_bytes() == user_script
    assert not (hook.parent / "pre-commit").exists()
    assert not (hook.parent / "pre-push.pre-commit").exists()
    assert git("status", "--short") == ""


def test_pre_push_input_requires_original_remote_context_and_keeps_manual_entry(tmp_path, monkeypatch):
    for key in list(os.environ):
        if key.startswith("PRE_COMMIT_") or key == "APS_PRE_PUSH_INPUT_FILE":
            monkeypatch.delenv(key)
    local_sha = "a" * 40
    raw = f"refs/heads/new {local_sha} refs/heads/new {checks.ZERO_SHA}\n"
    raw += f"(delete) {checks.ZERO_SHA} refs/heads/old {local_sha}\n"
    assert checks._pre_push_input_for_hook(io.StringIO(raw)).refs[0].local_sha == local_sha
    assert not checks._pre_push_input_for_hook(io.StringIO("")).saw_push_input
    monkeypatch.setenv("PRE_COMMIT_REMOTE_NAME", "origin")
    with pytest.raises(RuntimeError, match="tools/install_git_hooks.py"):
        checks._pre_push_input_for_hook(io.StringIO(""))
    source = tmp_path / "push-input"
    source.write_text(raw)
    monkeypatch.setenv("APS_PRE_PUSH_INPUT_FILE", str(source))
    parsed = checks._pre_push_input_for_hook(io.StringIO(""))
    assert parsed.saw_push_input and len(parsed.refs) == 1
    assert parsed.refs[0].local_sha == local_sha


def test_optional_caches_degrade_when_secret_key_present_while_mandatory_proofs_reject(tmp_path, monkeypatch):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    monkeypatch.setattr(runner, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(hooks, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(checks, "REPO_ROOT", tmp_path)
    secret = "secret-in-memory-do-not-persist"
    monkeypatch.setenv("SECRET_KEY", secret)
    monkeypatch.setenv("TOKENIZERS_PARALLELISM", "false")

    # Mandatory proofs must still reject sources or diffs containing SECRET_KEY.
    leaked_src = tmp_path / "pyproject.toml"
    leaked_src.write_text(f'token = "false"\nsecret = "{secret}"\n', encoding="utf-8")
    monkeypatch.setattr(shared, "QUALITY_GATE_SOURCE_FILES", ["pyproject.toml"])
    with pytest.raises(shared.QualityGateError, match="SECRET_KEY") as source_exc:
        shared.build_quality_gate_source_proof(tmp_path)
    assert secret not in str(source_exc.value)
    monkeypatch.setattr(runner, "_run_git_bytes", lambda _args: b"")
    with pytest.raises(runner.QualityGateError, match="SECRET_KEY") as dirty_file_exc:
        runner._dirty_worktree_content(["?? pyproject.toml"])
    assert secret not in str(dirty_file_exc.value)
    monkeypatch.setattr(runner, "_run_git_bytes", lambda _args: f"+{secret}\n".encode())
    with pytest.raises(runner.QualityGateError, match="敏感环境值"):
        runner._dirty_worktree_content([" M pyproject.toml"])

    # Optional long-gate cache boundaries (metadata / refresh / execution / write) degrade to cache_unavailable.
    runner_script = tmp_path / "scripts" / "run_quality_gate.py"
    runner_script.parent.mkdir(parents=True, exist_ok=True)
    runner_script.write_text(f"# {secret}\n", encoding="utf-8")
    plan = [
        {
            "display": "python tools/check_full_test_debt.py --sharded --shard-count 3",
            "args": ["python", "tools/check_full_test_debt.py", "--sharded", "--shard-count", "3"],
            "capture_output": True,
            "output_policy": "exact",
        }
    ]
    summary_entries, runtime_entries = runner._prepare_long_gate_cache_decisions(
        plan, cache_enabled=True, cache_dir="evidence/QualityGate/long_gate"
    )
    assert summary_entries[0]["cache_unavailable"] is True
    assert summary_entries[0]["cache_status"] == "cache_unavailable"
    # Cache is unavailable, but the command is still executed for real.
    assert summary_entries[0]["decision"] == "run"
    assert summary_entries[0]["reason"].startswith("cache metadata unavailable;")
    assert summary_entries[0]["fingerprint_error"]["failure_kind"] == "cache_metadata_unavailable"
    rt_entry = runtime_entries[plan[0]["display"]]

    # Refresh and write boundaries also catch sensitive sources and mark cache_unavailable without crashing.
    rt_entry["decision"] = {"decision": "run", "reason": "no previous success cache", "cache_unavailable": False}
    runner._refresh_full_test_debt_reuse_decision(rt_entry, cache_dir="evidence/QualityGate/long_gate")
    assert rt_entry["decision"]["cache_unavailable"] is True
    assert rt_entry["decision"]["decision"] == "run"
    assert rt_entry["decision"]["reason"].startswith("strict fingerprint failed;")
    assert rt_entry["decision"]["fingerprint_error"]["failure_kind"] == "source_content_unavailable"
    assert rt_entry["entry"]["cache_status"] == "cache_unavailable"

    valid_fp = {
        "schema_version": 2,
        "components": {"command": shared.normalize_quality_gate_command(rt_entry["entry"])},
    }
    rt_entry["decision"] = {"decision": "run", "reason": "no previous success cache", "cache_unavailable": False}
    rt_entry["entry"]["cache_status"] = "reusable"
    pending = [
        {
            "entry": rt_entry["entry"],
            "fingerprint": valid_fp,
            "command_result": {"returncode": 0, "stdout": "ok\n", "stderr": ""},
            "output_files": [str(leaked_src)],
            "runtime_entry": rt_entry,
        }
    ]
    prepared_writes = runner._prepare_pending_long_gate_successes(pending, cache_dir="evidence/QualityGate/long_gate")
    assert prepared_writes == []
    assert rt_entry["decision"]["cache_unavailable"] is True
    assert rt_entry["decision"]["reason"].startswith("cache write failed;")
    assert rt_entry["decision"]["fingerprint_error"]["failure_kind"] == "cache_write_unavailable"
    assert rt_entry["entry"]["cache_status"] == "cache_unavailable"
    assert rt_entry["summary_entry"]["cache_status"] == "cache_unavailable"
    assert rt_entry["summary_entry"]["cache_unavailable"] is True
    assert "SECRET_KEY" in rt_entry["decision"]["fingerprint_error"]["message"]
    assert not (tmp_path / "evidence/QualityGate/long_gate/logs").exists()
    assert not (tmp_path / "evidence/QualityGate/long_gate/results").exists()

    rt_entry["decision"] = {"decision": "run", "reason": "no previous success cache", "cache_unavailable": False}
    rt_entry["entry"]["cache_status"] = "reusable"
    rt_entry["fingerprint"] = valid_fp
    runner._maybe_write_full_test_debt_failure_cache(
        rt_entry,
        result={"returncode": 1, "stdout": "", "stderr": "fail", "execution_mode": "executed"},
        receipt_path="evidence/QualityGate/v4/receipts/01.json",
        cache_dir="evidence/QualityGate/long_gate",
        long_gate_cache_write_success=True,
    )
    assert rt_entry["decision"]["cache_unavailable"] is True
    assert rt_entry["entry"]["cache_status"] == "cache_unavailable"
    assert "SECRET_KEY" in rt_entry["decision"]["fingerprint_error"]["message"]
    assert not (tmp_path / "evidence/QualityGate/long_gate/results").exists()

    # Hook cache: SECRET_KEY disables pre-push daily cache; staged ruff executes without writing cache.
    scope = daily.DailyGateScope(
        daily.ChangedPathSet(["core/errors.py"], True, "actual paths"),
        daily.ImpactPlan(["tests/conftest.py"], ["domain"], False, "actual targets"),
        daily.RuffPlan(["core/errors.py"], False, "actual ruff targets"),
    )
    scope_payload = daily.daily_gate_scope_payload(scope)
    ref_contexts = [{"local_ref": "refs/heads/main", "local_sha": "a" * 40, "remote_ref": "refs/heads/main", "remote_sha": "b" * 40}]
    for raw_secret in (secret, f"  {secret}  "):
        monkeypatch.setenv("SECRET_KEY", raw_secret)
        with pytest.raises(hooks.HookCacheError, match="SECRET_KEY"):
            hooks.daily_gate_cache_key(sys.executable, scope_payload=scope_payload, ref_contexts=ref_contexts)
    monkeypatch.setenv("SECRET_KEY", "   ")
    assert hooks.daily_gate_cache_key(sys.executable, scope_payload=scope_payload, ref_contexts=ref_contexts)
    monkeypatch.setenv("SECRET_KEY", secret)

    monkeypatch.setattr(hooks, "staged_python_paths", lambda: ("app.py",))
    monkeypatch.setattr(hooks, "staged_tree_hash", lambda: "tree123")
    monkeypatch.setattr(hooks, "cache_path", lambda name: tmp_path / name)
    monkeypatch.setattr(hooks, "_export_index_to_temp", lambda prefix: (prefix / "app.py").write_text("x = 1\n", encoding="utf-8"))
    ruff_calls = []
    monkeypatch.setattr(
        hooks.subprocess,
        "call",
        lambda cmd, **kw: (ruff_calls.append((cmd, kw["cwd"])) or 0),
    )
    assert hooks.run_staged_ruff(sys.executable) == 0
    assert len(ruff_calls) == 1
    assert not (tmp_path / hooks.STAGED_RUFF_CACHE_NAME).exists()


def test_cache_boundaries_only_degrade_sensitive_sources_and_raise_other_value_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(hooks, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    defect = ValueError("internal cache defect")

    def raise_defect(*_args, **_kwargs):
        raise defect

    # Long-gate metadata: a non-sensitive ValueError is an internal defect, not "cache unavailable".
    plan = [
        {
            "display": "python tools/check_full_test_debt.py --sharded --shard-count 3",
            "args": ["python", "tools/check_full_test_debt.py", "--sharded", "--shard-count", "3"],
            "capture_output": True,
            "output_policy": "exact",
        }
    ]
    monkeypatch.setattr(runner, "long_gate_cache_metadata", raise_defect)
    with pytest.raises(ValueError, match="internal cache defect"):
        runner._prepare_long_gate_cache_decisions(plan, cache_enabled=True, cache_dir="evidence/QualityGate/long_gate")
    monkeypatch.setattr(runner, "fingerprint_entry", raise_defect)
    with pytest.raises(ValueError, match="internal cache defect"):
        runner._strict_long_gate_fingerprint({"entry_id": "full_test_debt"})

    # Long-gate writes: command content mismatch must surface instead of being recorded as cache unavailable.
    entry = {**plan[0], "entry_id": "full_test_debt"}
    mismatched_fp = {"schema_version": 2, "components": {"command": {"display": "other"}}}
    runtime_entry = {
        "entry": dict(entry),
        "decision": {"decision": "run", "reason": "no previous success cache", "cache_unavailable": False},
        "summary_entry": {},
        "fingerprint": mismatched_fp,
    }
    with pytest.raises(ValueError, match="matching command content"):
        runner._prepare_pending_long_gate_successes(
            [
                {
                    "entry": entry,
                    "fingerprint": mismatched_fp,
                    "command_result": {"returncode": 0, "stdout": "ok\n", "stderr": ""},
                    "output_files": [],
                    "runtime_entry": runtime_entry,
                }
            ],
            cache_dir="evidence/QualityGate/long_gate",
        )
    with pytest.raises(ValueError, match="matching command content"):
        runner._maybe_write_full_test_debt_failure_cache(
            runtime_entry,
            result={"returncode": 1, "stdout": "", "stderr": "fail", "execution_mode": "executed"},
            receipt_path="evidence/QualityGate/v4/receipts/01.json",
            cache_dir="evidence/QualityGate/long_gate",
            long_gate_cache_write_success=True,
        )
    assert runtime_entry["decision"]["cache_unavailable"] is False

    # Hook caches: only SensitiveSourceError becomes HookCacheError; other ValueErrors propagate.
    watched = tmp_path / "pyproject.toml"
    watched.write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(hooks, "read_file_content", raise_defect)
    with pytest.raises(ValueError, match="internal cache defect"):
        hooks._file_contents(["pyproject.toml"])

    def raise_sensitive(_path):
        raise SensitiveSourceError("source contains sensitive environment value for SECRET_KEY")

    monkeypatch.setattr(hooks, "read_file_content", raise_sensitive)
    with pytest.raises(hooks.HookCacheError, match="SECRET_KEY"):
        hooks._file_contents(["pyproject.toml"])
    monkeypatch.setattr(hooks, "staged_python_paths", lambda: ("app.py",))
    monkeypatch.setattr(hooks, "staged_tree_hash", lambda: "tree123")
    monkeypatch.setattr(hooks, "_cache_key_payload", raise_defect)
    with pytest.raises(ValueError, match="internal cache defect"):
        hooks.run_staged_ruff(sys.executable)

    # The daily env key set is classified once at import; an unclassified registry key fails loudly.
    monkeypatch.setattr(hooks, "REQUIRED_REGRESSION_GROUPS", [{"env_keys": ("UNCLASSIFIED_KEY",)}])
    with pytest.raises(RuntimeError, match="UNCLASSIFIED_KEY"):
        hooks._daily_gate_env_keys()


def test_git_nul_path_decoding_classifies_non_ascii_docs_and_code_with_quotepath_true(tmp_path, monkeypatch):
    assert hooks.decode_nul_paths(
        b"\xe5\xbc\x80\xe5\x8f\x91\xe6\x96\x87\xe6\xa1\xa3/\xe5\xbc\x80\xe5\x8f\x91\xe6\x96\x87\xe6\xa1\xa3.md\0core/errors.py\0"
    ) == ["开发文档/开发文档.md", "core/errors.py"]
    assert hooks.decode_nul_paths(b"core/line\rname.py\0tools/back\\slash.py\0") == [
        "core/line\rname.py",
        "tools/back\\slash.py",
    ]

    repo = tmp_path / "quotepath-repo"
    repo.mkdir()
    env = checks._quality_gate_env()

    def git(*args):
        res = subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True, text=True, encoding="utf-8")
        assert res.returncode == 0, res.stderr
        return res.stdout.strip()

    git("init")
    git("config", "core.quotepath", "true")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "QuotePath Tester")

    (repo / "README.md").write_text("base\n", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-m", "Initial commit")
    base_sha = git("rev-parse", "HEAD")
    git("branch", "base", base_sha)
    git("branch", "--set-upstream-to=base")

    doc_file = repo / "开发文档" / "开发文档.md"
    doc_file.parent.mkdir(parents=True, exist_ok=True)
    doc_file.write_text("# 中文说明\n", encoding="utf-8")
    git("add", "开发文档/开发文档.md")

    monkeypatch.setattr(daily, "REPO_ROOT", str(repo))
    monkeypatch.setattr(runner, "REPO_ROOT", str(repo))
    monkeypatch.setattr(hooks, "REPO_ROOT", repo)
    monkeypatch.setattr(checks, "REPO_ROOT", repo)

    assert hooks.staged_paths() == ["开发文档/开发文档.md"]
    assert checks._staged_paths() == ["开发文档/开发文档.md"]
    assert runner._current_impact_paths() == ["开发文档/开发文档.md"]
    doc_impact = runner.explain_long_gate_impact(
        shared.build_quality_gate_command_plan(),
        runner._current_impact_paths(),
        repo_root=str(repo),
    )
    assert doc_impact["changed_paths"] == ["开发文档/开发文档.md"]
    doc_entries = {row["entry_id"]: row for row in doc_impact["entries"]}
    assert doc_entries["debt_ledger_sync"]["affected"] is True
    assert doc_entries["ruff_check_full"]["affected"] is False

    staged_scope = daily.build_daily_gate_scope()
    assert staged_scope.changed.paths == ["开发文档/开发文档.md"]
    assert staged_scope.impact_plan.target_paths == []
    assert staged_scope.impact_plan.reason == "documentation-only changed paths"
    assert staged_scope.ruff_plan.target_paths == []
    assert not staged_scope.ruff_plan.all_files

    git("commit", "-m", "Add Chinese doc")
    doc_sha = git("rev-parse", "HEAD")
    pre_push_doc_scope = daily.build_daily_gate_scope(
        pre_push_from_ref=base_sha,
        pre_push_to_ref=doc_sha,
        pre_push_remote_name="origin",
    )
    assert pre_push_doc_scope.changed.paths == ["开发文档/开发文档.md"]
    assert pre_push_doc_scope.impact_plan.target_paths == []
    assert pre_push_doc_scope.impact_plan.reason == "documentation-only changed paths"

    code_file = repo / "core" / "algorithms" / "greedy" / "scheduler.py"
    code_file.parent.mkdir(parents=True, exist_ok=True)
    code_file.write_text("VALUE = 1\n", encoding="utf-8")
    git("add", "core/algorithms/greedy/scheduler.py")
    assert precheck.collect_changed_python_files(str(repo)).paths == ("core/algorithms/greedy/scheduler.py",)
    assert runner._current_impact_paths() == ["core/algorithms/greedy/scheduler.py"]
    code_impact = runner.explain_long_gate_impact(
        shared.build_quality_gate_command_plan(),
        runner._current_impact_paths(),
        repo_root=str(repo),
    )
    assert code_impact["changed_paths"] == ["core/algorithms/greedy/scheduler.py"]
    code_entries = {row["entry_id"]: row for row in code_impact["entries"]}
    assert code_entries["ruff_check_full"]["affected"] is True
    assert code_entries["pyright_gate_full"]["affected"] is True
    git("commit", "-m", "Modify scheduler code")
    code_sha = git("rev-parse", "HEAD")

    pre_push_code_scope = daily.build_daily_gate_scope(
        pre_push_from_ref=doc_sha,
        pre_push_to_ref=code_sha,
        pre_push_remote_name="origin",
    )
    assert pre_push_code_scope.changed.paths == ["core/algorithms/greedy/scheduler.py"]
    assert pre_push_code_scope.impact_plan.selected_group_ids == ["scheduler"]
    assert not pre_push_code_scope.impact_plan.all_required_groups
    assert pre_push_code_scope.ruff_plan.target_paths == ["core/algorithms/greedy/scheduler.py"]
    assert not pre_push_code_scope.ruff_plan.all_files

    if os.name != "nt":
        special_rel = "core/with\\slash\rand_cr.py"
        special_file = repo / "core" / "with\\slash\rand_cr.py"
        special_file.write_text("SPECIAL = 1\n", encoding="utf-8")
        git("add", "--", special_rel)
        assert hooks.staged_paths() == [special_rel]
        assert checks._staged_paths() == [special_rel]
        assert runner._current_impact_paths() == [special_rel]
        special_impact = runner.explain_long_gate_impact(
            shared.build_quality_gate_command_plan(),
            runner._current_impact_paths(),
            repo_root=str(repo),
        )
        assert special_impact["changed_paths"] == [special_rel]
        assert {row["entry_id"]: row for row in special_impact["entries"]}["ruff_check_full"]["affected"] is True


def test_cli_impact_paths_normalize_only_at_argument_boundary(capsys):
    canonical = "tools/long_gate_cache.py"
    args = runner._parse_args([
        "--long-gate-impact-explain",
        "--long-gate-impact-path", "./tools/long_gate_cache.py",
        "--long-gate-impact-path", "tools\\long_gate_cache.py",
        "--long-gate-impact-path", " /tools/long_gate_cache.py/ ",
    ])
    assert args.long_gate_impact_path == [canonical, canonical, canonical]
    plan = shared.build_quality_gate_command_plan()

    def affected(paths):
        impact = runner.explain_long_gate_impact(plan, paths, repo_root=runner.REPO_ROOT)
        return sorted(row["entry_id"] for row in impact["entries"] if row["affected"])

    expected = affected([canonical])
    assert expected
    assert affected(runner._dedupe_impact_paths(args.long_gate_impact_path)) == expected
    assert affected(["tools\\long_gate_cache.py"]) != expected
    with pytest.raises(SystemExit):
        runner._parse_args(["--long-gate-impact-explain", "--long-gate-impact-path", "./"])
    assert "not a repository-relative path" in capsys.readouterr().err


def test_dirty_sensitive_worktree_cli_exits_2_and_failed_cleanup_finalizes_manifest(tmp_path, monkeypatch):
    source_root = Path(__file__).resolve().parents[2]
    repo = tmp_path / "gate_repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copyfile(source_root / "scripts" / "run_quality_gate.py", repo / "scripts" / "run_quality_gate.py")
    (repo / ".gitignore").write_text("evidence/\n__pycache__/\n", encoding="utf-8")

    def git(*args):
        completed = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
        assert completed.returncode == 0, completed.stderr

    git("init")
    git("config", "user.email", "gate@example.invalid")
    git("config", "user.name", "Gate Fixture")
    git("add", ".")
    git("commit", "-m", "init fixture repo")

    secret = "cli-dirty-secret-do-not-persist"
    leaked_file = repo / "untracked_secret.env"
    leaked_file.write_text(f"SECRET={secret}\n", encoding="utf-8")
    cli_env = {
        **os.environ,
        "PYTHONPATH": str(source_root),
        "SECRET_KEY": secret,
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    manifest_file = repo / shared.QUALITY_GATE_MANIFEST_REL
    for mode_flag in ("--require-clean-worktree", "--allow-dirty-worktree"):
        completed = subprocess.run(
            [sys.executable, str(repo / "scripts" / "run_quality_gate.py"), mode_flag, "--no-long-gate-cache"],
            cwd=repo,
            env=cli_env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 2, completed.stderr
        assert "脏工作区包含敏感来源内容" in completed.stderr
        assert "SECRET_KEY" in completed.stderr
        assert "Traceback" not in completed.stderr
        assert secret not in (completed.stdout + completed.stderr)
        assert not manifest_file.exists()

    leaked_file.unlink()
    monkeypatch.setenv("SECRET_KEY", secret)
    monkeypatch.setattr(runner, "REPO_ROOT", str(repo))
    monkeypatch.setattr(runner, "REQUIRED_TEST_ARGS", [])
    monkeypatch.setattr(shared, "QUALITY_GATE_SOURCE_FILES", ())
    failing_plan = [
        {
            "display": "python step-leaks-sensitive-file-and-fails",
            "args": [
                "python",
                "-c",
                "import os, pathlib, sys; "
                "pathlib.Path('after_step_secret.env').write_text(os.environ['SECRET_KEY'], encoding='utf-8'); "
                "sys.exit(1)",
            ],
            "capture_output": True,
            "output_policy": "exact",
        }
    ]
    monkeypatch.setattr(runner, "build_quality_gate_command_plan", lambda: failing_plan)

    with pytest.raises(runner.QualityGateError, match="质量门禁第 1/1 步失败"):
        runner.main(["--require-clean-worktree", "--no-long-gate-cache"])

    assert manifest_file.is_file()
    saved_manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert saved_manifest["status"] == "failed"
    assert saved_manifest["finished_at"]
    assert "worktree_fingerprint:" in saved_manifest["worktree_proof_error"]
    assert "SECRET_KEY" in saved_manifest["worktree_proof_error"]
    assert secret not in json.dumps(saved_manifest, ensure_ascii=False)


def test_long_gate_summary_write_failure_does_not_persist_new_success_cache(tmp_path, monkeypatch):
    repo = tmp_path / "summary_order_repo"
    repo.mkdir()
    (repo / ".gitignore").write_text("evidence/\n__pycache__/\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_sample.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    def git(*args):
        completed = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
        assert completed.returncode == 0, completed.stderr

    git("init")
    git("config", "user.email", "gate@example.invalid")
    git("config", "user.name", "Gate Fixture")
    git("add", ".")
    git("commit", "-m", "init summary order repo")

    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setattr(runner, "REPO_ROOT", str(repo))
    monkeypatch.setattr(runner, "REQUIRED_TEST_ARGS", [])
    monkeypatch.setattr(shared, "QUALITY_GATE_SOURCE_FILES", ())
    minimal_plan = [
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
            "output_policy": "exact",
        },
        {
            "display": "python -m pytest --collect-only -q tests",
            "args": ["python", "-m", "pytest", "--collect-only", "-q", "tests"],
            "capture_output": True,
            "output_policy": "exact",
        },
    ]
    outputs_by_display = {
        "python -m ruff --version": "ruff 0.15.0\n",
        "python -m pyright --version": "pyright 1.1.406\n",
        "python -m pytest --collect-only -q tests": "tests/test_sample.py::test_ok\n\n1 test collected in 0.01s\n",
    }
    monkeypatch.setattr(runner, "build_quality_gate_command_plan", lambda: minimal_plan)
    monkeypatch.setattr(
        runner,
        "_run_command",
        lambda display, _args, **_kw: {"returncode": 0, "stdout": outputs_by_display[display], "stderr": ""},
    )

    real_write_summary = runner.write_long_gate_summary

    def fail_summary_write(_summary, _repo_root=None):
        raise OSError("summary disk full")

    monkeypatch.setattr(runner, "write_long_gate_summary", fail_summary_write)
    with pytest.raises(OSError, match="summary disk full"):
        runner.main(["--require-clean-worktree", "--long-gate-cache"])

    assert not (repo / "evidence/QualityGate/long_gate/results").exists()
    assert not (repo / "evidence/QualityGate/long_gate/logs").exists()
    failed_manifest = json.loads((repo / shared.QUALITY_GATE_MANIFEST_REL).read_text(encoding="utf-8"))
    assert failed_manifest["status"] == "failed"

    monkeypatch.setattr(runner, "write_long_gate_summary", real_write_summary)
    assert runner.main(["--require-clean-worktree", "--long-gate-cache"]) == 0
    assert (repo / "evidence/QualityGate/long_gate/results/pytest_collect_all.v2.success.json").is_file()
    assert (repo / "evidence/QualityGate/long_gate/logs/pytest_collect_all.v2.stdout.log").is_file()
