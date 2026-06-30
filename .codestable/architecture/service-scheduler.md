---
doc_type: architecture
slug: service-scheduler
scope: core/services/scheduler 排产调度模块的内部结构现状——对外接口面、已分包子系统、根目录业务族、排产主链数据流、内部依赖方向与已知结构张力
summary: 占 core/services 约 70% 的排产巨型模块的系统地图,记录其子包划分、业务族、枢纽文件和 run↔summary 包级循环依赖等现状
status: current
created: 2026-06-28
last_reviewed: 2026-06-30
tags: [scheduler, core, service, 排产, architecture]
depends_on: []
implements: []
---

# 排产调度模块(scheduler)架构现状

> 状态:CodeStable 现状地图(只记现状,不含改进方案;治理路径见后续 roadmap / refactor)
> 锚点根目录:`core/services/scheduler/`

## 1. 定位与规模

`core/services/scheduler/` 是 APS 的排产核心,也是全仓最大的单一模块:**约 43628 行 / 206 个 Python 文件**,占整个 `core/services/` 约 **70%**。它对上承接 web 层的排产请求,对下编排算法层(`core.algorithms`)、基础资料服务(equipment / material / personnel / process)、数据访问层(`data/repositories`),产出正式排产版本、甘特视图、资源派工、周计划、报表底数和现场执行事实。

模块内部已切出 5 个子包(`run/`、`summary/`、`analysis/`、`graph/`、`config/`),但仍有 **79 个业务文件直接平铺在根目录**(约占文件数 38%),按业务族聚集而未成包——这是理解本模块结构时最需要先建立的一张图(见 §3、§5)。

## 2. 对外接口面

对外公开入口集中在 `core/services/scheduler/__init__.py:18-57`,采用 **惰性 `__getattr__` 转出**(`_EXPORTS` 映射 + `__all__`),共 **13 个 Service**:

| Service | 来源文件 | 职责 |
|---|---|---|
| `ScheduleService` | `schedule_service.py`(根) | 排产运行总门面(抢锁、收输入、编排、持久化) |
| `BatchService` | `batch_service.py`(根) | 批次(生产订单)主数据 |
| `CalendarService` | `calendar_service.py`(根) | 工作日历 |
| `ConfigService` | `config/config_service.py`(**唯一来自子包**) | 排产策略配置门面 |
| `GanttService` | `gantt_service.py`(根) | 甘特视图任务/资源负荷装配 |
| `GanttAdjustmentDraftService` / `…ValidationService` / `…ScenarioService` / `…PublishService` | `gantt_adjustment_*`(根) | 甘特手工调整草稿→校验→场景→发布 |
| `ResourceDispatchService` / `…ActualRecordService` / `…ExecutionService` | `resource_dispatch_*`(根) | 资源派工视图、实际记录、执行态 |
| `OperationExecutionFeedbackService` | `operation_execution_feedback_service.py`(根) | 现场执行反馈/事实写入 |

**关键事实**:13 个 Service 里 12 个落在根目录文件、仅 `ConfigService` 来自子包;5 个子包的 `__init__.py` 几乎不做再导出(`run/__init__.py`、`summary/__init__.py` 仅 `from __future__`,`graph/__init__.py:10` 显式 `__all__ = []`),子包对外消费一律走完整模块路径(`...scheduler.run.X`)。即:**对外是"门面在根、实现散落"**。

## 3. 内部结构总览(地图)

