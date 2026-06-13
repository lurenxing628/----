---
doc_type: decision
category: convention
date: 2026-06-13
slug: execution-fact-display-label-single-source
status: active
area: scheduler/execution-fact-display
tags: [convention, execution-fact, contract-4.10, single-source, scheduler, frontend]
---

# 决策：ExecutionFact→前端公开标签只走 execution_fact_presentation.execution_detail_meta 单源

## 一句话结论

把「现场执行事实（ExecutionFact）→ 中文公开显示标签」的映射收敛到**唯一一处实现** `core/services/scheduler/execution_fact_presentation.execution_detail_meta`；现场状态文案统一走 `core/models/operation_execution_labels.execution_status_label`。**新消费方禁内联状态文案、禁重复实现这套标签映射**。

## 背景

契约 4.10（现场事实展示契约）规定「展示只消费公开标签：actual_summary_label / actual_start_time_label / actual_end_time_label / execution_status_label」，但**没有指定这些 label 由哪一处代码产出**。结果这套「状态码/原始时间 → 中文公开标签」的映射历史上是散的：

- 甘特任务详情区有一份（原 `gantt_tasks._execution_detail_meta`，模块私有）。
- `gantt_week_plan.py` 的 `_week_plan_execution_status_cell`（窄逻辑约 :100-101）又自己拼了一个窄版本——其注释自承「与甘特详情缺省一致」（该注释现已随本次抽取更新为指向公开名 `execution_fact_presentation.execution_detail_meta`），等于**靠注释做手工对账**，一旦一方改动另一方就静默漂移。
- 2026-06-13 做 fusion-batch-detail-schedule-card（批次详情排程去向卡）时，又需要在第三处显示现场状态/实际起止——若再内联一份就是第三套口径。

「多处各拼一份、靠注释对账」正是 4.10「展示只消费公开标签」会被逐渐架空的根。

## 决定

1. **唯一实现点**：ExecutionFact → 前端公开显示标签的映射，全站只允许 `execution_fact_presentation.execution_detail_meta(fact)` 一处。fusion-batch-detail-schedule-card 已把它从 `gantt_tasks._execution_detail_meta` 抽出、去前缀公开为全站单源（只搬不改行为，由既有甘特测试做回归锚）。
2. **状态文案单源**：现场 `status → 中文`一律走 `operation_execution_labels.execution_status_label`，不在消费方内联中文字典。
3. **新消费方纪律**：任何要展示「现场干到哪了」（开工/完工/状态/实际起止）的新功能，调 `execution_detail_meta` 取公开 `*_label` / `has_execution_record`，**不得**自己重写这套映射、不得内联状态文案。
4. **viewmodel 边界**：因 viewmodel 禁 import `core.services`，fact→label 的抽取放在路由/服务层，viewmodel 只接收已算好的纯 label 字符串（不碰 ExecutionFact / rows）。

## 理由

- 重复实现这套映射会在 4.10 关键路径制造第二、第三套口径，divergence 是迟早的事——`gantt_week_plan._week_plan_execution_status_cell`（:100-101）的窄实现 + 手工对账注释已经是活教材。
- 单源后，新增消费方零成本复用、口径天然一致；改一处全站同步。
- 跨模块去 import 一个 `_`-私有函数本身是 smell；抽成公开单源模块同时解决「谁都能用」与「不暴露甘特内部」。

## 考虑过的替代方案

- **每个消费方各自内联映射**（现状的自然延续）：被拒。N 套口径迟早漂移，4.10「只消费公开标签」形同虚设。
- **跨模块直接 import `gantt_tasks._execution_detail_meta`**：被拒。import `_`私有是 smell；且 gantt_tasks 是甘特专属模块，语义上不该承载全站单源。
- **现在就加硬门禁回潮守卫测试**（仿 fusion-label-single-source 的 `test_label_single_source_contract.py`）：暂不做。当前抽取后 `execution_detail_meta` 只剩 2 个真实消费方（`gantt_tasks.py:217`、`scheduler_batch_detail.py:231`；注：此处数的是「标签映射函数」的消费方，与 acceptance 第 5 节「现场事实**取数入口** `facts_by_op_id_for_plan_rows` 有 6 处消费方」数的是两个不同函数、不矛盾）且分叉已消，软规约 + cs-feat-design 阶段自动 grep compound 撞见已足够；待消费方增多或真有人复发内联时再上门禁（见「后果」——这是显式可升级项，不是永久放弃）。

## 后果

- **正向约束**：新增「现场实际」展示类功能，起手即受本规约约束（cs-feat-design 会搜 compound 撞见本条）。
- **历史遗留特例**：`gantt_week_plan._week_plan_execution_status_cell`（:100-101）那处窄 status-label 实现功能上与单源一致、物理上独立，属本规约的可收编对象——后续若动周计划可顺手并入 `execution_detail_meta` / `execution_status_label`。**非本决定的强制改动项**，列为后续观察，避免为收编而无谓触碰稳定的周计划代码。
- **软规约非门禁**：本条在 cs-feat-design 阶段给人/AI 提醒、喂上下文，但**不会**让违规代码测试变红。绕过设计流程的热修仍可能违反；需要硬保证时再加回潮守卫测试（届时本条 status 不变，新增一条配套门禁即可）。
- **与 live 文档关系**：`ARCHITECTURE.md` 第 3 节「现场事实公开标签单源」bullet 与 roadmap `aps-frontend-fusion` 的 4.10 契约段已记同款规则——本决定是它们的「为什么 + 被拒方案 + 后果」详细版，三者应一致、不应矛盾。

## 相关文档

- `.codestable/architecture/ARCHITECTURE.md` 第 3 节「现场事实公开标签单源（契约 4.10）」bullet
- `.codestable/roadmap/aps-frontend-fusion/aps-frontend-fusion-roadmap.md` § 4.10 现场事实展示契约
- `.codestable/features/2026-06-13-fusion-batch-detail-schedule-card/`（design 2.5 识别本模式、acceptance 第 5/8 节）
- 实现：`core/services/scheduler/execution_fact_presentation.py`、`core/models/operation_execution_labels.py`
