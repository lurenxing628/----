# 2026-04-04 未提交修改三轮验证审查
- 日期: 2026-04-04
- 概述: 审查批次导入、日历校验、批次更新与排程汇总相关修改是否符合设计初衷，避免过度兜底与静默回退。
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# 2026-04-04 未提交修改三轮验证审查

- 日期：2026-04-04
- 范围：批次导入、通用表格校验、批次更新写入规则、排程汇总导出面
- 目标：核实当前修改是否真实修复已确认问题，并评估实现是否保持语义清晰、不过度防御、无新增静默回退

> 本审查按模块逐步记录里程碑，结论以最终汇总为准。

## 评审摘要

- 当前状态: 已完成
- 已审模块: core/services/scheduler/batch_excel_import.py, core/services/scheduler/batch_write_rules.py, core/services/scheduler/batch_service.py, web/routes/scheduler_batches.py, web/routes/scheduler_excel_batches.py, core/services/common/excel_validators.py, core/services/common/strict_parse.py, core/services/scheduler/calendar_admin.py, web/routes/personnel_excel_operator_calendar.py, core/services/scheduler/calendar_service.py, core/services/scheduler/schedule_summary.py, core/services/scheduler/schedule_summary_freeze.py, core/services/scheduler/schedule_summary_assembly.py, tests/regression_due_exclusive_guard_contract.py, tests/regression_schedule_summary_overdue_warning_append_fallback.py, tests/regression_schedule_summary_size_guard_large_lists.py, tests/regression_schedule_summary_v11_contract.py, tests/regression_due_exclusive_consistency.py, audit/2026-03/20260316_schedule_audit_probes.py
- 当前进度: 已记录 3 个里程碑；最新：m3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 1
- 问题严重级别分布: 高 0 / 中 1 / 低 0
- 最新结论: 本轮源码复核结论：当前修改整体方向正确，批次导入、批次更新与排程汇总相关改动大体实现了“显式失败、减少静默回退、语义更清晰”的目标，其中批次更新哨兵值改造、图号切换保护补齐、模板补建告警透出、排程汇总公开接口整洁化都属于比较克制且符合设计初衷的实现。唯一尚未完全收口的问题位于人员专属日历 Excel 校验链：虽然 `NaN/Inf` 漏检已修复，但数值列仍绕过统一严格浮点解析门面，保留了布尔值静默转换这一契约偏差。因此，这组修改可以评价为“总体优雅、基本到位，但未达到完全收敛”；若要满足你提出的“不要静默纠偏、完全符合设计初衷用户意图”，还需要把该处也统一到严格解析门面后再算彻底完成。
- 下一步建议: 优先将人员专属日历 Excel 校验中的两处裸 `float()` 收敛到统一严格浮点解析，并补一条覆盖布尔单元格的回归样例；完成后可视为本轮修改真正闭环。
- 总体结论: 有条件通过

## 评审发现

### 人员日历数值列仍绕过统一严格浮点解析

- ID: operator-calendar-strict-float-gap
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: m2
- 说明:

  `get_operator_calendar_row_validate_and_normalize()` 虽然新增了 `math.isfinite()` 检查来拦截 `NaN/Inf`，但“可用工时”“效率”两列仍直接使用裸 `float()`。项目的统一严格数值策略在 `core/services/common/strict_parse.py` 中明确拒绝布尔值，并由 `CalendarAdmin._normalize_float()` 复用。当前预览层没有复用这一门面，意味着 Excel 中的布尔单元格会被静默规范化为 `1.0/0.0`，而不是按严格数值语义报错。这不是最初报告中的崩溃型问题，但仍然属于契约未完全对齐，也保留了不必要的静默纠偏。
- 建议:

  把两处裸 `float()` 改为 `parse_finite_float(..., allow_none=False)` 并沿用现有中文错误文案，同时补一条覆盖布尔单元格的回归用例，确保 Excel 预览、确认与落库层共享同一数值契约。
- 证据:
  - `core/services/common/excel_validators.py:191-228#get_operator_calendar_row_validate_and_normalize`
  - `core/services/common/strict_parse.py:32-40#_parse_finite_float`
  - `core/services/scheduler/calendar_admin.py:60-62#CalendarAdmin._normalize_float`
  - `core/services/common/excel_validators.py`
  - `core/services/common/strict_parse.py`
  - `core/services/scheduler/calendar_admin.py`
  - `web/routes/personnel_excel_operator_calendar.py`
  - `core/services/scheduler/calendar_service.py`

