---
doc_type: feature-acceptance
feature: 2026-05-28-resource-dispatch-calendar-readable-matrix
requirement: resource-dispatch-calendar-readable-output
status: accepted
accepted: 2026-05-28
tags: [resource-dispatch, calendar, excel, frontend]
---

# 资源派工日历矩阵可读化验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-28
> 关联方案 doc：`.codestable/features/2026-05-28-resource-dispatch-calendar-readable-matrix/resource-dispatch-calendar-readable-matrix-design.md`

## 1. 接口契约核对

对照方案第 2.1 节名词层逐一核查：

- [x] 日历 item：`core/services/scheduler/resource_dispatch_rows.py::_append_calendar_segments` 继续生成结构化 `cell.items`，本次只补公开业务字段 `part_name`；没有把 `schedule_id`、`op_id`、`_row_identity`、`source_table`、`state_revision`、`execution_snapshot_revision` 等内部字段塞进用户页面或 Excel。
- [x] 日历任务块：`static/js/resource_dispatch.js::renderCalendar` 不再把 `item.text` 直接堆成连续文字；每条 `cell.items` 会经过 `calendarTaskHtml()` 渲染为独立 `aps-calendar-task`。
- [x] 日历明细 Sheet：`core/services/scheduler/resource_dispatch_excel.py::build_resource_dispatch_workbook` 保留原矩阵 Sheet，并新增 `日历明细`；明细行来自 `calendar_rows[*].cells[*].items[*]`，不是从 `cell.text` 反拆。
- [x] 流程图核对：route / service / viewmodel 编排未改变；页面和 Excel 都继续消费装饰后的公开 payload。`git diff --name-only` 未出现 repository 文件，说明本次没有改 SQL 查询口径。

## 2. 行为与决策核对

- [x] D1 复用 `cell.items`：页面任务块和 Excel 明细都读取结构化 item，没有拆字符串。
- [x] D2 不大改后端结构：只补 `part_name` 公开字段，不新增表、不改路由、不改 SQL。
- [x] D3 超期中文：页面任务块有 `badge("超期", "error")` 和 `aps-calendar-task--overdue`，Excel 用 `是否超期` 的“是/否”。
- [x] D4 班组视角一张合并明细：班组导出新增一张 `日历明细`，用 `日历来源` 区分 `班组人员日历` 和 `班组设备日历`。
- [x] D5 保留矩阵：单人/单机继续有 `日历排班`；班组继续有 `班组人员日历` 和 `班组设备日历`。
- [x] 明确不做：没有新增拖拽排程、热力图、复杂折叠、外部 CDN、依赖升级或 repository SQL 改动。
- [x] 挂载点反向核对：实际改动落在方案第 2.3 节列出的 UI、CSS、Excel、帮助说明位置；额外增加 CodeStable design / checklist / acceptance、architecture、requirement，这是验收落档需要。
- [x] 拔除沙盘推演：若要回滚本 feature，按挂载点移除 `calendarTaskHtml` 任务块结构、CSS 任务块规则、Excel `日历明细` 写入、帮助说明和对应测试即可；不会牵连数据库或排程算法。

## 3. 验收场景核对

- [x] S1 多任务格子可读：浏览器打开用户 URL 后，`#rdCalendarTable` 里有 564 个 `.aps-calendar-task`；抽查一个格子有 9 条任务，任务之间通过独立块和间距分开。
- [x] S2 超期中文：当前用户 URL 的汇总显示超期任务为 0，所以真实页面没有可见超期任务块；回归测试用超期 item 锁住 `aps-calendar-task--overdue` 和中文 `超期`。
- [x] S3 固定左列：浏览器检查到 19 个 `.aps-calendar-scope-cell`，计算样式 `position: sticky; left: 0px`，横向看 30 天时不会丢失查询对象。
- [x] S4 字段分行：任务块显示时间、批次、工序、计划设备、计划人员、图号 / 物料；设备/人员显示名称和“编号：...”分行，不再用“完整身份”把编号和名称挤在一行。
- [x] S5 单人/单机 Excel：冒烟测试确认 Sheet 顺序为 `查询摘要`、`任务明细`、`日历排班`、`日历明细`。
- [x] S6 班组 Excel：冒烟测试确认仍保留 `班组人员日历`、`班组设备日历`，并新增 `日历明细`；合同测试确认来源列为 `班组人员日历` / `班组设备日历`。
- [x] S7 空数据：合同测试确认空日历也生成 `日历明细`，且只有中文表头，不报错。
- [x] S8 内部字段不外显：合同测试把内部字段和值塞进日历 item，最终 workbook 不包含这些字段名和值。
- [x] S9 护眼模式：CSS 有 `html[data-theme="dark"] .aps-calendar-task` 和超期任务块深色规则；浏览器当前页面处于深色风格，任务块没有刺眼白底。

浏览器验证地址：

`http://127.0.0.1:61731/scheduler/resource-dispatch?version=8&start_date=2026-06-01&end_date=2026-06-30&plan_role=adopted&period_preset=custom`

