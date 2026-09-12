---
title: GraphReady 多轮与工序资源邻域
status: implemented
date: 2026-09-12
scope: graph_ready_elite_repair
---

# 问题与方案

原 repair 只围绕初始 v2 elite 做一轮批次交换、插入和超期边界移动；找到改进后不会围绕新结果继续搜索。完整资源与工序决策仍由原 SGS 生成，本次不构造任何 ScheduleResult。

- 默认最多 3 轮，配置 `elite_repair.max_rounds` 严格正整数、封顶 8。每个 parent 完成其本轮有界邻居搜索后，如已严格改善全局 incumbent 且还有轮次，下一轮优先强化真实改进；所有尚未访问的 parent 和未耗尽的邻域尾部均保留，未首访 parent 优先于已访问尾部。最后一轮继续探索剩余 parent，不为不存在的下一轮提前重启；无改善且所有已选 parent 的实际邻域均已耗尽、总候选数耗尽、deadline 耗尽、达到轮数上限即停止。
- 保留既有 top_k 初始筛选与每轮活跃 elite 数量限制，超出的延期项独立排队；每轮每个 elite 最多访问 `max_neighbors_per_elite` 项（默认 8），跨轮只从已消费前缀之后继续。profile+repair 总候选上限和全局 deadline 不变，新增轮数不会重置预算。邻域构造后、正式 SGS 解码前再次检查；构造期间耗尽预算按 `budget_before_decode` 剪枝计数，不能计作真实解码。
- 先给实际存在的每个 batch 动作家族生成一个首代表，剩余 batch 与有界工序/资源邻域继续交错。只扫描 move 元数据，消费时才生成对应批序，不物化所有排列。工序邻域使用已解码机器/人员时间线上的相邻关键块，以及已解码空档前的插入位置；只移动 mutable 工序，候选优先顺序须满足 mutable DAG 拓扑约束，原始前后继与固定种子保持不变。所生成位置仅是待解码优先级，不宣称其时间可行。
- 资源邻域每次更改一个工序的合格机人组合；固定维度不能变，新选机器必须有工种资格，人员组合必须出自原 resource_pool，并遵守固定人员反向设备范围。复制工序后向真实 SGS 提供选择，不改原输入、资格池或历史种子。多轮继承先前已经接受的资源选择。
- 决策去重扩展为批次顺序、工序优先顺序、资源选择的完整三元内容；输出仍使用已有正式指纹与 improve_only。相同排程指纹、等分、劣解、不可行结果不能替换原可行方案。
- 图阶段已无总预算时，在 v2 容量特征构造前退出；profile 与 repair 配置仍先校验，错误不因超时被掩盖。
- 构造成本本身也有界：工序移动最多考察 `limit * 4` 个位置，DAG 拒绝和重复位置同样占用考察限额；不会因长链始终无合法移动而反复复制完整排列。下一轮只在确认还有轮数/时间/候选预算后才为 top_k 改进结果构建邻域，末轮和超时后的观察不构造无用邻域。

# 文件职责与联动

- `optimizer_graph_ready_repair.py`：有界轮次、elite 继承、接受与预算计数。
- `optimizer_graph_ready_repair_contract.py`：max_rounds 合同与轮次/停止原因报告。
- `optimizer_graph_ready_repair_neighbors.py`：原批次邻域与真实目标相关风险信号。
- `optimizer_graph_ready_operation_neighbors.py`：由真实资源时间线生成拓扑合法的工序候选。
- `optimizer_graph_ready_repair_portfolio.py`：交错批次、工序和资源候选；批次排列继续惰性生成。
- `optimizer_graph_ready_repair_decisions.py`：不可变候选决策、严格资源资格与输入复制。
- `optimizer_graph_ready.py`：向 profile 特征层传 objective/context，向 repair 传 context/pool，以及特征构造前的总预算检查。
- 同轮目标特征任务维护 `optimizer_graph_ready_candidates.py` / `optimizer_graph_ready_candidate_payload.py` / `optimizer_graph_ready_profile_selection.py`：接 `repair_decision`、真实 SGS、JSON-safe 决策与 decision fingerprint、`before_metrics` 回调。本记录不宣称这些文件为本子任务独占改动。

# 验证与边界

使用仓库 Python 3.8.10；不增加依赖。局部测试包括：资源资格与原输入不可变、DAG 与 seed 边界、空档/关键块来源、工序和资源选择进入真实 SGS、停机避让、决策/输出指纹变化、多轮实际改进、无改善停止、轮数/候选/deadline 上界，以及已有 repair 契约。