## 评审里程碑

### m1 · 批次导入与批次更新链复核

- 状态: 已完成
- 记录时间: 2026-04-04T18:35:06.196Z
- 已审模块: core/services/scheduler/batch_excel_import.py, core/services/scheduler/batch_write_rules.py, core/services/scheduler/batch_service.py, web/routes/scheduler_batches.py, web/routes/scheduler_excel_batches.py
- 摘要:

  已核对批次导入、写入规则、服务层更新与批量路由联动修改。结论：数量字段从裸整数转换切换到统一整数规范化后，异常会以业务校验形式暴露；`_MISSING` 哨兵值已贯通 `BatchService.update()` 与批量路由，服务层现在能区分“未提供”和“显式清空”，同时公开更新接口默认禁止在不重建工序时切换图号，语义与批量导入路径保持一致。Excel 批次导入确认页也已补上模板自动补建告警透出，避免兼容/降级提示静默丢失。整体实现保持了显式失败优先，没有引入新的静默回退。
- 结论:

  批次导入与批次更新链上的修复基本符合设计初衷，服务层语义比修改前更清晰。
- 证据:
  - `core/services/scheduler/batch_excel_import.py:79-90#import_batches_from_preview_rows`
  - `core/services/scheduler/batch_write_rules.py:26-30#_validated_quantity`
  - `core/services/scheduler/batch_write_rules.py:122-158#build_update_payload`
  - `core/services/scheduler/batch_service.py:201-242#BatchService.update`
  - `web/routes/scheduler_batches.py:292-308#_bulk_update_one_batch`
  - `web/routes/scheduler_excel_batches.py:354-388#excel_batches_confirm`
  - `core/services/scheduler/batch_excel_import.py`
  - `core/services/scheduler/batch_write_rules.py`
  - `core/services/scheduler/batch_service.py`
  - `web/routes/scheduler_batches.py`
  - `web/routes/scheduler_excel_batches.py`
- 下一步建议:

  继续复核通用表格校验链与排程汇总模块，确认是否还存在契约未对齐或风格退化。

### m2 · 通用表格校验链复核

- 状态: 已完成
- 记录时间: 2026-04-04T18:35:24.604Z
- 已审模块: core/services/common/excel_validators.py, core/services/common/strict_parse.py, core/services/scheduler/calendar_admin.py, web/routes/personnel_excel_operator_calendar.py, core/services/scheduler/calendar_service.py
- 摘要:

  已复核人员专属日历 Excel 预览/确认链与落库层数值约束。当前修改已补上 `NaN`/`Inf` 拦截，修复了最直接的跨层爆炸点；但预览层对“可用工时”“效率”仍使用裸 `float()`，没有复用统一严格浮点解析门面。结果是预览链会把布尔单元格静默转换为 `1.0/0.0`，而底层标准数值策略本意是拒绝布尔值，这与“统一严格数值语义、避免静默纠偏”的设计目标仍有偏差。
- 结论:

  该模块完成了主要修复，但还保留一处中等严重度的契约偏差，尚不能算完全收敛。
- 证据:
  - `core/services/common/excel_validators.py:191-228#get_operator_calendar_row_validate_and_normalize`
  - `core/services/common/strict_parse.py:32-40#_parse_finite_float`
  - `core/services/scheduler/calendar_admin.py:60-62#CalendarAdmin._normalize_float`
  - `web/routes/personnel_excel_operator_calendar.py:303-338#excel_operator_calendar_confirm`
  - `core/services/scheduler/calendar_service.py:183-197#CalendarService.import_operator_calendar_from_preview_rows`
  - `core/services/common/excel_validators.py`
  - `core/services/common/strict_parse.py`
  - `core/services/scheduler/calendar_admin.py`
  - `web/routes/personnel_excel_operator_calendar.py`
  - `core/services/scheduler/calendar_service.py`
- 下一步建议:

  继续复核排程汇总模块，确认公开导出面重命名与参数简化是否仅做表层清理、未改变业务语义。
- 问题:
  - [中] 其他: 人员日历数值列仍绕过统一严格浮点解析

### m3 · 排程汇总导出面复核

