"""回归测试：scripts/run_daily_quality_gate 的增量门禁选靶逻辑——_run_collect_only 只打印 collected_count 不泄露 nodeid 并在缺计数时判失败；pre-push ref/新分支 diff 能在无 upstream 时算出 changed_paths；_build_impact_plan 按变更路径匹配 required group、公共/未知 scope 跑全量、纯文档(含 .codestable/README/台账例外) 跳过 pytest；_build_ruff_plan 只 lint 变更的 Python 文件、公共配置或未知范围跑全量；_commands 保持 block-artifacts→ruff→impact→focused 的命令顺序。"""

from __future__ import annotations

import subprocess
import sys

import scripts.run_daily_quality_gate as daily_gate


def _patch_required_scope(monkeypatch, groups, common_policy=None) -> None:
    monkeypatch.setattr(daily_gate, "iter_required_regression_groups", lambda: groups)
    monkeypatch.setattr(
        daily_gate,
        "iter_required_regression_common_scope_policy",
        lambda: common_policy
        or {
            "input_file_scopes": [],
            "config_file_scopes": [],
            "tool_file_scopes": [],
            "dependency_file_scopes": [],
            "env_keys": [],
        },
    )


def _git(repo_root, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _init_repo(repo_root) -> None:
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "test@example.invalid")
    _git(repo_root, "config", "user.name", "Test User")


def _commit_all(repo_root, message: str) -> str:
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-q", "-m", message)
    return _git(repo_root, "rev-parse", "HEAD")


def test_collect_only_success_prints_count_without_raw_nodeids(monkeypatch, capsys) -> None:
    def fake_run(command, **kwargs):
        assert command == [sys.executable, "-m", "pytest", "--collect-only", "tests", "-q"]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="tests/test_example.py::test_example\n2307 tests collected in 1.23s\n",
            stderr="",
        )

    monkeypatch.setattr(daily_gate.subprocess, "run", fake_run)

    assert daily_gate._run_collect_only({}) == 0

    captured = capsys.readouterr()
    assert "collected_count=2307" in captured.out
    assert "tests/test_example.py::test_example" not in captured.out
    assert captured.err == ""


def test_collect_only_failure_prints_stdout_and_stderr_tail(monkeypatch, capsys) -> None:
    stdout = "\n".join(f"stdout-{index}" for index in range(45))
    stderr = "\n".join(f"stderr-{index}" for index in range(45))

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 3, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(daily_gate.subprocess, "run", fake_run)

    assert daily_gate._run_collect_only({}) == 3

    captured = capsys.readouterr()
    err_lines = captured.err.splitlines()
    assert "returncode=3" in captured.err
    assert "stdout-5" in err_lines
    assert "stdout-4" not in err_lines
    assert "stderr-5" in err_lines
    assert "stderr-4" not in err_lines


def test_collect_only_success_without_count_is_reported_as_gate_failure(monkeypatch, capsys) -> None:
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="unexpected output\n", stderr="")

    monkeypatch.setattr(daily_gate.subprocess, "run", fake_run)

    assert daily_gate._run_collect_only({}) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "did not report collected count" in captured.err
    assert "unexpected output" in captured.err


def test_pre_push_ref_diff_uses_explicit_from_to_without_upstream(monkeypatch, tmp_path) -> None:
    _init_repo(tmp_path)
    target = tmp_path / "core" / "services" / "scheduler" / "run_flow.py"
    target.parent.mkdir(parents=True)
    target.write_text("VALUE = 1\n", encoding="utf-8")
    base_sha = _commit_all(tmp_path, "base")
    target.write_text("VALUE = 2\n", encoding="utf-8")
    head_sha = _commit_all(tmp_path, "change scheduler")
    monkeypatch.setattr(daily_gate, "REPO_ROOT", str(tmp_path))

    changed = daily_gate._changed_paths(
        pre_push_from_ref=base_sha,
        pre_push_to_ref=head_sha,
        pre_push_remote_name="origin",
        pre_push_remote_ref="refs/heads/topic",
    )

    assert changed.scope_known is True
    assert changed.paths == ["core/services/scheduler/run_flow.py"]
    assert changed.reason == "pre-push ref diff"


