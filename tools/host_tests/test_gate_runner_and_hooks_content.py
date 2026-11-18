"""Host-only source, receipt and hook-cache contracts; not a product gate run."""

import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import venv
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import run_daily_quality_gate as daily
from scripts import run_quality_gate as runner
from tools import daily_gate_scope as scope_tools
from tools import fast_static_precheck as precheck
from tools import git_hook_cache as hooks
from tools import git_hook_checks as checks
from tools import long_gate_fingerprint as lg_fp
from tools import quality_gate_shared as shared
from tools.long_gate_paths import LEDGER_REL, LONG_GATE_CACHE_DIR_REL, GateContext, resolve_repo_root
from tools.long_gate_records import CacheDecision, CommandResult, DecisionCause, ReceiptRow, RuntimeEntry, gate_entries
from tools.long_gate_schema import SensitiveSourceError, content_equal
from tools.long_gate_summary import summary_entry

REPO_ROOT = resolve_repo_root()


def _daily_specs():
    return scope_tools.scanner_specs(REPO_ROOT)


def _plan(paths, *, scope_known=True, repo_root=REPO_ROOT):
    """日常门禁 CLI 与 pre-push hook 共用的范围计划：给定变更路径，得到 pytest、ruff 与扫描器计划。"""
    changed = scope_tools.ChangedPathSet(list(paths), scope_known, "fixture paths")
    return scope_tools.plan_daily_gate_scope(repo_root, changed, _daily_specs())


def _command_result(stdout="", *, returncode=0, stderr=""):
    return CommandResult(
        stdout=stdout,
        stderr=stderr,
        returncode=returncode,
        stdout_log_path="",
        stderr_log_path="",
        execution_mode="executed",
        reused_from={},
        started_at="2026-11-16T00:00:00",
        ended_at="2026-11-16T00:00:01",
        duration_s=0.1,
        duration_kind="executed",
        original_duration_s=None,
    )


def test_runner_binds_dirty_source_and_resume_receipt_to_original_content(tmp_path, monkeypatch):
    ctx = GateContext(str(tmp_path))
    monkeypatch.setattr(runner, "_run_git_bytes", lambda _ctx, _args: b"actual diff\n")
    source = tmp_path / "input.bin"
    source.write_bytes(b"\x00same\xff")
    status = ["?? input.bin"]
    original = runner._dirty_worktree_content(ctx, status)
    source.write_bytes(b"\x00SAME\xff")
    assert not content_equal(original, runner._dirty_worktree_content(ctx, status))
    source.write_bytes(b"\x00same\xff")
    assert content_equal(original, runner._dirty_worktree_content(ctx, status))
    # 未跟踪目录逐个记下其中文件，路径相对本次门禁的仓库根。
    (tmp_path / "fresh_dir" / "nested").mkdir(parents=True)
    (tmp_path / "fresh_dir" / "a.bin").write_bytes(b"a")
    (tmp_path / "fresh_dir" / "nested" / "b.bin").write_bytes(b"b")
    directory_row = runner._dirty_worktree_content(ctx, ["?? fresh_dir/"])["paths"][0]
    assert directory_row["kind"] == "directory"
    assert [row["path"] for row in directory_row["files"]] == ["fresh_dir/a.bin", "fresh_dir/nested/b.bin"]
    monkeypatch.setattr(runner, "REQUIRED_TEST_ARGS", ["input.bin"])
    monkeypatch.setattr(runner, "_guard_test_tracked", lambda _ctx, _path: False)
    runner._assert_guard_tests_ready(ctx, require_tracked=False)
    with pytest.raises(runner.QualityGateError, match="untracked"):
        runner._assert_guard_tests_ready(ctx, require_tracked=True)
    source.unlink()
    with pytest.raises(runner.QualityGateError, match="missing"):
        runner._assert_guard_tests_ready(ctx, require_tracked=False)
    monkeypatch.setattr(runner, "REQUIRED_TEST_ARGS", ["tests/test_a.py", "tests/test_b.py"])
    with pytest.raises(runner.QualityGateError, match="actual collect|实际 collect"):
        runner._handle_collect_quality_gate_command(ctx, _command_result("tests/test_a.py::test_a\n"))
    proof = runner._handle_collect_quality_gate_command(
        ctx, _command_result("tests/test_a.py::test_a\ntests/test_b.py::test_b\n")
    )
    assert proof["collection_proof"]["default_collect_nodeids"] == [
        "tests/test_a.py::test_a", "tests/test_b.py::test_b",
    ]

    spec = shared.GateCheckSpec(
        check_id="host_contract",
        entry_type=shared.ENTRY_VERSION_OR_ENV_PROBE,
        display="host contract",
        args=("python", "host_check.py"),
        capture_output=True,
        output_policy="exact",
        reuse_policy="success",
        runner_handler="default",
    )
    entry = gate_entries([spec])[0]
    monkeypatch.setenv("SECRET_KEY", "fixture-private-only")
    stdout = "fixture-private-only\r\nchecked\n"
    stdout_log, stderr_log = runner._write_command_output_logs(ctx, entry, stdout=stdout, stderr="")
    result = replace(_command_result(stdout), stdout_log_path=stdout_log, stderr_log_path=stderr_log)
    receipt = runner._write_command_receipt(
        ctx,
        entry,
        run_id="saved-run",
        result=result,
        environment=lg_fp.fingerprint_environment(spec.env_keys, repo_root=ctx.repo_root),
    )
    assert receipt["path"] == shared.build_quality_gate_receipt_rel_path(1, "host contract")
    assert receipt["content"]["stdout_content"] == "[REDACTED]\r\nchecked\n"
    assert "fixture-private-only" not in (tmp_path / stdout_log).read_text()
    row = ReceiptRow(receipt["path"], receipt["content"])
    step = runner._bind_previous_receipt(ctx, row, entry, previous_run_id="saved-run")
    assert isinstance(step, runner.ResumedStep)
    assert (step.stdout, step.stderr) == ("[REDACTED]\r\nchecked\n", "")
    assert runner._bind_previous_receipt(ctx, row, entry, previous_run_id="other-run") == (
        "UNBOUND: quality gate command receipt run_id mismatch"
    )
    changed = ReceiptRow(row.path, {**receipt["content"], "returncode": 1})
    assert runner._bind_previous_receipt(ctx, changed, entry, previous_run_id="saved-run") == (
        "UNBOUND: quality gate command receipt content mismatch"
    )
    (tmp_path / stderr_log).write_text("different output")
    assert runner._bind_previous_receipt(ctx, row, entry, previous_run_id="saved-run") == (
        f"旧 receipt 输出原文不一致：{stderr_log}"
    )
    # 续跑沿用绑定时已校验的日志原文，不回头重读磁盘上的日志。
    (tmp_path / stdout_log).write_text("tampered stdout")
    progress = runner.PlanProgress(
        run_id="resumed-run", total=1, commands=[], command_receipts=[], parsed_command_results={}, pending_successes=[]
    )
    runner._run_quality_gate_command_plan(
        ctx,
        [entry],
        progress,
        resume_decision=runner.ResumeDecision(True, "ok", resumed_steps=(step,)),
        long_gate_runtime_entries={},
        long_gate_context=None,
    )
    resumed = progress.command_receipts[0]["content"]
    assert (resumed["stdout_content"], resumed["stderr_content"]) == ("[REDACTED]\r\nchecked\n", "")
    assert resumed["environment"] == receipt["content"]["environment"]
    assert resumed["execution_mode"] == "resumed_success"
    assert resumed["reused_from"]["receipt_content"] == receipt["content"]
    assert (resumed["run_id"], resumed["reused_from"]["run_id"]) == ("resumed-run", "saved-run")
    assert (tmp_path / stdout_log).read_bytes() == b"[REDACTED]\r\nchecked\n"


def test_debt_ledger_sync_proof_records_repo_relative_ledger_path_under_injected_root(tmp_path):
    ctx = GateContext(str(tmp_path))
    spec = next(
        spec for spec in shared.build_quality_gate_check_specs(resolve_repo_root())
        if spec.check_id == shared.ENTRY_DEBT_LEDGER_SYNC
    )
    entry = gate_entries([spec])[0]
    summary = {"schema_version": 2, "checked_at": "2026-11-16T00:00:00+08:00", "oversize_count": 1}
    result = _command_result("治理台账校验通过\n" + json.dumps(summary))
    rel_path = runner._write_debt_ledger_sync_proof(
        ctx, entry, result, run_id="ledger-run", fingerprint={}, cache_dir=LONG_GATE_CACHE_DIR_REL
    )
    proof = json.loads((tmp_path / rel_path).read_text(encoding="utf-8"))
    assert proof["ledger_path"] == LEDGER_REL
    assert (proof["ledger_schema_version"], proof["ledger_counts"]["oversize_count"]) == (2, 1)


def _use_repo_root(monkeypatch, repo):
    """门禁 CLI 在 main() 里解析一次仓库根；临时仓库替换的就是这一次解析。"""
    monkeypatch.setattr(runner, "resolve_repo_root", lambda: str(repo))


def _init_fixture_repo(tmp_path, name):
    repo = tmp_path / name
    repo.mkdir()
    (repo / ".gitignore").write_text("evidence/\n__pycache__/\n", encoding="utf-8")
    for git_args in (
        ["init"],
        ["config", "user.email", "gate@example.invalid"],
        ["config", "user.name", "Gate Fixture"],
        ["add", "."],
        ["commit", "-m", f"init {name}"],
    ):
        subprocess.run(["git", *git_args], cwd=repo, check=True, capture_output=True)
    return repo


def _fail_second_step_in_dirty_gate(tmp_path, monkeypatch, *, env_keys):
    """真实跑一次 allow-dirty 门禁：第 1 步（可复用）通过、第 2 步失败，留下供续跑判定的失败 manifest。"""
    repo = _init_fixture_repo(tmp_path, "resume_env_repo")
    _use_repo_root(monkeypatch, repo)
    monkeypatch.setattr(runner, "REQUIRED_TEST_ARGS", [])
    monkeypatch.setattr(shared, "QUALITY_GATE_SOURCE_FILES", ())
    specs = [
        shared.GateCheckSpec(
            check_id=f"env_step_{index}",
            entry_type=shared.ENTRY_VERSION_OR_ENV_PROBE,
            display=f"env step {index}",
            args=("python", f"env_step_{index}.py"),
            capture_output=True,
            env_keys=env_keys,
            reuse_policy="success",
        )
        for index in (1, 2)
    ]
    monkeypatch.setattr(shared, "build_quality_gate_check_specs", lambda _root, **_kw: specs)
    monkeypatch.setattr(
        runner,
        "_run_command",
        lambda _ctx, check_id, _args, **_kw: {
            "returncode": int(check_id == "env_step_2"), "stdout": "", "stderr": "", "interrupted": False,
        },
    )
    with pytest.raises(runner.QualityGateError, match="第 2/2 步失败"):
        runner.main(["--allow-dirty-worktree"])
    return repo, gate_entries(specs)


def _resume_decision(repo, plan):
    ctx = GateContext(str(repo))
    return runner._decide_resume_from_previous_failure(
        ctx, plan, current_head_sha=runner._git_head_sha(ctx), current_git_status_short=runner._git_status_lines(ctx)
    )


