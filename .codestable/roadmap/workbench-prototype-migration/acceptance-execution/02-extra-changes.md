# 任务 E 额外授权修改清单

## 当前边界

- Main 后续明确授权本域 `FieldWorkspace.jsx`、`ActualGanttWorkspace.jsx`、`ReportWorkspace.jsx`、`ReviewWorkspace.jsx`、`CalibrationWorkspace.jsx` 接入共享 caption 和只读 history snapshot。
- Main 在 B 的 92/92 功能快照完成后明确解除产品 freeze，并授权 E 修复已确证的域内问题，继续剩余验收，无须重复审批。
- Main 后续针对关键链明确追加授权原只读分析 API `core/services/scheduler/gantt_critical_chain.py` 的 keyword-only 目标回溯，不涉及 Greedy 求解策略。详细边界和实际结果见 `05-critical-chain-evidence.md`。
- 不修改共享 `WorkbenchCaption.jsx`、`WorkbenchPageContext.jsx`、main、build-order、factory、数据库 schema、共享身份 DTO 模型或排产容量模块。这些由 Main 负责。下述现场汇总仅扩展本域 `summary` 输出，旧字段保留。
- `symbol_locator whereis FieldWorkspace` 和 `callers FieldWorkspace` 已使用私有 `CHECKUP_CALLGRAPH=/tmp/aps-final-e-resume.o4u6zI/callgraph` 执行；Python 定位器未收录 JSX，补以实际 JSX 定义、main 挂载和组件 probe 源列表核对。

## 产品文件

| 文件 | 限定改动 |
|---|---|
| `frontend/workbench/app/FieldWorkspace.jsx` | 顶层无条件 caption，真实 `data.plan` 身份；范围/分页/选中任务/原来源通过 `useSnapshot` 保存；显式刷新失效分页回第 1 页重新读，保存后按原选中任务定位。后续增加当前组件内的按任务草稿缓存，允许未提交时收起/切对象；取消或保存完成清当前草稿。写表单仍不进 history/localStorage，离开页面不重放 |
| `frontend/workbench/app/ActualGanttWorkspace.jsx` | 同源 caption；本域只读模式、筛选、展开、选中任务/报工、缩放和滚动位置保存/恢复；错误查看状态拒绝，不切其他对象。已修 F5 横向位置在初始化宽度下被截短，等实测板宽渲染后再消费保存位置 |
| `frontend/workbench/app/ReportWorkspace.jsx` | 报表与复盘共用真实 caption；保存经实际响应确认的 scope/topic/table/selected/charts/catalog、滚动位置和 returnTo，不只在业务 go() 时保存 |
| `frontend/workbench/app/ReviewWorkspace.jsx` | 注释明确复用 ReportWorkspace 的一次发布，避免嵌套 hook 互相覆盖 |
| `frontend/workbench/app/CalibrationWorkspace.jsx` | 无计划身份，caption 固定 null；仅保存已验证过滤/分页/模板和样本选择，不保存采用命令、理由、写入凭据 |
| `frontend/workbench/app/FieldEditor.jsx` | 补作业跨度/有效工时差额和已知累计数量预览，未知保持未知，不自动填写工时。接入工作区内暂存草稿并绑定原任务/计划/报工/修订/旧事实身份，身份变化即禁用保存 |
| `frontend/workbench/app/FieldDetail.jsx` | 传递暂存草稿及原身份；读取失败或原记录消失时允许明确取消暂存编辑，不改指其他记录 |
| `frontend/workbench/app/FieldFilters.jsx` | 五指标及状态计数显示服务端完整范围汇总，不由当前分页计算；未知工时明确显示未知和已知小计 |
| `core/services/workbench/field_workspace_scope.py` | 搜索加入已有计划资源名、实际资源名及报工号；不改范围身份/日期/资源校验，不修改数据 |
| `core/services/workbench/field_workspace.py` | 保留原四个 summary 字段，新增状态计数和逐次报工工时汇总；状态计数基于其他筛选后的完整范围且不随状态页签归零，新汇总纳入读取快照指纹。旧执行事件不伪造成逐次报工，不把未知报工工时填零 |

