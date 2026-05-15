---
doc_type: issue-report
issue: chrome-headless-preflight-final-proof-blocker
status: confirmed
severity: P1
summary: Chrome headless preflight 失败会阻断 long gate cache explain/final proof
tags:
  - quality-gate
  - long-gate-cache
  - chrome
  - final-proof
---

# Chrome headless preflight final proof blocker Issue Report

## 1. 问题现象

NEXT-11 已经完成 `debt_ledger_sync` long gate success cache，但还没有拿到完整的 clean-worktree final quality gate proof。

用户提供的本地事实显示：`scripts/run_quality_gate.py --long-gate-cache-explain` 曾在缓存决策阶段被 `full_test_debt` 的 `chrome_headless_preflight` 卡住，失败类型是 `chrome_exited_before_devtools`。当前错误信息只有 `stderr_tail_hash` 一类摘要，无法直接看出 Chrome 为什么在写出 `DevToolsActivePort` 之前退出。

## 2. 复现步骤

1. 在 `fix/scheduler-public-error-contract` 分支上，保持 NEXT-11 当前代码。
2. 执行 long gate cache explain：
   `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --long-gate-cache-explain`
3. 观察到：本地曾出现 `entry_id=full_test_debt`、`runtime_key=chrome_headless_preflight`、`failure_kind=chrome_exited_before_devtools`，并且无法继续拿 clean-worktree final proof。

复现频率：本机环境相关；当前仓库事实源已记录这次 Chrome preflight blocker，但 explain 本身不是 proof。

## 3. 期望 vs 实际

**期望行为**：Chrome preflight 如果失败，错误里要给出可定位的信息；final gate 不能复用旧 success cache，也不能写新的 success cache，但可以把受影响 entry 标成 cache unavailable 后执行真实命令。

**实际行为**：strict fingerprint 失败会在缓存决策阶段直接打断 explain/final；Chrome 失败信息过少，只能看到失败类型和 stderr hash，无法判断是路径、权限、profile、DevTools 端口、sandbox 还是 Chrome 版本行为。

## 4. 环境信息

- 涉及模块 / 功能：long gate success cache、quality gate final proof、Chrome headless preflight。
- 相关文件 / 函数：`tools/long_gate_fingerprint.py::_chrome_headless_preflight()`、`scripts/run_quality_gate.py::_prepare_long_gate_cache_decisions()`。
- 运行环境：本地 macOS + APS Python 3.8 虚拟环境；CI 为 Windows + Python 3.8 + 显式 `APS_CHROME_PATH`。
- 其他上下文：NEXT-11 acceptance 明确没有完成 clean-worktree final quality gate。

## 5. 严重程度

**P1** — 这个问题不代表 NEXT-11 要回滚，但会阻塞当前 HEAD 的 final clean proof，继续做 NEXT-12 之前应先解阻。

## 备注

- 不能回滚 `debt_ledger_sync`。
- 不能启用 `architecture_fitness` 或 `quickref_vs_routes`。
- 不能把 explain、cache hit、daily gate、`debt_ledger_sync.json` 当成 clean-worktree final proof。