def test_pre_push_new_branch_uses_remote_refs_without_upstream(monkeypatch, tmp_path) -> None:
    _init_repo(tmp_path)
    base = tmp_path / "README.md"
    base.write_text("base\n", encoding="utf-8")
    base_sha = _commit_all(tmp_path, "base")
    _git(tmp_path, "update-ref", "refs/remotes/origin/main", base_sha)
    target = tmp_path / "core" / "services" / "scheduler" / "run_flow.py"
    target.parent.mkdir(parents=True)
    target.write_text("VALUE = 1\n", encoding="utf-8")
    head_sha = _commit_all(tmp_path, "new branch change")
    monkeypatch.setattr(daily_gate, "REPO_ROOT", str(tmp_path))

    changed = daily_gate._pre_push_diff_paths(daily_gate._ZERO_SHA, head_sha, "origin", "refs/heads/topic")

    assert changed.scope_known is True
    assert changed.paths == ["core/services/scheduler/run_flow.py"]
    assert changed.reason == "pre-push new branch diff"


def test_daily_scope_payload_binds_changed_paths_and_targets(monkeypatch) -> None:
    monkeypatch.setattr(daily_gate, "_git_name_only", lambda _args: [])
    _patch_required_scope(
        monkeypatch,
        [
            {
                "group_id": "scheduler_run_core",
                "target_paths": ["tests/regression_scheduler_run.py"],
                "input_file_scopes": ["core/services/scheduler/**/*.py"],
                "config_file_scopes": [],
                "tool_file_scopes": [],
                "dependency_file_scopes": [],
            }
        ],
    )

    scope = daily_gate.build_daily_gate_scope(
        pre_push_changed_paths=["core/services/scheduler/run_flow.py"],
        pre_push_scope_reason="test supplied paths",
    )
    payload = daily_gate.daily_gate_scope_payload(scope)

    assert payload["scope_known"] is True
    assert payload["changed_paths"] == ["core/services/scheduler/run_flow.py"]
    assert payload["changed_paths_hash"]
    assert payload["impact_pytest"]["target_paths"] == ["tests/regression_scheduler_run.py"]
    assert payload["impact_pytest"]["target_hash"]


def test_impact_plan_selects_matching_required_group(monkeypatch) -> None:
    _patch_required_scope(
        monkeypatch,
        [
            {
                "group_id": "scheduler_run_core",
                "target_paths": ["tests/regression_scheduler_run.py"],
                "input_file_scopes": ["core/services/scheduler/**/*.py"],
                "config_file_scopes": [],
                "tool_file_scopes": [],
                "dependency_file_scopes": [],
            },
            {
                "group_id": "frontend_manual_excel",
                "target_paths": ["tests/regression_excel_hidden_payload_contract.py"],
                "input_file_scopes": ["templates_excel/**/*"],
                "config_file_scopes": [],
                "tool_file_scopes": [],
                "dependency_file_scopes": [],
            },
        ],
    )

    plan = daily_gate._build_impact_plan(
        daily_gate.ChangedPathSet(["core/services/scheduler/run_flow.py"], True, "")
    )

    assert plan.all_required_groups is False
    assert plan.selected_group_ids == ["scheduler_run_core"]
    assert plan.target_paths == ["tests/regression_scheduler_run.py"]


def test_impact_plan_runs_all_required_groups_for_common_scope(monkeypatch) -> None:
    _patch_required_scope(
        monkeypatch,
        [
            {
                "group_id": "quality_gate",
                "target_paths": ["tests/test_run_quality_gate.py"],
                "input_file_scopes": ["scripts/run_quality_gate.py"],
                "config_file_scopes": [],
                "tool_file_scopes": [],
                "dependency_file_scopes": [],
            },
            {
                "group_id": "scheduler_config",
                "target_paths": ["tests/regression_scheduler_config_route_contract.py"],
                "input_file_scopes": ["web/routes/scheduler_config.py"],
                "config_file_scopes": [],
                "tool_file_scopes": [],
                "dependency_file_scopes": [],
            },
        ],
        {
            "input_file_scopes": [],
            "config_file_scopes": ["pyproject.toml"],
            "tool_file_scopes": [],
            "dependency_file_scopes": [],
            "env_keys": [],
        },
    )

    plan = daily_gate._build_impact_plan(daily_gate.ChangedPathSet(["pyproject.toml"], True, ""))

    assert plan.all_required_groups is True
    assert plan.selected_group_ids == ["quality_gate", "scheduler_config"]
    assert plan.target_paths == [
        "tests/test_run_quality_gate.py",
        "tests/regression_scheduler_config_route_contract.py",
    ]
    assert "common quality gate scope changed" in plan.reason


