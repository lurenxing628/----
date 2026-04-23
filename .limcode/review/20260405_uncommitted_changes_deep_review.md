# 未提交修改三轮深度review
- 日期: 2026-04-05
- 概述: 针对当前工作区未提交修改进行三轮增量审查，关注目的达成、实现简洁性、兜底/静默回退以及潜在BUG。
- 状态: 已完成
- 总体结论: 需要后续跟进

## 评审范围

# 未提交修改三轮深度review

- 日期：2026-04-05
- 范围：当前工作区 `.git/modified_list.txt` 中列出的未提交修改
- 方法：按三轮进行，先做改动清单与风险分层，再做核心服务/算法链路深挖，最后做路由/模板/测试与一致性交叉审查
- 关注点：是否达成目的、实现是否优雅简洁、是否存在过度兜底或静默回退、逻辑是否严谨、是否仍有BUG

## 初始判断

待审文件覆盖算法、排产服务、Excel 导入、路由、模板与测试，属于跨层联动改动，风险较高。优先关注：
1. 数值解析与严格模式语义是否在各层保持一致；
2. 批次导入与模板回填链路是否引入隐藏兜底；
3. 排产结果持久化/汇总是否因契约调整出现边界退化；
4. 路由层是否把服务层异常重新静默吞掉；
5. 测试是否真正覆盖新增分支，而不是仅固化当前实现。

## 评审摘要

- 当前状态: 已完成
- 已审模块: scheduler.batch_excel, scheduler.batch_service, common.excel_validators, scheduler.schedule_persistence, scheduler.routes, ui_mode, team_pages, batch_detail_linkage, scheduler.config, scheduler.optimizer, scheduler.orchestrator, scheduler.persistence, scheduler.summary, greedy.scheduler, greedy.auto_assign, greedy.dispatch.sgs, system.backup, system.history, templates.base, templates.components.excel_import, test.template_endpoint_scan, process.route_parser, process.part_service, process.external_group_service, process.supplier_service, process.excel_routes, process.excel_part_operation_hours, process.excel_suppliers, process.parts_route, scheduler.calendar_admin, scheduler.calendar_routes, scheduler.excel_calendar, common.excel_utils, dashboard, equipment.pages, equipment.excel_machines, equipment.excel_links, personnel.pages, personnel.excel_operators, personnel.excel_links, personnel.calendar_pages, templates.equipment.list, templates.personnel.calendar, templates.process.detail, templates.process.list, templates.scheduler.batches, templates.scheduler.batches_manage, templates.scheduler.calendar, templates.scheduler.excel_batches, config_manual, manual_layout_tooling, test.architecture_fitness, web_new_test.base
- 当前进度: 已记录 5 个里程碑；最新：m5_ui_tooling_guardrails
- 里程碑总数: 5
- 已完成里程碑: 5
- 问题总数: 4
- 问题严重级别分布: 高 0 / 中 4 / 低 0
- 最新结论: 当前未提交改动相较上一轮已经明显收口：历史已知的批次告警限量展示、`BatchService.update()` 直接改零件号回归缺口、以及人员专属日历有限数字解析分叉问题都已看到有效修复；多数过程服务、列表页、说明书脚本与模板契约也基本清楚，没有再发现新的高危破坏性错误。 但从“逻辑严谨、避免过度兜底、保持契约单一来源”的标准看，本轮仍不能直接接受。当前至少还有 4 个中等问题未收口： 1. `excel-route-strict-numeric-drift`：多个 Excel 路由重新手写数字解析，已经和服务层严格契约漂移，存在预览放过脏值、确认阶段才失败，甚至写错主键的真实 BUG 风险； 2. `sgs-auto-assign-probe-counter-inflation`：当前改动后的 `sgs` / `auto_assign` / `schedule_summary` 仍会把评分探测次数污染进最终统计，影响可观测性和审计口径； 3. `silent-swallow-fitness-count-only-whitelist`：`test_no_silent_exception_swallow` 从位置约束退化成文件计数上限，削弱了后续识别新增静默吞错的能力； 4. `template-urlfor-regex-overmatches-safe-url-for`：历史测试误报问题仍未收口。 综合判断：本轮代码大方向基本对，但还没有达到可以安心收口的程度，建议先修完上述问题再做一次针对当前 `.git/modified_list.txt` 的定向回归。
- 下一步建议: 优先修复 `excel-route-strict-numeric-drift`、`sgs-auto-assign-probe-counter-inflation`、`silent-swallow-fitness-count-only-whitelist`；如仍保留模板端点扫描回归，再同时修正 `template-urlfor-regex-overmatches-safe-url-for`。完成后，针对当前 `.git/modified_list.txt` 重新跑一轮定向回归再决定是否接受。
- 总体结论: 需要后续跟进

## 评审发现

### SGS 探测式自动分配污染统计计数

- ID: sgs-auto-assign-probe-counter-inflation
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: m2_scheduler_core
- 说明:

  `dispatch_sgs` 在评分阶段为了估算候选优先级，会提前调用 `scheduler._auto_assign_internal_resources(...)` 做探测式选机选人；但 `auto_assign_internal_resources` 内部在缺少工种、缺少候选设备、候选人员为空、不可行配对等分支都会直接 `increment_counter(...)`。由于这些探测发生在真正排产之前，而且同一个候选可能在多轮评分中被重复探测，最终 `fallback_counts` 记录的是“评分探测次数”而不是“真实排产失败次数”。后续 `schedule_summary.build_result_summary()` 又会把这些计数并入摘要输出，导致留痕和诊断口径失真。该问题不会直接改变排产结果，但会误导排障、审计与回归比较。
- 建议:

  把自动分配拆成“纯评估/不记数”的探测入口与“真实执行/记数”的正式入口，或者为评分阶段新增显式 `probe_only` 开关，避免探测过程污染最终统计。
