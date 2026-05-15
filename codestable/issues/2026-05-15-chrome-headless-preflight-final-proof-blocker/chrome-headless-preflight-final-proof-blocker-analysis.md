---
doc_type: issue-analysis
issue: chrome-headless-preflight-final-proof-blocker
status: confirmed
root_cause_type: config
related:
  - chrome-headless-preflight-final-proof-blocker-report.md
tags:
  - quality-gate
  - long-gate-cache
  - chrome
  - false-reuse
---

# Chrome headless preflight final proof blocker 根因分析

## 1. 问题定位

| 关键位置 | 说明 |
|---|---|
| `tools/long_gate_fingerprint.py::_chrome_headless_preflight()` | strict 模式会启动 headless Chrome，等待 `DevToolsActivePort`，失败时只输出少量字段。 |
| `scripts/run_quality_gate.py::_prepare_long_gate_cache_decisions()` | enabled entry 会先算 strict fingerprint，再调用 `evaluate_reuse()`；strict fingerprint 抛错会在 explain/final 早期中断。 |
| `scripts/run_quality_gate.py::_run_quality_gate_command_plan()` | runner 只有在已有 fingerprint 和完整 clean proof 条件都满足后，才应写 long gate success cache。 |
| `tools/long_gate_cache.py::write_success()` | 底层 success cache 写入函数需要自己挡住空 fingerprint，避免未来绕过 runner 时写出坏缓存。 |

## 2. 失败路径还原

**正常路径**：runner 读取真实 command plan → manifest 标出 enabled entry → strict fingerprint 成功 → `evaluate_reuse()` 判断复用或重跑 → final gate 执行真实命令或复用已校验成功缓存 → clean worktree 前后都干净 → 写 summary → 再写新的 success cache。

**失败路径**：runner 读取真实 command plan → `full_test_debt` strict fingerprint 触发 `chrome_headless_preflight` → Chrome 在 `DevToolsActivePort` 写出前退出 → `_chrome_headless_preflight()` 抛 `LongGateFingerprintError` → explain/final 在缓存决策阶段提前失败 → 当前 HEAD 无法补完整 final clean proof。

**分叉点**：`tools/long_gate_fingerprint.py::_chrome_headless_preflight()` 失败 payload 诊断不足；`scripts/run_quality_gate.py::_prepare_long_gate_cache_decisions()` 也没有“cache unavailable 但真实命令继续跑”的安全分支。

## 3. 根因

**根因类型**：config

**根因描述**：Chrome headless preflight 是 runtime fingerprint 的一部分，它本来是为了确认“这台机器上的 Chrome 真能启动并提供 DevTools”。这个检查失败时，不能把失败包装成成功 hash，也不能拿旧缓存冒充当前通过。但缓存只是加速手段，不是命令本身。更安全的做法是：指纹不可用时禁用该 entry 的缓存读写，明确写出失败诊断，然后执行真实命令。

**是否有多个根因**：是。

- 根因 1：Chrome preflight 失败信息太少，不能靠 `stderr_tail_hash` 排查真实原因。
- 根因 2：runner 没有 cache unavailable 分支，导致单个 runtime fingerprint error 会阻断 final gate。
- 根因 3：底层 `write_success()` 对空 fingerprint 缺少最后一道保护。

## 4. 影响面

- **影响范围**：主要影响带 `chrome_headless_preflight` env key 的 long gate entry，当前重点是 `full_test_debt`。
- **潜在受害模块**：long gate explain、final quality gate、success cache 写入、summary 输出。
- **数据完整性风险**：如果错误处理写错，可能造成 false reuse，也就是拿旧成功缓存冒充当前成功；本次修复必须明确禁止。
- **严重程度复核**：维持 P1。它阻塞 final proof，但不要求回滚 NEXT-11。

## 5. 修复方案

### 方案 A：只增强 Chrome 失败诊断

- **做什么**：在 `_chrome_headless_preflight()` 失败 payload 里补 Chrome 路径、版本、启动参数、profile、`DevToolsActivePort`、stdout/stderr tail 等字段。
- **优点**：改动小，能帮助定位本机 Chrome 问题。
- **缺点 / 风险**：final gate 仍会被 fingerprint error 提前打断，不能完成“真实命令继续跑”的解阻目标。
- **影响面**：只动 `tools/long_gate_fingerprint.py` 和测试。

### 方案 B：诊断增强 + runner cache unavailable 安全执行

- **做什么**：先增强 Chrome 失败诊断；再让 runner 在 strict fingerprint 失败时把该 entry 标成 cache unavailable，禁止读旧 success cache、禁止写新 success cache、禁止 `full_test_debt` 特殊增量，并执行真实 command。
- **优点**：既能排查 Chrome 原因，又能避免缓存优化阻断真实 final gate；同时不会造成 false reuse。
- **缺点 / 风险**：summary / explain 口径要写清楚，否则容易被误解成“跳过了 Chrome 检查”。
- **影响面**：`tools/long_gate_fingerprint.py`、`scripts/run_quality_gate.py`、`tools/long_gate_summary.py`、`tools/long_gate_cache.py` 和相关测试。

### 方案 C：调整 Chrome 启动参数

- **做什么**：根据实际 stderr 证据再考虑 `--headless`、remote debugging、sandbox、temp/profile 等参数变化。
- **优点**：如果根因确实是参数兼容问题，可以从源头修。
- **缺点 / 风险**：没有诊断证据前直接改 flags 容易把环境问题伪装成通过，还可能影响 Win7 / CI / browser smoke 口径。
- **影响面**：Chrome preflight 和 browser smoke 参数策略，风险更高。

### 推荐方案

**推荐方案 B**。它改动范围可控，优先解决“看不懂失败”和“缓存决策阻断真实命令”两个核心问题，同时用测试锁住：fingerprint error 不能进入 reuse，不能写 success cache，不能走 `full_test_debt` 增量。
