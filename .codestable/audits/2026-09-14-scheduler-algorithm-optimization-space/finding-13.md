---
doc_type: audit-finding
audit: 2026-09-14-scheduler-algorithm-optimization-space
finding_id: quality-13
nature: quality
severity: P2
confidence: high
suggested_action: cs-issue
status: partially_fixed
---

# Finding 13：GRASP/IG 名不副实；v2 键单特征字典序；run 级预算被单次预算封顶；balanced 选优容差残留

## 速答

四条 P2 质量项合并记录：

1. **GRASP/IG**：`_grasp_order` 只是"每步从 base order 剩余前 3 个里随机取一个"，RCL 没有任何贪婪评价；`_ig_order` 随机删 3 个再随机位重插，不做最优重插、不以上一轮结果迭代；默认 5+3 = 8 次解码，等价于 8 个随机扰动起点。
2. **v2 键**：`_v2_priority_key_for_metric` 全是 `(rank01_a, rank01_b, …)` 字典序，rank 归一化是保序变换、对决策无影响；29 个 profile 只有 15 个不同输出。真正裸相加的是 v1 `_metric_bonus`，长链下游工时天然压倒其它项。
3. **预算封顶**：`optimizer_search_budget.py:30-32` 用 `min(slice_end, started_at + configured_seconds)`，用户给 60 秒 run 级预算实际每候选最多 5 秒，`time_budget_reached=False` 且无提示。
4. **balanced 选优**：健康覆盖只校验 failed_ops、主键、overdue+1、total_tardiness×1.1，min_overdue 下 weighted_tardiness 最多可差约 3.3 倍，makespan/changeover 无界。

## 关键证据

- `core/services/scheduler/run/optimizer_grasp_ig_specs.py:31-53`、`optimizer_grasp_ig_candidates.py:275`、`optimizer_candidate_profile.py:55-58`。
- `core/services/scheduler/run/optimizer_graph_ready_candidates.py:194-214,309-327,358-396`；`sgs_scoring.py:106-107`。
- `core/services/scheduler/run/optimizer_search_budget.py:30-32`、`schedule_candidate_runtime_helpers.py:81-92`、`web/routes/domains/scheduler/scheduler_run.py:47`。
- `core/services/scheduler/run/schedule_candidate_selection.py:72-90,158-172`、`schedule_candidate_health.py:96-115`、`config_field_spec.py:387`。

## 影响

各项单独影响有限，但都属于"看起来在做的事其实没做"或"用户给的资源没用上"。

## 修复方向

IG 用 best-insertion 并以上一轮结果为 parent 迭代，GRASP 的 RCL 用真实贪婪指标；v2 键改为加权 rank 复合指数 + 少数硬序，并允许个别 profile 把动态派工键放前；run 级预算存在时以其派生单候选上限并在诊断里报告截断秒数；balanced 容差扩展到目标全向量并附带分量差。

## 建议动作

`cs-issue`（预算封顶、选优容差）+ `cs-feat`（GRASP/IG、v2 键，属 roadmap）。

## 处理结果

2026-09-14 落地第 1 项里的"真正的迭代贪心"（记录见 `.codestable/features/2026-09-14-graph-ready-iterated-greedy/`）：图阶段精英修补之后新增拆修阶段，对现任方案解码后的工序顺序做"拆掉几个（先拖期/关键路径，其余随机）→ 停到最晚可行位 → 逐个按真实 SGS 解码在原位附近的拓扑可行位置里最优重插"，以上一轮结果为父迭代，每次解码都参与现任方案的严格改进接受，来源 `graph_ready_v2_iterated_greedy`。默认只花修补剩下的预算：SMTWT 250 实例经图阶段实测，从修补分走 30%/50% 时间分别是 42 好/31 差与 48 好/72 差（噪声底 4 好/1 差），切片里平均只解码 7～12 次、完成不到一轮；生产默认 5 秒预算下默认策略 54 好 / 196 平 / 0 差（达最优 48 → 51/250，gap 4.30 → 4.23），因为修补先撞到 60 次解码上限、留下时间；步进时钟给足 120 次解码时 wt40[2] 逾期 5 → 3。结论：算法有效，短预算下受现有预算结构（档位约 45%、修补拿剩余、总解码上限 60）限制，预算切分需单独裁决。原 `candidate_construction.iterated_greedy` 随机拆插起点未改名、未删除。第 2 项（v2 键字典序）、第 3 项（run 级预算封顶）、第 4 项（balanced 选优容差）仍未动。