def test_dirty_resume_binds_each_reused_step_to_its_recorded_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("APS_STATIC_VERSION", "first")
    repo, plan = _fail_second_step_in_dirty_gate(tmp_path, monkeypatch, env_keys=("APS_STATIC_VERSION",))
    decision = _resume_decision(repo, plan)
    assert decision.enabled
    assert [step.receipt.command_index for step in decision.resumed_steps] == [1]
    assert (decision.failed_command_index, decision.failed_command_display) == (2, "env step 2")

    monkeypatch.setenv("APS_STATIC_VERSION", "second")
    decision = _resume_decision(repo, plan)
    assert not decision.enabled
    assert decision.reason == "环境与上次不一致：第 1 步（APS_STATIC_VERSION）"

    # receipt（与 manifest 内嵌副本一致地）带坏环境声明时续跑明确拒绝、整轮重跑：没有环境、声明的键缺值
    # 过不了 receipt 准入；声明的键与本步规格的 env_keys 不同过不了续跑绑定。环境差异诊断因此只读已绑定的键。
    monkeypatch.setenv("APS_STATIC_VERSION", "first")
    manifest_path = repo / shared.QUALITY_GATE_MANIFEST_REL
    saved_manifest = manifest_path.read_text(encoding="utf-8")

    def corrupt_first_receipt_environment(mutate):
        manifest = json.loads(saved_manifest)
        receipt_entry = manifest["command_receipts"][0]
        mutate(receipt_entry["content"])
        (repo / receipt_entry["path"]).write_text(json.dumps(receipt_entry["content"]), encoding="utf-8")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return _resume_decision(repo, plan)

    invalid = "UNBOUND: quality gate command receipt environment invalid"
    for mutate, reason in (
        (lambda content: content.pop("environment"), invalid),
        (lambda content: content["environment"]["values"].clear(), invalid),
        (lambda content: content["environment"].update(keys="APS_STATIC_VERSION"), invalid),
        (
            lambda content: content["environment"].update(keys=[], values={}),
            "UNBOUND: quality gate command receipt environment keys mismatch",
        ),
    ):
        decision = corrupt_first_receipt_environment(mutate)
        assert (decision.enabled, decision.reason) == (False, reason)


def test_dirty_resume_refuses_step_whose_private_environment_value_cannot_be_compared(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "first-private-value")
    repo, plan = _fail_second_step_in_dirty_gate(tmp_path, monkeypatch, env_keys=("SECRET_KEY",))
    monkeypatch.setenv("SECRET_KEY", "second-private-value")
    decision = _resume_decision(repo, plan)
    assert not decision.enabled
    assert decision.reason == "环境含私有键，只能确认存在、核对不了取值：第 1 步（SECRET_KEY）"


