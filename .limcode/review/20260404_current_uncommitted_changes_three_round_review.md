# 20260404 未提交修改三轮深度审查
- 日期: 2026-04-04
- 概述: 针对当前工作区未提交修改开展三轮深度review，重点检查是否达成目的、是否存在过度兜底与静默回退、逻辑严谨性与潜在BUG。
- 状态: 已完成
- 总体结论: 需要后续跟进

## 评审范围

# 20260404 未提交修改三轮深度审查

- 日期：2026-04-04
- 范围：当前工作区未提交修改
- 方法：按模块分批审查，逐轮记录里程碑，重点关注目标达成度、实现简洁性、是否存在过度兜底或静默回退、逻辑严谨性与潜在BUG。

## 初始判断

尚在识别本次未提交修改的实际影响范围，将结合现有变更文件与相关测试进行逐步审查。

## 评审摘要

- 当前状态: 已完成
- 已审模块: core/services/scheduler/schedule_summary.py, core/services/scheduler/schedule_summary_assembly.py, core/services/scheduler/schedule_summary_degradation.py, core/services/scheduler/schedule_summary_freeze.py, web/viewmodels/scheduler_analysis_vm.py, core/services/scheduler/batch_write_rules.py, core/services/scheduler/batch_service.py, core/services/scheduler/batch_excel_import.py, core/services/scheduler/batch_template_ops.py, web/routes/scheduler_excel_batches.py, web/routes/scheduler_batches.py, core/services/common/excel_validators.py, web/routes/personnel_excel_operator_calendar.py, core/services/scheduler/calendar_service.py, core/services/scheduler/calendar_admin.py
- 当前进度: 已记录 3 个里程碑；最新：m3_operator_calendar_validator_recheck
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 3
- 问题严重级别分布: 高 0 / 中 1 / 低 2
- 最新结论: 三轮深度审查结论：本次未提交修改的主目标总体已经达成，且核心 BUG 基本都已被修掉。`schedule_summary` 拆分后的结构、合同与读侧消费基本成立；批次服务链已经补上公开更新图号切换保护，也不再静默吞掉模板补建 warning；人员专属日历 Excel 预览/确认与落库层之间的非有限数字漂移也已明显收敛。整体方向是对的，代码质量较此前版本明显提升。 但当前版本仍不建议直接视为“完全优雅、完全收口”。仍有 1 个中风险问题与 2 个低风险问题需要后续跟进：其一，批次 Excel 成功导入路径虽然补显了 warning，但现在是无上限逐条写入 flash，存在页面刷屏和会话膨胀风险；其二，公开批次更新图号切换保护缺少直达回归；其三，人员日历有限数字校验虽然语义上修好了，但实现仍未完全收口到单点严格解析，配套回归也不够贴身。综合判断：这批修改已经基本达成目的，但离“优雅、简洁、规则单源、长期稳态”还有一小段距离，建议先完成上述收口再视为最终通过。
- 下一步建议: 优先把批次 Excel warning 外显改成共享限流策略；随后补两类直达回归：`BatchService.update()` 图号切换保护、人员日历 `NaN/Inf` 预览/确认/落库一致拒绝；最后再考虑把人员日历有限数解析完全收口到 `parse_finite_float()` 或共用标准化函数。
- 总体结论: 需要后续跟进

## 评审发现

### 批次 Excel warning 外显无上限

- ID: batch-excel-warning-surface-unbounded
- 严重级别: 中
- 分类: 性能
- 跟踪状态: 开放
- 相关里程碑: m2_batch_import_and_write_rules
- 说明:

  批次 Excel 确认导入路径虽然修复了 warning 静默丢失，但实现方式是直接遍历 `svc.consume_user_visible_warnings()` 并逐条 `flash`。同一类 warning 在手工建批和重建工序路径已经通过 `_surface_route_warnings()` 统一做了数量上限与剩余条数汇总，而 Excel 路径没有复用这套策略。由于当前应用使用默认会话 cookie 机制，这种“逐条写入全部 warning”的做法在多零件、多模板补建场景下很容易造成页面刷屏，甚至推高会话体积，形成新的稳定性风险。
- 建议:

  把批次 Excel 成功路径改为复用 `_surface_route_warnings()` 或抽出共享限流函数，保留前几条明细并汇总剩余条数，不要再无上限地逐条写入 flash。
