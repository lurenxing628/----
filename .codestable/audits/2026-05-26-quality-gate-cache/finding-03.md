---
doc_type: audit-finding
audit: quality-gate-cache
finding_id: finding-03
nature: performance
severity: P2
confidence: high
suggested_action: cs-refactor
status: open
created: 2026-05-26
tags: [pre-push, hook-cache, daily-gate]
---

# pre-push daily cache key 太粗，小变化会整条重跑

## 结论

pre-push 当前跑的是 daily fast gate，不是完整 clean proof。它有本地 `.git/aps-hook-cache/pre-push-daily.json`，但 key 包含 `head_sha`、`head_tree`、`git_status_short` 和 remote 信息。提交说明 amend、rebase、不同 remote ref、工作区有无关 dirty，都可能让缓存完全用不上。

## 证据

- `.pre-commit-config.yaml:28` 的 pre-push hook 是 `aps-quality-gate`。
- `.pre-commit-config.yaml:30` 入口是 `python tools/git_hook_checks.py run-quality-gate`。
- `tools/git_hook_checks.py:208` 先查 `pre_push_daily_cache_hit()`，没命中才跑 daily gate。
- `tools/git_hook_cache.py:332` daily cache key 包含 `head_sha`、`head_tree`、`git_status_short`、remote 信息和工具版本。
- `tools/git_hook_cache.py:349` 工作区不干净时直接不命中。
- `scripts/run_daily_quality_gate.py:257` 范围未知时退回全 required groups。
- `scripts/run_daily_quality_gate.py:317` 范围未知时 ruff 退回全仓。

## 风险

- 新分支第一次 push 或没有 upstream 时，容易全量跑 daily 范围。
- amend message / rebase 这种内容没变但 commit hash 变了的场景会浪费重跑。

## 建议

优先改这里：pre-push 不声明最终 proof，优化空间最大。建议让 cache key 更偏向 tree 和 daily 影响范围，并把 pre-push stdin 里的 local/remote sha 用起来。