初版的 40 工序固定 SMTWT 样例用控制时钟验证搜索行为：1 轮相对 3 轮均保持超期数 5，后者继续找到更低的拖期分量。后续优先强化策略继续保留该样例的严格改善断言；此实验只证明多轮可真实到达进一步改善，不是性能计时、不证明同墙钟预算普遍更好。

工作区有同轮多个并行任务的未提交改动；本子任务不 commit、不跑 full gate、不做大型性能基准。这里的测试只能构成 dirty/unbound 局部验证，不能当 clean-worktree proof。

局部联合验证：`.venv/bin/python -m pytest -q tests/algorithm/test_graph_repair_deadline.py tests/algorithm/test_graph_repair_operation_neighbors.py tests/algorithm/test_graph_repair_real_decode.py tests/algorithm/test_graph_repair_decisions.py tests/algorithm/test_graph_repair_multiround.py tests/algorithm/test_optimizer_graph_ready_v2_elite_repair_neighbors.py tests/algorithm/test_optimizer_graph_ready_v2_elite_repair_contract.py` → 最终 **94 passed in 14.24s**。

本子任务产品文件与测试的 Ruff 检查通过，`git diff --check` 对本子任务修改的 tracked 文件通过。旧“同批次顺序必须去重”测试已改为校验完整实际决策，因为同一批序现在可以承载不同工序优先级或资源选择；仍要求相同完整决策不重复解码。目标评分抽取至新的 payload helper 后，计数测试跟随真实评分入口，保留每次解码都计算正式指标与目标的断言。

独立定点复核查出并闭环修正了长链失败移动的重复构造成本，并核对资源选择继承、种子/DAG、解码截止和报告计数。新增 100 工序纯链的调用计数回归：`limit=1` 时完整拓扑检查不超过 4 次；单轮执行不能为已修补候选创建下一轮邻域。旧“总预算耗尽后仍存在预建 elite”断言改为 `selected_elites==0` 且 `repair_stop_reason==time_budget`，保留零次 repair 解码、baseline 不变和截止留痕断言。

## 统一整合后的收敛

原核心矩阵曾发现中型最少换型目标由历史 12 次退化到 14 次。新特征改变了旧 v2 parent 的排序，而搜索在获得更好的资源选择后仍把剩余时间用于较旧的 elite。采用上述 `improvement_first` 顺序后，同一 10 秒、60 候选上限下达到 6 次换型，并通过原历史完整字典序比较；其余三个中型目标也通过。数据见主验收的核心矩阵记录，不把这个结果当作普遍最优或普遍提速。

第一次强化实验直接丢弃未探索旧 elite，导致原 SMTWT 严格改善回归失败；该实验未采用，最终保留旧队列和 top_k 槽位。`repair_deferred_by_improvement` 记录延期机会，不计成预算耗尽；若真正耗尽时间/候选预算，或下一轮尚未构造就耗尽时间，剩余旧空间才计入 `skipped_by_budget`。3 个边界测试先复现计数缺口再通过，真实 SGS 测试同时校验下一轮来源和总计数平衡。后续定点 **36 passed in 11.18s**；独立复核完成，未放宽候选/时间阈值。

## 已访问 elite 的尾部保留

完整入口的 `frozen_ready_external/min_tardiness` 暴露了另一个候选覆盖缺口：历史最佳为 `v2_repair_adjacent_swap`，显式批序 `[B00,B03,B02,B01]`，完整向量 `(0,171,4,285.5,135,1)`；新组合邻域先找到 `(0,171,4,308,112.5,1)` 后转向新 elite，但当前旧 elite 的未访问尾部被直接丢弃。两版共同的 `v2_edd` 和已执行批次邻域分数相同；未执行的历史赢家仍在该尾部，不能归因于时间配额或资源评分。

为 elite 保存 `decision_offset`，优先强化后继续保留当前尾部，并从游标继续生成；延期尾部只在真正终止时计入跳过空间。活跃列表每轮严格不超过 top_k，超出部分保存在独立队列。最初只保留曾延期尾部，后续 tiny 回归进一步收紧为任何真实未耗尽尾部均保留，见下文。1 秒单候选、5 秒完整比较、60 个图候选及每次 8 项访问上限均不变。临时探针仅加此游标后，三个外层图候选均恢复历史完整向量；该阶段队列版本复核也恢复，图评估从 33 次变为 45 次。原失败和因果探针保留在 `/private/tmp/aps-algorithm-implementation-20260912/a-frozen-{old,new,cursor,product,product-pending}-trace.json`，这些含探针观测的时间不作为正式性能证据。

