---
doc_type: audit-finding
audit: 2026-09-18-scheduler-best-algorithm-bugs
finding_id: quality-09
nature: quality
severity: P1
confidence: high
suggested_action: cs-refactor
status: fixed
---

# Finding 09：局搜迭代上限按配置秒数派生（09-14 finding-09 仍 open）且批次数 <10 时决策去重关闭

## 速答

`run_local_search` 用配置的 `time_budget_seconds`（5 → 200 次）派生迭代上限而不看实际分配到的切片；noop 与重复决策都计迭代；`init_seen_hashes` 在批次数小于 10 时返回 None，`should_skip_seen` 恒 False。

## 关键证据

- `core/services/scheduler/run/optimizer_local_search.py:326`；`optimizer_local_search_round.py:210-237`；`optimizer_search_state.py:118-120`。
- 实测（S4，真实时钟 5s/6 候选）：shift_pool 基线切片 833ms 只用 418ms，`stop=iteration_limit`，200 迭代 = 32 次解码 + 180 noop；frozen_ready_external（4 批）148 次解码里 134 次 `same_fingerprint`。步进时钟 tiny_improving 局搜 24 次解码 3 个不同输出。

## 影响

生产默认路径下基线候选一半切片白放弃，小实例九成解码重复。

## 修复方向

迭代上限按切片剩余时间与实测解码成本推进；noop/重复不计迭代但有有界的连续 noop 耗尽退出；去掉 10 批阈值。

## 处理结果

2026-09-18 同日落地：新模块 `optimizer_local_search_limits.py`（解码上限 = 切片剩余 ÷ 实测解码耗时，钳到 [200, 5000]，耗时未知或无截止用 5000 兜底；`restart_after = 上限//8`；`idle_round_limit = 2×restart_after + 邻域数`；停机原因 time_budget → iteration_limit → search_exhausted）与 `optimizer_local_search_restart.py`（restart 拆出，`seen_hashes` 跨 restart 持久）；`optimizer_local_search.py` 重写为"迭代 = 解码器调用，空转/重复不计"；`init_seen_hashes` 去掉 <10 豁免。实测（真实时钟 5s/5 档）：frozen_ready_external 基线 148 轮里 134 轮重复 → 79 次真实解码 + 544 轮零成本跳过、`search_exhausted` 收场；shift_pool 基线在 `estimated_decode_cost` 处停、48 轮重复零成本。合同测试 `tests/algorithm/test_optimizer_local_search_limits_contract.py`。
