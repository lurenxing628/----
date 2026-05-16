---
doc_type: feature-acceptance
feature: 2026-05-13-pre-push-long-gate-cache
requirement:
roadmap: quality-gate-long-cache
roadmap_item: pre-push-long-gate-cache
status: accepted
accepted_at: 2026-05-13
tags: [quality-gate, cache, pre-push, hook]
---

# pre-push-long-gate-cache 验收记录

## 1. 验收结论

> 2026-05-15 后续说明：下面的验收结论只代表 2026-05-13 这个 feature 完成时的历史事实。后续 2026-05-14 的耗时修复已经把 pre-push 默认入口改成 `scripts/run_daily_quality_gate.py`。当前 pre-push 只是日常快门禁，不声明 full-test-debt proof，也不声明 clean-worktree proof；最终完整门禁仍通过 `tools/git_hook_checks.py run-final-quality-gate` 或 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache` 运行。

- 2026-05-13 验收时，pre-push hook 通过 `tools/git_hook_checks.py` 调用 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。
- 2026-05-13 验收时保留 `--require-clean-worktree`。
- 没有加入 force/explain/no-cache。
- 没有启用 NEXT-8 到 NEXT-13。

## 2. 改动范围

- `tools/git_hook_checks.py`
- `tests/test_git_hook_checks.py`
- `README.md`
- `开发文档/README.md`
- roadmap/items
- 本 feature 文档

## 3. enabled / planned 边界

enabled:

- `pytest_collect_all`
- `full_test_debt`
- `startup_runtime_regressions`
- `required_regressions`

planned:

- `architecture_fitness`
- `ruff_check_full`
- `pyright_gate_full`
- `pyright_tools_full`
- `debt_ledger_sync`
- `quickref_vs_routes`

## 4. 验证命令

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_git_hook_checks.py`
  - 结果：通过，11 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_run_quality_gate.py tests/test_long_gate_cache.py tests/test_long_gate_manifest.py tests/test_long_gate_summary_output.py`
  - 结果：通过，156 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_cli_controls.py tests/test_long_gate_full_test_debt_cache.py tests/test_long_gate_startup_regression_cache.py tests/test_long_gate_required_regression_cache.py`
  - 结果：通过，207 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --long-gate-cache-explain`
  - 结果：通过；`pytest_collect_all`、`full_test_debt`、`startup_runtime_regressions`、`required_regressions` 是 enabled；`architecture_fitness`、`ruff_check_full`、`pyright_gate_full`、`pyright_tools_full`、`debt_ledger_sync`、`quickref_vs_routes` 仍是 planned。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check tools/git_hook_checks.py tests/test_git_hook_checks.py`
  - 结果：通过，All checks passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright tools/git_hook_checks.py tests/test_git_hook_checks.py`
  - 结果：通过，0 errors, 0 warnings, 0 informations；pyright 提示有新版本，但本仓库仍固定使用 1.1.406。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml`
  - 结果：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/features/2026-05-13-pre-push-long-gate-cache/pre-push-long-gate-cache-checklist.yaml`
  - 结果：通过。
- `git diff --check`
  - 结果：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree`
  - 结果：通过；完整 13 步质量门禁全部通过，最后输出“质量门禁通过”。其中 full-test-debt 收集 2303 个测试且无未登记失败，required regressions 1162 passed，startup runtime regressions 125 passed，quickref vs routes 输出 OK。后续如果再 amend 提交，必须重新运行同一条命令。

## 5. 风险与回滚

- 如果 pre-push 接入 cache 后出问题，移除 `tools/git_hook_checks.py` command 中的 `--long-gate-cache` 即可。
- 不需要回滚 NEXT-5/6/7 的 long gate cache 能力。
- 当前 pre-push 已经被后续 daily fast gate 入口替代；这份验收记录不能当作当前 HEAD 的 clean-worktree proof，也不能证明当前 pre-push 仍直接跑完整 clean gate。
