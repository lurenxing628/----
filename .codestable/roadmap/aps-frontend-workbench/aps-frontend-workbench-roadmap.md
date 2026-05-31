---
doc_type: roadmap
slug: aps-frontend-workbench
status: active
created: 2026-05-31
last_reviewed: 2026-06-01
tags: [aps, frontend, workbench, scheduler, gantt, resource-dispatch, win7]
related_requirements:
  - gantt-readonly-result-view
  - schedule-delay-diagnosis
  - candidate-comparison-business-view
  - resource-dispatch-calendar-readable-output
  - shop-floor-execution-feedback
related_architecture: [ARCHITECTURE, ui-gantt]
related_roadmaps: [aps-three-gap-directions, gantt-result-view-and-manual-adjustment]
related_compound:
  - aps-frontend-layout-benchmark
  - aps-three-gap-directions
related_audits:
  - 2026-05-31-aps-frontend-layout-gap
---

# APS 前端工作台路线图

## 1. 背景

这份 roadmap 专门承接 `.codestable/compound/2026-05-23-explore-aps-frontend-layout-benchmark.md` 里的“成熟 APS / MES / 计划排程软件前端怎么排版”结论。

上一份 `.codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-roadmap.md` 已经把三条纵向能力拆清楚：

1. 方案对比怎么讲成人话。
2. 延期解释怎么给证据和缺口。
3. 车间现场记录怎么形成事实闭环。

这些能力已经落了不少地基，但它们还分散在首页、甘特图、排产分析、报表、资源派工、计划和现场实际里。计划员每天打开系统时，仍需要自己判断“先去哪页、看哪个版本、为什么晚、资源哪里紧、现场有没有反馈、下一步怎么处理”。

本 roadmap 只解决一个横向问题：把已有页面组织成“计划员工作台”。

大白话说：不是把前端推翻重做，也不是换一层皮，而是让系统从“一堆页面”变成“一条做事路线”。

## 2. 范围与明确不做

### 本 roadmap 覆盖

- **首页值班台**：首页不再只放统计卡和入口宫格，要能显示“今日待处理”和最新排程风险。
- **顶层计划工作台入口**：顶层导航必须有核心作业入口，不能只靠页面内部按钮把用户带到分析、甘特、资源派工和复盘。
- **跨页计划上下文**：从首页、分析、甘特、资源派工、报表互相跳转时，必须带着同一个版本、方案、日期范围和业务对象，不能悄悄掉回默认正式计划。
- **甘特工作台增强**：甘特图继续保持只读，第一版先增加稳定的任务详情区；靠近甘特的资源负荷摘要放到第二阶段增强。
- **排产分析行动入口**：已有推荐方案卡、三方案摘要、诊断区继续复用，但页面层级要更像“先看异常和推荐，再看技术过程”。
- **资源派工和现场记录分层**：资源派工继续承担“看排班、看日历、看甘特、填现场记录”，但后续要把现场记录动作和计划员查看动作分清。
- **报表回跳**：报表中心、资源负荷、超期清单、计划和现场实际不能是死胡同，看完必须能带上下文回到甘特、资源派工或复盘；计划和现场实际只复盘正式采用方案。
- **工作台流程测试**：新增能证明主流程存在的测试，不只测试某个表格 class 或按钮文案。
- **用户手册同步**：页面变化后，同步说明“早上打开系统该先看什么、查问题怎么跳”。

### 明确不做

- 不重写排程算法。
- 不做完整 MES、ERP、WMS、PLM 或 IoT 实时采集。
- 不把资源派工改成自由拖拽排程编辑器。
- 不在本 roadmap 里开放甘特拖拽正式写库。
- 不引入外部 CDN、外链字体、外链脚本、外部前端框架。
- 不升级破坏 Python 3.8、Win7 x64、Chrome 109 的语法或依赖。
- 不把 dashboard 做成营销首页、大横幅或纯视觉展示页。
- 不把 `scenario_id`、`plan_role`、`source_table`、`candidate_id`、`op_id`、`schedule_id` 这类内部字段直接显示给普通用户。
- 不让候选方案或模拟预览直接写现场记录。现场记录只能写当前可执行的正式采用方案。
- 计划和现场实际只对照正式采用方案和现场事实；模拟预览、候选方案和对比参考方案不能进入现场实际复盘口径。
- 不承诺自动判断唯一根因。延期解释仍按“已确认事实、可能线索、证据缺口、建议动作”表达。
- 短期不做反馈人必填、多人现场账号、Excel 导入预览 / 二次确认。当前使用方式按“计划员一个人操作，其他人把现场情况汇报给计划员”处理。

