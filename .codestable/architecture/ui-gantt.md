---
doc_type: architecture
slug: ui-gantt
scope: 工作台计划、候选、试调及实际甘特的输入、显示模型、绘制与只读交互
summary: 计划和实际甘特按准备、分组筛选、布局、可见区绘制分工，保留点工序、现场事实及历史页面退役边界
status: current
created: 2026-05-22
last_reviewed: 2026-11-10
updated: 2026-11-10
tags: [scheduler, gantt, frontend, readonly, canvas, point, execution]
---

# 工作台甘特显示架构

本文记录 2026-11-10 全局架构收敛（`A0`～`A5`）落地实现。前期单次准备重构见[单次准备方案及执行记录](../refactors/2026-10-15-single-pass-workflow/single-pass-workflow-refactor-design.md)，全局收敛裁决见[全局架构收敛路线图](../roadmap/aps-architecture-consolidation/aps-architecture-consolidation-roadmap.md)，历史页面演进集中在文末。

## 1. 当前入口与事实来源

| 界面 | 前端拥有者 | 数据来源 |
|---|---|---|
| 计划甘特 | `PlanGantt.jsx`、`PlanGanttModel.js`、`PlanGanttCanvas.jsx` | `PlanAPI.js` / `PlanContract.js`，`/api/workbench/v1/plans/<plan_ref>/workspace` |
| 同次候选甘特 | `RunCandidateGantt.jsx`、`RunCandidateModel.js`、`RunBaselineModel.js` | 当前运行的已保存候选及明确选择的比较基准 |
| 试调甘特 | `TrialGantt.jsx` | 试调工作区的当前安排与其自身原安排 |
| 实际甘特 | `ActualGanttWorkspace.jsx`、`ActualGanttModel.js`、`ActualGanttCanvas.jsx` | `ActualGanttAPI.js` / `ActualGanttContract.js`，`/api/workbench/v1/actual-gantt` |

所有前端文件位于 `frontend/workbench/app/`，采用显式 ESM 模块（`import/export`），由 `scripts/workbench/build.py`（配合 `compile.cjs`）经宿主固定版本 `esbuild` 离线打包进入 `static/workbench/`（旧 `build-order.json` 手工脚本顺序拼接与 `window.*` 业务全局导出已退役）。实际图形来自当前领域响应，计划、已保存候选、试调和正式采用来源各自持永久引用。

后端 `WorkbenchPlanQueryService` 通过本次读取上下文共享所选计划、任务、资源和基准来源（报表读取经 `WorkbenchReportFacts.read_snapshot()` 传入并复用单一流式 `PlanMetadataRepository` 上下文）。内部 `execution_workspace` 提供现场、链路和报表继续加工所需的计划事实；完整响应在真实 HTTP 出口编码和计量。实际甘特由 `ActualGanttService` 组合计划与共同执行台账投影，现场状态、已报工和更正沿真实事件读取，缺失与未知值分别保留。

## 2. 准备、选择和布局

计划甘特的职责顺序为：

1. `PlanGanttModel.prepare(data)` 将后端受控紧凑引用展开为完整任务/资源事实（该展开职责已从 `PlanContract.js` 归位至 `PlanGanttModel`），一次性解析固定时间、标签、搜索文本、当前与基准任务、占用和来源事实；数据改变时才重新准备。
2. `groupPrepared` 根据设备或人员视角和基准开关建立组、冲突与轨道事实。
3. `selectPrepared` 根据搜索和仅看变化筛选成员，并更新可见成员的小汇总，复用已准备时间与轨道。
4. `layoutPrepared(prepared, width)` 只处理位置、点工序轨道的像素间距和定位索引。宽度或缩放变化进入这一层。
5. `visibleRows`、`visibleItems` 和 `PointGanttModel.visible` 选择当前视窗内的行与成员，绘制、命中和交互共用这批可见内容。

`PlanGantt` 用分开的 `useMemo` 表达以上依赖，hover 和滚动不会触发固定数据准备。总览条的固定区间与点列表按数据准备，直方图几何在实际宽度变化时重建。

实际甘特的 `prepare(data, asOf)` 一次准备工序、报工 marks、搜索文本、时间轴和任务索引；`groupPrepared` 建立当前视角的分组；`layoutPrepared` 根据搜索、偏差条件、选中集合和折叠状态生成可见汇总、行位置及任务/报工定位。宽度经 `ActualGanttWindow` 转为显示几何，不重新解析报工事实。固定原始 marks 和本次可见 marks 分别承担事实与显示职责。

候选及比较基线同样使用 `prepare → groupPrepared → selectPrepared → layoutPrepared`。工作区持有固定准备，query 只筛已准备成员并更新可见汇总；轨道号和重叠标记来自完整分组，搜索后保留这份分组事实。基线开关复用 retainedResult。候选 Lane 已接共同 `useCanvasPaint`，可见集由父层计算一次。实际甘特的默认视口、缩放与定位直接消费准备好的 range/task/report 索引。

