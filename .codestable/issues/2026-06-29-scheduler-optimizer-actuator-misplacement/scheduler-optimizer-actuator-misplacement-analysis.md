---
doc_type: issue-analysis
issue: 2026-06-29-scheduler-optimizer-actuator-misplacement
status: confirmed
root_cause_type: logic
related: [scheduler-optimizer-actuator-misplacement-report.md, ../../audits/2026-06-29-scheduler-optimizer-actuator-misplacement/index.md]
tags: [scheduler, optimizer, local-search, sgs, graph-ready]
---

# 排产优化器作用点错位根因分析

## 1. 问题定位

| 关键位置 | 说明 |
|---|---|
| `core/algorithms/dispatch_rules.py:87` | SGS 的基础排序键先比较 `primary`、换型、优先级、剩余时间,再比较 `batch_order`。也就是说,批次顺序不是主按钮,只是很靠后的平局按钮。 |
| `core/algorithms/greedy/dispatch/sgs_scoring.py:71` | SGS 最终排序键还会在最前面加 `score_penalty`,进一步把 `batch_order` 往后压。 |
| `core/services/scheduler/run/optimizer_grasp_ig_candidates.py:62` | GRASP/IG 解码时固定传 `dispatch_mode="sgs"`,候选的批次顺序变化会被送进 SGS 这条低杠杆路径。 |
| `core/services/scheduler/run/schedule_optimizer.py:220` | 有图 ready 上下文时,优化器会把派工模式强制改成 `sgs`。 |
| `core/services/scheduler/run/schedule_graph_dispatch_context.py:193` | 图 ready 路径自己按图节点构造 `sort_key_by_op_id`,不是按优化候选的 `batch_order` 排。 |
| `core/algorithms/greedy/dispatch/sgs_graph.py:267` | 图 ready 队列实际按 `graph_state["sort_key_by_op_id"]` 排 ready 工序。 |

## 2. 失败路径还原

**正常路径**: 优化器提出一个候选动作,这个动作应该改变正式排产会优先使用的判断条件,正式解码后得到不同排产结果,再由 objective score 判断是否变好。

**失败路径**: 当前很多候选动作只改变 `batch_order`。进入 SGS 后,SGS 先看 `score_penalty`、`primary`、剩余时间等更靠前的值。真实实例里这些值通常已经分出胜负,所以 `batch_order` 很少有机会生效。图 ready 路径更直接,它用图自己的 ready 排序,根本不拿候选 `batch_order` 当主要排序来源。

**分叉点**: `core/services/scheduler/run/optimizer_grasp_ig_candidates.py:62` 和 `core/services/scheduler/run/optimizer_local_search.py:390` 附近。前者把 GRASP/IG 候选固定送去 SGS 解码,后者按当前 best 的派工模式继续局搜。如果当前 best 是 SGS,但邻域仍只改批次顺序,局搜就会原地空转。

## 3. 根因

**根因类型**: 逻辑错误。

**根因描述**: 搜索动作和正式派工模式没有对齐。`batch_order` 对 `batch_order` 派工模式是主按钮,但对 SGS 只是末位附近的平局按钮。系统现在把同一套批次顺序邻域同时投给 `batch_order` 和 SGS,导致 `batch_order` 路径有效、SGS 路径无效。图 ready 路径又额外绕过了候选批次顺序,所以图路径也不该展示这类邻域为有效。

**是否有多个根因**: 是。

- 主根因: SGS 路径使用了不适合 SGS 的候选动作。
- 次根因: GRASP/IG 强制用 SGS 解码,没有按候选实际作用点选择解码模式。
- 次根因: 图 ready 路径没有把批次顺序当核心输入,但仍可能承接批次顺序邻域的“有效”说法。

## 4. 影响面

