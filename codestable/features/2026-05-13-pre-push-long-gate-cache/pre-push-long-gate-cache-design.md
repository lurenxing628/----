---
doc_type: feature-design
feature: 2026-05-13-pre-push-long-gate-cache
requirement:
roadmap: quality-gate-long-cache
roadmap_item: pre-push-long-gate-cache
status: approved
summary: pre-push 接入已有 long gate cache
tags: [quality-gate, cache, pre-push, hook]
---

# pre-push-long-gate-cache 设计方案

> 2026-05-15 后续说明：本文记录的是 2026-05-13 的历史设计。当时的目标是让 pre-push 直接跑完整 clean gate 并接入 long gate cache。2026-05-14 之后，pre-push 默认入口已经改成 `scripts/run_daily_quality_gate.py`，最终完整门禁改由 `tools/git_hook_checks.py run-final-quality-gate` 或 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache` 手动触发。这个历史设计不代表当前 pre-push 真实入口。

## 0. 术语

- pre-push hook：本地执行 `git push` 前自动跑的检查。
- long gate cache：质量门禁里给长耗时步骤准备的本地成功缓存。
- enabled entry：已经允许复用成功缓存的门禁步骤。
- planned entry：只是规划中，当前不能复用成功缓存的门禁步骤。
- clean-worktree proof：在工作区干净时跑完整质量门禁，并且结束后工作区仍然干净，才能当作正式通过证明。
- explain 不是 proof：`--long-gate-cache-explain` 只打印本次会跑还是会复用，不执行门禁，也不能当作通过证明。

## 1. 背景

- NEXT-5/6/7 已完成，`full_test_debt`、`startup_runtime_regressions` 和 `required_regressions` 已经接入安全成功缓存。
- 2026-05-13 设计时，pre-push 仍只运行 `scripts/run_quality_gate.py --require-clean-worktree`，还没有显式传入 `--long-gate-cache`。
- 本任务只把 pre-push 接到已有 cache 入口，不改 long gate cache 的判断逻辑，也不扩大 enabled 范围。

## 2. 目标

- 保留 `--require-clean-worktree`。
- 增加 `--long-gate-cache`。
- 只复用 enabled entry：`pytest_collect_all`、`full_test_debt`、`startup_runtime_regressions`、`required_regressions`。
- 坏证据、坏日志、hash 不一致、schema 变化、repo identity 变化、runner/tooling 变化都自动重跑。

## 3. 非目标

- 不做 hook 级整体缓存。
- 不做 pre-commit 快速化。
- 不启用 NEXT-8 到 NEXT-13。
- 不加 force/explain/no-cache 到 pre-push hook。
- 不改 CI 口径。
- 不改业务代码。

## 4. 实现点

- `tools/git_hook_checks.py::run_quality_gate()`。
- `tests/test_git_hook_checks.py`。
- `README.md`。
- `开发文档/README.md`。
- roadmap/items。

## 5. 验收场景

- S1 2026-05-13 验收时的 pre-push command 包含 `--require-clean-worktree`。
- S2 2026-05-13 验收时的 pre-push command 包含 `--long-gate-cache`。
- S3 2026-05-13 验收时的 pre-push command 不包含 force/explain/no-cache。
- S4 hook 仍使用项目 `.venv` Python。
- S5 hook 仍设置 UTF-8 环境并移除 `APS_SKIP_QUALITY_GATE`。
- S6 planned entry 不会变 enabled。
- S7 README / 开发文档 enabled 口径正确。
- S8 explain 不是 proof。
- S9 手动完整重跑口径明确。
