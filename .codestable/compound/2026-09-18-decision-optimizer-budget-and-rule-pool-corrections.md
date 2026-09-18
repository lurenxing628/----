---
doc_type: decision
category: architecture
date: 2026-09-18
slug: optimizer-budget-and-rule-pool-corrections
status: active
area: scheduler-optimizer
tags: [candidate-comparison, local-search, multi-start, dispatch-rule, budget, graph-ready, dedup]
---

## 背景

审计 `2026-09-18-scheduler-best-algorithm-bugs` 的 S4 子审（优化器外层：候选运行器、去重、预算、多起点、局搜、选优）实测发现一组"预算白烧"和"上报失真"问题，它们都不是解码器的问题，而是外层把预算和规则池接错了地方：

- 局搜把"每一轮"都算一次迭代，上限是 `time_budget_seconds * 20`。基线候选解码很快，约在切片一半时就撞到迭代上限收场；而其中大多数轮次是重复决策或空邻域（frozen_ready_external 基线 148 轮里 134 轮是重复），10 个批次以下的实例还完全关掉了去重，同一个邻居一轮一轮重复解码。
- 图档候选的多起点对每条注册表规则各解一次（3 次），但 SGS 的比较键是 `(penalty, *graph_key, *dispatch_key)`：图键两两不同时派工规则根本不参与决策，三次解码得到同一张排程（frozen_ready_external 四条规则哈希完全相同）。反过来，图键有并列时规则才起作用，这时又只给注册表规则、不给 ATC k 梯子。图阶段无论多起点采用了什么规则，一律用配置规则解码；`sgs-atc-k-ladder-ff-note.md` 写的"图候选可经换规则邻域到达梯子"不成立，因为图候选根本不跑局搜。
- 候选预算反馈把"上一档没改进"当成信号，把下一档切片砍半。图档权重之间的改进与否互不相关，这条规则只是把中间档饿瘦。复用兄弟方案的候选不调用 observe，上一条真实信号会漏到再下一档。
- GRASP/IG 起点按规则轮换，但它们只在 batch_order 下解码，batch_order 完全不看派工规则；轮换只让 `adopted_dispatch_rule` 报出一个从未生效的规则。`CandidatePlan.dispatch_mode` 报配置模式，而图档实际强制 sgs。
- 静默回退：去重指纹算不出来时返回 None 不说原因；编排器用 `getattr(cfg, ..., 默认值)` 复制了配置快照已有的默认；只有多起点给候选记解码耗时，GRASP/局搜的现任没有这个字段，后续 `can_afford_decode` / `guard_decoder` 等于关闭；局搜改进记录在 attempts 满 12 条后不再追加，最终采用的方案可能不在压缩后的 attempts 里。

## 决定

1. **局搜的迭代 = 解码器调用**。上限由"切片剩余时间 ÷ 现任的实测解码耗时"得出，再按 profile 窗口 `[200, 5000]` 钳制；耗时未知或没有有限截止时只用上限 5000 兜住终止。空邻域和重复决策不占解码，只累计"连续空转"，空转到 `2 × restart_after + 邻域数` 就以 `search_exhausted` 收场。`seen_hashes` 跨 restart 持久，restart 的扰动顺序若已解码过也跳过。10 个批次以下不再豁免去重。停机原因只有 `time_budget` / `iteration_limit` / `search_exhausted`，细节（解码数、重复数、上限来源、`estimated_decode_cost` 这类守卫拒绝）写进 `candidate_profile.local_search_limits` / `local_search_stop`。`derive_iteration_limits` 仍是 profile 合同的口径（`effective_max_iterations`），运行时上限以实测为准。
2. **图档规则范围按图键并列情况证明**。`graph_rule_search_scope` 读图上下文：`score_enabled` 为 True、每个工序都有同长度有限数值键、键两两不同 → 只起配置规则一个起点（`configured_only`）；有并列 → 注册表规则加 ATC k 梯子（`registry_and_ladder`），仍按离默认 k 近的先起、切片不够从远端截断；证明不了（图评分关闭、键缺失、非有限）→ 全池，并把原因写进 `multi_start_efficiency.graph_rule_scope`。
3. **图阶段沿用现任规则**。多起点采用了 sgs 规则的现任，图阶段就用它解码；没有 sgs 现任才用配置规则。来源写进 `candidate_profile.graph_phase_dispatch_rule(_source)`。
4. **预算反馈只奖励实测改进**。"上一档没改进"是中性信号，下一档保持等额切片（2026-09-12 optimizer-budget-efficiency 设计里"每个未试方案保底半份"仍然成立）；复用兄弟方案的候选调用 `observe_reused`，把上一条信号清掉，分配原因记为 `reused_sibling_no_new_signal`。
5. **规则只在 sgs 下轮换与上报**。GRASP/IG 起点在 batch_order 下只带配置规则；优化结果的 `dispatch_rule` 在采用模式不是 sgs 时一律等于配置规则；`CandidatePlan.dispatch_mode` 取优化结果实际采用的模式（图档为 sgs），复用方案沿用兄弟的模式，持久化列跟随方案。
6. **不静默**。去重改为 `certify_optimizer_inputs` 返回 `(指纹, 原因)`，账本记录 `certification`，方案带 `input_certification`（`certified` / `uncertified: <原因>`），未认证时记 warning 并在公开汇总里给出原因；编排器候选参数从配置快照直接读，缺失或空白抛 `ValidationError(field=参数名)`；GRASP/IG、局搜、restart 解出来的候选都带实测 `initial_decode_runtime_ms`（键名沿用多起点，供 `observed_decode_seconds` 消费）；局搜每次 best 改进都追加 attempts，靠最终 `compact_attempts` 保底"每种派工模式最优一条"。

