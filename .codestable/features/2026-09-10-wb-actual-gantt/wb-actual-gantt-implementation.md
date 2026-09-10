---
doc_type: feature-implementation
feature: wb-actual-gantt
status: pending-integration
created: 2026-09-10
summary: AL现场实际甘特整页、同快照只读查询及CSV，消费AJ唯一执行投影。
tags: [workbench, fieldgantt, execution, readonly]
---

# 现场实际甘特交付

## 范围和接点

全移植依据为已批准的 `workbench-contracts.md` 第4/6节与本轮用户授权。只新增 AL 独有文件；未修改 Plan、Field、Ledger、共享控件、全局 schema/路由注册、main 或 build；未 build/commit，未使用生产数据库。

- 注册：`web.routes.workbench.actual_gantt.register_actual_gantt_routes(bp)`。
- 服务：`core.services.workbench.actual_gantt.ActualGanttService(conn, logger=None)`；`read_snapshot()`、`workspace(ActualGanttScope)` 返回 `(public_data, private_fingerprint)`。
- 页面：`window.ActualGanttWorkspace({onNavigate, initialContext})`；可选 `adapter` 仅供独立测试，公开方法为 `load(context, signal)`、`export(context, signal)`。
- UI加载顺序：`ActualGanttModel.js`、`ActualGanttContract.js`、`ActualGanttAPI.js`、`ActualGanttControls.jsx`、`ActualGanttCanvas.jsx`、`ActualGanttRows.jsx`、`ActualGanttWorkspace.jsx`。
- 既有依赖：`APSResourceContract`、`APSResourceAPI`、`ResourceControls`、无明确计划时的 `APSPlanAPI`，以及原 `fg-/gb-` 样式和公共 tokens。日期与下拉沿既有 WorkbenchControls 宿主；它的 CalendarContract 依赖也须加载。

页面接受 `plan_ref`、`task_ref`、`scope`、`return_to:{view,context}`。未给计划且没有其他来源范围时，从真实目录寻找唯一当前正式计划；明确计划失效绝不替换。范围支持规范 `scope` 对象，也保留既有 Plan 页顶层起止日期字段。

## HTTP 和 DTO

```text
GET /api/workbench/v1/actual-gantt?plan_ref=<permanent-ref>
GET /api/workbench/v1/actual-gantt/export?plan_ref=<ref>&snapshot_ref=<read-ref>&format=csv

data = {
  plan, scope, plan_span, axis_span, calendar,
  availability:{state,reason_code,reason},
  items:[{task:<既有TaskProjection>,execution:<AJ完整ExecutionProjection>|null}],
  task_count, report_count, items_complete:true, resources,
  critical_chain:{state,reason,task_refs,edges}, semantics
}
```

标准 QuerySuccess 外壳的 `source=production`、`time_basis=factory_local`、`as_of`、`snapshot_ref` 保持现行合同。`report_count=null` 表示不可用，不是零。私有事实只参加快照指纹，不作为 DTO 暴露。

同一个连接和读取事务内，先调用现有 `WorkbenchPlanQueryService.workspace(PlanReadScope(plan_ref))` 读取完整计划，再调用 AJ `ExecutionLedgerService.workspace_projection(plan_ref, tasks)`。不读取旧 event 数组自行重算状态，不复制报工数量、工时或完成算法。历史计划的 `comparison_task_ref` 必须等于所选计划任务；`current_task_ref` 和报工录入依据不得覆盖它。

## 范围和导出

- 服务端支持 `plan_finish_date_from/to`（含两端日期）、`range_start/end`（原计划时段半开相交）、`resource_type=machine|operator + resource_ref`、JSON数组 `batch_ids`。
- 资源条件匹配计划、逐次实际、旧实际永久资源引用或已有剩余安排所关联的工序；入选工序保留全部有效报工，工序数和报工数分别计数。旧资源身份歧义且无法判定是否入选时明确拒绝，不误报无匹配。
- 不支持的参数、重复参数、半边日期、时区后缀、未知实体/旧快照均明确拒绝。`resource_type=batch` 不发送；批次范围使用 `batch_ids`。
- 搜索、晚期和仅选中属于本地视图。导出另传 `local_query`、`late_filter`、`selected_task_ref`，仍绑定原服务端范围和快照；服务器对全量工序重新应用相同显示筛选，绝不 dump DOM。
- CSV 为 UTF-8 BOM，逐条保留报告、录入依据 refs、计划/实际资源和时间、剩余安排、未知空值、旧事实、数据缺项、读取时间、快照、规范范围及本地筛选。公式起始文本转为文字单元格。无新报工的一道工序仍保留一行，不伪造 report。
- 范围内无匹配工序可导出只有表头的 CSV；UI禁用空视图按钮。已发生事实或隐含日历数据变化时原下载返回 `snapshot_stale`，要求明确刷新。
- 继承计划的 10000 任务上限；50000 报工事实、32 MiB 实际甘特响应上限并受 AJ 16 MiB 完整执行投影上限约束。超限拒绝，不截断。

