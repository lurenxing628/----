---
doc_type: feature-design
feature: 2026-05-27-candidate-drilldown-empty-states
status: approved
roadmap: aps-three-gap-directions
roadmap_item: candidate-drilldown-empty-states
created: 2026-05-27
retrospective_backfill: true
---

# 方案钻取和空状态设计

## 背景

代表方案并不总是有可查看明细。没有明细时，如果页面仍给甘特图、周计划、资源派工跳转，用户会点进空页面或误以为系统坏了。本阶段只做钻取入口和空状态，把“能看”和“不能看”的原因讲清楚。

这份设计是回溯补档，用来补齐 CodeStable 事实源。它记录的边界和后续 checklist、acceptance 保持一致。

## 目标

- 方案有明细时，继续给设备甘特图、人员甘特图、周计划、资源派工入口。
- 候选明细没有保存时，不生成假跳转，用中文写“这套对比参考方案没有保存明细，当前无法查看明细。”
- 候选方案失败、跳过、状态缺失或状态未识别时，即使历史记录里有明细标记，也不能生成跳转，必须用中文说明当前状态无法查看明细。
- 周计划、资源负荷、停机影响和导出继续保留当前 `version / plan_role / scenario_id`。
- 超期清单、资源负荷、停机影响在模拟预览下也可以导出；导出必须按模拟明细取数，Excel 文件名和“查询摘要”只写中文方案名，不显示模拟方案内部编号。
- 甘特图、周计划、资源排班这些排产主页面顶部互跳时，只要当前页面带着 `version / plan_role / scenario_id`，也必须继续带过去，不能因为没有 `scenario_id` 就丢掉普通候选方案身份。
- 甘特图、周计划、资源排班这些页面点回“排产优化分析”时，也必须继续带 `version / plan_role`，不能回到默认版本。
- 资源负荷和停机影响页面顶部报表导航互跳时，也继续保留当前 `version / plan_role / scenario_id / start_date / end_date`，不能点一下就回到正式采用方案。
- 报表、周计划、甘特图、资源排班的底层方案解析必须拒绝未完成候选方案；即使对比方案读取的是正式 `Schedule` 明细，也要先确认对应候选记录已完成，不能只靠分析页隐藏按钮，因为用户可能手工访问 URL。
- 分析页展示候选状态时，历史摘要和数据库方案选项都必须明确是已完成，任一边不是已完成或缺状态，都不能生成跳转。
- 模拟预览没有名称时，统一显示“模拟预览（未命名）”。
- 用户可见页面和导出不显示内部字段。

## 不做

- 不新增候选明细大屏。
- 不开放派工确认或现场反馈。
- 不改算法、不改数据库、不改迁移。

## 实现范围

- `web/viewmodels/scheduler_analysis_candidates.py`：为方案行增加 `detail_saved`、`can_open_detail` 和中文不可查看原因。
- `web/routes/domains/scheduler/scheduler_analysis_links.py`：只在可打开时生成跳转。
- `core/services/scheduler/schedule_plan_query_service.py`：统一方案解析时要求候选明细来自已完成候选，避免手工 URL 绕过页面按钮。
- `templates/components/ui_macros.html`：排产主导航和报表导航都按当前请求保留方案身份和日期上下文。
- `web/routes/report_plan_preview.py`、`web/routes/reports.py`、`core/services/report/report_engine.py`、`core/services/report/exporters/xlsx.py`：统一模拟预览公开名称、报表导出取数和导出脱敏。
- `tests/regression_scheduler_analysis_candidate_links_and_roles.py`、`tests/regression_scheduler_candidate_reports_contract.py`、`tests/regression_scenario_preview_secondary_outputs.py`、`tests/regression_report_delay_diagnosis_plain_language.py`、`tests/regression_report_export_size_mode_selection.py`、`tests/regression_reports_layout_contract.py`：覆盖跳转、空状态、导出和内部字段不外露。

## 验收口径

- 没有明细的对比方案不显示假链接。
- 没有完成的代表方案不显示假链接。
- 所有跳转都保留同一套计划身份。
- 报表页内互跳也保留同一套计划身份和日期范围。
- 模拟预览导出按模拟方案明细生成，Excel 查询摘要只显示中文方案名和提示，不显示内部编号。
- 用户可见内容不泄露内部字段。
- fallback 或缺明细时只允许查看，不开放派工或反馈。
