# 当前工作区未提交修改三轮深度审查
- 日期: 2026-04-04
- 概述: 按模块分轮审查当前工作区疑似未提交改动，重点关注目的达成、简洁性、严谨性、静默回退与潜在BUG。
- 状态: 已完成
- 总体结论: 需要后续跟进

## 评审范围

# 当前工作区未提交修改三轮深度审查

- 日期：2026-04-04
- 范围：当前工作区内疑似未提交修改，优先围绕调度汇总拆分、批次服务拆分、校验链路与对应测试覆盖进行三轮增量审查。
- 方法：先识别改动面，再按模块逐步检查实现、边界、回退路径、测试约束与跨层一致性；每完成一个有意义的审查单元即记录里程碑。
- 当前状态：进行中

## 评审摘要

- 当前状态: 已完成
- 已审模块: core/services/scheduler/schedule_summary.py, core/services/scheduler/schedule_summary_assembly.py, core/services/scheduler/schedule_summary_degradation.py, core/services/scheduler/schedule_summary_freeze.py, core/services/scheduler/batch_service.py, core/services/scheduler/batch_excel_import.py, core/services/scheduler/batch_template_ops.py, core/services/scheduler/batch_write_rules.py, web/routes/scheduler_excel_batches.py, core/services/common/excel_validators.py, web/routes/personnel_excel_operator_calendar.py, core/services/scheduler/calendar_service.py, core/services/scheduler/calendar_admin.py, web/routes/scheduler_batches.py, core/services/common/strict_parse.py
- 当前进度: 已记录 3 个里程碑；最新：m3_excel_validator_consistency
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 3
- 问题严重级别分布: 高 1 / 中 2 / 低 0
- 最新结论: 三轮审查表明，本次未提交修改在拆分方向、公开入口稳定性和大部分回归覆盖上总体是正确的：`schedule_summary` 拆分基本达成目标，`batch_service` 拆分也明显改善了职责边界。但当前实现仍未完全达到“优雅、简洁、无静默回退、跨层规则同源”的标准，至少还存在 1 个高风险 BUG 与 2 个中风险问题：日历 Excel 的非有限数字会在预览/确认阶段漏检、批次 Excel 成功导入路径会静默吞掉模板补建 warning、公开批次更新接口仍可绕过图号切换保护。因此本轮结论不是通过，而是需要先修复上述问题并补齐回归后再复核。
- 下一步建议: 优先修复 `operator-calendar-nonfinite-preview-gap`，随后修复 `batch-excel-warning-drop` 与 `batch-update-part-switch-guard-gap`，并分别补充覆盖预览/确认/落库一致性、warning 外显、公开更新接口约束的回归用例。
- 总体结论: 需要后续跟进

## 评审发现

### Excel 模板补建 warning 丢失

- ID: batch-excel-warning-drop
- 严重级别: 中
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: m2_batch_service_split
- 说明:

  `ensure_template_ops_in_tx()` 会把模板自动解析产生的 warning 追加到 `svc._user_visible_warnings`，说明实现本意是把这些退化/兼容信息暴露给用户；但批次 Excel 确认导入路径只读取导入统计并直接 `flash_import_result(...)`，没有像手工建批与重建工序路径那样调用 `consume_user_visible_warnings()`。结果是 `auto_generate_ops=True` 时的模板补建 warning 会在成功导入后被静默吞掉，用户看不到“自动解析产生了兼容/降级”的提示，这与本次审查的‘无静默回退’目标相冲突。
- 建议:

  让批次 Excel 导入成功路径与手工建批路径统一消费并展示 `consume_user_visible_warnings()`，至少在自动补建模板时把兼容/降级 warning 透传到页面提示中。
- 证据:
  - `core/services/scheduler/batch_template_ops.py:93-118#ensure_template_ops_in_tx`
  - `web/routes/scheduler_excel_batches.py:354-386#excel_batches_confirm`
  - `web/routes/scheduler_batches.py:198-213#create_batch`
  - `web/routes/scheduler_batches.py:386-400#generate_ops`
  - `core/services/scheduler/batch_service.py`
  - `core/services/scheduler/batch_excel_import.py`
  - `core/services/scheduler/batch_template_ops.py`
  - `core/services/scheduler/batch_write_rules.py`
  - `web/routes/scheduler_excel_batches.py`
  - `web/routes/scheduler_batches.py`
  - `tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py`
  - `tests/regression_batch_excel_import_reject_part_change_without_rebuild.py`
  - `tests/regression_batch_service_legacy_template_resolver_rejects_strict_mode.py`
  - `tests/regression_batch_service_strict_mode_template_autoparse.py`
  - `tests/regression_batch_template_autobuild_same_tx.py`

### 图号切换保护未统一落到公开更新接口