## 3. 当前事实

### 3.1 首页现状

`templates/dashboard.html` 已有待排批次、已排批次、超期批次、最近排产版本四张统计卡，也有“最近排产”和“常用工作区”。

短板是这些信息还偏静态展示。用户看到数字后，还要自己判断该点甘特、分析、报表、资源派工还是排产历史。

### 3.2 甘特图现状

`.codestable/architecture/ui-gantt.md` 已记录当前甘特图结构。甘特图是只读结果查看页，已有版本、方案、周切换、日期范围、时间粒度、配色、批次筛选、资源筛选、仅超期、仅外协、关键工序和关系线。

短板不是控件少，而是任务详情主要靠弹窗，资源负荷不在甘特附近，点到超期任务后还不能稳定看到“为什么红、下一步去哪看”。

### 3.3 排产分析现状

`templates/scheduler/analysis_parts/_candidate_comparison.html` 已有推荐方案卡、三方案摘要和方案对比表。`templates/scheduler/analysis_parts/_diagnostic_sections.html` 已有诊断区和查看依据。

短板是页面仍按“选择版本 → 概览 → warnings → 诊断 → 指标 → 方案对比 → 优化过程”铺开。计划员真正早上要看的“风险、推荐、下一步”还没有被提成主入口。

### 3.4 资源派工现状

`templates/scheduler/resource_dispatch.html` 已有任务明细、现场记录、日历矩阵、甘特图四个标签，也有计划身份提示、导出资源派工、查看计划和实际。

短板是资源派工同时承担计划员查看、现场情况沟通、现场记录填写和 Excel 导入，页面越来越重。后续需要把“计划员看排班”和“计划员代录现场事实”在布局上分清。

### 3.5 工作台 mockup 现状

`docs/aps_frontend_workbench_mockup.html` 是前端工作台方向的示例，不是上线实现。它能作为布局参考，但不能直接当实现方案；真实落地必须服从当前模板、CSS、JS、Win7 离线和 CodeStable 流程。

## 4. 模块拆分（概设）

```text
APS 前端工作台
├── 顶层计划工作台入口：让计划员从顶层一跳进入首页值班台、分析、甘特、资源派工和复盘
├── 首页值班台：把最新排产、超期、资源风险、方案待确认、现场情况待确认收成待处理列表
├── 工作台上下文协议：统一版本、方案、日期范围、批次/资源等跨页跳转参数
├── 甘特工作台层：第一版在只读甘特旁边补任务详情区和超期说明入口；第二阶段再补资源负荷摘要
├── 排产分析行动层：把方案推荐、延期解释、诊断建议放到技术过程之前
├── 资源派工执行层：把看排班、看现场记录、导入实际情况、计划和现场实际分出清楚入口
├── 报表回跳层：让超期、资源负荷、计划和现场实际、停机影响都能回到甘特或资源派工继续处理
├── 手册与文案层：用中文业务动作说明用户该先看什么、点哪里、为什么
└── 工作台流程测试：验证主流程，而不只验证静态样式和单个按钮
```

职责边界：

- 首页值班台只做“从哪里开始处理”，不承载所有明细。
- 甘特工作台只读，不负责写计划。
- 排产分析负责解释和推荐，不负责直接改计划。
- 资源派工负责下发查看和现场事实入口，不负责编辑排程算法结果。
- 工作台上下文协议负责跨页带参，不负责显示内部字段。

## 5. 接口契约（架构层详设）

### 5.1 工作台计划上下文

所有工作台入口和跨页跳转都必须围绕同一个计划上下文组织。

下面的契约示意要按 Python 3.8 能接受的类型写法落地；可空值写成 `Optional[...]`，列表写成 `List[...]`，枚举候选写在注释或说明里，不使用 `int | None`、`list[...]` 这类新语法。