```
core/services/scheduler/
├── __init__.py                 13 Service 惰性门面
│
├── 【已分包子系统】(按"排产计算流程"切)
│   ├── run/      (71 文件 / ~17567 行)  排产执行引擎:收输入→跑算法→多候选→校验→持久化
│   ├── summary/  (20 文件 / ~4124 行)   结果摘要投影:原始结果→公开摘要+降级+体积护栏
│   ├── config/   (21 文件 / ~5012 行)   排产策略配置:读写/预设/校验(自洽,唯一直连 data)
│   ├── graph/    (13 文件 / ~1675 行)   可选工序图分析(NetworkX,延迟 import 隔离)
│   └── analysis/ (2 文件 / 87 行)       诊断合同事实面(休眠/兼容,见 §8)
│
└── 【根目录业务族】(按"业务对象"聚集,尚未成包)
    ├── 计划身份内核 plan_core      计划身份/版本/视图上下文(全模块共享底座)
    ├── 甘特 gantt                  甘特图渲染全链
    ├── 甘特调整 gantt_adjustment   手工调整草稿/校验/发布
    ├── 资源派工 resource_dispatch  派工单视图 + 实际记录导入
    ├── 现场事实 exec_feedback      执行快照/事实 provider/反馈(共享服务层)
    ├── 工作日历 calendar           日历引擎/管理/门面
    ├── 延误诊断 delay_diag         延误根因诊断
    ├── 批次主数据 batch            批次 CRUD/模板/导入(与排产执行主链基本分离)
    ├── 周计划导出 week_plan        Excel/打印纸面/合计行
    ├── 排产门面 sched_svc          schedule_service + history + repository_bundle
    └── 共享层 shared_util / run_shim  纯工具 + run/ 回兼垫片
```

依赖大方向:**根目录业务族 / 子包 → 共享底座(plan_core + shared_util)→ 各层(models / algorithms / infrastructure / data)**,基本单向;唯一的环在子包间 `run ⇄ summary`(见 §8)。

## 4. 五个已分包子系统

### run/ —— 排产执行引擎
- **职责**:收集排产输入 → 跑算法 / 多候选对比 → 校验产出 → 持久化。排产主链的执行核心。
- **核心文件**:`run/schedule_orchestrator.py:279` `orchestrate_schedule_run`(总编排,把算法和摘要函数作为参数**注入**)、`run/schedule_input_collector.py` `collect_schedule_run_input`(输入收集)、`run/schedule_optimizer.py` `optimize_schedule`(算法入口)、`run/schedule_persistence.py`(持久化)。内部成簇:`optimizer_*`(36)、`schedule_candidate_*`(9)、`schedule_graph_*`(5,graph 子包消费者)。
- **optimizer 现状**:`run/schedule_optimizer.py` 的 improve 主链包含多起点、GRASP/IG 批次顺序候选、VNS/acceptance 局搜和 search report。GRASP/IG 生产候选只走 `batch_order` 解码，不保留不可达的 `sgs` 候选入口。局搜的 profile 默认配置六个业务邻域，但当当前 best 是 `dispatch_mode=sgs` 时，实际 effective 邻域只使用 SGS 专用 `sgs_dispatch_rule`，报告中必须分开 configured/effective，不能让页面或 diagnostics 误以为 SGS 跑了 critical_chain/tardy_window 等业务邻域。
- **graph ready 现状**:工序图分析仍是可选基础设施。生产链遇到 `graph_ready_context` 时,会先走 GraphReady 专用候选池:保留 v1 九组图权重,并可按 `objective_aware_portfolio` 生成 v2 目标感知候选。v2 候选只改 ready 工序排序键,仍交给正式 SGS 解码,不直接写排程结果。批次交期允许为空,空交期生成 no-due 特征并后置,非空非法交期一律 fail-loud。GRASP/IG 与局搜仍不会复用批次顺序邻域处理 graph ready;需要图邻域时记录 `graph_ready_uses_graph_candidate_phase` 并跳过。
- **对外依赖**:`core.infrastructure.errors`、`core.models.enums`、`core.algorithms.*`、`core.shared.strict_parse`、`core.services.common.build_outcome`;不直接 import `data`(经 svc 句柄)。
- **对其它子包**:→ graph(13 处,**全是函数内延迟 import**)、→ summary(4 处)、→ config(3 处)。

