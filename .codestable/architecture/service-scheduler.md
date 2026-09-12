---
doc_type: architecture
slug: service-scheduler
scope: core/services/scheduler 排产调度模块的内部结构现状——对外接口面、已分包子系统、根目录业务族、排产主链数据流、内部依赖方向与已知结构张力
summary: 排产巨型模块系统地图，记录子包/业务族/主链及 A1/A3 解耦后的单向依赖；区分目录 SCC、父包感知文件 SCC 与纯显式文件 SCC
status: current
created: 2026-06-28
last_reviewed: 2026-09-13
tags: [scheduler, core, service, 排产, architecture]
depends_on: []
implements: []
---

# 排产调度模块(scheduler)架构现状

> 状态:CodeStable 现状地图(只记现状,不含改进方案;治理路径见后续 roadmap / refactor)
> 锚点根目录:`core/services/scheduler/`
> 2026-09-12 本次只增补 §10 的算法合同；前文规模、引用计数及 SCC 数字保留各自历史统计口径，未重新普查，不代表本次源码规模。

## 1. 定位与规模

`core/services/scheduler/` 是 APS 的排产核心,也是全仓最大的单一模块:**43886 行 / 219 个 Python 文件**。它对上承接 web 层的排产请求,对下编排算法层(`core.algorithms`)、基础资料服务(equipment / material / personnel / process)、数据访问层(`data/repositories`),产出正式排产版本、甘特视图、资源派工、周计划、报表底数和现场执行事实。

模块内部现有 7 个子包(`run/`、`summary/`、`analysis/`、`graph/`、`config/`、`execution/`、`contracts/`),根目录仍有 **79 个 Python 文件**；其中一部分已是指向 run/execution/低层叶子的兼容入口，不能再把“根目录文件数”直接等同于“根目录实现数”。

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

**关键事实**:13 个 Service 里 12 个落在根目录文件、仅 `ConfigService` 来自子包；7 个子包的 `__init__.py` 都不做大规模再导出，`execution/` 与 `contracts/` 的 `__init__.py` 保持空文件，避免扩大父包初始化链。子包能力通过完整模块路径消费。即:**Service 门面仍在根，但执行事实与中立合同实现已有明确叶子归属**。

## 3. 内部结构总览(地图)

