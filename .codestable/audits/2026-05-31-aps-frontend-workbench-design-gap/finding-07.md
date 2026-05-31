---
doc_type: audit-finding
audit: 2026-05-31-aps-frontend-workbench-design-gap
finding_id: "design-gap-07"
classification: NOW_GLUE_ONLY
nature: maintainability
severity: P1
confidence: high
status: open
suggested_action: cs-feat-design
---

# Finding 07：报表中心和明细页还没形成处理闭环

## 结论

报表中心已经有超期、资源负荷、计划和现场实际、停机影响等页面，但很多报表仍像“看完就结束”。设计稿要求报表成为风险入口，并且明细行能带着同一版本、日期、资源跳回甘特、资源派工或延期解释。

## 证据

- 报表中心 route 主要取最新版本和超期数量：`web/routes/reports.py:149-166`。
- 报表中心模板只展示超期数和最新版本：`templates/reports/index.html:11-22`。
- 四张报表卡片是裸链接：`templates/reports/index.html:36-51`。
- 资源负荷表没有“查看排班 / 定位甘特 / 查看相关超期”操作列：`templates/reports/utilization.html:99-105`、`:143-149`。
- 计划和现场实际表也没有“下一步”操作列：`templates/reports/execution_review.html:76-118`。
- 执行复盘服务返回展示标签，没有把安全的资源定位字段完整交给模板：`core/services/report/execution_review.py:241-289`。
- 停机影响服务只汇总到设备维度，没有受影响任务级明细：`core/services/report/downtime_impact.py:91-98`。
- 当前测试锁住计划和现场实际链接不带 `plan_role/scenario_id`：`tests/regression_plan_vs_actual_review.py:349-357`。

## 当前能直接做

- 报表入口卡补“能回答什么 / 不能证明什么”。
- 报表中心入口保留当前 `version/date_from/date_to`。
- 资源负荷行补回甘特/资源派工的最小链接。
- 计划和现场实际行补查看对应任务的最小链接。

## 必须新增的功能

- 报表中心风险摘要：最忙资源、现场情况待确认、更新时间、当前方案。
- 非正式方案进入计划和现场实际时，按已拍板口径禁用并解释；正式采用方案才能进入复盘。

## 阶段归属

- 第一版：报表中心风险入口、资源负荷行回甘特/资源派工、计划和现场实际行回资源派工/甘特、非正式方案禁用说明。
- 第二阶段：停机影响任务级明细由 `downtime-task-impact-detail` 承接；更细的牵连批次/订单影响面由 `downstream-batch-order-impact` 承接。

## 风险

停机没有记录时，页面不能暗示“没有影响”。应该说“没有维护到停机记录，不能证明没有停机影响”。
