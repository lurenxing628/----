---
doc_type: roadmap
slug: aps-three-gap-directions
status: active
created: 2026-05-25
last_reviewed: 2026-05-27
tags: [aps, scheduler, delay-diagnosis, candidate-comparison, shop-floor-feedback, execution-facts, win7]
related_requirements:
  - gantt-readonly-result-view
  - schedule-delay-diagnosis
  - candidate-comparison-business-view
  - shop-floor-execution-feedback
related_architecture: [ARCHITECTURE, ui-gantt]
related_compound: [aps-three-gap-directions]
related_audits: [aps-market-gap]
---

# APS 三个差距方向局部路线图

## 1. 背景

这份 roadmap 是从 `.codestable/compound/2026-05-23-explore-aps-three-gap-directions.md` 拆出来的执行规划。

原 explore 文档已经把三个方向讲得很细，但它同时承担了两件事：

- 前半部分是研究证据：当前系统有什么、外部 APS/MES 产品怎么做、哪些能力第一版不该照搬。
- 后半部分已经变成路线图草案：页面怎么放、字段怎么设计、服务和路由怎么拆、验收怎么测。

为了让后续可以直接一条一条进入 `cs-feat-design`，这里把“可以实施的路线”迁到 `.codestable/roadmap/aps-three-gap-directions/`，原 explore 文件继续保留为证据来源。

从本 roadmap 建立后，后续 feature-design 和实现都以本文件第 5 节接口契约、`aps-three-gap-directions-items.yaml` 和本目录后续更新为准。原 explore 后半段里的旧路线草案只作为历史研究材料，不再作为实现口径；其中“主要原因 / 主原因 / 根因 / primary_reason / 任意 A/B 方案对比 / `/exception` 路由 / `created_by` 可默认 system / 页面直接显示 `scenario_id`、`candidate_id`、`score tuple`、`event_type`、`source_table`”等说法全部作废。

这份 roadmap 只覆盖三个局部方向：

1. 多方案对比业务化。
2. 延期原因诊断。
3. 车间实际开工、完工、异常反馈。

它不是全项目最高优先级清单。全局优先级仍以 `.codestable/audits/2026-05-23-aps-market-gap/index.md` 为准；那份审计把甘特图调整和物料问题闭环放在更前。这里的顺序只表示“这三个方向内部怎么推进更稳”。

## 2. 范围与明确不做

### 本 roadmap 覆盖

- **公共计划身份口径**：把正式计划、候选代表方案、模拟场景预览分清楚，避免候选或 scenario 被误当成现场执行计划。
- **延期解释最小闭环**：基于现有超期清单、甘特任务、资源负荷、停机影响、关键链、物料齐套状态，输出“事实、可能原因、证据、缺口、建议动作”。
- **方案对比业务化**：把现有候选方案表升级成业务能看懂的推荐卡、三方案摘要卡、指标差值和跳转入口。
- **派工身份护栏**：资源派工页可以看正式计划、候选方案、模拟场景，但“确认派工”和“现场反馈”只能基于正式 adopted 计划。
- **车间执行事件基础**：新增现场事件和执行状态读模型，记录开工、暂停、继续、完工、报异常。
- **资源派工车间反馈入口**：在资源派工上下文里加任务卡和按钮，支持现场回填实际状态。
- **异常反馈独立拆分**：异常原因、严重程度、影响时间、影响资源、是否建议重排，单独作为一条功能，不塞进开工完工最小闭环。
- **计划和现场实际复盘**：让计划员看到计划开始/结束和现场实际开始/结束之间的偏差。
- **重排尊重执行事实**：后续重排不能随意移动已开工、暂停、已完工的现场事实；异常中要先阻止普通自动重排，提示计划员处理。
- **测试和门禁约束**：每条子 feature 都要覆盖正常、空数据、非法状态、候选/正式/场景切换、Win7 + Chrome 109 + 离线静态资源。

### 明确不做

- 不重写排程算法。
- 不把这三方向做成完整 MES。
- 不做完整 MRP、ERP/MES/WMS/PLM 集成。
- 不做 IoT 设备实时采集。
- 不做扫码枪依赖、电子签名、工资计件、完整质量追溯。
- 不做 PowerBI 或外部 BI 嵌入。
- 不做云端多人协同、消息推送、在线审批流。
- 不做“AI 自动根因”。证据不足时必须明确写“证据不足”。
- 不把所有 3/5/7 档候选都铺成大屏。第一版只承诺代表三方案。
- 不做候选方案全量明细甘特对比。
- 不让手工 scenario 直接下发给现场。scenario 只有发布成新正式版本后，才能进入派工和反馈。
- 不让车间反馈直接覆盖历史 `Schedule` 计划行。
- 不把 `BatchOperations.status` 当作现场事实的唯一来源。
- 不引入外部 CDN、外链字体、外链脚本、外链样式。
- 不升级到破坏 Python 3.8 / Win7 x64 的依赖或语法。

## 3. 当前事实和关键修正

### 3.1 候选方案现状

当前系统已经能生成多个候选方案，不是从零开始。

- `core/services/scheduler/run/schedule_candidate_specs.py:11` 支持 `3 / 5 / 7` 档候选权重。
- `core/services/scheduler/run/schedule_candidate_specs.py:49` 生成候选规格。
- `core/services/scheduler/run/schedule_candidate_selection.py:44` 从成功候选里选择方案。
- `core/services/scheduler/run/schedule_candidate_selection.py:156` 在 balanced 模式下用失败工序、超期批次、总拖期做保护。
- `schema.sql:250`、`schema.sql:282`、`schema.sql:297` 已有 `ScheduleCandidate`、`ScheduleCandidateRows`、`ScheduleCandidateSelection`。
- `web/viewmodels/scheduler_analysis_candidates.py:282` 和 `templates/scheduler/analysis_parts/_candidate_comparison.html:29` 已有方案表字段。
- `web/routes/domains/scheduler/scheduler_analysis_links.py:8` 已有设备甘特图、人员甘特图、周计划、资源排班跳转。

需要修正原 explore 里的一个旧引用：

- 原文提到 `schedule_orchestrator.py:366-404`，但当前文件没有这些行。
- 当前“运行候选比较并采用选中方案”的证据在 `core/services/scheduler/run/schedule_orchestrator.py:237`。
- 当前“把候选摘要放进 summary context”的证据在 `core/services/scheduler/run/schedule_orchestrator.py:309`。

第一版只能承诺代表三方案：

- `adopted`：正式采用方案，来源必须是正式 `Schedule`。
- `baseline_best`：原算法代表方案。
- `critical_best`：重点工序优先代表方案。

`baseline_best / critical_best` 是业务角色，不等于固定读取候选表。真正读取哪里以 `source_table` 为准：如果代表方案和正式采用方案是同一套结果，非 adopted 角色也可能解析到 `source_table=schedule`。即便如此，它们仍只能当“对比参考方案”展示，不能因此打开派工或现场反馈写入。

第一版不能承诺全部候选明细、批次级影响清单、资源级变化清单、左右甘特差异。这些都要等后续差异服务和明细持久化边界进一步明确。

### 3.2 延期解释现状

当前系统已经能判断是否超期，但还不能可靠说明“根因是什么”。

- `core/services/common/overdue_calculations.py:55` 能算已排程逾期。
- `core/services/common/overdue_calculations.py:78` 能算未排程逾期。
- `core/services/report/report_engine.py:245` 会输出 `scheduled_count` 和 `unscheduled_count`。
- `templates/reports/overdue.html:91` 现在展示批次、交期、完工/截至时间、超期时长，没有原因字段。
- `core/services/scheduler/gantt_tasks.py:157` 只是在甘特任务上标记 `is_overdue`。
- `core/services/scheduler/gantt_critical_chain.py:244` 的关键链终点是全局最晚结束任务，不是某个批次自己的根因链。
- `core/services/report/downtime_impact.py:81` 是设备级停机影响汇总，不是批次级原因结论。

所以延期解释必须写成：

- 已确认事实：比如“计划完成晚于交期 6 小时”。
- 可能原因：比如“当前数据下最明显线索是 M-03 负荷高”。
- 证据：资源负荷、停机重叠、最后工序、内部 `critical_chain` 线索、物料齐套状态。
- 缺口：比如“没有现场实际完工时间”“没有完整库存/采购链路”。
- 建议动作：去甘特图、资源派工、停机记录、物料页面核对。

不能写成：

- “根因已经定位”。
- “AI 判断一定是设备问题”。
- “物料不足导致延期”，除非当前批次确实有可追溯的齐套证据。

### 3.3 资源派工和 scenario 现状

资源派工页不是只看正式计划，它已经能看三类结果：

- 正式计划：`adopted`，通常读 `Schedule`。
- 候选代表方案：`baseline_best / critical_best`，通常读 `ScheduleCandidateRows`；如果代表方案和 adopted 是同一套结果，也可能按 `source_table=schedule` 读取，但仍按对比参考方案展示。
- 模拟场景预览：带 `scenario_id` 时，读 `ScheduleAdjustmentScenarioRow`。

证据：

- `core/services/scheduler/resource_dispatch_service.py:271` 把 `version / plan_role / scenario_id` 传进结果解析。
- `data/repositories/schedule_plan_query_repo.py:15`、`:29`、`:43` 分别读取正式、候选、场景数据。
- `templates/scheduler/resource_dispatch.html:158` 在场景预览时提示正式计划未改变。

scenario 后端能力已经比较完整：

- `schema.sql:399` 已有 draft / scenario / scenario row 相关表。
- `core/services/scheduler/gantt_adjustment_scenario_service.py:30` 保存 scenario 前会重新校验草稿。
- `core/services/scheduler/gantt_adjustment_publish_service.py:91` 发布 scenario 会分配新正式版本，写 `Schedule` 和 `ScheduleHistory`。

发布 scenario 也是“生成新正式计划”的入口。车间执行事件落地后，scenario publish 必须和普通重排一样检查 `execution_snapshot_revision`：如果用户保存 scenario 后现场已经开工、完工或状态发生变化，发布必须返回 409，不写 `Schedule` 和 `ScheduleHistory`。

但前端拖拽编辑还没有开放：

- `templates/scheduler/gantt.html:163` 显示当前为查看模式，模拟调整入口是 disabled。
- `tests/regression_gantt_adjustment_validate_simulate.py:383` 也明确校验接口可调，但没有接到甘特页面。

所以本 roadmap 不能写“拖拽甘特已经可用”。如果要把 scenario 用于派工，必须先发布成新的正式版本。

### 3.4 车间反馈现状

第 8 项完成后，当前已经有独立的车间执行事件基础，但计划行和现场事实仍然要分开看。

- `core/models/schedule.py:10` 的 `Schedule` 是计划排程行，没有实际开始/结束。
- `schema.sql:235` 的 `Schedule` 只有计划开始、计划结束、锁定状态、版本。
- `schema.sql:211` 的 `BatchOperations.status` 没有实际时间、反馈人、异常原因。
- `schema.sql:250` 的 `OperationExecutionEvents` 是现场执行事件表，只追加记录开工、完工、暂停、继续生产和报异常等现场动作。
- `data/repositories/operation_execution_event_repo.py:319` 会从执行事件聚合当前执行状态和 `state_revision`。
- `core/services/scheduler/operation_execution_feedback_service.py:284` 的 `OperationExecutionFeedbackService` 负责正式计划身份、幂等键、状态版本和合法状态流转校验。
- `core/services/scheduler/run/schedule_persistence.py:78` 正式排程会把已排上工序写成 `scheduled`。
- `web/routes/domains/scheduler/scheduler_ops.py:12` 批次工序保存路由没有传 `status`。
- `templates/scheduler/resource_dispatch.html:280` 已有资源派工现场反馈任务卡容器；第 10 项开始前，普通用户开工/完工写入仍由反馈保护开关控制，暂停、继续生产、报异常还没有作为普通用户按钮完整开放。

这意味着：

- `Schedule.start_time/end_time` 不能改成实际开工/完工。
- `Schedule.lock_status` 不能当作生产中、暂停、已完工。
- `BatchOperations.status` 不能单独承担现场事实，因为它没有事件、时间、反馈人、原因，而且正式排程也会写 `scheduled`。
- 当前执行状态必须从 `OperationExecutionEvents` 聚合，后续重排护栏和复盘视图不能回头把 `Schedule` 或 `BatchOperations.status` 当作现场事实源。

### 3.5 重排现状

当前重排主要靠冻结窗口，不是现场事实闭环。

- `core/services/scheduler/schedule_service.py:26` 只把 `completed/skipped` 当作工序终态。
- `processing` 当前仍会进入可重排范围。
- `core/services/scheduler/run/freeze_window.py:426` 从上一版 `Schedule` 行读取冻结 seed，不读取现场执行事实。
- `core/models/schedule.py:18` 注释写明 `lock_status` V1 仅占位。
- `core/services/scheduler/run/schedule_persistence.py:52` 正式排程落库没有保护现场 `processing` 状态。

