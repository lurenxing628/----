---
doc_type: architecture
slug: ARCHITECTURE
scope: 项目架构总入口，覆盖 APS 整体结构、核心模块索引、关键架构决定和长期交付边界
summary: APS 在 Win7 x64、Python 3.8、离线交付约束下的系统地图入口
status: current
created: 2026-04-27
last_reviewed: 2026-06-01
tags: [aps, codestable, architecture, win7]
depends_on: []
implements: []
---

# 回转壳体单元智能排产系统（APS）架构总入口

> 状态：CodeStable 现状索引
> 创建日期：2026-04-27

## 1. 项目简介

本项目是面向 Win7 x64 离线单机与共享数据场景的本地 APS 智能排产系统。系统目标是在目标机不安装 Python、不依赖外网的前提下，完成基础资料维护、Excel 导入导出、批次排产、结果查看、报表导出、备份恢复和现场交付。

当前开发与打包基线保持在 Python 3.8，并继续服从 Win7 兼容边界。正式交付时，目标机通过安装包和本地浏览器运行时访问 APS 页面。

## 2. 核心概念 / 术语表

- APS：围绕批次、工序、设备、人员、日历、齐套约束和排产策略组织的智能排产系统。
- 经典界面：`templates/` 与 `static/` 下的原有页面体系。
- 现代界面：`web_new_test/templates/` 下的覆盖模板体系，通过界面模式切换逐步接管页面。
- Win7 交付边界：目标机不要求安装 Python，页面和静态资源随应用本地交付，依赖升级必须考虑 Python 3.8 与 Win7。

## 3. 子系统 / 模块索引

- `core/`：核心领域、算法、基础设施、服务与插件运行框架。
- `data/`：数据访问层。
- `web/`：Flask 启动、路由、页面装配、界面模式与 viewmodel。
- `templates/`、`static/`：经典页面模板与本地静态资源。
- `web_new_test/templates/`：现代界面模板覆盖层。
- `templates_excel/`：交付 Excel 模板。
- `plugins/`：自研插件目录，当前插件默认关闭。
- `tests/`：自动化测试。
- `tools/`、`scripts/`：质量门禁、治理台账、辅助检查脚本。
- `开发文档/`、`audit/`、`evidence/`：开发说明、审计记录和验证证据。
- `.codestable/architecture/ui-gantt.md`：甘特图结果查看页面、缩放协议、只读边界、模拟预览身份传递和本地 Frappe 补丁治理现状。
- 车间执行事件基础：`OperationExecutionEvents`、执行事件仓储、执行反馈服务和执行状态读模型记录现场开工、暂停、继续、完工、报异常这些事实。
- 资源派工现场记录：资源派工页用户入口叫“现场记录”，支持单条填写实际情况、下载填写模板、导入实际情况 Excel；普通页面是一键导入，后台先整批检查，有错不写库并返回错误明细，无错才事务写入；route 拆在 `scheduler_resource_dispatch_execution_routes.py`，业务编排拆在 `resource_dispatch_actual_*` service 文件。页面把计划员查看排班和计划员代录现场事实分成两个区域；执行区 JS 按 context、cards、actual、import 和 coordinator 拆分，任务卡公开图号/物料、计划/实际时间偏差，执行流水把 `created_at/source_table` 转成中文记录时间和来源。
- 重排执行事实快照：普通重排和甘特模拟方案发布在写新正式计划前，都会按同一批工序复算现场状态，现场状态变化时拒绝写入。
- APS 工作台上下文链接合同：`web/viewmodels/scheduler_workbench_links.py` 统一封装工作台计划上下文、跨页链接、中文标签映射和现场写入地址护栏；`web/viewmodels/scheduler_workbench_link_query.py` 集中维护各目标页要带的版本、方案、日期、批次和资源参数矩阵；`core/services/scheduler/resource_dispatch_page_context.py` 装配资源派工页面的版本、方案身份、筛选条件和可查询状态等只读查询上下文；`web/routes/domains/scheduler/scheduler_resource_dispatch.py` 接线资源派工只读复盘入口和写入入口状态。第 1 阶段已用于排产分析候选方案跳转、周计划入口、资源派工现场记录写入口控制和现场记录二级接口公开身份脱敏，避免这些页面各自拼 URL 时丢版本、方案、日期、批次或资源对象，也避免把内部计划身份交给前端当作写入凭证。
- 顶层计划工作台入口：经典界面 `templates/base.html` 顶层导航最左侧挂载 `ui.workbench_nav_menu()`；宏定义在 `templates/components/ui_macros.html`，样式在 `static/css/ui_contract.css`。它用原生 `<details>/<summary>` 展开“计划工作台”快捷菜单，提供首页值班台、排产分析、设备甘特图、人员甘特图、资源派工、计划和现场实际 6 个只读页面入口；不新增独立工作台页面，不依赖外部 JS/CSS，不输出现场记录写入、Excel 导入、模板下载或表单写入地址。
- 首页计划员值班台：经典首页 `templates/dashboard.html` 和现代镜像 `web_new_test/templates/dashboard.html` 由 `web/routes/dashboard.py` 读取最新排产、正式采用方案范围、今日计划任务和现场事实，再交给 `web/viewmodels/dashboard_workbench.py` 与 `web/viewmodels/dashboard_workbench_cards.py` 生成风险卡、今日待处理和快捷入口。首页值班台只展示实时生成的待处理，不保存已处理状态，不直接写现场记录，不新增数据库表，不改排产算法；所有跨页动作继续使用 `WorkbenchLink`，页面只显示中文计划身份和中文业务文案，内部字段只留在 URL、隐藏参数或服务端日志里。现场事实读取失败时，首页显示“现场情况暂时读不到”这类数据缺口提醒，不把读取失败误判成“现场情况待确认”。
- 排产分析行动入口：`web/routes/domains/scheduler/scheduler_analysis.py` 在候选方案链接绑定后调用 `web/viewmodels/scheduler_analysis_action_hub.py`，把已有推荐结论、代表方案摘要、诊断摘要和下一步入口整理成首屏行动区；`templates/scheduler/analysis_parts/_action_hub.html` 展示该行动区，`templates/scheduler/analysis.html` 的选中版本顺序为版本身份、行动区、告警、详细方案对比、完整诊断、指标、优化过程。行动区只复用已有 `candidate_comparison_display`、`diagnostic_sections` 和 `WorkbenchLink`，不重算候选方案、不改算法、不新增数据库，也不把候选方案变成可写现场记录入口。
- 甘特任务详情区：`/scheduler/gantt/data` 由 `GanttService` 读取排程明细，并通过 `ExecutionFactProvider` 按 `op_id` 聚合现场执行事实；`core/services/scheduler/gantt_tasks.py` 输出公开任务标题、计划时间、现场实际小结、超期提示和资源/工序/图号字段；`web/viewmodels/scheduler_gantt_task_detail.py` 追加资源派工、计划和现场实际、超期清单链接；`static/js/gantt_render.js` 点击任务后刷新 `#ganttTaskDetail`，`static/js/gantt_popup.js` 继续维护旧弹窗和新详情区。详情区和旧弹窗只展示公开字段，关键链 edge 保留内部 `from/to` 做连线，同时用 `from_label/to_label` 给用户看，避免缺 `op_code` 时把 `op_<数字>` 露出来。

