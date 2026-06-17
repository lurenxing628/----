---
doc_type: audit-finding
audit: 2026-06-14-subagent-reference-trace-verification
finding_id: "performance-05"
nature: performance
severity: P1
confidence: high
suggested_action: cs-issue
status: open
---

# Finding 05：延期诊断不吃页面/导出筛选条件

## 速答

超期清单本身已经能按资源和批次筛选，但延期诊断链路只认方案身份，会先生成整版诊断，再在页面或导出层丢弃多余结果。

## 关键证据

- `web/routes/reports_page_support.py:183-190`：超期清单查询会传 `resource_type/resource_id/batch_id`。
- `web/routes/reports_page_support.py:238-242`：`_raw_delay_diagnosis()` 只传 `version/plan_role/scenario_id`，不传筛选条件。
- `core/services/scheduler/schedule_delay_diagnosis_service.py:42-78`：诊断服务签名没有资源或批次筛选，内部对全部超期行逐条 `_diagnose_item()`。
- `core/services/report/report_engine.py:242-248`：导出先拿筛选后的批次号做白名单，但诊断生成仍不下推。
- `core/services/report/delay_diagnosis_presentation.py:39-41`：导出展示层才按 `allowed_batch_ids` 做 Python 事后过滤。
- `data/repositories/schedule_plan_query_repo.py:423`、`:396-407`：底层超期 SQL 实际支持批次和资源过滤，问题不在 repo 能力不足。

## 影响

筛选结果很少时仍可能对整版所有超期批次做诊断，导出和页面都会浪费计算；用户看不到多余诊断，但后台已经算过。

## 修复方向

给诊断入口补 `resource_type/resource_id/batch_id` 或 `allowed_batch_ids`，并把条件传到超期基础行和明细行查询。

## 建议动作

`cs-issue`，因为链路已经有底层能力，问题是中间漏传筛选条件。