浏览器证据摘要：

- `tableVisible=true`
- `taskCount=564`
- `multiTaskCellCount=9`
- `scopeStickyCount=19`
- `hasNumberLabel=true`
- `hasOldIdentityLabel=false`
- `overdueCount=0`（当前数据本身没有超期任务）

## 4. 术语一致性

- “日历矩阵”：页面仍使用现有标签和 `rdCalendarTable`，未改含义。
- “日历任务块”：代码统一使用 `aps-calendar-task`，没有和现场反馈任务卡混用。
- “日历明细”：Excel 新增 Sheet 固定叫 `日历明细`，帮助说明、测试和架构文档同名。
- 防冲突：普通页面和 Excel 表头未新增 `op_id`、`schedule_id`、`state_revision`、`execution_snapshot_revision` 等内部字段名。

## 5. 架构归并

- [x] `.codestable/architecture/ARCHITECTURE.md`：已补充资源派工导出现在提供“矩阵表 + 日历明细表”，并强调内部追踪字段不进入普通用户可见输出。
- [x] `.codestable/architecture/ui-gantt.md`：已补充资源排班页面、日历矩阵、日历明细和导出都按同一份计划身份与公开 payload 输出；新增 2026-05-28 变更日志。
- [x] 不需要新增新的 architecture 子文档：本次没有新增独立子系统，也没有改变 route / service / repository 分层。

## 6. requirement 回写

- [x] 已 backfill 当前能力文档：`.codestable/requirements/resource-dispatch-calendar-readable-output.md`。
- [x] 已更新 `.codestable/requirements/VISION.md`，把“看清资源派工和日历明细”放入当前有效能力。
- [x] 需求文档只讲用户为什么需要、怎么被满足和边界，没有塞代码函数名、SQL 或内部实现细节。

## 7. roadmap 回写

- [x] 本 feature 不是从 roadmap 条目启动，design frontmatter 的 `roadmap` / `roadmap_item` 为空，因此无需回写 roadmap items。

## 8. attention.md 候选盘点

- [x] 本 feature 未暴露需要追加到 `.codestable/attention.md` 的新环境坑或长期启动注意事项。
- [x] 已有长期约束（Win7、Python 3.8、Chrome 109、不引外部资源、不暴露内部字段）仍沿用现有 attention / AGENTS / architecture 约束，不重复追加。

## 9. 遗留

- 当前用户 URL 数据本身没有超期任务，所以浏览器不能肉眼看到任务块上的 `超期`；该行为已由回归测试覆盖。
- `static/js/resource_dispatch.js` 和 `static/css/ui_contract.css` 都是存量较长文件，本次只做局部增强；后续若要拆前端文件，应单独走 `cs-refactor`。
- 未发现需要另开 issue 的阻塞问题。

## SubAgent 只读探索记录

- A `019e6ecd-95f7-7391-b746-fd3614fe122f`：资源派工数据链路。结论：`cell.items` 已经是一条任务一条结构化记录；内部字段不应给普通用户看。最终状态：已关闭。
- B `019e6ecd-fae5-7360-8015-1f3678687ae0`：前端和样式。结论：改点在 `renderCalendar()`；可复用 `.table-sticky-col`；任务块要补深色主题样式。最终状态：已关闭。
- C `019e6ecd-fb68-7d22-b7c1-a7a5335b6b02`：Excel 导出。结论：保留矩阵 Sheet，新增 `日历明细` 从 `cell.items` 扁平化。最终状态：已关闭。
- D `019e6ecd-fbca-7b00-bf93-a0c4661fbe35`：测试和 CodeStable。结论：补页面合同、Excel 合同、空数据、内部字段不外显和验收产物。最终状态：已关闭。

## 验证命令

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_table_layout_readability_contract.py tests/regression_resource_dispatch_public_output_contract.py tests/test_scheduler_resource_dispatch_smoke.py tests/test_resource_dispatch_viewmodel.py`：`27 passed`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_resource_dispatch_viewmodel_public_output_contract.py tests/regression_resource_dispatch_export_surfaces_degraded.py tests/regression_resource_dispatch_public_output_contract.py tests/regression_table_layout_readability_contract.py tests/regression_ui_contract_table_overflow_guard.py tests/test_scheduler_resource_dispatch_smoke.py`：`20 passed`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_dispatch_plan_identity_guardrails.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_resource_dispatch_partial_overdue_summary_surfaces_warning.py`：`11 passed`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit core/services/scheduler/resource_dispatch_excel.py core/services/scheduler/resource_dispatch_rows.py web/viewmodels/page_manuals_scheduler_outputs.py tests/regression_resource_dispatch_public_output_contract.py tests/test_scheduler_resource_dispatch_smoke.py tests/regression_table_layout_readability_contract.py`：未发现 Python 3.8 兼容风险。
- CodeStable YAML 校验：design、checklist、acceptance、requirement、VISION、architecture 均通过。
- `git diff --check`：通过。