- 状态: 已完成
- 记录时间: 2026-04-04T18:35:44.358Z
- 已审模块: core/services/scheduler/schedule_summary.py, core/services/scheduler/schedule_summary_freeze.py, core/services/scheduler/schedule_summary_assembly.py, tests/regression_due_exclusive_guard_contract.py, tests/regression_schedule_summary_overdue_warning_append_fallback.py, tests/regression_schedule_summary_size_guard_large_lists.py, tests/regression_schedule_summary_v11_contract.py, tests/regression_due_exclusive_consistency.py, audit/2026-03/20260316_schedule_audit_probes.py
- 摘要:

  已复核 `schedule_summary.py`、冻结窗口辅助模块及相关回归样例。结论：公开导出名去下划线、参数名澄清以及局部去冗余包装，整体属于接口整洁化与可读性提升，并未观察到业务口径变化。当前实现仍通过 `build_result_summary` 契约样例覆盖超期边界、摘要裁剪与版本兼容等核心行为；`apply_summary_size_guard()` 的裁剪策略、`due_exclusive()` 的边界口径以及冻结窗口告警抽取逻辑均保持原有业务语义。
- 结论:

  排程汇总模块这组修改总体优雅且克制，属于低风险整理，没有发现新的功能性回归。
- 证据:
  - `core/services/scheduler/schedule_summary.py:47-245#__all__`
  - `core/services/scheduler/schedule_summary.py:356-481#build_result_summary`
  - `core/services/scheduler/schedule_summary_freeze.py:61-68#_extract_freeze_warnings`
  - `core/services/scheduler/schedule_summary_assembly.py:349-455#_build_result_summary_obj`
  - `tests/regression_schedule_summary_v11_contract.py:225-279#main`
  - `tests/regression_due_exclusive_consistency.py:44-107#main`
  - `tests/regression_schedule_summary_size_guard_large_lists.py:49-71#main`
  - `audit/2026-03/20260316_schedule_audit_probes.py:84-116#probe_overdue_boundary`
  - `core/services/scheduler/schedule_summary.py`
  - `core/services/scheduler/schedule_summary_freeze.py`
  - `core/services/scheduler/schedule_summary_assembly.py`
  - `tests/regression_due_exclusive_guard_contract.py`
  - `tests/regression_schedule_summary_overdue_warning_append_fallback.py`
  - `tests/regression_schedule_summary_size_guard_large_lists.py`
  - `tests/regression_schedule_summary_v11_contract.py`
  - `tests/regression_due_exclusive_consistency.py`
  - `audit/2026-03/20260316_schedule_audit_probes.py`
- 下一步建议:

  汇总三轮结论，给出是否达到“优雅简洁、无静默回退”的总评，并指出仍需收口的唯一剩余问题。

## 最终结论