- 证据:
  - `core/algorithms/greedy/dispatch/sgs.py:216-248`
  - `core/algorithms/greedy/auto_assign.py:45-109`
  - `core/algorithms/greedy/auto_assign.py:221-225`
  - `core/services/scheduler/schedule_summary.py:415-416`
  - `core/services/scheduler/schedule_summary.py:465-466`
  - `core/services/scheduler/config_service.py`
  - `core/services/scheduler/config_snapshot.py`
  - `core/services/scheduler/config_validator.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_persistence.py`
  - `core/services/scheduler/schedule_summary.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `tests/regression_schedule_summary_v11_contract.py`
  - `tests/regression_auto_assign_persist_truthy_variants.py`
  - `tests/regression_schedule_service_passes_algo_stats_to_summary.py`
  - `tests/regression_sgs_scoring_fallback_unscorable.py`
  - `tests/regression_sgs_penalize_nonfinite_proc_hours.py`

### 端点扫描回归把 safe_url_for 当成强制 url_for

- ID: template-urlfor-regex-overmatches-safe-url-for
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: m3_ui_routes_tests
- 说明:

  `tests/regression_template_urlfor_endpoints.py` 的说明明确写着：`safe_url_for(...)` 允许引用未注册端点，不应像 `url_for(...)` 那样直接判失败；但实现里用于抓取 `url_for(...)` 的正则是 `url_for\(`，它同样会匹配 `safe_url_for(` 里的子串。随后同一行又会被 `pat_safe` 再抓一次，于是“可选链接”实际上会同时进入 `missing_url` 与 `missing_safe` 两套集合，最终仍可能触发失败分支。这样会把本应允许缺失的灰度/可选入口错误地升级为强制断言，导致测试契约与实现描述不一致。
- 建议:

  把 `url_for` 提取规则改成不会命中 `safe_url_for` 的表达式（例如增加词边界或显式负向前瞻/后顾），或改用更稳妥的模板语法级扫描，确保“强制链接”和“可选链接”分开统计。
- 证据:
  - `tests/regression_template_urlfor_endpoints.py:9-15`
  - `tests/regression_template_urlfor_endpoints.py:60-61`
  - `tests/regression_template_urlfor_endpoints.py:74-82`
  - `tests/regression_template_urlfor_endpoints.py:112-129`
  - `web/routes/system_backup.py`
  - `web/routes/system_history.py`
  - `web/ui_mode.py`
  - `templates/base.html`
  - `templates/components/excel_import.html`
  - `tests/test_ui_mode.py`
  - `tests/regression_template_urlfor_endpoints.py`
  - `tests/regression_backup_restore_pending_verify_code.py`

### Excel 路由数值校验与服务契约漂移

- ID: excel-route-strict-numeric-drift
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: m4_process_calendar_excel
- 说明:

  本轮修改里，多个 Excel 路由重新手写了整数/浮点解析，未复用服务层已经存在的严格解析入口，导致 preview/confirm 与真正写库阶段的契约再次分裂。`web/routes/scheduler_excel_calendar.py` 用原始 `float(...)` 校验“可用工时/效率”，会把 `True`、`NaN`、`Inf` 等值放过预览，但 `CalendarAdmin` 真正落库时会拒绝；`web/routes/process_excel_part_operation_hours.py::_parse_seq()` 会把 `True` 与 `"5e0"` 变成合法工序号，直接绕过 `PartOperationHoursExcelImportService._coerce_int()` 的防御；`web/routes/process_excel_suppliers.py::_normalize_supplier_default_days()` 会把 `True` 当成 `1.0`，与 `SupplierService` 通过 `parse_required_float()` 拒绝布尔值的行为不一致。结果是：有的脏数据会在预览阶段被错误放行，有的会在确认阶段才爆出异常，有的甚至会静默写到错误主键上，整体既不简洁也不严谨。
- 建议:

  把这些路由层校验统一收敛到共享严格解析入口：日历链路直接复用 `CalendarAdmin` / `parse_finite_float`，零件工时链路复用 `PartOperationHoursExcelImportService._coerce_int()` 或等价共享函数，供应商链路复用 `parse_required_float()` / `SupplierService`。同时补上路由级回归，至少覆盖 `True/False/NaN/Inf/"5e0"` 这几类输入。
- 证据:
  - `web/routes/scheduler_excel_calendar.py:197-220#validate_row`
  - `web/routes/scheduler_excel_calendar.py:331-353#validate_row`
  - `core/services/scheduler/calendar_admin.py:138-147#_build_work_calendar`
  - `web/routes/process_excel_part_operation_hours.py:46-64#_parse_seq`
  - `core/services/process/part_operation_hours_excel_import_service.py:111-129#_coerce_int`
  - `web/routes/process_excel_suppliers.py:89-100#_normalize_supplier_default_days`
  - `core/services/process/supplier_service.py:29-36#_normalize_default_days`
  - `core/services/common/strict_parse.py:32-64#parse_required_float`
  - `tests/test_part_operation_hours_import_apply_defense.py:13-29#test_parse_write_row_accepts_integer_float_string_forms`
  - `tests/regression_calendar_no_tx_hardening.py:240-252#main`
  - `core/services/process/route_parser.py`
  - `core/services/process/part_service.py`
  - `core/services/process/external_group_service.py`
  - `core/services/process/supplier_service.py`
  - `web/routes/process_excel_routes.py`
  - `web/routes/process_excel_part_operation_hours.py`
  - `web/routes/process_excel_suppliers.py`
  - `web/routes/process_parts.py`
  - `web/routes/scheduler_calendar_pages.py`
  - `web/routes/scheduler_excel_calendar.py`
  - `core/services/scheduler/calendar_admin.py`
  - `web/routes/excel_utils.py`
  - `core/services/process/part_operation_hours_excel_import_service.py`
  - `core/services/common/strict_parse.py`
  - `tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py`
  - `tests/regression_external_group_service_strict_mode_blank_days.py`
  - `tests/regression_supplier_service_invalid_default_days_not_silent.py`
  - `tests/regression_process_reparse_preserve_internal_hours.py`
  - `tests/regression_process_suppliers_route_reject_blank_default_days.py`
  - `tests/regression_calendar_no_tx_hardening.py`
  - `tests/regression_scheduler_excel_calendar_uses_executor.py`
  - `tests/test_part_operation_hours_import_apply_defense.py`

### 静默吞异常护栏退化为按文件计数

- ID: silent-swallow-fitness-count-only-whitelist
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: m5_ui_tooling_guardrails
- 说明:

  `tests/test_architecture_fitness.py::test_no_silent_exception_swallow()` 现在先把 `known_violations` 压平成 `known_counts`，随后只检查“每个文件里的 `except Exception: pass / ...` 数量是否超过上限”。这确实能避免单纯行号漂移带来的误报，但代价是丢掉了对具体吞异常位置的约束：同一个文件里，删除一个旧的 allowlist 点、再新增一个新的静默吞错点，只要总数不变，测试就会通过。考虑到当前代码里已经存在不少兼容性回退分支，这个改动会明显削弱后续发现新增静默吞错的能力，也会降低 review 对这类问题的信心。
- 建议:

  不要只按文件计数做白名单。更稳妥的做法是保留具体位置约束，并用 AST 上下文、处理体摘要或稳定指纹来抵抗行号漂移；至少也要把 allowlist 从“文件级数量”提升到“文件+处理块语义”级别。
- 证据:
  - `tests/test_architecture_fitness.py:391-551#test_no_silent_exception_swallow`
  - `web/routes/dashboard.py`
  - `web/routes/equipment_pages.py`
  - `web/routes/personnel_pages.py`
  - `web/routes/equipment_excel_machines.py`
  - `web/routes/equipment_excel_links.py`
  - `web/routes/personnel_excel_operators.py`
  - `web/routes/personnel_excel_links.py`
  - `web/routes/personnel_calendar_pages.py`
  - `templates/equipment/list.html`
  - `templates/personnel/calendar.html`
  - `templates/process/detail.html`
  - `templates/process/list.html`
  - `templates/scheduler/batches.html`
  - `templates/scheduler/batches_manage.html`
  - `templates/scheduler/calendar.html`
  - `templates/scheduler/excel_import_batches.html`
  - `static/js/config_manual.js`
  - `check_manual_layout.py`
  - `verify_manual_styles.py`
  - `web_new_test/templates/base.html`
  - `tests/test_architecture_fitness.py`
  - `tests/test_team_pages_excel_smoke.py`
  - `tests/regression_config_manual_markdown.py`

## 评审里程碑

### m1_reverify_fixed_issues · 历史已知问题复核与回归契约校验

- 状态: 已完成
- 记录时间: 2026-04-05T03:52:05.995Z
- 已审模块: scheduler.batch_excel, scheduler.batch_service, common.excel_validators, scheduler.schedule_persistence, scheduler.routes, ui_mode, team_pages, batch_detail_linkage
- 摘要:

  本阶段先按上一轮遗留清单做回归复核，重点核对三类高风险问题是否真正收口，并补查若干相关契约回归。

  结论：上一轮明确挂起的三项问题在当前未提交树上均已看到有效收口迹象，且都有对应回归约束，不再按开放问题继续追踪：
  - 批次 Excel 导入告警已统一走限量展示链路，批量模板回填后的用户可见告警不再无上限刷屏；
  - `BatchService.update()` 直接改零件号但未重建工序的回归缺口已补上，当前测试直接锁定服务层入口；
  - 操作员工日历导入的有限数字解析已统一到单一严格解析入口，`True/False/NaN/±Inf` 等脏值会被显式拒绝。

  同时复核的相关契约也保持一致：
  - 排产配置兼容 `dict`/对象双形态；
  - `enforce_ready` 三态语义与 `strict_mode` 解析分离；
  - 排产持久化仅写入可落库/可重排结果；
  - 班组页面与批次详情联动的关键界面契约已有测试锁定。

  本里程碑未发现新的开放 BUG。
- 结论:

  上一轮三项已知问题在当前未提交实现中均可视为已修复，且相关回归契约已补齐。
- 证据:
  - `web/routes/scheduler_excel_batches.py`
  - `web/routes/scheduler_batches.py`
  - `core/services/scheduler/batch_excel_import.py`
  - `core/services/common/excel_validators.py`
  - `tests/regression_scheduler_batch_template_warning_surface.py`
  - `tests/regression_batch_service_update_reject_part_change_without_rebuild.py`
  - `tests/test_excel_import_hardening.py`
  - `tests/regression_calendar_no_tx_hardening.py`
  - `tests/regression_dict_cfg_contract.py`
  - `tests/regression_auto_assign_persist_truthy_variants.py`
  - `tests/regression_scheduler_route_enforce_ready_tristate.py`
  - `tests/test_ui_mode.py`
  - `tests/test_team_pages_excel_smoke.py`
  - `tests/regression_batch_detail_linkage.py`
- 下一步建议:

  继续深挖算法/优化/汇总主链路，重点排查剩余的静默回退与可观测性偏差。

### m2_scheduler_core · 排产核心链路深挖（配置/优化/汇总/持久化）

- 状态: 已完成
- 记录时间: 2026-04-05T03:52:29.357Z
- 已审模块: scheduler.config, scheduler.optimizer, scheduler.orchestrator, scheduler.persistence, scheduler.summary, greedy.scheduler, greedy.auto_assign, greedy.dispatch.sgs
- 摘要:

  本阶段继续深挖排产核心主链路，覆盖 `config_service` / `config_snapshot` / `config_validator`、`schedule_optimizer` / `schedule_optimizer_steps`、`schedule_orchestrator` / `schedule_service` / `schedule_persistence`、`schedule_summary`，以及算法侧 `GreedyScheduler`、`auto_assign`、`dispatch.sgs`。

  确认结果：
  - 配置数值严格解析、摘要 1.1 契约、摘要截断、停机退化与冻结退化留痕总体是自洽的；
  - `auto_assign_persist` 在配置缺省时按 `yes` 处理，当前更像兼容既有回写语义，而不是新的误回退；
  - 可落库结果过滤、版本分配时机、摘要组装与 warning 合并链路整体已收口。

  但本阶段识别出一个仍然开放的问题：SGS 评分阶段直接调用自动分配逻辑进行“探测式选人选机”，而自动分配函数本身会修改算法统计计数。这样一来，只要候选在评分阶段被多次探测，`fallback_counts` 就会累计“探测次数”而不是“真实排产失败次数”，最终又会被汇总进排产摘要，导致可观测性口径失真。
- 结论:

  核心排产链路的大部分契约已经比上一轮更稳，但 `sgs` 与自动分配联动处仍有一处统计口径污染，属于需要修复的开放问题。
- 证据:
  - `core/algorithms/greedy/dispatch/sgs.py:216-248`
  - `core/algorithms/greedy/auto_assign.py:45-109`
  - `core/algorithms/greedy/auto_assign.py:221-225`
  - `core/services/scheduler/schedule_summary.py:415-416`
  - `core/services/scheduler/schedule_summary.py:465-466`
  - `core/services/scheduler/config_service.py`
  - `core/services/scheduler/config_snapshot.py`
  - `core/services/scheduler/config_validator.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_persistence.py`
  - `core/services/scheduler/schedule_summary.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `tests/regression_schedule_summary_v11_contract.py`
  - `tests/regression_auto_assign_persist_truthy_variants.py`
  - `tests/regression_schedule_service_passes_algo_stats_to_summary.py`
  - `tests/regression_sgs_scoring_fallback_unscorable.py`
  - `tests/regression_sgs_penalize_nonfinite_proc_hours.py`
- 下一步建议:

  继续转到系统路由、UI 兼容层与测试质量，重点核对是否还有会掩盖真实问题的静默回退。
- 问题:
  - [中] 其他: SGS 探测式自动分配污染统计计数

### m3_ui_routes_tests · 系统路由、UI 兼容层、模板与测试交叉审查

- 状态: 已完成
- 记录时间: 2026-04-05T03:52:52.700Z
- 已审模块: system.backup, system.history, ui_mode, templates.base, templates.components.excel_import, test.template_endpoint_scan
- 摘要:

  本阶段补审 `system_backup`、`system_history`、`ui_mode`、`base.html`、通用 Excel 导入组件，以及相关回归测试。

  结论分层如下：
  - `system_backup` 的恢复流程已经把“复制完成待校验”“校验失败自动回滚”“成功后独立留痕”三段语义拆开，主流程比旧实现更清晰；
  - `system_history` 对摘要解析失败会保留原文展示，不会因为坏 JSON 直接打崩页面；
  - `base.html` 与通用 Excel 导入组件的关键界面契约没有看到新的明显逻辑错误。

  需要单独指出的是：
  - `web/ui_mode.py` 仍保留较多宽泛回退分支，但本轮核对后，大部分属于兼容边界而非直接 BUG；其中 `v2_env` 缺失时至少会一次性告警并显式标记 `v1_fallback`，当前先作为低风险接受；
  - 但测试质量上仍有一个开放问题：`regression_template_urlfor_endpoints.py` 自称允许 `safe_url_for(...)` 指向未注册端点，可其 `url_for(...)` 提取正则会同时命中 `safe_url_for(...)`，导致“可选链接”仍会被当作“强制链接”去失败，测试契约与实现不一致。
- 结论:

  系统路由与模板本身未见新的高风险逻辑错误，但测试层仍有一处会误报的端点扫描问题，需要修正。
- 证据:
  - `web/ui_mode.py:182-195`
  - `web/ui_mode.py:259-295`
  - `tests/regression_template_urlfor_endpoints.py:9-15`
  - `tests/regression_template_urlfor_endpoints.py:60-61`
  - `tests/regression_template_urlfor_endpoints.py:74-82`
  - `tests/regression_template_urlfor_endpoints.py:112-129`
  - `web/routes/system_backup.py`
  - `web/routes/system_history.py`
  - `web/ui_mode.py`
  - `templates/base.html`
  - `templates/components/excel_import.html`
  - `tests/test_ui_mode.py`
  - `tests/regression_template_urlfor_endpoints.py`
  - `tests/regression_backup_restore_pending_verify_code.py`
- 下一步建议:

  如需收口本轮 review，可在修复上述两个开放问题后做一次针对性回归，再决定是否 finalize。
- 问题:
  - [中] 测试: 端点扫描回归把 safe_url_for 当成强制 url_for

### m4_process_calendar_excel · 过程服务与工作日历 Excel 链路补审

- 状态: 已完成
- 记录时间: 2026-04-05T04:10:18.500Z
- 已审模块: process.route_parser, process.part_service, process.external_group_service, process.supplier_service, process.excel_routes, process.excel_part_operation_hours, process.excel_suppliers, process.parts_route, scheduler.calendar_admin, scheduler.calendar_routes, scheduler.excel_calendar, common.excel_utils
- 摘要:

  本阶段补审了当前未提交改动里尚未细看的过程服务与工作日历链路，覆盖 `core/services/process/route_parser.py`、`part_service.py`、`external_group_service.py`、`supplier_service.py`，以及 `web/routes/process_excel_routes.py`、`process_excel_part_operation_hours.py`、`process_excel_suppliers.py`、`process_parts.py`、`scheduler_calendar_pages.py`、`scheduler_excel_calendar.py`、`core/services/scheduler/calendar_admin.py`、`web/routes/excel_utils.py` 与相关回归脚本。

  正向结论：
  - `route_parser` / `part_service` / `external_group_service` 的严格模式语义基本自洽：未知工种、缺供应商映射、外协周期空值等都会在严格模式下显式失败，不再静默落库；
  - `part_service.reparse_and_save()` 仍能保留既有内部工时，相关回归覆盖存在；
  - 工作日历页面与 Excel 页面对 `holiday_default_efficiency` 非法值都给出了可见告警或拒绝导入，兼容边界比旧实现清晰。

  新发现的问题在于：多个路由层 Excel 预览/确认校验重新实现了各自的数字解析，没有复用服务层已经存在的严格解析约束，导致预览/确认契约重新漂移：
  - `web/routes/scheduler_excel_calendar.py` 直接用 `float(...)` 校验“可用工时/效率”，会把 `True`、`NaN`、`Inf` 之类值放过预览，但真正写库时 `CalendarAdmin` 又会拒绝，从而把问题延后到确认执行阶段；
  - `web/routes/process_excel_part_operation_hours.py::_parse_seq()` 会把 `True` 和 `"5e0"` 解析成合法工序号，绕过了 `PartOperationHoursExcelImportService._coerce_int()` 已明确加上的防御；
  - `web/routes/process_excel_suppliers.py::_normalize_supplier_default_days()` 会把 `True` 当成 `1.0`，与 `SupplierService` 通过 `parse_required_float()` 拒绝布尔值的契约不一致。

  此外，顺带复核了当前版本的 `core/algorithms/greedy/dispatch/sgs.py` / `auto_assign.py` / `schedule_summary.py`，之前的开放问题 `sgs-auto-assign-probe-counter-inflation` 仍然存在，最新改动尚未收口。
- 结论:

  过程服务与工作日历主链路整体更清楚，但路由层 Excel 数值校验重新出现多源实现，已经形成真实 BUG 风险，当前不宜直接收口。
- 证据:
  - `web/routes/scheduler_excel_calendar.py:197-220#validate_row`
  - `web/routes/scheduler_excel_calendar.py:331-353#validate_row`
  - `core/services/scheduler/calendar_admin.py:60-62#_normalize_float`
  - `core/services/scheduler/calendar_admin.py:138-147#_build_work_calendar`
  - `web/routes/process_excel_part_operation_hours.py:46-64#_parse_seq`
  - `web/routes/process_excel_part_operation_hours.py:125-129#_validate_row`
  - `core/services/process/part_operation_hours_excel_import_service.py:111-129#_coerce_int`
  - `web/routes/process_excel_suppliers.py:89-100#_normalize_supplier_default_days`
  - `core/services/process/supplier_service.py:29-36#_normalize_default_days`
  - `core/services/common/strict_parse.py:32-64#parse_required_float`
  - `tests/test_part_operation_hours_import_apply_defense.py:13-29#test_parse_write_row_accepts_integer_float_string_forms`
  - `tests/regression_calendar_no_tx_hardening.py:240-252#main`
  - `core/algorithms/greedy/dispatch/sgs.py:216-248#dispatch_sgs`
  - `core/algorithms/greedy/auto_assign.py:45-109#auto_assign_internal_resources`
  - `core/services/scheduler/schedule_summary.py:415-466#build_result_summary`
  - `core/services/process/route_parser.py`
  - `core/services/process/part_service.py`
  - `core/services/process/external_group_service.py`
  - `core/services/process/supplier_service.py`
  - `web/routes/process_excel_routes.py`
  - `web/routes/process_excel_part_operation_hours.py`
  - `web/routes/process_excel_suppliers.py`
  - `web/routes/process_parts.py`
  - `web/routes/scheduler_calendar_pages.py`
  - `web/routes/scheduler_excel_calendar.py`
  - `core/services/scheduler/calendar_admin.py`
  - `web/routes/excel_utils.py`
  - `core/services/process/part_operation_hours_excel_import_service.py`
  - `core/services/common/strict_parse.py`
  - `tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py`
  - `tests/regression_external_group_service_strict_mode_blank_days.py`
  - `tests/regression_supplier_service_invalid_default_days_not_silent.py`
  - `tests/regression_process_reparse_preserve_internal_hours.py`
  - `tests/regression_process_suppliers_route_reject_blank_default_days.py`
  - `tests/regression_calendar_no_tx_hardening.py`
  - `tests/regression_scheduler_excel_calendar_uses_executor.py`
  - `tests/test_part_operation_hours_import_apply_defense.py`
- 下一步建议:

  先统一 Excel 路由层的数字解析入口并补齐路由级回归，再继续看剩余 UI/工具链改动是否可以收口。
- 问题:
  - [中] 其他: Excel 路由数值校验与服务契约漂移

### m5_ui_tooling_guardrails · 列表页/UI 工具链与测试护栏补审

- 状态: 已完成
- 记录时间: 2026-04-05T04:11:05.335Z
- 已审模块: dashboard, equipment.pages, equipment.excel_machines, equipment.excel_links, personnel.pages, personnel.excel_operators, personnel.excel_links, personnel.calendar_pages, templates.equipment.list, templates.personnel.calendar, templates.process.detail, templates.process.list, templates.scheduler.batches, templates.scheduler.batches_manage, templates.scheduler.calendar, templates.scheduler.excel_batches, config_manual, manual_layout_tooling, test.architecture_fitness, web_new_test.base
- 摘要:

  本阶段补审了本轮新改动中的列表页、Excel 辅助页面、说明书脚本与测试护栏，覆盖 `web/routes/dashboard.py`、`equipment_pages.py`、`personnel_pages.py`、`equipment_excel_machines.py`、`equipment_excel_links.py`、`personnel_excel_operators.py`、`personnel_excel_links.py`、`personnel_calendar_pages.py`、`static/js/config_manual.js`、`check_manual_layout.py`、`verify_manual_styles.py`、`tests/test_architecture_fitness.py`、`tests/test_team_pages_excel_smoke.py`、`tests/regression_config_manual_markdown.py`，以及对应模板 `templates/equipment/list.html`、`templates/personnel/calendar.html`、`templates/process/detail.html`、`templates/process/list.html`、`templates/scheduler/batches.html`、`templates/scheduler/batches_manage.html`、`templates/scheduler/calendar.html`、`templates/scheduler/excel_import_batches.html`、`web_new_test/templates/base.html`。

  正向结论：
  - 设备/人员列表、班组筛选、批量操作和停机覆盖告警的界面契约基本一致，和 `test_team_pages_excel_smoke.py` 的断言能对上；
  - `config_manual.js` 现在优先按 `getElementById(hashId)` 处理数字开头锚点，再回退 `querySelector`，结合 `regression_config_manual_markdown.py`、`check_manual_layout.py`、`verify_manual_styles.py`，说明书页面的可用性与布局验证链路比之前完整；
  - `dashboard.py` 对坏 `result_summary` 的处理是显式 warning + 安全降级，不属于静默吞错；
  - `web_new_test/templates/base.html` 的界面模式切换、主题与表格密度控制没有看到新的高风险逻辑错误。

  本阶段真正需要记账的是测试护栏退化：`tests/test_architecture_fitness.py::test_no_silent_exception_swallow()` 虽然表面上还保留 `known_violations`，但后续不再核对这些 allowlist 的具体位置，只把它们压平成 `known_counts`，最后仅按“同文件吞异常点数量是否增加”做判定。这样一来，只要在同一个文件里删掉一个旧的 `except Exception: pass`，再新增一个新的静默吞错点，测试依然会通过；也就是说，原本针对具体位置的保护已经被降级成粗粒度计数保护，和当前代码库里大量兼容性回退分支并存时，风险会被进一步放大。

  另外，顺带复核了 `tests/regression_template_urlfor_endpoints.py` 当前版本，`url_for\(` 仍会命中 `safe_url_for(`，该历史开放问题本阶段未见收口；不过它并不来自本轮新增文件，因此这里不重复记账。
- 结论:

  UI 与说明书工具链改动整体可接受，但测试护栏本身被削弱了一层，当前 review 仍不建议 finalize。
- 证据:
  - `static/js/config_manual.js:519-548#initManual`
  - `tests/regression_config_manual_markdown.py:59-257#_run_hash_runtime_check`
  - `check_manual_layout.py:92-119#check_layout_via_styles`
  - `verify_manual_styles.py:57-125#main`
  - `web/routes/equipment_pages.py:62-69#_load_active_downtime_machine_ids`
  - `templates/equipment/list.html:64-73`
  - `web/routes/personnel_calendar_pages.py:14-27#_resolve_page_holiday_default_efficiency`
  - `templates/personnel/calendar.html:41-45`
  - `web/routes/dashboard.py:27-54#index`
  - `tests/test_architecture_fitness.py:391-551#test_no_silent_exception_swallow`
  - `web/routes/dashboard.py`
  - `web/routes/equipment_pages.py`
  - `web/routes/personnel_pages.py`
  - `web/routes/equipment_excel_machines.py`
  - `web/routes/equipment_excel_links.py`
  - `web/routes/personnel_excel_operators.py`
  - `web/routes/personnel_excel_links.py`
  - `web/routes/personnel_calendar_pages.py`
  - `templates/equipment/list.html`
  - `templates/personnel/calendar.html`
  - `templates/process/detail.html`
  - `templates/process/list.html`
  - `templates/scheduler/batches.html`
  - `templates/scheduler/batches_manage.html`
  - `templates/scheduler/calendar.html`
  - `templates/scheduler/excel_import_batches.html`
  - `static/js/config_manual.js`
  - `check_manual_layout.py`
  - `verify_manual_styles.py`
  - `web_new_test/templates/base.html`
  - `tests/test_architecture_fitness.py`
  - `tests/test_team_pages_excel_smoke.py`
  - `tests/regression_config_manual_markdown.py`
- 下一步建议:

  在修复 Excel 路由数值契约漂移和测试护栏退化后，再决定是否把本轮 review finalize；当前不建议直接接受。
- 问题:
  - [中] 测试: 静默吞异常护栏退化为按文件计数

## 最终结论

当前未提交改动相较上一轮已经明显收口：历史已知的批次告警限量展示、`BatchService.update()` 直接改零件号回归缺口、以及人员专属日历有限数字解析分叉问题都已看到有效修复；多数过程服务、列表页、说明书脚本与模板契约也基本清楚，没有再发现新的高危破坏性错误。

但从“逻辑严谨、避免过度兜底、保持契约单一来源”的标准看，本轮仍不能直接接受。当前至少还有 4 个中等问题未收口：
1. `excel-route-strict-numeric-drift`：多个 Excel 路由重新手写数字解析，已经和服务层严格契约漂移，存在预览放过脏值、确认阶段才失败，甚至写错主键的真实 BUG 风险；
2. `sgs-auto-assign-probe-counter-inflation`：当前改动后的 `sgs` / `auto_assign` / `schedule_summary` 仍会把评分探测次数污染进最终统计，影响可观测性和审计口径；
3. `silent-swallow-fitness-count-only-whitelist`：`test_no_silent_exception_swallow` 从位置约束退化成文件计数上限，削弱了后续识别新增静默吞错的能力；
4. `template-urlfor-regex-overmatches-safe-url-for`：历史测试误报问题仍未收口。

综合判断：本轮代码大方向基本对，但还没有达到可以安心收口的程度，建议先修完上述问题再做一次针对当前 `.git/modified_list.txt` 的定向回归。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnl7lfc9-wpjwit",
  "createdAt": "2026-04-05T00:00:00.000Z",
  "updatedAt": "2026-04-05T04:12:04.184Z",
  "finalizedAt": "2026-04-05T04:12:04.184Z",
  "status": "completed",
  "overallDecision": "needs_follow_up",
  "header": {
    "title": "未提交修改三轮深度review",
    "date": "2026-04-05",
    "overview": "针对当前工作区未提交修改进行三轮增量审查，关注目的达成、实现简洁性、兜底/静默回退以及潜在BUG。"
  },
  "scope": {
    "markdown": "# 未提交修改三轮深度review\n\n- 日期：2026-04-05\n- 范围：当前工作区 `.git/modified_list.txt` 中列出的未提交修改\n- 方法：按三轮进行，先做改动清单与风险分层，再做核心服务/算法链路深挖，最后做路由/模板/测试与一致性交叉审查\n- 关注点：是否达成目的、实现是否优雅简洁、是否存在过度兜底或静默回退、逻辑是否严谨、是否仍有BUG\n\n## 初始判断\n\n待审文件覆盖算法、排产服务、Excel 导入、路由、模板与测试，属于跨层联动改动，风险较高。优先关注：\n1. 数值解析与严格模式语义是否在各层保持一致；\n2. 批次导入与模板回填链路是否引入隐藏兜底；\n3. 排产结果持久化/汇总是否因契约调整出现边界退化；\n4. 路由层是否把服务层异常重新静默吞掉；\n5. 测试是否真正覆盖新增分支，而不是仅固化当前实现。"
  },
  "summary": {
    "latestConclusion": "当前未提交改动相较上一轮已经明显收口：历史已知的批次告警限量展示、`BatchService.update()` 直接改零件号回归缺口、以及人员专属日历有限数字解析分叉问题都已看到有效修复；多数过程服务、列表页、说明书脚本与模板契约也基本清楚，没有再发现新的高危破坏性错误。\n\n但从“逻辑严谨、避免过度兜底、保持契约单一来源”的标准看，本轮仍不能直接接受。当前至少还有 4 个中等问题未收口：\n1. `excel-route-strict-numeric-drift`：多个 Excel 路由重新手写数字解析，已经和服务层严格契约漂移，存在预览放过脏值、确认阶段才失败，甚至写错主键的真实 BUG 风险；\n2. `sgs-auto-assign-probe-counter-inflation`：当前改动后的 `sgs` / `auto_assign` / `schedule_summary` 仍会把评分探测次数污染进最终统计，影响可观测性和审计口径；\n3. `silent-swallow-fitness-count-only-whitelist`：`test_no_silent_exception_swallow` 从位置约束退化成文件计数上限，削弱了后续识别新增静默吞错的能力；\n4. `template-urlfor-regex-overmatches-safe-url-for`：历史测试误报问题仍未收口。\n\n综合判断：本轮代码大方向基本对，但还没有达到可以安心收口的程度，建议先修完上述问题再做一次针对当前 `.git/modified_list.txt` 的定向回归。",
    "recommendedNextAction": "优先修复 `excel-route-strict-numeric-drift`、`sgs-auto-assign-probe-counter-inflation`、`silent-swallow-fitness-count-only-whitelist`；如仍保留模板端点扫描回归，再同时修正 `template-urlfor-regex-overmatches-safe-url-for`。完成后，针对当前 `.git/modified_list.txt` 重新跑一轮定向回归再决定是否接受。",
    "reviewedModules": [
      "scheduler.batch_excel",
      "scheduler.batch_service",
      "common.excel_validators",
      "scheduler.schedule_persistence",
      "scheduler.routes",
      "ui_mode",
      "team_pages",
      "batch_detail_linkage",
      "scheduler.config",
      "scheduler.optimizer",
      "scheduler.orchestrator",
      "scheduler.persistence",
      "scheduler.summary",
      "greedy.scheduler",
      "greedy.auto_assign",
      "greedy.dispatch.sgs",
      "system.backup",
      "system.history",
      "templates.base",
      "templates.components.excel_import",
      "test.template_endpoint_scan",
      "process.route_parser",
      "process.part_service",
      "process.external_group_service",
      "process.supplier_service",
      "process.excel_routes",
      "process.excel_part_operation_hours",
      "process.excel_suppliers",
      "process.parts_route",
      "scheduler.calendar_admin",
      "scheduler.calendar_routes",
      "scheduler.excel_calendar",
      "common.excel_utils",
      "dashboard",
      "equipment.pages",
      "equipment.excel_machines",
      "equipment.excel_links",
      "personnel.pages",
      "personnel.excel_operators",
      "personnel.excel_links",
      "personnel.calendar_pages",
      "templates.equipment.list",
      "templates.personnel.calendar",
      "templates.process.detail",
      "templates.process.list",
      "templates.scheduler.batches",
      "templates.scheduler.batches_manage",
      "templates.scheduler.calendar",
      "templates.scheduler.excel_batches",
      "config_manual",
      "manual_layout_tooling",
      "test.architecture_fitness",
      "web_new_test.base"
    ]
  },
  "stats": {
    "totalMilestones": 5,
    "completedMilestones": 5,
    "totalFindings": 4,
    "severity": {
      "high": 0,
      "medium": 4,
      "low": 0
    }
  },
  "milestones": [
    {
      "id": "m1_reverify_fixed_issues",
      "title": "历史已知问题复核与回归契约校验",
      "status": "completed",
      "recordedAt": "2026-04-05T03:52:05.995Z",
      "summaryMarkdown": "本阶段先按上一轮遗留清单做回归复核，重点核对三类高风险问题是否真正收口，并补查若干相关契约回归。\n\n结论：上一轮明确挂起的三项问题在当前未提交树上均已看到有效收口迹象，且都有对应回归约束，不再按开放问题继续追踪：\n- 批次 Excel 导入告警已统一走限量展示链路，批量模板回填后的用户可见告警不再无上限刷屏；\n- `BatchService.update()` 直接改零件号但未重建工序的回归缺口已补上，当前测试直接锁定服务层入口；\n- 操作员工日历导入的有限数字解析已统一到单一严格解析入口，`True/False/NaN/±Inf` 等脏值会被显式拒绝。\n\n同时复核的相关契约也保持一致：\n- 排产配置兼容 `dict`/对象双形态；\n- `enforce_ready` 三态语义与 `strict_mode` 解析分离；\n- 排产持久化仅写入可落库/可重排结果；\n- 班组页面与批次详情联动的关键界面契约已有测试锁定。\n\n本里程碑未发现新的开放 BUG。",
      "conclusionMarkdown": "上一轮三项已知问题在当前未提交实现中均可视为已修复，且相关回归契约已补齐。",
      "evidence": [
        {
          "path": "web/routes/scheduler_excel_batches.py"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        },
        {
          "path": "core/services/scheduler/batch_excel_import.py"
        },
        {
          "path": "core/services/common/excel_validators.py"
        },
        {
          "path": "tests/regression_scheduler_batch_template_warning_surface.py"
        },
        {
          "path": "tests/regression_batch_service_update_reject_part_change_without_rebuild.py"
        },
        {
          "path": "tests/test_excel_import_hardening.py"
        },
        {
          "path": "tests/regression_calendar_no_tx_hardening.py"
        },
        {
          "path": "tests/regression_dict_cfg_contract.py"
        },
        {
          "path": "tests/regression_auto_assign_persist_truthy_variants.py"
        },
        {
          "path": "tests/regression_scheduler_route_enforce_ready_tristate.py"
        },
        {
          "path": "tests/test_ui_mode.py"
        },
        {
          "path": "tests/test_team_pages_excel_smoke.py"
        },
        {
          "path": "tests/regression_batch_detail_linkage.py"
        }
      ],
      "reviewedModules": [
        "scheduler.batch_excel",
        "scheduler.batch_service",
        "common.excel_validators",
        "scheduler.schedule_persistence",
        "scheduler.routes",
        "ui_mode",
        "team_pages",
        "batch_detail_linkage"
      ],
      "recommendedNextAction": "继续深挖算法/优化/汇总主链路，重点排查剩余的静默回退与可观测性偏差。",
      "findingIds": []
    },
    {
      "id": "m2_scheduler_core",
      "title": "排产核心链路深挖（配置/优化/汇总/持久化）",
      "status": "completed",
      "recordedAt": "2026-04-05T03:52:29.357Z",
      "summaryMarkdown": "本阶段继续深挖排产核心主链路，覆盖 `config_service` / `config_snapshot` / `config_validator`、`schedule_optimizer` / `schedule_optimizer_steps`、`schedule_orchestrator` / `schedule_service` / `schedule_persistence`、`schedule_summary`，以及算法侧 `GreedyScheduler`、`auto_assign`、`dispatch.sgs`。\n\n确认结果：\n- 配置数值严格解析、摘要 1.1 契约、摘要截断、停机退化与冻结退化留痕总体是自洽的；\n- `auto_assign_persist` 在配置缺省时按 `yes` 处理，当前更像兼容既有回写语义，而不是新的误回退；\n- 可落库结果过滤、版本分配时机、摘要组装与 warning 合并链路整体已收口。\n\n但本阶段识别出一个仍然开放的问题：SGS 评分阶段直接调用自动分配逻辑进行“探测式选人选机”，而自动分配函数本身会修改算法统计计数。这样一来，只要候选在评分阶段被多次探测，`fallback_counts` 就会累计“探测次数”而不是“真实排产失败次数”，最终又会被汇总进排产摘要，导致可观测性口径失真。",
      "conclusionMarkdown": "核心排产链路的大部分契约已经比上一轮更稳，但 `sgs` 与自动分配联动处仍有一处统计口径污染，属于需要修复的开放问题。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 216,
          "lineEnd": 248
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 45,
          "lineEnd": 109
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 221,
          "lineEnd": 225
        },
        {
          "path": "core/services/scheduler/schedule_summary.py",
          "lineStart": 415,
          "lineEnd": 416
        },
        {
          "path": "core/services/scheduler/schedule_summary.py",
          "lineStart": 465,
          "lineEnd": 466
        },
        {
          "path": "core/services/scheduler/config_service.py"
        },
        {
          "path": "core/services/scheduler/config_snapshot.py"
        },
        {
          "path": "core/services/scheduler/config_validator.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_persistence.py"
        },
        {
          "path": "core/services/scheduler/schedule_summary.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "tests/regression_schedule_summary_v11_contract.py"
        },
        {
          "path": "tests/regression_auto_assign_persist_truthy_variants.py"
        },
        {
          "path": "tests/regression_schedule_service_passes_algo_stats_to_summary.py"
        },
        {
          "path": "tests/regression_sgs_scoring_fallback_unscorable.py"
        },
        {
          "path": "tests/regression_sgs_penalize_nonfinite_proc_hours.py"
        }
      ],
      "reviewedModules": [
        "scheduler.config",
        "scheduler.optimizer",
        "scheduler.orchestrator",
        "scheduler.persistence",
        "scheduler.summary",
        "greedy.scheduler",
        "greedy.auto_assign",
        "greedy.dispatch.sgs"
      ],
      "recommendedNextAction": "继续转到系统路由、UI 兼容层与测试质量，重点核对是否还有会掩盖真实问题的静默回退。",
      "findingIds": [
        "sgs-auto-assign-probe-counter-inflation"
      ]
    },
    {
      "id": "m3_ui_routes_tests",
      "title": "系统路由、UI 兼容层、模板与测试交叉审查",
      "status": "completed",
      "recordedAt": "2026-04-05T03:52:52.700Z",
      "summaryMarkdown": "本阶段补审 `system_backup`、`system_history`、`ui_mode`、`base.html`、通用 Excel 导入组件，以及相关回归测试。\n\n结论分层如下：\n- `system_backup` 的恢复流程已经把“复制完成待校验”“校验失败自动回滚”“成功后独立留痕”三段语义拆开，主流程比旧实现更清晰；\n- `system_history` 对摘要解析失败会保留原文展示，不会因为坏 JSON 直接打崩页面；\n- `base.html` 与通用 Excel 导入组件的关键界面契约没有看到新的明显逻辑错误。\n\n需要单独指出的是：\n- `web/ui_mode.py` 仍保留较多宽泛回退分支，但本轮核对后，大部分属于兼容边界而非直接 BUG；其中 `v2_env` 缺失时至少会一次性告警并显式标记 `v1_fallback`，当前先作为低风险接受；\n- 但测试质量上仍有一个开放问题：`regression_template_urlfor_endpoints.py` 自称允许 `safe_url_for(...)` 指向未注册端点，可其 `url_for(...)` 提取正则会同时命中 `safe_url_for(...)`，导致“可选链接”仍会被当作“强制链接”去失败，测试契约与实现不一致。",
      "conclusionMarkdown": "系统路由与模板本身未见新的高风险逻辑错误，但测试层仍有一处会误报的端点扫描问题，需要修正。",
      "evidence": [
        {
          "path": "web/ui_mode.py",
          "lineStart": 182,
          "lineEnd": 195
        },
        {
          "path": "web/ui_mode.py",
          "lineStart": 259,
          "lineEnd": 295
        },
        {
          "path": "tests/regression_template_urlfor_endpoints.py",
          "lineStart": 9,
          "lineEnd": 15
        },
        {
          "path": "tests/regression_template_urlfor_endpoints.py",
          "lineStart": 60,
          "lineEnd": 61
        },
        {
          "path": "tests/regression_template_urlfor_endpoints.py",
          "lineStart": 74,
          "lineEnd": 82
        },
        {
          "path": "tests/regression_template_urlfor_endpoints.py",
          "lineStart": 112,
          "lineEnd": 129
        },
        {
          "path": "web/routes/system_backup.py"
        },
        {
          "path": "web/routes/system_history.py"
        },
        {
          "path": "web/ui_mode.py"
        },
        {
          "path": "templates/base.html"
        },
        {
          "path": "templates/components/excel_import.html"
        },
        {
          "path": "tests/test_ui_mode.py"
        },
        {
          "path": "tests/regression_template_urlfor_endpoints.py"
        },
        {
          "path": "tests/regression_backup_restore_pending_verify_code.py"
        }
      ],
      "reviewedModules": [
        "system.backup",
        "system.history",
        "ui_mode",
        "templates.base",
        "templates.components.excel_import",
        "test.template_endpoint_scan"
      ],
      "recommendedNextAction": "如需收口本轮 review，可在修复上述两个开放问题后做一次针对性回归，再决定是否 finalize。",
      "findingIds": [
        "template-urlfor-regex-overmatches-safe-url-for"
      ]
    },
    {
      "id": "m4_process_calendar_excel",
      "title": "过程服务与工作日历 Excel 链路补审",
      "status": "completed",
      "recordedAt": "2026-04-05T04:10:18.500Z",
      "summaryMarkdown": "本阶段补审了当前未提交改动里尚未细看的过程服务与工作日历链路，覆盖 `core/services/process/route_parser.py`、`part_service.py`、`external_group_service.py`、`supplier_service.py`，以及 `web/routes/process_excel_routes.py`、`process_excel_part_operation_hours.py`、`process_excel_suppliers.py`、`process_parts.py`、`scheduler_calendar_pages.py`、`scheduler_excel_calendar.py`、`core/services/scheduler/calendar_admin.py`、`web/routes/excel_utils.py` 与相关回归脚本。\n\n正向结论：\n- `route_parser` / `part_service` / `external_group_service` 的严格模式语义基本自洽：未知工种、缺供应商映射、外协周期空值等都会在严格模式下显式失败，不再静默落库；\n- `part_service.reparse_and_save()` 仍能保留既有内部工时，相关回归覆盖存在；\n- 工作日历页面与 Excel 页面对 `holiday_default_efficiency` 非法值都给出了可见告警或拒绝导入，兼容边界比旧实现清晰。\n\n新发现的问题在于：多个路由层 Excel 预览/确认校验重新实现了各自的数字解析，没有复用服务层已经存在的严格解析约束，导致预览/确认契约重新漂移：\n- `web/routes/scheduler_excel_calendar.py` 直接用 `float(...)` 校验“可用工时/效率”，会把 `True`、`NaN`、`Inf` 之类值放过预览，但真正写库时 `CalendarAdmin` 又会拒绝，从而把问题延后到确认执行阶段；\n- `web/routes/process_excel_part_operation_hours.py::_parse_seq()` 会把 `True` 和 `\"5e0\"` 解析成合法工序号，绕过了 `PartOperationHoursExcelImportService._coerce_int()` 已明确加上的防御；\n- `web/routes/process_excel_suppliers.py::_normalize_supplier_default_days()` 会把 `True` 当成 `1.0`，与 `SupplierService` 通过 `parse_required_float()` 拒绝布尔值的契约不一致。\n\n此外，顺带复核了当前版本的 `core/algorithms/greedy/dispatch/sgs.py` / `auto_assign.py` / `schedule_summary.py`，之前的开放问题 `sgs-auto-assign-probe-counter-inflation` 仍然存在，最新改动尚未收口。",
      "conclusionMarkdown": "过程服务与工作日历主链路整体更清楚，但路由层 Excel 数值校验重新出现多源实现，已经形成真实 BUG 风险，当前不宜直接收口。",
      "evidence": [
        {
          "path": "web/routes/scheduler_excel_calendar.py",
          "lineStart": 197,
          "lineEnd": 220,
          "symbol": "validate_row",
          "excerptHash": "m4-cal-validate-1"
        },
        {
          "path": "web/routes/scheduler_excel_calendar.py",
          "lineStart": 331,
          "lineEnd": 353,
          "symbol": "validate_row",
          "excerptHash": "m4-cal-validate-2"
        },
        {
          "path": "core/services/scheduler/calendar_admin.py",
          "lineStart": 60,
          "lineEnd": 62,
          "symbol": "_normalize_float",
          "excerptHash": "m4-cal-admin-parse"
        },
        {
          "path": "core/services/scheduler/calendar_admin.py",
          "lineStart": 138,
          "lineEnd": 147,
          "symbol": "_build_work_calendar",
          "excerptHash": "m4-cal-admin-build"
        },
        {
          "path": "web/routes/process_excel_part_operation_hours.py",
          "lineStart": 46,
          "lineEnd": 64,
          "symbol": "_parse_seq",
          "excerptHash": "m4-part-hours-seq"
        },
        {
          "path": "web/routes/process_excel_part_operation_hours.py",
          "lineStart": 125,
          "lineEnd": 129,
          "symbol": "_validate_row",
          "excerptHash": "m4-part-hours-validate"
        },
        {
          "path": "core/services/process/part_operation_hours_excel_import_service.py",
          "lineStart": 111,
          "lineEnd": 129,
          "symbol": "_coerce_int",
          "excerptHash": "m4-part-hours-service"
        },
        {
          "path": "web/routes/process_excel_suppliers.py",
          "lineStart": 89,
          "lineEnd": 100,
          "symbol": "_normalize_supplier_default_days",
          "excerptHash": "m4-supplier-route-days"
        },
        {
          "path": "core/services/process/supplier_service.py",
          "lineStart": 29,
          "lineEnd": 36,
          "symbol": "_normalize_default_days",
          "excerptHash": "m4-supplier-service-days"
        },
        {
          "path": "core/services/common/strict_parse.py",
          "lineStart": 32,
          "lineEnd": 64,
          "symbol": "parse_required_float",
          "excerptHash": "m4-strict-parse-float"
        },
        {
          "path": "tests/test_part_operation_hours_import_apply_defense.py",
          "lineStart": 13,
          "lineEnd": 29,
          "symbol": "test_parse_write_row_accepts_integer_float_string_forms",
          "excerptHash": "m4-test-part-hours"
        },
        {
          "path": "tests/regression_calendar_no_tx_hardening.py",
          "lineStart": 240,
          "lineEnd": 252,
          "symbol": "main",
          "excerptHash": "m4-test-cal-no-tx"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 216,
          "lineEnd": 248,
          "symbol": "dispatch_sgs",
          "excerptHash": "m4-sgs-probe"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 45,
          "lineEnd": 109,
          "symbol": "auto_assign_internal_resources",
          "excerptHash": "m4-auto-assign-count"
        },
        {
          "path": "core/services/scheduler/schedule_summary.py",
          "lineStart": 415,
          "lineEnd": 466,
          "symbol": "build_result_summary",
          "excerptHash": "m4-summary-fallback"
        },
        {
          "path": "core/services/process/route_parser.py"
        },
        {
          "path": "core/services/process/part_service.py"
        },
        {
          "path": "core/services/process/external_group_service.py"
        },
        {
          "path": "core/services/process/supplier_service.py"
        },
        {
          "path": "web/routes/process_excel_routes.py"
        },
        {
          "path": "web/routes/process_excel_part_operation_hours.py"
        },
        {
          "path": "web/routes/process_excel_suppliers.py"
        },
        {
          "path": "web/routes/process_parts.py"
        },
        {
          "path": "web/routes/scheduler_calendar_pages.py"
        },
        {
          "path": "web/routes/scheduler_excel_calendar.py"
        },
        {
          "path": "core/services/scheduler/calendar_admin.py"
        },
        {
          "path": "web/routes/excel_utils.py"
        },
        {
          "path": "core/services/process/part_operation_hours_excel_import_service.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
        },
        {
          "path": "tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py"
        },
        {
          "path": "tests/regression_external_group_service_strict_mode_blank_days.py"
        },
        {
          "path": "tests/regression_supplier_service_invalid_default_days_not_silent.py"
        },
        {
          "path": "tests/regression_process_reparse_preserve_internal_hours.py"
        },
        {
          "path": "tests/regression_process_suppliers_route_reject_blank_default_days.py"
        },
        {
          "path": "tests/regression_calendar_no_tx_hardening.py"
        },
        {
          "path": "tests/regression_scheduler_excel_calendar_uses_executor.py"
        },
        {
          "path": "tests/test_part_operation_hours_import_apply_defense.py"
        }
      ],
      "reviewedModules": [
        "process.route_parser",
        "process.part_service",
        "process.external_group_service",
        "process.supplier_service",
        "process.excel_routes",
        "process.excel_part_operation_hours",
        "process.excel_suppliers",
        "process.parts_route",
        "scheduler.calendar_admin",
        "scheduler.calendar_routes",
        "scheduler.excel_calendar",
        "common.excel_utils"
      ],
      "recommendedNextAction": "先统一 Excel 路由层的数字解析入口并补齐路由级回归，再继续看剩余 UI/工具链改动是否可以收口。",
      "findingIds": [
        "excel-route-strict-numeric-drift"
      ]
    },
    {
      "id": "m5_ui_tooling_guardrails",
      "title": "列表页/UI 工具链与测试护栏补审",
      "status": "completed",
      "recordedAt": "2026-04-05T04:11:05.335Z",
      "summaryMarkdown": "本阶段补审了本轮新改动中的列表页、Excel 辅助页面、说明书脚本与测试护栏，覆盖 `web/routes/dashboard.py`、`equipment_pages.py`、`personnel_pages.py`、`equipment_excel_machines.py`、`equipment_excel_links.py`、`personnel_excel_operators.py`、`personnel_excel_links.py`、`personnel_calendar_pages.py`、`static/js/config_manual.js`、`check_manual_layout.py`、`verify_manual_styles.py`、`tests/test_architecture_fitness.py`、`tests/test_team_pages_excel_smoke.py`、`tests/regression_config_manual_markdown.py`，以及对应模板 `templates/equipment/list.html`、`templates/personnel/calendar.html`、`templates/process/detail.html`、`templates/process/list.html`、`templates/scheduler/batches.html`、`templates/scheduler/batches_manage.html`、`templates/scheduler/calendar.html`、`templates/scheduler/excel_import_batches.html`、`web_new_test/templates/base.html`。\n\n正向结论：\n- 设备/人员列表、班组筛选、批量操作和停机覆盖告警的界面契约基本一致，和 `test_team_pages_excel_smoke.py` 的断言能对上；\n- `config_manual.js` 现在优先按 `getElementById(hashId)` 处理数字开头锚点，再回退 `querySelector`，结合 `regression_config_manual_markdown.py`、`check_manual_layout.py`、`verify_manual_styles.py`，说明书页面的可用性与布局验证链路比之前完整；\n- `dashboard.py` 对坏 `result_summary` 的处理是显式 warning + 安全降级，不属于静默吞错；\n- `web_new_test/templates/base.html` 的界面模式切换、主题与表格密度控制没有看到新的高风险逻辑错误。\n\n本阶段真正需要记账的是测试护栏退化：`tests/test_architecture_fitness.py::test_no_silent_exception_swallow()` 虽然表面上还保留 `known_violations`，但后续不再核对这些 allowlist 的具体位置，只把它们压平成 `known_counts`，最后仅按“同文件吞异常点数量是否增加”做判定。这样一来，只要在同一个文件里删掉一个旧的 `except Exception: pass`，再新增一个新的静默吞错点，测试依然会通过；也就是说，原本针对具体位置的保护已经被降级成粗粒度计数保护，和当前代码库里大量兼容性回退分支并存时，风险会被进一步放大。\n\n另外，顺带复核了 `tests/regression_template_urlfor_endpoints.py` 当前版本，`url_for\\(` 仍会命中 `safe_url_for(`，该历史开放问题本阶段未见收口；不过它并不来自本轮新增文件，因此这里不重复记账。",
      "conclusionMarkdown": "UI 与说明书工具链改动整体可接受，但测试护栏本身被削弱了一层，当前 review 仍不建议 finalize。",
      "evidence": [
        {
          "path": "static/js/config_manual.js",
          "lineStart": 519,
          "lineEnd": 548,
          "symbol": "initManual",
          "excerptHash": "m5-config-manual-hash"
        },
        {
          "path": "tests/regression_config_manual_markdown.py",
          "lineStart": 59,
          "lineEnd": 257,
          "symbol": "_run_hash_runtime_check",
          "excerptHash": "m5-config-manual-test"
        },
        {
          "path": "check_manual_layout.py",
          "lineStart": 92,
          "lineEnd": 119,
          "symbol": "check_layout_via_styles",
          "excerptHash": "m5-manual-layout-style"
        },
        {
          "path": "verify_manual_styles.py",
          "lineStart": 57,
          "lineEnd": 125,
          "symbol": "main",
          "excerptHash": "m5-manual-style-verify"
        },
        {
          "path": "web/routes/equipment_pages.py",
          "lineStart": 62,
          "lineEnd": 69,
          "symbol": "_load_active_downtime_machine_ids",
          "excerptHash": "m5-equipment-downtime"
        },
        {
          "path": "templates/equipment/list.html",
          "lineStart": 64,
          "lineEnd": 73,
          "excerptHash": "m5-equipment-banner"
        },
        {
          "path": "web/routes/personnel_calendar_pages.py",
          "lineStart": 14,
          "lineEnd": 27,
          "symbol": "_resolve_page_holiday_default_efficiency",
          "excerptHash": "m5-personnel-calendar-hde"
        },
        {
          "path": "templates/personnel/calendar.html",
          "lineStart": 41,
          "lineEnd": 45,
          "excerptHash": "m5-personnel-calendar-banner"
        },
        {
          "path": "web/routes/dashboard.py",
          "lineStart": 27,
          "lineEnd": 54,
          "symbol": "index",
          "excerptHash": "m5-dashboard-summary"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 391,
          "lineEnd": 551,
          "symbol": "test_no_silent_exception_swallow",
          "excerptHash": "m5-arch-swallow"
        },
        {
          "path": "web/routes/dashboard.py"
        },
        {
          "path": "web/routes/equipment_pages.py"
        },
        {
          "path": "web/routes/personnel_pages.py"
        },
        {
          "path": "web/routes/equipment_excel_machines.py"
        },
        {
          "path": "web/routes/equipment_excel_links.py"
        },
        {
          "path": "web/routes/personnel_excel_operators.py"
        },
        {
          "path": "web/routes/personnel_excel_links.py"
        },
        {
          "path": "web/routes/personnel_calendar_pages.py"
        },
        {
          "path": "templates/equipment/list.html"
        },
        {
          "path": "templates/personnel/calendar.html"
        },
        {
          "path": "templates/process/detail.html"
        },
        {
          "path": "templates/process/list.html"
        },
        {
          "path": "templates/scheduler/batches.html"
        },
        {
          "path": "templates/scheduler/batches_manage.html"
        },
        {
          "path": "templates/scheduler/calendar.html"
        },
        {
          "path": "templates/scheduler/excel_import_batches.html"
        },
        {
          "path": "static/js/config_manual.js"
        },
        {
          "path": "check_manual_layout.py"
        },
        {
          "path": "verify_manual_styles.py"
        },
        {
          "path": "web_new_test/templates/base.html"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "tests/test_team_pages_excel_smoke.py"
        },
        {
          "path": "tests/regression_config_manual_markdown.py"
        }
      ],
      "reviewedModules": [
        "dashboard",
        "equipment.pages",
        "equipment.excel_machines",
        "equipment.excel_links",
        "personnel.pages",
        "personnel.excel_operators",
        "personnel.excel_links",
        "personnel.calendar_pages",
        "templates.equipment.list",
        "templates.personnel.calendar",
        "templates.process.detail",
        "templates.process.list",
        "templates.scheduler.batches",
        "templates.scheduler.batches_manage",
        "templates.scheduler.calendar",
        "templates.scheduler.excel_batches",
        "config_manual",
        "manual_layout_tooling",
        "test.architecture_fitness",
        "web_new_test.base"
      ],
      "recommendedNextAction": "在修复 Excel 路由数值契约漂移和测试护栏退化后，再决定是否把本轮 review finalize；当前不建议直接接受。",
      "findingIds": [
        "silent-swallow-fitness-count-only-whitelist"
      ]
    }
  ],
  "findings": [
    {
      "id": "sgs-auto-assign-probe-counter-inflation",
      "severity": "medium",
      "category": "other",
      "title": "SGS 探测式自动分配污染统计计数",
      "descriptionMarkdown": "`dispatch_sgs` 在评分阶段为了估算候选优先级，会提前调用 `scheduler._auto_assign_internal_resources(...)` 做探测式选机选人；但 `auto_assign_internal_resources` 内部在缺少工种、缺少候选设备、候选人员为空、不可行配对等分支都会直接 `increment_counter(...)`。由于这些探测发生在真正排产之前，而且同一个候选可能在多轮评分中被重复探测，最终 `fallback_counts` 记录的是“评分探测次数”而不是“真实排产失败次数”。后续 `schedule_summary.build_result_summary()` 又会把这些计数并入摘要输出，导致留痕和诊断口径失真。该问题不会直接改变排产结果，但会误导排障、审计与回归比较。",
      "recommendationMarkdown": "把自动分配拆成“纯评估/不记数”的探测入口与“真实执行/记数”的正式入口，或者为评分阶段新增显式 `probe_only` 开关，避免探测过程污染最终统计。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 216,
          "lineEnd": 248
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 45,
          "lineEnd": 109
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 221,
          "lineEnd": 225
        },
        {
          "path": "core/services/scheduler/schedule_summary.py",
          "lineStart": 415,
          "lineEnd": 416
        },
        {
          "path": "core/services/scheduler/schedule_summary.py",
          "lineStart": 465,
          "lineEnd": 466
        },
        {
          "path": "core/services/scheduler/config_service.py"
        },
        {
          "path": "core/services/scheduler/config_snapshot.py"
        },
        {
          "path": "core/services/scheduler/config_validator.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_persistence.py"
        },
        {
          "path": "core/services/scheduler/schedule_summary.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "tests/regression_schedule_summary_v11_contract.py"
        },
        {
          "path": "tests/regression_auto_assign_persist_truthy_variants.py"
        },
        {
          "path": "tests/regression_schedule_service_passes_algo_stats_to_summary.py"
        },
        {
          "path": "tests/regression_sgs_scoring_fallback_unscorable.py"
        },
        {
          "path": "tests/regression_sgs_penalize_nonfinite_proc_hours.py"
        }
      ],
      "relatedMilestoneIds": [
        "m2_scheduler_core"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "template-urlfor-regex-overmatches-safe-url-for",
      "severity": "medium",
      "category": "test",
      "title": "端点扫描回归把 safe_url_for 当成强制 url_for",
      "descriptionMarkdown": "`tests/regression_template_urlfor_endpoints.py` 的说明明确写着：`safe_url_for(...)` 允许引用未注册端点，不应像 `url_for(...)` 那样直接判失败；但实现里用于抓取 `url_for(...)` 的正则是 `url_for\\(`，它同样会匹配 `safe_url_for(` 里的子串。随后同一行又会被 `pat_safe` 再抓一次，于是“可选链接”实际上会同时进入 `missing_url` 与 `missing_safe` 两套集合，最终仍可能触发失败分支。这样会把本应允许缺失的灰度/可选入口错误地升级为强制断言，导致测试契约与实现描述不一致。",
      "recommendationMarkdown": "把 `url_for` 提取规则改成不会命中 `safe_url_for` 的表达式（例如增加词边界或显式负向前瞻/后顾），或改用更稳妥的模板语法级扫描，确保“强制链接”和“可选链接”分开统计。",
      "evidence": [
        {
          "path": "tests/regression_template_urlfor_endpoints.py",
          "lineStart": 9,
          "lineEnd": 15
        },
        {
          "path": "tests/regression_template_urlfor_endpoints.py",
          "lineStart": 60,
          "lineEnd": 61
        },
        {
          "path": "tests/regression_template_urlfor_endpoints.py",
          "lineStart": 74,
          "lineEnd": 82
        },
        {
          "path": "tests/regression_template_urlfor_endpoints.py",
          "lineStart": 112,
          "lineEnd": 129
        },
        {
          "path": "web/routes/system_backup.py"
        },
        {
          "path": "web/routes/system_history.py"
        },
        {
          "path": "web/ui_mode.py"
        },
        {
          "path": "templates/base.html"
        },
        {
          "path": "templates/components/excel_import.html"
        },
        {
          "path": "tests/test_ui_mode.py"
        },
        {
          "path": "tests/regression_template_urlfor_endpoints.py"
        },
        {
          "path": "tests/regression_backup_restore_pending_verify_code.py"
        }
      ],
      "relatedMilestoneIds": [
        "m3_ui_routes_tests"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "excel-route-strict-numeric-drift",
      "severity": "medium",
      "category": "other",
      "title": "Excel 路由数值校验与服务契约漂移",
      "descriptionMarkdown": "本轮修改里，多个 Excel 路由重新手写了整数/浮点解析，未复用服务层已经存在的严格解析入口，导致 preview/confirm 与真正写库阶段的契约再次分裂。`web/routes/scheduler_excel_calendar.py` 用原始 `float(...)` 校验“可用工时/效率”，会把 `True`、`NaN`、`Inf` 等值放过预览，但 `CalendarAdmin` 真正落库时会拒绝；`web/routes/process_excel_part_operation_hours.py::_parse_seq()` 会把 `True` 与 `\"5e0\"` 变成合法工序号，直接绕过 `PartOperationHoursExcelImportService._coerce_int()` 的防御；`web/routes/process_excel_suppliers.py::_normalize_supplier_default_days()` 会把 `True` 当成 `1.0`，与 `SupplierService` 通过 `parse_required_float()` 拒绝布尔值的行为不一致。结果是：有的脏数据会在预览阶段被错误放行，有的会在确认阶段才爆出异常，有的甚至会静默写到错误主键上，整体既不简洁也不严谨。",
      "recommendationMarkdown": "把这些路由层校验统一收敛到共享严格解析入口：日历链路直接复用 `CalendarAdmin` / `parse_finite_float`，零件工时链路复用 `PartOperationHoursExcelImportService._coerce_int()` 或等价共享函数，供应商链路复用 `parse_required_float()` / `SupplierService`。同时补上路由级回归，至少覆盖 `True/False/NaN/Inf/\"5e0\"` 这几类输入。",
      "evidence": [
        {
          "path": "web/routes/scheduler_excel_calendar.py",
          "lineStart": 197,
          "lineEnd": 220,
          "symbol": "validate_row",
          "excerptHash": "m4-cal-validate-1"
        },
        {
          "path": "web/routes/scheduler_excel_calendar.py",
          "lineStart": 331,
          "lineEnd": 353,
          "symbol": "validate_row",
          "excerptHash": "m4-cal-validate-2"
        },
        {
          "path": "core/services/scheduler/calendar_admin.py",
          "lineStart": 138,
          "lineEnd": 147,
          "symbol": "_build_work_calendar",
          "excerptHash": "m4-cal-admin-build"
        },
        {
          "path": "web/routes/process_excel_part_operation_hours.py",
          "lineStart": 46,
          "lineEnd": 64,
          "symbol": "_parse_seq",
          "excerptHash": "m4-part-hours-seq"
        },
        {
          "path": "core/services/process/part_operation_hours_excel_import_service.py",
          "lineStart": 111,
          "lineEnd": 129,
          "symbol": "_coerce_int",
          "excerptHash": "m4-part-hours-service"
        },
        {
          "path": "web/routes/process_excel_suppliers.py",
          "lineStart": 89,
          "lineEnd": 100,
          "symbol": "_normalize_supplier_default_days",
          "excerptHash": "m4-supplier-route-days"
        },
        {
          "path": "core/services/process/supplier_service.py",
          "lineStart": 29,
          "lineEnd": 36,
          "symbol": "_normalize_default_days",
          "excerptHash": "m4-supplier-service-days"
        },
        {
          "path": "core/services/common/strict_parse.py",
          "lineStart": 32,
          "lineEnd": 64,
          "symbol": "parse_required_float",
          "excerptHash": "m4-strict-parse-float"
        },
        {
          "path": "tests/test_part_operation_hours_import_apply_defense.py",
          "lineStart": 13,
          "lineEnd": 29,
          "symbol": "test_parse_write_row_accepts_integer_float_string_forms",
          "excerptHash": "m4-test-part-hours"
        },
        {
          "path": "tests/regression_calendar_no_tx_hardening.py",
          "lineStart": 240,
          "lineEnd": 252,
          "symbol": "main",
          "excerptHash": "m4-test-cal-no-tx"
        },
        {
          "path": "core/services/process/route_parser.py"
        },
        {
          "path": "core/services/process/part_service.py"
        },
        {
          "path": "core/services/process/external_group_service.py"
        },
        {
          "path": "core/services/process/supplier_service.py"
        },
        {
          "path": "web/routes/process_excel_routes.py"
        },
        {
          "path": "web/routes/process_excel_part_operation_hours.py"
        },
        {
          "path": "web/routes/process_excel_suppliers.py"
        },
        {
          "path": "web/routes/process_parts.py"
        },
        {
          "path": "web/routes/scheduler_calendar_pages.py"
        },
        {
          "path": "web/routes/scheduler_excel_calendar.py"
        },
        {
          "path": "core/services/scheduler/calendar_admin.py"
        },
        {
          "path": "web/routes/excel_utils.py"
        },
        {
          "path": "core/services/process/part_operation_hours_excel_import_service.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
        },
        {
          "path": "tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py"
        },
        {
          "path": "tests/regression_external_group_service_strict_mode_blank_days.py"
        },
        {
          "path": "tests/regression_supplier_service_invalid_default_days_not_silent.py"
        },
        {
          "path": "tests/regression_process_reparse_preserve_internal_hours.py"
        },
        {
          "path": "tests/regression_process_suppliers_route_reject_blank_default_days.py"
        },
        {
          "path": "tests/regression_calendar_no_tx_hardening.py"
        },
        {
          "path": "tests/regression_scheduler_excel_calendar_uses_executor.py"
        },
        {
          "path": "tests/test_part_operation_hours_import_apply_defense.py"
        }
      ],
      "relatedMilestoneIds": [
        "m4_process_calendar_excel"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "silent-swallow-fitness-count-only-whitelist",
      "severity": "medium",
      "category": "test",
      "title": "静默吞异常护栏退化为按文件计数",
      "descriptionMarkdown": "`tests/test_architecture_fitness.py::test_no_silent_exception_swallow()` 现在先把 `known_violations` 压平成 `known_counts`，随后只检查“每个文件里的 `except Exception: pass / ...` 数量是否超过上限”。这确实能避免单纯行号漂移带来的误报，但代价是丢掉了对具体吞异常位置的约束：同一个文件里，删除一个旧的 allowlist 点、再新增一个新的静默吞错点，只要总数不变，测试就会通过。考虑到当前代码里已经存在不少兼容性回退分支，这个改动会明显削弱后续发现新增静默吞错的能力，也会降低 review 对这类问题的信心。",
      "recommendationMarkdown": "不要只按文件计数做白名单。更稳妥的做法是保留具体位置约束，并用 AST 上下文、处理体摘要或稳定指纹来抵抗行号漂移；至少也要把 allowlist 从“文件级数量”提升到“文件+处理块语义”级别。",
      "evidence": [
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 391,
          "lineEnd": 551,
          "symbol": "test_no_silent_exception_swallow",
          "excerptHash": "m5-arch-swallow"
        },
        {
          "path": "web/routes/dashboard.py"
        },
        {
          "path": "web/routes/equipment_pages.py"
        },
        {
          "path": "web/routes/personnel_pages.py"
        },
        {
          "path": "web/routes/equipment_excel_machines.py"
        },
        {
          "path": "web/routes/equipment_excel_links.py"
        },
        {
          "path": "web/routes/personnel_excel_operators.py"
        },
        {
          "path": "web/routes/personnel_excel_links.py"
        },
        {
          "path": "web/routes/personnel_calendar_pages.py"
        },
        {
          "path": "templates/equipment/list.html"
        },
        {
          "path": "templates/personnel/calendar.html"
        },
        {
          "path": "templates/process/detail.html"
        },
        {
          "path": "templates/process/list.html"
        },
        {
          "path": "templates/scheduler/batches.html"
        },
        {
          "path": "templates/scheduler/batches_manage.html"
        },
        {
          "path": "templates/scheduler/calendar.html"
        },
        {
          "path": "templates/scheduler/excel_import_batches.html"
        },
        {
          "path": "static/js/config_manual.js"
        },
        {
          "path": "check_manual_layout.py"
        },
        {
          "path": "verify_manual_styles.py"
        },
        {
          "path": "web_new_test/templates/base.html"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "tests/test_team_pages_excel_smoke.py"
        },
        {
          "path": "tests/regression_config_manual_markdown.py"
        }
      ],
      "relatedMilestoneIds": [
        "m5_ui_tooling_guardrails"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:625bd963e674582eef32d5880fc5b98472cdf95d2f1160d38c1ad0b006e4715f",
    "generatedAt": "2026-04-05T04:12:04.184Z",
    "locale": "zh-CN"
  }
}
```