## 页面行为

三视图、范围/资源/晚期筛选、图例、展开/折叠、选中、详情、逐次报告选择、缩放、适应、定位、来源返回及 CSV 均可达。返回上下文无递归嵌套，保存本页选择、筛选、缩放和滚动偏好。

计划基线只在原计划资源出现一次，位于实际轨下方；各实际子轨另有计划完工时点。没有结束只画开工点，不连到数据时点。没有真实剩余安排显示“待续排”，不从计划尾段或数量比例造时段。旧 finish 仍整道完成，旧数量/工时未知不转零。

时间轴包含真实计划、报工、已有剩余安排和绑定快照的数据时点。浏览器以 UTC 数值作本地墙钟坐标，不改变传输字段为 UTC；跨夜/DST 不折掉小时。时点只用细线，无参考灰色背景带。窄条保持真实时间宽度，不扩大命中区域。

实际重叠按 report_ref 和真实资源分子轨，不标记为安排冲突。冻结栏遮住水平滚入的图形；纵向二分虚拟行与密集行 canvas 限制 DOM 数量。资源长中文限两行并提供完整 title，工序标题/详细数据可选择核对。

## 验证边界

所有数据库夹具使用真实 `core.infrastructure.database.get_connection`。Flask 每请求断言 `WorkCalendar.date` 确实是 `datetime.date`，并开启 `PRAGMA query_only=ON`。包含全局与人员夜班日历、DATE型交期和私有 BLOB；不只覆盖裸 SQLite 字符串。

专属测试：`test_actual_gantt_api.py`、`test_actual_gantt_ui.py`，支持/探针文件均使用 `test_actual_gantt*` 命名。API覆盖真实ledger、跨版本引用、旧finish、旧资源、unknown/0、同范围CSV、过期拒绝、10000/10001容量、converter和同事务并发快照。

Chrome 109 实测通过的早期基线为 1920/1392 浅深主题、390窄屏、日期弹层、真实鼠标/键盘操作、真实临时Flask CSV、10000任务显示夹具虚拟化及非空实际canvas像素。最终源哈希、截图、API次数和临时DB未改证明由最近一次 `result.json` / `db-evidence.json` 记录；最终复跑位置在收尾补充。

10000行页面密集数据是明确标记的内存显示夹具；10000工序服务端另有真实临时SQLite测试。既有剩余安排目前仅 DTO 夹具提供；AJ 尚未提供真实剩余安排证据时保持 null。无绑定本次执行快照的真实引擎关键链，当前明确不可用，不展示伪关键链。

新ledger未安装/结构不完整时显示“新报工执行投影尚未安装或安装不完整”，只显示真实计划，execution/null、实际指标不可用，实际CSV禁止；不伪装整页生产集成完成。

主代理负责 v25 迁移、全局路由/页面注册、pending-live闭合与最终打包。AL不启动会覆盖共享门禁产物的全仓门禁；目前为 dirty-worktree 局部验证，不是 clean-worktree proof，也不是 Win7 真机验收。

## 最终局部证据

最终产品源码验证环境：Python 3.8.10、Chromium 109.0.5414.46、macOS；浏览器时区刻意设置为 America/New_York，工厂墙钟轴不随浏览器 DST 改变。

```text
.venv/bin/python -m pytest -q -s tests/workbench/test_actual_gantt_api.py tests/workbench/test_actual_gantt_ui.py tests/workbench/test_plan_query_api.py tests/workbench/test_plan_export_api.py
80 passed in 91.94s
```

其中 actual 专属20条API、2条模型/浏览器测试，另有58条计划只读/导出回归；本轮独有 Python 文件 `ruff check` 全部通过，定向 `git diff --check` 无错误。所有新增文件仍未提交。

最终浏览器证据目录：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/actual-gantt-ui-pouo5wh4/`。

- `result.json`：11组交互、11截图、18次真实临时 API 读取；页面异常与外联均0；21个参与编译的当前源码（含7个ActualGantt模块）及探针SHA-256已核对。
- `db-evidence.json`：3931条记录的SQL语句，临时数据库前后内容 `unchanged=true`；每请求使用get_connection和query_only，并断言DATE转换。
- `actual.csv`：真实下载，搜索FG-003仍导出同一道工序全部FG-001/002/003逐次记录，符合工序集合与报工集合分开的合同。
- 10000任务显示夹具只挂载8行，实际canvas读取到2726个非透明像素；另有真实SQLite 10000工序完整读取与10001拒绝测试。
- 已查看最终1920浅色、1392深色截图；早期额外查看过日期弹层、窄屏、水平冻结与密集末页。末端刻度无法完整容纳文字时保留刻度线和title，不画被裁半的日期。

v25已由主代理合入schema.sql后，未安装测试必须主动在临时夹具中移除 `execution_ledger_objects()` 列出的对象，再证明GET没有补建。此动作只发生于测试临时数据库，未修改产品schema或迁移注册。