## 3. Canvas 生命周期与可见区

`GanttPresentation.useCanvasPaint` 负责计划、实际和候选 Canvas 的真实绘制出口：

- 节点挂载时登记一次主题、尺寸和打印监听；卸载时断开 observer、移除监听并取消待执行帧。
- 最新 paint 回调由 ref 持有，数据和几何变化只安排重绘。`requestAnimationFrame` 合并同一帧的触发。
- 真实绘制时读取当前 CSS 调色板，按 `devicePixelRatio` 调整缓冲区，清理并绘制当前可见成员。
- hover、详情和关系高亮使用自己的状态及叠层；成员选择、命中和键盘导航共用当前布局及可见索引。

`GanttGraph` 拥有关系索引、选中链与连线路径；其事实索引在图数据变化时准备，屏幕宽度和视窗只改变路径几何。选中任务或报工条仍可定位、查看稳定详情及沿链导航。

`RunDecisionResourceHeatmap` 直接消费后端 `heatmap.buckets/items`、现成 cell 与 continuation，准备资源、行、列和组的查询索引。切换当前/对照/差值只生成对应显示值，键盘和钻取沿真实 bucket 身份操作。

## 4. 时间、点工序与实际状态

- 时间轴使用工厂本地墙钟字段，与浏览器时区和夏令时分离；业务时间文本保留秒和原有小数精度，轴标签只负责显示。
- 合法零工时工序显示为点标记，不放大成占用区间，不消耗设备或人员容量。`PointGanttModel.prepareTracks/layoutTracks` 统一轨道与最小命中区域，Canvas 和 DOM 标记沿同一规则。
- 当前安排与原安排各有来源。试调比较自己的原安排；计划采用来源和候选的比较基准由后端明确投影。
- 实际甘特以真实报工、旧事件和更正后的共同台账表达开工、完工、未知数量和未知工时。计划结束与现场实际结束保持各自字段和含义，零工时计划也需真实执行事实才能显示实际完工。
- 缩放、打印和跨宽度恢复保持时间中心与可见时长；实际甘特保留服务端的 `axis_span/as_of`，显示窗口由 `ActualGanttWindow` 管理。

## 5. 交互、输出与写入边界

图形负责选择、定位、筛选、关系高亮、详情和只读比较。试调决策编辑、保存和正式采用由试调领域命令处理；绘制函数不写正式安排。报工和更正经执行台账命令及回执恢复，图形刷新消费已确认事实。

公开任务、计划和资源使用各自永久引用，程序定位与用户名称分开。详情保留工序、批次/分件、资源、时间、数量、风险和来源，错误与空结果分别展示。请求信封、快照/计划绑定（如 `ActualGanttContract` 的 `snapshot_ref`、`d.plan` 视图能力与 `d.items_complete === true` 守卫）由 API/Contract 边界确认，不再在主线程对本机受控 DTO 逐行重扫范围或排序；内部显示模型直接消费已准入数据。

计划/实际 JSON 在 Web 最终信封上编码 UTF-8 并直接发送相同字节；导出在自己的文件出口生成。保留实际端点的大小和行数约束，内部甘特投影不预演整份 HTTP JSON。报表详情按实际 `plan + detail` DTO 读取并统一经 `ReportAPI.validate` 核验 `snapshot_ref` 与 `plan_ref`，不重新请求整页报表数据。

浏览器验证通过当前宿主实际浏览器或项目[工具入口](../reference/tools.md)取得真实渲染与交互证据，21 项 Node `vm.Context` 显示与交互合同（`tests/workbench/test_ui_refinement_node_contracts.py`）并入常规 pytest。局部用例、实际页面与最终整合检查分别记录覆盖范围。

## 6. 历史页面与数据兼容

- 2026-05—06 的经典甘特由 Frappe Gantt、本地 `static/js/gantt_*` 与旧 `/scheduler/gantt/data`、模板共同实现只读任务条、详情、负荷条带与沿链导航；这是旧路由层的历史结构。
- 2026-09-18 旧页面路由和模板退役，现行查看入口统一进入工作台。旧 Frappe 的 URL 缩放档位、脚本加载序和 vendor 补丁规则保留在对应历史记录与 [vendor 说明](../vendor/frappe-gantt-local-patches.md)，不作为当前 Canvas 接线要求。
- 2026-09-20 旧 Draft/Validation/Scenario/Publish 服务及草稿保存链退役。历史 `ScheduleAdjustmentScenario` 和行数据继续由工作台计划目录按永久来源读取；当前试调保存与正式采用走 `core/services/workbench/trial/`。
- 2026-10-15 计划、实际、候选及比较基线均退出原一次性布局入口，固定准备、可见汇总、布局与绘制分别归口。历史测试和截图继续绑定各自当时源码及界面。

相关说明：[工作台宿主](workbench-shell.md)、[排产服务](service-scheduler.md)。
