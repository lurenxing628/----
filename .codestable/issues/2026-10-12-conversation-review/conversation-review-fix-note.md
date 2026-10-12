---
doc_type: issue-fix
issue: 2026-10-12-conversation-review
path: review-and-fix
fix_date: 2026-10-12
status: fixed
tags: [workbench, gantt, provenance, baseline, maintenance]
---

# 本对话改动整体审查与同根因修复

## 范围

覆盖本对话未提交的产品改动及直接调用路径：完整工艺图/关键链，正式、候选、实际、试调、值班台和现场时间线，共享日期/控件与主题，原安排/来源/数量投影，系统管理状态处理；同时核对新增和改动的契约、构建产物及相关说明。六条独立审查线的发现由主代理核验、合并并完成修复。用户进一步要求对“未知”追到保存记录和投影源头。

## 已修复的根因

### 已有事实在投影或展示中丢失

- 候选关键链原来从展示资源引用建立依赖；冻结资源目录或引用缺失时，仍存在的机器/人员安排也随之丢失。现在从已验证原始任务分配建立资源边。
- 资源目录缺少名称时保留永久资源身份。名称缺失、身份缺失、合法未指定、外协不适用和零工时不占用分别表达；详情现有编号区保留可核对的资源引用。
- 候选原安排供应商原先固定为 null，外协工序还被无条件判成历史供应商未记录。现在从对应正式版本的候选/试调采用来源读取原 source 和供应商；时间相同、供应商相同的外协安排可正确判为未变化。
- 明确新增、移除或双方均未安排与证据缺失分开处理。新增/移除计工序变化；更换设备仅比较两边已有安排。首轮无正式计划明确显示“无原安排/不适用”，交付对比值保持 null 及对应原因。
- 正式计划原安排原先硬置供应商为空，资源目录仅覆盖当前安排。现在当前和原安排分别读取自己的采用来源，现有目录覆盖对照双方实际引用的资源；原安排独有的冻结名称进入目录。采用后修改当前供应商不会改变历史正式计划的供应商身份。同一永久引用继续沿用既有名称展示语义。
- 采用凭据缺失、已归档、不一致保留原分类及具体原因。正式来源/原安排原因直接展示，计划类型和版本按实际身份显示。
- 正式、候选数量为空时直接显示对应来源原因，真实零值保留。移除候选页硬编码的“系统没有实际工时和成本记录”伪指标；实际报工数据由现有现场模块负责。

### 时间坐标截断

合法微秒级正时长经 Date.parse 截成零跨度，现场时间线产生 NaN 坐标。PlanGanttModel.instant 统一保留分数秒，正式、候选、实际、试调、值班台及现场时间线共用；业务时间字符串保留原精度。

### 打印分页与连线分离

正式/候选轨道自然分页，整层绝对坐标 SVG 未随轨道移动，造成后续页箭头悬空。打印改用每轨的共享 SVG 裁片，屏幕继续使用整层连线；关键任务标记与连线均保留。

### 维护状态缺少恢复闭环

- 临时维护锁释放后缺少有效重查入口。现在状态重查、页面刷新和网络恢复进入共同查询路径，较旧响应不覆盖新结果。
- HTTP 503 等明确 committed:false 被当作结果未知，导致恢复请求长期 pending。明确拒绝立即结束持久 pending，并保留当前页拒绝详情；未知提交结果继续保留操作编号。
- 整页重载、网络恢复及跨标签确认沿同一语义处理。已被另一标签确认清除的编号视为完成，不同编号保持原记录并提示。

## 主要实现入口

- `core/services/workbench/facts/gantt_graph.py`、`candidate_tasks.py`、`candidate_baseline.py`
- `core/models/workbench_run_baseline.py`、`workbench_run_analysis.py`
- `core/services/workbench/plan/adoption_baseline_sources.py`、`adoption_baseline_identity.py`、`projection.py`、`workspace_dto.py`、`queries.py`、`baseline.py`、`point_evidence.py`
- `core/services/workbench/run/candidates.py`、`candidate_baseline.py`、`candidate_comparison.py`
- `frontend/workbench/app/GanttGraph.js`、`GanttGraphLayer.jsx`、`PlanGantt.jsx`、`RunCandidateGantt.jsx`、各时间线的共同坐标入口
- `PlanContract.js`、`PlanDetailsUI.jsx`、`RunCandidateModel.js`、`RunCandidateControls.jsx`、`RunCandidateAnalysis.jsx`、`RunBaselineAPI.js`、`RunBaselineModel.js`、`RunBaselineControls.jsx`
- `SystemMaintenanceAPI.js`、`SystemMaintenanceWorkspace.jsx`、`SystemMaintenanceControls.jsx`

正式基准仍沿既有四项比较字段：开始、结束、设备、人员。本轮恢复既有供应商字段与资源目录，未增加公开字段或改名比较功能。

## 实际验证

- 真实临时 SQLite/worker/采用链覆盖：资源引用及目录缺失仍保留关键链；候选采用、候选来源试调采用、正式来源试调采用；相同外协安排、供应商变更、采用后当前资料改名；V1/V2 各自保留对应供应商，原安排独有 M1/O1 名称完整；来源不一致保留原错误分类。
- 只读核验现有 8 份候选共 632 道安排：数量缺失、设备/人员身份或名称缺失、调整数量未知、更换设备数量未知、候选交付未知均为 0。前四份无正式基准，保留明确 no_admission_baseline 原因；后四份原安排交付依据完整。
- 最终 Chrome 109 构建通过。日常门禁 Ruff 通过，342 passed / 20 skipped。首轮唯一失败是目录缺失用例仍要求删除资源对象；断言已与保留身份/缺项说明的新契约同步，最终完整日常门禁通过。
- 39 个改动 Python 文件通过 Python 3.8 语法检查，git diff --check 通过。
- Chrome 完整系统管理 19 项交互检查通过；真实完整应用正式/候选/首次排产页面另 13 项检查通过，包括最终 DTO、原安排显示、72/79 变更筛选含两道零工时、来源和数量、无原安排语义及无页面接口错误。
- 正式 9 行/9 个打印裁片、候选 10 行/10 个打印裁片；两页 PDF 目视确认箭头落到任务边。共享真实组件回归覆盖微秒正时长与零工时区分、打印裁片和来源原因。
- 期间本机休眠影响了墙钟耗时；最终用例计时最慢 3.54 秒，未据休眠时长判定产品性能回退。

证据：`output/playwright/conversation-review-20261012/` 的 `daily-gate-final.log`、`final-pages-check.log`、`system-browser-check.js`、`formal-final.png`、`candidate-final.png`；打印证据为 `output/playwright/gantt-full-pages-20261012/review-*-print-fixed-*.png` 及对应 PDF。

完整应用使用正式 app_main 启动，验证数据库、备份、日志和维护记录位于本对话隔离目录。生产数据库未改动。上述证明为当前改动工作区的审查、定点/日常门禁及浏览器验证；未执行提交、打包发布或最终 clean-worktree 门禁。
