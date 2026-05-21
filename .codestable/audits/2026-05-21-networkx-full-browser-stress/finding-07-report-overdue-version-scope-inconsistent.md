---
doc_type: audit-finding
audit: 2026-05-21-networkx-full-browser-stress
finding_id: report-overdue-version-scope-inconsistent
nature: data-consistency
severity: P1
confidence: high
status: open
suggested_action: cs-issue
last_deep_trace: 2026-05-21
---

# Finding 07：报表中心超期数量和 v15 优化分析页口径不一致

## 现象

v15 优化分析页显示本次选中 9 个批次、超期批次数为 0。但报表中心按最新版本 v15 展示时，显示超期批次数为 121。

## 操作步骤

1. 打开 `/scheduler/analysis?version=15`。
2. 查看 v15 摘要。
3. 打开 `/reports/`。
4. 打开 `/reports/overdue`。

## 实际表现

- 分析页：v15，9 批 / 24 工序，超期批次数 0。
- 报表中心：最新版本 v15，超期批次数 121。
- 超期报表里出现大量不属于 v15 这 9 个选中批次的重压批次。

## 期望表现

如果报表选择的是 v15，就应该清楚说明口径：

- 要么只统计 v15 本次排产选中的批次；
- 要么明确写“全系统未完成批次超期，不限于当前版本选中批次”。

现在页面看起来像是在说“v15 这个排产版本有 121 个超期”，和分析页对不上。

## 问题类型

数据口径不一致、页面解释不足。

## 严重程度

明显影响使用。用户会误判排产版本质量。

## 证据

只读 SQL：

```text
v15 analysis overdue = 0
v15 selected_batch_ids = 9
all pending batches = 130
```

截图：

- `/tmp/aps-networkx-full-browser-stress.h88s1vh4/browser-artifacts/screenshots/reports-latest-v15-overdue-mismatch.png`

## 追加根因追踪（2026-05-21）

根因从“口径不清”升级为“查询漏了批次范围”。报表中心虽然拿到了 `v15`，但超期查询从 `Batches` 全表开始查，再把 v15 的排程行左连接上去；不属于 v15 的批次会被当成“v15 没排上且已经过交期”，一起算进超期数。

分析页 v15 的超期数来源：

- [web/routes/domains/scheduler/scheduler_analysis.py](/Users/lurenxing/Documents/GitHub/----/web/routes/domains/scheduler/scheduler_analysis.py:16) 读取 `version=15`。
- [web/routes/domains/scheduler/scheduler_analysis_read.py](/Users/lurenxing/Documents/GitHub/----/web/routes/domains/scheduler/scheduler_analysis_read.py:43) 按版本读取 `ScheduleHistory.get_by_version(15)`。
- [web/viewmodels/scheduler_analysis_trends.py](/Users/lurenxing/Documents/GitHub/----/web/viewmodels/scheduler_analysis_trends.py:151) 从 `ScheduleHistory.result_summary` 解析 `selected_summary` 和 `selected_metrics`。
- [templates/scheduler/analysis_parts/_metric_cards.html](/Users/lurenxing/Documents/GitHub/----/templates/scheduler/analysis_parts/_metric_cards.html:21) 展示 `selected_metrics['overdue_count']`。
- [core/services/scheduler/summary/schedule_summary_assembly.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/summary/schedule_summary_assembly.py:374) 写 `selected_batch_ids = ctx.normalized_batch_ids`。
- [core/services/scheduler/summary/schedule_summary_assembly.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/summary/schedule_summary_assembly.py:393) 写 `overdue_batches.count = len(runtime_state.overdue_items)`。

报表中心超期数来源：

- [web/routes/reports.py](/Users/lurenxing/Documents/GitHub/----/web/routes/reports.py:232) 首页取最新版本，临时库最新是 `15`。
- [web/routes/reports.py](/Users/lurenxing/Documents/GitHub/----/web/routes/reports.py:238) 首页调用 `engine.overdue_batches(latest_ver)`。
- [web/routes/reports.py](/Users/lurenxing/Documents/GitHub/----/web/routes/reports.py:254) 超期明细页解析页面版本。
- [web/routes/reports.py](/Users/lurenxing/Documents/GitHub/----/web/routes/reports.py:259) 明细页调用 `engine.overdue_batches(int(version), plan_role=raw_plan_role)`。
- [core/services/report/report_engine.py](/Users/lurenxing/Documents/GitHub/----/core/services/report/report_engine.py:208) 计算超期总数。
- [data/repositories/schedule_plan_query_repo.py](/Users/lurenxing/Documents/GitHub/----/data/repositories/schedule_plan_query_repo.py:171) 的 SQL 从 `Batches b` 起步，`LEFT JOIN plan_rows s ON s.op_id = bo.id`，只用 `version=15` 过滤排程行，不过滤批次范围。
- [core/services/common/overdue_calculations.py](/Users/lurenxing/Documents/GitHub/----/core/services/common/overdue_calculations.py:78) 对没有 `finish_time` 且交期已过的行判为未排程超期。

关键变量：

- v15 `selected_batch_ids` 共 9 个。
- 分析页 summary 的 `overdue_count=0`。
- `ReportEngine.overdue_batches(15)` 得到 `count=121`，其中 `scheduled_count=0`、`unscheduled_count=121`。
- 这 121 个超期批次里，属于 v15 这 9 个选中批次的数量是 `0`。
- 报表 filters 只有 `version` 和 `plan_role`，没有 `selected_batch_ids` 或批次范围。

产品口径证据：

- 说明书说报表首页超期数“不是全库不分版本实时计算”： [static/docs/scheduler_manual.md](/Users/lurenxing/Documents/GitHub/----/static/docs/scheduler_manual.md:1559)。
- 页面帮助说“首页的超期批次数只按最新排产版本统计”： [web/viewmodels/page_manuals_reports.py](/Users/lurenxing/Documents/GitHub/----/web/viewmodels/page_manuals_reports.py:19)。
- 当前未看到明确产品决策说“超期报表必须展示全系统未完成批次，不限于当前版本”。所以目前判断为查询漏了版本批次范围，不只是页面解释不足。

## 建议修复方向

优先改 [data/repositories/schedule_plan_query_repo.py](/Users/lurenxing/Documents/GitHub/----/data/repositories/schedule_plan_query_repo.py:171) 的 `list_overdue_base_rows()`。如果口径是“当前排产版本/当前方案里的批次”，底表应限制到该版本或候选方案明细涉及的批次，不能从全量 `Batches` 直接左连接。

需要补回归：建两类批次，一类属于目标版本且不超期，另一类不属于目标版本但交期已过；访问 `/reports/` 和 `/reports/overdue?version=目标版本`，断言不属于该版本的批次不会算进超期总数。候选方案 `plan_role=baseline_best` 也要补一条，只按该候选方案明细涉及的批次统计。
