---
doc_type: issue-fix
issue: 2026-05-25-quality-gate-timeout
path: fast-track
fix_date: 2026-05-25
status: fixed
severity: medium
root_cause_type: ci-timeout
tags:
  - github-actions
  - quality-gate
  - long-gate-cache
  - timeout
---

# quality gate GitHub Actions 超时修复记录

## 1. 问题描述

PR #7 已合并，但 GitHub 上对应的 `quality` workflow 不是测试失败，而是被取消。

证据来自 GitHub Actions：

- PR：`https://github.com/lurenxing628/----/pull/7`
- PR 头提交：`c657e59c08d1d74871bcff99923214fd8785fad0`
- workflow run：`26269048696`
- job：`quality-gate`，job id `77318418196`
- run 状态：`completed`
- run 结论：`cancelled`
- 被取消步骤：第 9 步 `执行统一质量门禁`

## 2. 根因

当时 `.github/workflows/quality.yml` 里 `quality-gate` job 仍写着：

```yaml
timeout-minutes: 15
```

PR #7 日志时间线能对上这个 15 分钟上限：

- `2026-05-22T04:49:49Z`：job 开始。
- `2026-05-22T04:51:06Z`：开始执行统一质量门禁。
- `2026-05-22T04:51:49Z`：开始跑 `full_test_debt`。
- `2026-05-22T05:04:53Z`：出现 `KeyboardInterrupt`，GitHub 输出 `The operation was canceled.`

从 job 开始到取消大约 15 分钟，说明外层 GitHub job 上限先到了。质量门禁当时还在 `full_test_debt`，没有跑到后面的步骤，所以不能把这次记录说成“远端门禁失败”，也不能说成“远端门禁已通过”。

当时 cache restore 也没有命中：

```text
Cache not found for input keys: quality-long-gate-...
```

所以这次属于冷启动或缓存不可用时，完整门禁可能超过 15 分钟；GitHub 外层超时太小。

## 3. 修复方案

本次做最小修复：

- 把 `.github/workflows/quality.yml` 的 `quality-gate.timeout-minutes` 从 `15` 调到 `45`。
- 不改正式质量门禁命令，仍是 `python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。
- 不放宽 long gate cache 证明要求。
- 不让 PR 保存缓存，仍只允许 `push` 和 `workflow_dispatch` 在完整门禁成功后保存缓存。
- 在 `tests/test_quality_workflow_cache.py` 新增配置合同测试，要求 timeout 必须大于旧的 15 分钟取消线，并且至少是 45 分钟。

这样以后如果有人把 workflow 又改回 15 分钟，局部测试会直接失败。

## 4. 改动文件清单

- `.github/workflows/quality.yml`
- `tests/test_quality_workflow_cache.py`
- `.codestable/issues/2026-05-25-quality-gate-timeout/quality-gate-timeout-fix-note.md`

## 5. 验证结果

已通过：

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_quality_workflow_cache.py`：`4 passed`
- `ruby -e 'require "yaml"; YAML.load_file(".github/workflows/quality.yml"); puts "workflow yaml ok"'`：通过
- `git diff --check -- .github/workflows/quality.yml tests/test_quality_workflow_cache.py`：通过
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check tests/test_quality_workflow_cache.py`：通过
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright tests/test_quality_workflow_cache.py`：`0 errors, 0 warnings, 0 informations`

本次验证能证明：

- workflow 不再使用 15 分钟 job 上限。
- 以后改回 15 分钟或低于 45 分钟，会被 `tests/test_quality_workflow_cache.py` 挡住。
- YAML 语法和局部测试文件质量是通过的。

本次没有声称完成：

- 没有跑完整 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。
- 由于当前主工作区已有大量本次无关的未提交修改，本次局部验证不是 clean-worktree proof。

## 6. 后续观察

下一次 GitHub Actions 跑 `quality` 时，如果 cache 仍没命中，也不应该再因为 15 分钟 job 上限被 GitHub 直接取消。

如果后续 45 分钟仍不够，问题就不是这次的 15 分钟配置错误，而是需要另开 issue 继续拆 `full_test_debt` 或优化 long gate cache 冷启动耗时。
