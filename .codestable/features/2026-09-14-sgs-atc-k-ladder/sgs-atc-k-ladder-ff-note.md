---
doc_type: feature-ff-note
feature: sgs-atc-k-ladder
date: 2026-09-14
requirement: ""
source: .codestable/audits/2026-09-14-scheduler-algorithm-optimization-space/finding-08.md
tags: [scheduler, sgs, dispatch-rule, atc, multi-start, local-search, search-space]
---

## 做了什么
SGS 派工规则里 ATC 的参数 k 原来写死 2.0，三条规则之间切换就是全部搜索空间。现在 k 成为优化器可搜的旋钮：默认值仍是 2.0，用户配置页仍只在 slack / cr / atc 三条规则之间选；优化器内部多起点与换规则邻域在 `atc:k=<值>` 梯子（0.5、1、2、4、8、16）上搜索，采用的规则令牌如实上报到 `adopted_dispatch_rule`。

## 为什么这样定
- 250 个 SMTWT 标准实例（逾期数目标，对照 Moore-Hodgson 精确最优）上单值扫描：k=2 达最优 44/250、gap 6.82；k=6 达最优 50/250、gap 4.87；k=8 gap 4.66；k≥12 达最优率开始下滑，k→∞（WSPT）0/250。总拖期则随 k 增大单调变差（11590 → 14625）。最佳 k 随目标变化，所以不改默认值，只把它交给搜索。
- 每实例取梯子最优（best-of-k）57/250、gap 4.50，对比三规则取最优 44/250、gap 6.82。
- 图候选把图键排在规则键前面，梯子起点多半重复同一决策，所以多起点只在没有图上下文时展开梯子。（2026-09-18 更正：原文写“图候选仍可通过换规则邻域到达梯子令牌”不成立——图候选跳过局搜，换规则邻域根本不会运行，图阶段也只用配置规则解码。现已改为按图键是否并列决定规则范围：图键两两不同时规则不起作用，只起配置规则一个起点；有并列时展开注册表规则加梯子；图阶段沿用多起点采用的规则。见 `.codestable/compound/2026-09-18-decision-optimizer-budget-and-rule-pool-corrections.md`。）端到端矩阵实测显示图候选多起点解码 21 → 20，把梯子留给基线候选后不再挤占图阶段。

## 改了哪些
- `core/algorithm_contracts/dispatch_rules.py`：`DEFAULT_ATC_K`、`ATC_K_LADDER`、`DispatchRuleSpec`（规则 + k，`token` 唯一文本形式）、`parse_dispatch_rule_token`（只接受 `slack` / `cr` / `atc` / `atc:k=<正数>`，其余报错）、`as_dispatch_rule_spec`、`dispatch_rule_search_pool`（注册表规则在前、梯子按离默认值远近追加）；`DispatchInputs.atc_k`，`build_dispatch_key` 用它并拒绝非有限或非正的 k。
- `core/algorithms/greedy/schedule_params.py`、`dispatch/route.py`、`dispatch/sgs.py`、`dispatch/sgs_scoring.py`、`scheduler.py`：参数解析产出 `dispatch_rule_spec`，`used_params["dispatch_rule"]` 记录规范令牌；SGS 入口与评分同时接受枚举与规格，非法令牌抛 `ValidationError(field="dispatch_rule")`。
- `core/services/scheduler/run/optimizer_multi_start.py`（起点按搜索池展开，图上下文下只用注册表规则）、`optimizer_local_search.py`（换规则邻域用搜索池）、`optimizer_multi_start_dedup.py`（决策键用规范令牌；原来用枚举值会把 `atc:k=16.0` 与 `atc` 当成同一决策直接剪掉，这是接线时实测暴露并修掉的缺陷）。
- 测试：新增 `tests/resource_dispatch/test_dispatch_rule_spec_contract.py`（令牌语法、规格校验、k 对键的影响、搜索池、调度器解码梯子令牌与拒绝非法令牌）；`tests/algorithm/test_optimizer_multi_start_budget_integration.py`、`test_dict_cfg_contract.py`、`test_optimizer_choice_case_normalization.py`、`tests/candidate/test_scheduler_candidate_rule_pool_end_to_end.py` 的起点组合与计数改为从搜索池推导，并锁定 shift_pool 基线在步进时钟下采用 `atc:k=16.0`。

## 怎么验证的
- SMTWT 250 实例真实局搜基准（`tests/_scripts_e2e/benchmark_smtwt_localsearch.py`，sgs 派工，1 秒预算）：gap 16.16 → 4.14、211/250 改进；此前记录为 16.16 → 6.82、209/250。
- 端到端 20 例（`tests/_support/optimizer_end_to_end_runner.build_end_to_end_matrix`，与规则池修复后的快照对比）：选中方案 1 例更好（shift_pool/min_tardiness 1423.5 → 1419.5）、19 例相同、0 例更差；基线候选在 shift_pool 四个目标上都变好；总解码 3203 → 3494。
- 定向回归：`tests/algorithm tests/scheduler_graph tests/candidate tests/resource_dispatch tests/schedule` 加两个工作台合同文件，本项单独落地时 3832 passed；与迭代贪心一并完成后最终 3855 passed。
- 未跑全量质量门禁（用户明令），工作区含他人未提交改动，不构成 clean-worktree proof。

## 已知边界
- 采用的规则令牌可能是 `atc:k=4.0` 这类值；持久化列 `dispatch_rule` 仍是配置值，界面若展示规则必须取 `adopted_dispatch_rule`。
- 梯子是离散点，不做连续参数搜索；改梯子就是改合同，需要重跑 SMTWT 证据。
- 多起点在有图上下文的候选上是否展开梯子，自 2026-09-18 起由图键并列情况决定（无并列只起配置规则，有并列展开注册表加梯子），不再一律不展开。
