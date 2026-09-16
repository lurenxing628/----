---
doc_type: issue
slug: workbench-utilization
status: fixed
created: 2026-09-15
last_reviewed: 2026-09-15
related_roadmap: workbench-manual-remediation
roadmap_item: wbfix-utilization
validation_status: targeted-passed-manual-pending
---

# 资源利用率口径统一

## 问题与结论

旧 ReportEngine.utilization 使用任务起止的自然跨度累加，再除以全局、效率加权的容量。工作台则按逐资源可用区间取占用交集，跨夜、个人班表和停机条件下会得到不同数字。此次将资源占用率统一为 `班表内占用并集 / 逐资源可用时长`，没有修改排产算法或真实数据库。

同一时间段安排三个各占 8 小时的任务时，占用为 8 小时、累计负荷为 24 小时、重叠负荷为 16 小时。没有把累计负荷静默截成 8 小时，也没有把冲突隐藏在一个 100% 比率里。班表外时段按并集单列；它不是加工工时。

## 实现

- `core/services/workbench/resource_utilization_metrics.py`：共享的区间计算内核，固定口径版本 `available_occupancy_v1`。整窗与逐日查询使用同一套索引；占用率不使用效率乘数。零可用时长返回 null；缺日历返回未知并保留已知自然跨度。
- `core/services/report/utilization_calendars.py`：复用工作台 CalendarFacts、SnapshotCalendarEngine、policy_projection、apply_resource，读取实际资源状态、个人/轮班日历和有效停机。读取有日期、资源日期组合和记录数量上限，不写入或补齐资料。
- `core/services/report/utilization.py`、`calculations.py`、`report_engine.py`：移除旧共享容量标量计算路径，逐资源计算，保留坏时间行留痕和零容量说明；未知日历明确留痕。`capacity_hours_per_resource` 兼容字段仅在所有资源分母相同时提供数字，不能用来代替逐行分母。已使用的 `parse_dt`、`overlap_seconds` re-export 保留。
- `dashboard_resource_metrics.py`、`plan_occupancy.py`：消费同一内核。已有严格 DTO 的历史字段名保留：`available_occupied_hours` / `inside_available_hours` 对应规范内的 occupied_hours；旧 occupied_hours 仍表示自然跨度并集。日报响应另含同窗 window_metrics，可与报表直接核对。
- `DashboardPanels.jsx`：资源压力表展示“班表内占用”“整窗占用率”“重叠时段”，分子直接取 available_occupied_hours；不再把自然跨度作为占用分子展示。
- `report_catalog.py`、`report/exporters/xlsx.py`：网页、CSV、XLSX 使用相同已计算行，列明班表内占用、可用工时、整窗占用率、累计负荷、重叠负荷和班表外占用。导出包含计算版本和固定范围，旧 XLSX 导出也使用相同列和百分比格式。原 query / plan_ref / snapshot_ref 及导出全筛选集规则保留。

报表的“生产数据 source=production”与统计来源不是一回事；现有资源利用率入口仍明确是 `metric_source=planned`。已有实际工时报表继续读取执行事实。共享内核接受 actual 区间且不从计划补值，但没有新增独立的“实际占用率”界面入口，不把这次变更说成已经交付了该额外界面。

## 测试与证据

一次完整定点回归：**137 passed in 73.10s**，覆盖以下文件：

- `tests/workbench/test_resource_utilization_shared.py`
- `tests/scheduler_analysis/test_report_calendar_capacity_intersections.py`
- `tests/scheduler_analysis/test_report_source_case_insensitive.py`
- `tests/workbench/test_report_export.py`
- `tests/workbench/test_plan_occupancy.py`
- `tests/workbench/test_final_operations_analysis.py`
- `tests/workbench/test_round1_analytics_contract.py`
- `tests/scheduler_analysis/test_report_a6_dependency_boundary.py`
- `tests/scheduler_analysis/test_utilization_zero_capacity_degradation.py`
- `tests/scheduler_analysis/test_source_merge_mode_constants.py`
- `tests/web_pages/test_reports_workbench_backlink_contract.py`
- `tests/calendar_maintenance/test_calendar_shift_hours_roundtrip.py`
- `tests/scheduler_analysis/test_report_export_size_mode_selection.py`