### summary/ —— 排产结果摘要投影
- **职责**:把算法原始结果投影成"对外可见摘要 + 降级状态 + 体积护栏"的展示合同。
- **核心文件**:`summary/schedule_summary.py` `build_result_summary`(总入口)、`summary/schedule_summary_assembly.py:381` `_build_result_summary_obj`(组装枢纽)、`summary/optimizer_public_summary.py` `project_public_result_summary`(web 直连投影)、`summary/summary_size_guard.py:271` `apply_summary_size_guard`(体积护栏)。
- **对外依赖**:`core.models.enums`、`core.models.public_identifier_redaction`(脱敏)、`core.services.common.build_outcome`;无 data、无兄弟服务。
- **对其它子包**:→ config(5 处,取 `ensure_schedule_config_snapshot`)、→ run(4 处,**反向依赖**,见 §8)。
- **web 直连**:`web/routes/domains/scheduler/scheduler_analysis.py:5`、`scheduler_week_plan.py:14`。

### config/ —— 排产策略配置
- **职责**:配置读写、预设管理、字段校验/强转、活跃预设溯源。
- **核心文件**:`config/config_service.py` `ConfigService`(对外门面)、`config/config_snapshot.py` `ensure_schedule_config_snapshot`(被 run/summary 共依的跨包出口)、`config/config_field_spec.py`(包内枢纽,被引 12 次)、`config/config_page_save_service.py`(配置页保存事务)。
- **依赖现状**:`core.infrastructure.errors`、`core.shared.field_labels`、`core.services.common.safe_logging`;**唯一直连仓储的子包**——`config_service.py` import `data.repositories.config_repo.ConfigRepository`。
- **对其它子包**:**0**(完全自洽,不依赖 run/summary/graph/analysis)。
- **被重度依赖**:全仓 15 个 config/ 之外文件引用 `ConfigService`;web 三个 `scheduler_config*` 路由直连。

### graph/ —— 可选工序图分析
- **职责**:基于工序前驱关系建图、算关键路径/拓扑层/图警告。package docstring 明确"图分析是可选基础设施,import 期不得要求 NetworkX"(`graph/__init__.py:1-6`)。
- **核心文件**:`graph/analysis_service.py:14` `ScheduleGraphAnalysisService`、`graph/precedence_builder.py`(建图)、`graph/metrics.py`(指标)、`graph/nx_runtime.py` `NetworkXUnavailable`(缺失隔离闸)。
- **依赖现状**:几乎零外部依赖(仅 `graph/scoring.py` 引 `core.algorithms.greedy.dispatch.ready_queue`)。
- **唯一消费者**:run/ 的 5 个 `schedule_graph_*` 文件,其中 4 个直接函数体内延迟 import graph 子包(如 `run/schedule_graph_report.py:158-162`),贯彻"不在 import 期拉 NetworkX"。代价是 graph 的真实接入点散落在 run/ 里、不在 graph 包边界上。

### analysis/ —— 诊断合同事实面(休眠/兼容)
- **职责**:仅 `analysis/schedule_diagnostic_contract.py`,提供诊断合同构造器。
- **现状**:在 core/web 中**零 Python import**,自带 `# O23 KEEP` 注解(`analysis/schedule_diagnostic_contract.py:5-7`)说明活护栏已迁到 `web.viewmodels.scheduler_analysis_diagnostic_helpers`。占一个独立子包却不在活路径上,属"为兼容刻意保留"的事实面(tests/ 是否引用未深扫,**TODO: 待确认**)。

## 5. 根目录业务族(尚未分包)

79 个根目录业务文件按业务对象聚成 13 族 + 2 共享层。多数文件无 docstring,职责按文件名 + import 结构推断;每族"可否独立成包"判断依据是"族内互依紧、跨族缠绕松"。

