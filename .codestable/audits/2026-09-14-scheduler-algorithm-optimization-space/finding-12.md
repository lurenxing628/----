---
doc_type: audit-finding
audit: 2026-09-14-scheduler-algorithm-optimization-space
finding_id: performance-12
nature: performance
severity: P1
confidence: medium
suggested_action: cs-refactor
status: open
---

# Finding 12：图候选 29% 解码后才发现重复；邻域急切构造、指纹双算、容量无记忆化；首解码给收益最低的 v1 profile

## 速答

预解码等价只能抓"排序键等价类完全相同"的 profile，实测 29 个生产 profile 预解码剪掉 8、解码 21、仍有 6 个（29%）解码后才发现同指纹；`EliteRepairPool.observe` 对每个新 v2 输出急切构造全套邻域（5000 工序约 50ms）再做 top_k 筛选，被淘汰精英的构造全废；输出指纹每候选算两遍（约 35ms）；`residual_capacity_for_operation` 对同批工序重复做日历逐日游走。另外 portfolio 首个解码固定是 v1 `balanced`，而 10-seed 基准里 v2 对 v1 是 10/0/0。

## 关键证据

- `core/services/scheduler/run/optimizer_graph_ready_predecode.py:13-30` —— 只做精确 preorder 等价。
- `core/services/scheduler/run/optimizer_graph_ready.py:307-313,396-401` —— 指纹去重在解码后。
- `core/services/scheduler/run/optimizer_graph_ready_repair.py:67-89,107-122` —— 急切构造后才筛 top_k；`:68` 与 `optimizer_graph_ready.py:398` 指纹双算。
- `core/services/scheduler/run/optimizer_graph_ready_v2_capacity.py:26-76,109-133,324-367` —— 逐日游走无 memo。
- `core/services/scheduler/run/optimizer_graph_ready_profiles.py:201` —— 首解码 v1 `balanced`；`scheduler-global-optimizer-items.yaml:291` v2 对 v1 10/0/0。
- 基线 JSON：`benchmark-ratchet-baseline.json:72-75,98-99` v1 九组 same_fingerprint 4/10；`graph-ready-v2-comparison-baseline.json` rows[4]/[5] same_fingerprint 11-12/20。

## 影响

图阶段本就预算饥饿，每一次白烧的解码都直接挤掉一个可能改进的 profile。

## 修复方向

让 SGS 输出"决策轨迹"（每步就绪集与选中工序），新候选在解码前用自己的静态键回放轨迹判定同输出；邻域构造改惰性（进入 top_k 后才 `build_repair_portfolio`）；指纹在 `evaluate` 内算一次随 payload 返回；容量计算按 (machine, operator, window, priority) 记忆化；profile 顺序改为 v2 baseline EDD/micro 优先。

## 建议动作

`cs-refactor`。