```text
WorkbenchPlanContext:
  version: Optional[int]
  version_label: str
  plan_role: str  # adopted / baseline_best / critical_best
  plan_role_label: str
  scenario_id: Optional[str]
  scenario_display_label: str
  date_from: Optional[str]
  date_to: Optional[str]
  query_date: Optional[str]
  period_preset: Optional[str]  # week / month / custom
  batch_id: Optional[str]
  resource_type: Optional[str]  # operator / machine / team
  resource_id: Optional[str]
  resource_label: str
  is_preview: bool
  can_write_feedback: bool
  guardrail_text: str
  guardrail_reason_type: str  # plan_not_writable / task_state_blocked / action_unavailable / data_gap
  capacity_source_label: str
  capacity_gap_text: str
```

约束：

- `scenario_id` 可以留在 URL、隐藏字段、日志和服务端参数里，但用户可见位置必须显示 `scenario_display_label` 或“模拟预览（未命名）”。
- `plan_role` 可以作为 URL 参数，但页面必须显示中文 `plan_role_label`。
- 只有 `can_write_feedback=true` 时，现场记录写入按钮才可能可用；最终仍以后端 `available_actions` 为准。
- 现场记录不可写时，必须显示中文原因，至少区分当前方案不可写、当前任务状态不可写、后端动作不可用、数据缺口；短期不新增多人账号和现场权限模型。
- 从首页跳到甘特、分析、资源派工、报表时，必须带上能保持同一套计划的上下文参数。
- 资源派工 URL 里现有视角参数叫 `scope_type`；它和上下文里的 `resource_type` 表达的是同一类“人员 / 设备 / 班组视角”，后续实现可以保留 URL 的 `scope_type`，但 ViewModel 对用户可见处统一显示中文视角。
- `plan_role`、`guardrail_reason_type`、`resource_type`、`period_preset`、`view` 等内部枚举必须在 feature design 里写成“内部值 -> 中文展示值”映射表；页面、导出列和公开 payload 都不能直接露内部值。

### 5.2 首页值班台摘要

首页新增的工作台摘要由 viewmodel 统一组织，页面只负责展示，不在模板里临时猜风险。

```text
SchedulerWorkbenchSummary:
  generated_at_label: str
  latest_plan: WorkbenchPlanContext
  risk_cards: List[WorkbenchRiskCard]
  todo_items: List[WorkbenchTodoItem]
  quick_links: List[WorkbenchLink]
  empty_state: str
```

```text
WorkbenchRiskCard:
  kind: str  # pending_batches / scheduled_batches / overdue_batches / resource_overload / latest_version / site_record_gap
  label: str
  value: str
  helper_text: str
  severity: str  # ok / notice / warning / danger
  target_url: str
```

```text
WorkbenchTodoItem:
  kind: str  # failed_schedule / overdue / resource_overload / candidate_review / site_record_gap / data_gap
  severity: str  # danger / warning / notice
  title: str
  impact_text: str
  evidence_text: str
  handling_state_label: str
  action_label: str
  target_url: str
```

约束：

- todo 最多展示 6 条，按严重程度排序。
- 没有待处理时显示“当前没有必须马上处理的排产风险”，并给出查看甘特或执行排产入口。
- todo 文案必须是中文大白话，例如“3 个批次会晚于交期”，不能显示内部错误码。
- 资源高负荷 todo 优先说明能安全算出的影响面，比如受影响批次数或最晚受影响批次；如果当前服务只能拿到利用率，就显示“暂时只能看到资源压力，受影响批次还不能判断”，不能硬编。
- 第一版如果不保存“已查看 / 已处理”状态，页面要说明待处理项是实时生成，不让用户误以为系统会记住处理进度。
- 首页不直接查复杂明细；复杂明细从对应页面继续看。

### 5.3 工作台链接

所有跨页入口使用统一链接结构，方便测试锁住“带着同一上下文跳转”。

```text
WorkbenchLink:
  label: str
  url: str
  target_page: str  # dashboard / analysis / gantt / resource_dispatch / overdue_report / delay_diagnosis / utilization_report / execution_review / reports_index
  context_summary: str
  disabled: bool
  disabled_reason: str
  required_params: List[str]
```

约束：