| 族 | 代表文件 | 职责 | 内聚现状 |
|---|---|---|---|
| **plan_core 计划身份内核** | `schedule_plan_query_service.py`(in-deg **9**)、`schedule_result_view_context.py`(in-deg 7)、`schedule_plan_identity_builder.py`、`version_resolution.py`(in-deg 5) | 计划身份/版本/视图上下文最底层语义 | **全模块共享底座**,被 gantt/dispatch/adjustment/exec/delay_diag 五大族单向依赖 |
| **gantt 甘特** | `gantt_service.py:44`(族内总装)、`gantt_range.py`(in-deg 6)、`gantt_tasks.py`、`gantt_critical_chain.py` | 甘特图渲染全链 | 族内自洽;纠缠点 `gantt_tasks`(被 dispatch 借)、`gantt_range`(被 plan_core 借) |
| **gantt_adjustment 甘特调整** | `gantt_adjustment_validation_service.py`、`…publish_service.py`、`…scenario_service.py` | 手工调整草稿→校验→投影→发布 | 族内链清晰;依赖 plan_core + exec_feedback + calendar |
| **resource_dispatch 资源派工** | `resource_dispatch_service.py:41`、`…rows.py`、`…execution_service.py` | 派工单(资源×工序)视图 | 与 gantt + exec_feedback 双向纠缠 |
| **resource_dispatch_actual 实际派工** | `resource_dispatch_actual_record_service.py`、`…records.py`、`…import*.py` | 实际记录录入/校验/Excel 导入 | 内聚高(6 文件成链),dispatch 大族里相对独立子簇 |
| **exec_feedback 现场事实** | `execution_fact_provider.py`、`execution_snapshot.py`、`operation_execution_feedback_*`、`operation_execution_scope_read.py`(in-deg 5) | 现场执行事实采集/反馈(契约 4.10) | **实为共享服务层**,被 adjustment/dispatch/actual 三族共依;`execution_fact_provider ↔ execution_snapshot` 已用 `TYPE_CHECKING` 拆环(`execution_snapshot.py:8`,`:103` 注释"勿上提否则 ImportError") |
| **calendar 工作日历** | `calendar_service.py`、`calendar_admin.py`、`calendar_engine.py` | 日历引擎/管理/门面 | 干净单向链,稳定底座(in-deg 4) |
| **delay_diag 延误诊断** | `schedule_delay_diagnosis_service.py`、`…clues.py`、`…utils.py` | 排产延误根因诊断 | 内聚高、只回依赖 plan_core,最干净的可独立候选之一 |
| **batch 批次主数据** | `batch_service.py`、`batch_template_ops.py`、`batch_write_rules.py`、`batch_excel_import.py`、`batch_copy.py`、`batch_query_service.py` | 批次 CRUD/模板/写规则/导入/复制 | **围绕 `batch_service.py` 形成批次主数据簇**;`batch_service.py` 同目录导入 `batch_copy` / `batch_excel_import` / `batch_template_ops` / `batch_write_rules`,并通过 `batch_template_ops` 从模板建批次;对 run/summary/graph 等排产执行族仍基本无反向耦合 |
| **week_plan 周计划导出** | `week_plan_excel.py`、`week_plan_print_sheet.py`、`week_plan_daily_summary.py` | 周计划/派工单 Excel/打印/合计 | 纯展示转换层,三文件互不 import |
| **op_edit / resource_pool / sched_svc** | `operation_edit_service.py` / `resource_pool_builder.py` / `schedule_service.py`、`schedule_history_query_service.py`、`repository_bundle.py` | 工序编辑 / 资源池构建 / 排产运行门面 | op_edit 孤立;resource_pool 只被 sched_svc 用;sched_svc 是 run+summary 引擎对外门面 |

**两个横切共享层**:
- **shared_util(纯工具)**:`_sched_display_utils.py`(in-deg **8**,二号枢纽)、`_sched_utils.py`、`number_utils.py`、`degradation_messages.py`、`history_summary_parser.py`——跨族纯函数(显示格式化/安全整数/降级文案)。
- **run_shim(回兼垫片)**:`schedule_optimizer.py`、`schedule_orchestrator.py`、`schedule_persistence.py`、`schedule_input_*.py`、`freeze_window.py` 等 **7 个薄 re-export shim**,把旧路径重定向到已存在的 `run/` 子包(逻辑已下沉、入口还留根目录,见 §8)。