- ID: batch-update-part-switch-guard-gap
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: m2_batch_service_split
- 说明:

  `batch_write_rules` 已抽出 `_ensure_part_switch_allowed()`，并且 Excel 导入更新路径会显式传入 `auto_generate_ops`，从而在‘改图号但不重建工序’时拒绝写入；但 `BatchService.update()` 构造 `build_update_payload()` 参数时没有传入 `auto_generate_ops`，默认命中 `_MISSING` 分支，保护逻辑直接失效。这样一来，同一条业务规则只在 Excel 路径生效，在公开服务更新接口上却失效，调用者可以把批次头图号改掉而保留旧批次工序，形成头/体不一致。
- 建议:

  把“图号切换是否允许”收口为服务层统一约束：要么让 `BatchService.update()` 也显式要求/接收重建上下文，要么彻底禁止公开更新接口改图号，避免只有 Excel 路径守规矩。
- 证据:
  - `core/services/scheduler/batch_write_rules.py:61-66#_ensure_part_switch_allowed`
  - `core/services/scheduler/batch_write_rules.py:121-157#build_update_payload`
  - `core/services/scheduler/batch_service.py:214-233#update`
  - `core/services/scheduler/batch_excel_import.py:47-62#import_batches_from_preview_rows`
  - `tests/regression_batch_excel_import_reject_part_change_without_rebuild.py:21-79#test_batch_excel_import_rejects_part_change_without_rebuild`
  - `core/services/scheduler/batch_service.py`
  - `core/services/scheduler/batch_excel_import.py`
  - `core/services/scheduler/batch_template_ops.py`
  - `core/services/scheduler/batch_write_rules.py`
  - `web/routes/scheduler_excel_batches.py`
  - `web/routes/scheduler_batches.py`
  - `tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py`
  - `tests/regression_batch_excel_import_reject_part_change_without_rebuild.py`
  - `tests/regression_batch_service_legacy_template_resolver_rejects_strict_mode.py`
  - `tests/regression_batch_service_strict_mode_template_autoparse.py`
  - `tests/regression_batch_template_autobuild_same_tx.py`

### 日历 Excel 非有限数字校验漂移

- ID: operator-calendar-nonfinite-preview-gap
- 严重级别: 高
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: m3_excel_validator_consistency
- 说明:

  `get_operator_calendar_row_validate_and_normalize()` 对“可用工时/效率”直接使用 `float()`，只检查 `<0` 或 `<=0`，因此 `NaN`、`Inf`、`-Inf` 这类值不会在预览/确认阶段被拦下；而确认后的真正写入路径会进入 `CalendarService.import_operator_calendar_from_preview_rows()`，最终调用 `CalendarAdmin` 的严格有限数解析，那里会明确拒绝非有限值。于是同一份数据会出现“预览通过、确认重放也通过、真正落库时才失败”的跨层契约漂移，既不优雅也不严谨。
- 建议:

  把 `excel_validators` 中该路径的数值解析统一改成 `parse_finite_float()`（或直接复用 `CalendarAdmin` 的同源标准化逻辑），确保预览、确认、落库三段使用完全一致的有限数约束。
- 证据:
  - `core/services/common/excel_validators.py:190-222#get_operator_calendar_row_validate_and_normalize`
  - `web/routes/personnel_excel_operator_calendar.py:303-338#excel_operator_calendar_confirm`
  - `core/services/scheduler/calendar_service.py:183-197#import_operator_calendar_from_preview_rows`
  - `core/services/scheduler/calendar_admin.py:210-224#upsert_operator_calendar_no_tx`
  - `core/services/common/strict_parse.py:32-40#_parse_finite_float`
  - `core/services/common/excel_validators.py`
  - `web/routes/personnel_excel_operator_calendar.py`
  - `core/services/scheduler/calendar_service.py`
  - `core/services/scheduler/calendar_admin.py`
  - `core/services/common/strict_parse.py`
  - `tests/regression_excel_operator_calendar_cross_midnight.py`
  - `tests/regression_calendar_no_tx_hardening.py`
  - `tests/test_excel_import_hardening.py`

## 评审里程碑

### m1_schedule_summary_split · 第一轮：调度摘要拆分模块审查

- 状态: 已完成
- 记录时间: 2026-04-04T18:01:01.885Z
- 已审模块: core/services/scheduler/schedule_summary.py, core/services/scheduler/schedule_summary_assembly.py, core/services/scheduler/schedule_summary_degradation.py, core/services/scheduler/schedule_summary_freeze.py
- 摘要:

  已完成对 `schedule_summary` 拆分面的首轮深审。结论：拆分边界基本清晰，入口文件已压到 500 行门禁以内，`freeze / degradation / assembly` 三个子模块的职责分界较自然；摘要结构、冻结窗口契约、无效交期与未完工批次计数、尺寸保护等关键行为均有专门回归覆盖。当前轮次未发现新的阻断级问题。
- 结论:

  调度摘要拆分整体达到“目的明确、结构更清晰、门禁对齐”的目标，当前主要问题不在该模块。