## 4. 关键架构决定

- CodeStable 从 2026-04-27 起作为新的 AI 协作工作流入口。
- `.limcode/` 暂不删除，保留为旧工作流归档、历史计划、历史审查和 APS 专项技能资料库。
- 新增功能、问题修复、重构、知识沉淀等新工作默认落到 `.codestable/` 下；只有需要引用历史资料或 APS 专项技能时，再回看 `.limcode/`。

## 5. 已知约束 / 硬边界

- 面向用户默认使用简体中文。
- Win7 x64、Python 3.8、离线交付是长期约束。
- 页面、导出、文件名、提示语和帮助文档不能直接展示 `scenario_id`、`plan_role`、`source_table`、`candidate_id` 这类程序内部字段；这些字段可以留在 URL、隐藏字段、请求参数和日志里用于对齐同一套计划，但用户可见位置必须转成中文大白话。
- 非正式方案、候选方案、模拟预览和历史正式方案不能下发现场记录写入入口、Excel 导入地址或模板下载地址。后端校验仍是最后防线，但页面层也要避免让用户看到“好像能写”的入口。
- 资源派工导出当前同时提供矩阵表和日历明细表：矩阵表用于看资源与日期的大盘，`日历明细` 按一条日历任务一行展开，继续只展示中文业务字段，不展示 `op_id`、`schedule_id`、`state_revision`、`execution_snapshot_revision` 等内部追踪字段。当前证据在 `core/services/scheduler/resource_dispatch_excel.py` 和 `tests/regression_resource_dispatch_public_output_contract.py`。
- 质量门禁入口仍以仓库现有 `scripts/run_quality_gate.py` 为准。
- 旧 `.limcode/plans/`、`.limcode/review/` 里有大量历史上下文，迁移初期不得批量删除或搬动。

## 6. 排产工序图分析现状