- 证据:
  - `core/services/scheduler/batch_write_rules.py`
  - `core/services/scheduler/batch_service.py`
  - `core/services/scheduler/batch_excel_import.py`
  - `core/services/scheduler/batch_template_ops.py`
  - `web/routes/scheduler_excel_batches.py`
  - `web/routes/scheduler_batches.py`
  - `core/services/common/normalize.py`
  - `web/bootstrap/factory.py`
  - `web/bootstrap/security.py`
  - `tests/regression_batch_excel_import_reject_part_change_without_rebuild.py`
  - `tests/regression_scheduler_batch_template_warning_surface.py`
  - `tests/regression_excel_import_result_semantics.py`

### 公开批次更新保护缺少直达回归

- ID: batch-update-guard-regression-gap
- 严重级别: 低
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: m2_batch_import_and_write_rules
- 说明:

  当前代码已经在 `BatchService.update()` 中显式把 `auto_generate_ops` 固定为 `False`，从而收紧了“公开更新接口禁止无重建切换图号”的规则；但现有测试仍主要覆盖 Excel 导入路径的拒绝行为，没有直接覆盖公开服务入口本身。这个修复点高度依赖一处很小的上下文字段传递，后续重构时非常容易再次被绕开，而现有测试套件未必能第一时间报警。
- 建议:

  补一条直接调用 `BatchService.update(part_no=...)` 的回归，验证图号切换会抛出校验错误且不会改动批次头与批次工序。
- 证据:
  - `core/services/scheduler/batch_write_rules.py`
  - `core/services/scheduler/batch_service.py`
  - `core/services/scheduler/batch_excel_import.py`
  - `core/services/scheduler/batch_template_ops.py`
  - `web/routes/scheduler_excel_batches.py`
  - `web/routes/scheduler_batches.py`
  - `core/services/common/normalize.py`
  - `web/bootstrap/factory.py`
  - `web/bootstrap/security.py`
  - `tests/regression_batch_excel_import_reject_part_change_without_rebuild.py`
  - `tests/regression_scheduler_batch_template_warning_surface.py`
  - `tests/regression_excel_import_result_semantics.py`

### 人员日历有限数字校验仍是双份实现

- ID: operator-calendar-finite-parse-not-single-source
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: m3_operator_calendar_validator_recheck
- 说明:

  当前 `get_operator_calendar_row_validate_and_normalize()` 已经补上了非有限数字拒绝逻辑，运行结果与 `CalendarAdmin` 基本一致；但它仍然没有直接复用 `parse_finite_float()`，而是手写了一份 `float() + math.isfinite()` 分支。与此同时，现有测试覆盖了跨午夜、负工时、零效率等相邻场景，却没有专门锁住 `NaN/Inf` 在预览与确认阶段的行为。这意味着本次修复虽然解决了眼前 BUG，但还没有完全达到“同源规则、低维护成本”的理想状态，未来再次漂移的门槛仍然偏低。
- 建议:

  把人员日历 Excel 的“可用工时/效率”解析直接改为复用 `parse_finite_float()` 或抽成与 `CalendarAdmin` 共用的标准化函数；同时补两条直达回归，分别覆盖 `NaN` 与 `Inf` 在预览、确认、落库三段的一致拒绝语义。
- 证据:
  - `core/services/common/excel_validators.py`
  - `core/services/common/number_utils.py`
  - `core/services/common/strict_parse.py`
  - `web/routes/personnel_excel_operator_calendar.py`
  - `core/services/scheduler/calendar_service.py`
  - `core/services/scheduler/calendar_admin.py`
  - `tests/regression_excel_operator_calendar_cross_midnight.py`
  - `tests/regression_calendar_no_tx_hardening.py`
  - `tests/test_excel_import_hardening.py`

## 评审里程碑

### m1_schedule_summary_split_recheck · 第一轮：调度摘要拆分与读侧消费复核