- 链接禁用时必须给中文原因。
- 链接 label 不能出现内部字段名。
- `required_params` 只写测试必须锁住的上下文参数，避免跳转时悄悄丢版本、方案、日期、批次或资源。
- `required_params` 必须按页面设计稿第 3.4 节的逐路线参数矩阵落地；跳资源派工或报表类页面时，能拿到就同时保留 `date_from/date_to`、`query_date`、`period_preset`，跳资源派工还要保留 `scope_type`。
- 只要当前上下文有 `plan_role` 和 `scenario_id`，除 `execution_review` 这类只看正式采用方案的页面外，跨页链接都要继续携带，页面可见处再翻译成中文。
- 去甘特图时必须明确 `view=machine` 或 `view=operator`。
- 去资源派工时必须明确 `scope_type`；没有资源对象时可以默认 `operator` 且展示全部人员。

### 5.4 甘特任务详情区

甘特图后续新增稳定详情区，不替代现有弹窗。详情区只显示公开字段。

```text
GanttTaskDetailPanel:
  selected_task_key: str
  title: str
  batch_label: str
  plan_actual_summary: str
  part_label: str
  operation_label: str
  planned_time_label: str
  resource_label: str
  status_label: str
  overdue_label: str
  delay_hint: str
  next_links: List[WorkbenchLink]
  empty_state: str
```

约束：

- `selected_task_key` 只能用于前端定位，不显示给用户。
- 如果延期诊断没有足够证据，`delay_hint` 必须写“当前数据不足，建议先查看超期清单或排产诊断”，不能硬说根因。
- 详情区必须能被清空，清空后显示“点击甘特条查看任务详情”。
- 移动端或窄屏可以放到甘特下方，宽屏可以放右侧。

### 5.5 甘特资源负荷摘要（第二阶段增强）

第二阶段在甘特附近新增资源负荷摘要。第一版甘特只要求任务详情区、超期说明入口和去资源负荷报表的上下文链接，不把 Top 资源摘要作为验收项。

```text
ResourceLoadSummary:
  context: WorkbenchPlanContext
  items: List[ResourceLoadItem]
  source_label: str
  target_url: str
  empty_state: str
```

```text
ResourceLoadItem:
  resource_type: str  # machine / operator
  resource_label: str
  load_hours_label: str
  utilization_label: str
  task_count_label: str
  capacity_source_label: str
  capacity_gap_text: str
  severity: str  # ok / warning / danger / unknown
  evidence_text: str
```

约束：

- 第二阶段最多显示最忙设备 5 个、最忙人员 5 个。
- 阈值必须在 feature-design 里写清，例如超过 90% 显示危险、超过 75% 显示提醒。
- 没有可用工时或日历数据时，显示“利用率暂时算不了”，不能假装正常。
- 必须说明容量来源，例如工作日历、班次、是否扣除停机；如果当前只是用全局日历工时估算、没有按单台设备或单个人细分，也要写清楚；算不出来时说明缺什么。
- 必须提供“去资源派工查看明细”“去资源负荷报表”或“查看这个资源的时间轴负荷”入口。

### 5.6 排产分析行动入口

排产分析页继续复用已有诊断和方案对比 ViewModel，但页面层级要符合工作台顺序。

建议顺序：

1. 当前版本和计划身份。
2. 今日最需要看的风险或空状态。
3. 方案推荐卡和三方案摘要。
4. 延期/诊断行动卡。
5. 指标卡。
6. 优化过程和趋势图。

约束：

- 方案推荐和诊断信息必须引用既有 ViewModel 数据，不在模板里重新计算业务规则。
- 推荐方案卡和三方案摘要优先显示已有影响面和差值，例如超期批次、总拖期、换型次数、数据缺口；资源压力信息能算就显示，算不了就写“资源压力暂时不能判断”。
- 技术过程仍可保留，但不能抢第一屏主位置。
- 没有候选方案时，要写“本次没有开启方案对比”，不能让用户以为页面坏了。

### 5.7 资源派工执行分层

资源派工后续分层遵守以下入口口径：

```text
ResourceDispatchWorkbenchTabs:
  detail: 任务明细
  calendar: 日历矩阵
  gantt: 甘特图
  execution: 现场记录
  review_link: 查看计划和实际
```

约束：