- `core/services/scheduler/graph/` 是排产工序图的内部分析模块，当前负责把已整理好的待排工序转成图节点、构建同批次前后工序边、校验 DAG / 环、计算拓扑顺序、关键路径和节点指标，并导出普通 dict 摘要。
- `graph_analysis_mode=off` 是默认关闭模式。关闭时排产主链不导入图模块，不要求安装 NetworkX，也不会在 `result_summary` 里写 `graph_analysis`。
- `graph_analysis_mode=report` 已作为旁路报告接入 `core/services/scheduler/run/schedule_orchestrator.py`。接入点在原排产算法已经算完、`validated_schedule_payload` 已经生成之后，图报告判断、错误投影和采样投影收在 `core/services/scheduler/run/schedule_graph_report.py`，只读取 `ScheduleRunInput.cfg`、`algo_ops_to_schedule`、`batches` 和 `resource_pool`。
- report 模式只把公开小摘要写进 `result_summary["algo"]["graph_analysis"]`，把采样诊断写进 `result_summary["diagnostics"]["graph_analysis"]`。OperationLogs 沿用现有 `detail["algo"]` 小摘要路径，因此只能看到 `algo.graph_analysis`，不能看到完整 nodes、edges、node_metrics、topological_order 或 raw 对象。
- `graph_analysis_mode=on` 当前已经接入 PR-5 ready 队列和 PR-6 图评分：可用 DAG 会在 optimizer 前生成 plain `graph_ready_context`，SGS 候选集合只从图 ready 工序里取；当 `graph_critical_weight` 或 `graph_impact_weight` 大于 0 时，图模块会计算 full `node_metrics`，在 service 层预先转成 `graph_priority_key_by_op_id`，算法层只拼普通 tuple，不反向依赖 scheduler service。`on + 有环 + graph_block_on_cycle=yes` 会在 version 分配前阻止排产；`on + 有环 + graph_block_on_cycle=no` 会继续旧 SGS 逻辑，但 public 摘要会写明图增强和图评分未启用。候选方案链路已经接入 3/5/7 档权重试跑、自动选择、候选落库和代表三方案页面切换；第一版只承诺正式采用方案、原算法代表方案和重点工序优先代表方案的查看与对比，不承诺全候选明细大屏、任意两方案自由对比、批次级或资源级差异清单。

## 7. 车间执行事件基础现状

- `OperationExecutionEvents` 是现场事实表，记录工序、批次、正式计划身份、动作、反馈时间、实际设备、实际人员、异常信息、幂等键、服务端指纹、写入前状态版本和反馈人。
- 执行事件只追加。`schedule_id` 和 `op_id` 仍保留外键用于审计对齐，但不使用级联删除，避免删除计划行时把现场事实一起带走。
- `data/repositories/operation_execution_event_repo.py` 负责执行事件的全部 SQL，并按 `op_id` 聚合 `OperationExecutionState`。service 不直接拼写事件表 SQL。
- `core/services/scheduler/operation_execution_feedback_service.py` 负责正式计划身份校验、幂等键优先判断、状态版本校验、合法状态流转和事件写入。
- 资源派工页的用户入口叫“现场记录”，普通操作区使用“填写实际情况”“下载填写模板”“导入实际情况 Excel”“查看计划和实际”“暂停时间”“异常记录”这些说法，不把 `op_id`、`schedule_id`、`state_revision`、`execution_snapshot_revision` 等内部追踪字段放到用户可见模板和普通页面里。
- 单条填写和 Excel 导入最终都追加 `OperationExecutionEvents`。单条填写由 `ResourceDispatchActualRecordService.record_actual_situation()` 编排；Excel 模板和读取在 `resource_dispatch_actual_excel.py`，预览校验在 `resource_dispatch_actual_import.py`，共享值对象和字段解析在 `resource_dispatch_actual_records.py`。
- Excel 普通页面采用一键导入。后端先做任务匹配、时间格式、完工早于开工、暂停重叠、可能重复等检查；有错误就返回行级错误并且不写数据库，整批无错误才在同一事务里追加事件。预览 / 确认写入接口保留为兼容入口，但不作为普通页面主流程。
- 反馈人对用户可空。写入事件时 service 使用内部兜底值满足数据库非空约束，但页面不强迫用户填写。
- 暂停/继续生产在页面上不作为醒目的实时控制按钮展示；用户填写的是暂停开始、暂停结束或暂停时长，系统仍按事件模型追加暂停和继续生产事件。
- 状态读模型按事件流聚合：`last_event_*` 表示最后一条现场事件，`latest_exception_*` 表示最近一次报异常；两组字段分开计算。
- 程序动作 `report_exception` 入库为 `event_type=exception`，页面和返回值显示“报异常”；现场状态 `exception` 显示“异常中”，两套中文映射分开维护。

## 8. 重排执行事实快照现状

- `core/services/scheduler/execution_snapshot.py` 负责把一批工序的执行状态版本整理成可复算快照。快照包含 `execution_snapshot_revision`、`execution_snapshot_op_ids` 和 `execution_snapshot_op_count`。
- 普通重排在 `schedule_input_collector.py` 读取执行事实：生产中和暂停中工序作为现场固定 seed，已完工工序保留真实时间并从待排输入剔除，异常中工序阻止普通自动重排。
- 候选比较、多起点、局部搜索、优化器和图排程 ready queue 复用同一批执行 seed；执行 seed 的来源标记为 `execution_fact`，和冻结窗口 seed 分开。
- 普通重排写正式计划前会在 `schedule_persistence.py` 复算执行快照并校验固定工序、已完工工序和下游时间。现场状态变化时返回中文冲突提示，不写 `Schedule`、`ScheduleHistory` 或版本号。
- 甘特模拟方案保存时会在 `ScheduleAdjustmentScenario` 里记录执行快照；正式采用模拟方案前会用保存时同一批工序复算，现场状态变化时拒绝发布并回滚发布状态。
- 执行快照字段是开发和测试追溯信息，不直接给普通用户看；页面和普通接口只返回中文消息、名称、预览或查看链接等用户需要的信息。