- 状态: 已完成
- 记录时间: 2026-04-04T18:40:39.098Z
- 已审模块: core/services/scheduler/schedule_summary.py, core/services/scheduler/schedule_summary_assembly.py, core/services/scheduler/schedule_summary_degradation.py, core/services/scheduler/schedule_summary_freeze.py, web/viewmodels/scheduler_analysis_vm.py
- 摘要:

  已完成 `schedule_summary` 拆分面与分析页读侧的首轮复核。当前实现相比此前版本明显更清晰：主入口文件已降到可控体量，`assembly / degradation / freeze` 三个子模块边界基本自然；`comparison_metric / best_score_schema / top-level degradation_events / invalid_due_count / unscheduled_batch_count / size guard` 等关键留痕字段均已落到摘要合同，并且分析页读侧已经开始优先消费这些字段。就本轮观察，拆分目标基本达成，未发现新的阻断级 BUG。
- 结论:

  调度摘要拆分方向正确，结构与可见性都比此前版本更好，当前主要风险已不在该模块。
- 证据:
  - `core/services/scheduler/schedule_summary.py`
  - `core/services/scheduler/schedule_summary_assembly.py`
  - `core/services/scheduler/schedule_summary_degradation.py`
  - `core/services/scheduler/schedule_summary_freeze.py`
  - `web/viewmodels/scheduler_analysis_vm.py`
  - `tests/regression_schedule_summary_v11_contract.py`
  - `tests/regression_schedule_summary_freeze_state_contract.py`
  - `tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py`
  - `tests/regression_schedule_summary_size_guard_large_lists.py`
  - `tests/regression_schedule_summary_algo_warnings_union.py`
  - `tests/regression_scheduler_analysis_observability.py`
- 下一步建议:

  继续审查批次服务与 Excel 导入链路，重点复核此前发现的静默 warning、图号切换保护与新实现是否引入新的边界问题。

### m2_batch_import_and_write_rules · 第二轮：批次写入规则与 Excel 导入链路复核

- 状态: 已完成
- 记录时间: 2026-04-04T18:41:53.396Z
- 已审模块: core/services/scheduler/batch_write_rules.py, core/services/scheduler/batch_service.py, core/services/scheduler/batch_excel_import.py, core/services/scheduler/batch_template_ops.py, web/routes/scheduler_excel_batches.py, web/routes/scheduler_batches.py
- 摘要:

  已完成 `batch_write_rules / batch_service / batch_excel_import / scheduler_excel_batches / scheduler_batches` 的第二轮复核。此前明确的两个逻辑缺口目前已得到实质修正：公开 `BatchService.update()` 已把图号切换保护收回到服务层默认约束，批次 Excel 确认导入路径也开始消费并外显模板补建 warning，方向正确。不过本轮仍发现 1 个新的中风险问题：Excel 导入成功路径直接把所有 warning 逐条写入 flash，而手工建批与重建工序路径已经有数量上限与汇总策略；在当前默认会话方案下，这会带来页面刷屏与会话膨胀风险。此外，图号切换保护的公开服务入口仍缺少直达回归，当前测试主要锁住了 Excel 路径。
- 结论:

  批次服务拆分与规则收口整体已接近目标，但 Excel warning 外显策略还不够优雅，且公开更新入口的修复验证仍不够贴身，暂时不能视为完全收口。
- 证据:
  - `core/services/scheduler/batch_write_rules.py`
  - `core/services/scheduler/batch_service.py`
  - `core/services/scheduler/batch_excel_import.py`
  - `core/services/scheduler/batch_template_ops.py`
  - `web/routes/scheduler_excel_batches.py`
  - `web/routes/scheduler_batches.py`
  - `core/services/common/normalize.py`
  - `web/bootstrap/factory.py`
  - `web/bootstrap/security.py`
  - `tests/regression_batch_excel_import_reject_part_change_without_rebuild.py`
  - `tests/regression_scheduler_batch_template_warning_surface.py`
  - `tests/regression_excel_import_result_semantics.py`
- 下一步建议:

  继续复核人员专属日历 Excel 校验链，确认非有限数字问题是否真正与落库层对齐，并检查当前修复是否还有实现重复与回归覆盖空洞。
- 问题:
  - [中] 性能: 批次 Excel warning 外显无上限
  - [低] 测试: 公开批次更新保护缺少直达回归

### m3_operator_calendar_validator_recheck · 第三轮：人员专属日历 Excel 校验链复核

