# Finding 13：目标提交 clean gate 失败在债务台账同步

- 优先级：P1 阻塞
- 结论：`313f6528` 没有 clean-worktree proof。临时干净 worktree 上的正式门禁失败在 `scripts/sync_debt_ledger.py check`。

## 根因

债务台账里 `oversize:core-infrastructure-backup` 登记的 `current_value` 是 550，但当前扫描到的 `core/infrastructure/backup.py` 行数是 554。门禁要求台账里的自动扫描值必须和当前代码一致，因此失败。

大白话说：台账说这个大文件现在 550 行，实际代码已经 554 行，台账没有跟着更新，门禁不认这个 proof。

## 证据

- 临时 clean worktree：`/private/tmp/codex-review-313f6528-j9hgA9/wt`，HEAD 为 `313f6528ed2d42cdbe306110189623100bf962b7`，`git status --short --branch` 只显示 `## HEAD (no branch)`。
- 门禁命令：`PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 PYTHONIOENCODING=utf-8 /Users/lurenxing/GitHub/----/.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`
- 第 1-10 步通过：collect-only、full-test-debt、ruff、pyright、architecture fitness、required_regressions。
- 第 11/17 步失败：`python scripts/sync_debt_ledger.py check`
- 错误：`ERROR: oversize 条目 current_value 与当前扫描不一致：oversize:core-infrastructure-backup`
- `开发文档/技术债务治理台账.md:57-67`：`oversize:core-infrastructure-backup` 的 `current_value` 为 550，`limit` 为 500。
- `wc -l core/infrastructure/backup.py`：当前为 554 行。
- `scripts/sync_debt_ledger.py:219-222`：check 会调用 `validate_ledger_against_current_scan(ledger)`。

## 影响

- 不能宣称该提交具备 clean-worktree proof。
- 这不是测试执行环境缺包导致的失败；第二次临时门禁已经补了被忽略的 `.venv` 指向，pyright 也通过了。

## 建议

- 如果 554 行是合理现状，用受控刷新命令更新台账自动字段。
- 如果不希望扩大大文件债务，先拆分 `core/infrastructure/backup.py`，让行数重新满足或回到登记值。
- 修复后必须在最新 HEAD 上重新跑 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。
