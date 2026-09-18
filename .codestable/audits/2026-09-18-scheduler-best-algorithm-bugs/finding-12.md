---
doc_type: audit-finding
audit: 2026-09-18-scheduler-best-algorithm-bugs
finding_id: quality-12
nature: quality
severity: P2
confidence: high
suggested_action: cs-refactor
status: fixed
---

# Finding 12：候选预算反馈"上一档无改进→下一档减半"饿死中间档

## 速答

`_allocation_factor` 在上一个已算候选无严格改进时给下一档 0.5 倍切片，判据来自上一档而与即将跑的档无关；复用候选不 `observe`，`_last` 沿用陈旧信号。

## 关键证据

- `core/services/scheduler/run/optimizer_search_budget.py:129-130`；`schedule_candidate_runner.py:249-250`。
- 实测（S4，真实时钟 shift_pool）：w3 376ms/8 次解码、w4 463ms/12 次，w2/w5 各 1349/1366ms、38 次；w3/w4 终值 [0,10,2469,1571.5] 差于 w1/w2/w5 的 [0,10,2417.5,1451.5]。步进时钟 w4 247ms 只解 2 次得 [0,12,3910]，等分后同档得 [0,10,2523.5]。整体选中结果反馈开着反而更好（w2 拿到加成），所以是分配粗糙不是净退化。

## 影响

中间档拿不到公平的搜索机会。

## 修复方向

去掉减半，保留改进加成；复用候选的 observe 口径理顺。

## 处理结果

2026-09-18 同日落地：`optimizer_search_budget._allocation_factor` 非改进返回 1.0（`observed_no_improvement_neutral`），保留改进加成；新增 `observe_reused`，复用候选分配原因 `reused_sibling_no_new_signal`，报告含 `reused_count`；`schedule_candidate_runner` 复用分支调用它。测试 `tests/algorithm/test_optimizer_shared_budget.py` 与 `tests/candidate/test_scheduler_candidate_corrections_contract.py`。