所以“重排尊重执行事实”必须放在执行事件和执行状态之后做，不能提前承诺。

### 3.6 数据库和 repository 约束

新增持久化能力不能只改 `schema.sql`。

- `schema.sql:17` 已有 `SchemaVersion`。
- `core/infrastructure/migration_state.py:8` 调研时当前 schema 版本是 `14`。
- `core/infrastructure/database.py:136` 空库才执行 `schema.sql`，老库靠迁移升级。
- `core/infrastructure/migrations/__init__.py:22` 按版本注册迁移。
- `开发文档/ADR/0008-schema-version-轻量迁移.md:41` 约定每次 schema 变更要新增迁移脚本，`schema.sql` 保持最新完整定义。
- `data/repositories/base_repo.py:20` 表明 repository 是统一数据访问层。

后续 feature-design 进入实现时，要先确认当时的最新 schema 版本。如果还是 `14`，下一次 schema 改动应新增 `v15`；如果版本已经前进，就按当时版本继续递增。

## 4. 模块拆分（概设）

```text
APS 三个差距方向
├── 公共计划身份与证据协议：统一正式计划、候选方案、scenario、证据、链接、置信度
├── 延期诊断模块：把超期事实、关键链、资源、停机、物料齐套收成保守解释
├── 方案对比模块：把代表三方案讲成业务推荐、摘要卡、指标差值和钻取入口
├── 派工身份护栏：防止候选方案或 scenario 被误下发成现场执行计划
├── 执行事件基础：记录现场开工、暂停、继续、完工、异常
├── 车间反馈页面：在资源派工上下文里给现场任务卡和状态按钮
├── 异常反馈模块：单独处理异常原因、影响、处理状态和重排建议
├── 计划和现场实际复盘：展示计划时间和现场实际时间的偏差
├── 重排执行事实接入：把已开始、已暂停、已异常、已完工事实喂给排程输入
└── 测试和 Win7 约束：为每条 feature 固定正常、空数据、非法状态、离线兼容验收
```

### 公共计划身份与证据协议

- **职责**：统一 `version / plan_role / scenario_id / source_table / candidate_id` 的含义，让诊断、对比、派工、反馈都知道自己看的到底是什么。
- **承载子 feature**：`shared-plan-identity-evidence-contract`
- **触碰现有模块**：`core/models/schedule_plan_role.py`、`core/services/scheduler/schedule_plan_query_service.py`、`data/repositories/schedule_plan_query_repo.py`、`data/repositories/schedule_history_repo.py`、资源派工和分析页 viewmodel。

### 延期诊断模块

- **职责**：只读地解释超期，输出“事实 + 可能线索 + 证据 + 缺口 + 建议动作”，不改排程结果。
- **承载子 feature**：`delay-diagnosis-core-service`、`delay-diagnosis-overdue-report-entry`。
- **触碰现有模块**：`core/services/common/overdue_calculations.py`、`web/routes/reports.py`、`web/routes/report_plan_preview.py`、`core/services/report/report_engine.py`、`core/services/report/exporters/xlsx.py`、`core/services/scheduler/gantt_critical_chain_provider.py`、`templates/reports/overdue.html`。

### 方案对比模块

- **职责**：只围绕代表三方案做推荐卡、摘要卡、差值、跳转，第一版不做全候选明细大屏。
- **承载子 feature**：`candidate-recommendation-card`、`candidate-summary-delta-cards`、`candidate-drilldown-empty-states`。
- **触碰现有模块**：`web/viewmodels/scheduler_analysis_candidates.py`、`templates/scheduler/analysis_parts/_candidate_comparison.html`、`web/routes/domains/scheduler/scheduler_analysis_links.py`、`templates/scheduler/week_plan.html`、`web/routes/domains/scheduler/scheduler_week_plan.py`、`core/services/scheduler/week_plan_excel.py`。

### 派工身份护栏

- **职责**：资源派工页可以展示不同方案，但写入现场事实、确认派工、导出说明都必须清楚标识计划身份。
- **承载子 feature**：`dispatch-plan-identity-guardrails`。
- **触碰现有模块**：`core/services/scheduler/resource_dispatch_service.py`、`core/services/scheduler/resource_dispatch_excel.py`、`templates/scheduler/resource_dispatch.html`、`web/routes/domains/scheduler/scheduler_resource_dispatch.py`、`web/viewmodels/scheduler_resource_dispatch.py`、`static/js/resource_dispatch.js`。

### 执行事件基础

- **职责**：新增现场事件，作为现场实际状态的事实源。计划行继续代表“计划怎么排”，事件代表“现场怎么做”。
- **承载子 feature**：`operation-execution-event-foundation`。
- **触碰现有模块**：`schema.sql`、`core/infrastructure/migrations/`、`data/repositories/`、`core/models/`、新增执行反馈 service。

### 车间反馈页面

- **职责**：让现场人员在资源派工任务卡上做开工、完工等最小反馈。
- **承载子 feature**：`resource-dispatch-start-finish-feedback`。
- **触碰现有模块**：`templates/scheduler/resource_dispatch.html`、`static/js/resource_dispatch.js`、`web/routes/domains/scheduler/scheduler_resource_dispatch.py`。

### 异常反馈模块

- **职责**：把暂停、继续、报异常、异常类型、严重程度、影响时间、处理状态和是否建议重排单独做清楚。
- **承载子 feature**：`shop-exception-feedback`。
- **触碰现有模块**：执行事件 service、执行事件 repository、资源派工页面、`core/services/scheduler/run/schedule_input_collector.py`、`core/services/scheduler/schedule_service.py`、`core/services/scheduler/run/schedule_persistence.py`。

### 计划和现场实际复盘

- **职责**：把计划开始/结束和实际开始/结束放在同一张表里，让计划员能看到偏差。
- **承载子 feature**：`plan-vs-actual-review`。
- **触碰现有模块**：报表、资源派工、执行状态读模型。

### 重排执行事实接入

- **职责**：下次排程时读取执行事实，已完工不再排，已开工/暂停默认固定，异常中阻止普通自动重排，落库前检查执行状态版本没有变化。
- **承载子 feature**：`reschedule-minimum-execution-guardrails`、`reschedule-respects-execution-facts`。
- **触碰现有模块**：`core/services/scheduler/run/schedule_input_collector.py`、`core/services/scheduler/run/freeze_window.py`、`core/services/scheduler/run/schedule_graph_dispatch_context.py`、`core/services/scheduler/run/schedule_seed_contracts.py`、`core/services/scheduler/run/schedule_persistence.py`、`core/algorithms/greedy/dispatch/sgs_graph.py`。

### 测试和 Win7 约束

- **职责**：把测试、门禁、离线静态资源、Python 3.8、Win7 + Chrome 109 约束写进每条子 feature。
- **承载子 feature**：`aps-three-gap-docs-quality-gate`。
- **触碰现有模块**：`tests/`、`.codestable/tools/validate-yaml.py`、`scripts/run_quality_gate.py`、用户文档。

## 5. 模块间接口契约 / 共享协议（架构层详设）

这一节是后续 feature-design 的硬约束输入。后续如果要改变字段、状态、路由或错误码，先回到这个 roadmap update。

本节里的英文结构名、字段名和枚举值只给代码和测试使用，不允许直接展示给用户。页面、导出、弹窗、按钮、表格列名、空状态、错误提示都必须先转成中文大白话。

所有 Python 签名和类型示例按 Python 3.8 可落地写法表达：使用 `Optional[...] / List[...] / Dict[...] / Union[...]`，不使用 `int | None`、`list[str]`、`dict[int, X]` 这类 Python 3.8 不支持的写法。

### 5.0 用户可见文案总规则

**内部值到页面文案的固定映射**：

实现时不要做一个“大杂烩映射函数”把所有内部值都塞进去，尤其不能让同一个 `exception` 同时承担“现场状态”和“报异常动作”两个意思。代码里至少要拆成两个清楚的函数或表：

- `current_status / reported_status` 这类现场状态值走“状态中文名”映射，`exception` 只能显示为“异常中”。
- `event_type / action` 这类现场动作值走“动作中文名”映射，数据库 `event_type='exception'` 读给前端时必须先转成 `action='report_exception'`，再显示为“报异常”。

**计划身份 / 现场状态 / 证据强度**：

| 内部值 | 用户能看到的说法 |
|---|---|
| `adopted` | 正式采用方案 |
| `baseline_best` | 原算法代表方案 |
| `critical_best` | 重点工序优先代表方案 |
| `candidate` / `candidate_rows` | 对比参考方案 |
| `scenario` / `scenario_id` | 模拟预览 |
| `source_table=schedule` | 内部读取来源是正式排程表，用户最终看到什么身份还要看计划身份 |
| `not_started` | 待开工 |
| `processing` | 生产中 |
| `paused` | 已暂停 |
| `exception` | 异常中 |
| `completed` | 已完工 |
| `critical_chain` | 建议先复核的工序 / 可能拖住后面工序的任务 |
| `fact` | 证据比较充分 |
| `likely` | 可能性较高，建议人工复核 |
| `weak` | 线索较弱，仅供参考 |
| `missing_data` | 当前数据不足 |
| `failed` | 这套方案没有跑成功 |
| `skipped` | 本次跳过 |
| `not_run` | 本次未运行 |

**现场事件动作**：

| 程序动作或数据库事件 | 用户能看到的说法 |
|---|---|
| `start` | 开工 |
| `pause` | 暂停 |
| `resume` | 继续生产 |
| `finish` | 完工 |
| `event_type='exception'` -> `action='report_exception'` | 报异常 |

**空状态和异常原因**：

| 内部值 | 用户能看到的说法 |
|---|---|
| `unavailable` | 暂无可用数据 |
| `equipment` | 设备问题 |
| `person` | 人员问题 |
| `material` | 物料问题 |
| `quality` | 质量问题 |
| `process` | 工艺问题 |
| `external` | 外协问题 |
| `other` | 其他 |

**严重程度 / 处理状态 / 是否建议重新排程**：

| 内部值 | 用户能看到的说法 |
|---|---|
| `low` | 轻微 |
| `medium` | 一般 |
| `high` | 严重 |
| `critical` | 紧急 |
| `new` | 刚上报 |
| `checking` | 处理中 |
| `waiting` | 等待条件 |
| `handled` | 已处理 |
| `suggest_reschedule=true` | 建议重新排程 |
| `suggest_reschedule=false` | 暂不建议重新排程 |

**硬规则**：

- 页面、导出和错误提示里不能出现 `plan_role`、`scenario_id`、`source_table`、`candidate_id`、`event_type`、`ReasonCode`、`score tuple`、数据库字段名、函数名或内部异常堆栈。
- 页面不写“根因已定位”“主要原因已确认”。统一写“可能线索”“建议先复核”“当前数据不足，不能确定唯一原因”。
- 页面不能把内部 `critical_chain` 翻成“关键链命中”，只能写“建议先复核的工序”。
- 页面不能把 `scenario_id` 当名称兜底展示；没有模拟方案名称时写“模拟预览（未命名）”，导出文件名也用中文名称和日期，不拼内部编号。
- `source_table=schedule` 只说明后端这一行是从正式排程表读出来的，不等于用户正在看的就是“可反馈的正式采用方案”。页面最终显示“正式采用方案 / 对比参考方案 / 模拟预览”，必须同时看 `requested_plan_role`、`effective_plan_role`、`plan_resolution_status`、`can_dispatch` 和 `can_write_feedback`。只要请求角色不是 `adopted`，即使 `source_table=schedule`，也要按“对比参考方案”展示，并禁止派工和现场反馈。
- 车间反馈错误提示必须告诉用户下一步怎么做，例如“这道工序已经完工，不能再次开工。如确实点错，请找计划员修正。”
- 必须把“给程序传参用的字段”和“用户能看到、复制、导出、截图传播的文字”分开。URL、隐藏表单、前端请求体、服务端响应里可以保留 `plan_role / scenario_id / source_table / candidate_id / event_type / action / details.reason` 这类稳定字段，让浏览器和服务端能对上同一套计划；但这些字段只能给程序判断用，不能直接当页面文案、按钮文案、表格列名、导出列名、导出文件名、弹窗、错误提示或可复制说明展示。
- 给前端页面和公开接口返回程序字段时，必须同时提供中文 `label / message / disabled_reason / action_label / *_label` 这类给用户看的字段。页面只能显示中文字段；如果前端脚本把 `data-*`、隐藏字段或 JSON 里的程序字段转成可见文字，必须先映射成中文大白话。内部日志、开发专用接口和测试诊断可以保留内部字段，但必须明确标成“开发和测试使用，不给用户看”。
- 每个前端 feature 的验收都必须检查页面、导出文件名、导出列名、空状态、错误提示、按钮、弹窗、表格表头，确认没有内部字段或英文枚举露给用户。