- 状态: 已完成
- 记录时间: 2026-04-04T18:42:28.334Z
- 已审模块: core/services/common/excel_validators.py, web/routes/personnel_excel_operator_calendar.py, core/services/scheduler/calendar_service.py, core/services/scheduler/calendar_admin.py
- 摘要:

  已完成 `excel_validators / personnel_excel_operator_calendar / calendar_service / calendar_admin` 的第三轮复核。此前的高风险逻辑 BUG 目前确实已修掉：预览与确认阶段已经会拒绝 `NaN/Inf/-Inf`，不再把非有限数字拖到真正落库时才爆炸，行为与 `CalendarAdmin` 明显更接近。从运行语义看，这条链路现在基本达成目的。不过实现上仍有一个低风险但值得收口的问题：预览校验层仍然手写了一份 `float()+isfinite` 规则，而不是直接复用严格解析门面；再叠加当前测试主要覆盖跨午夜、负工时、零效率，没有专门锁住 `NaN/Inf` 的预览/确认回归，后续演进仍存在再漂移的空间。
- 结论:

  人员日历导入链路的核心 BUG 已修复，当前未再看到阻断级问题；但从优雅性和长期稳态看，仍建议把有限数校验真正收口到单点实现，并补齐贴身回归。
- 证据:
  - `core/services/common/excel_validators.py`
  - `core/services/common/number_utils.py`
  - `core/services/common/strict_parse.py`
  - `web/routes/personnel_excel_operator_calendar.py`
  - `core/services/scheduler/calendar_service.py`
  - `core/services/scheduler/calendar_admin.py`
  - `tests/regression_excel_operator_calendar_cross_midnight.py`
  - `tests/regression_calendar_no_tx_hardening.py`
  - `tests/test_excel_import_hardening.py`
- 下一步建议:

  汇总三轮结论，优先处理批次 Excel warning 限流问题，并顺手补齐公开批次更新与人员日历非有限数字的直达回归。
- 问题:
  - [低] 可维护性: 人员日历有限数字校验仍是双份实现

## 最终结论

三轮深度审查结论：本次未提交修改的主目标总体已经达成，且核心 BUG 基本都已被修掉。`schedule_summary` 拆分后的结构、合同与读侧消费基本成立；批次服务链已经补上公开更新图号切换保护，也不再静默吞掉模板补建 warning；人员专属日历 Excel 预览/确认与落库层之间的非有限数字漂移也已明显收敛。整体方向是对的，代码质量较此前版本明显提升。