已注册的 `test_graph_repair_multiround.py` 新增真实入口回归，用明确的测试控制时钟锁定完整向量、跨轮游标连续、每次访问不超过 8、每轮活跃数不超过 top_k、共享候选预算与生成/跳过计数守恒。`test_graph_repair_deadline.py` 用 top_k=1 覆盖新 elite 占满本轮后原尾部仍在下一轮恢复、已恢复深尾在无改善时继续排队，以及候选/时间/轮数终止时只计一次。限定三模块测试 **45 passed in 15.35s**，Ruff 与 Pyright 检查通过，独立静态复核未找到新的阻断；属于 dirty/unbound 局部验证，正式无探针重测由主线程完成。

主线程随后运行官方结构门禁，发现 `_repair_elites` 复杂度为 16，超过既有阈值 15。将“按改善顺序构造下一轮 active 与 pending、控制构造截止、计入新候选空间”整体提取至 `_prepare_next_repair_round`，循环主函数保留轮次停止与终端延期结算职责；未改阈值或基线。官方 `scan_complexity_entries` / `scan_oversize_entries` 对该产品模块与两个改动测试均返回空列表；限定三模块复跑 **45 passed in 14.17s**，Ruff、Pyright 通过。原结构未过回执保留，新增结构回执为 `/private/tmp/aps-algorithm-implementation-20260912/a-frozen-structure-refactor-scan.json`。

## 动作家族与特征语义覆盖

后续完整入口 D 的 `shift_pool` 暴露限时家族覆盖问题。旧第三类 `tardy_boundary_move` 被每个 batch 之后插入的 extras 推迟；同一旧 decision 在新 decoder 精确复现旧 payload，因此按动作家族保留各自首代表，再交错余下 batch/extras。前缀按实际 kind 去重挑选，不依赖 case 名或“第三个赢家”；不同家族可能产生相同 decision，仍交给现有完整决策去重，不虚报不同解。每个原始 move 只生成一次，默认前 8 项仍给新增工序/资源动作机会。

E 为基础整批排序与增强后继排序提供明确 `profile.feature_basis` 和 `select_profile_metrics`。repair 必须使用所属 profile 的同一套特征，否则恢复基础父解后仍可能用增强 saveability/sacrifice 生成不同边界动作。top_k 按不同父排程计数，同父排程的 basis 变体共享一个 slot，只保存各自 profile 与邻域元数据，不重复保存大排程。初始选择在原 top_k 内覆盖实际 basis 的最佳 parent，其余槽位按原完整分数填充；top_k=1 只能保留一个父排程，该父排程可以携带多个 basis。变体入池身份仍为 `(feature_basis, output_fingerprint)`；未经跨 basis 等价证明，repair 决策仅在同 basis 内按完整 `RepairDecision` 去重。输出指纹和正式分数比较不变。

已有测试模块补充家族前缀惰性生成、每个 move 恰好一次、extras 相对顺序和继承资源不变；基础/增强 top_k 槽位、同 parent 不同 basis 均可入池、同 basis 重复仍被去重，以及实际送给邻域的特征选择。成本预留细节和限定探针数值记录在同轮 `optimizer-budget-efficiency` 验收中；正式无探针全量验收仍由主线程运行。

## resume2：不同父排程名额与真正耗尽

resume1 完整入口 20 例比较已通过，但核心 `tiny/min_changeover` 的完整向量由旧 `(0,4,2,12,12,26)` 变为 `(0,4,2,12,16,26)`。精确 trace 确认旧赢家来自 `v2_min_slack` parent 的 `tardy_boundary_move`，批序 `[B02,B01,B00,B03]`。新 EDD 与增强 type_group 的父排程指纹相同，却因不同 basis 占了两个名额，挤掉 min_slack；只延续原 top3 尾部仍不能恢复赢家。按不同 parent 选槽的临时反事实恢复旧向量，随后采用上述共享 slot 表示保留全部 basis 元数据。

一个 parent 内的各变体轮转生成，所有变体合计每次最多 8 项；变体不是额外的 top_k 名额。接受改进后把该 parent 的 basis 元数据带到后续邻域。任何尚未耗尽的有限候选流都进入 pending，`no_improvement` 不再用于“只看了前 8 项但仍有尾部”的情况；未首访 parent 在 pending 中优先，避免多个 basis 的尾部抢光原父解的首次机会。3 轮、60 总解码、deadline 和每轮 top_k 均不扩大。

真 tiny 合同恢复完整 `(0,4,2,12,12,26)`，并锁住首轮零改善、后续轮真实改善、不同 parent 名额、跨 basis 不误剪、每 visit 合计不超过 8 和总解码不超过 60。原 SMTWT 的多轮严格改善合同同时保留。六个受影响既有测试模块 **156 passed in 15.94s**；限定 shift_pool 三目标及 frozen/minT 探针均保持原已达标向量。探针在 `/private/tmp/aps-algorithm-implementation-20260912/a-*-resume2-trace.json`，仍不代替主线程无探针正式验收。
