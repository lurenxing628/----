---
doc_type: issue-fix
issue: daily-fast-gate-pre-push-roadmap-sync
status: fixed
severity: medium
root_cause_type: documentation-drift
tags:
  - quality-gate
  - pre-push
  - daily-fast-gate
  - long-gate-cache
---

# daily fast gate 与 pre-push roadmap 口径同步修复记录

## 1. 问题描述

网页端只读审核和本地复核都发现，当前代码、README 和开发文档已经把 pre-push 默认入口改成 `scripts/run_daily_quality_gate.py`，但 quality-gate-long-cache roadmap 和 NEXT-7.5 的历史 feature 记录仍把 pre-push 写成直接运行完整 clean gate + long gate cache。

这会造成一个很容易误解的问题：维护者看 README 会以为 pre-push 只是日常快门禁，看 roadmap 又会以为 pre-push 仍是完整 clean proof。两边说法同时存在，后续做 NEXT-8 到 NEXT-13 时容易把错误前提带进去。

## 2. 根因

- `2026-05-13-pre-push-long-gate-cache` 完成时，pre-push 确实接入过 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。
- 2026-05-14 后续耗时修复新增了 `scripts/run_daily_quality_gate.py`，并把 pre-push 默认入口改成日常快门禁。
- README 和开发文档已经同步了新口径，但 roadmap、items.yaml 和 NEXT-7.5 历史 feature 记录没有标清“这是历史完成项，不代表当前 pre-push 真实入口”。

## 3. 修复方案

- 不改代码，不改 hook，不改 CI，不改缓存逻辑。
- 不新增 roadmap 条目，避免打乱 NEXT-8 到 NEXT-13 的顺序。
- 保留 `pre-push-long-gate-cache` 的 `done` 历史状态，但把它写清楚：这是历史完成项，当前 pre-push 已由 daily fast gate 替代。
- 在 roadmap 中写清当前真实入口：
  - pre-push 默认运行 `scripts/run_daily_quality_gate.py`。
  - daily fast gate 不是 full-test-debt proof，也不是 clean-worktree proof。
  - 最终完整门禁和 CI 仍运行 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。
  - 当前 enabled entry 仍只有 `pytest_collect_all`、`full_test_debt`、`startup_runtime_regressions`、`required_regressions`。
- 在 NEXT-7.5 历史 design、checklist、acceptance 里追加后续说明，避免读者把 2026-05-13 的验收事实误当成当前事实。

## 4. 改动文件清单

- `.codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-roadmap.md`
- `.codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml`
- `.codestable/features/2026-05-13-pre-push-long-gate-cache/pre-push-long-gate-cache-design.md`
- `.codestable/features/2026-05-13-pre-push-long-gate-cache/pre-push-long-gate-cache-checklist.yaml`
- `.codestable/features/2026-05-13-pre-push-long-gate-cache/pre-push-long-gate-cache-acceptance.md`
- `.codestable/issues/2026-05-15-daily-fast-gate-pre-push-roadmap-sync/daily-fast-gate-pre-push-roadmap-sync-fix-note.md`

## 5. 明确没做

- 没有改 `scripts/run_quality_gate.py`。
- 没有改 `scripts/run_daily_quality_gate.py`。
- 没有改 `tools/git_hook_checks.py`。
- 没有改 `.pre-commit-config.yaml`。
- 没有启用 `architecture_fitness`、`ruff_check_full`、`pyright_gate_full`、`pyright_tools_full`、`debt_ledger_sync`、`quickref_vs_routes`。
- 没有把 `NEXT-8` 到 `NEXT-13` 改成 `in-progress` 或 `done`。
- 没有把 `--long-gate-cache-explain` 写成 proof。
- 没有声明本次改动跑过完整 clean-worktree quality gate。

## 6. 验证结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml --yaml-only`
  - 结果：通过，1 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/features/2026-05-13-pre-push-long-gate-cache/pre-push-long-gate-cache-checklist.yaml --yaml-only`
  - 结果：通过，1 passed。
- `git diff --check`
  - 结果：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_git_hook_checks.py`
  - 结果：通过，12 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_manifest.py`
  - 结果：通过，23 passed。

## 7. 后续影响

- 后续继续做 NEXT-8 时，应以“pre-push 是 daily fast gate，最终完整 proof 单独运行”为当前前提。
- CI 当前已经传入 `--long-gate-cache`，但 planned entry 不会因此复用；未来任何新 entry 进入 enabled，都要单独评估 CI 下复用证据是否可靠。
- NEXT-8 到 NEXT-13 的状态仍保持 planned，本次只是文档口径收口。
