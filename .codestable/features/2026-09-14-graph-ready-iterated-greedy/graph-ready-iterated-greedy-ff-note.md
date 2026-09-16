---
doc_type: feature-ff-note
feature: graph-ready-iterated-greedy
date: 2026-09-14
requirement: ""
source: .codestable/audits/2026-09-14-scheduler-algorithm-optimization-space/finding-13.md
tags: [scheduler, graph-ready, iterated-greedy, destroy-repair, elite-repair, budget]
---

> 本文保留前一阶段的历史实现和测量。当前三阶段轮转、检查点复用、解池及交期起点的决定见 `../../compound/2026-09-14-decision-graph-search-rotation-and-checkpoint.md`，接续验收见同目录 `graph-ready-iterated-greedy-acceptance.md`；下文固定剩余预算策略不再描述当前实现。历史端到端记录中的“总拖期 258 → 246”实际为加权拖期，总拖期为 199 → 183；历史回执已保留，不能冒作本次同条件基线。

## 做了什么
在图阶段精英修补之后新增"迭代贪心"阶段：对现任最优方案解码后的工序顺序，每轮拆掉几个工序（先挑拖期或关键路径上的，其余随机），把它们停到各自后继允许的最晚位置，再逐个在原位置附近一组拓扑可行的位置里按真实 SGS 解码挑最优插入位；每次解码都是完整排程，因此也同时参与现任方案的严格改进接受。原有 `candidate_construction.iterated_greedy` 只是随机拆插的批次顺序起点（审计 finding-13 指出名不副实），这次是真正以上一轮结果为父、做最优重插的迭代贪心，且作用在工序级优先决策上。

## 预算与默认策略（实测决定）
- 阶段默认只花精英修补剩下的预算（`time_share` 默认 0），并有自己的解码上限（`max_decodes` 默认 400）与迭代上限；下一次解码预计会超过截止时刻就不启动，连续 5 轮没有新决策或连续 3 轮解码全被解码器拒绝也会停止，停止原因如实上报。
- 之所以不默认从修补分时间：SMTWT 250 实例经图阶段实测（同预算、同配置跑两遍的噪声底为 4 好 / 1 差）：
  - 3 秒预算，从修补分走 30% 时间：42 好 / 177 平 / 31 差，逾期 gap 4.38 → 4.32，但总拖期略差；分走 50%：48 好 / 72 差，净负。迭代贪心在这些切片里平均只解码 7～12 次、完成不到一轮。
  - 1 秒预算（第一版实现，分走 50%）：61 好 / 70 差。
  - 默认策略（只用剩余）：1 秒 19 好 / 17 差、3 秒 8 好 / 4 差，都在噪声附近，因为短预算下修补几乎总是用满时间。
  - **生产默认 5 秒预算、默认策略：54 好 / 196 平 / 0 差**，达最优 48 → 51/250，逾期 gap 4.30 → 4.23，总拖期也略降；这时修补先撞到 60 次解码上限、留下时间，迭代贪心平均解码 13.7 次、在 53 个实例上成为胜出来源。改进只接受严格更优且未见过的输出、只花剩余预算，所以没有变差的实例。
- 步进时钟下给足 120 次解码时，wt40 第 3 个实例逾期 5 → 3、第 4 个实例总拖期改善：算法本身有效；短预算下的瓶颈是图阶段现有的预算结构（档位约占 45%、修补拿剩余、总解码上限 60）。要让它在短预算里也发力，需要单独裁决预算切分与解码上限，见"后续建议"。