- 证据:
  - `core/services/scheduler/schedule_summary.py:37-49#__all__`
  - `core/services/scheduler/schedule_summary.py:345-470#build_result_summary`
  - `core/services/scheduler/schedule_summary_assembly.py:349-455#_build_result_summary_obj`
  - `core/services/scheduler/schedule_summary_degradation.py:161-228#_summary_degradation_state`
  - `core/services/scheduler/schedule_summary_freeze.py:71-92#_freeze_meta_dict`
  - `tests/test_architecture_fitness.py:43-56#_known_oversize_files`
  - `tests/regression_schedule_summary_v11_contract.py:225-281#main`
  - `tests/regression_schedule_summary_freeze_state_contract.py:61-103#test_schedule_summary_freeze_state_controls_hard_constraints`
  - `tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py:64-109#main`
  - `core/services/scheduler/schedule_summary.py`
  - `core/services/scheduler/schedule_summary_assembly.py`
  - `core/services/scheduler/schedule_summary_degradation.py`
  - `core/services/scheduler/schedule_summary_freeze.py`
  - `tests/test_architecture_fitness.py`
  - `tests/regression_schedule_summary_v11_contract.py`
  - `tests/regression_schedule_summary_freeze_state_contract.py`
  - `tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py`
  - `tests/regression_schedule_summary_size_guard_large_lists.py`
- 下一步建议:

  继续审查批次服务拆分与 Excel 导入/模板补建链路，重点看是否出现隐藏回退或事务边界松动。

### m2_batch_service_split · 第二轮：批次服务拆分与模板补建链路审查

- 状态: 已完成
- 记录时间: 2026-04-04T18:01:33.425Z
- 已审模块: core/services/scheduler/batch_service.py, core/services/scheduler/batch_excel_import.py, core/services/scheduler/batch_template_ops.py, core/services/scheduler/batch_write_rules.py, web/routes/scheduler_excel_batches.py
- 摘要:

  已完成对 `batch_service / batch_excel_import / batch_template_ops / batch_write_rules` 的第二轮深审。结论：事务边界与职责拆分总体比旧实现清晰，`strict_mode` 与同事务补建模板的主要回归也补得较到位；但本轮仍发现两个实质问题：其一，批次 Excel 自动补建模板时产生的用户可见 warning 在确认导入路径中没有被消费和外显，形成静默退化；其二，`batch_write_rules` 已经抽出了“图号切换必须配合重建工序”的保护，但 `BatchService.update()` 并未传入该约束上下文，导致公开服务方法与 Excel 导入路径的约束不一致。
- 结论:

  批次服务拆分方向正确，但仍未完全达成“无静默回退、规则单点收口”的目标，当前不能视为完全收口。
- 证据:
  - `core/services/scheduler/batch_template_ops.py:93-118#ensure_template_ops_in_tx`
  - `core/services/scheduler/batch_excel_import.py:79-91#import_batches_from_preview_rows`
  - `web/routes/scheduler_excel_batches.py:354-386#excel_batches_confirm`
  - `web/routes/scheduler_batches.py:198-213#create_batch`
  - `web/routes/scheduler_batches.py:386-400#generate_ops`
  - `core/services/scheduler/batch_write_rules.py:61-66#_ensure_part_switch_allowed`
  - `core/services/scheduler/batch_write_rules.py:121-157#build_update_payload`
  - `core/services/scheduler/batch_service.py:214-233#update`
  - `core/services/scheduler/batch_excel_import.py:47-62#import_batches_from_preview_rows`
  - `tests/regression_batch_excel_import_reject_part_change_without_rebuild.py:21-79#test_batch_excel_import_rejects_part_change_without_rebuild`
  - `tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py:64-86#main`
  - `tests/regression_batch_template_autobuild_same_tx.py:58-89#main`
  - `core/services/scheduler/batch_service.py`
  - `core/services/scheduler/batch_excel_import.py`
  - `core/services/scheduler/batch_template_ops.py`
  - `core/services/scheduler/batch_write_rules.py`
  - `web/routes/scheduler_excel_batches.py`
  - `web/routes/scheduler_batches.py`
  - `tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py`
  - `tests/regression_batch_excel_import_reject_part_change_without_rebuild.py`
  - `tests/regression_batch_service_legacy_template_resolver_rejects_strict_mode.py`
  - `tests/regression_batch_service_strict_mode_template_autoparse.py`
  - `tests/regression_batch_template_autobuild_same_tx.py`
- 下一步建议:

  继续审查 Excel 校验层与真正落库层的一致性，重点检查是否还有预览通过但确认/落库阶段再失败的隐蔽漂移。
- 问题:
  - [中] JavaScript: Excel 模板补建 warning 丢失
  - [中] 可维护性: 图号切换保护未统一落到公开更新接口

### m3_excel_validator_consistency · 第三轮：Excel 校验层与落库层一致性审查