## 测试接线

以下既有域 probe 的显式源列表加入 `WorkbenchCaption.jsx` 和 `WorkbenchPageContext.jsx`，位于 Workspace 前；不改断言或共享构建：

- `tests/workbench/field_workspace_probe_harness.cjs`
- `tests/workbench/test_actual_gantt_browser.cjs`
- `tests/workbench/be_surface_browser.cjs`
- `tests/workbench/report_widgets_probe.cjs`
- `tests/workbench/test_report_ledger_widgets.cjs`
- `tests/workbench/calibration_widgets_probe.cjs`
- `tests/workbench/calibration_lineage_ui_probe.cjs`
- `tests/workbench/calibration_adoption_widgets_probe.cjs`
- `tests/workbench/process_quota_widgets_probe.cjs`

## 已运行与待运行

- caption/snapshot 接入前的真实域后端：第二次运行 6 passed / 1 failed，失败是新测试未隔离模板内既有待补记录，详见私有 `backend-02.xml`；不是已确认产品故障。
- 模板验收改为先核对全部可报任务的预填引用，再从实际下载文件保留两件明确目标行，避免顺带提交其他待补行。保持“只写本次指定目标”的精确断言。
- 真实重启已确认只追加 1 条 `plugins/load` 审计日志及其序列值；测试精确核对这一对表变化，同时要求所有旧行、原报工/修订/计划/来源和其他表不变。不是把日志表全量排除。
- caption/snapshot 后的完整构建、浏览器 F5/侧栏/后退复验正在进行，尚不记为通过。最终源哈希与通过结果另列 handoff。

## 后续验证状态

- 实际甘特水平恢复修复后，四域完整入口只读往返测试 **4 passed / 22.26s**：`/tmp/aps-final-e-repaired.9IGEax/history-01.xml`。仍是指定构建的功能证据，不是最终 HEAD。
- Main 共享日期关闭修复后，`/tmp/aps-final-e-main-current.O4sDrD/aps-workbench-live-88momrto/final-controls-initial.json` 中 **68/68 操作**通过，四组合各 17；内部 wheel 保持打开，外部滚动/resize 各自首次重开后关闭、原输入与焦点不变。整条 pytest 当时因未补的跨度预览失败，未伪报测试通过。
- 搜索修复后旧定点组 **22 passed / 9.70s**；五指标和本轮字段调整后的真实 factory-client + 原接口 + 四组合组件兼容 **26 passed / 22.91s**，后者只含组件级 UI，不冒充完整入口。证据分别在 `/tmp/aps-final-e-field-preview.yxjtcV/search-after.xml`、`field-regression-01.xml`。
- `/tmp/aps-final-e-remaining.TI8M7m/field-01.xml` 已结束：7 passed / 2 failed。四域 history、68 个共享控件操作、搜索通过，现场与校准的实际动作/字节/重启完成后仅在剩余能力 gap 断言失败。不是 69 条能力全部通过。

## 后续本域产品补齐

- `ActualGanttModel.js`、`ActualGanttControls.jsx`、`ActualGanttWorkspace.jsx`：自动/手动和刻度恢复为原型已有的缩放状态显示，不增加虚构独立开关。
- `CalibrationControls.jsx`、`CalibrationWorkspace.jsx`：图号复用现成 `ProcessDetail`，精确 `part_ref`/模板引用，adapter 只提供 detail 且禁止维护，关闭回原校准列表。
- `ReviewCharts.jsx`、`ReportWorkspace.jsx`：三类事实重点下钻、设备/人员工时页签、六组分页、资源名/柱下钻。用真实 scope/ref，未知工时不绘成已知零；原范围、图表和资源页签状态进入只读返回上下文。
- `actual_gantt_chain.py`、`actual_gantt.py`、`web/routes/workbench/actual_gantt.py`、`ActualGanttAPI.js`、`ActualGanttContract.js`、`ActualGanttRows.jsx`、上述两个甘特叶文件及明确获准的原只读引擎：真实全量计划链、目标回溯、严格证据绑定和显示。此批仍在验证，不计最终全通过。