- **影响范围**: 默认优化路径、图 ready 候选、GRASP/IG 候选、VNS/局搜路径都会受影响。
- **潜在受害模块**: `schedule_optimizer.py` 的候选编排、`optimizer_grasp_ig_candidates.py` 的解码、`optimizer_local_search.py` 的局搜、`optimizer_neighborhood_moves.py` 的业务邻域、图 ready 排序相关模块。
- **数据完整性风险**: 暂未看到会写坏数据,主要风险是优化预算空烧和优化报告误导。
- **严重程度复核**: 维持 P0。实测 `sgs` 局搜 250 个实例改进 0 个,而规则切换轻量实测中前 60 个 SMTWT 实例有 58 个能通过 `slack/cr/atc` 规则差异找到更好 SGS 解码结果,说明 SGS 本身有可优化空间,只是当前动作没打中。

## 5. 修复方案

### 方案 A: 给 SGS 增加专属邻域,同时保留 batch_order 路径

- **做什么**: 在局搜候选里区分派工模式。`batch_order` 模式继续使用批次顺序邻域;`sgs` 模式新增能真正改变 SGS 选择结果的动作,第一步先做 `dispatch_rule` 切换邻域,例如在 `slack`、`cr`、`atc` 之间尝试。候选解码时把 move 携带的 `dispatch_rule` 传给正式 `GreedyScheduler.schedule`。
- **优点**: 直接打中 P0 根因,有轻量实测支撑;改动比重写 SGS 打分小;能让 `benchmark_smtwt_localsearch.py` 的 `sgs` 改进数从 0 提升到大于 0。
- **缺点 / 风险**: 需要扩展 `NeighborhoodMove` 或局搜候选上下文,让 move 可以携带 `dispatch_rule` 变更;测试要覆盖报告字段和公开输出不泄漏内部细节。
- **影响面**: 主要改 `optimizer_neighborhood_moves.py`、`optimizer_neighborhood_registry.py`、`optimizer_local_search.py`、`optimizer_local_search_candidate_eval.py` 和相关测试。

### 方案 B: 让 GRASP/IG 按候选实际派工模式解码

- **做什么**: 取消 GRASP/IG 的固定 `dispatch_mode="sgs"`。当候选来自批次顺序搜索时,用 `batch_order` 解码;只有 SGS 专属候选才用 SGS 解码。
- **优点**: 能消除 GRASP/IG 在 `batch_order` 作用点上的空烧,并补上 P1 要求的 GRASP/IG 真实端到端改善测试。
- **缺点 / 风险**: 只做它不能满足 P0 的 `sgs` 改进数大于 0,因为它主要是把批次顺序候选送回正确的 `batch_order` 路径。
- **影响面**: 主要改 `optimizer_grasp_ig_candidates.py`、`schedule_optimizer.py` 和 GRASP/IG 合同测试。

### 方案 C: 图 ready 路径禁用批次顺序邻域,只允许图语义邻域

- **做什么**: 当 `graph_ready_context` 存在时,不再把批次顺序邻域标成有效;图路径只允许未来的图语义 move,比如关键路径节点权重、影响面节点优先级这类真正进入 `sort_key_by_op_id` 的维度。
- **优点**: 不硬塞 `batch_order` 到图排序里,避免破坏图 ready 语义;能把报告从“伪有效”改成“明确跳过”。
- **缺点 / 风险**: 它是收敛误导,不是提升质量的主修复;单独做不能让 `sgs` benchmark 变好。
- **影响面**: 主要改 `optimizer_local_search.py`、图 ready 候选入口和搜索报告。

### 推荐方案

推荐先做 **方案 A + 方案 C**,再补 **方案 B**。

理由:

- 方案 A 是让 `sgs` 真正变好的最短路径,能直接满足 P0 的核心验收。
- 方案 C 防止图 ready 路径继续把批次顺序邻域说成有效,属于同步修正 P5。
- 方案 B 解决 GRASP/IG 的解码错位,但它本身不能让 `sgs` benchmark 变好,所以排在 A/C 之后或同批实现的第二段。

当前状态: `draft`,等待用户确认。用户确认推荐方案后,再进入 `cs-issue-fix` 实现阶段。