- 计划员看排班：默认仍从任务明细、日历矩阵、甘特图进入。
- 现场记录：继续使用任务卡、大按钮、手填和 Excel 导入，不把现场动作塞回大表格里。
- 现场事实区提供今日任务、待开工、待完工、现场情况待确认等快速筛选；短期不做“我的任务”，因为当前不是现场人员登录填报。
- 现场记录不可写时必须显示中文原因，不能只显示“不可写”。
- 非正式方案、候选方案、模拟预览、历史正式方案下，不输出写入按钮、表单 action、API URL、Excel 导入 URL、模板下载 URL 或任何 `data-*` 写入地址。
- 短期不新增多人现场账号和权限模型；如果后端已有动作不可用原因，就按中文展示，不把它扩展成新权限系统。
- Excel 继续按直接导入处理，短期不做预览 / 二次确认；导入后返回新增、失败、跳过数量，并刷新任务卡、任务明细和资源派工甘特。
- 计划和实际复盘：使用独立“查看计划和实际”入口，不能让用户误以为它会改现场记录。
- 计划和实际复盘只面向正式采用方案。非正式方案下入口必须禁用，并给出中文原因。
- 后续如果新增独立现场记录页，必须从这里保留双向入口，并继续服从 `available_actions`。

### 5.8 测试契约

每条 feature 至少要覆盖对应层级：

- 静态合同：页面出现工作台入口、中文文案、跨页链接参数、无内部字段泄露。
- ViewModel 合同：`SchedulerWorkbenchSummary`、`WorkbenchTodoItem`、`WorkbenchLink` 字段完整，空数据和异常数据都有中文解释。
- 前端合同：甘特详情区、第二阶段资源负荷摘要、资源派工 tab 不互相遮挡；按钮可用性由后端数据驱动。
- 浏览器几何：关键页面在本地浏览器里不出现主内容重叠、按钮文字挤出、表格撑破。
- Win7 / Chrome 109：不使用需要新版浏览器才支持的前端能力，不引入外链资源。

## 6. 子 feature 清单

| 顺序 | 子 feature | 目标 | 依赖 | 最小闭环 |
|---|---|---|---|---|
| 1 | `workbench-context-link-contract` | 统一跨页链接和计划上下文，防止跳转丢版本、丢方案、丢日期 | 无 | 是 |
| 2 | `workbench-nav-entry` | 顶层出现计划工作台一跳入口，分析、甘特、资源派工、复盘不再藏得太深 | 1 | 是 |
| 3 | `dashboard-workbench-risk-todos` | 首页显示最新排产风险和今日待处理，用户能从首页进入正确下一步 | 1, 2 | 是 |
| 4 | `analysis-action-hub-layout` | 排产分析页把方案推荐、延期解释、诊断行动提到技术过程之前 | 1 | 否 |
| 5 | `gantt-task-detail-panel` | 甘特图增加稳定任务详情区和下一步链接 | 1 | 否 |
| 6 | `resource-dispatch-execution-lane` | 资源派工把看排班、现场记录、计划和现场实际入口分清 | 1 | 否 |
| 7 | `reports-workbench-backlink` | 报表中心和报表明细能带上下文回到甘特、资源派工和复盘 | 1 | 否 |
| 8 | `workbench-flow-regression-suite` | 用测试证明第一版“首页 → 异常/方案/甘特/派工/报表/复盘”的主流程存在 | 1-7 | 否 |
| 9 | `workbench-user-guide-refresh` | 更新用户手册，告诉用户每天该先看哪里、怎么查问题 | 8 | 否 |
| 10 | `delay-diagnosis-site-facts-bridge` | 延期解释接入已录入的现场事实，不能继续固定说没有现场事实 | 1, 6 | 否 |
| 11 | `gantt-resource-load-summary` | 甘特附近显示最忙设备/人员和资源负荷入口 | 1, 5 | 否 |
| 12 | `downtime-task-impact-detail` | 停机影响从设备级说明补到受影响任务级明细 | 1, 7 | 否 |
| 13 | `downstream-batch-order-impact` | 延期和方案解释在数据足够时说明牵连批次/订单影响面 | 1, 4, 10 | 否 |

## 7. 排期建议

