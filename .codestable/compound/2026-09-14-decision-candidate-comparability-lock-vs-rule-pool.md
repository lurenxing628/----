---
doc_type: decision
category: architecture
date: 2026-09-14
slug: candidate-comparability-lock-vs-rule-pool
status: active
area: scheduler-optimizer
tags: [candidate-comparison, sgs, dispatch-rule, multi-start, local-search, PR7b]
---

## 背景

工作台候选对比（PR7b，2026-05-19，`d2ee6461`）给每个候选注入 `_CandidateTrialConfigService`，把排序策略、派工模式、派工规则三张允许清单都缩成"当前配置值"单元素，目的是让候选之间只差图权重、结果可比。审计 `2026-09-14-scheduler-algorithm-optimization-space` finding-07 发现这把锁同时锁死了优化器内部的两种搜索：多起点按规则清单枚举起点，清单只剩一个值就只有一个起点；`sgs_dispatch_rule` 邻域要从清单里挑一个不同的规则，挑不到就每次返回"无可用规则"，200 次迭代全部空转仍消耗预算。六月"SGS 局搜已修"的实测直接调内层函数、没经过候选对比，所以没看到这层收窄。生产默认路径图分析开启，必然走候选对比，必然被收窄。250 个 SMTWT 实例上 atc 全是最佳或并列最佳，而生产从不试它。

## 决定

1. 候选之间的"可比性锁"只锁四项：排序策略、派工模式、目标函数、算法模式。图权重仍是候选之间唯一的实验变量。
2. SGS 派工规则池（slack / cr / atc）属于优化器内部的搜索维度，候选试跑不再收窄它。多起点对每个策略解三条规则，换规则邻域有真实候选。
3. 派工模式不解锁：图档要图权重起作用就必须是 sgs（代码已强制），换成按批次顺序就失去比较意义。
4. 排序策略暂不解锁：会让每个候选的起点数乘四到五，把预算摊薄，且没有质量证据；要放开先单独做一轮量化实验。
5. 如实上报：优化结果记录采用的派工模式与规则，候选方案带 `adopted_dispatch_rule`，公开汇总里与配置不同时同时给出 `adopted_dispatch_rule` 与 `configured_dispatch_rule`；持久化列 `dispatch_rule` 仍是配置值。工作台候选目录目前只显示名称、状态、任务数与指标，不显示任何派工规则，遗留分析页模板已不在仓库中，因此上报落在公开汇总与落库的 `summary_json` 上；日后在界面展示规则时必须取 `adopted_dispatch_rule`。

## 理由

规则池是三把锁里唯一"锁了就让搜索失效"的一把；解锁后基线候选才会试到在标准实例上普遍更好的 atc。上一轮解码提速五倍以上，多出的预算若邻域空转只会被白烧，所以这条排在真正做迭代贪心之前。

## 考虑过的替代方案

- 全部解锁（回到 PR7b 之前）：图档可能跑成 batch_order，图权重失效；起点数暴涨，预算被摊薄。否决。
- 给 `run_local_search` / `_run_multi_start` 单独传搜索规则池，试跑清单继续收窄：多一条平行合同，语义上仍把规则池当"配置约束"，不如直接从锁里拆掉。否决。

## 后果

- 候选方案最终采用的规则可以与用户配置不同，界面或导出若展示规则必须用 `adopted_dispatch_rule`，配置值只作对照。
- 端到端实测（`tests/_support/optimizer_end_to_end_runner`，20 例）：选中方案 1 例更好、19 例相同、0 例更差；基线候选在 tiny_improving（2 逾期 → 1）与 shift_pool（总拖期 3136.5 → 2937.0）上变好。
- 换规则邻域从"必空转"变成真搜索，但只有三条规则可换、atc 参数写死（finding-08），搜索空间很快见底，下一步应把 atc 参数变成可搜旋钮再做迭代贪心。

## 相关文档

- `.codestable/audits/2026-09-14-scheduler-algorithm-optimization-space/finding-07.md`、`finding-08.md`
- `.codestable/issues/2026-09-14-candidate-trial-rule-pool/candidate-trial-rule-pool-fix-note.md`
- `tests/candidate/test_scheduler_candidate_rule_pool_end_to_end.py`、`tests/candidate/test_scheduler_candidate_runner_contract.py`