- 状态: 已完成
- 记录时间: 2026-04-04T18:02:09.327Z
- 已审模块: core/services/common/excel_validators.py, web/routes/personnel_excel_operator_calendar.py, core/services/scheduler/calendar_service.py, core/services/scheduler/calendar_admin.py
- 摘要:

  已完成对 `excel_validators` 与日历导入确认链路的一致性复核。结论：枚举标准化方向基本正确，但人员专属日历 Excel 校验仍存在一处高风险漂移：预览/确认阶段对“可用工时/效率”使用宽松 `float()` 解析，只校验正负，不校验有限性；而真正落库时 `CalendarAdmin` 使用严格有限数解析。结果是 `NaN/Inf` 一类值可能在预览与确认重放阶段都被当成合法数据，最终在落库阶段才失败，形成典型的预览通过、确认再炸的跨层契约漂移。
- 结论:

  当前 Excel 校验层还没有完全做到与服务层同源规则，至少日历导入链路仍存在高风险校验漂移。
- 证据:
  - `core/services/common/excel_validators.py:190-222#get_operator_calendar_row_validate_and_normalize`
  - `web/routes/personnel_excel_operator_calendar.py:303-338#excel_operator_calendar_confirm`
  - `core/services/scheduler/calendar_service.py:183-197#import_operator_calendar_from_preview_rows`
  - `core/services/scheduler/calendar_admin.py:210-224#upsert_operator_calendar_no_tx`
  - `core/services/common/strict_parse.py:32-40#_parse_finite_float`
  - `tests/regression_calendar_no_tx_hardening.py:196-214#main`
  - `tests/regression_excel_operator_calendar_cross_midnight.py:61-108#main`
  - `tests/test_excel_import_hardening.py:88-97#test_batch_quantity_float_is_rejected_without_truncation`
  - `core/services/common/excel_validators.py`
  - `web/routes/personnel_excel_operator_calendar.py`
  - `core/services/scheduler/calendar_service.py`
  - `core/services/scheduler/calendar_admin.py`
  - `core/services/common/strict_parse.py`
  - `tests/regression_excel_operator_calendar_cross_midnight.py`
  - `tests/regression_calendar_no_tx_hardening.py`
  - `tests/test_excel_import_hardening.py`
- 下一步建议:

  综合三轮结论，给出最终审查判断，并优先要求修复高风险校验漂移与静默 warning 问题。
- 问题:
  - [高] 其他: 日历 Excel 非有限数字校验漂移

## 最终结论