**跨族枢纽文件(被多族共依,分包时的"胶水")**:`schedule_plan_query_service`(in-deg 9,5 族共依)、`_sched_display_utils`(8,4 族)、`schedule_result_view_context`(7)、`gantt_range`(6)、`operation_execution_scope_read`(5)、`version_resolution`(5)、`gantt_tasks`(gantt↔dispatch 纠缠点)。

## 6. 排产主链数据流

入口在根目录 `ScheduleService`(**不在子包内**):

1. **触发**:`schedule_service.py:197` `run_schedule()` 抢 `_RUN_SCHEDULE_LOCK` 单实例锁 → `:226` `_run_schedule_impl()`。
2. **收输入(→run/)**:`collect_schedule_run_input`(批次归一/窗口归一/可重排状态/执行护栏/算法输入构建)→ `ScheduleRunInput`。
3. **编排(→run/)**:`schedule_service.py:321` 调 `run/schedule_orchestrator.py:279` `orchestrate_schedule_run`,把 `optimize_schedule` 和 `build_result_summary` 作为**函数参数注入**(`optimize_schedule_fn` / `build_result_summary_fn`)——这是 run 内部解耦的关键先例。
4. **选解(run/)**:`_run_plan_selection` →(关候选)`optimize_schedule`(调 `core.algorithms` 的 `GreedyScheduler`/`StrategyFactory`)/(开候选)`run_candidate_comparison` + `_graph_analysis_for_summary`(经 `schedule_graph_*` 延迟拉 graph 子包)。
5. **校验产出(run/)**:`build_validated_schedule_payload` → `ValidatedSchedulePayload`。
6. **投影摘要(→summary/)**:调注入的 `build_result_summary`(`summary/schedule_summary.py`,内部装配/降级/护栏)。
7. **持久化(run/,非 simulate)**:`persist_schedule` 在事务内分配版本并落库。
8. **返回**:组 `result` dict 回 web。

一句话链:`ScheduleService.run_schedule`(根)→ `collect_schedule_run_input`(run)→ `orchestrate_schedule_run`(run)→ {`optimize_schedule` + `core.algorithms` | `run_candidate_comparison`→graph(延迟)} → `build_validated_schedule_payload`(run)→ `build_result_summary`(summary)→ `persist_schedule`(run)。

## 7. 跨层与依赖方向现状

- **跨层单向、零反向依赖**:scheduler 不反依赖 web;`core.models` 干净(只依赖 dataclasses + ValidationError);`core.algorithms` 不依赖 service(算法层纯计算);`core.infrastructure`/`core.shared` 是纯叶子。web 层经 `ScheduleService` 等门面消费 scheduler,不绕过它直接动子包内部(`web→core.services` 214 次 vs `web→data` 仅 1 次)。
- **服务间无环 DAG**:`report → scheduler → {equipment → process/personnel, process, personnel, material} → common(叶子)`。
- **config 自带持久化通道**:config/ 是唯一直连 `data` 仓储的子包,抽象层比其它纯计算/投影子包"厚"。
- **graph 接入靠延迟 import**:静态调用图(symbol_locator / checkup)对 run→graph 这些边标"动态/盲区",外人难从包结构看出 graph 何时被触发。

## 8. 已知结构现状与张力

> 本节只陈述现状事实与客观影响,**不含改进方案**。治理路径(断环 / 分包 / 搬迁)归后续 roadmap / refactor。

### 8.1 run ⇄ summary 包级循环依赖
- **现状**:run 与 summary 两个子包**互相顶层 import**,各 4 处:
  - run→summary:`run/schedule_orchestrator.py:7`(`SummaryBuildContext`)、`run/schedule_summary_contract.py:6`(`parse_summary_count`)、`run/schedule_candidate_persistence_models.py:8-9`(`project_public_graph_analysis`/`project_search_report`)。
  - summary→run:`summary/schedule_summary_assembly.py:9-11`(`auto_assign_failed_op_ids_from_errors`/`compact_attempts`/`missing_internal_resource_samples`)、`summary/summary_size_guard_fields.py:11`(`candidate_comparison_minimal_summary`)。