### 5.1 计划身份协议 `PlanIdentity`

**方向**：所有读排程结果的模块 → `SchedulePlanQueryService`

**形式**：Python 数据结构 + viewmodel 字段 + URL 参数

```text
PlanIdentity
- version: Optional[int]
- requested_plan_role: Optional[PlanRole]
- effective_plan_role: PlanRole
- plan_resolution_status: PlanResolutionStatus
- source_table: PlanSourceTable
- source_row_id: Optional[int]
- candidate_id: Optional[int]
- candidate_key: Optional[str]
- scenario_id: Optional[str]
- schedule_result_status: Optional[str]
- is_simulation: bool
- label: str
- user_label: str
- is_official: bool
- is_preview: bool
- is_current_executable_version: bool
- is_current_executable_official_version: bool
- is_superseded_by_newer_version: bool
- schedule_lock_status: Optional[str]
- can_dispatch: bool
- can_write_feedback: bool
- detail_saved: bool

PlanRole = adopted, baseline_best, critical_best
PlanResolutionStatus = resolved_adopted, resolved_comparison, scenario_preview, fallback_to_adopted, historical_version, missing_detail, not_found
PlanSourceTable = schedule, candidate_rows, adjustment_scenario_rows
```

**规则**：

- `adopted` 必须读正式 `Schedule`。
- `baseline_best / critical_best` 是对比角色，不是来源表。读取来源以 `source_table` 为准；它们可能读 `candidate_rows`，也可能在和正式采用方案相同时读 `schedule`，但仍不能当作现场执行计划。
- `scenario_id` 只表示模拟方案预览，发布前不能派工、不能写现场反馈。
- `plan_resolution_status` 用来说明“请求是怎么被解析出来的”。如果请求的是候选代表方案但缺明细后回退到 adopted，必须写 `fallback_to_adopted`；这类结果只能看，不能写现场反馈。
- `is_current_executable_version=true` 只说明“这个版本号在可执行版本范围内”。它不能单独打开现场反馈。
- `is_current_executable_official_version=true` 的第一版口径：请求版本等于当前最新可执行正式版本，且该版本有可读取的正式 `Schedule` 行，且 `ScheduleHistory.result_status` 不是 `simulated / failed`，且 `result_summary.is_simulation` 不是 true。当前代码里模拟排产也会写 `Schedule` 和 `ScheduleHistory`，所以必须排除模拟版本，不能只看 `MAX(version)`。
- `is_superseded_by_newer_version=true` 表示请求版本小于当前最新正式 `ScheduleHistory.version`，也就是已被新版本替代。
- `schedule_lock_status` 只展示 `Schedule.lock_status` 这类排程冻结信息。第一版不能把它混成“被新版本替代”，也不能仅因为 `lock_status=locked/frozen` 就阻止现场反馈；如果以后确实要让某类锁定行禁止反馈，必须单独起业务规则。
- `can_dispatch=true` 的唯一条件是：`source_table=schedule`、`requested_plan_role` 为空或 `adopted`、`effective_plan_role=adopted`、`scenario_id` 为空、`plan_resolution_status=resolved_adopted`、`is_current_executable_official_version=true`、`is_superseded_by_newer_version=false`、`is_simulation=false`、`schedule_result_status` 不是 `simulated / failed`、`result_summary.is_simulation` 不是 true。
- `can_write_feedback=true` 的条件和 `can_dispatch` 一样。历史正式方案也只能查看，不能写现场反馈。
- 候选代表方案即使因为“和正式采用方案同源”读到了 `source_table=schedule`，只要 `requested_plan_role` 是 `baseline_best / critical_best`，或者 `plan_resolution_status` 是 `resolved_comparison / fallback_to_adopted / missing_detail`，`can_dispatch` 和 `can_write_feedback` 都必须是 false。
- `can_write_feedback` 还必须排除 `schedule_result_status=simulated / failed` 和 `result_summary.is_simulation=true`。也就是说，只要这版结果是模拟、失败、回退查看、缺明细查看或对比查看，就算能读到 `Schedule` 行，也不能写现场反馈。
- `PlanIdentity` 只定义身份字段和中文显示名；派工确认、现场反馈写入和后端拦截由“派工身份护栏”和“执行反馈服务”落实。
- 页面必须展示中文身份标签：正式采用方案、对比参考方案、模拟预览。导出文件名和 JSON payload 里也要带身份，避免用户离线传播后看不出来源。

### 5.2 证据协议 `EvidenceLink`

**方向**：延期诊断、方案对比、复盘模块 → 页面 / 报表 / 导出

```text
EvidenceLink
- evidence_type: overdue | schedule_row | critical_chain | utilization | downtime | material_ready | warning | execution_event
- evidence_label: str
- object_type: batch | operation | machine | operator | schedule | scenario | candidate | event
- object_id: Optional[Union[str, int]]
- plan_identity: PlanIdentity
- source_table: Optional[str]
- source_row_id: Optional[Union[str, int]]
- evidence_scope: row | aggregate | missing_data
- aggregation_key: Optional[str]
- contributing_count: Optional[int]
- missing_data_key: Optional[str]
- expected_source: Optional[str]
- checked_object_type: Optional[str]
- checked_object_id: Optional[Union[str, int]]
- checked_range_start: Optional[datetime]
- checked_range_end: Optional[datetime]
- checked_at: Optional[datetime]
- gap_label: Optional[str]
- source_version: Optional[int]
- candidate_id: Optional[int]
- scenario_id: Optional[str]
- metric_name: Optional[str]
- metric_value: Optional[Union[str, int, float]]
- time_range_start: Optional[datetime]
- time_range_end: Optional[datetime]
- source_page: str
- link: Optional[str]
- confidence: fact | likely | weak | missing_data
```

**规则**：

- 用户页面只显示中文，不显示内部枚举。
- `source_table` 是“这条证据来自哪张内部表”的审计字段，不是所有证据都能填。行级证据必须带 `source_table / source_row_id`；聚合证据和缺数据证据可以不带 `source_table / source_row_id`，不能为了凑字段填假表名。
- 聚合证据必须带 `evidence_scope=aggregate`、`aggregation_key` 和 `contributing_count`，例如设备负荷或停机影响这类按设备汇总的证据。
- 每条“可能线索”必须至少有一条可追到来源的证据；确实缺数据时明确写 `evidence_scope=missing_data` 和 `confidence=missing_data`。
- 缺数据证据也必须能追溯“缺什么、查过哪里、影响谁”。`evidence_scope=missing_data` 时必须带 `missing_data_key`、`expected_source`、`checked_object_type`、`checked_object_id`、`checked_at` 和 `gap_label`；如果缺口和时间范围有关，还要带 `checked_range_start / checked_range_end`。例如“缺少批次 B-001 的齐套状态”“缺少工序 123 的现场完工时间”，不能只写一个笼统的“数据不足”。
- 证据不足不是系统错误，页面要正常展示“证据不足”。
- 链接必须带 `version / plan_role / scenario_id`，不能跳到另一套计划。
- `source_table / source_row_id` 是审计字段。页面不能直接显示表名或字段名，只能显示 `evidence_label` 这类中文说明。导出给用户看的表也不能出现“source_table”或真实表名，只能写“证据来源”“已核对数据”“证据缺口”这类中文列名。

### 5.3 延期诊断服务契约

**方向**：报表 / 分析页 / 甘特详情 → 延期诊断服务

**拟新增服务**：

```text
core/services/scheduler/schedule_delay_diagnosis_service.py
```

**函数签名**：

```text
diagnose_plan_overdue(
    version: Optional[int],
    plan_role: Optional[str] = None,
    scenario_id: Optional[str] = None,
    as_of_time: Optional[datetime] = None,
) -> OverdueDiagnosisReport

diagnose_batch(
    version: Optional[int],
    batch_id: str,
    plan_role: Optional[str] = None,
    scenario_id: Optional[str] = None,
    as_of_time: Optional[datetime] = None,
) -> OverdueDiagnosisItem
```

**输出结构**：

```text
OverdueDiagnosisReport
- plan_identity: PlanIdentity
- generated_at: datetime
- as_of_time: datetime
- total_count: int
- scheduled_count: int
- unscheduled_count: int
- top_clues: List[ClueSummary]
- items: List[OverdueDiagnosisItem]
- warnings: List[str]
- trace_meta: DiagnosisTraceMeta

OverdueDiagnosisItem
- batch_id: str
- part_no: Optional[str]
- part_name: Optional[str]
- due_date: Optional[Union[date, datetime]]
- bucket: scheduled_overdue | unscheduled_overdue
- delay_hours: float
- delay_days: float
- finish_time: Optional[datetime]
- as_of_time: datetime
- suggested_operation_clue: Optional[OperationClue]
- last_operation: Optional[OperationClue]
- confirmed_facts: List[ConfirmedFact]
- candidate_clues: List[DiagnosisClue]
- leading_clue_code: ReasonCode
- leading_clue_label: str
- confidence: fact | likely | weak | missing_data
- evidences: List[EvidenceLink]
- data_gaps: List[str]
- suggested_actions: List[SuggestedAction]
- links: List[EvidenceLink]
- trace_meta: DiagnosisTraceMeta

ClueSummary
- clue_code: ReasonCode
- clue_label: str
- count: int
- confidence: fact | likely | weak | missing_data

OperationClue
- op_id: Optional[int]
- op_name: Optional[str]
- batch_id: str
- machine_id: Optional[str]
- operator_id: Optional[str]
- planned_start_time: Optional[datetime]
- planned_end_time: Optional[datetime]
- actual_start_time: Optional[datetime]
- actual_end_time: Optional[datetime]
- clue_label: str
- evidences: List[EvidenceLink]

DiagnosisClue
- clue_code: ReasonCode
- clue_label: str
- plain_text: str
- confidence: fact | likely | weak | missing_data
- evidences: List[EvidenceLink]
- data_gaps: List[str]

ConfirmedFact
- text: str
- evidences: List[EvidenceLink]

SuggestedAction
- label: str
- target_page: str
- link: Optional[str]
- reason: str
- priority: high | medium | low

DiagnosisTraceMeta
- generated_at: datetime
- as_of_time: datetime
- plan_identity: PlanIdentity
- evidence_count: int
- evidence_sources: List[EvidenceLink]
- rule_version: str
- ranking_inputs: List[str]
- clue_selection_trace: List[str]
- input_fingerprint: str
```

**第一版原因码**：

```text
machine_bottleneck
operator_bottleneck
predecessor_late
downtime_impact
material_not_ready
material_status_missing
external_duration
due_too_tight
missing_resource
frozen_window
unscheduled
unknown
```

`confirmed_facts` 不能只是一串文字。每条已确认事实都必须至少绑定一条 `EvidenceLink`；如果没有可追溯证据，只能降级到 `candidate_clues` 或 `data_gaps`，页面写“建议复核”或“证据不足”，不能写成已确认事实。

**判断口径**：

- `scheduled_overdue`：已有计划完成时间，完成时间晚于交期边界。
- `unscheduled_overdue`：没有计划完成时间，当前时间已经过交期。
- `critical_chain` 只能作为线索，不能直接当单批次根因。
- 设备/人员利用率高只能作为高风险线索，必须和延期批次的具体工序关联后再提高置信度。
- 物料原因第一版只基于齐套状态和批次物料需求明细，不承诺库存、采购、在途物料的完整追溯。
- 第一版必须读取 `Batches.ready_status / ready_date`、`BatchMaterials.ready_status / required_qty / available_qty`，以及物料名称、规格、单位等基础资料；涉及路径至少包括 `data/repositories/batch_repo.py`、`data/repositories/batch_material_repo.py`、`data/repositories/material_repo.py`、`core/services/material/batch_material_service.py`。
- 如果没有批次物料需求明细，页面只能说“缺少物料明细，暂时不能判断是不是物料问题”；不能直接说“物料不够导致延期”。
- 没有现场执行事件前，不能判断“现场做慢了”。
- 页面字段用“可能线索 / 建议先复核 / 证据不足”，不使用“主要原因”“根因”。
- `suggested_operation_clue` 只能表示“建议先复核的工序”，页面不能翻译成“第一卡点已确认”“主要原因”或“系统已判定”。
- 第一版可以实时计算，不强制新增诊断快照表；但每次页面详情接口和导出都必须带 `DiagnosisTraceMeta`。
- 导出文件本身必须包含追溯信息，不能用“详情接口里有”替代。第一版增强现有 `GET /reports/overdue/export`：导出工作簿至少包含“超期清单”和“诊断依据”两部分；“诊断依据”里要有计划身份、生成时间、筛选条件、证据来源和证据缺口。程序内部仍可使用 `trace_meta / rule_version / input_fingerprint` 存值，但导出表头、用户说明和页面提示必须写成中文大白话，推荐固定列名为“本次诊断编号”“生成依据摘要”“核对信息”“证据来源”“证据缺口”“生成时间”“筛选条件”。不要把 `trace_meta / rule_version / input_fingerprint` 原样给用户看，也不要把“诊断规则版本”“输入指纹”作为用户表头；这些词只允许出现在开发说明或测试断言里。如果当前系统仍拒绝 scenario 预览导出，延期诊断导出也必须保持拒绝，并用中文提示“模拟预览暂不支持导出，请切换到正式采用方案”；同时同步 `web/routes/report_plan_preview.py` 里的模拟预览拒绝文案、导出筛选条件和导出日志小字段，避免路由层和导出文件追溯信息对不上。
- `input_fingerprint` 用计划身份、`as_of_time`、证据来源、证据范围、排序依据按稳定顺序拼接后计算哈希；同一批输入必须得到同一个指纹。
- 若后续需要历史复现，再单独设计 `ScheduleDiagnosisSnapshot` 持久化表。第一版不要把延期诊断扩大成完整审计系统。