def test_impact_plan_runs_all_required_groups_for_unknown_scope(monkeypatch) -> None:
    _patch_required_scope(
        monkeypatch,
        [
            {
                "group_id": "quality_gate",
                "target_paths": ["tests/test_run_quality_gate.py"],
                "input_file_scopes": ["scripts/run_quality_gate.py"],
                "config_file_scopes": [],
                "tool_file_scopes": [],
                "dependency_file_scopes": [],
            },
            {
                "group_id": "scheduler_run_core",
                "target_paths": ["tests/regression_scheduler_run.py"],
                "input_file_scopes": ["core/services/scheduler/**/*.py"],
                "config_file_scopes": [],
                "tool_file_scopes": [],
                "dependency_file_scopes": [],
            },
        ],
    )

    plan = daily_gate._build_impact_plan(daily_gate.ChangedPathSet(["core/new_area.py"], True, ""))

    assert plan.all_required_groups is True
    assert plan.selected_group_ids == ["quality_gate", "scheduler_run_core"]
    assert plan.target_paths == ["tests/test_run_quality_gate.py", "tests/regression_scheduler_run.py"]
    assert "outside known required regression scopes" in plan.reason


def test_docs_only_changes_skip_required_pytest(monkeypatch) -> None:
    _patch_required_scope(
        monkeypatch,
        [
            {
                "group_id": "quality_gate",
                "target_paths": ["tests/test_run_quality_gate.py"],
                "input_file_scopes": ["开发文档/**/*.md"],
                "config_file_scopes": [],
                "tool_file_scopes": [],
                "dependency_file_scopes": [],
            }
        ],
    )

    plan = daily_gate._build_impact_plan(daily_gate.ChangedPathSet(["开发文档/README.md"], True, ""))

    assert plan.all_required_groups is False
    assert plan.selected_group_ids == []
    assert plan.target_paths == []
    assert plan.reason == "documentation-only changed paths"


def test_governance_ledger_doc_is_not_docs_only(monkeypatch) -> None:
    _patch_required_scope(
        monkeypatch,
        [
            {
                "group_id": "quality_gate",
                "target_paths": ["tests/test_run_quality_gate.py"],
                "input_file_scopes": ["开发文档/技术债务治理台账.md"],
                "config_file_scopes": [],
                "tool_file_scopes": [],
                "dependency_file_scopes": [],
            }
        ],
    )

    plan = daily_gate._build_impact_plan(
        daily_gate.ChangedPathSet(["开发文档/技术债务治理台账.md"], True, "")
    )

    assert plan.all_required_groups is False
    assert plan.selected_group_ids == ["quality_gate"]
    assert plan.target_paths == ["tests/test_run_quality_gate.py"]


def test_codestable_only_changes_skip_required_pytest(monkeypatch) -> None:
    _patch_required_scope(
        monkeypatch,
        [
            {
                "group_id": "quality_gate",
                "target_paths": ["tests/test_run_quality_gate.py"],
                "input_file_scopes": [".codestable/**/*.yaml"],
                "config_file_scopes": [],
                "tool_file_scopes": [],
                "dependency_file_scopes": [],
            }
        ],
    )

    plan = daily_gate._build_impact_plan(
        daily_gate.ChangedPathSet([".codestable/roadmap/demo/items.yaml"], True, "")
    )

    assert plan.all_required_groups is False
    assert plan.selected_group_ids == []
    assert plan.target_paths == []
    assert plan.reason == "documentation-only changed paths"


def test_readme_only_changes_skip_required_pytest(monkeypatch) -> None:
    _patch_required_scope(
        monkeypatch,
        [
            {
                "group_id": "quality_gate",
                "target_paths": ["tests/test_run_quality_gate.py"],
                "input_file_scopes": ["README.md"],
                "config_file_scopes": [],
                "tool_file_scopes": [],
                "dependency_file_scopes": [],
            }
        ],
    )

    plan = daily_gate._build_impact_plan(daily_gate.ChangedPathSet(["README.md"], True, ""))

    assert plan.all_required_groups is False
    assert plan.selected_group_ids == []
    assert plan.target_paths == []
    assert plan.reason == "documentation-only changed paths"