- **性质(静态)**:8 处全是模块顶层 import、相关文件均无 `TYPE_CHECKING`,故**加载期是真环**,当前不报 ImportError 仅因环切在双方的"叶子纯函数模块"上;任一叶子模块新增一条回指对面顶层的 import 即会触发"半初始化模块" ImportError。checkup 的 `cycle_count`(`callgraph/summary.json`)是**函数级 SCC**,看不到此**包级**环——这是它长期潜伏的原因。
- **性质(动态实测)**:8 条跨包边运行时**全部真实触发(函数体执行),无死边**。拓扑是**嵌套回调**——run 编排时调注入的 `build_result_summary`(summary 组装),summary 组装内部再回调 run 的 4 个纯函数;stub 掉 summary 时反向边一条不触发,证明反向边只从 summary 内部发起,不是两包对穿。被反借的 4 个 run 符号**均为无副作用纯函数**(算缺资源 op / 压缩 attempts / 取样本 / 最小化候选对比),summary 当工具借用。
- **客观影响**:运行时无死锁/正确性风险;张力集中在**分层与可维护性**——summary(数据流下游)反向依赖 run(上游)的内部模块,且加载期真环随时可被一次普通改动引爆。
- **全景定位(2026-06-28 全仓普查)**:本环在循环依赖普查中编号 **A1**——实为 `scheduler 根 ⇄ run ⇄ summary ⇄ config` 的**四方**硬加载期目录环的一段(不是孤立的 run⇄summary 两方环),与 infrastructure/models(A2)等共 **6 个硬加载期目录环**并列。完整三类口径 + Codex 对抗核验见 `.codestable/audits/2026-06-28-circular-imports/`;复扫工具 `python3 -m tools.scan_import_cycles`。

### 8.2 分包标准不统一,79 文件平铺根目录
- 已按"计算流程"切出 run/summary/graph/config,但 resource / schedule / gantt 等多组**业务族**仍平铺根目录,每族体量都不小。一半按流程分包、一半按业务族平铺,目录可读性与心智负担偏高。

### 8.3 batch 族与排产执行主链基本分离
- `batch` 族 6 文件(批次主数据 CRUD/模板/导入/复制)通过 `batch_service.py` 串起多个同目录 helper,不是静态调用图里的全孤岛。它本质仍是"批次主数据服务":主要依赖 `data.repositories`+`core.models`,没有被 run/summary/graph 这些排产执行族反向调用,归在 scheduler 内属历史归类。

### 8.4 run_shim 双入口
- 根目录 7 个 `schedule_*` 是 re-export 垫片(逻辑已在 `run/` 子包),导致同一能力既能从 `scheduler.run.X` 也能从 `scheduler.X` 进入;新代码该走哪个入口当前无文档约定(**TODO: 待确认是否有约定文件**)。外部(web/report/tools/tests)仍大量 import 根路径符号。

### 8.5 config_snapshot 是隐性跨包公共依赖
- `config/config_snapshot.py` `ensure_schedule_config_snapshot` 被 run(2 处)和 summary(5 处)直接钻进 config 子包取用,共 8 处。它已成事实上的"公共契约层"却物理埋在 config/ 内,config 内部重构会同时震动 run + summary。

## 9. 相关文档

- `.codestable/architecture/ARCHITECTURE.md` —— 项目架构总入口。
- `.codestable/audits/2026-06-28-circular-imports/` —— 全仓循环依赖普查(本模块 run⇄summary 即其中 A1 四方环),三类口径 + Codex 对抗核验。
- `.codestable/architecture/ui-gantt.md` —— 甘特图结果查看页面(前端职责/缩放/只读边界),与本文档的后端 service 视角互补。
- `core/services/scheduler/__init__.py` —— 本模块对外 13 个 Service 的惰性门面。
