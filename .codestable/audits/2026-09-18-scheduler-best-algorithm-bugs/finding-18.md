---
doc_type: audit-finding
audit: 2026-09-18-scheduler-best-algorithm-bugs
finding_id: performance-18
nature: performance
severity: P2
confidence: medium-high
suggested_action: cs-refactor
status: fixed
---

# Finding 18：共享槽位只收录整段落在同一认证窗口内的估算，饱和资源上几乎全部落空

## 速答

只有 `earliest <= start < end <= window[1]` 才写入共享槽位；饱和机台上后续候选的槽位都在次日以后，永远不缓存。模块头注释的定理（释放时刻在 [S,T] 内则最早可行开工相同）只依赖"可行集是子集且仍含 T"+ 日历单调，不需要恒定窗口；窗口约束只保护 `efficiency_fallback_used` 这类标志，而原生 `CalendarEngine.get_efficiency` 从不返回 None。

## 关键证据

- `core/algorithm_runtime/sgs_shared_slot.py:113-117`，模块头 3-6 行；`calendar_engine.py:266-267`。
- 实测（`/tmp/aps-audit-20260918/S1/s2_full.json` 种子 7006/7007：320 个单工序批次、同工时、单机单人、无图）：shared_slot_hits 1266 / misses 50094，日历备忘调用 2185 万次 ≈ 每次估算 425 次备忘；耗时 25.7s（全关 46.6s）。同类实例一旦有唯一图键走剪枝（7004）只要 0.15s。

## 影响

无图/并列键场景下瓶颈机台有几百个就绪候选时，每轮每候选都全量避让游走，解码 O(n²·跳数)。

## 修复方向

写入条件去掉窗口约束（保留 `_native_walk`、`abort_after_hit`、fallback 排除、`note_scan` 超集），用差分探针做等价证明；预期 7006 类实例从 25s 降到 1s 量级。

## 处理结果

2026-09-18 同日落地，且修正了本条"窗口无关"的定理：按日效率变化会让结束时刻对起始时刻非单调，所以不能完全去掉窗口，改成"同效率证书窗口链"（`sgs_shared_slot.py:52-72 constant_efficiency_span`、`:127-143`）——跨天但效率不变的槽位可以共享，效率变化或跨午夜处链断。合同测试 `tests/algorithm/test_sgs_shared_slot_saturated_resource.py`。实测饱和 7006/7007 普通日历 5.4s → 0.94s（全关 35s）；随机夜班日历仍约 25s（跨午夜与效率变化处必须断链，继续链接需改 `CalendarService.certified_slot_window` 的午夜截断语义，未动）。