### 5.4 方案对比契约

**方向**：排产分析页 → 候选方案摘要 / 差值服务

**第一版只承诺三类角色**：

```text
adopted
baseline_best
critical_best
```

**页面模型**：

```text
CandidateComparisonPage
- plan_identity: PlanIdentity
- recommendation: Optional[RecommendationSummary]
- cards: List[CandidateCard]
- metric_table: List[CandidateMetricRow]
- empty_state: Optional[str]
- warnings: List[str]
- links: List[EvidenceLink]

RecommendationSummary
- adopted_candidate_key: Optional[str]
- adopted_label: str
- headline: str
- reasons: List[str]
- tradeoffs: List[str]
- review_points: List[str]
- next_actions: List[SuggestedAction]

CandidateCard
- role: adopted | baseline_best | critical_best
- candidate_key: Optional[str]
- candidate_label: str
- status: completed | failed | skipped | not_run | unavailable
- is_official: bool
- detail_saved: bool
- metrics: CandidateMetrics
- diff_from_adopted: Optional[CandidateMetricDiff]
- business_summary: str
- risk_summary: str
- links: List[EvidenceLink]

CandidateMetrics
- failed_ops: Optional[int]
- overdue_count: Optional[int]
- total_tardiness_hours: Optional[float]
- weighted_tardiness_hours: Optional[float]
- makespan_hours: Optional[float]
- changeover_count: Optional[int]
- score: Optional[float]
- score_display: Optional[str]

CandidateMetricDiff
- metric_name: str
- current_value: Optional[Union[int, float]]
- adopted_value: Optional[Union[int, float]]
- diff_value: Optional[Union[int, float]]
- direction_label: 多了 | 少了 | 基本持平 | 暂无数据
- user_label: str
```

**第一版指标**：

```text
failed_ops
overdue_count
total_tardiness_hours
weighted_tardiness_hours
makespan_hours
changeover_count
score
```

**差值规则**：

```text
diff = current_metric - adopted_metric
```

- 失败工序数、超期批次数、总拖期、加权拖期、总工期、换型次数，默认越小越好。
- 差值很小要显示“基本持平”，不要强行红绿。
- 评分可以保留，但不能作为业务主解释。
- 页面第一眼不能直接显示 `score tuple` 或 `0 / 3 / 18.5 / 126` 这类内部串。若确实要保留，只能放到“技术详情”折叠区，并显示为“系统内部参考分”。
- `candidate-recommendation-card` 只做推荐结论壳、现有 `selection_reason_code` 的中文翻译、候选失败/未开启提示；不提前计算三方案差值。`tradeoffs` 在第一个 feature 里只能写“详细差值见后续摘要卡”，真正差值由 `candidate-summary-delta-cards` 负责。

**不能承诺**：

- 不承诺全部 3/5/7 档候选明细。
- 不承诺批次级提前/延后清单。
- 不承诺资源负荷变化清单。
- 不承诺对照甘特图。
- 不用任意两个 `candidate_id` 做自由对比。第一版只按固定角色 `adopted / baseline_best / critical_best` 取数。
- 第一版所有差值固定相对 `adopted` 计算，不提供 `compare_plan_role` 这类自由比较参数。

这些放到后续 feature。

### 5.5 派工确认护栏契约

**方向**：资源派工页 / 未来确认派工动作 → 计划身份校验

第一版只做“身份提示、禁用写入、后端拒绝候选和模拟预览”。不新增真正的“确认派工”写入模型，不新增确认派工表，不承诺 `/resource-dispatch/confirm` 的 POST 副作用。以后若要做确认派工，必须另起 feature，先定义写入表、状态、副作用、撤销和审计。

**允许确认派工的条件**：

确认派工和现场反馈只能在 `PlanIdentity.can_dispatch=true` 时开放。第一版 `can_dispatch=true` 必须同时满足下面所有条件，不能只看其中一两项：

```text
source_table == schedule
requested_plan_role is empty or adopted
effective_plan_role == adopted
scenario_id == null
plan_resolution_status == resolved_adopted
is_current_executable_official_version == true
is_superseded_by_newer_version == false
is_simulation == false
schedule_result_status not in simulated, failed
result_summary.is_simulation is not true
```

**拒绝条件**：

- `source_table=candidate_rows`：这是候选代表方案，只能查看或对比。
- `source_table=adjustment_scenario_rows`：这是模拟方案预览，必须先发布成正式版本。
- 计划版本不是最新正式采用方案、是模拟预览、是失败结果、是回退查看、是缺明细查看、是对比参考方案：提示用户切换到最新正式采用方案。
- 历史正式方案：只能查看，不能提交派工或现场反馈。

**页面文案**：

- 正式计划：`当前查看的是正式采用方案，可用于派工和现场反馈。`
- 候选方案：`当前查看的是对比参考方案，不能直接派工。`
- 模拟方案：`当前查看的是模拟预览，正式计划还没有改变。`
- 历史正式方案：`当前查看的是历史正式方案，只能查看，不能提交开工或完工。请切换到最新正式采用方案。`

### 5.6 执行事件表契约

**方向**：资源派工车间反馈页面 → 执行反馈服务 → repository / 数据库

**拟新增表**：

```text
OperationExecutionEvents
- id INTEGER PRIMARY KEY AUTOINCREMENT
- op_id INTEGER NOT NULL
- batch_id TEXT NOT NULL
- schedule_version INTEGER NOT NULL
- schedule_id INTEGER NOT NULL
- source_table TEXT NOT NULL
- effective_plan_role TEXT NOT NULL
- scenario_id TEXT
- event_type TEXT NOT NULL
- event_time DATETIME NOT NULL
- reported_status TEXT NOT NULL
- actual_machine_id TEXT
- actual_operator_id TEXT
- reason_code TEXT
- reason_detail TEXT
- severity TEXT
- impact_minutes INTEGER
- affected_machine_id TEXT
- affected_operator_id TEXT
- handling_status TEXT
- suggest_reschedule INTEGER NOT NULL DEFAULT 0
- quantity_done INTEGER
- quantity_scrapped INTEGER
- remark TEXT
- idempotency_key TEXT NOT NULL
- request_fingerprint TEXT NOT NULL
- previous_state_revision TEXT NOT NULL
- created_by TEXT NOT NULL
- created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
```

**约束**：

- 数据库必须有 `FOREIGN KEY(op_id) REFERENCES BatchOperations(id)`。
- 数据库必须有 `FOREIGN KEY(schedule_id) REFERENCES Schedule(id)`。
- 数据库必须有 `CHECK(event_type IN ('start', 'pause', 'resume', 'finish', 'exception'))`。
- 数据库必须有 `CHECK(reported_status IN ('processing', 'paused', 'exception', 'completed'))`。
- 数据库必须有 `CHECK(source_table = 'schedule')`、`CHECK(effective_plan_role = 'adopted')`、`CHECK(scenario_id IS NULL)`。
- 数据库必须有 `CHECK(suggest_reschedule IN (0, 1))`；`suggest_reschedule` 入库用 `0 / 1`，页面和接口展示时再映射成“暂不建议重新排程 / 建议重新排程”。
- 数据库必须约束 `pause / exception` 的 `reason_code` 不能为空；`exception` 的 `severity` 不能为空。
- 数据库必须有 `UNIQUE(idempotency_key)`，同一个请求重复提交只能产生一条事件。
- 数据库必须有 `UNIQUE(op_id, previous_state_revision)`，或在同一事务内用等价行锁方案保证同一旧状态只会被消费一次。
- 索引至少包含 `idx_operation_execution_events_op(op_id, event_time)`、`idx_operation_execution_events_schedule(schedule_id)`、`idx_operation_execution_events_schedule_op(schedule_id, op_id)`、`idx_operation_execution_events_batch(batch_id)`、`idx_operation_execution_events_op_revision_unique(op_id, previous_state_revision)`。
- `event_type` 允许：`start / pause / resume / finish / exception`。
- `reported_status` 允许：`processing / paused / exception / completed`。
- `pause / exception` 必须有 `reason_code`。
- `finish.event_time` 不能早于实际开始时间。
- 同一工序后续事件不能早于上一条事件时间；误点修正走后续纠错流程，不在第一版静默覆盖。
- 每条事件都必须绑定正式 `Schedule` 行：`source_table=schedule`、`effective_plan_role=adopted`、`scenario_id` 为空、`schedule_id` 指向同一个 `op_id` 和 `schedule_version`。
- `schedule_id / schedule_version / op_id / batch_id` 必须在同一事务里重新查库确认属于同一条正式计划行，不能只分别校验“计划行存在”和“工序存在”。如果任一项对不上，返回 409，不写事件。
- `schedule_id / schedule_version` 表示“事件发生时用户看到的正式计划行”，用于审计和追溯；现场事实本身以 `op_id` 为工序级事实源，后续新计划版本必须按 `op_id` 聚合读取最新现场状态。
- 新版本不能复制旧事件，也不能把旧事件改写到新 `schedule_id`。如果同一个 `op_id` 在新版本里继续存在，读取执行状态时跨版本按 `op_id` 聚合；如果工序不存在，则作为数据异常用中文提示。
- `created_by` 第一版来自页面必填的“反馈人”输入；空值直接拒绝。后续接登录体系时再替换来源，不允许默认写假用户。
- 执行事件只允许追加，不允许更新或删除。纠错、撤销、反冲都必须另起 correction/reversal 设计。
- `actual_machine_id / actual_operator_id` 是事件落库后的实际资源字段。前端开工提交仍使用 `machine_id / operator_id`，由 service 校验后转换成实际资源字段写入事件表。
- 暂停、继续、异常相关字段可以在 foundation 表结构里预留，但 `operation-execution-event-foundation` 的业务验收只验证字段、约束、幂等、状态聚合边界；暂停和异常完整业务入口由 `shop-exception-feedback` 验收。
- `request_fingerprint` 必须由服务端按稳定规则重新计算，前端可以不传，传了也只能当调试信息，不能信任。指纹输入必须包含完整计划身份、`schedule_id / schedule_version / op_id / batch_id`、`expected_state_revision`、动作类型和动作载荷。
- 服务端写入顺序必须固定为：第一步先用 `idempotency_key` 查已有事件；如果同 key 已存在，并且服务端指纹、计划身份、`op_id`、动作和载荷都和本次重算一致，直接返回已有事件，哪怕这时当前状态版本已经被这条事件消费过，也不能误报 `stale_state_revision`；如果同 key 但任何一项不一致，返回 `409 idempotency_conflict` 且不写。第二步只有在 key 不存在时，才读取当前执行状态、比较 `expected_state_revision`。第三步状态版本没过期才写入事件；插入后重新聚合得到新的 `state_revision` 并随响应返回，不把新 `state_revision` 更新回事件行。
- 只要插入时捕获到任何唯一约束冲突，处理顺序也必须先回到 `idempotency_key`：重新按本次 key 查询已有事件；如果查到同 key 且服务端指纹、计划身份、`op_id`、动作和载荷都一致，返回已有事件；如果查到同 key 但内容不一致，返回 `409 idempotency_conflict`；只有查不到同 key 时，才按 `UNIQUE(op_id, previous_state_revision)` 这类状态版本冲突处理，重新聚合当前状态并返回 `409 stale_state_revision`。
- 如果采用 SQLite 行锁方案代替唯一约束，必须在独立事务入口里使用 `BEGIN IMMEDIATE` 或等价写锁，不能把并发控制只放在 route 层。

**严禁复用**：

- 禁止把 `Schedule.start_time/end_time` 改成实际时间。
- 禁止把 `Schedule.lock_status` 当作现场状态。
- 禁止把候选方案运行时间当作现场时间。
- 禁止只靠 `BatchOperations.status` 记录开工完工。
- 禁止用通用操作日志替代执行事件表。

### 5.7 执行状态读模型契约