## 理由

- 迭代语义改成解码后，切片里省下来的不是时间而是重复解码：基线不再在半程收场，也不再把同一个邻居解 100 多次。空转有界，无截止路径也能终止。
- 图档规则范围是可以从输入证明的，不需要猜；证明不了就保守全开并说明原因，比"图档一律只给注册表"既省又诚实。
- 砍半规则没有证据支撑（不同权重档之间的改进没有相关性），去掉它只影响中间档的切片，不影响选优逻辑。
- 一律显式上报的成本是几个字段，收益是审计能看到每条降级的原因。

## 考虑过的替代方案

- 只把迭代上限调大：仍然按轮计数，重复解码和空转照旧白烧。否决。
- 图档多起点一律全池：无并列时 8 次解码得到同一张排程，纯浪费。否决。
- 图阶段永远用配置规则：多起点找到更好的规则却不用，等于多起点白跑。否决。
- 去重失败直接 raise：候选对比可以在没有指纹的情况下正常跑（只是不能复用），失败不该阻断排产，但必须可见。否决 raise，采用带原因上报。

## 后果

- 停机原因新增 `search_exhausted`；`candidate_profile` 新增 `local_search_limits`、`local_search_stop`、`graph_phase_dispatch_rule(_source)`、`multi_start_efficiency.graph_rule_scope`，公开投影未收录的键落到 diagnostics。
- 预算分配报告的 `reason` 取值变化：`observed_no_improvement_reserve_untried` 不再出现，新增 `observed_no_improvement_neutral`、`reused_sibling_no_new_signal`，并新增 `reused_count`。
- `CandidatePlan` 新增 `input_certification`；`CandidatePlan`、状态常量与方案工厂拆到 `schedule_candidate_plan.py`，`schedule_candidate_runner.py` 继续再导出。
- 实时钟实测（budget 5 秒、5 档、min_overdue）：frozen_ready_external 基线局搜 79 次解码后见底（`search_exhausted`，重复 544 轮无一解码）；shift_pool 基线在 `estimated_decode_cost` 处停（每次解码 46 毫秒，切片只够 12 次）；frozen 图档多起点 3 次解码 → 1 次；shift_pool 图档（48 个工序 24 个不同键）开放全池。
- 端到端 20 例（`benchmark_optimizer_end_to_end.py`，真实时钟）与本轮开工前快照对比：选中方案 1 例更好、13 例相同、6 例更差（shift_pool 2 例、frozen_ready_external 4 例）。用步进时钟逐因素回退核对（图阶段规则、图档规则范围、砍半三项全部退回旧逻辑）后，两组场景的主目标分数与全修版本一致（frozen 逾期 4、shift_pool 逾期 11），说明差异来自同期并行落地的解码层/图阶段改动与真实时钟噪声，不是本轮外层改动；基线候选分数前后完全一致。发版前须在 S1/S3 改动稳定后、机器空闲时重跑端到端快照对比。

## 相关文档

- `.codestable/audits/2026-09-18-scheduler-best-algorithm-bugs/`（S4 子审）
- `.codestable/features/2026-09-14-sgs-atc-k-ladder/sgs-atc-k-ladder-ff-note.md`（已更正"图候选可达梯子"的说法）
- `.codestable/compound/2026-09-14-decision-candidate-comparability-lock-vs-rule-pool.md`
- `tests/algorithm/test_optimizer_local_search_limits_contract.py`、`tests/algorithm/test_optimizer_graph_rule_scope_contract.py`、`tests/candidate/test_scheduler_candidate_corrections_contract.py`
