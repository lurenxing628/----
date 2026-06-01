---
doc_type: feature-acceptance
feature: 2026-06-01-gantt-task-detail-panel
requirement: shop-floor-execution-feedback
roadmap: aps-frontend-workbench
roadmap_item: gantt-task-detail-panel
status: accepted
accepted_at: 2026-06-01
summary: 甘特图已新增稳定任务详情区，点击任务后显示公开字段、现场实际小结、超期提示和下一步入口；旧弹窗与关键链前驱也完成内部编号防漏。
tags: [aps, gantt, workbench, execution-facts, acceptance]
---

# 甘特任务详情区验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-01
> 关联方案 doc：`.codestable/features/2026-06-01-gantt-task-detail-panel/gantt-task-detail-panel-design.md`

## 1. 接口契约核对

- [x] `meta.execution_status_label / actual_start_time / actual_end_time / actual_summary_label` 已由 `core/services/scheduler/gantt_service.py` 读取 `ExecutionFactProvider` 后交给 `core/services/scheduler/gantt_tasks.py` 生成。
- [x] `meta.planned_time_label / part_label / operation_label / resource_label / overdue_label / delay_hint` 已在 `gantt_tasks.py` 输出，前端只展示这些公开字段。
- [x] `meta.detail_links` 已由 `web/viewmodels/scheduler_gantt_task_detail.py` 追加，包含资源派工、计划和现场实际、超期清单。
- [x] 现有 `op_id / schedule_id` 留在 JSON 内部字段里做兼容，不进入详情区或弹窗正文。
- [x] 关键链 edge 保留内部 `from/to` 做高亮与连线，同时新增 `from_label/to_label` 给弹窗展示。

## 2. 行为与决策核对

- [x] 点击任务后，`static/js/gantt_render.js` 保留批次聚焦，并刷新 `#ganttTaskDetail`。
- [x] 未选任务、筛选后重绘、空数据时，详情区回到“点击甘特条查看任务详情”。
- [x] 没有现场事件时显示“暂未记录现场实际”，没有把计划时间当成实际开工/完工。
- [x] 非正式方案下，“计划和现场实际”入口由 `WorkbenchLink` 禁用并显示中文原因。
- [x] 甘特图仍传入只读配置，不开放拖拽写库，不改 `static/js/frappe-gantt.min.js`。
- [x] Claude Code 复审指出旧弹窗关键链前驱可能显示 `op_<op_id>`；已下钻到 `gantt_critical_chain.py` 数据生成层修复，并补前端旧 payload 兜底。

## 3. 验收场景核对

- [x] 空状态：`tests/regression_gantt_task_detail_panel_contract.py` 覆盖未选任务提示。
- [x] 公开字段：同一测试覆盖批次、图号或物料、工序、资源、计划时间、状态、超期提示。
- [x] 计划和实际小结：同一测试覆盖无现场记录和写入实际记录后的实际开工/完工。
- [x] 下一步入口：同一测试覆盖资源派工、计划和现场实际、超期清单链接及非正式方案禁用。
- [x] 内部字段防漏：同一测试覆盖 `op_id / schedule_id / source_table / scenario_id / op_<数字>` 不进入详情区和旧弹窗。
- [x] 响应式布局：`tests/regression_ui_browser_geometry_smoke.py::test_ui_pages_do_not_create_body_level_overflow_in_real_browser` 已通过。

## 4. 术语一致性

- [x] 用户可见文案继续使用“现场实际”“计划和现场实际”“暂未记录现场实际”“查看资源排班”“查看超期清单”等中文业务词。
- [x] 页面正文、按钮文案、链接标签不显示 `plan_role`、`scenario_id`、`source_table`、`op_id`、`schedule_id`。
- [x] 内部字段只留在 URL、JSON、隐藏参数、服务端日志或测试追溯里。

## 5. 架构归并

- [x] `.codestable/architecture/ui-gantt.md` 已补充稳定任务详情区数据链、执行事实来源、下一步链接职责、旧弹窗和关键链防漏口径。
- [x] `.codestable/architecture/ARCHITECTURE.md` 已补充甘特任务详情区总入口说明。
- [x] 同步记录第 1~3 项复盘修复：现场事实读取失败时首页显示数据缺口，不误报“现场情况待确认”。

## 6. requirement 回写

- [x] `.codestable/requirements/gantt-readonly-result-view.md` 已补充稳定任务详情区能力、只读边界和内部字段防漏。
- [x] `.codestable/requirements/shop-floor-execution-feedback.md` 已补充甘特详情区查看现场实际小结的用户故事和边界。

## 7. roadmap 回写

- [x] `.codestable/roadmap/aps-frontend-workbench/aps-frontend-workbench-items.yaml` 中 `gantt-task-detail-panel` 已改为 `done`。
- [x] `.codestable/roadmap/aps-frontend-workbench/aps-frontend-workbench-roadmap.md` 子 feature 清单已改为 `done`，变更日志已记录。
- [x] `.codestable/features/2026-06-01-gantt-task-detail-panel/gantt-task-detail-panel-checklist.yaml` 的 checks 已全部改为 `passed`。

## 8. attention.md 候选盘点

- [x] 本 feature 未暴露需要补入 `.codestable/attention.md` 的新通用启动注意事项。
- [x] 可复用经验更适合后续 `cs-learn`：前端防漏不能只堵新详情区，旧弹窗和同源数据出口也要下钻检查。

## 9. 遗留

- 后续优化点：`scenario_id` 仍会作为模拟预览 URL 参数存在；当前按既有架构口径不算正文展示。
- 已知限制：详情区只查看现场实际小结，不在甘特页写现场记录。
- 复审结论：本地 SubAgent 定向复核与盲审复核均无阻塞；Claude Code 复审发现的旧弹窗关键链前驱漏口已修复并回归。
- 验证摘要：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_gantt_task_detail_panel_contract.py`：8 passed
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_gantt_task_detail_panel_contract.py tests/regression_gantt_layout_contract.py tests/regression_gantt_readonly_mode_contract.py tests/regression_gantt_adapter_contract.py tests/regression_gantt_contract_snapshot.py tests/regression_scheduler_workbench_links_contract.py`：35 passed
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_workbench_links_contract.py tests/regression_workbench_nav_entry_contract.py tests/regression_dashboard_workbench_contract.py tests/regression_aps_workbench_first_round_flow_contract.py tests/regression_manual_entry_scope.py tests/regression_frontend_ui_language_polish.py tests/regression_mirror_template_sync.py`：50 passed
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_ui_browser_geometry_smoke.py::test_ui_pages_do_not_create_body_level_overflow_in_real_browser -vv --tb=short -p no:cacheprovider`：1 passed
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree`：16 步都通过，但因工作区未提交，manifest 标记为 `passed_but_unbound`；提交后需再跑 clean gate 绑定证明。