技术依赖上，第一条应先做 `workbench-context-link-contract`。原因很简单：如果不先把跨页链接和参数口径定住，首页、分析、甘特、资源派工和报表都会各自拼 URL，后续再统一会返工。

建议顺序：

1. 先做 `workbench-context-link-contract`，把跨页带参口径锁住。
2. 再做 `workbench-nav-entry`，把顶层计划工作台入口补出来。
3. 再做 `dashboard-workbench-risk-todos`，让首页从静态入口变成“今天先处理什么”。
4. 然后拆第一版页面：
   - 分析页行动入口。
   - 甘特详情区。
   - 资源派工执行分层。
   - 报表中心和报表明细回跳。
5. 第一版页面完成后，先补主流程测试和用户指南；这一步只依赖第一版阶段 1-7，不等待第二阶段增强。
6. 甘特资源负荷摘要、延期解释接现场事实、停机影响任务级明细、牵连批次/订单影响面放在第二阶段增强，避免第一轮和第一版范围过大。

产品优先级可以由用户调整；技术依赖只要求跨页上下文在后续页面大改前先稳定。

## 8. 观察项

- `.codestable/roadmap/aps-three-gap-directions/` 已经是 completed，本 roadmap 不重拆它的实施计划；如果当前页面契约或用户可见文案已经漂移，只允许做事实对齐型小修并写入变更日志。
- `.codestable/features/2026-05-29-resource-dispatch-execution-page-extraction/` 当前是未纳入 git 的已有工作区内容。后续做 `resource-dispatch-execution-lane` 时要先确认它是否继续推进、废弃或改成新设计输入。
- `docs/aps_frontend_workbench_mockup.html` 可作为视觉参考，但它使用独立样式和较强示例感，不能直接复制到正式模板。
- 当前首页仍是 `templates/dashboard.html` 的经典模板；如果现代界面覆盖层参与，需要在对应 feature-design 里单独确认。
- 大布局改动必须做浏览器验证，不能只靠静态字符串测试。
- 2026-05-31 Exa 外部对标结论已回写到页面级设计稿：第一版补方案影响面、容量来源、不可写原因、现场事实快速筛选；折叠式任务简表、保存视图、基线甘特叠线、模拟沙盒和 MES 异常闭环作为第二阶段观察项，不塞进第一版。用户已明确 Excel 导入预览 / 二次确认短期不做。

## 9. 自查结果

- 模块拆分：已按首页、上下文、甘特、分析、资源派工、测试和手册拆分。
- 接口契约：已写到 viewmodel 字段、链接字段和页面层级约束。
- 子 feature 粒度：每条都能单独进入 `cs-feat-design`。
- 依赖关系：DAG，无循环。
- 最小闭环：`workbench-context-link-contract` + `workbench-nav-entry` + `dashboard-workbench-risk-todos` 三项完成后，才能演示从顶层进入首页、从首页待处理跳到目标页且不丢上下文。
- 明确不做：已写。
- 与现有 req / arch：不改 requirements / architecture，只引用现状和观察项。

## 10. 变更日志

- 2026-05-31：新建 roadmap，承接 APS 前端布局调研和 2026-05-31 前端布局审计结论，专门规划横向工作台骨架。
- 2026-05-31：根据页面级设计稿与 SubAgent 对抗复核，补入 `workbench-nav-entry` 和 `reports-workbench-backlink` 两条正式子 feature，避免顶层导航和报表回跳无人承接。
- 2026-05-31：追加 Exa MCP 外部对标结论，补强方案差异、资源容量来源和现场写入禁用原因；保留第二阶段能力边界，避免第一版扩大成完整 APS/MES 平台。
- 2026-05-31：根据用户补充口径，短期不做反馈人必填、多人现场账号、Excel 导入预览 / 二次确认；现场记录按计划员单人代录现场事实处理。
- 2026-05-31：根据开工总方案对抗复核，把执行顺序调整为“上下文链接合同先行”，新增 `delay-diagnosis-site-facts-bridge` 条目，并明确非正式方案下不得输出任何写入 URL 或 `data-*` 写入地址。
- 2026-06-01：根据只读审查补强 `required_params` 逐路线矩阵口径、内部值到中文展示映射要求，并把停机影响任务级明细、牵连批次/订单影响面补成第二阶段独立条目。