def test_docs_paths_do_not_force_full_gate_for_mixed_known_changes(monkeypatch) -> None:
    _patch_required_scope(
        monkeypatch,
        [
            {
                "group_id": "quality_gate",
                "target_paths": ["tests/test_run_quality_gate.py"],
                "input_file_scopes": ["scripts/run_quality_gate.py"],
                "config_file_scopes": [],
                "tool_file_scopes": [],
                "dependency_file_scopes": [],
            },
            {
                "group_id": "scheduler_run_core",
                "target_paths": ["tests/regression_scheduler_run.py"],
                "input_file_scopes": ["core/services/scheduler/**/*.py"],
                "config_file_scopes": [],
                "tool_file_scopes": [],
                "dependency_file_scopes": [],
            },
        ],
    )

    plan = daily_gate._build_impact_plan(
        daily_gate.ChangedPathSet(["README.md", "scripts/run_quality_gate.py"], True, "")
    )

    assert plan.all_required_groups is False
    assert plan.selected_group_ids == ["quality_gate"]
    assert plan.target_paths == ["tests/test_run_quality_gate.py"]


def test_ruff_plan_targets_changed_python_files(monkeypatch) -> None:
    _patch_required_scope(monkeypatch, [])
    impact_plan = daily_gate.ImpactPlan([], [], False, "matched changed paths")

    plan = daily_gate._build_ruff_plan(
        daily_gate.ChangedPathSet(["scripts/run_daily_quality_gate.py", "README.md"], True, ""),
        impact_plan,
    )

    assert plan.all_files is False
    assert plan.target_paths == ["scripts/run_daily_quality_gate.py"]
    assert plan.reason == "changed Python files"


def test_ruff_plan_ignores_deleted_python_files(monkeypatch) -> None:
    _patch_required_scope(monkeypatch, [])
    monkeypatch.setattr(daily_gate.os.path, "isfile", lambda _path: False)
    impact_plan = daily_gate.ImpactPlan([], [], False, "matched changed paths")

    plan = daily_gate._build_ruff_plan(
        daily_gate.ChangedPathSet(["scripts/deleted_module.py"], True, ""),
        impact_plan,
    )

    assert plan.all_files is False
    assert plan.target_paths == []
    assert plan.reason == "no changed Python files"


def test_ruff_plan_runs_full_for_public_config(monkeypatch) -> None:
    _patch_required_scope(monkeypatch, [])
    impact_plan = daily_gate.ImpactPlan([], [], False, "matched changed paths")

    plan = daily_gate._build_ruff_plan(daily_gate.ChangedPathSet(["pyproject.toml"], True, ""), impact_plan)

    assert plan.all_files is True
    assert plan.target_paths == []
    assert "common static quality scope changed" in plan.reason


def test_ruff_plan_runs_full_for_unknown_range(monkeypatch) -> None:
    _patch_required_scope(monkeypatch, [])
    impact_plan = daily_gate.ImpactPlan([], [], True, "upstream not found")

    plan = daily_gate._build_ruff_plan(daily_gate.ChangedPathSet([], False, "upstream not found"), impact_plan)

    assert plan.all_files is True
    assert plan.target_paths == []
    assert plan.reason == "upstream not found"


def test_unknown_range_keeps_required_pytest_and_full_ruff(monkeypatch) -> None:
    _patch_required_scope(
        monkeypatch,
        [
            {
                "group_id": "quality_gate",
                "target_paths": ["tests/test_run_quality_gate.py"],
                "input_file_scopes": ["scripts/run_quality_gate.py"],
                "config_file_scopes": [],
                "tool_file_scopes": [],
                "dependency_file_scopes": [],
            }
        ],
    )

    changed = daily_gate.ChangedPathSet([], False, "branch diff failed")
    impact_plan = daily_gate._build_impact_plan(changed)
    ruff_plan = daily_gate._build_ruff_plan(changed, impact_plan)

    assert impact_plan.all_required_groups is True
    assert impact_plan.target_paths == ["tests/test_run_quality_gate.py"]
    assert impact_plan.reason == "branch diff failed"
    assert ruff_plan.all_files is True
    assert ruff_plan.reason == "branch diff failed"


def test_commands_keep_focused_smoke_after_impact_targets() -> None:
    ruff_plan = daily_gate.RuffPlan(["scripts/run_daily_quality_gate.py"], False, "changed Python files")
    commands = daily_gate._commands(["tests/regression_scheduler_run.py"], ruff_plan)

    labels = [label for label, _command in commands]
    assert labels == [
        "block staged runtime artifacts",
        "ruff check changed files",
        "impact pytest",
        "focused pytest",
    ]
    assert commands[1][1][-2:] == ["--", "scripts/run_daily_quality_gate.py"]
    assert "--force-exclude" in commands[1][1]
    assert commands[2][1][-1] == "tests/regression_scheduler_run.py"
    assert commands[3][1][-len(daily_gate.FOCUSED_PYTEST_NODEIDS) :] == list(daily_gate.FOCUSED_PYTEST_NODEIDS)