def test_dirty_resume_reuses_validated_steps_by_command_index_and_reruns_none_steps(tmp_path, monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    repo = _init_fixture_repo(tmp_path, "resume_index_repo")
    _use_repo_root(monkeypatch, repo)
    monkeypatch.setattr(runner, "REQUIRED_TEST_ARGS", [])
    monkeypatch.setattr(shared, "QUALITY_GATE_SOURCE_FILES", ())

    def step(check_id, reuse_policy, runner_handler="default"):
        return shared.GateCheckSpec(
            check_id=check_id,
            entry_type=shared.ENTRY_VERSION_OR_ENV_PROBE,
            display=f"step {check_id}",
            args=("python", f"{check_id}.py"),
            capture_output=True,
            reuse_policy=reuse_policy,
            runner_handler=runner_handler,
        )

    specs = [
        step("ruff_probe", "none", "ruff_version"),
        step("check_a", "success"),
        step("pyright_probe", "none", "pyright_version"),
        step("collect", "success", "pytest_collect_all"),
        step("check_b", "success"),
    ]
    outputs = {
        "ruff_probe": "ruff 0.15.0\n",
        "pyright_probe": "pyright 1.1.406\n",
        "collect": "tests/test_sample.py::test_ok\n\n1 test collected\n",
    }
    failing = {"check_b"}
    calls = []

    def fake_run(_ctx, check_id, _args, **_kw):
        calls.append(check_id)
        return {
            "returncode": int(check_id in failing),
            "stdout": outputs.get(check_id, f"{check_id} ok\n"),
            "stderr": "",
            "interrupted": False,
        }

    monkeypatch.setattr(shared, "build_quality_gate_check_specs", lambda _root, **_kw: specs)
    monkeypatch.setattr(runner, "_run_command", fake_run)
    with pytest.raises(runner.QualityGateError, match="第 5/5 步失败"):
        runner.main(["--allow-dirty-worktree"])
    assert calls == ["ruff_probe", "check_a", "pyright_probe", "collect", "check_b"]

    summary_path = repo / "evidence/QualityGate/long_gate/summary.v2.json"

    def summary_rows(summary):
        return [(row["entry_id"], row["execution_mode"], row["failed"]) for row in summary["entries"]]

    # 续跑期间 long-gate 缓存关闭（不读写缓存），summary 仍按每步实际结果计数：复用 2、失败 1，并给出失败步骤。
    calls.clear()
    with pytest.raises(runner.QualityGateError, match="第 5/5 步失败"):
        runner.main(["--allow-dirty-worktree", "--long-gate-cache"])
    assert calls == ["ruff_probe", "pyright_probe", "check_b"]
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["counts"] == {"executed": 0, "reused": 2, "failed": 1, "disabled": 0}
    assert summary_rows(summary) == [
        ("check_a", "resumed_success", False), ("collect", "resumed_success", False), ("check_b", "executed", True),
    ]
    assert (summary["failure"]["entry_id"], summary["failure"]["receipt_path"]) == (
        "check_b", shared.build_quality_gate_receipt_rel_path(5, "step check_b"),
    )
    assert summary["duration"]["reuse_overhead_total_s"] > 0.0

    failing.clear()
    calls.clear()
    assert runner.main(["--allow-dirty-worktree", "--long-gate-cache"]) == 2
    # none 步骤与上次失败的步骤照常执行；失败位置之前已校验通过的非 none 步骤按原序号复用（含上次续跑复用过的步骤）。
    assert calls == ["ruff_probe", "pyright_probe", "check_b"]
    manifest = json.loads((repo / shared.QUALITY_GATE_MANIFEST_REL).read_text(encoding="utf-8"))
    assert manifest["status"] == "passed_but_unbound"
    resume = manifest["resume"]
    assert (resume["enabled"], resume["resumed_command_indexes"]) == (True, [2, 4])
    assert (resume["failed_command_index"], resume["proof_status"]) == (5, "fast_feedback_only")
    receipts = manifest["command_receipts"]
    assert [row["content"]["command_index"] for row in receipts] == [1, 2, 3, 4, 5]
    assert [row["content"]["execution_mode"] for row in receipts] == [
        "executed", "resumed_success", "executed", "resumed_success", "executed",
    ]
    assert manifest["collection_proof"]["default_collect_nodeids"] == ["tests/test_sample.py::test_ok"]
    assert "long_gate_cache_dir" not in manifest
    assert not (repo / "evidence/QualityGate/long_gate/results").exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["counts"] == {"executed": 1, "reused": 2, "failed": 0, "disabled": 0}
    assert summary_rows(summary) == [
        ("check_a", "resumed_success", False), ("collect", "resumed_success", False), ("check_b", "executed", False),
    ]
    assert summary["failure"] is None


class _FakeChild:
    """门禁子命令替身：输出预先备好，先“运行” `running_polls` 轮再结束。

    运行中被无超时地 wait 就失败：Windows 上无超时的 wait 停在原生等待里，父进程处理不了 Ctrl+C。
    `interrupt_exit` 不为 None 表示父进程在等待时收到 Ctrl+C：子命令随后以该退出码结束；
    为 "ignore" 时子命令不理会中断，宽限期满被终止。
    """

    def __init__(self, stdout, *, running_polls, interrupt_exit=None):
        self.stdout = io.StringIO(stdout)
        self.stderr = io.StringIO("")
        self.running_polls = running_polls
        self.interrupt_exit = interrupt_exit
        self.interrupted = False
        self.terminated = False
        self.returncode = 0

    def wait(self, timeout=None):
        if self.running_polls:
            assert timeout is not None, "等待运行中的子命令必须带超时轮询"
            self.running_polls -= 1
            raise subprocess.TimeoutExpired("fake child", timeout)
        if self.interrupt_exit is not None and not self.interrupted:
            self.interrupted = True
            raise KeyboardInterrupt
        if self.interrupt_exit == "ignore" and not self.terminated:
            raise subprocess.TimeoutExpired("fake child", timeout)
        if self.interrupt_exit not in (None, "ignore"):
            self.returncode = self.interrupt_exit
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15


@pytest.mark.parametrize("step_count", [2, 3])
@pytest.mark.parametrize("interrupt_exit, receipt_returncode", [(0, 0), (130, 130), ("ignore", -15)])
def test_interrupt_while_waiting_for_command_records_step_finalizes_manifest_and_propagates(
    tmp_path, monkeypatch, step_count, interrupt_exit, receipt_returncode
):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    repo = _init_fixture_repo(tmp_path, "interrupt_repo")
    _use_repo_root(monkeypatch, repo)
    monkeypatch.setattr(runner, "REQUIRED_TEST_ARGS", [])
    monkeypatch.setattr(shared, "QUALITY_GATE_SOURCE_FILES", ())
    names = ("first", "slow", "third")[:step_count]
    specs = [
        shared.GateCheckSpec(
            check_id=name,
            entry_type=shared.ENTRY_VERSION_OR_ENV_PROBE,
            display=f"step {name}",
            args=("python", f"{name}.py"),
            capture_output=True,
            reuse_policy="success",
        )
        for name in names
    ]
    monkeypatch.setattr(shared, "build_quality_gate_check_specs", lambda _root, **_kw: specs)
    real_popen = subprocess.Popen
    scripts = {f"{name}.py" for name in names}
    children = {}

    def popen(args, **kwargs):
        script = args[-1]
        if script not in scripts:
            return real_popen(args, **kwargs)  # git 等门禁自身的命令照常执行
        children[script] = _FakeChild(
            f"{script} partial\n", running_polls=2, interrupt_exit=interrupt_exit if script == "slow.py" else None
        )
        return children[script]

    monkeypatch.setattr(subprocess, "Popen", popen)
    with pytest.raises(KeyboardInterrupt, match=f"第 2/{step_count} 步被中断"):
        runner.main(["--allow-dirty-worktree", "--long-gate-cache"])
    assert list(children) == ["first.py", "slow.py"]
    assert children["slow.py"].terminated is (interrupt_exit == "ignore")
    # 中断照样写完失败总账：被中断的步骤带着真实退出码（可能是 0）与已取得的输出写了 receipt，
    # 失败位置单独记录；summary 里登记为失败。
    manifest = json.loads((repo / shared.QUALITY_GATE_MANIFEST_REL).read_text(encoding="utf-8"))
    assert (manifest["status"], manifest["failure_kind"], manifest["failure_command_index"]) == (
        "failed", "interrupted", 2,
    )
    assert f"第 2/{step_count} 步被中断" in manifest["failure_message"]
    receipts = [row["content"] for row in manifest["command_receipts"]]
    assert [(row["command_index"], row["returncode"]) for row in receipts] == [(1, 0), (2, receipt_returncode)]
    assert receipts[1]["stdout_content"] == "slow.py partial\n"
    summary = json.loads((repo / "evidence/QualityGate/long_gate/summary.v2.json").read_text(encoding="utf-8"))
    assert summary["counts"] == {"executed": 1, "reused": 0, "failed": 1, "disabled": 0}
    assert (summary["failure"]["entry_id"], summary["failure"]["receipt_path"]) == (
        "slow", manifest["command_receipts"][1]["path"],
    )

    # 这份失败总账可以续跑：复用第 1 步，从被中断的第 2 步起重跑（不靠退出码定位失败步骤）。
    decision = _resume_decision(repo, gate_entries(specs))
    assert decision.enabled, decision.reason
    assert ([step.receipt.command_index for step in decision.resumed_steps], decision.failed_command_index) == ([1], 2)


def test_hook_cache_and_daily_scope_compare_full_content_and_preserve_old_record(tmp_path, monkeypatch):
    source = tmp_path / "config.bin"
    source.write_bytes(b"\x00first\xff")
    key = {"files": hooks._file_contents(tmp_path, ["config.bin"]), "enabled": True}
    path = tmp_path / "cache.v2.json"
    hooks._write_pass_cache(path, key_payload=key, extra={})
    assert hooks._cache_matches(path, key)
    assert not hooks._cache_matches(path, {**key, "enabled": 1})
    source.write_bytes(b"\x00FIRST\xff")
    assert not hooks._cache_matches(path, {**key, "files": hooks._file_contents(tmp_path, ["config.bin"])})
    old = tmp_path / "cache.json"
    historical = b'{"schema_version":1,"status":"passed","key_hash":"old","key_payload":{}}\n'
    old.write_bytes(historical)
    assert not hooks._cache_matches(old, {})
    assert old.read_bytes() == historical
    assert "key_hash" not in json.loads(path.read_text())

    scope = scope_tools.DailyGateScope(
        scope_tools.ChangedPathSet(["core/a.py"], True, "actual paths"),
        scope_tools.ImpactPlan(["tests/test_a.py"], ["domain"], False, "actual targets"),
        scope_tools.RuffPlan(["core/a.py"], False, "actual ruff targets"),
    )
    content = scope_tools.daily_gate_scope_payload(scope)
    extra = hooks._daily_scope_cache_extra(content)
    assert extra["changed_paths"] == ["core/a.py"]
    assert extra["impact_pytest_target_paths"] == ["tests/test_a.py"]
    assert extra["ruff_target_paths"] == ["core/a.py"]
    assert not any("hash" in key for key in extra)

    ref_contexts = [{"local_ref": "refs/heads/main", "local_sha": "a" * 40, "remote_ref": "refs/heads/main", "remote_sha": "b" * 40}]
    base_key = hooks.daily_gate_cache_key(tmp_path, sys.executable, scope_payload=content, ref_contexts=ref_contexts)
    assert "pytest.ini" in base_key["watched_files"] and "pyproject.toml" in base_key["watched_files"]
    assert base_key["extra"]["pytest_plugins"]
    (tmp_path / "pytest.ini").write_text("[pytest]\naddopts = -q\n", encoding="utf-8")
    assert not content_equal(base_key, hooks.daily_gate_cache_key(tmp_path, sys.executable, scope_payload=content, ref_contexts=ref_contexts))
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k sample")
    env_key = hooks.daily_gate_cache_key(tmp_path, sys.executable, scope_payload=content, ref_contexts=ref_contexts)
    assert env_key["extra"]["pytest_env"]["PYTEST_ADDOPTS"] == "-k sample"

    for env_name, env_value, expected_probe_key, expected_probe_prefix in (
        ("WORKBENCH_NODE", "missing-node-runtime", "node_executable_realpath", "__missing_node__:missing-node-runtime"),
        ("NODE_OPTIONS", "--max-old-space-size=512", None, None),
        ("APS_TEST_POWERSHELL", "missing-pwsh-runtime", "powershell_executable_realpath", "__missing_powershell__:missing-pwsh-runtime"),
    ):
        before = hooks.daily_gate_cache_key(tmp_path, sys.executable, scope_payload=content, ref_contexts=ref_contexts)
        monkeypatch.setenv(env_name, env_value)
        after = hooks.daily_gate_cache_key(tmp_path, sys.executable, scope_payload=content, ref_contexts=ref_contexts)
        assert after["extra"]["pytest_env"][env_name] == env_value
        if expected_probe_key is not None:
            assert after["extra"]["pytest_env"][expected_probe_key] == expected_probe_prefix
        assert not content_equal(before, after)

    win_esbuild_rel = "vendor/node_modules/@esbuild/win32-x64/esbuild.exe"
    win_esbuild = tmp_path / win_esbuild_rel
    win_esbuild.parent.mkdir(parents=True, exist_ok=True)
    win_esbuild.write_bytes(b"MZ\x00win32-esbuild-v1\xff")
    entries = {entry.spec.check_id: entry for entry in gate_entries(shared.build_quality_gate_check_specs(REPO_ROOT))}
    for entry_id in (shared.ENTRY_FULL_TEST_DEBT, shared.ENTRY_REQUIRED_REGRESSIONS):
        fp_v1 = runner.fingerprint_entry(entries[entry_id], str(tmp_path), strict=False)
        win_esbuild.write_bytes(b"MZ\x00win32-esbuild-v2\xff")
        fp_v2 = runner.fingerprint_entry(entries[entry_id], str(tmp_path), strict=False)
        assert not content_equal(fp_v1, fp_v2)
        win_esbuild.write_bytes(b"MZ\x00win32-esbuild-v1\xff")
        assert content_equal(fp_v1, runner.fingerprint_entry(entries[entry_id], str(tmp_path), strict=False))


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink venv probe regression")
def test_daily_gate_cache_key_tracks_symlink_venv_pytest_plugin_versions(tmp_path):
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

    scope = scope_tools.DailyGateScope(
        scope_tools.ChangedPathSet(["app.py"], True, "actual paths"),
        scope_tools.ImpactPlan(["tools/host_tests/test_gate_runner_and_hooks_content.py"], ["domain"], False, "actual targets"),
        scope_tools.RuffPlan(["app.py"], False, "actual ruff targets"),
    )
    content = scope_tools.daily_gate_scope_payload(scope)
    local_ref = "/".join(("refs", "heads", "main"))
    ref_contexts = [{"local_ref": local_ref, "local_sha": "a" * 40, "remote_ref": local_ref, "remote_sha": "b" * 40}]

    hooks._PYTEST_PLUGIN_VERSIONS_CACHE.clear()
    key_v1 = hooks.daily_gate_cache_key(tmp_path, str(venv_python), scope_payload=content, ref_contexts=ref_contexts)
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
    key_v2 = hooks.daily_gate_cache_key(tmp_path, str(venv_python), scope_payload=content, ref_contexts=ref_contexts)
    assert {"name": "audit-hook-plugin", "version": "2.0", "plugins": ["audit_hook"]} in key_v2["extra"]["pytest_plugins"]
    assert not content_equal(key_v1, key_v2)
    assert not hooks._cache_matches(cache_file, key_v2)


def test_daily_gate_runs_all_scanners_after_ruff_whenever_ruff_runs():
    # 五个棘轮与两档循环依赖共用一条触发规则：有 Python 变更（含删除）或要全量跑 ruff 时七个全跑。
    specs = _daily_specs()
    scanners = [*shared.BOUNDARY_RATCHET_CHECK_IDS, *shared.IMPORT_CYCLE_CHECK_IDS]
    assert scanners == [
        "sql_boundary", "private_imports", "dead_path_literals", "over_defense", "dead_code_islands",
        "import_cycles_production", "import_cycles_with_tests",
    ]
    for changed_paths, scope_known in ((["core/models/machine.py"], True), ([], False)):
        scope = _plan(changed_paths, scope_known=scope_known)
        assert scope.ruff_plan.all_files or scope.ruff_plan.target_paths
        commands = daily._commands([], scope.ruff_plan, specs)
        labels = [label for label, _command in commands]
        ruff_index = next(index for index, label in enumerate(labels) if label.startswith("ruff check"))
        scanner_indexes = [index for index, label in enumerate(labels) if label in scanners]
        assert [labels[index] for index in scanner_indexes] == scanners
        assert all(index > ruff_index for index in scanner_indexes)
    skipped = _plan(["README.md"])
    assert not set(scanners) & {label for label, _command in daily._commands([], skipped.ruff_plan, specs)}


def test_daily_gate_scans_deleted_python_files_and_lints_only_existing_ones(tmp_path):
    # 推送里删除的模块已不在工作区；改动的模块还在。扫描器看全部 Python 变更，ruff 只查还存在的文件。
    # 工作区指向临时目录，只写入 modified；deleted 取真实模块路径，在临时工作区里它就是已删除的文件。
    specs = _daily_specs()
    deleted = "core/services/workbench/plan/projection.py"
    modified = "core/services/workbench/plan/queries.py"
    (tmp_path / modified).parent.mkdir(parents=True)
    (tmp_path / modified).write_text("VALUE = 1\n", encoding="utf-8")
    scanners = (*shared.BOUNDARY_RATCHET_CHECK_IDS, *shared.IMPORT_CYCLE_CHECK_IDS)

    deleted_only = _plan([deleted], repo_root=str(tmp_path))
    assert not deleted_only.impact_plan.all_required_groups
    assert deleted_only.ruff_plan == scope_tools.RuffPlan(
        [], False, "changed Python files are all deleted: scanners only, ruff skipped", scanners,
    )
    assert [label for label, _command in daily._commands([], deleted_only.ruff_plan, specs)] == [
        "block staged runtime artifacts", *scanners, "focused pytest",
    ]

    mixed = _plan([deleted, modified], repo_root=str(tmp_path))
    assert mixed.ruff_plan == scope_tools.RuffPlan([modified], False, "changed Python files", scanners)
    mixed_commands = dict(daily._commands([], mixed.ruff_plan, specs))
    assert mixed_commands["ruff check changed files"][-2:] == ["--", modified]
    assert set(scanners) <= set(mixed_commands)


def test_daily_gate_runs_scanners_whose_declared_scopes_match_non_python_changes():
    # 没有 Python 改动时，改动路径落在哪个扫描器规格声明的范围（输入、基线、工具、依赖、只看存在性的路径）里就跑哪个。
    specs = _daily_specs()
    over_defense_cmd = [sys.executable, "-m", "tools.scan_over_defense", "--fail-on-new", "--quiet-when-clean"]

    # over_defense 读前端与跨语言文本：只改前端 JS 或模板也要跑它，pytest 仍只跑受影响的组。
    for changed_path in ("frontend/workbench/app/ActualGanttModel.js", "templates/workbench/index.html"):
        scope = _plan([changed_path])
        assert scope.impact_plan.target_paths
        assert not scope.impact_plan.all_required_groups
        # 前端 JS 与模板同时是 dead_path_literals 只看存在性的路径（顶层目录 × 扩展名）。
        assert scope.ruff_plan == scope_tools.RuffPlan(
            [], False, "scanner scopes changed: " + changed_path, ("dead_path_literals", "over_defense"),
        )
        assert scope_tools.daily_gate_scope_payload(scope)["ruff"] == {
            "target_paths": [],
            "all_files": False,
            "reason": "scanner scopes changed: " + changed_path,
            "boundary_scanners": ["dead_path_literals", "over_defense"],
        }
        commands = daily._commands(scope.impact_plan.target_paths, scope.ruff_plan, specs)
        assert [label for label, _cmd in commands] == [
            "block staged runtime artifacts",
            "dead_path_literals",
            "over_defense",
            "impact and focused pytest",
        ]
        assert commands[2] == ("over_defense", over_defense_cmd)

    # 源码字面量可能引用 `开发文档/` 下的文件：增删改这些文档时 pytest 仍按文档改动处理，只跑 dead_path_literals。
    dead_path_cmd = [sys.executable, "-m", "tools.scan_dead_path_literals", "--fail-on-new", "--quiet-when-clean"]
    doc_path = "开发文档/ADR/0002-python38-依赖锁定.md"
    doc_scope = _plan([doc_path])
    assert doc_scope.impact_plan.reason == "documentation-only changed paths"
    assert doc_scope.ruff_plan == scope_tools.RuffPlan(
        [], False, "scanner scopes changed: " + doc_path, ("dead_path_literals",),
    )
    assert daily._commands(doc_scope.impact_plan.target_paths, doc_scope.ruff_plan, specs) == [
        ("block staged runtime artifacts", [sys.executable, "tools/git_hook_checks.py", "check-staged-artifacts"]),
        ("dead_path_literals", dead_path_cmd),
        ("focused pytest", [sys.executable, "-m", "pytest", "-q", "-rfE", *daily.FOCUSED_PYTEST_NODEIDS]),
    ]
    # 与任何扫描器范围都无关的文档：不跑扫描器。
    readme_scope = _plan(["README.md"])
    assert readme_scope.impact_plan.reason == "documentation-only changed paths"
    assert readme_scope.ruff_plan == scope_tools.RuffPlan([], False, "no changed Python files")

    sql_cmd = [sys.executable, "-m", "tools.scan_sql_boundary", "--rule", "all", "--fail-on-new", "--quiet-when-clean"]
    expected_map = {
        ".codestable/checkup/sql_boundary_baseline.json": ("sql_boundary", sql_cmd),
        ".codestable/checkup/data_policy_baseline.json": ("sql_boundary", sql_cmd),
        ".codestable/checkup/private_import_baseline.json": (
            "private_imports",
            [sys.executable, "-m", "tools.scan_private_imports", "--fail-on-new", "--quiet-when-clean"],
        ),
        ".codestable/checkup/dead_path_literal_baseline.json": (
            "dead_path_literals",
            [sys.executable, "-m", "tools.scan_dead_path_literals", "--fail-on-new", "--quiet-when-clean"],
        ),
        ".codestable/checkup/over_defense_baseline.json": ("over_defense", over_defense_cmd),
        ".codestable/checkup/dead_code_islands_baseline.json": (
            "dead_code_islands",
            [
                sys.executable,
                "-m",
                "tools.scan_dead_code_islands",
                "--mode",
                "quick",
                "--fail-on-new",
                "--quiet-when-clean",
            ],
        ),
        ".codestable/checkup/import_cycles_production_baseline.json": (
            "import_cycles_production",
            [sys.executable, "-m", "tools.scan_import_cycles", "--fail-on-new-cycle", "--quiet-when-clean"],
        ),
        ".codestable/checkup/import_cycles_with_tests_baseline.json": (
            "import_cycles_with_tests",
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
    # 基线是扫描器规格的 config 范围：只改基线时跑它的扫描器，不跑 ruff 和 pytest 影响组。
    # JSON 基线还落在 over_defense 声明的根目录 `*.json` 范围里（现有匹配器的 `*` 跨目录），所以允许它同跑。
    for baseline_path, (expected_scanner, expected_cmd) in expected_map.items():
        scope = _plan([baseline_path])
        assert scope.impact_plan == scope_tools.ImpactPlan([], [], False, "documentation-only changed paths")
        assert scope.ruff_plan.target_paths == []
        assert not scope.ruff_plan.all_files
        assert expected_scanner in scope.ruff_plan.boundary_scanners
        assert set(scope.ruff_plan.boundary_scanners) <= {expected_scanner, "over_defense"}
        assert (expected_scanner, expected_cmd) in daily._commands(scope.impact_plan.target_paths, scope.ruff_plan, specs)

    # 前端、两份 SQL 基线与普通文档混合：取各自命中扫描器的并集，按登记顺序各跑一次，pytest 只跑受影响的组。
    mixed_scope = _plan([
        "frontend/workbench/app/ActualGanttModel.js",
        ".codestable/checkup/data_policy_baseline.json",
        ".codestable/checkup/sql_boundary_baseline.json",
        "README.md",
    ])
    assert mixed_scope.impact_plan.selected_group_ids == ["workbench"]
    assert mixed_scope.ruff_plan.boundary_scanners == ("sql_boundary", "dead_path_literals", "over_defense")
    assert [
        label for label, _cmd in daily._commands(mixed_scope.impact_plan.target_paths, mixed_scope.ruff_plan, specs)
    ] == [
        "block staged runtime artifacts",
        "sql_boundary",
        "dead_path_literals",
        "over_defense",
        "impact and focused pytest",
    ]

    # Python 文件 + 循环依赖基线混合改动：跑 ruff 就七个扫描器全跑，命中的基线不收窄范围
    py_and_cycle_scope = _plan([
        "core/models/machine.py",
        ".codestable/checkup/import_cycles_with_tests_baseline.json",
    ])
    assert py_and_cycle_scope.ruff_plan.target_paths == ["core/models/machine.py"]
    expected_py_scanners = (*shared.BOUNDARY_RATCHET_CHECK_IDS, *shared.IMPORT_CYCLE_CHECK_IDS)
    assert py_and_cycle_scope.ruff_plan.boundary_scanners == expected_py_scanners
    py_and_cycle_cmds = daily._commands(
        py_and_cycle_scope.impact_plan.target_paths, py_and_cycle_scope.ruff_plan, specs
    )
    scanner_ids = {spec.check_id for spec in specs}
    assert tuple(label for label, _cmd in py_and_cycle_cmds if label in scanner_ids) == expected_py_scanners


def test_daily_cli_and_pre_push_hook_plan_the_same_scope_from_the_same_changes(tmp_path):
    repo = _init_fixture_repo(tmp_path, "scope_parity_repo")

    def git(*args):
        completed = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
        return completed.stdout.strip()

    # 扫描器规格从仓库自己的 pyright 配置推导输入范围。
    for name in (shared.QUALITY_GATE_PYRIGHT_GATE_CONFIG, shared.QUALITY_GATE_PYRIGHT_TOOLS_CONFIG):
        shutil.copyfile(Path(REPO_ROOT) / name, repo / name)
    git("add", ".")
    git("commit", "-m", "pyright configs")
    base = git("rev-parse", "HEAD")
    git("branch", "base")
    git("branch", "--set-upstream-to=base")
    code = repo / "core" / "models" / "machine.py"
    code.parent.mkdir(parents=True)
    code.write_text("VALUE = 1\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "code change")
    head = git("rev-parse", "HEAD")
    local_js = repo / "frontend" / "workbench" / "app" / "ActualGanttModel.js"
    local_js.parent.mkdir(parents=True)
    local_js.write_text("export const value = 1;\n", encoding="utf-8")
    specs = scope_tools.scanner_specs(str(repo))

    def cli_payload(*argv):
        scope = daily.daily_gate_scope_for_args(str(repo), daily._parse_args(list(argv)), specs)
        return scope_tools.daily_gate_scope_payload(scope)

    # 没有推送 ref：两边都取本地变更并上相对上游的已提交变更。
    local_payload = cli_payload()
    assert local_payload["changed_paths"] == ["frontend/workbench/app/ActualGanttModel.js", "core/models/machine.py"]
    assert checks._daily_scope_for_refs(repo, [], remote_name="") == local_payload

    # 有推送 ref：hook 只取目标提交的差异；目标 worktree 里的日常门禁读它写的范围文件或自己按 ref 计算，计划一致。
    ref = checks.PrePushRef("refs/heads/main", head, "refs/heads/main", base)
    hook_payload = checks._daily_scope_for_refs(repo, [ref], remote_name="origin")
    assert hook_payload["changed_paths"] == ["core/models/machine.py"]
    local_js.unlink()
    scope_file = tmp_path / "scope.json"
    scope_file.write_text(json.dumps(hook_payload, ensure_ascii=False), encoding="utf-8")
    assert cli_payload("--pre-push-scope-file", str(scope_file)) == hook_payload
    assert cli_payload(
        "--pre-push-from-ref", base, "--pre-push-to-ref", head, "--pre-push-remote-name", "origin"
    ) == hook_payload


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
        "pyrightconfig.gate.json", "tools/__init__.py", "tools/git_hook_checks.py", "tools/git_hook_cache.py",
        "tools/git_hook_blocked_paths.py", "tools/long_gate_schema.py", "tools/long_gate_paths.py",
        "tools/long_gate_fingerprint.py", "tools/long_gate_records.py", "tools/quality_gate_shared.py",
        "tools/install_git_hooks.py", "tools/native_pre_push.py", "tools/test_registry.py",
        "tools/test_registry_data.py", "tools/daily_gate_scope.py", "scripts/__init__.py",
        # 门禁规格从扫描器自己的扫描根与路径角色推导输入范围。
        "tools/boundary_baseline.py", "tools/path_roles.py", "tools/scan_sql_boundary.py",
        "tools/scan_private_imports.py", "tools/scan_dead_path_literals.py", "tools/scan_over_defense.py",
        "tools/scan_import_cycles.py", "tools/import_cycle_analysis.py", "tools/import_cycle_baseline.py",
        "tools/import_cycle_graph.py",
        "scripts/workbench/node_runtime.py",
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
    from tools.daily_gate_scope import daily_gate_scope_payload

    args = _parse_args(sys.argv[1:])
    repo_root = resolve_repo_root()
    scope = daily_gate_scope_for_args(repo_root, args, scanner_specs(repo_root))
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
    ctx = GateContext(str(tmp_path))
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
    monkeypatch.setattr(runner, "_run_git_bytes", lambda _ctx, _args: b"")
    with pytest.raises(runner.QualityGateError, match="SECRET_KEY") as dirty_file_exc:
        runner._dirty_worktree_content(ctx, ["?? pyproject.toml"])
    assert secret not in str(dirty_file_exc.value)
    monkeypatch.setattr(runner, "_run_git_bytes", lambda _ctx, _args: f"+{secret}\n".encode())
    with pytest.raises(runner.QualityGateError, match="敏感环境值"):
        runner._dirty_worktree_content(ctx, [" M pyproject.toml"])

    # Optional long-gate cache boundaries (metadata / refresh / execution / write) degrade to cache_unavailable.
    runner_script = tmp_path / "scripts" / "run_quality_gate.py"
    runner_script.parent.mkdir(parents=True, exist_ok=True)
    runner_script.write_text(f"# {secret}\n", encoding="utf-8")
    plan = [
        entry for entry in gate_entries(shared.build_quality_gate_check_specs(REPO_ROOT))
        if entry.spec.check_id == shared.ENTRY_FULL_TEST_DEBT
    ]
    runtime_entries, context = runner._prepare_long_gate_cache_decisions(
        ctx,
        plan,
        cache_enabled=True,
        cache_dir=LONG_GATE_CACHE_DIR_REL,
        write_success=True,
        force_rerun_entry_ids=(),
        force_rerun_all=False,
    )
    rt = runtime_entries[shared.ENTRY_FULL_TEST_DEBT]
    row = summary_entry(rt)
    assert row["cache_unavailable"] is True
    assert row["cache_status"] == "cache_unavailable"
    # Cache is unavailable, but the command is still executed for real.
    assert row["decision"] == "run"
    assert row["reason"].startswith("cache metadata unavailable;")
    assert row["fingerprint_error"]["failure_kind"] == "cache_metadata_unavailable"
    assert context is not None and context.metadata is None

    # Refresh and write boundaries also catch sensitive sources and mark cache_unavailable without crashing.
    pending_rt = replace(
        rt, decision=CacheDecision("run", DecisionCause.MISSING, "no previous success cache")
    )
    refreshed = runner._refresh_long_gate_decision(
        ctx, pending_rt, runner.LongGateCacheContext(LONG_GATE_CACHE_DIR_REL, {}, True)
    )
    assert refreshed.decision.cache_unavailable is True
    assert refreshed.decision.kind == "run"
    assert refreshed.decision.reason.startswith("strict fingerprint failed;")
    assert refreshed.decision.fingerprint_error.failure_kind == "source_content_unavailable"
    assert summary_entry(refreshed)["cache_status"] == "cache_unavailable"

    runtime_entries[rt.entry.spec.check_id] = pending_rt
    pending = [
        runner.PendingSuccess(
            rt.entry,
            {"schema_version": 2, "components": {"command": rt.entry.command}},
            _command_result("ok\n"),
            "evidence/QualityGate/v4/receipts/01.json",
            ("pyproject.toml",),
            {},
        )
    ]
    prepared_writes = runner._prepare_pending_long_gate_successes(
        ctx, pending, runtime_entries=runtime_entries, run_id="run", cache_dir=LONG_GATE_CACHE_DIR_REL
    )
    assert prepared_writes == []
    written = runtime_entries[rt.entry.spec.check_id]
    assert written.decision.cache_unavailable is True
    assert written.decision.reason.startswith("cache write failed;")
    assert written.decision.fingerprint_error.failure_kind == "cache_write_unavailable"
    assert "SECRET_KEY" in written.decision.fingerprint_error.message
    assert summary_entry(written)["cache_status"] == "cache_unavailable"
    assert not (tmp_path / "evidence/QualityGate/long_gate/logs").exists()
    assert not (tmp_path / "evidence/QualityGate/long_gate/results").exists()

    # Hook cache: SECRET_KEY disables pre-push daily cache; staged ruff executes without writing cache.
    scope = scope_tools.DailyGateScope(
        scope_tools.ChangedPathSet(["core/errors.py"], True, "actual paths"),
        scope_tools.ImpactPlan(["tests/conftest.py"], ["domain"], False, "actual targets"),
        scope_tools.RuffPlan(["core/errors.py"], False, "actual ruff targets"),
    )
    scope_payload = scope_tools.daily_gate_scope_payload(scope)
    ref_contexts = [{"local_ref": "refs/heads/main", "local_sha": "a" * 40, "remote_ref": "refs/heads/main", "remote_sha": "b" * 40}]
    for raw_secret in (secret, f"  {secret}  "):
        monkeypatch.setenv("SECRET_KEY", raw_secret)
        with pytest.raises(hooks.HookCacheError, match="SECRET_KEY"):
            hooks.daily_gate_cache_key(tmp_path, sys.executable, scope_payload=scope_payload, ref_contexts=ref_contexts)
    monkeypatch.setenv("SECRET_KEY", "   ")
    assert hooks.daily_gate_cache_key(tmp_path, sys.executable, scope_payload=scope_payload, ref_contexts=ref_contexts)
    monkeypatch.setenv("SECRET_KEY", secret)

    monkeypatch.setattr(hooks, "staged_python_paths", lambda _root: ("app.py",))
    monkeypatch.setattr(hooks, "staged_tree_hash", lambda _root: "tree123")
    monkeypatch.setattr(hooks, "cache_path", lambda _root, name: tmp_path / name)
    monkeypatch.setattr(
        hooks, "_export_index_to_temp", lambda _root, prefix: (prefix / "app.py").write_text("x = 1\n", encoding="utf-8")
    )
    ruff_calls = []
    monkeypatch.setattr(
        hooks.subprocess,
        "call",
        lambda cmd, **kw: (ruff_calls.append((cmd, kw["cwd"])) or 0),
    )
    assert hooks.run_staged_ruff(tmp_path, sys.executable) == 0
    assert len(ruff_calls) == 1
    assert not (tmp_path / hooks.STAGED_RUFF_CACHE_NAME).exists()


def test_cache_boundaries_only_degrade_sensitive_sources_and_raise_other_value_errors(tmp_path, monkeypatch):
    ctx = GateContext(str(tmp_path))
    monkeypatch.delenv("SECRET_KEY", raising=False)
    defect = ValueError("internal cache defect")

    def raise_defect(*_args, **_kwargs):
        raise defect

    # Long-gate metadata: a non-sensitive ValueError is an internal defect, not "cache unavailable".
    plan = [
        entry for entry in gate_entries(shared.build_quality_gate_check_specs(REPO_ROOT))
        if entry.spec.check_id == shared.ENTRY_FULL_TEST_DEBT
    ]
    monkeypatch.setattr(runner, "long_gate_cache_metadata", raise_defect)
    with pytest.raises(ValueError, match="internal cache defect"):
        runner._prepare_long_gate_cache_decisions(
            ctx,
            plan,
            cache_enabled=True,
            cache_dir=LONG_GATE_CACHE_DIR_REL,
            write_success=True,
            force_rerun_entry_ids=(),
            force_rerun_all=False,
        )
    monkeypatch.setattr(runner, "fingerprint_entry", raise_defect)
    with pytest.raises(ValueError, match="internal cache defect"):
        runner._strict_long_gate_fingerprint(ctx, plan[0])

    # Long-gate writes: a missing declared output is a defect and surfaces instead of being recorded as cache unavailable.
    entry = plan[0]
    rt = RuntimeEntry(entry, CacheDecision("run", DecisionCause.MISSING, "no previous success cache"), None, None)
    runtime_entries = {entry.spec.check_id: rt}
    pending = [
        runner.PendingSuccess(
            entry,
            {"schema_version": 2, "components": {"command": entry.command}},
            _command_result("ok\n"),
            "evidence/QualityGate/v4/receipts/01.json",
            entry.spec.output_result_files,
            {},
        )
    ]
    with pytest.raises(ValueError, match="long gate output file does not exist"):
        runner._prepare_pending_long_gate_successes(
            ctx, pending, runtime_entries=runtime_entries, run_id="run", cache_dir=LONG_GATE_CACHE_DIR_REL
        )
    assert runtime_entries[entry.spec.check_id] is rt

    # Hook caches: only SensitiveSourceError becomes HookCacheError; other ValueErrors propagate.
    watched = tmp_path / "pyproject.toml"
    watched.write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(hooks, "read_file_content", raise_defect)
    with pytest.raises(ValueError, match="internal cache defect"):
        hooks._file_contents(tmp_path, ["pyproject.toml"])

    def raise_sensitive(_path):
        raise SensitiveSourceError("source contains sensitive environment value for SECRET_KEY")

    monkeypatch.setattr(hooks, "read_file_content", raise_sensitive)
    with pytest.raises(hooks.HookCacheError, match="SECRET_KEY"):
        hooks._file_contents(tmp_path, ["pyproject.toml"])
    monkeypatch.setattr(hooks, "staged_python_paths", lambda _root: ("app.py",))
    monkeypatch.setattr(hooks, "staged_tree_hash", lambda _root: "tree123")
    monkeypatch.setattr(hooks, "_cache_key_payload", raise_defect)
    with pytest.raises(ValueError, match="internal cache defect"):
        hooks.run_staged_ruff(tmp_path, sys.executable)

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

    ctx = GateContext(str(repo))
    specs = shared.build_quality_gate_check_specs(REPO_ROOT)

    def daily_scope(*argv):
        return daily.daily_gate_scope_for_args(ctx.repo_root, daily._parse_args(list(argv)), _daily_specs())

    assert hooks.staged_paths(repo) == ["开发文档/开发文档.md"]
    assert checks._staged_paths(repo) == ["开发文档/开发文档.md"]
    assert runner._current_impact_paths(ctx) == ["开发文档/开发文档.md"]
    doc_impact = runner.explain_long_gate_impact(specs, runner._current_impact_paths(ctx), repo_root=ctx.repo_root)
    assert doc_impact["changed_paths"] == ["开发文档/开发文档.md"]
    doc_entries = {row["entry_id"]: row for row in doc_impact["entries"]}
    assert doc_entries["full_test_debt"]["matched_categories"] == ["input"]
    assert doc_entries["ruff_check_full"]["affected"] is False
    # 台账同步检查只读台账与 Python 源码：普通开发文档不影响它，台账本身才影响。
    assert doc_entries["debt_ledger_sync"]["affected"] is False
    ledger_impact = runner.explain_long_gate_impact(specs, [LEDGER_REL], repo_root=ctx.repo_root)
    assert {row["entry_id"]: row for row in ledger_impact["entries"]}["debt_ledger_sync"]["matched_categories"] == [
        "input"
    ]

    staged_scope = daily_scope()
    assert staged_scope.changed.paths == ["开发文档/开发文档.md"]
    assert staged_scope.impact_plan.target_paths == []
    assert staged_scope.impact_plan.reason == "documentation-only changed paths"
    assert staged_scope.ruff_plan.target_paths == []
    assert not staged_scope.ruff_plan.all_files

    git("commit", "-m", "Add Chinese doc")
    doc_sha = git("rev-parse", "HEAD")
    pre_push_doc_scope = daily_scope(
        "--pre-push-from-ref", base_sha, "--pre-push-to-ref", doc_sha, "--pre-push-remote-name", "origin"
    )
    assert pre_push_doc_scope.changed.paths == ["开发文档/开发文档.md"]
    assert pre_push_doc_scope.impact_plan.target_paths == []
    assert pre_push_doc_scope.impact_plan.reason == "documentation-only changed paths"

    code_file = repo / "core" / "algorithms" / "greedy" / "scheduler.py"
    code_file.parent.mkdir(parents=True, exist_ok=True)
    code_file.write_text("VALUE = 1\n", encoding="utf-8")
    git("add", "core/algorithms/greedy/scheduler.py")
    assert precheck.collect_changed_python_files(str(repo)).paths == ("core/algorithms/greedy/scheduler.py",)
    assert runner._current_impact_paths(ctx) == ["core/algorithms/greedy/scheduler.py"]
    code_impact = runner.explain_long_gate_impact(specs, runner._current_impact_paths(ctx), repo_root=ctx.repo_root)
    assert code_impact["changed_paths"] == ["core/algorithms/greedy/scheduler.py"]
    code_entries = {row["entry_id"]: row for row in code_impact["entries"]}
    assert code_entries["ruff_check_full"]["affected"] is True
    assert code_entries["pyright_gate_full"]["affected"] is True
    git("commit", "-m", "Modify scheduler code")
    code_sha = git("rev-parse", "HEAD")

    pre_push_code_scope = daily_scope(
        "--pre-push-from-ref", doc_sha, "--pre-push-to-ref", code_sha, "--pre-push-remote-name", "origin"
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
        assert hooks.staged_paths(repo) == [special_rel]
        assert checks._staged_paths(repo) == [special_rel]
        assert runner._current_impact_paths(ctx) == [special_rel]
        special_impact = runner.explain_long_gate_impact(
            specs, runner._current_impact_paths(ctx), repo_root=ctx.repo_root
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
    plan = shared.build_quality_gate_check_specs(REPO_ROOT)

    def affected(paths):
        impact = runner.explain_long_gate_impact(plan, paths, repo_root=REPO_ROOT)
        return sorted(row["entry_id"] for row in impact["entries"] if row["affected"])

    expected = affected([canonical])
    assert expected
    assert affected(runner._dedupe_impact_paths(args.long_gate_impact_path)) == expected
    assert affected(["tools\\long_gate_cache.py"]) != expected
    win_esbuild_rel = "vendor/node_modules/@esbuild/win32-x64/esbuild.exe"
    assert affected([win_esbuild_rel]) == ["full_test_debt", "required_regressions"]
    win_esbuild_impact = _plan([win_esbuild_rel]).impact_plan
    assert win_esbuild_impact.selected_group_ids == ["workbench"]
    entry_bundle_impact = runner.explain_long_gate_impact(
        plan, ["scripts/workbench/entry_bundle.py"], repo_root=REPO_ROOT
    )
    assert entry_bundle_impact["global_runner_tooling_affected"] is False
    node_runtime_impact = runner.explain_long_gate_impact(
        plan, ["scripts/workbench/node_runtime.py"], repo_root=REPO_ROOT
    )
    assert node_runtime_impact["global_runner_tooling_affected"] is True
    with pytest.raises(SystemExit):
        runner._parse_args(["--long-gate-impact-explain", "--long-gate-impact-path", "./"])
    assert "not a repository-relative path" in capsys.readouterr().err


def test_dirty_sensitive_worktree_cli_exits_2_and_failed_cleanup_finalizes_manifest(tmp_path, monkeypatch):
    source_root = Path(__file__).resolve().parents[2]
    repo = tmp_path / "gate_repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copyfile(source_root / "scripts" / "run_quality_gate.py", repo / "scripts" / "run_quality_gate.py")
    shutil.copyfile(source_root / "pyrightconfig.gate.json", repo / "pyrightconfig.gate.json")
    # 门禁根取自 tools 包所在仓库（resolve_repo_root），fixture 仓库带一份 tools 才会以它为根。
    shutil.copytree(
        source_root / "tools",
        repo / "tools",
        ignore=shutil.ignore_patterns("__pycache__", "host_tests", "symbol_locator", "wufenchang_demo"),
    )
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
    _use_repo_root(monkeypatch, repo)
    monkeypatch.setattr(runner, "REQUIRED_TEST_ARGS", [])
    monkeypatch.setattr(shared, "QUALITY_GATE_SOURCE_FILES", ())
    failing_spec = shared.GateCheckSpec(
        check_id="failing_step",
        entry_type=shared.ENTRY_VERSION_OR_ENV_PROBE,
        display="python step-leaks-sensitive-file-and-fails",
        args=(
            "python",
            "-c",
            "import os, pathlib, sys; "
            "pathlib.Path('after_step_secret.env').write_text(os.environ['SECRET_KEY'], encoding='utf-8'); "
            "sys.exit(1)",
        ),
        capture_output=True,
        output_policy="exact",
        reuse_policy="none",
        runner_handler="default",
    )
    monkeypatch.setattr(shared, "build_quality_gate_check_specs", lambda _root, **_kw: [failing_spec])

    with pytest.raises(runner.QualityGateError, match="质量门禁第 1/1 步失败"):
        runner.main(["--require-clean-worktree", "--no-long-gate-cache"])

    assert manifest_file.is_file()
    saved_manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert saved_manifest["status"] == "failed"
    assert saved_manifest["finished_at"]
    assert "worktree_fingerprint:" in saved_manifest["worktree_proof_error"]
    assert "SECRET_KEY" in saved_manifest["worktree_proof_error"]
    assert secret not in json.dumps(saved_manifest, ensure_ascii=False)


def _clean_collect_gate_repo(tmp_path, monkeypatch):
    """干净临时仓库上的最小真实计划（两个版本探针 + 可复用的 collect 步骤），命令输出由替身给出。"""
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
    _use_repo_root(monkeypatch, repo)
    monkeypatch.setattr(runner, "REQUIRED_TEST_ARGS", [])
    monkeypatch.setattr(shared, "QUALITY_GATE_SOURCE_FILES", ())
    all_specs = shared.build_quality_gate_check_specs(REPO_ROOT)
    minimal_specs = [
        spec
        for spec in all_specs
        if spec.check_id in {"ruff_version_probe", "pyright_version_probe", shared.ENTRY_PYTEST_COLLECT_ALL}
    ]
    outputs_by_check_id = {
        "ruff_version_probe": "ruff 0.15.0\n",
        "pyright_version_probe": "pyright 1.1.406\n",
        shared.ENTRY_PYTEST_COLLECT_ALL: "tests/test_sample.py::test_ok\n\n1 test collected in 0.01s\n",
    }
    monkeypatch.setattr(shared, "build_quality_gate_check_specs", lambda _root, **_kw: minimal_specs)
    monkeypatch.setattr(
        runner,
        "_run_command",
        lambda _ctx, check_id, _args, **_kw: {
            "returncode": 0, "stdout": outputs_by_check_id[check_id], "stderr": "", "interrupted": False,
        },
    )
    return repo, all_specs


def test_proof_write_failure_after_command_success_keeps_step_result_in_summary(tmp_path, monkeypatch):
    repo, _all_specs = _clean_collect_gate_repo(tmp_path, monkeypatch)

    def deny_proof_write(*_args, **_kwargs):
        raise PermissionError("proof write denied")

    monkeypatch.setattr(runner, "_write_long_gate_output_files", deny_proof_write)
    with pytest.raises(PermissionError, match="proof write denied"):
        runner.main(["--require-clean-worktree", "--long-gate-cache"])
    manifest = json.loads((repo / shared.QUALITY_GATE_MANIFEST_REL).read_text(encoding="utf-8"))
    collect_receipt = manifest["command_receipts"][-1]
    assert (manifest["status"], collect_receipt["content"]["returncode"]) == ("failed", 0)
    # 命令已通过、receipt 已写，写证明失败：summary 保留这一步的执行结果、receipt 与失败定位，不写成功缓存。
    summary = json.loads((repo / "evidence/QualityGate/long_gate/summary.v2.json").read_text(encoding="utf-8"))
    (row,) = summary["entries"]
    assert (row["entry_id"], row["execution_mode"], row["returncode"], row["failed"]) == (
        shared.ENTRY_PYTEST_COLLECT_ALL, "executed", 0, True,
    )
    assert row["receipt_path"] == collect_receipt["path"] and row["duration_s"] > 0.0
    assert summary["counts"] == {"executed": 0, "reused": 0, "failed": 1, "disabled": 0}
    assert summary["failure"]["entry_id"] == shared.ENTRY_PYTEST_COLLECT_ALL
    assert not (repo / "evidence/QualityGate/long_gate/results").exists()


def test_long_gate_summary_write_failure_does_not_persist_new_success_cache(tmp_path, monkeypatch):
    repo, all_specs = _clean_collect_gate_repo(tmp_path, monkeypatch)
    real_write_summary = runner.write_long_gate_summary

    def fail_summary_write(_summary, _repo_root):
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

    # Custom check_id entries with proof_kind="full_test_debt" / "required_regressions" dispatch by proof_kind.
    base_by_id = {spec.check_id: spec for spec in all_specs}
    custom_full_spec = replace(base_by_id[shared.ENTRY_FULL_TEST_DEBT], check_id="custom_full_debt_probe")
    custom_req_spec = replace(base_by_id[shared.ENTRY_REQUIRED_REGRESSIONS], check_id="custom_req_regressions_probe")
    custom_entries = {entry.spec.check_id: entry for entry in gate_entries([custom_full_spec, custom_req_spec])}
    assert shared.QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL in lg_fp._entry_file_scopes(
        custom_entries["custom_req_regressions_probe"]
    )
    assert shared.QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL not in lg_fp._entry_file_scopes_for_fingerprint(
        custom_entries["custom_req_regressions_probe"]
    )

    def fake_fingerprint(_ctx, entry, **_kw):
        return {
            "schema_version": 2,
            "components": {"command": entry.command, "environment": {"non_reusable_env_keys": []}},
        }

    monkeypatch.setattr(runner, "_strict_long_gate_fingerprint", fake_fingerprint)
    context = runner.LongGateCacheContext(
        LONG_GATE_CACHE_DIR_REL, runner.long_gate_cache_metadata(str(repo), cache_dir=LONG_GATE_CACHE_DIR_REL), True
    )
    for entry in custom_entries.values():
        stale = RuntimeEntry(entry, CacheDecision("run", DecisionCause.REJECTED, "stale initial decision"), None, None)
        refreshed = runner._refresh_long_gate_decision(GateContext(str(repo)), stale, context)
        assert refreshed.fingerprint == fake_fingerprint(None, entry)
        assert (refreshed.decision.cause, refreshed.decision.reason) == (DecisionCause.MISSING, "no previous success cache")


def _load_full_selftest_module(monkeypatch):
    monkeypatch.syspath_prepend(
        str(Path(REPO_ROOT) / ".limcode/skills/aps-full-selftest/scripts")
    )
    monkeypatch.delitem(sys.modules, "run_full_selftest", raising=False)
    import run_full_selftest  # type: ignore[import-not-found]

    return run_full_selftest


def test_full_selftest_delegates_quality_gate_binding_to_common_runner(tmp_path, monkeypatch):
    selftest_rel = ".limcode/skills/aps-full-selftest/scripts/run_full_selftest.py"
    assert selftest_rel in shared.QUALITY_GATE_TOOL_PATHS
    runner._assert_pyright_tools_config_matches_tool_paths(GateContext(REPO_ROOT))

    selftest = _load_full_selftest_module(monkeypatch)
    head_sha = "c" * 40
    manifest_path = tmp_path / shared.QUALITY_GATE_MANIFEST_REL
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    binding_log = tmp_path / "evidence/FullSelfTest/logs/00_quality_gate_binding.log.txt"
    calls = []

    def fake_run_cmd(*, cmd, cwd, timeout_s):
        calls.append((list(cmd), cwd, timeout_s))
        return cmd_outcome["exit_code"], 0.25, cmd_outcome["output"], False

    cmd_outcome = {"exit_code": 0, "output": "gate stdout\n"}
    post_status = {"lines": []}
    monkeypatch.setattr(selftest, "_run_cmd", fake_run_cmd)
    monkeypatch.setattr(selftest, "_git_head_sha", lambda _root: head_sha)
    monkeypatch.setattr(selftest, "_git_status_lines", lambda _root: list(post_status["lines"]))

    dirty_step = selftest._quality_gate_binding_status(tmp_path, head_sha, [" M app.py"])
    assert not dirty_step.effective_pass
    assert calls == []
    assert "工作区不干净" in dirty_step.note
    assert " M app.py" in binding_log.read_text(encoding="utf-8")

    expected_gate_cmd = [
        selftest._project_python(tmp_path),
        "scripts/run_quality_gate.py",
        "--require-clean-worktree",
        "--long-gate-cache",
        "--no-resume",
    ]
    cmd_outcome = {"exit_code": 2, "output": "gate failed output"}
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": shared.QUALITY_GATE_PROOF_SCHEMA_VERSION,
                "status": "failed",
                "head_sha": head_sha,
                "failure_kind": "ruff_failed",
                "failure_message": "ruff check exited 1",
            }
        ),
        encoding="utf-8",
    )
    failed_step = selftest._quality_gate_binding_status(tmp_path, head_sha, [])
    assert not failed_step.effective_pass
    assert failed_step.exit_code == 2
    assert calls[-1] == (expected_gate_cmd, tmp_path, None)
    assert "failure_kind=ruff_failed" in failed_step.note
    assert "gate failed output" in binding_log.read_text(encoding="utf-8")

    valid_manifest = {
        "schema_version": shared.QUALITY_GATE_PROOF_SCHEMA_VERSION,
        "status": "passed",
        "head_sha": head_sha,
        "is_dirty_before": False,
        "is_dirty_after": False,
        "tracked_drift_detected": False,
    }
    cmd_outcome = {"exit_code": 0, "output": "质量门禁通过"}
    for invalid_override in (
        {"schema_version": 3},
        {"status": "passed_but_unbound"},
        {"head_sha": "d" * 40},
        {"is_dirty_after": True},
        {"tracked_drift_detected": True},
    ):
        manifest_path.write_text(json.dumps({**valid_manifest, **invalid_override}), encoding="utf-8")
        rejected_step = selftest._quality_gate_binding_status(tmp_path, head_sha, [])
        assert not rejected_step.effective_pass

    manifest_path.write_text(json.dumps(valid_manifest), encoding="utf-8")
    post_status["lines"] = ["?? leaked.tmp"]
    drifted_step = selftest._quality_gate_binding_status(tmp_path, head_sha, [])
    assert not drifted_step.effective_pass
    assert "运行后工作区不干净" in drifted_step.note

    post_status["lines"] = []
    calls.clear()
    ok, results, report_rel = selftest.run_full_selftest(repo_root=tmp_path, fail_fast=False, step_timeout_s=120)
    assert ok is True
    assert [row.name for row in results] == ["quality_gate_binding", "pytest_tests"]
    assert [row[0] for row in calls] == [
        expected_gate_cmd,
        [selftest._project_python(tmp_path), "-m", "pytest", "tests", "-q", "--tb=short"],
    ]
    assert calls[0][2] is None and calls[1][2] == 120
    assert (tmp_path / report_rel).is_file()
    assert "- 总执行耗时：" in (tmp_path / report_rel).read_text(encoding="utf-8")
    assert "[BINDING] BOUND" in binding_log.read_text(encoding="utf-8")


def test_quickref_vs_routes_output_path_matches_gate_spec_and_long_gate_cache(tmp_path, monkeypatch, capsys):
    from flask import Flask

    from tests.gate_meta import check_quickref_vs_routes as quickref_check
    from tools import long_gate_cache

    spec = next(
        item
        for item in shared.build_quality_gate_check_specs(REPO_ROOT)
        if item.check_id == shared.ENTRY_QUICKREF_VS_ROUTES
    )
    expected_rel = shared.QUALITY_GATE_QUICKREF_VS_ROUTES_REL.replace("\\", "/")
    assert spec.output_result_files == (expected_rel,)

    doc_dir = tmp_path / "开发文档"
    doc_dir.mkdir(parents=True)
    (doc_dir / "系统速查表.md").write_text("- `GET /api/ping`：健康检查\n", encoding="utf-8")

    fake_app = Flask("quickref_contract")
    fake_app.add_url_rule("/api/ping", "ping", lambda: "ok", methods=["GET"])

    monkeypatch.setattr(quickref_check, "find_repo_root", lambda: str(tmp_path))
    monkeypatch.setattr(quickref_check, "_load_app_for_scan", lambda _root: (fake_app, ""))

    assert quickref_check.main() == 0
    assert capsys.readouterr().out.splitlines() == [expected_rel, "OK"]
    assert (tmp_path / expected_rel).is_file()

    rows = long_gate_cache._read_output_files(str(tmp_path), spec.output_result_files)
    assert [row["path"] for row in rows] == [expected_rel]
    entry = next(
        entry
        for entry in gate_entries(shared.build_quality_gate_check_specs(REPO_ROOT))
        if entry.spec.check_id == shared.ENTRY_QUICKREF_VS_ROUTES
    )
    assert entry.spec.output_result_files == (expected_rel,)
    assert long_gate_cache.missing_declared_output(entry, rows) == ""
    assert (
        long_gate_cache.missing_declared_output(entry, [])
        == f"previous output files missing required path: {expected_rel}"
    )


def test_provision_worktree_esbuild_vendor_skips_minimal_copies_cleanly_and_fails_offline_when_missing(
    tmp_path, monkeypatch
):
    from scripts.workbench import vendor_react

    source_root = Path(__file__).resolve().parents[2]
    monkeypatch.setattr(
        vendor_react,
        "read_url",
        lambda _url: (_ for _ in ()).throw(AssertionError("worktree provisioning must never touch network")),
    )

    env = checks._quality_gate_env()
    # 1. Minimal fixture without scripts/workbench/esbuild-manifest.json skips silently.
    minimal_wt = tmp_path / "minimal_worktree"
    minimal_wt.mkdir()
    checks._provision_worktree_esbuild_vendor(tmp_path / "nonexistent_host", minimal_wt, environment=env)
    assert not (minimal_wt / "vendor").exists()

    # 2. Tracked manifest in a clean git worktree copies esbuild vendor, passes verify_esbuild_vendor,
    #    and keeps `git status --porcelain` completely clean via .gitignore.
    repo = tmp_path / "esbuild_wt_repo"
    (repo / "scripts" / "workbench").mkdir(parents=True)
    shutil.copyfile(source_root / ".gitignore", repo / ".gitignore")
    shutil.copyfile(
        source_root / "scripts" / "workbench" / "esbuild-manifest.json",
        repo / "scripts" / "workbench" / "esbuild-manifest.json",
    )

    def git(cwd, *args):
        res = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8")
        assert res.returncode == 0, res.stderr
        return res.stdout

    git(repo, "init")
    git(repo, "config", "user.email", "wt@example.invalid")
    git(repo, "config", "user.name", "Worktree Tester")
    git(repo, "add", ".gitignore", "scripts/workbench/esbuild-manifest.json")
    git(repo, "commit", "-m", "Add esbuild manifest")
    head_sha = git(repo, "rev-parse", "HEAD").strip()

    worktree = tmp_path / "detached_wt"
    git(repo, "worktree", "add", "--detach", str(worktree), head_sha)
    try:
        checks._provision_worktree_esbuild_vendor(source_root, worktree, environment=env)
        host_platform = vendor_react.current_esbuild_platform_key()
        verified = vendor_react.verify_esbuild_vendor(
            worktree,
            vendor_react.load_esbuild_manifest(worktree / "scripts/workbench/esbuild-manifest.json"),
            host_platform=host_platform,
            target_platform=host_platform,
        )
        assert verified["status"] == "verified"
        assert verified["version"] == vendor_react.ESBUILD_VERSION
        assert git(worktree, "status", "--porcelain") == ""

        # 3. Missing host vendor fails fast offline with clear remediation message.
        missing_host = tmp_path / "empty_host"
        missing_host.mkdir()
        fresh_wt = tmp_path / "fresh_wt"
        git(repo, "worktree", "add", "--detach", str(fresh_wt), head_sha)
        try:
            with pytest.raises(RuntimeError, match=r"vendor_react\.py --install-esbuild"):
                checks._provision_worktree_esbuild_vendor(missing_host, fresh_wt, environment=env)
        finally:
            git(repo, "worktree", "remove", "--force", str(fresh_wt))
    finally:
        git(repo, "worktree", "remove", "--force", str(worktree))

    # 4. run_quality_gate catches RuntimeError from missing vendor, prints to stderr, returns 1, and cleans up worktree.
    monkeypatch.setattr(checks, "project_python_executable", lambda _root: sys.executable)
    monkeypatch.setattr(
        checks,
        "_pre_push_input_for_hook",
        lambda _stream=None: checks.PrePushInput(
            [checks.PrePushRef("refs/heads/main", head_sha, "refs/heads/main", checks.ZERO_SHA)],
            True,
        ),
    )
    monkeypatch.setattr(checks, "_daily_scope_for_refs", lambda _root, _refs, *, remote_name: {"changed_paths": []})
    monkeypatch.setattr(
        hooks,
        "daily_gate_cache_key",
        lambda *_a, **_kw: (_ for _ in ()).throw(hooks.HookCacheError("skip cache in unit test")),
    )
    err_buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", err_buf)
    rc = checks.run_quality_gate(repo, checks.argparse.Namespace(remote_name="origin", remote_url="origin", remote_ref=""))
    assert rc == 1
    assert "vendor_react.py --install-esbuild" in err_buf.getvalue()
    assert git(repo, "worktree", "list", "--porcelain").count("worktree ") == 1


def test_daily_gate_cache_invalidates_when_host_esbuild_vendor_tampered_or_removed(tmp_path, monkeypatch):
    source_root = Path(__file__).resolve().parents[2]
    repo = tmp_path / "esbuild_cache_repo"
    (repo / "scripts" / "workbench").mkdir(parents=True)
    shutil.copyfile(
        source_root / "scripts" / "workbench" / "esbuild-manifest.json",
        repo / "scripts" / "workbench" / "esbuild-manifest.json",
    )
    env = checks._quality_gate_env()
    init_res = subprocess.run(["git", "init"], cwd=repo, env=env, capture_output=True, text=True, encoding="utf-8")
    assert init_res.returncode == 0, init_res.stderr
    checks._provision_worktree_esbuild_vendor(source_root, repo, environment=env)

    scope = scope_tools.DailyGateScope(
        scope_tools.ChangedPathSet(["app.py"], True, "actual paths"),
        scope_tools.ImpactPlan(["tests/conftest.py"], ["domain"], False, "actual targets"),
        scope_tools.RuffPlan(["app.py"], False, "actual ruff targets"),
    )
    content = scope_tools.daily_gate_scope_payload(scope)
    ref_contexts = [
        {"local_ref": "refs/heads/main", "local_sha": "a" * 40, "remote_ref": "refs/heads/main", "remote_sha": "b" * 40}
    ]

    key_ok = hooks.daily_gate_cache_key(
        repo, sys.executable, remote_name="origin", remote_ref="refs/heads/main", scope_payload=content, ref_contexts=ref_contexts
    )
    esbuild_meta = key_ok["extra"]["esbuild_vendor"]
    assert esbuild_meta["required"] is True
    assert esbuild_meta["verified"] is True
    assert "files" in esbuild_meta and not any("sha" in k or "hash" in k for k in esbuild_meta)

    hooks.write_pre_push_daily_cache(
        repo,
        sys.executable,
        remote_name="origin",
        remote_ref="refs/heads/main",
        scope_payload=content,
        ref_contexts=ref_contexts,
        key_payload=key_ok,
    )
    assert hooks.pre_push_daily_cache_hit(
        repo, sys.executable, remote_name="origin", remote_ref="refs/heads/main", scope_payload=content, ref_contexts=ref_contexts
    )

    # Modifying esbuild core JS updates (size, mtime_ns) metadata and misses cache immediately.
    main_js = repo / "vendor/node_modules/esbuild/lib/main.js"
    original_main_js = main_js.read_bytes()
    original_stat = main_js.stat()
    tampered_main_js = (b"//" if not original_main_js.startswith(b"//") else b"/*") + original_main_js[2:]
    main_js.write_bytes(tampered_main_js)
    os.utime(main_js, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns + 1_000_000))
    key_tampered = hooks.daily_gate_cache_key(
        repo, sys.executable, remote_name="origin", remote_ref="refs/heads/main", scope_payload=content, ref_contexts=ref_contexts
    )
    assert key_tampered["extra"]["esbuild_vendor"]["verified"] is True
    assert key_tampered["extra"]["esbuild_vendor"]["files"] != esbuild_meta["files"]
    assert not hooks.pre_push_daily_cache_hit(
        repo, sys.executable, remote_name="origin", remote_ref="refs/heads/main", scope_payload=content, ref_contexts=ref_contexts
    )

    main_js.write_bytes(original_main_js)
    os.utime(main_js, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    assert hooks.pre_push_daily_cache_hit(
        repo, sys.executable, remote_name="origin", remote_ref="refs/heads/main", scope_payload=content, ref_contexts=ref_contexts
    )

    # Removing host esbuild vendor flips verified=False and invalidates cache immediately.
    shutil.rmtree(repo / "vendor/node_modules/esbuild")
    key_missing = hooks.daily_gate_cache_key(
        repo, sys.executable, remote_name="origin", remote_ref="refs/heads/main", scope_payload=content, ref_contexts=ref_contexts
    )
    assert key_missing["extra"]["esbuild_vendor"]["required"] is True
    assert key_missing["extra"]["esbuild_vendor"]["verified"] is False
    assert not hooks.pre_push_daily_cache_hit(
        repo, sys.executable, remote_name="origin", remote_ref="refs/heads/main", scope_payload=content, ref_contexts=ref_contexts
    )


@pytest.mark.skipif(os.name == "nt", reason="POSIX Rosetta node shim regression")
def test_esbuild_platform_key_and_worktree_provision_follow_rosetta_node_arch(tmp_path, monkeypatch):
    from scripts.workbench import vendor_react

    source_root = Path(__file__).resolve().parents[2]
    shim_dir = tmp_path / "rosetta_bin"
    shim_dir.mkdir()
    rosetta_node = shim_dir / "node"
    rosetta_node.write_text(
        '#!/bin/sh\n'
        'if [ "$1" = "--version" ]; then\n'
        '  echo "v20.11.1"\n'
        '  exit 0\n'
        'fi\n'
        'if [ "$1" = "-p" ]; then\n'
        '  printf "\\377" >&2\n'
        '  echo "darwin-x64"\n'
        '  exit 0\n'
        'fi\n'
        'exit 1\n',
        encoding="utf-8",
    )
    rosetta_node.chmod(0o755)

    unsupported_node = shim_dir / "unsupported_node"
    unsupported_node.write_text(
        '#!/bin/sh\n'
        'if [ "$1" = "--version" ]; then\n'
        '  echo "v20.11.1"\n'
        '  exit 0\n'
        'fi\n'
        'echo "freebsd-x64"\n',
        encoding="utf-8",
    )
    unsupported_node.chmod(0o755)
    with monkeypatch.context() as patch_ctx:
        patch_ctx.setenv("WORKBENCH_NODE", str(rosetta_node))
        assert vendor_react.current_esbuild_platform_key() == "darwin-x64"
        patch_ctx.setenv("WORKBENCH_NODE", str(unsupported_node))
        with pytest.raises(ValueError, match="Unsupported esbuild Node platform"):
            vendor_react.current_esbuild_platform_key()

    fake_host = tmp_path / "rosetta_host"
    (fake_host / "vendor/node_modules").mkdir(parents=True)
    shutil.copytree(source_root / "vendor/node_modules/esbuild", fake_host / "vendor/node_modules/esbuild")
    x64_dir = fake_host / "vendor/node_modules/@esbuild/darwin-x64"
    (x64_dir / "bin").mkdir(parents=True)
    (x64_dir / "package.json").write_text(
        json.dumps({"name": "@esbuild/darwin-x64", "version": vendor_react.ESBUILD_VERSION}),
        encoding="utf-8",
    )
    x64_bin = x64_dir / "bin/esbuild"
    x64_bin.write_text(f"#!/bin/sh\necho {vendor_react.ESBUILD_VERSION}\n", encoding="utf-8")
    x64_bin.chmod(0o755)

    worktree = tmp_path / "rosetta_worktree"
    (worktree / "scripts/workbench").mkdir(parents=True)
    shutil.copyfile(
        source_root / "scripts/workbench/esbuild-manifest.json",
        worktree / "scripts/workbench/esbuild-manifest.json",
    )
    gate_env = {**checks._quality_gate_env(), "WORKBENCH_NODE": str(rosetta_node)}
    lg_fp._RUNTIME_FINGERPRINT_CACHE.clear()
    checks._provision_worktree_esbuild_vendor(fake_host, worktree, environment=gate_env)

    assert (worktree / "vendor/node_modules/@esbuild/darwin-x64/bin/esbuild").is_file()
    assert not (worktree / "vendor/node_modules/@esbuild/darwin-arm64").exists()


def test_anchor_node_env_anchors_relative_workbench_node_and_path_across_cwd_changes(
    tmp_path, monkeypatch
):
    import ntpath
    import types

    from scripts.workbench import node_runtime
    from scripts.workbench.node_runtime import NodeNotFoundError, anchor_node_env, select_node_runtime

    parent_dir = tmp_path / "parent"
    child_repo = parent_dir / "repo"
    child_repo.mkdir(parents=True)
    bin_name = "node-local.exe" if os.name == "nt" else "node-local"
    if os.name == "nt":
        real_rt = lg_fp.resolve_cached_node_runtime()
        child_node = Path(shutil.copy2(real_rt.realpath, child_repo / bin_name))
    else:
        child_node = child_repo / bin_name
        child_node.write_text('#!/bin/sh\necho "v20.11.1"\n', encoding="utf-8")
        child_node.chmod(0o755)

    monkeypatch.chdir(parent_dir)
    anchored_missing = anchor_node_env({"WORKBENCH_NODE": "./node-local", "PATH": ""})
    assert anchored_missing["WORKBENCH_NODE"] == os.path.join(str(parent_dir), "./node-local")
    monkeypatch.chdir(child_repo)
    with pytest.raises(NodeNotFoundError):
        select_node_runtime(anchored_missing)

    if os.name == "nt":
        parent_node = Path(shutil.copy2(child_node, parent_dir / bin_name))
    else:
        parent_node = parent_dir / bin_name
        parent_node.write_text('#!/bin/sh\necho "v22.12.0"\n', encoding="utf-8")
        parent_node.chmod(0o755)

    monkeypatch.chdir(parent_dir)
    anchored_present = anchor_node_env(
        {"WORKBENCH_NODE": "./node-local", "PATH": f"rel_bin{os.pathsep}{tmp_path / 'abs_bin'}"}
    )
    assert anchored_present["PATH"] == f"{os.path.join(str(parent_dir), 'rel_bin')}{os.pathsep}{tmp_path / 'abs_bin'}"
    monkeypatch.chdir(child_repo)
    selected = select_node_runtime(anchored_present)
    assert selected.realpath == os.path.realpath(str(parent_node))
    if os.name != "nt":
        assert selected.version == "v22.12.0"

    child_tilde_bin = child_repo / "home" / "bin"
    child_tilde_bin.mkdir(parents=True)
    shutil.copy2(child_node, child_tilde_bin / ("node.exe" if os.name == "nt" else "node"))

    monkeypatch.chdir(parent_dir)
    unconfigured = anchor_node_env({"PATH": f"rel_only{os.pathsep}~/keep_tilde{os.pathsep}"})
    assert "WORKBENCH_NODE" not in unconfigured
    expected_trailing = "" if os.name == "nt" else str(parent_dir)
    assert unconfigured["PATH"] == os.pathsep.join(
        (os.path.join(str(parent_dir), "rel_only"), os.path.join(str(parent_dir), "~/keep_tilde"), expected_trailing)
    )
    assert anchor_node_env({"WORKBENCH_NODE": "custom-node"})["WORKBENCH_NODE"] == "custom-node"
    tilde_anchored = anchor_node_env(
        {"HOME": "home", "USERPROFILE": "home", "WORKBENCH_NODE": "~/bin/node", "PATH": ""}
    )
    assert tilde_anchored["WORKBENCH_NODE"] == os.path.join(str(parent_dir), "home", "bin/node")
    monkeypatch.chdir(child_repo)
    with pytest.raises(NodeNotFoundError):
        select_node_runtime(tilde_anchored)

    monkeypatch.chdir(parent_dir)
    monkeypatch.setenv("WORKBENCH_NODE", "./missing-hook-node")
    monkeypatch.setenv("PATH", f"hook_rel_bin{os.pathsep}{os.environ.get('PATH', '')}")
    hook_env = checks._quality_gate_env()
    assert hook_env["WORKBENCH_NODE"] == os.path.join(str(parent_dir), "./missing-hook-node")
    assert hook_env["PATH"].split(os.pathsep)[0] == os.path.join(str(parent_dir), "hook_rel_bin")
    assert daily._gate_env()["WORKBENCH_NODE"] == os.path.join(str(parent_dir), "./missing-hook-node")

    fake_nt_os = types.SimpleNamespace(
        name="nt",
        path=ntpath,
        pathsep=";",
        curdir=".",
        pardir="..",
        sep="\\",
        altsep="/",
        getcwd=lambda: "D:\\repo",
    )
    with monkeypatch.context() as patch_ctx:
        patch_ctx.setattr(node_runtime, "os", fake_nt_os)
        win_anchored = anchor_node_env(
            {"WORKBENCH_NODE": "\\Tools\\nodejs\\node.exe", "PATH": "\\Tools\\nodejs;C:\\Windows\\System32;;rel_bin"}
        )
        assert win_anchored == {
            "WORKBENCH_NODE": "D:\\Tools\\nodejs\\node.exe",
            "PATH": "D:\\Tools\\nodejs;C:\\Windows\\System32;;D:\\repo\\rel_bin",
        }
        assert not node_runtime._has_root_anchor("\\Tools\\nodejs")
        assert node_runtime._has_root_anchor("D:\\Tools\\nodejs")
        assert node_runtime._has_root_anchor("\\\\server\\share\\nodejs")


@pytest.mark.skipif(os.name == "nt", reason="POSIX empty PATH segment and runtime probe cache regression")
def test_command_environment_empty_path_segment_and_hook_node_probe_dedup(tmp_path, monkeypatch):
    from scripts.workbench import node_runtime, vendor_react
    from scripts.workbench.node_runtime import NodeProbeError, select_node_runtime

    def write_exe(path: Path, body: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
        return path

    # 1. POSIX empty PATH segment in command_environment matches between fingerprint and child execution.
    parent_dir = tmp_path / "git_parent"
    child_repo = parent_dir / "child_repo"
    parent_git = write_exe(parent_dir / "git", '#!/bin/sh\necho "git version 1.1.0"\n')
    write_exe(child_repo / "git", '#!/bin/sh\necho "git version 2.2.0"\n')
    with monkeypatch.context() as patch_ctx:
        patch_ctx.chdir(parent_dir)
        patch_ctx.setenv("PATH", ":/usr/bin:/bin")
        lg_fp._RUNTIME_FINGERPRINT_CACHE.clear()
        cmd_env = lg_fp.command_environment({})
        fp = lg_fp.fingerprint_environment(
            ("git_executable_realpath", "git_version"), environment=cmd_env, repo_root=str(child_repo)
        )
        raw = runner._run_command(
            GateContext(str(child_repo)), "git_probe", ["git", "--version"], capture_output=True, environment=cmd_env
        )
    assert fp["values"] == {
        "git_executable_realpath": os.path.realpath(str(parent_git)),
        "git_version": "git version 1.1.0",
    }
    assert raw["returncode"] == 0 and raw["stdout"].strip() == "git version 1.1.0"

    # 2. Partial env omitting PATH incorporates live process PATH into resolve_cached_node_runtime cache key.
    empty_home = tmp_path / "empty_home"
    empty_home.mkdir()
    node_a = write_exe(tmp_path / "bin_a/node", '#!/bin/sh\necho "v20.11.1"\n')
    node_b = write_exe(tmp_path / "bin_b/node", '#!/bin/sh\necho "v22.12.0"\n')
    partial_env = {"HOME": str(empty_home)}
    lg_fp._RUNTIME_FINGERPRINT_CACHE.clear()
    with monkeypatch.context() as patch_ctx:
        patch_ctx.delenv("WORKBENCH_NODE", raising=False)
        patch_ctx.setenv("PATH", str(node_a.parent))
        rt_a = lg_fp.resolve_cached_node_runtime(partial_env)
        patch_ctx.setenv("PATH", str(node_b.parent))
        rt_b = lg_fp.resolve_cached_node_runtime(partial_env)
    assert (rt_a.realpath, rt_a.version) == (os.path.realpath(str(node_a)), "v20.11.1")
    assert (rt_b.realpath, rt_b.version) == (os.path.realpath(str(node_b)), "v22.12.0")

    # 3. PermissionError reading ~/.nvm/versions/node preserves first PATH probe error and lets vendor_react fall back.
    nvm_versions = empty_home / ".nvm/versions/node"
    nvm_versions.mkdir(parents=True)
    bad_path_node = write_exe(tmp_path / "bad_path/node", "#!/bin/sh\nprintf 'path-probe-err\\n' >&2\nexit 23\n")
    real_listdir = os.listdir
    listdir_hits = []

    def guarded_listdir(target):
        if os.path.realpath(str(target)) == os.path.realpath(str(nvm_versions)):
            listdir_hits.append(str(target))
            raise PermissionError("nvm versions unreadable")
        return real_listdir(target)

    perm_env = {
        "PATH": str(bad_path_node.parent),
        "HOME": str(empty_home),
        "NODE_OPTIONS": "--definitely-invalid-node-option",
    }
    with monkeypatch.context() as patch_ctx:
        patch_ctx.setattr(node_runtime.os, "listdir", guarded_listdir)
        with pytest.raises(NodeProbeError, match=r"returncode 23[\s\S]*path-probe-err"):
            select_node_runtime(perm_env)
        assert len(listdir_hits) == 1
        patch_ctx.delenv("WORKBENCH_NODE", raising=False)
        patch_ctx.setenv("PATH", str(bad_path_node.parent))
        patch_ctx.setenv("HOME", str(empty_home))
        patch_ctx.setenv("NODE_OPTIONS", "--definitely-invalid-node-option")
        assert vendor_react.current_esbuild_platform_key() == vendor_react._python_esbuild_platform_key()
        assert len(listdir_hits) == 2

    # 4. Broken Node in daily_gate_cache_key probes once; full pre-push hook run probes --version and -p once each.
    source_root = Path(__file__).resolve().parents[2]
    hook_repo = tmp_path / "dedup_hook_repo"
    (hook_repo / "scripts/workbench").mkdir(parents=True)
    shutil.copyfile(source_root / ".gitignore", hook_repo / ".gitignore")
    shutil.copyfile(
        source_root / "scripts/workbench/esbuild-manifest.json",
        hook_repo / "scripts/workbench/esbuild-manifest.json",
    )
    write_exe(hook_repo / "scripts/run_daily_quality_gate.py", "#!/usr/bin/env python3\nraise SystemExit(0)\n")
    base_gate_env = checks._quality_gate_env()
    for git_args in (
        ("init",),
        ("config", "user.email", "dedup@example.invalid"),
        ("config", "user.name", "Dedup Tester"),
        ("add", ".gitignore", "scripts/workbench/esbuild-manifest.json", "scripts/run_daily_quality_gate.py"),
        ("commit", "-m", "Setup dedup hook repo"),
    ):
        subprocess.run(["git", *git_args], cwd=hook_repo, env=base_gate_env, check=True, capture_output=True)
    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=hook_repo, env=base_gate_env, check=True, capture_output=True, text=True
    ).stdout.strip()
    checks._provision_worktree_esbuild_vendor(source_root, hook_repo, environment=base_gate_env)

    broken_log = tmp_path / "broken_node.log"
    broken_node = write_exe(
        tmp_path / "broken_node",
        f"#!/bin/sh\nprintf 'probe\\n' >> {shlex.quote(str(broken_log))}\nexit 1\n",
    )
    scope_payload = {"changed_paths": ["app.py"], "scope_known": True, "reason": "test"}
    ref_contexts = [{"local_ref": "refs/heads/main", "local_sha": head_sha, "remote_ref": "refs/heads/main", "remote_sha": checks.ZERO_SHA}]
    lg_fp._RUNTIME_FINGERPRINT_CACHE.clear()
    broken_key = hooks.daily_gate_cache_key(
        hook_repo,
        sys.executable,
        scope_payload=scope_payload,
        ref_contexts=ref_contexts,
        env={**base_gate_env, "WORKBENCH_NODE": str(broken_node)},
    )
    assert broken_key["extra"]["pytest_env"]["node_executable_realpath"] == f"__missing_node__:{broken_node}"
    assert broken_log.read_text(encoding="utf-8").splitlines() == ["probe"]

    ok_log = tmp_path / "ok_node.log"
    host_plat = vendor_react._python_esbuild_platform_key()
    ok_node = write_exe(
        tmp_path / "ok_node",
        '#!/bin/sh\n'
        f'printf "%s\\n" "$1" >> {shlex.quote(str(ok_log))}\n'
        'if [ "$1" = "--version" ]; then echo "v20.11.1"; exit 0; fi\n'
        f'if [ "$1" = "-p" ]; then echo {shlex.quote(host_plat)}; exit 0; fi\n'
        'exit 1\n',
    )
    with monkeypatch.context() as patch_ctx:
        patch_ctx.setenv("WORKBENCH_NODE", str(ok_node))
        patch_ctx.setattr(checks, "project_python_executable", lambda _root: sys.executable)
        patch_ctx.setattr(
            checks,
            "_pre_push_input_for_hook",
            lambda _stream=None: checks.PrePushInput(
                [checks.PrePushRef("refs/heads/main", head_sha, "refs/heads/main", checks.ZERO_SHA)],
                True,
            ),
        )
        patch_ctx.setattr(checks, "_daily_scope_for_refs", lambda _root, _refs, *, remote_name: scope_payload)
        lg_fp._RUNTIME_FINGERPRINT_CACHE.clear()
        rc = checks.run_quality_gate(
            hook_repo, checks.argparse.Namespace(remote_name="origin", remote_url="origin", remote_ref="")
        )
    assert rc == 0
    assert ok_log.read_text(encoding="utf-8").splitlines() == ["--version", "-p"]