**方向**：执行事件 repository → 资源派工页面 / 复盘页面 / 重排输入

第一版可以先不物化表，由事件聚合；页面变慢后再加物化表。

```text
OperationExecutionState
- op_id: int
- batch_id: str
- current_status: not_started | processing | paused | exception | completed
- current_status_label: 待开工 | 生产中 | 已暂停 | 异常中 | 已完工
- actual_start_time: Optional[datetime]
- actual_end_time: Optional[datetime]
- actual_duration_minutes: Optional[float]
- pause_duration_minutes: float
- actual_machine_id: Optional[str]
- actual_machine_label: Optional[str]
- actual_operator_id: Optional[str]
- actual_operator_label: Optional[str]
- last_event_id: Optional[int]
- last_event_type: Optional[str]
- last_event_time: Optional[datetime]
- last_event_action_label: Optional[str]
- last_event_remark: Optional[str]
- latest_exception_event_id: Optional[int]
- latest_exception_time: Optional[datetime]
- latest_exception_reason_code: Optional[str]
- latest_exception_reason_label: Optional[str]
- latest_exception_severity: Optional[str]
- latest_exception_severity_label: Optional[str]
- latest_exception_impact_minutes: Optional[int]
- latest_exception_impact_minutes_label: Optional[str]
- latest_exception_affected_machine_id: Optional[str]
- latest_exception_affected_machine_label: Optional[str]
- latest_exception_affected_operator_id: Optional[str]
- latest_exception_affected_operator_label: Optional[str]
- latest_exception_handling_status: Optional[str]
- latest_exception_handling_status_label: Optional[str]
- latest_exception_suggest_reschedule: bool
- latest_exception_suggest_reschedule_label: Optional[str]
- latest_exception_remark: Optional[str]
- state_revision: str
- updated_at: datetime
```

`last_event_*` 只表示时间上最后一条现场事件，可能是开工、暂停、继续、完工或报异常。`latest_exception_*` 只表示最近一次“报异常”事件。两组字段必须分开计算：最后一条事件如果是完工，`last_event_type=finish`，但 `latest_exception_*` 仍然保留最近一次异常信息；如果从未报过异常，`latest_exception_*` 全部为空或默认 false，不能把暂停原因、完工备注硬塞进去。

**状态流转**：

```text
not_started -> start -> processing
processing -> pause -> paused
processing -> finish -> completed
processing -> exception -> exception
paused -> resume -> processing
paused -> finish -> completed
paused -> exception -> exception
exception -> resume -> processing
exception -> finish -> completed
completed -> view only
```

`completed` 是只读终态。后续如果要纠错，必须单独设计 correction/reversal，不允许把 completed 直接改回 processing。
第一版不允许 `not_started -> exception`，避免一条还没开工的任务被异常上报扩大影响范围；未开工发现问题时，先由计划员处理计划或资源数据。

**revision 口径**：

- 单个工序的 `state_revision` 不能依赖“本次刚插入后才知道的事件 id”来决定是否可写，否则会和只追加事件的并发控制打架。第一版用 `op_id:event_count:last_committed_event_id` 从已提交事件聚合得到；没有事件时使用 `op_id:0:0`。
- 新事件写入时，`previous_state_revision` 必须等于写入前聚合出来的旧 revision；写入完成后再用已提交事件重新聚合出新的 `state_revision` 并随事件返回。
- 多个工序的 `execution_snapshot_revision` 用同一批 `op_id=state_revision` 按 `op_id` 排序后计算哈希。生成快照时必须同时保存 `execution_snapshot_op_ids`，否则后面无法确认复算用的是不是同一批工序。
- 写反馈和重排落库都必须比较 revision；不一致时返回 409，并用中文提示用户刷新后重试。

### 5.8 执行反馈服务契约

**拟新增服务**：

```text
core/services/scheduler/operation_execution_feedback_service.py
data/repositories/operation_execution_event_repo.py
```

**拟新增 repository**：

```text
class OperationExecutionEventRepo
- get_event_by_id(event_id) -> Optional[OperationExecutionEvent]
- get_by_idempotency_key(idempotency_key) -> Optional[OperationExecutionEvent]
- insert_event(event_row) -> OperationExecutionEvent
- list_events_by_op_id(op_id) -> List[OperationExecutionEvent]
- list_events_by_op_ids(op_ids) -> List[OperationExecutionEvent]
- list_latest_events_by_op_ids(op_ids) -> Dict[int, OperationExecutionEvent]
- list_latest_exception_events_by_op_ids(op_ids) -> Dict[int, OperationExecutionEvent]
- aggregate_states_by_op_ids(op_ids) -> Dict[int, OperationExecutionState]
```

`OperationExecutionEventRepo` 负责所有 `OperationExecutionEvents` 的 SQL。service 只能调用 repository，不能在 `operation_execution_feedback_service.py` 里散写 `SELECT / INSERT / UPDATE`。如果状态聚合逻辑放在 service，repository 也必须至少提供按 `op_ids` 批量拉事件的方法，避免 service 里自己拼 SQL。捕获 `idempotency_key` 的 UNIQUE 冲突后，必须通过 `get_by_idempotency_key()` 回查同 key 事件，再按 fingerprint 和载荷判断是重复提交还是冲突提交。

**函数签名**：

```text
ExecutionFeedbackContext
- version: int
- requested_plan_role: adopted | baseline_best | critical_best
- schedule_id: int
- op_id: int
- batch_id: str
- source_table: schedule
- effective_plan_role: adopted
- scenario_id: None
- expected_state_revision: str
- created_by: str
- idempotency_key: str

start_operation(context, event_time, operator_id, machine_id, remark=None) -> OperationExecutionEvent
pause_operation(context, event_time, reason_code, remark=None) -> OperationExecutionEvent
resume_operation(context, event_time, remark=None) -> OperationExecutionEvent
finish_operation(context, event_time, quantity_done, quantity_scrapped, remark=None) -> OperationExecutionEvent
report_exception(context, event_time, reason_code, severity, impact_minutes=None, affected_machine_id=None, affected_operator_id=None, handling_status=None, suggest_reschedule=False, remark=None) -> OperationExecutionEvent
get_execution_state(op_ids) -> Dict[int, OperationExecutionState]
list_execution_events(op_id) -> List[OperationExecutionEvent]
```

服务端不能信任前端传来的 `schedule_id`。写入前必须用 `version + requested_plan_role + scenario_id + op_id + schedule_id` 重新解析 `PlanIdentity`，再查询正式 `Schedule` 行，并确认 `PlanIdentity.can_write_feedback=true`。这个校验必须放在 service 层，route 层只负责收参和返回；即使有别的入口绕过 route 调 service，也不能写入候选方案、模拟预览或历史正式方案。

`request_fingerprint` 由服务端根据完整计划身份、`op_id / schedule_id / schedule_version / batch_id / expected_state_revision / action / event_time / created_by / machine_id / operator_id / quantity_done / quantity_scrapped / reason_code / severity / impact_minutes / affected_machine_id / affected_operator_id / handling_status / suggest_reschedule / remark` 等请求关键字段按稳定顺序生成。它只用于判断“同一个幂等键是不是同一次请求”，不能当权限或状态判断。

开工/完工字段校验必须固定，后续 feature-design 不能临时决定：

| 程序字段 | 用户看到的中文 | 动作 | 是否必填 | 校验规则 |
|---|---|---|---|---|
| `operator_id` | 操作人员 | 开工 | 必填 | 必须能匹配到已有人员；找不到时返回 `1001 / 400`，`details.field_label=操作人员`，message 用“请选择有效的操作人员” |
| `machine_id` | 设备 | 开工 | 必填 | 必须能匹配到已有设备，且要和当前正式排程记录允许的设备一致；找不到或不匹配时返回 `1001 / 400`，`details.field_label=设备` |
| `quantity_done` | 完成数量 | 完工 | 必填 | 必须是大于等于 0 的整数；不能为空、不能是小数、不能是负数、不能是文字 |
| `quantity_scrapped` | 报废数量 | 完工 | 选填 | 不填按 0；填写时必须是大于等于 0 的整数，不能是小数、负数或文字 |
| `quantity_done + quantity_scrapped` | 完成数量和报废数量合计 | 完工 | 必须校验 | 合计不能超过任务计划数量；超过时返回 `1001 / 400`，message 用“完成数量和报废数量加起来不能超过计划数量” |
| `remark` | 备注 | 开工/完工 | 选填 | 允许为空；如果填写，去掉前后空格后保存，页面只叫“备注” |

以上字段的程序名只给前端和测试判断用。页面、弹窗、错误提示和用户手册只能显示中文名，例如“操作人员”“设备”“完成数量”“报废数量”，不能显示 `operator_id / machine_id / quantity_done / quantity_scrapped`。

`handling_status` 第一版只记录上报异常当时的处理状态，不提供后续更新动作。如果后续要支持“处理状态改为已处理 / 已关闭”，必须另补更新路由、权限、状态流转和测试，不能在本条里顺手改事件。

**异常反馈字段固定表**：

后续 feature-design 不能临时改这些可选值。确实要改，必须先回本 roadmap update，再同步页面、导出、测试和说明书。页面、导出、弹窗和错误提示只显示“用户看到的中文”，不显示程序值。

| 字段 | 程序值 | 用户看到的中文 | 校验规则 |
|---|---|---|---|
| `reason_code` | `equipment` | 设备问题 | 暂停和报异常必填；如果用户选择设备问题，必须填说明，能选到影响设备时应记录影响设备 |
| `reason_code` | `person` | 人员问题 | 暂停和报异常必填；如果用户选择人员问题，必须填说明，能选到影响人员时应记录影响人员 |
| `reason_code` | `material` | 物料问题 | 暂停和报异常必填；只能说明现场反馈，不得自动改成“物料不够的原因已确认” |
| `reason_code` | `quality` | 质量问题 | 暂停和报异常必填；必须填说明 |
| `reason_code` | `process` | 工艺问题 | 暂停和报异常必填；必须填说明 |
| `reason_code` | `external` | 外协问题 | 暂停和报异常必填；必须填说明 |
| `reason_code` | `other` | 其他 | 暂停和报异常必填；必须填说明 |
| `severity` | `low` | 轻微 | 报异常必填 |
| `severity` | `medium` | 一般 | 报异常必填 |
| `severity` | `high` | 严重 | 报异常必填 |
| `severity` | `critical` | 紧急 | 报异常必填；页面要提示计划员尽快处理，不自动重排 |
| `handling_status` | `new` | 刚上报 | 可选；为空时默认按“刚上报”展示 |
| `handling_status` | `checking` | 处理中 | 可选；第一版只记录上报时状态，不提供后续更新 |
| `handling_status` | `waiting` | 等待条件 | 可选；第一版只记录上报时状态，不提供后续更新 |
| `handling_status` | `handled` | 已处理 | 可选；第一版只记录上报时状态，不代表系统已经闭环 |
| `suggest_reschedule` | `true` | 建议重新排程 | 报异常可选；只作为人工提示，不自动触发重排 |
| `suggest_reschedule` | `false` | 暂不建议重新排程 | 报异常可选；默认值 |
| `impact_minutes` | 非负整数分钟 | 预计影响时间 | 可选；为空时页面、弹窗和导出统一显示“暂时不知道影响多久” |
| `affected_machine_id` | 设备 ID | 影响设备 | 可选；填写时必须能查到设备，页面和导出显示设备名称或编号 |
| `affected_operator_id` | 人员 ID | 影响人员 | 可选；填写时必须能查到人员，页面和导出显示姓名或工号 |

其他校验规则：

- 未开工不能报异常。
- `pause / exception` 必须有 `reason_code`。
- `report-exception` 必须有 `severity`。
- `impact_minutes` 必须是大于等于 0 的整数；不填表示“暂时不知道影响多久”。
- `affected_machine_id / affected_operator_id` 可空；如果填写，服务端必须确认对应设备或人员存在，不能只信任前端字符串。
- `remark / reason_detail` 面向用户时叫“情况说明”，不能叫字段名。
- 开工时 `operator_id / machine_id` 必填，分别对应“操作人员 / 设备”；缺失或找不到时返回 `1001 / 400` 和中文字段名。
- 完工时 `quantity_done` 必填且为大于等于 0 的整数；`quantity_scrapped` 可空，空值按 0；两者相加不能超过计划数量。

**错误规则**：

- 未开工不能继续生产。
- 未开工第一版不允许直接完工。
- 未开工第一版不允许直接报异常；请先由计划员处理排程、资源或数据问题。
- 已完工不能再次开工、暂停、完工。
- 暂停和异常必须有原因。
- 候选方案和 scenario 预览不能写执行事件。
- 当前查看的不是最新正式采用方案时，直接 POST 写入现场反馈必须返回 `6003 / 409`，并带 `details.reason=not_current_official_plan`；权限不足才返回 `1004 / 403`。
- `expected_state_revision` 不一致时不能写事件。
- 所有错误 `message` 都必须是中文大白话，不展示内部枚举或字段名。

