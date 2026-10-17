"""Host-only source, receipt and hook-cache contracts; not a product gate run."""

import copy
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import run_daily_quality_gate as daily
from scripts import run_quality_gate as runner
from tools import git_hook_cache as hooks
from tools import git_hook_checks as checks
from tools.long_gate_schema import content_equal


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
    accepted, error = runner._load_resume_receipt_payload(entry, command, index=1, previous_run_id="saved-run")
    assert accepted is not None and not error
    assert runner._load_resume_receipt_payload(entry, command, index=1, previous_run_id="other-run")[1]
    changed = copy.deepcopy(entry)
    changed["content"]["returncode"] = 1
    assert runner._load_resume_receipt_payload(changed, command, index=1, previous_run_id="saved-run")[1]
    stderr = tmp_path / result["stderr_log_path"]
    stderr.write_text("different output")
    assert runner._load_resume_receipt_payload(entry, command, index=1, previous_run_id="saved-run")[1]
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