新增合同测试证明跨夜、周末、个人日历、停机、效率、三重重叠、零容量与未知容量、左闭右开边界；用真实临时 SQLite/API 数据逐列核对网页、CSV 与 direct/stream XLSX，并验证日历/资源变化后旧导出快照被拒绝。fixture 中 9 月 2 日设备占用为 0.5 小时、可用 7.5 小时、累计负荷 11.5 小时、重叠负荷 11 小时、班表外跨度 8.5 小时。

旧测试中设备 4 小时占用调整为扣除 1 小时已登记停机后的 3 小时；人员仍为 4 小时。这是批准的公式变化。旧全局效率加权 capacity_hours 的测试被逐资源真实日历测试替代；不保留第二套隐藏分母。

补充资源筛选、候选报表、计划日历及工作台压力专项：相关文件共 132 项。首次 130 通过、2 条候选导出旧断言失败；确认 2026-01-03 默认周六休息后，将其断言改为班表内 0 小时、班表外 4 小时、占用率 null，候选文件重跑 **9 passed in 7.64s**。其余 123 项已通过，产品源码没有因这次断言适配再次变化。补充范围：`test_report_context_filters_contract.py`、`test_scheduler_candidate_reports_contract.py`、`test_plan_calendar.py`、`test_plan_calendar_runtime_dates.py`、`test_dashboard_capacity.py`。

另修正 `report_widgets_probe.cjs` 的过期停机文案断言为当前已有文案“按已登记的停机记录统计。”，同时断言“停机工时（小时）”表头，保留确认切到停机视图的功能验证。该浏览器脚本的集成复跑由主代理负责。

`git diff --check` 与定点 Ruff 的 E9/F63/F7/F82 检查通过。新合同测试已登记在 workbench_reports 必跑组，注册文件后续由 schema_integration_impl 统一维护。

## 验收边界

本工作区已有大量未提交改动，本项不提交、不清理他人文件。以上为本项定点证据，不是 clean-worktree proof。用户明确要求不要跑全量质量门禁；本项未运行 run_quality_gate 的任何模式或整仓测试。未在本项代理中执行全局构建或手动浏览器验收；由主代理集成最终版本后执行构建、专项检查与手动验收。未触碰真实数据库，不需要数据迁移。

## 手动验收补修：计划与试调详情的占用分子

主代理在隔离实例 5001 的正式计划 v14 手动查看任务详情时发现，资源详情仍展示旧 `occupied_hours=389.2`，而占用率按 `available_occupied_hours=101.2 / available_hours=115.8` 计算，出现分子与比例对不上的表达。追查确认计划负荷表、试调资源表也存在同一字段误用。

- `PlanDetailsUI.jsx` 的任务详情与计划负荷表改为显示 `available_occupied_hours`，标签为“班表内占用”；占用率独立列出，`outside_available_hours` 用“班表外占用”单列。原“安排”累计值仍保留。任务详情与表格的占用率统一保留两位小数。
- `TrialResults.jsx` 的资源表使用同一分子和明确标签；不再将自然跨度称为“实际占用”。`TrialContract.js` 要求传回 `available_occupied_hours`，缺失时报数据不完整，不能用 0 或旧跨度代替。
- 没有修改后端算法、原始 `occupied_hours` 兼容语义、正式计划或保存的试调快照，也没有修改 `TrialDetails.jsx` 的执行固定安排说明。

定点验证 `.venv/bin/python -m pytest -q tests/workbench/test_plan_ui.py::test_utilization_details_use_calendar_intersection tests/workbench/test_plan_ui.py::test_plan_ui_model`：**2 passed in 1.50s**。其中新增源组件探针包含 11 个案例，覆盖任务详情、计划负荷表、试调结果三处的跨夜数字、零可用和未知可用；断言 `101.20 / 115.80 = 87.39%`，班表外单列 `288.00`，且渲染没有修改输入。真实临时 SQLite 试调 DTO 另验证 26 小时自然跨度对应班表内 10 小时、班表外 16 小时，缺分子字段被契约拒绝。原计划模型的 15 项断言也通过。

上述补修只做 JSX 源组件编译及定点测试，未运行全局构建、浏览器或全门禁；实际浏览器重验由主代理集成最新资源后执行。