## 改了哪些
- 新增 `core/services/scheduler/run/optimizer_graph_ready_iterated_greedy_contract.py`（限额解析 `graph_ready_optimization.iterated_greedy.{enabled,destruction_size,insertion_window,max_iterations,max_decodes,time_budget_ms,time_share,worse_acceptance}`，非法配置 `ValidationError(field="graph_ready_iterated_greedy")`；报告结构与公开文案）与 `optimizer_graph_ready_iterated_greedy.py`（拆修搜索、分数缓存、预算守卫、接受与上报）。
- `optimizer_graph_ready.py`：解析限额（跟随修补开关；配置错误在没有搜索时间时同样先报错），修补后调用；`time_share > 0` 时给修补设时间上限（`repair_time_ceiling_reason`）。
- `optimizer_graph_ready_repair.py`：`run_graph_ready_elite_repair(time_ceiling=...)`。
- 候选来源 `graph_ready_v2_iterated_greedy`（`optimizer_graph_ready_profiles.py`、`optimizer_candidate_comparison.py` 择优顺序、`optimizer_graph_ready_candidates.py` 决策来源校验、`optimizer_graph_ready_candidate_payload.py` 可变范围 `graph_ready_iterated_greedy`）；`operation_neighbors` / `candidate_payload` 提供公开别名 `decoded_topological_order` / `decoded_batch_order`。
- 报告：`graph_ready_optimization.iterated_greedy`（状态、停止原因、迭代与解码数、去重剪枝、拒绝原因、行走接受次数、采纳次数、父来源与分数、平均解码毫秒），attempts 里一条 `graph_ready_v2_iterated_greedy` 阶段摘要，公开 message 追加一句中文摘要。
- 测试：新增 `tests/algorithm/test_graph_ready_iterated_greedy_contract.py`（限额、插入窗口、停放、拆除、禁用、无预算、解码器全拒、真实 SMTWT 图用例的完整拓扑决策与计数、分时开关）；既有修补测试的解码计数改为"档位 + 修补"口径（`phase_calls`），迭代贪心解码单独计数（`tests/_support/optimizer_graph_ready_repair_benchmark.py`、`optimizer_graph_ready_v2_benchmark.py`、`optimizer_quality_matrix.py`），修补轮次合同在冻结时钟下显式关闭迭代贪心。

## 怎么验证的
- 见上文实测；步进时钟下 SMTWT wt40[2]：修补后 (5 逾期, 17760) → 迭代贪心 (3 逾期, 16968)，120 次解码、8 轮、3 次严格改进，全部决策拓扑合法且无重复解码。
- 端到端 20 例（`build_end_to_end_matrix`，与 k 梯子之后的快照对比）：选中方案 2 例更好（frozen_ready_external 的 min_overdue 与 min_weighted_tardiness，三个图候选都由迭代贪心把总拖期 258 → 246）、18 例相同、0 例更差。
- 质量矩阵 tiny/min_changeover：修补后 4 次换型，迭代贪心用剩余预算找到 2 次换型的排程，连续三次运行结果一致（`tests/algorithm/test_graph_repair_multiround.py` 已按实测更新锁定值）。
- 广域回归 `tests/algorithm tests/scheduler_graph tests/candidate tests/resource_dispatch tests/schedule` 加两个工作台合同文件：3855 passed（含本轮两项改动与全部合同更新）。
- 未跑全量质量门禁（用户明令），工作区含他人未提交改动，不构成 clean-worktree proof。

## 已知边界
- 停放必须按"后继先停放"的顺序做：同时拆掉一条链上的两个工序时，若先停放前驱，它会落到列表末尾、跑到自己后继的后面，随后的插入窗口下界大于上界并触发 fail-loud（端到端矩阵实跑抓到，已修并加回归测试）。
- 质量矿阵快照（`tests/_support/optimizer_quality_matrix*.py`）是精确键合同并带历史基线，本轮没有扩展其 schema：快照里的 `counts` 只记档位与修补解码，迭代贪心的解码数只在内部做一致性校验，完整数据在搜索报告的 `graph_ready_optimization.iterated_greedy` 里。
- 迭代贪心只改工序级优先决策，不写任何时间；每次解码都走正式 SGS、`compute_metrics`、`objective_score`、指纹去重与 `candidate_is_preferred`。

## 后续建议
- 预算结构是下一个真正的杠杆：`graph_ready_optimization.max_candidate_profiles=60` 是解码变快前定的，且档位/修补/迭代贪心的时间切分没有按"每次解码成本 × 想要的轮数"派生。建议单独开 cs-decide：按解码成本自适应分配三段预算，并重新校准解码上限。
- 迭代贪心目前用固定 `destruction_size=3`、`insertion_window=6`；若预算切片很短，可按剩余时间自适应缩小一轮的解码数，但要先证明小轮次仍有质量收益。
