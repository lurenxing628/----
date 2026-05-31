---
doc_type: audit-finding
audit: 2026-05-31-aps-frontend-workbench-design-gap
finding_id: "design-gap-05"
classification: NOW_GLUE_ONLY
nature: maintainability
severity: P1
confidence: high
status: open
suggested_action: cs-feat-design
---

# Finding 05：甘特工作台可复用现有数据补详情区和资源负荷

## 结论

甘特页的只读、禁拖、禁保存基础已经较稳。设计稿要求的右侧稳定详情区、计划/实际小结、资源负荷 Top 摘要，大部分可以复用已有数据和报表服务，不需要改排程算法。但容量来源和停机扣除不能乱承诺。

## 证据

- 当前模板主体只有 `#gantt` 容器，没有固定任务详情区：`templates/scheduler/gantt.html:260`。
- 点击任务现在主要处理高亮和弹窗：`static/js/gantt_render.js:304`、`static/js/gantt_popup.js:55`。
- 甘特任务 meta 有计划字段和 `op_id`：`core/services/scheduler/gantt_tasks.py:176`。
- 计划和现场实际服务能通过 `op_id` 查现场状态和偏差字段：`core/services/report/execution_review.py:94`、`:241`。
- 资源负荷服务能给设备/人员利用率：`core/services/report/report_engine.py:226`、`core/services/report/utilization.py:71`。
- 甘特路由目前没有传资源负荷摘要：`web/routes/domains/scheduler/scheduler_gantt.py:171`。
- 容量计算主要按工作日历和效率：`core/services/report/calculations.py:56`；停机影响单独算：`core/services/report/report_engine.py:315`。

## 当前能直接做

- 补甘特最小高度和空态。
- 补固定详情容器，先复用现有弹窗字段。
- 点击任务时把当前任务渲染到详情区。
- 把“仅超期”提到高频工具条。

## 需要接线的功能

- 通过 `op_id` 接计划/实际小结。
- 复用资源负荷报表，给甘特页补 Top 5 设备/人员。
- 非正式方案下显示“不能复盘现场实际”的中文原因。

## 风险

第一版不要顺手做左侧任务简表、保存视图、模拟沙盒。设计稿把这些放到后续阶段；现在硬塞会挤压甘特主区。