本轮源码复核结论：当前修改整体方向正确，批次导入、批次更新与排程汇总相关改动大体实现了“显式失败、减少静默回退、语义更清晰”的目标，其中批次更新哨兵值改造、图号切换保护补齐、模板补建告警透出、排程汇总公开接口整洁化都属于比较克制且符合设计初衷的实现。唯一尚未完全收口的问题位于人员专属日历 Excel 校验链：虽然 `NaN/Inf` 漏检已修复，但数值列仍绕过统一严格浮点解析门面，保留了布尔值静默转换这一契约偏差。因此，这组修改可以评价为“总体优雅、基本到位，但未达到完全收敛”；若要满足你提出的“不要静默纠偏、完全符合设计初衷用户意图”，还需要把该处也统一到严格解析门面后再算彻底完成。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnko1r8h-lvslfd",
  "createdAt": "2026-04-04T00:00:00.000Z",
  "updatedAt": "2026-04-04T18:35:56.008Z",
  "finalizedAt": "2026-04-04T18:35:56.008Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "2026-04-04 未提交修改三轮验证审查",
    "date": "2026-04-04",
    "overview": "审查批次导入、日历校验、批次更新与排程汇总相关修改是否符合设计初衷，避免过度兜底与静默回退。"
  },
  "scope": {
    "markdown": "# 2026-04-04 未提交修改三轮验证审查\n\n- 日期：2026-04-04\n- 范围：批次导入、通用表格校验、批次更新写入规则、排程汇总导出面\n- 目标：核实当前修改是否真实修复已确认问题，并评估实现是否保持语义清晰、不过度防御、无新增静默回退\n\n> 本审查按模块逐步记录里程碑，结论以最终汇总为准。"
  },
  "summary": {
    "latestConclusion": "本轮源码复核结论：当前修改整体方向正确，批次导入、批次更新与排程汇总相关改动大体实现了“显式失败、减少静默回退、语义更清晰”的目标，其中批次更新哨兵值改造、图号切换保护补齐、模板补建告警透出、排程汇总公开接口整洁化都属于比较克制且符合设计初衷的实现。唯一尚未完全收口的问题位于人员专属日历 Excel 校验链：虽然 `NaN/Inf` 漏检已修复，但数值列仍绕过统一严格浮点解析门面，保留了布尔值静默转换这一契约偏差。因此，这组修改可以评价为“总体优雅、基本到位，但未达到完全收敛”；若要满足你提出的“不要静默纠偏、完全符合设计初衷用户意图”，还需要把该处也统一到严格解析门面后再算彻底完成。",
    "recommendedNextAction": "优先将人员专属日历 Excel 校验中的两处裸 `float()` 收敛到统一严格浮点解析，并补一条覆盖布尔单元格的回归样例；完成后可视为本轮修改真正闭环。",
    "reviewedModules": [
      "core/services/scheduler/batch_excel_import.py",
      "core/services/scheduler/batch_write_rules.py",
      "core/services/scheduler/batch_service.py",
      "web/routes/scheduler_batches.py",
      "web/routes/scheduler_excel_batches.py",
      "core/services/common/excel_validators.py",
      "core/services/common/strict_parse.py",
      "core/services/scheduler/calendar_admin.py",
      "web/routes/personnel_excel_operator_calendar.py",
      "core/services/scheduler/calendar_service.py",
      "core/services/scheduler/schedule_summary.py",
      "core/services/scheduler/schedule_summary_freeze.py",
      "core/services/scheduler/schedule_summary_assembly.py",
      "tests/regression_due_exclusive_guard_contract.py",
      "tests/regression_schedule_summary_overdue_warning_append_fallback.py",
      "tests/regression_schedule_summary_size_guard_large_lists.py",
      "tests/regression_schedule_summary_v11_contract.py",
      "tests/regression_due_exclusive_consistency.py",
      "audit/2026-03/20260316_schedule_audit_probes.py"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 1,
    "severity": {
      "high": 0,
      "medium": 1,
      "low": 0
    }
  },
  "milestones": [
    {
      "id": "m1",
      "title": "批次导入与批次更新链复核",
      "status": "completed",
      "recordedAt": "2026-04-04T18:35:06.196Z",
      "summaryMarkdown": "已核对批次导入、写入规则、服务层更新与批量路由联动修改。结论：数量字段从裸整数转换切换到统一整数规范化后，异常会以业务校验形式暴露；`_MISSING` 哨兵值已贯通 `BatchService.update()` 与批量路由，服务层现在能区分“未提供”和“显式清空”，同时公开更新接口默认禁止在不重建工序时切换图号，语义与批量导入路径保持一致。Excel 批次导入确认页也已补上模板自动补建告警透出，避免兼容/降级提示静默丢失。整体实现保持了显式失败优先，没有引入新的静默回退。",
      "conclusionMarkdown": "批次导入与批次更新链上的修复基本符合设计初衷，服务层语义比修改前更清晰。",
      "evidence": [
        {
          "path": "core/services/scheduler/batch_excel_import.py",
          "lineStart": 79,
          "lineEnd": 90,
          "symbol": "import_batches_from_preview_rows"
        },
        {
          "path": "core/services/scheduler/batch_write_rules.py",
          "lineStart": 26,
          "lineEnd": 30,
          "symbol": "_validated_quantity"
        },
        {
          "path": "core/services/scheduler/batch_write_rules.py",
          "lineStart": 122,
          "lineEnd": 158,
          "symbol": "build_update_payload"
        },
        {
          "path": "core/services/scheduler/batch_service.py",
          "lineStart": 201,
          "lineEnd": 242,
          "symbol": "BatchService.update"
        },
        {
          "path": "web/routes/scheduler_batches.py",
          "lineStart": 292,
          "lineEnd": 308,
          "symbol": "_bulk_update_one_batch"
        },
        {
          "path": "web/routes/scheduler_excel_batches.py",
          "lineStart": 354,
          "lineEnd": 388,
          "symbol": "excel_batches_confirm"
        },
        {
          "path": "core/services/scheduler/batch_excel_import.py"
        },
        {
          "path": "core/services/scheduler/batch_write_rules.py"
        },
        {
          "path": "core/services/scheduler/batch_service.py"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        },
        {
          "path": "web/routes/scheduler_excel_batches.py"
        }
      ],
      "reviewedModules": [
        "core/services/scheduler/batch_excel_import.py",
        "core/services/scheduler/batch_write_rules.py",
        "core/services/scheduler/batch_service.py",
        "web/routes/scheduler_batches.py",
        "web/routes/scheduler_excel_batches.py"
      ],
      "recommendedNextAction": "继续复核通用表格校验链与排程汇总模块，确认是否还存在契约未对齐或风格退化。",
      "findingIds": []
    },
    {
      "id": "m2",
      "title": "通用表格校验链复核",
      "status": "completed",
      "recordedAt": "2026-04-04T18:35:24.604Z",
      "summaryMarkdown": "已复核人员专属日历 Excel 预览/确认链与落库层数值约束。当前修改已补上 `NaN`/`Inf` 拦截，修复了最直接的跨层爆炸点；但预览层对“可用工时”“效率”仍使用裸 `float()`，没有复用统一严格浮点解析门面。结果是预览链会把布尔单元格静默转换为 `1.0/0.0`，而底层标准数值策略本意是拒绝布尔值，这与“统一严格数值语义、避免静默纠偏”的设计目标仍有偏差。",
      "conclusionMarkdown": "该模块完成了主要修复，但还保留一处中等严重度的契约偏差，尚不能算完全收敛。",
      "evidence": [
        {
          "path": "core/services/common/excel_validators.py",
          "lineStart": 191,
          "lineEnd": 228,
          "symbol": "get_operator_calendar_row_validate_and_normalize"
        },
        {
          "path": "core/services/common/strict_parse.py",
          "lineStart": 32,
          "lineEnd": 40,
          "symbol": "_parse_finite_float"
        },
        {
          "path": "core/services/scheduler/calendar_admin.py",
          "lineStart": 60,
          "lineEnd": 62,
          "symbol": "CalendarAdmin._normalize_float"
        },
        {
          "path": "web/routes/personnel_excel_operator_calendar.py",
          "lineStart": 303,
          "lineEnd": 338,
          "symbol": "excel_operator_calendar_confirm"
        },
        {
          "path": "core/services/scheduler/calendar_service.py",
          "lineStart": 183,
          "lineEnd": 197,
          "symbol": "CalendarService.import_operator_calendar_from_preview_rows"
        },
        {
          "path": "core/services/common/excel_validators.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
        },
        {
          "path": "core/services/scheduler/calendar_admin.py"
        },
        {
          "path": "web/routes/personnel_excel_operator_calendar.py"
        },
        {
          "path": "core/services/scheduler/calendar_service.py"
        }
      ],
      "reviewedModules": [
        "core/services/common/excel_validators.py",
        "core/services/common/strict_parse.py",
        "core/services/scheduler/calendar_admin.py",
        "web/routes/personnel_excel_operator_calendar.py",
        "core/services/scheduler/calendar_service.py"
      ],
      "recommendedNextAction": "继续复核排程汇总模块，确认公开导出面重命名与参数简化是否仅做表层清理、未改变业务语义。",
      "findingIds": [
        "operator-calendar-strict-float-gap"
      ]
    },
    {
      "id": "m3",
      "title": "排程汇总导出面复核",
      "status": "completed",
      "recordedAt": "2026-04-04T18:35:44.358Z",
      "summaryMarkdown": "已复核 `schedule_summary.py`、冻结窗口辅助模块及相关回归样例。结论：公开导出名去下划线、参数名澄清以及局部去冗余包装，整体属于接口整洁化与可读性提升，并未观察到业务口径变化。当前实现仍通过 `build_result_summary` 契约样例覆盖超期边界、摘要裁剪与版本兼容等核心行为；`apply_summary_size_guard()` 的裁剪策略、`due_exclusive()` 的边界口径以及冻结窗口告警抽取逻辑均保持原有业务语义。",
      "conclusionMarkdown": "排程汇总模块这组修改总体优雅且克制，属于低风险整理，没有发现新的功能性回归。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_summary.py",
          "lineStart": 47,
          "lineEnd": 245,
          "symbol": "__all__"
        },
        {
          "path": "core/services/scheduler/schedule_summary.py",
          "lineStart": 356,
          "lineEnd": 481,
          "symbol": "build_result_summary"
        },
        {
          "path": "core/services/scheduler/schedule_summary_freeze.py",
          "lineStart": 61,
          "lineEnd": 68,
          "symbol": "_extract_freeze_warnings"
        },
        {
          "path": "core/services/scheduler/schedule_summary_assembly.py",
          "lineStart": 349,
          "lineEnd": 455,
          "symbol": "_build_result_summary_obj"
        },
        {
          "path": "tests/regression_schedule_summary_v11_contract.py",
          "lineStart": 225,
          "lineEnd": 279,
          "symbol": "main"
        },
        {
          "path": "tests/regression_due_exclusive_consistency.py",
          "lineStart": 44,
          "lineEnd": 107,
          "symbol": "main"
        },
        {
          "path": "tests/regression_schedule_summary_size_guard_large_lists.py",
          "lineStart": 49,
          "lineEnd": 71,
          "symbol": "main"
        },
        {
          "path": "audit/2026-03/20260316_schedule_audit_probes.py",
          "lineStart": 84,
          "lineEnd": 116,
          "symbol": "probe_overdue_boundary"
        },
        {
          "path": "core/services/scheduler/schedule_summary.py"
        },
        {
          "path": "core/services/scheduler/schedule_summary_freeze.py"
        },
        {
          "path": "core/services/scheduler/schedule_summary_assembly.py"
        },
        {
          "path": "tests/regression_due_exclusive_guard_contract.py"
        },
        {
          "path": "tests/regression_schedule_summary_overdue_warning_append_fallback.py"
        },
        {
          "path": "tests/regression_schedule_summary_size_guard_large_lists.py"
        },
        {
          "path": "tests/regression_schedule_summary_v11_contract.py"
        },
        {
          "path": "tests/regression_due_exclusive_consistency.py"
        },
        {
          "path": "audit/2026-03/20260316_schedule_audit_probes.py"
        }
      ],
      "reviewedModules": [
        "core/services/scheduler/schedule_summary.py",
        "core/services/scheduler/schedule_summary_freeze.py",
        "core/services/scheduler/schedule_summary_assembly.py",
        "tests/regression_due_exclusive_guard_contract.py",
        "tests/regression_schedule_summary_overdue_warning_append_fallback.py",
        "tests/regression_schedule_summary_size_guard_large_lists.py",
        "tests/regression_schedule_summary_v11_contract.py",
        "tests/regression_due_exclusive_consistency.py",
        "audit/2026-03/20260316_schedule_audit_probes.py"
      ],
      "recommendedNextAction": "汇总三轮结论，给出是否达到“优雅简洁、无静默回退”的总评，并指出仍需收口的唯一剩余问题。",
      "findingIds": []
    }
  ],
  "findings": [
    {
      "id": "operator-calendar-strict-float-gap",
      "severity": "medium",
      "category": "other",
      "title": "人员日历数值列仍绕过统一严格浮点解析",
      "descriptionMarkdown": "`get_operator_calendar_row_validate_and_normalize()` 虽然新增了 `math.isfinite()` 检查来拦截 `NaN/Inf`，但“可用工时”“效率”两列仍直接使用裸 `float()`。项目的统一严格数值策略在 `core/services/common/strict_parse.py` 中明确拒绝布尔值，并由 `CalendarAdmin._normalize_float()` 复用。当前预览层没有复用这一门面，意味着 Excel 中的布尔单元格会被静默规范化为 `1.0/0.0`，而不是按严格数值语义报错。这不是最初报告中的崩溃型问题，但仍然属于契约未完全对齐，也保留了不必要的静默纠偏。",
      "recommendationMarkdown": "把两处裸 `float()` 改为 `parse_finite_float(..., allow_none=False)` 并沿用现有中文错误文案，同时补一条覆盖布尔单元格的回归用例，确保 Excel 预览、确认与落库层共享同一数值契约。",
      "evidence": [
        {
          "path": "core/services/common/excel_validators.py",
          "lineStart": 191,
          "lineEnd": 228,
          "symbol": "get_operator_calendar_row_validate_and_normalize"
        },
        {
          "path": "core/services/common/strict_parse.py",
          "lineStart": 32,
          "lineEnd": 40,
          "symbol": "_parse_finite_float"
        },
        {
          "path": "core/services/scheduler/calendar_admin.py",
          "lineStart": 60,
          "lineEnd": 62,
          "symbol": "CalendarAdmin._normalize_float"
        },
        {
          "path": "core/services/common/excel_validators.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
        },
        {
          "path": "core/services/scheduler/calendar_admin.py"
        },
        {
          "path": "web/routes/personnel_excel_operator_calendar.py"
        },
        {
          "path": "core/services/scheduler/calendar_service.py"
        }
      ],
      "relatedMilestoneIds": [
        "m2"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:5286a4a1b342199cf0a5a0c1b6e9f3b6322eee9f0f3bf1147df40b03a03bae8b",
    "generatedAt": "2026-04-04T18:35:56.008Z",
    "locale": "zh-CN"
  }
}
```