但当前版本仍不建议直接视为“完全优雅、完全收口”。仍有 1 个中风险问题与 2 个低风险问题需要后续跟进：其一，批次 Excel 成功导入路径虽然补显了 warning，但现在是无上限逐条写入 flash，存在页面刷屏和会话膨胀风险；其二，公开批次更新图号切换保护缺少直达回归；其三，人员日历有限数字校验虽然语义上修好了，但实现仍未完全收口到单点严格解析，配套回归也不够贴身。综合判断：这批修改已经基本达成目的，但离“优雅、简洁、规则单源、长期稳态”还有一小段距离，建议先完成上述收口再视为最终通过。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnko980a-7nxbcm",
  "createdAt": "2026-04-04T00:00:00.000Z",
  "updatedAt": "2026-04-04T18:42:42.880Z",
  "finalizedAt": "2026-04-04T18:42:42.880Z",
  "status": "completed",
  "overallDecision": "needs_follow_up",
  "header": {
    "title": "20260404 未提交修改三轮深度审查",
    "date": "2026-04-04",
    "overview": "针对当前工作区未提交修改开展三轮深度review，重点检查是否达成目的、是否存在过度兜底与静默回退、逻辑严谨性与潜在BUG。"
  },
  "scope": {
    "markdown": "# 20260404 未提交修改三轮深度审查\n\n- 日期：2026-04-04\n- 范围：当前工作区未提交修改\n- 方法：按模块分批审查，逐轮记录里程碑，重点关注目标达成度、实现简洁性、是否存在过度兜底或静默回退、逻辑严谨性与潜在BUG。\n\n## 初始判断\n\n尚在识别本次未提交修改的实际影响范围，将结合现有变更文件与相关测试进行逐步审查。"
  },
  "summary": {
    "latestConclusion": "三轮深度审查结论：本次未提交修改的主目标总体已经达成，且核心 BUG 基本都已被修掉。`schedule_summary` 拆分后的结构、合同与读侧消费基本成立；批次服务链已经补上公开更新图号切换保护，也不再静默吞掉模板补建 warning；人员专属日历 Excel 预览/确认与落库层之间的非有限数字漂移也已明显收敛。整体方向是对的，代码质量较此前版本明显提升。\n\n但当前版本仍不建议直接视为“完全优雅、完全收口”。仍有 1 个中风险问题与 2 个低风险问题需要后续跟进：其一，批次 Excel 成功导入路径虽然补显了 warning，但现在是无上限逐条写入 flash，存在页面刷屏和会话膨胀风险；其二，公开批次更新图号切换保护缺少直达回归；其三，人员日历有限数字校验虽然语义上修好了，但实现仍未完全收口到单点严格解析，配套回归也不够贴身。综合判断：这批修改已经基本达成目的，但离“优雅、简洁、规则单源、长期稳态”还有一小段距离，建议先完成上述收口再视为最终通过。",
    "recommendedNextAction": "优先把批次 Excel warning 外显改成共享限流策略；随后补两类直达回归：`BatchService.update()` 图号切换保护、人员日历 `NaN/Inf` 预览/确认/落库一致拒绝；最后再考虑把人员日历有限数解析完全收口到 `parse_finite_float()` 或共用标准化函数。",
    "reviewedModules": [
      "core/services/scheduler/schedule_summary.py",
      "core/services/scheduler/schedule_summary_assembly.py",
      "core/services/scheduler/schedule_summary_degradation.py",
      "core/services/scheduler/schedule_summary_freeze.py",
      "web/viewmodels/scheduler_analysis_vm.py",
      "core/services/scheduler/batch_write_rules.py",
      "core/services/scheduler/batch_service.py",
      "core/services/scheduler/batch_excel_import.py",
      "core/services/scheduler/batch_template_ops.py",
      "web/routes/scheduler_excel_batches.py",
      "web/routes/scheduler_batches.py",
      "core/services/common/excel_validators.py",
      "web/routes/personnel_excel_operator_calendar.py",
      "core/services/scheduler/calendar_service.py",
      "core/services/scheduler/calendar_admin.py"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 3,
    "severity": {
      "high": 0,
      "medium": 1,
      "low": 2
    }
  },
  "milestones": [
    {
      "id": "m1_schedule_summary_split_recheck",
      "title": "第一轮：调度摘要拆分与读侧消费复核",
      "status": "completed",
      "recordedAt": "2026-04-04T18:40:39.098Z",
      "summaryMarkdown": "已完成 `schedule_summary` 拆分面与分析页读侧的首轮复核。当前实现相比此前版本明显更清晰：主入口文件已降到可控体量，`assembly / degradation / freeze` 三个子模块边界基本自然；`comparison_metric / best_score_schema / top-level degradation_events / invalid_due_count / unscheduled_batch_count / size guard` 等关键留痕字段均已落到摘要合同，并且分析页读侧已经开始优先消费这些字段。就本轮观察，拆分目标基本达成，未发现新的阻断级 BUG。",
      "conclusionMarkdown": "调度摘要拆分方向正确，结构与可见性都比此前版本更好，当前主要风险已不在该模块。",
      "evidence": [
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
          "path": "web/viewmodels/scheduler_analysis_vm.py"
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
        },
        {
          "path": "tests/regression_schedule_summary_algo_warnings_union.py"
        },
        {
          "path": "tests/regression_scheduler_analysis_observability.py"
        }
      ],
      "reviewedModules": [
        "core/services/scheduler/schedule_summary.py",
        "core/services/scheduler/schedule_summary_assembly.py",
        "core/services/scheduler/schedule_summary_degradation.py",
        "core/services/scheduler/schedule_summary_freeze.py",
        "web/viewmodels/scheduler_analysis_vm.py"
      ],
      "recommendedNextAction": "继续审查批次服务与 Excel 导入链路，重点复核此前发现的静默 warning、图号切换保护与新实现是否引入新的边界问题。",
      "findingIds": []
    },
    {
      "id": "m2_batch_import_and_write_rules",
      "title": "第二轮：批次写入规则与 Excel 导入链路复核",
      "status": "completed",
      "recordedAt": "2026-04-04T18:41:53.396Z",
      "summaryMarkdown": "已完成 `batch_write_rules / batch_service / batch_excel_import / scheduler_excel_batches / scheduler_batches` 的第二轮复核。此前明确的两个逻辑缺口目前已得到实质修正：公开 `BatchService.update()` 已把图号切换保护收回到服务层默认约束，批次 Excel 确认导入路径也开始消费并外显模板补建 warning，方向正确。不过本轮仍发现 1 个新的中风险问题：Excel 导入成功路径直接把所有 warning 逐条写入 flash，而手工建批与重建工序路径已经有数量上限与汇总策略；在当前默认会话方案下，这会带来页面刷屏与会话膨胀风险。此外，图号切换保护的公开服务入口仍缺少直达回归，当前测试主要锁住了 Excel 路径。",
      "conclusionMarkdown": "批次服务拆分与规则收口整体已接近目标，但 Excel warning 外显策略还不够优雅，且公开更新入口的修复验证仍不够贴身，暂时不能视为完全收口。",
      "evidence": [
        {
          "path": "core/services/scheduler/batch_write_rules.py"
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
          "path": "web/routes/scheduler_excel_batches.py"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        },
        {
          "path": "core/services/common/normalize.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "web/bootstrap/security.py"
        },
        {
          "path": "tests/regression_batch_excel_import_reject_part_change_without_rebuild.py"
        },
        {
          "path": "tests/regression_scheduler_batch_template_warning_surface.py"
        },
        {
          "path": "tests/regression_excel_import_result_semantics.py"
        }
      ],
      "reviewedModules": [
        "core/services/scheduler/batch_write_rules.py",
        "core/services/scheduler/batch_service.py",
        "core/services/scheduler/batch_excel_import.py",
        "core/services/scheduler/batch_template_ops.py",
        "web/routes/scheduler_excel_batches.py",
        "web/routes/scheduler_batches.py"
      ],
      "recommendedNextAction": "继续复核人员专属日历 Excel 校验链，确认非有限数字问题是否真正与落库层对齐，并检查当前修复是否还有实现重复与回归覆盖空洞。",
      "findingIds": [
        "batch-excel-warning-surface-unbounded",
        "batch-update-guard-regression-gap"
      ]
    },
    {
      "id": "m3_operator_calendar_validator_recheck",
      "title": "第三轮：人员专属日历 Excel 校验链复核",
      "status": "completed",
      "recordedAt": "2026-04-04T18:42:28.334Z",
      "summaryMarkdown": "已完成 `excel_validators / personnel_excel_operator_calendar / calendar_service / calendar_admin` 的第三轮复核。此前的高风险逻辑 BUG 目前确实已修掉：预览与确认阶段已经会拒绝 `NaN/Inf/-Inf`，不再把非有限数字拖到真正落库时才爆炸，行为与 `CalendarAdmin` 明显更接近。从运行语义看，这条链路现在基本达成目的。不过实现上仍有一个低风险但值得收口的问题：预览校验层仍然手写了一份 `float()+isfinite` 规则，而不是直接复用严格解析门面；再叠加当前测试主要覆盖跨午夜、负工时、零效率，没有专门锁住 `NaN/Inf` 的预览/确认回归，后续演进仍存在再漂移的空间。",
      "conclusionMarkdown": "人员日历导入链路的核心 BUG 已修复，当前未再看到阻断级问题；但从优雅性和长期稳态看，仍建议把有限数校验真正收口到单点实现，并补齐贴身回归。",
      "evidence": [
        {
          "path": "core/services/common/excel_validators.py"
        },
        {
          "path": "core/services/common/number_utils.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
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
      "recommendedNextAction": "汇总三轮结论，优先处理批次 Excel warning 限流问题，并顺手补齐公开批次更新与人员日历非有限数字的直达回归。",
      "findingIds": [
        "operator-calendar-finite-parse-not-single-source"
      ]
    }
  ],
  "findings": [
    {
      "id": "batch-excel-warning-surface-unbounded",
      "severity": "medium",
      "category": "performance",
      "title": "批次 Excel warning 外显无上限",
      "descriptionMarkdown": "批次 Excel 确认导入路径虽然修复了 warning 静默丢失，但实现方式是直接遍历 `svc.consume_user_visible_warnings()` 并逐条 `flash`。同一类 warning 在手工建批和重建工序路径已经通过 `_surface_route_warnings()` 统一做了数量上限与剩余条数汇总，而 Excel 路径没有复用这套策略。由于当前应用使用默认会话 cookie 机制，这种“逐条写入全部 warning”的做法在多零件、多模板补建场景下很容易造成页面刷屏，甚至推高会话体积，形成新的稳定性风险。",
      "recommendationMarkdown": "把批次 Excel 成功路径改为复用 `_surface_route_warnings()` 或抽出共享限流函数，保留前几条明细并汇总剩余条数，不要再无上限地逐条写入 flash。",
      "evidence": [
        {
          "path": "core/services/scheduler/batch_write_rules.py"
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
          "path": "web/routes/scheduler_excel_batches.py"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        },
        {
          "path": "core/services/common/normalize.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "web/bootstrap/security.py"
        },
        {
          "path": "tests/regression_batch_excel_import_reject_part_change_without_rebuild.py"
        },
        {
          "path": "tests/regression_scheduler_batch_template_warning_surface.py"
        },
        {
          "path": "tests/regression_excel_import_result_semantics.py"
        }
      ],
      "relatedMilestoneIds": [
        "m2_batch_import_and_write_rules"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "batch-update-guard-regression-gap",
      "severity": "low",
      "category": "test",
      "title": "公开批次更新保护缺少直达回归",
      "descriptionMarkdown": "当前代码已经在 `BatchService.update()` 中显式把 `auto_generate_ops` 固定为 `False`，从而收紧了“公开更新接口禁止无重建切换图号”的规则；但现有测试仍主要覆盖 Excel 导入路径的拒绝行为，没有直接覆盖公开服务入口本身。这个修复点高度依赖一处很小的上下文字段传递，后续重构时非常容易再次被绕开，而现有测试套件未必能第一时间报警。",
      "recommendationMarkdown": "补一条直接调用 `BatchService.update(part_no=...)` 的回归，验证图号切换会抛出校验错误且不会改动批次头与批次工序。",
      "evidence": [
        {
          "path": "core/services/scheduler/batch_write_rules.py"
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
          "path": "web/routes/scheduler_excel_batches.py"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        },
        {
          "path": "core/services/common/normalize.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "web/bootstrap/security.py"
        },
        {
          "path": "tests/regression_batch_excel_import_reject_part_change_without_rebuild.py"
        },
        {
          "path": "tests/regression_scheduler_batch_template_warning_surface.py"
        },
        {
          "path": "tests/regression_excel_import_result_semantics.py"
        }
      ],
      "relatedMilestoneIds": [
        "m2_batch_import_and_write_rules"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "operator-calendar-finite-parse-not-single-source",
      "severity": "low",
      "category": "maintainability",
      "title": "人员日历有限数字校验仍是双份实现",
      "descriptionMarkdown": "当前 `get_operator_calendar_row_validate_and_normalize()` 已经补上了非有限数字拒绝逻辑，运行结果与 `CalendarAdmin` 基本一致；但它仍然没有直接复用 `parse_finite_float()`，而是手写了一份 `float() + math.isfinite()` 分支。与此同时，现有测试覆盖了跨午夜、负工时、零效率等相邻场景，却没有专门锁住 `NaN/Inf` 在预览与确认阶段的行为。这意味着本次修复虽然解决了眼前 BUG，但还没有完全达到“同源规则、低维护成本”的理想状态，未来再次漂移的门槛仍然偏低。",
      "recommendationMarkdown": "把人员日历 Excel 的“可用工时/效率”解析直接改为复用 `parse_finite_float()` 或抽成与 `CalendarAdmin` 共用的标准化函数；同时补两条直达回归，分别覆盖 `NaN` 与 `Inf` 在预览、确认、落库三段的一致拒绝语义。",
      "evidence": [
        {
          "path": "core/services/common/excel_validators.py"
        },
        {
          "path": "core/services/common/number_utils.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
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
        "m3_operator_calendar_validator_recheck"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:52f3695b0f493420fd73b676d2deb7c3675e88f9aff8c6515421e07e73ad196a",
    "generatedAt": "2026-04-04T18:42:42.880Z",
    "locale": "zh-CN"
  }
}
```