### 5.9 路由契约

第一版尽量挂在现有页面上下文里，不抢先新增大平台入口。下面的路由只有当前子 feature 真要用的才是硬约束；“后续可选入口”不能被当作第一版承诺。

**延期诊断只读入口**：

```text
GET /reports/overdue
GET /reports/overdue/delay-diagnosis?version=&plan_role=&scenario_id=&batch_id=
```

独立 `/scheduler/delay-diagnosis` 页面和导出是后续可选入口，不属于最小闭环第一版。

**方案对比只读路由**：

```text
GET /scheduler/analysis?version=
GET /scheduler/analysis/candidate-comparison/data?version=&plan_role=&scenario_id=
```

第一版继续嵌在 `/scheduler/analysis` 的方案对比区域。差值固定相对 `adopted` 计算；不得只靠 `candidate_id` 做自由对比；如后续要支持任意候选 ID 或任意两方案比较，必须同时带完整计划身份并另起 feature。

**资源派工确认路由**：

```text
GET /scheduler/resource-dispatch?version=&plan_role=&scenario_id=
```

第一版不新增 `POST /scheduler/resource-dispatch/confirm`。如果后续要做确认派工写入，必须先补数据模型和审计契约。

**车间反馈写入路由**：

```text
GET  /scheduler/resource-dispatch/execution/data?version=&plan_role=&scenario_id=&date=&machine_id=&operator_id=&status=
POST /scheduler/resource-dispatch/execution/<op_id>/start
POST /scheduler/resource-dispatch/execution/<op_id>/pause
POST /scheduler/resource-dispatch/execution/<op_id>/resume
POST /scheduler/resource-dispatch/execution/<op_id>/finish
POST /scheduler/resource-dispatch/execution/<op_id>/report-exception
GET  /scheduler/resource-dispatch/execution/<op_id>/events
```

这些路由第一版落在 `web/routes/domains/scheduler/scheduler_resource_dispatch.py`。如果未来改成独立 `scheduler_execution_feedback.py`，必须同步加入 `scheduler_route_registrar.py` 的 `_ROUTE_MODULES`。

`execution/data` 也必须解析完整 `PlanIdentity`，并在返回里带 `can_write_feedback` 和中文禁用原因。候选方案、模拟预览、历史正式方案只能返回只读数据，不能默认为 adopted 去查。`plan_identity` 是给程序核对身份的内部对象，页面展示只能使用 `plan_identity_label / can_write_feedback / disabled_reason` 这些中文字段。

`execution/data` 返回结构必须固定，至少包含下面这些字段。按钮能不能点必须由服务端返回，前端只负责照着显示，不允许前端自己猜状态字符串。

```text
{
  success: true,
  data: {
    plan_identity: PlanIdentity,
    plan_identity_label: 正式采用方案 | 对比参考方案 | 模拟预览,
    can_write_feedback: bool,
    disabled_reason: Optional[str],
    tasks: [
      {
        op_id: int,
        schedule_id: int,
        batch_id: str,
        op_name: Optional[str],
        current_status: not_started | processing | paused | exception | completed,
        current_status_label: 待开工 | 生产中 | 已暂停 | 异常中 | 已完工,
        state_revision: str,
        actual_start_time: Optional[datetime],
        actual_end_time: Optional[datetime],
        actual_machine_label: Optional[str],
        actual_operator_label: Optional[str],
        last_event_action_label: Optional[str],
        last_event_remark: Optional[str],
        latest_exception_reason_label: Optional[str],
        latest_exception_severity_label: Optional[str],
        latest_exception_impact_minutes_label: Optional[str],
        latest_exception_affected_machine_label: Optional[str],
        latest_exception_affected_operator_label: Optional[str],
        latest_exception_handling_status_label: Optional[str],
        latest_exception_suggest_reschedule_label: Optional[str],
        updated_at: datetime,
        available_actions: [
          {
            action: start | pause | resume | finish | report_exception,
            label: 开工 | 暂停 | 继续生产 | 完工 | 报异常,
            enabled: bool,
            disabled_reason: Optional[str]
          }
        ],
        unavailable_reasons: {
          start: Optional[str],
          pause: Optional[str],
          resume: Optional[str],
          finish: Optional[str],
          report_exception: Optional[str]
        }
      }
    ]
  }
}
```

`available_actions` 是唯一允许前端用来画按钮的数据源，旧字段名 `actions` 不再使用。`available_actions[].action` 是程序内部动作值，页面只能显示 `label`；`disabled_reason` 和 `unavailable_reasons` 必须是中文大白话，例如“当前是模拟预览，只能查看，不能提交现场反馈”或“这道工序还没开工，不能完工”。

**车间反馈 POST 基础请求体**：

下面这些字段是浏览器提交给服务端的程序内部字段，不是页面展示文案。服务端不能信任它们，必须重新查库解析；页面、弹窗、错误提示和导出不能把这些字段名原样给用户看。

```text
version: int
requested_plan_role: adopted | baseline_best | critical_best
schedule_id: int
batch_id: str
source_table: schedule
effective_plan_role: adopted
scenario_id: null
expected_state_revision: str
event_time: datetime
created_by: str
idempotency_key: str
remark: Optional[str]
```

`requested_plan_role` 必须来自当前页面身份；服务端仍要重新解析 `PlanIdentity`，不能因为前端传了 `source_table=schedule` 就认为可以写。只要 `requested_plan_role` 不是 `adopted`，或者重新解析出的 `PlanIdentity.can_write_feedback` 不是 true，就返回 409 且不写事件。

`request_fingerprint` 不由前端填写，由服务端收到请求后重算并写入事件。`start` 额外带 `operator_id / machine_id`；`pause` 额外带 `reason_code`；`finish` 额外带 `quantity_done / quantity_scrapped`；`report_exception` 额外带 `reason_code / severity / impact_minutes / affected_machine_id / affected_operator_id / handling_status / suggest_reschedule`。路由路径仍是 `/report-exception`，只在 route 层映射到程序动作 `report_exception`。入库前必须把程序动作 `report_exception` 转成数据库 `event_type='exception'`；从数据库读出 `event_type='exception'` 返回给前端时，再转成 `action='report_exception'` 和 `action_label='报异常'`。页面、按钮、表格、弹窗、导出和用户手册都不能显示 `exception` 或 `report_exception`，只能显示“报异常”。注意这里的 `event_type='exception'` 是现场事件动作，不能直接拿现场状态的 `exception -> 异常中` 映射来显示；状态中文名和动作中文名必须分开。

**计划和现场实际复盘路由**：

```text
GET /reports/execution-review?version=&batch_id=&date_from=&date_to=
GET /reports/execution-review/export?version=&batch_id=&date_from=&date_to=
```

第一版只做报表入口。资源派工页如需入口，只跳转到 `/reports/execution-review`，不新增 `/scheduler/execution-review` 路由；后续如果要做调度域内复盘页，必须补 `web/routes/domains/scheduler/scheduler_execution_review.py` 和 `scheduler_route_registrar.py`。

**JSON 成功形状**：

成功响应里的 `action`、`state_revision`、`idempotency_reused` 等字段给程序继续操作用；页面只能显示 `action_label`、`current_status_label`、`task_card` 里的中文内容。

```text
{
  success: true,
  data: {
    event: {
      event_id: int,
      op_id: int,
      schedule_id: int,
      action: start | pause | resume | finish | report_exception,
      action_label: 开工 | 暂停 | 继续生产 | 完工 | 报异常,
      event_time: datetime,
      created_by: str,
      remark: Optional[str],
      reason_code: Optional[str],
      reason_label: Optional[str],
      severity: Optional[str],
      severity_label: Optional[str],
      impact_minutes: Optional[int],
      impact_minutes_label: Optional[str],
      affected_machine_label: Optional[str],
      affected_operator_label: Optional[str],
      handling_status_label: Optional[str],
      suggest_reschedule_label: Optional[str]
    },
    current_status: not_started | processing | paused | exception | completed,
    current_status_label: 待开工 | 生产中 | 已暂停 | 异常中 | 已完工,
    state_revision: str,
    idempotency_reused: bool,
    task_card: "必须等同 execution/data.tasks[] 的单项完整结构，不能只返回局部字段"
  }
}
```

`event.action` 在 JSON 里统一使用 `report_exception`，因为这是给程序读的稳定动作名；路由路径仍是 `/report-exception`，数据库 `event_type` 统一写 `exception`，三者只在 route/service/repository 边界做明确映射，页面按钮只显示“报异常”。如果页面要显示当前现场状态，另走 `current_status_label`；如果页面要显示最近动作，另走 `last_event_action_label`。这两个 label 不能复用同一个 `exception` 映射。

**JSON 失败形状**：

失败响应里的 `details.reason`、`details.field` 和 `details.action` 是给前端分支和测试用的程序值；`details.field_label` 是页面、弹窗和错误摘要给用户看的中文字段名；`details.action_label` 是页面、弹窗和错误摘要给用户看的中文动作名。用户只能看到 `message`、`field_label`、`action_label` 和中文下一步提示，不能看到 `reason_code`、`severity`、`expected_state_revision`、`start`、`finish`、`report_exception` 这类程序字段名或程序动作值。如果某个失败和具体动作有关，失败 JSON 必须带 `details.action_label`，例如“开工”“完工”“报异常”。

```text
{
  success: false,
  error: {
    code: "...",
    message: "...",
    details: {
      reason: not_current_official_plan | stale_state_revision | invalid_state_transition | idempotency_conflict | feedback_not_enabled | schedule_mismatch | missing_required_field | invalid_field_value | permission_denied | not_found,
      action: Optional[str],
      action_label: Optional[str],
      field: Optional[str],
      field_label: Optional[str],
      current_state_revision: Optional[str],
      expected_state_revision: Optional[str],
      can_retry: bool
    }
  }
}
```

复用 `core/infrastructure/errors.py` 的错误口径，不另造一套。`message` 必须是中文大白话，例如：

- `这道工序已经完工，不能再次开工。如确实点错，请找计划员修正。`
- `暂停前请先选择原因，比如设备问题、物料问题、质量问题。`
- `当前是模拟预览，只能查看，不能提交现场反馈。请切换到正式采用方案。`
- `现场状态刚刚变了，请刷新页面后再操作。`

常用错误：

- `1001 / 400`：参数不合法。
- `1002 / 404`：版本、批次、工序、任务、反馈记录不存在。
- `1004 / 403`：权限不足，例如当前账号不能提交现场反馈。不要用它表示“状态不允许”。
- `6003 / 409`：计划或执行事实冲突，包括当前状态不允许操作、现场状态刚变了、同一个幂等键对应的内容不一致、同一个旧状态版本已经被别的请求消费、当前查看的不是最新正式采用方案。
- `6003 / 409` 且 `details.reason=not_current_official_plan`：当前查看的不是最新正式采用方案，不能写入现场反馈。不要占用现有 `6004`，因为当前代码里 `6004` 已经表示排程锁定。
- `6004 / 409`：排程锁定。
- `6005 / 409`：资源不可用。
- `1000 / 500`：未知错误，只给通用提示，不暴露内部字段。

失败 `details.reason` 固定含义：

- `not_current_official_plan`：当前查看的不是最新正式采用方案，不能写入现场反馈。
- `stale_state_revision`：现场状态刚刚变了，用户需要刷新后重试。
- `invalid_state_transition`：当前状态不允许这个动作，例如已完工后再次开工。
- `idempotency_conflict`：同一个幂等键对应了不同内容，不写事件。
- `feedback_not_enabled`：现场反馈保护还没开启，暂不能提交。
- `schedule_mismatch`：`schedule_id / schedule_version / op_id / batch_id` 不是同一条正式计划行。
- `missing_required_field`：缺少必填内容，例如反馈人、原因、严重程度。
- `invalid_field_value`：字段值不合法，例如影响分钟数小于 0。
- `permission_denied`：权限不足。
- `not_found`：版本、工序、任务或记录不存在。

`details.reason` 到错误码和 HTTP 状态的固定矩阵：

| `details.reason` | error.code | HTTP |
|---|---:|---:|
| `missing_required_field` | `1001` | `400` |
| `invalid_field_value` | `1001` | `400` |
| `not_found` | `1002` | `404` |
| `permission_denied` | `1004` | `403` |
| `not_current_official_plan` | `6003` | `409` |
| `stale_state_revision` | `6003` | `409` |
| `invalid_state_transition` | `6003` | `409` |
| `idempotency_conflict` | `6003` | `409` |
| `feedback_not_enabled` | `6003` | `409` |
| `schedule_mismatch` | `6003` | `409` |