```
core/services/scheduler/
├── __init__.py                 13 Service 惰性门面
│
├── 【已分包子系统】
│   ├── run/       (73 文件 / 17686 行)  排产执行引擎:收输入→跑算法→多候选→校验→持久化
│   ├── summary/   (20 文件 / 3520 行)   结果摘要组装:公开摘要+降级+体积护栏
│   ├── config/    (21 文件 / 5011 行)   排产策略配置:读写/预设/校验(自洽,唯一直连 data)
│   ├── graph/     (13 文件 / 1714 行)   可选工序图分析(NetworkX,延迟 import 隔离)
│   ├── analysis/  (2 文件 / 87 行)      诊断合同事实面(休眠/兼容,见 §8)
│   ├── execution/ (5 文件 / 513 行)     执行事实/快照/计划 scope/派工执行态叶子
│   └── contracts/ (6 文件 / 812 行)     summary/run 共用 DTO、计数解析与公开投影叶子
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

依赖大方向:**根目录门面/业务族 → summary → run → config/execution/contracts，summary 也单向依赖 config/contracts；底层再指向 models / algorithms / infrastructure / data**。A1 后 scheduler 根、config、run、summary 均不在 hard 目录 SCC 中。

## 4. 七个已分包子系统

### run/ —— 排产执行引擎
- **职责**:收集排产输入 → 跑算法 / 多候选对比 → 校验产出 → 持久化。排产主链的执行核心。
- **核心文件**:`run/schedule_orchestrator.py:279` `orchestrate_schedule_run`(总编排,把算法和摘要函数作为参数**注入**)、`run/schedule_input_collector.py` `collect_schedule_run_input`(输入收集)、`run/schedule_optimizer.py` `optimize_schedule`(算法入口)、`run/schedule_persistence.py`(持久化)。内部成簇:`optimizer_*`(36)、`schedule_candidate_*`(9)、`schedule_graph_*`(5,graph 子包消费者)。
- **optimizer 现状**:`run/schedule_optimizer.py` 的 improve 主链包含多起点、GRASP/IG 批次顺序候选、VNS/acceptance 局搜和 search report。GRASP/IG 生产候选只走 `batch_order` 解码，不保留不可达的 `sgs` 候选入口。局搜的 profile 默认配置六个业务邻域，但当当前 best 是 `dispatch_mode=sgs` 时，实际 effective 邻域只使用 SGS 专用 `sgs_dispatch_rule`，报告中必须分开 configured/effective，不能让页面或 diagnostics 误以为 SGS 跑了 critical_chain/tardy_window 等业务邻域。
- **graph ready 现状**:工序图分析仍是可选基础设施。生产链遇到 `graph_ready_context` 时,会先走 GraphReady 专用候选池:保留 v1 九组图权重,并可按 `objective_aware_portfolio` 生成 v2 目标感知候选。v2 候选只改 ready 工序排序键,仍交给正式 SGS 解码,不直接写排程结果。批次交期允许为空,空交期生成 no-due 特征并后置,非空非法交期一律 fail-loud。GRASP/IG 与局搜仍不会复用批次顺序邻域处理 graph ready;需要图邻域时记录 `graph_ready_uses_graph_candidate_phase` 并跳过。
- **对外依赖**:`core.errors`/既有 infrastructure 兼容错误入口、`core.models.enums`、`core.algorithms` 根 façade，以及 `core.algorithm_contracts.*` / `core.algorithm_runtime.*` 中立叶子、`core.shared.strict_parse`、`core.services.common.build_outcome`;不直接 import `data`(经 svc 句柄)。
- **对其它子包**:→ graph(13 处,**全是函数内延迟 import**)、→ execution(6 处)、→ contracts(4 处)、→ config(3 处)；→ summary 已为 0。

### summary/ —— 排产结果摘要投影
- **职责**:把算法原始结果投影成"对外可见摘要 + 降级状态 + 体积护栏"的展示合同。
- **核心文件**:`summary/schedule_summary.py` `build_result_summary`(总入口)、`summary/schedule_summary_assembly.py:381` `_build_result_summary_obj`(组装枢纽)、`summary/optimizer_public_summary.py` `project_public_result_summary`(web 直连投影)、`summary/summary_size_guard.py:271` `apply_summary_size_guard`(体积护栏)。
- **对外依赖**:`core.models.enums`、`core.services.common.build_outcome`；公开标识脱敏与 projection 实现在 contracts 叶子。
- **对其它子包**:→ config(5 处)、→ contracts(22 处)、→ run(4 处)。summary→run 仍是现有 helper 调用，但 run→summary 已清零，因此是单向依赖，不再成环。
- **web 直连**:`web/routes/domains/scheduler/scheduler_analysis.py:5`、`scheduler_week_plan.py:14`。

### config/ —— 排产策略配置
- **职责**:配置读写、预设管理、字段校验/强转、活跃预设溯源。
- **核心文件**:`config/config_service.py` `ConfigService`(对外门面)、`config/config_snapshot.py` `ensure_schedule_config_snapshot`(被 run/summary 共依的跨包出口)、`config/config_field_spec.py`(包内枢纽,被引 12 次)、`config/config_page_save_service.py`(配置页保存事务)。
- **依赖现状**:`core.infrastructure.errors`、`core.shared.field_labels`、`core.services.common.safe_logging`;**唯一直连仓储的子包**——`config_service.py` import `data.repositories.config_repo.ConfigRepository`。
- **对其它子包**:**0**(完全自洽,不依赖 run/summary/graph/analysis)。
- **被重度依赖**:全仓 15 个 config/ 之外文件引用 `ConfigService`;web 三个 `scheduler_config*` 路由直连。

### execution/ —— 现场执行事实叶子
- **职责**:集中 `ExecutionFact`/provider、执行快照、计划身份 scope 读取和派工行执行态 enrichment。
- **核心文件**:`execution/execution_fact_provider.py`、`execution/execution_snapshot.py`、`execution/operation_execution_scope_read.py`、`execution/resource_dispatch_execution_enrichment.py`。
- **依赖现状**:只依赖 models 与 execution event repository，不反向依赖 scheduler 根、run、summary、config。provider 提供 `positive_op_ids`，snapshot 单向依赖 provider；旧有 provider⇄snapshot 的函数内 import 已消失。
- **兼容面**:根目录四个同名模块仅显式 re-export，同一符号在旧/新路径满足对象 identity。

### contracts/ —— run/summary 中立合同叶子
- **职责**:集中 `SummaryBuildContext` 等摘要 DTO、summary count parser、graph/optimizer 公开投影与安全过滤。
- **核心文件**:`contracts/schedule_summary_types.py`、`summary_count_parse.py`、`graph_public_summary.py`、`optimizer_public_safety.py`、`optimizer_public_search_report.py`。
- **依赖现状**:只依赖 models/common 等更低层能力，不反向依赖 root/run/summary/config；run 与 summary 可同时单向消费。
- **兼容面**:summary 下五个旧模块仅显式 re-export，旧/新路径对象 identity、签名、dataclass 字段/默认值由 A1 边界测试锁定。

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
| **exec_feedback 现场事实** | `execution/` 实现、根目录四个兼容 wrapper、`operation_execution_feedback_*` | 现场执行事实采集/反馈(契约 4.10) | 共享服务叶子被 adjustment/dispatch/actual/run 单向依赖；provider→scope/enrichment、snapshot→provider，不再靠 `TYPE_CHECKING` 或函数内 import 拆环 |
| **calendar 工作日历** | `calendar_service.py`、`calendar_admin.py`、`calendar_engine.py` | 日历引擎/管理/门面 | 干净单向链,稳定底座(in-deg 4) |
| **delay_diag 延误诊断** | `schedule_delay_diagnosis_service.py`、`…clues.py`、`…utils.py` | 排产延误根因诊断 | 内聚高、只回依赖 plan_core,最干净的可独立候选之一 |
| **batch 批次主数据** | `batch_service.py`、`batch_template_ops.py`、`batch_write_rules.py`、`batch_excel_import.py`、`batch_copy.py`、`batch_query_service.py` | 批次 CRUD/模板/写规则/导入/复制 | **围绕 `batch_service.py` 形成批次主数据簇**;`batch_service.py` 同目录导入 `batch_copy` / `batch_excel_import` / `batch_template_ops` / `batch_write_rules`,并通过 `batch_template_ops` 从模板建批次;对 run/summary/graph 等排产执行族仍基本无反向耦合 |
| **week_plan 周计划导出** | `week_plan_excel.py`、`week_plan_print_sheet.py`、`week_plan_daily_summary.py` | 周计划/派工单 Excel/打印/合计 | 纯展示转换层,三文件互不 import |
| **op_edit / resource_pool / sched_svc** | `operation_edit_service.py` / `resource_pool_builder.py` / `schedule_service.py`、`schedule_history_query_service.py`、`repository_bundle.py` | 工序编辑 / 资源池构建 / 排产运行门面 | op_edit 孤立;resource_pool 只被 sched_svc 用;sched_svc 是 run+summary 引擎对外门面 |

**两个横切共享层**:
- **shared_util(纯工具/兼容入口)**:`_sched_display_utils.py`(in-deg **8**)、`_sched_utils.py`、`history_summary_parser.py`；`number_utils.py` 与 `degradation_messages.py` 已是分别指向 `core.shared` 和 `core.models` 的单向兼容入口。
- **compat shim(回兼垫片)**:原有 **7 个** `schedule_*`/`freeze_window` 薄入口指向 run；新增 **4 个** execution 同名入口指向 execution。兼容层只从新实现导出，不允许新叶子反向引用 wrapper。

**跨族枢纽文件(被多族共依,分包时的"胶水")**:`schedule_plan_query_service`(in-deg 9,5 族共依)、`_sched_display_utils`(8,4 族)、`schedule_result_view_context`(7)、`gantt_range`(6)、`execution/operation_execution_scope_read`、`version_resolution`(5)、`gantt_tasks`(gantt↔dispatch 纠缠点)。

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

- **主要跨层方向仍清楚，但并非全仓零反向依赖**:scheduler 不反依赖 web；算法层不依赖 service，并已形成 `algorithms → greedy → dispatch → algorithm_contracts/algorithm_runtime` 主方向，runtime 只单向依赖 contracts；web 主要经 `ScheduleService` 等门面消费 scheduler。基础层 A2 已改成 `migrations → infrastructure → models → shared → core.errors` 单向结构：models/shared 不再反借 infrastructure，migrations 复用父层事件合同但 infrastructure 不再反借 child common；实现提交 `d6d41e1a` 已完成前后工作区均干净的 19 步完整门禁。
- **服务主链大体单向，但目录商图并非全 DAG**:`report → scheduler → {equipment → process/personnel, process, personnel, material}` 是主要方向；同时现存 A5 `plugins⇄services/common`、A6 `report⇄report/exporters` 等目录 SCC，须与“主要调用方向”分开表述。
- **config 自带持久化通道**:config/ 是唯一直连 `data` 仓储的子包,抽象层比其它纯计算/投影子包"厚"。
- **graph 接入靠延迟 import**:静态调用图(symbol_locator / checkup)对 run→graph 这些边标"动态/盲区",外人难从包结构看出 graph 何时被触发。

## 8. 已知结构现状、已解除张力与剩余张力

> 本节只陈述现状事实与客观影响,**不含改进方案**。治理路径与执行证据归 roadmap / refactor。

### 8.1 A1 已解除：root/config/run/summary 改为单向依赖
- **起点**:A1 原为 scheduler 根、config、run、summary 四目录 hard SCC，共 49 条圈内规范化模块边；其中 run→summary 与 summary→run 各 4 条。
- **当前方向**:run 原消费的 `SummaryBuildContext`、count parser、graph/search public projection 已归入 `contracts/`，run→summary 为 0；summary→run 的 4 个既有纯 helper 调用保留为单向边。config/run/summary 不再反借根目录 number/degradation 实现，run 直接消费 `execution/`。
- **兼容边界**:旧 root/summary 路径仍通过显式 re-export 可用，旧新符号为同一对象；`execution/__init__.py`、`contracts/__init__.py` 不做聚合导出。没有用函数内 import、`TYPE_CHECKING` 或动态 `__getattr__` 隐藏结构边。
- **静态终态(2026-07-12)**:生产 761 模块、5 个 hard 目录 SCC；含测试 1455 模块、6 个 hard 目录 SCC。A1 四目录均不在任何 hard SCC；其他 SCC 的成员和圈内边逐项未变，production / with-tests unresolved 分别仍为 6 / 44。父包感知 hard 文件 SCC 仍为 9，纯显式 hard 文件 SCC 仍为 0。
- **基线终态**:双 v2 基线只删除各自 1 个 A1 块(每份 59 行)，未新增或改写其他 SCC；因此旧 A1 若回潮会被 `--fail-on-new-cycle` 重新阻断。行为等价由 identity、签名、正逆序新解释器 import 和 scheduler 专项测试锁定。
- **clean proof**:实现提交 `c2243cd0` 在前后工作区均干净的条件下完成 19/19 步门禁；4716 collected、unexpected failure 0，required proof 为 253 targets / 2467 nodeids。

### 8.2 A3 已解除：algorithms / greedy / dispatch 改为主链 + sibling leaves
- **当前方向**：`core.algorithms → core.algorithms.greedy → core.algorithms.greedy.dispatch` 保留 façade/执行主链；纯合同归 `core.algorithm_contracts`，共享运行时归 `core.algorithm_runtime`，后者只单向依赖前者。两个 leaf 的 `__init__.py` 都不聚合导出，也不反向依赖 algorithms/services。
- **兼容边界**：根 `GreedyScheduler` identity、签名、`__module__` 和根 `__all__` 不变，`core/algorithms/__init__.py` 字节不变；旧日期/排序/类型/runtime 路径显式同对象 re-export。dispatch 和旧 `greedy.algo_stats` 继续保留真实执行模块 globals，既有 monkeypatch 路径仍有效。
- **静态终态（2026-07-13）**：生产 779 模块 / 3 hard 目录 SCC，含测试 1475 模块 / 4 SCC；A3 消失，A4/A5/A6/tests 记录不变，unresolved 仍为 6/44。A3 相关父包感知文件圈从 21/94 严格缩为 8/24；hard/runtime 文件 SCC 总数仍为 9/13，纯显式口径仍为 0/4。
- **证明边界**：调用图两个独立候选逐文件确定；7329 个旧 callable 全映射，新增仅 8 个 context adapter callable。实现已提交为 `f422b88c`，并在该固定 HEAD 的干净工作区前后完成无缓存、无续跑 19/19 步门禁；4731 collected、unexpected failure 0，manifest=`passed`。该 clean proof 只绑定此实现提交。

### 8.3 分包标准不统一,79 文件平铺根目录
- 已按"计算流程"切出 run/summary/graph/config,但 resource / schedule / gantt 等多组**业务族**仍平铺根目录,每族体量都不小。一半按流程分包、一半按业务族平铺,目录可读性与心智负担偏高。

### 8.4 batch 族与排产执行主链基本分离
- `batch` 族 6 文件(批次主数据 CRUD/模板/导入/复制)通过 `batch_service.py` 串起多个同目录 helper,不是静态调用图里的全孤岛。它本质仍是"批次主数据服务":主要依赖 `data.repositories`+`core.models`,没有被 run/summary/graph 这些排产执行族反向调用,归在 scheduler 内属历史归类。

### 8.5 兼容 shim 双入口
- 根目录 7 个 `schedule_*`/`freeze_window` 与 4 个 execution wrapper 保留旧 import 路径；仓内生产代码直接依赖 `scheduler.run.*` / `scheduler.execution.*`，旧根路径只服务 tests/外部兼容消费。wrapper 不得承载业务实现或反向被新叶子依赖。

### 8.6 config_snapshot 是隐性跨包公共依赖
- `config/config_snapshot.py` `ensure_schedule_config_snapshot` 被 run(2 处)和 summary(5 处)直接钻进 config 子包取用,共 8 处。它已成事实上的"公共契约层"却物理埋在 config/ 内,config 内部重构会同时震动 run + summary。

## 9. 相关文档

- `.codestable/architecture/ARCHITECTURE.md` —— 项目架构总入口。
- `.codestable/audits/2026-06-28-circular-imports/` —— 全仓循环依赖普查；其中 A1/A2/A3 已由独立 refactor 解除，A4/A5/A6/tests 继续按 roadmap 治理。
- `.codestable/refactors/2026-07-10-scheduler-a1-dependency-decoupling/` —— A1 scan/design/checklist/apply 证据。
- `.codestable/architecture/ui-gantt.md` —— 甘特图结果查看页面(前端职责/缩放/只读边界),与本文档的后端 service 视角互补。
- `core/services/scheduler/__init__.py` —— 本模块对外 13 个 Service 的惰性门面。

## 10. 算法能力与效率合同（2026-09-12 增补）

本节对应已进入当前工作区的实现，记录调度内部的职责和边界。模块测试、完整入口对照与最终门禁是不同证据；验收状态统一见 `.codestable/features/2026-09-12-algorithm-capability-efficiency/algorithm-capability-efficiency-acceptance.md`，本节不声明最终 HEAD 的 clean-worktree proof。实施与定向验收已完成，最终整仓门禁按用户要求未追加完成；稳定证据见[最终记录](../../evidence/algorithm-capability-efficiency/2026-09-13-final/README.md)。

### 10.1 候选总预算与搜索阶段

`run_candidate_comparison` 的所有候选共用同一个 monotonic 总截止时间。每个未运行方案从剩余总时间中取得显式份额；图准备也消耗该份额，未使用时间继续留在总池。预算组件仅用同目标、完整成功方案的实际改善和有限耗时调整下一份额，并为其他未试候选保留至少半个均分份额；未知观测保持中性，不预测下一候选收益。SGS 不能自行延长截止时间。`SearchBudget` 是冻结的候选预算合同，`optimize_schedule(..., search_budget=None)` 接受它，并同时受配置的单次优化上限约束。首次正式基线先于可选搜索；多起点、warm-start、非图构造具有阶段截点，给后续阶段保留机会，图阶段沿用自身 repair 预留。

每次启动可选正式解码前检查 `now >= deadline`。已开始的 SGS 允许完成，下一次解码停止，准备耗尽份额的方案记录为 skipped。阶段份额耗尽记录 `reserved_for_later_phases`，不冒充整个优化超时。公开 `assigned_time_budget_ms` 与配置预算分开；预算诊断只通过白名单投影准备耗时、优化额度和超时等聚合字段。原生真实解码计数留在内部 search report，不进入该公共投影。

代码锚点：`run/schedule_candidate_runner.py:167`、`run/optimizer_search_budget.py:15`、`run/optimizer_search_budget.py:54`、`run/optimizer_deadline_guard.py:9`、`contracts/optimizer_budget_projection.py:15`。原生多起点去重在 `run/optimizer_multi_start_dedup.py:167`：只有完整、成功的原生决策与输入/日历/事务证据一致时省去重复解码；每个策略仍进行原参数校验和排序构造，自定义对象或方法不套用该证明。

### 10.2 真实插入位置与稀缺资源

`MachineTypeState` 归 `algorithm_runtime` 所有，保留原 dict 尾工种接口，同时维护真实时间邻接工种。时隙找到后按实际前后邻居计算换型增量，避免用机器尾工种评价早期插空。`ResourceDemand` 记录当前未完成需求，成功、失败、跳过与图阻塞的退休由运行态统一负责；只在合法资源组合的实际完工时间和换型增量均相同时比较稀缺占用。提示只计会完全剥夺其他待排工序全部合格组合的选择；不更改资格池、固定资源、工时或已有种子，也不把换型次数升级成顺序相关 setup 时长模型。exact SimpleNamespace的工序类型读取直接访问当前原生字段，不缓存mutable字段；一般对象与潜在回调仍保留原入口时序。

代码锚点：`core/algorithm_runtime/resource_quality.py:16`、`core/algorithm_runtime/resource_quality.py:75`、`core/algorithm_runtime/resource_quality.py:95`、`core/algorithm_runtime/resource_demand.py:153`、`core/algorithm_runtime/run_state.py:189`。运行态向派工暴露内容证书，算法层仍单向依赖 `algorithm_runtime`，不反向依赖 scheduler service。

### 10.3 SGS 评分与时隙复用

`NativeSgsReuse` 属于一次 SGS 运行，只缓存成功的固定机人评分；新建缓存要求当前 ready 集合中机器和人员均独占，并且至少有两个可比较的固定资源候选。自动分配且无固定机人组合的输入跳过无收益缓存并用普通占用时间轴；首次helper导入前的模型覆盖、动态getter和自定义metaclass不会被认作原生证书。已有条目只有输入、批次进度、前置完成、资源占用、插入邻居与日历政策等相关内容一致才可复用。`OwnedTimeline` / `OwnedSegments` 由运行态维护可验证变更，普通借入容器仍按实际内容检查；同长度修改、方法覆盖、自定义输入或回调不能借用原生证书。

评分估算可以在选中后交给正式 dispatch，但正式执行仍重验适用证书；证书不成立便重新估算，不复用错误。日历实现通过中立注册入口提供原生政策证书，避免 `algorithm_runtime` 反向 import service。交期字符串解析仅缓存 exact `str` 的成功结果，按 strict mode 区分，最多 4096 条；无效输入和自定义转换仍按原入口暴露错误。

代码锚点：`core/algorithms/greedy/dispatch/sgs_reuse.py:168`、`core/algorithms/greedy/dispatch/sgs_reuse.py:341`、`core/algorithm_runtime/owned_timeline.py:11`、`core/algorithm_runtime/sgs_estimate_reuse.py:10`、`calendar_sgs_certificate.py:11`、`core/algorithms/greedy/dispatch/sgs_scoring.py:45`。跨设备、人员、停机的连续忙段仅在原生索引与恒定日历窗口认证后合并跳过；任意真实空隙、工作窗边界和自定义行为都限制该快路径，见 `core/algorithm_runtime/busy_block_skip.py:12`、`:50`。

### 10.4 图候选、目标特征和修补

GraphReady profile显式接收四个正式目标，保留既有v1基线；batch_workload_v1基础排序和operation_successor_v1增强排序明确并存，通过feature basis选择各自指标。增强特征按真实后继唯一计量负担、按前置最长路径和毛日历计算释放偏移；基础启发只在明确子行中保存，不覆盖顶层正确工量。piece 菱形汇合不能重复累加工量，合并外协按现有身份规则去重，冻结 seed 的完成时间进入释放条件但不重复加入待排负担；必要的 piece 图缺失时明确报错。停机后净窗口与毛容量预算仍分别表达，没有改变毛容量或跨日效率的既有业务语义。

正式 elite repair 默认最多 3 轮，`max_rounds` 严格正整数并封顶 8；轮数、候选总额和同一deadline继续限制搜索，真实未耗尽尾部可在有限轮数内继续。批次顺序、关键块/空档导出的工序优先序以及单工序合格机人选择交错生成，`RepairDecision` 只承载决策，不承载新排程时间。每个候选由真实 SGS 解码，固定维度、资格、DAG 和种子继续受约束；只有严格改善且输出指纹不同的结果才能生成新 elite。下一轮优先强化改进并保留未探索旧elite；top_k按不同已解码parent计槽，同parent的所有basis变体共享该槽和每次最多8个邻域决策，避免重复父排程挤占探索名额。候选家族先保留代表，并按实际解码成本预留；原总预算与60候选上限不变。成功延期和真正预算耗尽分别计数。通用 GRASP/IG 和局搜对 GraphReady 仍保持 §4 的跳过边界，新增图邻域属于 GraphReady 自己的正式阶段。

代码锚点：`run/optimizer_graph_ready_profiles.py:105`、`run/optimizer_graph_ready_workload.py:14`、`run/optimizer_graph_ready_v2_features.py:43`、`run/optimizer_graph_ready_repair_contract.py:23`、`run/optimizer_graph_ready_repair.py:161`、`run/optimizer_graph_ready_repair_decisions.py:13`、`run/optimizer_graph_ready_repair_portfolio.py:90`。

### 10.5 图准备复用与工作台只读快照

图影响计数先证明全图每节点至多一个后继，再使用 O(N+E) 反向动态规划；一般 DAG 使用真实弱连通分量中的位集合精确去重，不能简单累加菱形后继。联合评分只做一次指标合法化，同时产出精确整数 bonus 和原排序 key。comparison 内可缓存权重无关的健康/ready/资源匹配模板；缓存键保留模式与指标模式，每个候选的可变容器独立复制，指标和权重仍重新验证。该缓存不跨排产运行使用。

工作台组合入口在已有 `candidate_read_snapshot` 内连续 prepare 后立刻 compute，中间不向调用者暴露 prepared 对象，因此只扫描一次完整事实指纹。公开独立 `compute_prepared_candidate_run` 仍重新扫描全部事实并拒绝 stale 输入，共享计算体要求活动的 query_only 事务。原 worker 私有数据库快照、最终事实复核与持久化边界保留；每个候选和选中结果的 payload 校验也保留，没有加入结果缓存或可复用的新鲜度 token。

代码锚点：`graph/impact_counts.py:10`、`graph/scoring.py:107`、`run/schedule_graph_cached_projection.py:40`、`core/services/workbench/run_compute.py:22`、`core/services/workbench/run_compute.py:70`、`core/services/workbench/run_compute.py:83`、`core/services/workbench/run_worker.py:64`。

## 变更日志

- 2026-09-13：归并最终共享parent/basis额度、基础与增强特征、全剥夺提示及原生回调边界；实施和定向验收完成，最终整仓门禁未完成，见统一验收。未更新历史规模/SCC统计。

- 2026-09-12：增补 §10 当前算法预算、资源选择、SGS/图准备复用、正式图修补与只读快照合同，并链接本轮统一验收；未刷新历史规模或 SCC 统计。
