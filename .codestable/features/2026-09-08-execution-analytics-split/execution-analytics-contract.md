---
doc_type: feature-design
feature: execution-analytics-split
status: approved
date: 2026-09-08
summary: 执行复盘与报表中心独立入口，增加基于同源数据的分析总览与专题报表
tags: [prototype, analytics, reports, shared-scope]
---

# 执行分析与报表拆分合同

## 授权与范围
用户已批准两个独立侧栏入口及并行实施。主代理负责共享计算、筛选控件、入口和跨页验证；两个 worker 分别实现执行复盘和报表中心。保留其他页面、已有草稿、生产后端及既有主数据/系统管理，不接数据库、不升级依赖。

## 页面职责
- `review` / `ExecutionReviewScreen`：默认分析总览，不以长表作为第一屏主体。应完兑现、计划/实际累计曲线、偏差分布、未闭合工序账龄、资源已报工时与事实重点；点图或重点进入对应专题的明细。
- `reports` / `ReportsScreen`：工序兑现、报工记录、设备工时、人员工时、数据完整性五类可用专题，每类包含相应汇总/必要图表/明细/CSV。批次交付、日历利用率、停机原因仍不能从当前样例臆造。
- 两页复用同一分析模型、筛选范围和容差。单道工序不冒充批次，已报工时不冒充利用率，异常标记不冒充原因归因。

## 共享模型接口（主代理实现）
全局 `window.APSExecutionAnalysis`，依赖已加载的 `APSReportWorkbench`，不改原始任务/报工记录。

`build(scope, host=window)` 返回下列结构，坏来源/非法日期直接抛错，由页面呈现错误而非旧数据：

```text
scope = {source:'current'|'complex'|'dense', dateFrom:'YYYY-MM-DD', dateTo:'YYYY-MM-DD',
         batch:'', resourceType:'all'|'machine'|'person', resource:'', search:'',
         focus:'all'|'due'|'unclosed'|'finishLate'|'incomplete'|'resourceChanged'}
result = {
 scope, source, sourceRows, cohortRows, rows,
 choices:{batches:string[], machines:string[], people:string[]},
 asOfLabel:string, rangeLabel:string, toleranceMinutes:10,
 summary:{operations,batches,due,confirmedDue,unclosedDue,lateOpen,fulfilledRate,
          dueOnTime,ontimeRate,completed,completedOnTime,completedOnTimeRate,
          finishSample,medianFinish,p90Finish,knownHours,unknownHourRecords,
          records,unreported,incompleteOperations,missingRecords,changedResources},
 trend:[{time:number,label:string,planned:number,actual:number|null,unclosed:number|null}],
 distributions:{finish:[{id,label,count,tone}],start:[{id,label,count,tone}]},
 aging:[{id,label,count,tone}],
 resources:{machines:[{id,resource,operations,batches,records,hours,unknownHours,
                       changedOperations,openOperations}],people:[same]},
 insights:[{id,title,detail,tone,focus,topic,batch?,resourceType?,resource?}],
 limitations:string[]
}
```

- `source` 是原 `APSReportWorkbench.source` 的结果；`rows` 保留原 `snapshot` 行，增加 `due`、`confirmedDue`、`unclosed`、`lateOpen`、`ageMinutes`、`finishLate`、`onTime`、`missing`、`resourceChanged`。
- 日期选取计划完工日期所在的工序群体；缺计划完工日期单列警告并不进入时间范围分母。日期上限保持原模型数据，不假设实际结束。统计截止原数据源 `model.state.clock`，不是系统现在。
- `cohortRows` 按日期、批次、关联计划/实际资源和搜索筛选；`rows` 在其上叠加 `focus`。图表/指标/导出必须使用同一 `rows`。
- 兑现率 = 已确认完工的应完工序 / 应完工序；按期率 = 在计划完工+10分钟内完工的应完工序 / 应完工序。分母为0返回null。
- 未闭合含刚到计划截止点；`lateOpen` 严格超过截止点+容差10分钟。未闭合的统计时点差距不记作真实完工偏差。
- 新分析行的开工/完工/未闭合偏差标记也统一超过10分钟才出现，CSV沿用这组标记。原`APSReportWorkbench.snapshot`的原始正偏差接口保留，不全局改变旧调用方。
- 偏差中位数和P90仅使用已完工且有计划结束的工序，必须显示样本量；分布分为提前>10m、±10m、延后10-30m、30-120m、>120m。
- `trend` 用当前记录按实际发生时间回算，不冒充历史当时快照。实际线到数据时点为止，未来为null；不会按计划跨度线性摊派完成数量或有效工时。
- 资源工时汇总来自所选工序的全部实际记录；未填资源、未知工时独立保留，不按工时多少评价人员效率。
- `insights` 只陈述可核实的差距/分布/数据缺口，不将资源关联称为因果、不产生自动责任结论。

其他方法：
- `defaults(sourceId, host=window)` -> 合法默认scope；默认来源current，日期覆盖该源计划。
- `linkScope(result, patch={})` -> result.scope与patch的纯对象副本；只传播公开筛选字段，不含数据行。
- `formatPercent(number|null)` -> `33.3%`或`—`；`formatNumber(number|null)` -> `7.5`或`—`。
- `summaryCSV(result)` -> `{text,count,filename}`，由现有`APSReportWorkbench.download`下载。
- `tableCSV(result, kind, sortedRows)` -> 同样下载结构；只允许所选范围全量、唯一记录，增加范围日期、批次、资源、搜索、focus和容差列。
- `warnings:string[]` 单列动态数据缺口，保持可见；`limitations` 仅为可折叠的固定口径。`incompleteOperations` 只计字段待补，未报工由`unreported`单列。
- 资源分组额外提供`resourceKey`原始值；未填资源用`__unassigned__`作为筛选值，不能使用显示文字代替身份。

## 共享界面接口（主代理实现）
`window.APSAnalysisUI`：
- `ScopeBar({analysis, scope, onChange, idPrefix})`：数据源/日期/批次/关联资源/搜索/范围focus，必须两页使用。
- `TrendChart({points, label})`：计划灰蓝、实际主题蓝，未来actual=null不绘制，SVG线图+可读取数据表。
- `DistributionChart({items, label, onSelect?})`：横条对比，标签和数值不塞进短条，可键盘点击分组。
- `Icon({name})`：沿用本地Lucide子集。

ScopeBar在analysis不可用时仍提供来源/日期输入，页面自己显示错误。两页顶层props都为`{onNav,scope,onScopeChange,initialContext}`；scope由App保存，两页sidebar互换仍保留；业务跳转用`onNav('reports'|'review',{scope,topic})`。报表跳转甘特仍用`{source,search}`原协议。

## 布局与验收
沿用工作台平直指标条、轻分隔、右侧命令、左侧筛选；页面区块不做浮动卡片，图表主体比明细更突出。按窗口收缩重排而非缩小字号，主题使用现有ui变量。

必须验证：两个独立侧栏；当前3应完/1确认、复杂10应完/7确认；分母0、空结果、坏日期、缺失时间；完工容差边界；样例和原报工隔离；筛选与图表/CSV对账；跨页保留条件；160道密集样例；两主题和键盘操作。此处仅静态原型，浏览器访问先前被拒绝，不绕过，也不声称像素验收。