第一版现场反馈 POST 不使用 `schedule_locked`，因为本 roadmap 没有定义“哪一种排程锁定会禁止现场反馈”的业务规则；如果以后要使用，必须另起规则并明确触发场景。第一版也不使用 `resource_not_available`，因为开工/完工/报异常只记录现场事实，不做资源可用性重新校验；如果以后要加入资源可用性校验，再单独映射到 `6005 / 409`。

### 5.10 重排执行事实契约

**方向**：执行状态读模型 → 排程输入收集 → 算法 seed / fixed op

**拟新增只读接口**：

```text
ExecutionFactProvider.list_by_op_ids(op_ids) -> List[ExecutionFact]
```

`ExecutionFactProvider` 按 `op_id` 聚合最新现场事实，不按单个 `schedule_id` 取一版计划内的历史事实。`schedule_id / schedule_version` 只告诉我们事件发生时用户看的是哪一版正式计划；重排和复盘要读取工序当前事实时，都以 `op_id` 为主线。

**返回结构**：

```text
ExecutionFact
- op_id
- batch_id
- actual_status: not_started | processing | paused | exception | completed
- actual_start_time: Optional[datetime]
- actual_end_time: Optional[datetime]
- actual_machine_id: Optional[str]
- actual_operator_id: Optional[str]
- last_event_schedule_version: Optional[int]
- last_event_schedule_id: Optional[int]
- state_revision: str
```

没有执行事件的 `not_started` 工序不能伪造当前 `Schedule.id`。`last_event_schedule_id / last_event_schedule_version` 只有在确实存在执行事件时才有值。

**`ScheduleRunInput` 扩展字段**：

```text
execution_facts
execution_fixed_op_ids
execution_completed_op_ids
execution_seed_results
execution_snapshot_revision
execution_snapshot_op_ids
```

**规则**：

- `reschedule-minimum-execution-guardrails` 只落地开工/完工上线后的最小安全补洞：已开工默认固定、已完工不再排、后续工序不能早于真实完工时间、落库前不把已经发生的现场状态覆盖回计划状态。它不负责候选比较、多起点、局部搜索、图排程统一快照，也不负责 scenario 保存/发布的快照复算。
- `reschedule-respects-execution-facts` 才落地完整执行事实接入：候选比较、多起点、局部搜索、优化器、图排程 ready queue、普通重排、scenario 保存和 scenario 发布都必须使用同一批执行事实快照，并保存或复算 `execution_snapshot_revision / execution_snapshot_op_ids`。
- 已完工：在 input collector 阶段从 `reschedulable_operations` 删除；同时把实际完工时间作为下游最早开始约束，确保后续工序不能早于真实完工时间。
- 已开工/暂停：作为 `execution_fixed_op_ids / execution_seed_results` 固定输入传给算法，不复用 freeze window 的含义；freeze window 仍表示排程冻结，execution fixed seed 表示现场已经发生。图排程链路也要接入同一批 fixed / seed 输入，不能只改普通排程。
- 异常中：普通自动重排默认返回 409 并提示计划员先处理异常；完整的异常算法接入在 `reschedule-respects-execution-facts` 中补齐。
- 没有预计剩余工时时，第一版按计划剩余时间估算。
- 候选比较、多起点、局部搜索、优化器和图排程 ready queue 都必须使用同一批执行事实，不能只让主流程尊重现场事实而让候选或图排程继续移动现场已经发生的工序。
- `execution_seed_results` 是执行事实进入算法的统一合并点：来源包含现场已开工/暂停的固定任务，以及必要时从 freeze window 继承的冻结任务；每条 seed 都必须带 `seed_source=execution_fact | freeze_window` 或等价来源标记，避免后续排查时分不清“现场已经发生”和“排程冻结”。
- freeze seed 和 execution seed 合并后必须按同一套冲突规则检查：如果同一个 `op_id` 同时来自现场事实和冻结窗口，以现场事实为准；如果两边时间或资源冲突，返回中文错误并拒绝落库，不静默择一。
- `simulate=True` 的校验也必须读取执行快照，但只做冲突提示和返回校验结果，不写 `Schedule / ScheduleHistory / ScheduleVersionSeq`，也不更新 scenario 的执行快照。scenario save/publish 和普通落库才需要保存或复算快照。
- 排程开始时记录 `execution_snapshot_revision` 和同一批 `execution_snapshot_op_ids`，并把它们写入 `ScheduleHistory.result_summary`。`result_summary` 里还要写 `execution_snapshot_op_count`，以及 op_id 清单摘要或完整清单位置，不能只写一个 hash。
- scenario 保存时也要保存 `execution_snapshot_revision`、`execution_snapshot_op_ids` 和 op_id 数量。发布 scenario 时必须用保存时同一批 op_id 重新复算；如果现场状态变化，返回 409，不写 `Schedule / ScheduleHistory`。
- 所有生成新正式计划的入口都要检查 `execution_snapshot_revision`，包括普通重排和 scenario publish。落库或发布前重新检查 revision；如果现场状态变化，本次排程或发布失败，返回 409，不写 `Schedule / ScheduleHistory`。
- 如果算法结果和现场事实冲突，在落库前拒绝；`schedule_persistence` 还要做最后防线，不允许把 `processing / paused / exception / completed` 的现场状态覆盖回 `scheduled`。
- `resource-dispatch-start-finish-feedback` 只能先做好后端受控写入和页面任务卡预备；在 `reschedule-minimum-execution-guardrails` 通过前，普通用户不仅看不到或点不了开工/完工按钮，绕过页面直接 POST 也必须被服务端拒绝，默认返回 `6003 / 409`，中文提示“现场反馈保护还没开启，暂不能提交开工或完工”。完整异常重排规则在后续 `reschedule-respects-execution-facts` 里补齐。

### 5.11 数据库迁移和 repository 契约

凡是新增表或字段，都必须：

1. 更新 `schema.sql`，让新库拿到最新完整结构。
2. 新增 `core/infrastructure/migrations/v{next}.py`。
3. 更新 `core/infrastructure/migration_state.py`。
4. 更新 `core/infrastructure/migrations/__init__.py`。
5. 新增 `data/repositories/operation_execution_event_repo.py`，定义 `OperationExecutionEventRepo`，不在 service 里散写 SQL。
6. 同步更新 `detect_schema_is_current()` 的结构特征检测，新增表、字段、FK、CHECK、UNIQUE、索引列和索引唯一性都不能漏；不能只检查名字存在。
7. 补新库 schema 测试和老库迁移测试；必须覆盖“缺少 OperationExecutionEvents 时检测为非当前结构”。

`OperationExecutionEventRepo` 至少要提供这些方法：`get_event_by_id(event_id)`、`get_by_idempotency_key(idempotency_key)`、`insert_event(event_row)`、`list_events_by_op_id(op_id)`、`list_events_by_op_ids(op_ids)`、`list_latest_events_by_op_ids(op_ids)`、`list_latest_exception_events_by_op_ids(op_ids)`、`aggregate_states_by_op_ids(op_ids)`。如果实现时选择把聚合放在 service，repository 仍必须提供按 `op_ids` 批量取事件的方法，service 不能裸写 SQL。所有事件新增、按幂等键回查、按工序回查、最近异常回查，都必须走这个 repository。

调研时当前 schema 版本是 `14`。如果实现时仍是 `14`，下一次应做 `v15`；如果版本已经前进，按当时版本继续递增。

## 6. 子 feature 清单

1. **shared-plan-identity-evidence-contract**：统一读取排程结果时必须带的计划身份、证据来源和中文显示口径。
   - 所属模块：公共计划身份与证据协议。
   - 依赖：无。
   - 状态：done。
   - 对应 feature：`2026-05-27-shared-plan-identity-evidence-contract`。
   - 备注：只做公共读取协议，不提前实现派工确认或现场反馈写入。

2. **delay-diagnosis-core-service**：新增延期诊断核心服务，只读生成事实、可能线索、证据、缺口和建议动作。
   - 所属模块：延期诊断模块。
   - 依赖：`shared-plan-identity-evidence-contract`。
   - 状态：done。
   - 对应 feature：`2026-05-27-delay-diagnosis-core-service`。
   - 备注：不改算法，不写排程结果。

3. **delay-diagnosis-overdue-report-entry**：把延期诊断接到超期清单，给用户第一条能端到端看到的解释闭环。
   - 所属模块：延期诊断模块。
   - 依赖：`delay-diagnosis-core-service`。
   - 状态：done。
   - 对应 feature：`2026-05-27-delay-diagnosis-overdue-report-entry`。
   - 备注：这是本 roadmap 的最小闭环。

4. **candidate-recommendation-card**：在方案对比区域增加推荐结论卡和中文推荐原因。
   - 所属模块：方案对比模块。
   - 依赖：`shared-plan-identity-evidence-contract`。
   - 状态：done。
   - 对应 feature：`2026-05-27-candidate-recommendation-card`。
   - 备注：只做推荐结论壳和中文解释；差值卡在下一条做。

5. **candidate-summary-delta-cards**：把代表三方案做成摘要卡，并计算相对正式采用方案的总指标差值。
   - 所属模块：方案对比模块。
   - 依赖：`candidate-recommendation-card`。
   - 状态：done。
   - 对应 feature：`2026-05-27-candidate-summary-delta-cards`。
   - 备注：不做批次级明细，不做资源级明细。

6. **candidate-drilldown-empty-states**：补跳转、空状态、失败候选提示和 plan_role 不丢失验证。
   - 所属模块：方案对比模块。
   - 依赖：`candidate-summary-delta-cards`。
   - 状态：done。
   - 对应 feature：`2026-05-27-candidate-drilldown-empty-states`。
   - 备注：保留现有甘特、周计划、资源派工跳转。

7. **dispatch-plan-identity-guardrails**：资源派工页标清正式计划、对比参考方案、模拟预览，并阻止候选和模拟预览写现场反馈。
   - 所属模块：派工身份护栏。
   - 依赖：`shared-plan-identity-evidence-contract`。
   - 状态：done。
   - 对应 feature：`2026-05-27-dispatch-plan-identity-guardrails`。
   - 备注：只做提示、禁用和后端拒绝，不新增真正的确认派工写入。

8. **operation-execution-event-foundation**：新增执行事件表、repository、状态聚合服务、幂等写入和状态版本规则。
   - 所属模块：执行事件基础。
   - 依赖：`dispatch-plan-identity-guardrails`。
   - 状态：done。
   - 对应 feature：`2026-05-27-operation-execution-event-foundation`。
   - 备注：不改历史 `Schedule` 计划行；本条只完成执行事件基础，不开放普通用户现场反馈入口。

9. **resource-dispatch-start-finish-feedback**：资源派工页增加车间反馈任务卡，先支持开工和完工。
   - 所属模块：车间反馈页面。
   - 依赖：`operation-execution-event-foundation`。
   - 状态：done。
   - 对应 feature：`2026-05-27-resource-dispatch-start-finish-feedback`。
   - 备注：先跑通受控写入和页面预备，不把异常塞进同一条；最小重排护栏完成前，普通用户直接 POST 也不能写入。

10. **reschedule-minimum-execution-guardrails**：开工和完工反馈上线后，先让重排尊重最基本现场事实。
    - 所属模块：重排执行事实接入。
    - 依赖：`resource-dispatch-start-finish-feedback`。
    - 状态：done。
    - 对应 feature：`2026-05-27-reschedule-minimum-execution-guardrails`。
    - 备注：普通重排已尊重开工/完工事实，并同批放开最新正式方案的普通用户开工/完工；完整执行快照和异常重排仍留给后续条目。

11. **shop-exception-feedback**：单独支持暂停、继续、报异常、异常原因、严重程度、影响时间、影响资源、处理状态和是否建议重排。
    - 所属模块：异常反馈模块。
    - 依赖：`reschedule-minimum-execution-guardrails`。
    - 状态：done。
    - 对应 feature：`2026-05-27-shop-exception-feedback`。
    - 备注：已开放暂停、继续生产、报异常、异常字段展示、事件列表和异常中阻止普通自动重排；第 13 项继续做完整重排尊重执行事实。

12. **plan-vs-actual-review**：新增计划和现场实际复盘视图，展示开工偏差、完工偏差、暂停时长、异常原因和资源变化。
    - 所属模块：计划和现场实际复盘。
    - 依赖：`shop-exception-feedback`。
    - 状态：planned。
    - 对应 feature：未启动。
    - 备注：做完后延期解释可以升级为区分计划问题和现场问题。

13. **reschedule-respects-execution-facts**：重排输入完整接入执行事实，已完工不再排，生产中默认固定，异常中阻止自动重排，落库前检查状态版本。
    - 所属模块：重排执行事实接入。
    - 依赖：`reschedule-minimum-execution-guardrails`、`shop-exception-feedback`。
    - 状态：planned。
    - 对应 feature：未启动。
    - 备注：不再被复盘页面阻塞，但必须等执行事件、状态读模型、最小重排护栏和异常反馈完成。

