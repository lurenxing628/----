---
doc_type: decision
status: active
created_at: 2026-09-19
slug: graph-priority-pruning-auto-assign
tags: [scheduler, sgs, auto-assign, graph-ready, decode-speed, python38]
---

# 图优先剪枝开放给自动派工工序

2026-09-19 实测生产解码（GraphReady v2 图模式）里派工键只在同图优先键组内裁决：medium 48 道工序的 4196 步中 95% 的步骤最小图键组只有 1 个候选，192 道放大夹具里是 94%，赢家 100% 落在最小组且可行。每步对全部就绪候选做自动派工探针的工作几乎都是白算的。2026-09-15 决定第 4 条把"只评最高图优先级组"限定为全固定机人输入，本决定把它开放给自动派工，排程逐位不变。用户裁决"先压解码成本"，并同意以精确剪枝替代改语义的候选窗。

1. 支配论证不依赖资源类型：最终键 = (可行性罚分, 图键…, 派工键…)。最小图键组里任一罚分为 0 的成员严格优于所有图键更大的候选，与派工键和机人对无关；同组仍完整评分；最高组全部不可行时恢复其余候选的原评分。自动派工只改变罚分的来源（截止窗口内放不下 → 1.0），罚分非 0 时本就回退全量评分。
2. 评分阶段只读。跳过更大图键组的评分不改变任何运行状态，只改变 `algo_stats["fallback_counts"]` 里自动派工尝试计数（`auto_assign_window_blocked_count` 等，按评分尝试次数计）和 `ResourceDemand` 证书诊断的触发次数；它们是诊断量，不是排程输出，公开摘要口径按"评分尝试次数"解释。
3. 静态首错保障：自动派工工序只有在缓存已认证的原生资源池下、`eligible_auto_assign_resources` 静态给出至少一台机和一个人时才被认证；无合格机/人、自动派工关闭、无资源池的输入都让剪枝 `supported=False`，走原全量路径，首错类型与文案与今天相同（`tests/algorithm/test_sgs_priority_pruning.py`）。多个候选同时含动态错误时首错顺序可能不同，与固定资源剪枝已接受的边界一致。
4. 认证来源只走评分缓存：`GraphPriorityPruning.for_cache` 从 `SgsScoreCache` 取已认证的资源池与探针合同，不从 dispatch 反向导入 auto_assign；剪枝仍只在评分缓存在位、日历可认证、评分/自动派工内部函数未被插桩时启用，插桩者看到全量评分。
5. 尾段复用维持固定资源专属：`GraphPriorityPruning.fixed_resources` 只在每道工序都写明机人时为真，`DecodeAcceleration.tail_eligible` 改用它；自动派工的需求窗口不在尾段状态比较里，不能证明后缀相同。
6. 优先堆（≥128 道且图键两两不同）随剪枝认证自动覆盖自动派工，仍要求键唯一。

验收（改前后各一次 `measure.py`，同一脏工作区）：8 个工况剪枝开/关 payload 逐位相同且与改前哈希相同；评分次数 192 道 3256→192、480 道 20180→480；解码中位耗时 192 道有界池 0.348→0.080 s、全池 0.998→0.180 s、480 道 1.649→0.207 s；基线解码（`score_enabled=False`）不变。收据 `.codestable/refactors/2026-09-19-sgs-decode-pruning-and-memo/measure-{before,after-step1}.json`。本决定更新 2026-09-15 决定第 4 条的适用范围，其余条款不变。