三轮审查表明，本次未提交修改在拆分方向、公开入口稳定性和大部分回归覆盖上总体是正确的：`schedule_summary` 拆分基本达成目标，`batch_service` 拆分也明显改善了职责边界。但当前实现仍未完全达到“优雅、简洁、无静默回退、跨层规则同源”的标准，至少还存在 1 个高风险 BUG 与 2 个中风险问题：日历 Excel 的非有限数字会在预览/确认阶段漏检、批次 Excel 成功导入路径会静默吞掉模板补建 warning、公开批次更新接口仍可绕过图号切换保护。因此本轮结论不是通过，而是需要先修复上述问题并补齐回归后再复核。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnkmodzm-srcw9h",
  "createdAt": "2026-04-04T00:00:00.000Z",
  "updatedAt": "2026-04-04T18:04:16.263Z",
  "finalizedAt": "2026-04-04T18:04:16.263Z",
  "status": "completed",
  "overallDecision": "needs_follow_up",
  "header": {
    "title": "当前工作区未提交修改三轮深度审查",
    "date": "2026-04-04",
    "overview": "按模块分轮审查当前工作区疑似未提交改动，重点关注目的达成、简洁性、严谨性、静默回退与潜在BUG。"
  },
  "scope": {
    "markdown": "# 当前工作区未提交修改三轮深度审查\n\n- 日期：2026-04-04\n- 范围：当前工作区内疑似未提交修改，优先围绕调度汇总拆分、批次服务拆分、校验链路与对应测试覆盖进行三轮增量审查。\n- 方法：先识别改动面，再按模块逐步检查实现、边界、回退路径、测试约束与跨层一致性；每完成一个有意义的审查单元即记录里程碑。\n- 当前状态：进行中"
  },
  "summary": {
    "latestConclusion": "三轮审查表明，本次未提交修改在拆分方向、公开入口稳定性和大部分回归覆盖上总体是正确的：`schedule_summary` 拆分基本达成目标，`batch_service` 拆分也明显改善了职责边界。但当前实现仍未完全达到“优雅、简洁、无静默回退、跨层规则同源”的标准，至少还存在 1 个高风险 BUG 与 2 个中风险问题：日历 Excel 的非有限数字会在预览/确认阶段漏检、批次 Excel 成功导入路径会静默吞掉模板补建 warning、公开批次更新接口仍可绕过图号切换保护。因此本轮结论不是通过，而是需要先修复上述问题并补齐回归后再复核。",
    "recommendedNextAction": "优先修复 `operator-calendar-nonfinite-preview-gap`，随后修复 `batch-excel-warning-drop` 与 `batch-update-part-switch-guard-gap`，并分别补充覆盖预览/确认/落库一致性、warning 外显、公开更新接口约束的回归用例。",
    "reviewedModules": [
      "core/services/scheduler/schedule_summary.py",
      "core/services/scheduler/schedule_summary_assembly.py",
      "core/services/scheduler/schedule_summary_degradation.py",
      "core/services/scheduler/schedule_summary_freeze.py",
      "core/services/scheduler/batch_service.py",
      "core/services/scheduler/batch_excel_import.py",
      "core/services/scheduler/batch_template_ops.py",
      "core/services/scheduler/batch_write_rules.py",
      "web/routes/scheduler_excel_batches.py",
      "core/services/common/excel_validators.py",
      "web/routes/personnel_excel_operator_calendar.py",
      "core/services/scheduler/calendar_service.py",
      "core/services/scheduler/calendar_admin.py",
      "web/routes/scheduler_batches.py",
      "core/services/common/strict_parse.py"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 3,
    "severity": {
      "high": 1,
      "medium": 2,
      "low": 0
    }
  },
  "milestones": [
    {
      "id": "m1_schedule_summary_split",
      "title": "第一轮：调度摘要拆分模块审查",
      "status": "completed",
      "recordedAt": "2026-04-04T18:01:01.885Z",
      "summaryMarkdown": "已完成对 `schedule_summary` 拆分面的首轮深审。结论：拆分边界基本清晰，入口文件已压到 500 行门禁以内，`freeze / degradation / assembly` 三个子模块的职责分界较自然；摘要结构、冻结窗口契约、无效交期与未完工批次计数、尺寸保护等关键行为均有专门回归覆盖。当前轮次未发现新的阻断级问题。",
      "conclusionMarkdown": "调度摘要拆分整体达到“目的明确、结构更清晰、门禁对齐”的目标，当前主要问题不在该模块。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_summary.py",
          "lineStart": 37,
          "lineEnd": 49,
          "symbol": "__all__"
        },
        {
          "path": "core/services/scheduler/schedule_summary.py",
          "lineStart": 345,
          "lineEnd": 470,
          "symbol": "build_result_summary"
        },
        {
          "path": "core/services/scheduler/schedule_summary_assembly.py",
          "lineStart": 349,
          "lineEnd": 455,
          "symbol": "_build_result_summary_obj"
        },
        {
          "path": "core/services/scheduler/schedule_summary_degradation.py",
          "lineStart": 161,
          "lineEnd": 228,
          "symbol": "_summary_degradation_state"
        },
        {
          "path": "core/services/scheduler/schedule_summary_freeze.py",
          "lineStart": 71,
          "lineEnd": 92,
          "symbol": "_freeze_meta_dict"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 43,
          "lineEnd": 56,
          "symbol": "_known_oversize_files"
        },
        {
          "path": "tests/regression_schedule_summary_v11_contract.py",
          "lineStart": 225,
          "lineEnd": 281,
          "symbol": "main"
        },
        {
          "path": "tests/regression_schedule_summary_freeze_state_contract.py",
          "lineStart": 61,
          "lineEnd": 103,
          "symbol": "test_schedule_summary_freeze_state_controls_hard_constraints"
        },
        {
          "path": "tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py",
          "lineStart": 64,
          "lineEnd": 109,
          "symbol": "main"
        },
        {
          "path": "core/services/scheduler/schedule_summary.py"
        },
        {
          "path": "core/services/scheduler/schedule_summary_assembly.py"
        },
        {
          "path": "core/services/scheduler/schedule_summary_degradation.py"
        },
        {
          "path": "core/services/scheduler/schedule_summary_freeze.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "tests/regression_schedule_summary_v11_contract.py"
        },
        {
          "path": "tests/regression_schedule_summary_freeze_state_contract.py"
        },
        {
          "path": "tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py"
        },
        {
          "path": "tests/regression_schedule_summary_size_guard_large_lists.py"
        }
      ],
      "reviewedModules": [
        "core/services/scheduler/schedule_summary.py",
        "core/services/scheduler/schedule_summary_assembly.py",
        "core/services/scheduler/schedule_summary_degradation.py",
        "core/services/scheduler/schedule_summary_freeze.py"
      ],
      "recommendedNextAction": "继续审查批次服务拆分与 Excel 导入/模板补建链路，重点看是否出现隐藏回退或事务边界松动。",
      "findingIds": []
    },
    {
      "id": "m2_batch_service_split",
      "title": "第二轮：批次服务拆分与模板补建链路审查",
      "status": "completed",
      "recordedAt": "2026-04-04T18:01:33.425Z",
      "summaryMarkdown": "已完成对 `batch_service / batch_excel_import / batch_template_ops / batch_write_rules` 的第二轮深审。结论：事务边界与职责拆分总体比旧实现清晰，`strict_mode` 与同事务补建模板的主要回归也补得较到位；但本轮仍发现两个实质问题：其一，批次 Excel 自动补建模板时产生的用户可见 warning 在确认导入路径中没有被消费和外显，形成静默退化；其二，`batch_write_rules` 已经抽出了“图号切换必须配合重建工序”的保护，但 `BatchService.update()` 并未传入该约束上下文，导致公开服务方法与 Excel 导入路径的约束不一致。",
      "conclusionMarkdown": "批次服务拆分方向正确，但仍未完全达成“无静默回退、规则单点收口”的目标，当前不能视为完全收口。",
      "evidence": [
        {
          "path": "core/services/scheduler/batch_template_ops.py",
          "lineStart": 93,
          "lineEnd": 118,
          "symbol": "ensure_template_ops_in_tx"
        },
        {
          "path": "core/services/scheduler/batch_excel_import.py",
          "lineStart": 79,
          "lineEnd": 91,
          "symbol": "import_batches_from_preview_rows"
        },
        {
          "path": "web/routes/scheduler_excel_batches.py",
          "lineStart": 354,
          "lineEnd": 386,
          "symbol": "excel_batches_confirm"
        },
        {
          "path": "web/routes/scheduler_batches.py",
          "lineStart": 198,
          "lineEnd": 213,
          "symbol": "create_batch"
        },
        {
          "path": "web/routes/scheduler_batches.py",
          "lineStart": 386,
          "lineEnd": 400,
          "symbol": "generate_ops"
        },
        {
          "path": "core/services/scheduler/batch_write_rules.py",
          "lineStart": 61,
          "lineEnd": 66,
          "symbol": "_ensure_part_switch_allowed"
        },
        {
          "path": "core/services/scheduler/batch_write_rules.py",
          "lineStart": 121,
          "lineEnd": 157,
          "symbol": "build_update_payload"
        },
        {
          "path": "core/services/scheduler/batch_service.py",
          "lineStart": 214,
          "lineEnd": 233,
          "symbol": "update"
        },
        {
          "path": "core/services/scheduler/batch_excel_import.py",
          "lineStart": 47,
          "lineEnd": 62,
          "symbol": "import_batches_from_preview_rows"
        },
        {
          "path": "tests/regression_batch_excel_import_reject_part_change_without_rebuild.py",
          "lineStart": 21,
          "lineEnd": 79,
          "symbol": "test_batch_excel_import_rejects_part_change_without_rebuild"
        },
        {
          "path": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py",
          "lineStart": 64,
          "lineEnd": 86,
          "symbol": "main"
        },
        {
          "path": "tests/regression_batch_template_autobuild_same_tx.py",
          "lineStart": 58,
          "lineEnd": 89,
          "symbol": "main"
        },
        {
          "path": "core/services/scheduler/batch_service.py"
        },
        {
          "path": "core/services/scheduler/batch_excel_import.py"
        },
        {
          "path": "core/services/scheduler/batch_template_ops.py"
        },
        {
          "path": "core/services/scheduler/batch_write_rules.py"
        },
        {
          "path": "web/routes/scheduler_excel_batches.py"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        },
        {
          "path": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py"
        },
        {
          "path": "tests/regression_batch_excel_import_reject_part_change_without_rebuild.py"
        },
        {
          "path": "tests/regression_batch_service_legacy_template_resolver_rejects_strict_mode.py"
        },
        {
          "path": "tests/regression_batch_service_strict_mode_template_autoparse.py"
        },
        {
          "path": "tests/regression_batch_template_autobuild_same_tx.py"
        }
      ],
      "reviewedModules": [
        "core/services/scheduler/batch_service.py",
        "core/services/scheduler/batch_excel_import.py",
        "core/services/scheduler/batch_template_ops.py",
        "core/services/scheduler/batch_write_rules.py",
        "web/routes/scheduler_excel_batches.py"
      ],
      "recommendedNextAction": "继续审查 Excel 校验层与真正落库层的一致性，重点检查是否还有预览通过但确认/落库阶段再失败的隐蔽漂移。",
      "findingIds": [
        "batch-excel-warning-drop",
        "batch-update-part-switch-guard-gap"
      ]
    },
    {
      "id": "m3_excel_validator_consistency",
      "title": "第三轮：Excel 校验层与落库层一致性审查",
      "status": "completed",
      "recordedAt": "2026-04-04T18:02:09.327Z",
      "summaryMarkdown": "已完成对 `excel_validators` 与日历导入确认链路的一致性复核。结论：枚举标准化方向基本正确，但人员专属日历 Excel 校验仍存在一处高风险漂移：预览/确认阶段对“可用工时/效率”使用宽松 `float()` 解析，只校验正负，不校验有限性；而真正落库时 `CalendarAdmin` 使用严格有限数解析。结果是 `NaN/Inf` 一类值可能在预览与确认重放阶段都被当成合法数据，最终在落库阶段才失败，形成典型的预览通过、确认再炸的跨层契约漂移。",
      "conclusionMarkdown": "当前 Excel 校验层还没有完全做到与服务层同源规则，至少日历导入链路仍存在高风险校验漂移。",
      "evidence": [
        {
          "path": "core/services/common/excel_validators.py",
          "lineStart": 190,
          "lineEnd": 222,
          "symbol": "get_operator_calendar_row_validate_and_normalize"
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
          "symbol": "import_operator_calendar_from_preview_rows"
        },
        {
          "path": "core/services/scheduler/calendar_admin.py",
          "lineStart": 210,
          "lineEnd": 224,
          "symbol": "upsert_operator_calendar_no_tx"
        },
        {
          "path": "core/services/common/strict_parse.py",
          "lineStart": 32,
          "lineEnd": 40,
          "symbol": "_parse_finite_float"
        },
        {
          "path": "tests/regression_calendar_no_tx_hardening.py",
          "lineStart": 196,
          "lineEnd": 214,
          "symbol": "main"
        },
        {
          "path": "tests/regression_excel_operator_calendar_cross_midnight.py",
          "lineStart": 61,
          "lineEnd": 108,
          "symbol": "main"
        },
        {
          "path": "tests/test_excel_import_hardening.py",
          "lineStart": 88,
          "lineEnd": 97,
          "symbol": "test_batch_quantity_float_is_rejected_without_truncation"
        },
        {
          "path": "core/services/common/excel_validators.py"
        },
        {
          "path": "web/routes/personnel_excel_operator_calendar.py"
        },
        {
          "path": "core/services/scheduler/calendar_service.py"
        },
        {
          "path": "core/services/scheduler/calendar_admin.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
        },
        {
          "path": "tests/regression_excel_operator_calendar_cross_midnight.py"
        },
        {
          "path": "tests/regression_calendar_no_tx_hardening.py"
        },
        {
          "path": "tests/test_excel_import_hardening.py"
        }
      ],
      "reviewedModules": [
        "core/services/common/excel_validators.py",
        "web/routes/personnel_excel_operator_calendar.py",
        "core/services/scheduler/calendar_service.py",
        "core/services/scheduler/calendar_admin.py"
      ],
      "recommendedNextAction": "综合三轮结论，给出最终审查判断，并优先要求修复高风险校验漂移与静默 warning 问题。",
      "findingIds": [
        "operator-calendar-nonfinite-preview-gap"
      ]
    }
  ],
  "findings": [
    {
      "id": "batch-excel-warning-drop",
      "severity": "medium",
      "category": "javascript",
      "title": "Excel 模板补建 warning 丢失",
      "descriptionMarkdown": "`ensure_template_ops_in_tx()` 会把模板自动解析产生的 warning 追加到 `svc._user_visible_warnings`，说明实现本意是把这些退化/兼容信息暴露给用户；但批次 Excel 确认导入路径只读取导入统计并直接 `flash_import_result(...)`，没有像手工建批与重建工序路径那样调用 `consume_user_visible_warnings()`。结果是 `auto_generate_ops=True` 时的模板补建 warning 会在成功导入后被静默吞掉，用户看不到“自动解析产生了兼容/降级”的提示，这与本次审查的‘无静默回退’目标相冲突。",
      "recommendationMarkdown": "让批次 Excel 导入成功路径与手工建批路径统一消费并展示 `consume_user_visible_warnings()`，至少在自动补建模板时把兼容/降级 warning 透传到页面提示中。",
      "evidence": [
        {
          "path": "core/services/scheduler/batch_template_ops.py",
          "lineStart": 93,
          "lineEnd": 118,
          "symbol": "ensure_template_ops_in_tx"
        },
        {
          "path": "web/routes/scheduler_excel_batches.py",
          "lineStart": 354,
          "lineEnd": 386,
          "symbol": "excel_batches_confirm"
        },
        {
          "path": "web/routes/scheduler_batches.py",
          "lineStart": 198,
          "lineEnd": 213,
          "symbol": "create_batch"
        },
        {
          "path": "web/routes/scheduler_batches.py",
          "lineStart": 386,
          "lineEnd": 400,
          "symbol": "generate_ops"
        },
        {
          "path": "core/services/scheduler/batch_service.py"
        },
        {
          "path": "core/services/scheduler/batch_excel_import.py"
        },
        {
          "path": "core/services/scheduler/batch_template_ops.py"
        },
        {
          "path": "core/services/scheduler/batch_write_rules.py"
        },
        {
          "path": "web/routes/scheduler_excel_batches.py"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        },
        {
          "path": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py"
        },
        {
          "path": "tests/regression_batch_excel_import_reject_part_change_without_rebuild.py"
        },
        {
          "path": "tests/regression_batch_service_legacy_template_resolver_rejects_strict_mode.py"
        },
        {
          "path": "tests/regression_batch_service_strict_mode_template_autoparse.py"
        },
        {
          "path": "tests/regression_batch_template_autobuild_same_tx.py"
        }
      ],
      "relatedMilestoneIds": [
        "m2_batch_service_split"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "batch-update-part-switch-guard-gap",
      "severity": "medium",
      "category": "maintainability",
      "title": "图号切换保护未统一落到公开更新接口",
      "descriptionMarkdown": "`batch_write_rules` 已抽出 `_ensure_part_switch_allowed()`，并且 Excel 导入更新路径会显式传入 `auto_generate_ops`，从而在‘改图号但不重建工序’时拒绝写入；但 `BatchService.update()` 构造 `build_update_payload()` 参数时没有传入 `auto_generate_ops`，默认命中 `_MISSING` 分支，保护逻辑直接失效。这样一来，同一条业务规则只在 Excel 路径生效，在公开服务更新接口上却失效，调用者可以把批次头图号改掉而保留旧批次工序，形成头/体不一致。",
      "recommendationMarkdown": "把“图号切换是否允许”收口为服务层统一约束：要么让 `BatchService.update()` 也显式要求/接收重建上下文，要么彻底禁止公开更新接口改图号，避免只有 Excel 路径守规矩。",
      "evidence": [
        {
          "path": "core/services/scheduler/batch_write_rules.py",
          "lineStart": 61,
          "lineEnd": 66,
          "symbol": "_ensure_part_switch_allowed"
        },
        {
          "path": "core/services/scheduler/batch_write_rules.py",
          "lineStart": 121,
          "lineEnd": 157,
          "symbol": "build_update_payload"
        },
        {
          "path": "core/services/scheduler/batch_service.py",
          "lineStart": 214,
          "lineEnd": 233,
          "symbol": "update"
        },
        {
          "path": "core/services/scheduler/batch_excel_import.py",
          "lineStart": 47,
          "lineEnd": 62,
          "symbol": "import_batches_from_preview_rows"
        },
        {
          "path": "tests/regression_batch_excel_import_reject_part_change_without_rebuild.py",
          "lineStart": 21,
          "lineEnd": 79,
          "symbol": "test_batch_excel_import_rejects_part_change_without_rebuild"
        },
        {
          "path": "core/services/scheduler/batch_service.py"
        },
        {
          "path": "core/services/scheduler/batch_excel_import.py"
        },
        {
          "path": "core/services/scheduler/batch_template_ops.py"
        },
        {
          "path": "core/services/scheduler/batch_write_rules.py"
        },
        {
          "path": "web/routes/scheduler_excel_batches.py"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        },
        {
          "path": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py"
        },
        {
          "path": "tests/regression_batch_excel_import_reject_part_change_without_rebuild.py"
        },
        {
          "path": "tests/regression_batch_service_legacy_template_resolver_rejects_strict_mode.py"
        },
        {
          "path": "tests/regression_batch_service_strict_mode_template_autoparse.py"
        },
        {
          "path": "tests/regression_batch_template_autobuild_same_tx.py"
        }
      ],
      "relatedMilestoneIds": [
        "m2_batch_service_split"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "operator-calendar-nonfinite-preview-gap",
      "severity": "high",
      "category": "other",
      "title": "日历 Excel 非有限数字校验漂移",
      "descriptionMarkdown": "`get_operator_calendar_row_validate_and_normalize()` 对“可用工时/效率”直接使用 `float()`，只检查 `<0` 或 `<=0`，因此 `NaN`、`Inf`、`-Inf` 这类值不会在预览/确认阶段被拦下；而确认后的真正写入路径会进入 `CalendarService.import_operator_calendar_from_preview_rows()`，最终调用 `CalendarAdmin` 的严格有限数解析，那里会明确拒绝非有限值。于是同一份数据会出现“预览通过、确认重放也通过、真正落库时才失败”的跨层契约漂移，既不优雅也不严谨。",
      "recommendationMarkdown": "把 `excel_validators` 中该路径的数值解析统一改成 `parse_finite_float()`（或直接复用 `CalendarAdmin` 的同源标准化逻辑），确保预览、确认、落库三段使用完全一致的有限数约束。",
      "evidence": [
        {
          "path": "core/services/common/excel_validators.py",
          "lineStart": 190,
          "lineEnd": 222,
          "symbol": "get_operator_calendar_row_validate_and_normalize"
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
          "symbol": "import_operator_calendar_from_preview_rows"
        },
        {
          "path": "core/services/scheduler/calendar_admin.py",
          "lineStart": 210,
          "lineEnd": 224,
          "symbol": "upsert_operator_calendar_no_tx"
        },
        {
          "path": "core/services/common/strict_parse.py",
          "lineStart": 32,
          "lineEnd": 40,
          "symbol": "_parse_finite_float"
        },
        {
          "path": "core/services/common/excel_validators.py"
        },
        {
          "path": "web/routes/personnel_excel_operator_calendar.py"
        },
        {
          "path": "core/services/scheduler/calendar_service.py"
        },
        {
          "path": "core/services/scheduler/calendar_admin.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
        },
        {
          "path": "tests/regression_excel_operator_calendar_cross_midnight.py"
        },
        {
          "path": "tests/regression_calendar_no_tx_hardening.py"
        },
        {
          "path": "tests/test_excel_import_hardening.py"
        }
      ],
      "relatedMilestoneIds": [
        "m3_excel_validator_consistency"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:c13f9430758a1b7565a8630b5d784c6ebf7e866d1686ab19798d5b7b3d41731c",
    "generatedAt": "2026-04-04T18:04:16.263Z",
    "locale": "zh-CN"
  }
}
```