14. **aps-three-gap-docs-quality-gate**：补用户说明、开发说明、回归测试清单和 Win7/offline 验收手册。
    - 所属模块：测试和 Win7 约束。
    - 依赖：`delay-diagnosis-overdue-report-entry`、`candidate-drilldown-empty-states`、`plan-vs-actual-review`、`reschedule-respects-execution-facts`。
    - 状态：planned。
    - 对应 feature：未启动。
    - 备注：收尾项，不能替代每条 feature 自己的测试。

**最小闭环**：第 3 条 `delay-diagnosis-overdue-report-entry` 做完后，用户可以从超期清单看到某个超期批次为什么晚、证据是什么、下一步去哪里看。这是风险低、能立即提升信任的第一条端到端路径。

## 7. 排期思路

默认顺序是：

```text
公共身份协议
-> 延期解释最小闭环
-> 方案对比业务化
-> 派工身份护栏
-> 执行事件基础
-> 车间反馈开工/完工
-> 重排最小现场护栏
-> 异常反馈
-> 计划和现场实际
-> 重排尊重执行事实
-> 文档和质量门禁收口
```

为什么不是先做方案对比：

- 方案对比最快能看到页面变化，但它仍需要“原因和证据”的语言体系。
- 延期解释先做，可以建立“系统为什么这么判断”的底座。
- 方案对比后做，可以复用延期解释的原因码、证据、链接口径。

为什么车间反馈放后面：

- 它要新增表、迁移、repository、写入服务、状态流转、幂等、审计、误操作保护。
- 它会影响后续重排。
- 如果没有派工身份护栏，候选方案或 scenario 很容易被误写成现场事实。

如果用户只想快速改善页面观感，可以把 `candidate-recommendation-card` 提前到延期解释之前。但这会牺牲一部分解释深度，不作为默认顺序。

## 8. 观察项和待拍板问题

- `created_by` 当前没有完整登录体系。车间反馈第一版已默认使用页面必填的“反馈人”输入；后续接权限体系时再替换来源。
- 是否第一版支持“撤销开工/撤销完工”。默认本 roadmap 不直接做撤销事件，先用开工/完工确认提示、服务端状态版本校验、完整事件审计和计划员人工处理误点说明兜底；真正的 correction / reversal 另起后续 feature，不阻塞最小重排护栏完成后的普通用户按钮放开。
- 已开工未完工的剩余工时怎么算。默认建议先按计划剩余时间估算，后续再让现场填写预计剩余工时。
- 真正的“确认派工”写入要不要做。默认第一版不做，只在资源派工上下文里做身份提示、禁用和后端拒绝。
- 延期诊断第一版是否只放超期清单。默认建议先放超期清单，后续再接排产分析 Top 5 和甘特 tooltip。
- 方案对比第一版是否只展示三类代表方案。默认建议只展示代表三方案，不保存全部 3/5/7 明细。
- 原 explore 文档顶部已经标注后半路线草案被本 roadmap 覆盖；若后续继续维护，可用 `cs-explore update` 清理旧行号和旧字段名。
- 如果后续要把延期诊断结果缓存成 `ScheduleDiagnosisSnapshot`，要先确认是否真的有历史复现或性能压力；第一版先在返回结果里带 `DiagnosisTraceMeta`，不急着新增持久化表。

## 9. 变更日志

- 2026-05-25：从 `.codestable/compound/2026-05-23-explore-aps-three-gap-directions.md` 拆出局部 roadmap；整合 16 个 Subagent 的引用链调查结果；新增主文档、items.yaml 和 Subagent 证据账本。
- 2026-05-25：按第一轮 16 个对抗性审核 Subagent 结果修正阻塞项：统一 Python 3.8 契约写法、执行状态枚举、反馈写入身份校验和 state_revision，收窄第一版路由范围，新增重排最小现场护栏，补用户可见大白话规则和每条 feature 的测试/Win7 离线验收。
- 2026-05-25：按第二轮 16 个同范围对抗性审核 Subagent 结果继续修正：拆清当前正式版本和锁定展示的边界，补执行事件跨版本事实读取、幂等指纹、数据库约束、scenario 发布执行事实检查、重排护栏输入输出边界、用户可见文案映射、复盘路由收窄、诊断追溯信息和 explore 旧口径作废提示。
- 2026-05-25：按第三轮 16 个同范围对抗性审核 Subagent 结果继续修正：`request_fingerprint` 改为服务端按完整载荷重算，`state_revision` 改为写入前后已提交事件聚合口径，补 `execution_snapshot_op_ids`、scenario 保存/发布同批 op_id 复算、异常状态流转、复盘导出固定列、离线静态资源测试和 explore superseded 状态。
- 2026-05-25：按第四轮 16 个同范围对抗性审核 Subagent 结果继续修正：补周计划页面和导出不露 `scenario_id`，补超期导出真实生成路径，补图排程 fixed/seed 关键路径，收窄非最新正式方案 POST 的错误码为 `6003 / 409`，把开工/完工放开和最小重排护栏拆清，把异常反馈同批纳入“异常中阻止普通自动重排”。
- 2026-05-25：按第五轮 16 个同范围对抗性审核 Subagent 结果继续修正：补 `web/routes/report_plan_preview.py` 进入超期导出链路，要求导出追溯表头中文化，统一 `1004 / 403` 只表示权限不足、状态冲突走 `6003 / 409`，补重排执行事实读取路径，修正开工/完工按钮预备口径，增强离线资源测试覆盖，修复 CodeStable 工具 Python 3.8 兼容，并清理用户可见的 `latest`、`ID`、`_to_` 旧表达。
- 2026-05-25：按第六轮 16 个同范围对抗性审核 Subagent 结果继续修正：补延期诊断读取物料/齐套事实源路径，写死最小重排护栏完成前普通 POST 也不能写开工/完工，并继续清理用户可见说明里的内部字段词。
- 2026-05-25：按第七轮 16 个同范围对抗性审核 Subagent 结果继续修正：补每条 item 的入口和测试命令，`EvidenceLink.source_table` 改为行级证据必填、聚合和缺数据证据可空，延期诊断导出用户表头改成“本次诊断编号 / 生成依据摘要 / 核对信息”等大白话，写死 `execution/data`、现场反馈 POST 成功/失败 JSON 形状和错误 details，补异常反馈字段固定表，并修正模拟预览、工种/供应商编号、Python 3.8 注解等会卡住落地的细节。
- 2026-05-25：按主代理归并的第八轮修复采纳记录继续修正：收紧 `source_table=schedule` 与计划身份显示的关系，去掉执行事件行里的新 `state_revision`，补幂等和并发冲突处理矩阵，补现场反馈 POST 成功事件字段、任务卡完整返回、失败 reason 到错误码映射，补重排执行事实覆盖候选比较、多起点、局部搜索、图排程 ready queue 和 scenario 保存/发布，并把旧 explore 局部草案和前端原型旧词继续标废。第八轮逐个 `agent_id` 证据不完整，证据缺口已记录在 drafts/subagent-reference-chain-ledger.md。
- 2026-05-25：按第九轮 16 个同范围对抗性审核 Subagent 结果继续修正：把执行状态里的最后事件和最近异常字段拆开，明确幂等键优先于状态版本冲突判断，给每条 roadmap item 补依赖理由，收窄最小重排护栏和完整重排边界，补资源负荷/停机影响导出文件名路径、原型离线外链扫描和用户可见旧词清理。
- 2026-05-25：按第十轮 16 个同范围对抗性审核 Subagent 结果继续修正：补资源派工公开 JSON 脱敏、执行状态字段完整性、用户可见 Excel 工作表中文名、原型页旧词清理和第十轮 Subagent 账本。
- 2026-05-25：按第十一轮 16 个同范围对抗性审核 Subagent 结果继续修正：把程序内部字段和用户可见文案分开，`execution/data` 改用 `available_actions` 并补最后事件/更新时间字段，修正最小重排和完整重排边界，清理模拟预览、候选失败原因、资源负荷工作表、原型页和 docs-quality 命令里的阻塞点。
- 2026-05-25：按第十二轮 16 个同范围对抗性审核 Subagent 结果继续修正：清理 active explore 和原型页旧词，普通用户错误提示不再暴露内部工序编号，现场反馈失败 JSON 补 `details.field_label`，现场反馈字段中文名覆盖计划身份、排程记录、模拟预览和工序编号，docs-quality 明确 Python 3.8 扫描不能只照抄固定文件。
- 2026-05-25：按第十三轮 16 个同范围对抗性审核 Subagent 结果继续修正：把前端布局 explore 标为 superseded，补执行事件 repository 的具体文件、类名和方法清单，写死 `/report-exception`、程序动作 `report_exception`、数据库 `event_type='exception'` 和页面“报异常”的转换关系，明确开工/完工按钮必须等最小重排护栏同批验收后才能对普通用户放开。
- 2026-05-25：按第十四轮同范围对抗性审核归并结果继续修正：补齐第十二/十三/十四轮变更日志，进一步清理旧 explore 和原型页过度承诺，原型当前阶段只展示开工/完工，把 `exception` 的“异常中”状态和“报异常”动作拆成不同中文映射，细化 items 里的迁移、repository、模型、报表、导出和测试文件路径，并把 Excel 手册“预览过期”旧词改为“检查结果过期”。
- 2026-05-25：按第十五轮 16 个同范围对抗性审核 Subagent 有效结果继续修正：原型页移除当前阶段复盘入口和英文时间单位，旧 explore 继续收窄第一阶段异常暗示，现场反馈失败 JSON 补 `details.action / details.action_label`，复盘导出文件名和工作表名固定为中文格式，最小重排条目补 Chrome 109 / 离线前端硬约束，Excel 通用确认错误改为“检查结果已失效”。
- 2026-05-25：按第十六轮同范围对抗性审核归并结果继续修正：原型页把“分析复盘 / 风险复盘入口”改成当前阶段能理解的结果查看说法，旧前端 explore 移除开工/完工第一阶段里的异常原因暗示，排产分析优化过程表不再直接展示内部评分串，docs-quality 质量门禁命令改用 clean proof 口径，并补第十六轮 Subagent 账本。
- 2026-05-25：按第十七轮同范围对抗性审核有效结果继续修正：旧 three-gap explore 的车间反馈草案继续收窄，当前第一阶段只保留开工、完工、查看记录；暂停、继续生产、报异常、异常原因和相关测试统一放到后续 `shop-exception-feedback`。用户同时更新后续调度口径：按合适颗粒度使用 Subagent，不再硬性固定 16 个。
- 2026-05-25：按第十八轮 5 个同范围对抗性审核 Subagent 结果继续修正：清理旧 explore 前部“第一版异常原因”和反馈人占位旧口径，明确不做完整撤销事件但普通按钮放开前要有确认提示、状态版本校验、事件审计和人工处理误点说明；补开工/完工字段中文名、必填和非法值规则；用户帮助和手册里的英文单位改成中文大白话；质量门禁 helper 修复 Python 3.8 注解风险，docs-quality 扫描清单纳入质量门禁入口和 helper。
- 2026-05-25：按第十九轮 5 个同范围对抗性审核 Subagent 结果继续修正：设备页面帮助里的 `step-by-step` 标题改成中文，并在页面说明注册测试里加入 `step-by-step` 禁词，防止用户可见帮助文案回退。
- 2026-05-25：按第二十轮 2 个同范围最终复审 Subagent 结果确认：用户可见大白话、路线图/items/账本/旧 explore 一致性、接口字段、错误码、依赖和测试命令均无阻塞项；当前路线图可进入后续 feature-design。
- 2026-05-25：补齐三类差距方向的 draft requirement 引用，并同步刷新 `ui-gantt` 架构文档里的模拟预览用户可见口径；路线图实施拆解不变。
- 2026-05-27：完成 `dispatch-plan-identity-guardrails`。资源派工页、data 和 Excel 导出会用中文标清当前正式、历史正式、对比参考和模拟预览，并锁住本阶段不新增确认派工写入、不新增确认派工表、不产生确认派工副作用。
- 2026-05-27：完成 `resource-dispatch-start-finish-feedback`。资源派工页新增现场反馈任务卡和受控开工/完工写入；普通用户在最小重排护栏完成前仍默认不能提交，直接 POST 返回中文 409/6003；测试专用开关只在 TESTING=True 下生效，并补普通 data 递归脱敏、设备匹配、数量边界和成功返回结构测试。
- 2026-05-27：完成 `reschedule-minimum-execution-guardrails`。普通重排会读取开工/完工执行事实，已完工工序不再进待排集合，生产中工序保留实际开始和实际资源，落库前复查现场状态版本；如果最终校验失败，`Schedule`、`ScheduleHistory` 和 `ScheduleVersionSeq` 一起回滚；最新正式方案普通用户开工/完工按钮和直接 POST 已放开，候选、模拟预览、历史正式和非最新正式仍拒绝写入。
