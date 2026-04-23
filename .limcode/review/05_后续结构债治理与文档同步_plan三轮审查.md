# 05_后续结构债治理与文档同步 plan 三轮审查
- 日期: 2026-04-04
- 概述: 围绕架构适应度账本、排产摘要链与批次导入链，对实施 plan 做三轮深度审查。
- 状态: 已完成
- 总体结论: 需要后续跟进

## 评审范围

# 05_后续结构债治理与文档同步 plan 三轮审查

## 审查范围
- `.limcode/plans/core目录系统性修复/05_后续结构债治理与文档同步.plan.md`
- `tests/test_architecture_fitness.py`
- `core/services/scheduler/schedule_service.py`
- `core/services/scheduler/schedule_orchestrator.py`
- `core/services/scheduler/schedule_summary.py`
- `core/services/scheduler/batch_service.py`
- `core/services/scheduler/batch_template_ops.py`
- `core/services/scheduler/batch_excel_import.py`
- 相关 route 与回归测试

## 审查方法
1. 先核对 plan 与当前代码/适应度账本是否一致。
2. 再沿 `ScheduleService -> schedule_orchestrator -> build_result_summary` 深挖排产摘要链。
3. 最后沿 `route -> BatchService -> batch_excel_import -> batch_template_ops` 深挖批次更新/模板协调链。
4. 补跑定向回归，确认当前基线是否稳定。

## 当前状态
- 状态：in_progress
- 初步判断：plan 方向基本对，但存在基线陈旧、拆分边界不足、回归清单不完整三个问题，需要 revision 后再执行。

## 评审摘要

- 当前状态: 已完成
- 已审模块: tests/test_architecture_fitness.py, core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_orchestrator.py, core/services/scheduler/schedule_summary.py, tests/regression_schedule_summary_freeze_state_contract.py, tests/regression_due_exclusive_consistency.py, tests/regression_legacy_external_days_defaulted_visible.py, tests/regression_warmstart_failure_surfaces_degradation.py, tests/regression_schedule_summary_end_date_type_guard.py, tests/regression_dict_cfg_contract.py, core/services/scheduler/batch_service.py, core/services/scheduler/batch_template_ops.py, core/services/scheduler/batch_excel_import.py, web/routes/scheduler_batches.py, web/routes/scheduler_excel_batches.py
- 当前进度: 已记录 3 个里程碑；最新：round3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 5
- 问题严重级别分布: 高 4 / 中 1 / 低 0
- 最新结论: 该 plan 的治理方向总体正确，但当前版本不宜直接执行。首批次与现状基线已脱节；批次 B 的拆分边界不足以兑现“去掉超长与复杂度白名单”的完成标准；批次 C 的风险说明主要落在 Excel 导入链，却没有把 `batch_excel_import.py` 纳入变更范围。建议先按本次三轮审查结果做 revision，再进入实现。
- 下一步建议: 先 revision plan：把批次 A 改成复杂度白名单陈旧项清理；把批次 B 改成两段式拆分并扩充 direct summary 回归；把批次 C 改成 `batch_service.update()` 收口 + `batch_excel_import.py`/`batch_template_ops.py` 联动治理。
- 总体结论: 需要后续跟进

## 评审发现

### 批次A与当前适应度账本已脱节

- ID: plan-baseline-drift
- 严重级别: 高
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: round1
- 说明:

  plan 仍把“为超长白名单新增自校验、移除 schedule_service 超长登记”当作待执行动作，但当前代码里这两件事都已经完成：`test_known_oversize_entries_still_exceed_limit()` 已存在，`_known_oversize_files()` 也已不含 `schedule_service.py`。继续按原批次执行会造成重复劳动，并且掩盖一个更真实的问题——高复杂度白名单里仍残留 `schedule_service.py:_run_schedule_impl` 这类已不再超阈值的陈旧登记。
- 建议:

  把批次 A revision 为“账本陈旧项清理”：先清复杂度白名单里的 `schedule_service.py:_run_schedule_impl`，再批量检查是否还存在类似 stale 项。
- 证据:
  - `tests/test_architecture_fitness.py:43-56#_known_oversize_files`
  - `tests/test_architecture_fitness.py:479-486#test_known_oversize_entries_still_exceed_limit`
  - `tests/test_architecture_fitness.py:567-568#known_violations`
  - `core/services/scheduler/schedule_service.py:271-396#run_schedule / _run_schedule_impl`
  - `tests/test_architecture_fitness.py`
  - `core/services/scheduler/schedule_service.py`

### 批次B当前拆分边界不足以移除 schedule_summary 超长登记

- ID: schedule-summary-scope-insufficient
- 严重级别: 高
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: round2
- 说明:

  `schedule_summary.py` 当前共有 923 行，而 plan 计划外提的冻结/退化热点大致位于 385-685 行。即便这些段落全部迁出，主文件仍会保留 1-384 与 688-921 两块，总量仍明显高于 500 行门禁。与此同时，`build_result_summary()` 当前复杂度为 57；只把冻结/退化计算外提，并不能自动证明它会降到 ≤15。按现 scope 执行，最可能出现的结果是“模块拆了一部分，但 oversize 与 complexity 白名单仍删不掉”。
- 建议:

  把批次 B revision 为“两段式拆分”：第一步先把冻结/退化/告警拼装整体外提；第二步再把 `build_result_summary()` 中的摘要对象装配与尾部 `algo_dict` 补丁拆成独立构造器，确保同时满足 500 行门禁与复杂度门禁。
- 证据:
  - `core/services/scheduler/schedule_summary.py:385-921#_extract_freeze_warnings / _freeze_meta_dict / _summary_degradation_state / build_result_summary`
  - `tests/test_architecture_fitness.py:467-476#test_file_size_limit`
  - `tests/test_architecture_fitness.py:569-601#known_violations`
  - `core/services/scheduler/schedule_orchestrator.py:147-178#orchestrate_schedule_run`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_summary.py`
  - `tests/test_architecture_fitness.py`
  - `tests/regression_schedule_summary_freeze_state_contract.py`
  - `tests/regression_due_exclusive_consistency.py`
  - `tests/regression_legacy_external_days_defaulted_visible.py`
  - `tests/regression_warmstart_failure_surfaces_degradation.py`
  - `tests/regression_schedule_summary_end_date_type_guard.py`
  - `tests/regression_dict_cfg_contract.py`

### 批次B的必跑回归清单遗漏直接调用 summary 合同的用例

- ID: schedule-summary-regression-gap
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: round2
- 说明:

  当前 plan 只列出一部分 `schedule_summary` 回归，但仓库里还有多组直接调用 `build_result_summary()` 的测试，分别覆盖冻结硬约束开关、交期边界一致性、历史外协周期回退可见性、OR-Tools 预热失败退化、`end_date` 类型守卫、dict/object 配置合同。如果只跑 plan 现有清单，`result_summary` 的若干细粒度合同可能被遗漏。
- 建议:

  把所有直接调用 `build_result_summary()` 的回归并入批次 B 的必跑清单，至少覆盖冻结状态、交期边界、退化计数、配置快照、类型守卫五类合同。
- 证据:
  - `tests/regression_schedule_summary_freeze_state_contract.py:61-104#test_schedule_summary_freeze_state_controls_hard_constraints`
  - `tests/regression_due_exclusive_consistency.py:80-107#main`
  - `tests/regression_legacy_external_days_defaulted_visible.py:96-130#main`
  - `tests/regression_warmstart_failure_surfaces_degradation.py:107-138#main`
  - `tests/regression_schedule_summary_end_date_type_guard.py:31-72#_build_summary_with_end_date`
  - `tests/regression_dict_cfg_contract.py:216-252#_run_summary_case`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_summary.py`
  - `tests/test_architecture_fitness.py`
  - `tests/regression_schedule_summary_freeze_state_contract.py`
  - `tests/regression_due_exclusive_consistency.py`
  - `tests/regression_legacy_external_days_defaulted_visible.py`
  - `tests/regression_warmstart_failure_surfaces_degradation.py`
  - `tests/regression_schedule_summary_end_date_type_guard.py`
  - `tests/regression_dict_cfg_contract.py`

### 批次C误把陈旧白名单项当成当前复杂热点

- ID: batch-plan-mistargeted-hotspot
- 严重级别: 高
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: round3
- 说明:

  plan 仍把 `core/services/scheduler/batch_service.py:create_batch_from_template_no_tx` 当成需要继续拆分的复杂函数，但当前 `BatchService.create_batch_from_template_no_tx()` 已经只剩一层薄包装；真正的模板协调逻辑位于 `core/services/scheduler/batch_template_ops.py:create_batch_from_template_no_tx`。继续按旧目标推进，会把真正的实现热点与陈旧白名单项混为一谈。
- 建议:

  把批次 C 拆成两个子目标：一是直接清理 `batch_service.py:create_batch_from_template_no_tx` 的复杂度白名单；二是把真正的模板协调治理放在 `batch_template_ops.py`（必要时连同 `batch_excel_import.py`）里完成。
- 证据:
  - `core/services/scheduler/batch_service.py:528-555#BatchService.create_batch_from_template_no_tx`
  - `core/services/scheduler/batch_template_ops.py:75-133#create_batch_from_template_no_tx`
  - `tests/test_architecture_fitness.py:549-550#known_violations`
  - `core/services/scheduler/batch_service.py`
  - `core/services/scheduler/batch_template_ops.py`
  - `core/services/scheduler/batch_excel_import.py`
  - `web/routes/scheduler_batches.py`
  - `web/routes/scheduler_excel_batches.py`
  - `tests/test_architecture_fitness.py`
  - `tests/regression_batch_excel_import_reject_part_change_without_rebuild.py`
  - `tests/regression_batch_import_unchanged_no_rebuild.py`
  - `tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py`

### 批次C的风险说明主要发生在 Excel 导入链，但计划文件清单未纳入 batch_excel_import.py

- ID: batch-excel-chain-out-of-scope
- 严重级别: 高
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: round3
- 说明:

  plan 列出的回归里，多数都命中 `BatchService.import_from_preview_rows()` 再进入 `batch_excel_import.import_batches_from_preview_rows()`。其中“改图号必须开启自动生成工序”“UNCHANGED 行不得触发写入”“strict_mode 失败后不得残留批次/工序”都发生在 `_apply_row_no_tx()` 这一层，而不是 `BatchService.update()`。如果批次 C 不把 `batch_excel_import.py` 纳入变更范围，那么 plan 的测试集与改动对象会继续错位。
- 建议:

  把 `core/services/scheduler/batch_excel_import.py` 加入批次 C 的文件清单与必跑回归说明；若只想消除 `batch_service.py` 超长债务，则应把 Excel 语义保护明确标成“受影响链路验证”，而不是默认由 `update()` 重构顺带覆盖。
- 证据:
  - `core/services/scheduler/batch_excel_import.py:37-115#_apply_row_no_tx / import_batches_from_preview_rows`
  - `web/routes/scheduler_excel_batches.py:354-360#excel_batches_confirm`
  - `tests/regression_batch_excel_import_reject_part_change_without_rebuild.py:58-79#test_batch_excel_import_rejects_part_change_without_rebuild`
  - `tests/regression_batch_import_unchanged_no_rebuild.py:66-89#main`
  - `tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py:64-86#main`
  - `core/services/scheduler/batch_service.py`
  - `core/services/scheduler/batch_template_ops.py`
  - `core/services/scheduler/batch_excel_import.py`
  - `web/routes/scheduler_batches.py`
  - `web/routes/scheduler_excel_batches.py`
  - `tests/test_architecture_fitness.py`
  - `tests/regression_batch_excel_import_reject_part_change_without_rebuild.py`
  - `tests/regression_batch_import_unchanged_no_rebuild.py`
  - `tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py`

## 评审里程碑

### round1 · 第一轮：plan 与架构适应度基线一致性复核

- 状态: 已完成
- 记录时间: 2026-04-04T15:43:16.992Z
- 已审模块: tests/test_architecture_fitness.py, core/services/scheduler/schedule_service.py
- 摘要:

  ### 复核动作
  - 对照 plan 中批次 A 的目标，核验 `tests/test_architecture_fitness.py` 当前账本状态。
  - 复核 `schedule_service.py` 当前体量与公开执行链。
  - 实跑 `python -m pytest -q tests/test_architecture_fitness.py -k "known_oversize_entries_still_exceed_limit or file_size_limit or cyclomatic_complexity_threshold"`，结果为 **3 passed**。

  ### 关键事实
  1. `tests/test_architecture_fitness.py` 已经包含 `test_known_oversize_entries_still_exceed_limit()`，说明 plan 批次 A 中“新增白名单自校验”的动作已经落地，不再是待做事项。
  2. `_known_oversize_files()` 当前已不含 `core/services/scheduler/schedule_service.py`；同时该集合按现状只有 9 项，不再是 plan 文本里写的 10 项。
  3. `schedule_service.py` 当前总代码行数为 398 行，`run_schedule()` 只负责锁与门面转发，`_run_schedule_impl()` 已退化为“输入收集 -> 编排 -> 落库”的协调函数。
  4. 尽管超长白名单已清理，`tests/test_architecture_fitness.py` 里仍保留了 `core/services/scheduler/schedule_service.py:_run_schedule_impl` 的高复杂度白名单；结合本轮实测的复杂度结果，该条目已明显陈旧。

  ### 轮次结论
  - 批次 A 不能再按原文执行；更合理的 revision 是把它改成“适应度账本陈旧项二次清理”，重点从超长白名单转向高复杂度白名单陈旧项。
- 结论:

  plan 的首批次已与当前代码基线脱节，需要 revision 后再继续。
- 证据:
  - `tests/test_architecture_fitness.py:43-56#_known_oversize_files`
  - `tests/test_architecture_fitness.py:467-486#test_file_size_limit / test_known_oversize_entries_still_exceed_limit`
  - `tests/test_architecture_fitness.py:566-568#known_violations`
  - `core/services/scheduler/schedule_service.py:271-396#run_schedule / _run_schedule_impl`
  - `tests/test_architecture_fitness.py`
  - `core/services/scheduler/schedule_service.py`
- 下一步建议:

  先修订 plan 的批次 A 描述与完成标准，再继续评估后续批次。
- 问题:
  - [高] 可维护性: 批次A与当前适应度账本已脱节

### round2 · 第二轮：排产摘要链深审（ScheduleService → Orchestrator → Summary）

- 状态: 已完成
- 记录时间: 2026-04-04T15:43:51.307Z
- 已审模块: core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_orchestrator.py, core/services/scheduler/schedule_summary.py, tests/regression_schedule_summary_freeze_state_contract.py, tests/regression_due_exclusive_consistency.py, tests/regression_legacy_external_days_defaulted_visible.py, tests/regression_warmstart_failure_surfaces_degradation.py, tests/regression_schedule_summary_end_date_type_guard.py, tests/regression_dict_cfg_contract.py
- 摘要:

  ### 引用链复核
  - `ScheduleService._run_schedule_impl()` 通过 `orchestrate_schedule_run()` 传入 `build_result_summary_fn=build_result_summary`。
  - `orchestrate_schedule_run()` 在确认 `has_actionable_schedule=True`、分配版本号后，按关键字参数把 `cfg / version / batches / operations / results / freeze_meta / input_build_outcome / downtime_meta / resource_pool_meta / algo_stats / warning_merge_status` 全量传给 `build_result_summary()`。
  - 这意味着批次 B 不是单纯的文件拆分，而是 `result_summary` 合同装配点的重构；任何参数名、返回五元组、字段路径改变，都会直接打到主排产链。

  ### 实测与事实
  - 实跑 `tests/regression_schedule_service_facade_delegation.py tests/regression_schedule_input_collector_contract.py tests/regression_schedule_orchestrator_contract.py tests/regression_schedule_summary_v11_contract.py tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py tests/regression_schedule_summary_algo_warnings_union.py tests/regression_schedule_summary_size_guard_large_lists.py tests/regression_schedule_summary_fallback_counts_output.py`，结果 **8 passed**。
  - `schedule_summary.py` 当前总长 923 行；plan 准备外提的冻结/退化区段主要集中在 385-685 行。即使整段搬走，主文件仍会保留 1-384 与 688-921 两大段，总量仍约 618 行，无法满足 `tests/test_architecture_fitness.py:test_file_size_limit()` 的 500 行门禁。
  - 同时 `build_result_summary()` 当前复杂度为 57，plan 虽提出外提冻结/退化逻辑，但没有明确第二层拆分点（如告警拼装、算法块装配、最终 dict 打包），无法证明可降到 ≤15。
  - 直接命中 `build_result_summary()` 的回归不止 plan 列出的 5 个；至少还有 `regression_schedule_summary_freeze_state_contract.py`、`regression_due_exclusive_consistency.py`、`regression_legacy_external_days_defaulted_visible.py`、`regression_warmstart_failure_surfaces_degradation.py`、`regression_schedule_summary_end_date_type_guard.py`、`regression_dict_cfg_contract.py`。

  ### 轮次结论
  - 批次 B 的方向是对的，但当前 scope 不足以兑现“移除超长白名单 + 移除复杂度白名单”这两个完成标准；必须先 revision 拆分边界与回归清单。
- 结论:

  批次 B 需要扩大拆分边界，并把直接依赖 `build_result_summary()` 的回归纳入必跑清单。
- 证据:
  - `core/services/scheduler/schedule_service.py:344-351#_run_schedule_impl`
  - `core/services/scheduler/schedule_orchestrator.py:102-178#orchestrate_schedule_run`
  - `core/services/scheduler/schedule_summary.py:385-921#_extract_freeze_warnings / _freeze_meta_dict / _summary_degradation_state / build_result_summary`
  - `tests/test_architecture_fitness.py:467-476#test_file_size_limit`
  - `tests/test_architecture_fitness.py:569-601#known_violations`
  - `tests/regression_schedule_summary_freeze_state_contract.py:61-104#test_schedule_summary_freeze_state_controls_hard_constraints`
  - `tests/regression_due_exclusive_consistency.py:80-107#main`
  - `tests/regression_legacy_external_days_defaulted_visible.py:96-130#main`
  - `tests/regression_warmstart_failure_surfaces_degradation.py:107-138#main`
  - `tests/regression_schedule_summary_end_date_type_guard.py:31-72#_build_summary_with_end_date`
  - `tests/regression_dict_cfg_contract.py:216-252#_run_summary_case`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_summary.py`
  - `tests/test_architecture_fitness.py`
  - `tests/regression_schedule_summary_freeze_state_contract.py`
  - `tests/regression_due_exclusive_consistency.py`
  - `tests/regression_legacy_external_days_defaulted_visible.py`
  - `tests/regression_warmstart_failure_surfaces_degradation.py`
  - `tests/regression_schedule_summary_end_date_type_guard.py`
  - `tests/regression_dict_cfg_contract.py`
- 下一步建议:

  先修订批次 B 的拆分边界与回归矩阵，再开始实现。
- 问题:
  - [高] 可维护性: 批次B当前拆分边界不足以移除 schedule_summary 超长登记
  - [中] 测试: 批次B的必跑回归清单遗漏直接调用 summary 合同的用例

### round3 · 第三轮：批次更新 / 模板协调 / Excel 导入链深审

- 状态: 已完成
- 记录时间: 2026-04-04T15:44:26.175Z
- 已审模块: core/services/scheduler/batch_service.py, core/services/scheduler/batch_template_ops.py, core/services/scheduler/batch_excel_import.py, web/routes/scheduler_batches.py, web/routes/scheduler_excel_batches.py
- 摘要:

  ### 引用链复核
  - 页面批量修改链：`web/routes/scheduler_batches.py:_bulk_update_one_batch()` → `BatchService.update()`。
  - 页面重建工序链：`web/routes/scheduler_batches.py:generate_ops()` → `BatchService.create_batch_from_template()` → `BatchService.create_batch_from_template_no_tx()` → `batch_template_ops.create_batch_from_template_no_tx()`。
  - Excel 确认导入链：`web/routes/scheduler_excel_batches.py:excel_batches_confirm()` → `BatchService.import_from_preview_rows()` → `batch_excel_import.import_batches_from_preview_rows()` → `_apply_row_no_tx()` → `svc.update_no_tx()` / `svc.create_no_tx()` / `svc.create_batch_from_template_no_tx()`。

  ### 实测与事实
  - 实跑 `tests/regression_batch_template_autobuild_same_tx.py tests/regression_batch_service_strict_mode_template_autoparse.py tests/regression_batch_service_legacy_template_resolver_rejects_strict_mode.py tests/regression_batch_excel_import_reject_part_change_without_rebuild.py tests/regression_batch_import_unchanged_no_rebuild.py tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py`，结果 **6 passed**。
  - `BatchService` 当前总长 564 行，其中 `update()` 占 330-409 行，单独外提已足以让主文件降到 500 行以下。
  - 但 plan 锁定的复杂度热点之一 `BatchService.create_batch_from_template_no_tx()` 现在只是 528-555 行的薄转调；实际模板协调逻辑已经下沉在 `batch_template_ops.py:75-133`。
  - 与 plan 风险说明最相关的“改图号但不重建工序 / Excel strict 模式硬失败 / unchanged 行不得误触发写入”并不经过 `BatchService.update()`，而是落在 `batch_excel_import.py:_apply_row_no_tx()` 里。

  ### 轮次结论
  - 批次 C 目前把“真实复杂链路”和“白名单陈旧条目”混在了一起：如果目的是清理架构账本，`create_batch_from_template_no_tx` 的白名单可以直接删；如果目的是守住 Excel 导入与模板协调语义，则必须把 `batch_excel_import.py` 纳入变更范围。
- 结论:

  批次 C 需要重写目标文件清单：`batch_service.py` 以 `update()` 收口为主，Excel/模板语义则转到 `batch_excel_import.py + batch_template_ops.py`。
- 证据:
  - `core/services/scheduler/batch_service.py:330-409#BatchService.update`
  - `core/services/scheduler/batch_service.py:466-555#BatchService.create_batch_from_template / create_batch_from_template_no_tx`
  - `core/services/scheduler/batch_template_ops.py:75-133#create_batch_from_template_no_tx`
  - `core/services/scheduler/batch_excel_import.py:37-115#_apply_row_no_tx / import_batches_from_preview_rows`
  - `web/routes/scheduler_batches.py:292-309#_bulk_update_one_batch`
  - `web/routes/scheduler_batches.py:380-403#generate_ops`
  - `web/routes/scheduler_excel_batches.py:354-360#excel_batches_confirm`
  - `tests/test_architecture_fitness.py:549-550#known_violations`
  - `tests/regression_batch_excel_import_reject_part_change_without_rebuild.py:58-79#test_batch_excel_import_rejects_part_change_without_rebuild`
  - `tests/regression_batch_import_unchanged_no_rebuild.py:66-89#main`
  - `tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py:64-86#main`
  - `core/services/scheduler/batch_service.py`
  - `core/services/scheduler/batch_template_ops.py`
  - `core/services/scheduler/batch_excel_import.py`
  - `web/routes/scheduler_batches.py`
  - `web/routes/scheduler_excel_batches.py`
  - `tests/test_architecture_fitness.py`
  - `tests/regression_batch_excel_import_reject_part_change_without_rebuild.py`
  - `tests/regression_batch_import_unchanged_no_rebuild.py`
  - `tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py`
- 下一步建议:

  先 revision 批次 C 的文件范围与完成标准，再进入实现。
- 问题:
  - [高] 可维护性: 批次C误把陈旧白名单项当成当前复杂热点
  - [高] 测试: 批次C的风险说明主要发生在 Excel 导入链，但计划文件清单未纳入 batch_excel_import.py

## 最终结论

该 plan 的治理方向总体正确，但当前版本不宜直接执行。首批次与现状基线已脱节；批次 B 的拆分边界不足以兑现“去掉超长与复杂度白名单”的完成标准；批次 C 的风险说明主要落在 Excel 导入链，却没有把 `batch_excel_import.py` 纳入变更范围。建议先按本次三轮审查结果做 revision，再进入实现。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnki4mc6-fxfzsd",
  "createdAt": "2026-04-04T00:00:00.000Z",
  "updatedAt": "2026-04-04T15:44:34.823Z",
  "finalizedAt": "2026-04-04T15:44:34.823Z",
  "status": "completed",
  "overallDecision": "needs_follow_up",
  "header": {
    "title": "05_后续结构债治理与文档同步 plan 三轮审查",
    "date": "2026-04-04",
    "overview": "围绕架构适应度账本、排产摘要链与批次导入链，对实施 plan 做三轮深度审查。"
  },
  "scope": {
    "markdown": "# 05_后续结构债治理与文档同步 plan 三轮审查\n\n## 审查范围\n- `.limcode/plans/core目录系统性修复/05_后续结构债治理与文档同步.plan.md`\n- `tests/test_architecture_fitness.py`\n- `core/services/scheduler/schedule_service.py`\n- `core/services/scheduler/schedule_orchestrator.py`\n- `core/services/scheduler/schedule_summary.py`\n- `core/services/scheduler/batch_service.py`\n- `core/services/scheduler/batch_template_ops.py`\n- `core/services/scheduler/batch_excel_import.py`\n- 相关 route 与回归测试\n\n## 审查方法\n1. 先核对 plan 与当前代码/适应度账本是否一致。\n2. 再沿 `ScheduleService -> schedule_orchestrator -> build_result_summary` 深挖排产摘要链。\n3. 最后沿 `route -> BatchService -> batch_excel_import -> batch_template_ops` 深挖批次更新/模板协调链。\n4. 补跑定向回归，确认当前基线是否稳定。\n\n## 当前状态\n- 状态：in_progress\n- 初步判断：plan 方向基本对，但存在基线陈旧、拆分边界不足、回归清单不完整三个问题，需要 revision 后再执行。"
  },
  "summary": {
    "latestConclusion": "该 plan 的治理方向总体正确，但当前版本不宜直接执行。首批次与现状基线已脱节；批次 B 的拆分边界不足以兑现“去掉超长与复杂度白名单”的完成标准；批次 C 的风险说明主要落在 Excel 导入链，却没有把 `batch_excel_import.py` 纳入变更范围。建议先按本次三轮审查结果做 revision，再进入实现。",
    "recommendedNextAction": "先 revision plan：把批次 A 改成复杂度白名单陈旧项清理；把批次 B 改成两段式拆分并扩充 direct summary 回归；把批次 C 改成 `batch_service.update()` 收口 + `batch_excel_import.py`/`batch_template_ops.py` 联动治理。",
    "reviewedModules": [
      "tests/test_architecture_fitness.py",
      "core/services/scheduler/schedule_service.py",
      "core/services/scheduler/schedule_orchestrator.py",
      "core/services/scheduler/schedule_summary.py",
      "tests/regression_schedule_summary_freeze_state_contract.py",
      "tests/regression_due_exclusive_consistency.py",
      "tests/regression_legacy_external_days_defaulted_visible.py",
      "tests/regression_warmstart_failure_surfaces_degradation.py",
      "tests/regression_schedule_summary_end_date_type_guard.py",
      "tests/regression_dict_cfg_contract.py",
      "core/services/scheduler/batch_service.py",
      "core/services/scheduler/batch_template_ops.py",
      "core/services/scheduler/batch_excel_import.py",
      "web/routes/scheduler_batches.py",
      "web/routes/scheduler_excel_batches.py"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 5,
    "severity": {
      "high": 4,
      "medium": 1,
      "low": 0
    }
  },
  "milestones": [
    {
      "id": "round1",
      "title": "第一轮：plan 与架构适应度基线一致性复核",
      "status": "completed",
      "recordedAt": "2026-04-04T15:43:16.992Z",
      "summaryMarkdown": "### 复核动作\n- 对照 plan 中批次 A 的目标，核验 `tests/test_architecture_fitness.py` 当前账本状态。\n- 复核 `schedule_service.py` 当前体量与公开执行链。\n- 实跑 `python -m pytest -q tests/test_architecture_fitness.py -k \"known_oversize_entries_still_exceed_limit or file_size_limit or cyclomatic_complexity_threshold\"`，结果为 **3 passed**。\n\n### 关键事实\n1. `tests/test_architecture_fitness.py` 已经包含 `test_known_oversize_entries_still_exceed_limit()`，说明 plan 批次 A 中“新增白名单自校验”的动作已经落地，不再是待做事项。\n2. `_known_oversize_files()` 当前已不含 `core/services/scheduler/schedule_service.py`；同时该集合按现状只有 9 项，不再是 plan 文本里写的 10 项。\n3. `schedule_service.py` 当前总代码行数为 398 行，`run_schedule()` 只负责锁与门面转发，`_run_schedule_impl()` 已退化为“输入收集 -> 编排 -> 落库”的协调函数。\n4. 尽管超长白名单已清理，`tests/test_architecture_fitness.py` 里仍保留了 `core/services/scheduler/schedule_service.py:_run_schedule_impl` 的高复杂度白名单；结合本轮实测的复杂度结果，该条目已明显陈旧。\n\n### 轮次结论\n- 批次 A 不能再按原文执行；更合理的 revision 是把它改成“适应度账本陈旧项二次清理”，重点从超长白名单转向高复杂度白名单陈旧项。",
      "conclusionMarkdown": "plan 的首批次已与当前代码基线脱节，需要 revision 后再继续。",
      "evidence": [
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 43,
          "lineEnd": 56,
          "symbol": "_known_oversize_files"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 467,
          "lineEnd": 486,
          "symbol": "test_file_size_limit / test_known_oversize_entries_still_exceed_limit"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 566,
          "lineEnd": 568,
          "symbol": "known_violations"
        },
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 271,
          "lineEnd": 396,
          "symbol": "run_schedule / _run_schedule_impl"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        }
      ],
      "reviewedModules": [
        "tests/test_architecture_fitness.py",
        "core/services/scheduler/schedule_service.py"
      ],
      "recommendedNextAction": "先修订 plan 的批次 A 描述与完成标准，再继续评估后续批次。",
      "findingIds": [
        "plan-baseline-drift"
      ]
    },
    {
      "id": "round2",
      "title": "第二轮：排产摘要链深审（ScheduleService → Orchestrator → Summary）",
      "status": "completed",
      "recordedAt": "2026-04-04T15:43:51.307Z",
      "summaryMarkdown": "### 引用链复核\n- `ScheduleService._run_schedule_impl()` 通过 `orchestrate_schedule_run()` 传入 `build_result_summary_fn=build_result_summary`。\n- `orchestrate_schedule_run()` 在确认 `has_actionable_schedule=True`、分配版本号后，按关键字参数把 `cfg / version / batches / operations / results / freeze_meta / input_build_outcome / downtime_meta / resource_pool_meta / algo_stats / warning_merge_status` 全量传给 `build_result_summary()`。\n- 这意味着批次 B 不是单纯的文件拆分，而是 `result_summary` 合同装配点的重构；任何参数名、返回五元组、字段路径改变，都会直接打到主排产链。\n\n### 实测与事实\n- 实跑 `tests/regression_schedule_service_facade_delegation.py tests/regression_schedule_input_collector_contract.py tests/regression_schedule_orchestrator_contract.py tests/regression_schedule_summary_v11_contract.py tests/regression_schedule_summary_invalid_due_and_unscheduled_counts.py tests/regression_schedule_summary_algo_warnings_union.py tests/regression_schedule_summary_size_guard_large_lists.py tests/regression_schedule_summary_fallback_counts_output.py`，结果 **8 passed**。\n- `schedule_summary.py` 当前总长 923 行；plan 准备外提的冻结/退化区段主要集中在 385-685 行。即使整段搬走，主文件仍会保留 1-384 与 688-921 两大段，总量仍约 618 行，无法满足 `tests/test_architecture_fitness.py:test_file_size_limit()` 的 500 行门禁。\n- 同时 `build_result_summary()` 当前复杂度为 57，plan 虽提出外提冻结/退化逻辑，但没有明确第二层拆分点（如告警拼装、算法块装配、最终 dict 打包），无法证明可降到 ≤15。\n- 直接命中 `build_result_summary()` 的回归不止 plan 列出的 5 个；至少还有 `regression_schedule_summary_freeze_state_contract.py`、`regression_due_exclusive_consistency.py`、`regression_legacy_external_days_defaulted_visible.py`、`regression_warmstart_failure_surfaces_degradation.py`、`regression_schedule_summary_end_date_type_guard.py`、`regression_dict_cfg_contract.py`。\n\n### 轮次结论\n- 批次 B 的方向是对的，但当前 scope 不足以兑现“移除超长白名单 + 移除复杂度白名单”这两个完成标准；必须先 revision 拆分边界与回归清单。",
      "conclusionMarkdown": "批次 B 需要扩大拆分边界，并把直接依赖 `build_result_summary()` 的回归纳入必跑清单。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 344,
          "lineEnd": 351,
          "symbol": "_run_schedule_impl"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py",
          "lineStart": 102,
          "lineEnd": 178,
          "symbol": "orchestrate_schedule_run"
        },
        {
          "path": "core/services/scheduler/schedule_summary.py",
          "lineStart": 385,
          "lineEnd": 921,
          "symbol": "_extract_freeze_warnings / _freeze_meta_dict / _summary_degradation_state / build_result_summary"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 467,
          "lineEnd": 476,
          "symbol": "test_file_size_limit"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 569,
          "lineEnd": 601,
          "symbol": "known_violations"
        },
        {
          "path": "tests/regression_schedule_summary_freeze_state_contract.py",
          "lineStart": 61,
          "lineEnd": 104,
          "symbol": "test_schedule_summary_freeze_state_controls_hard_constraints"
        },
        {
          "path": "tests/regression_due_exclusive_consistency.py",
          "lineStart": 80,
          "lineEnd": 107,
          "symbol": "main"
        },
        {
          "path": "tests/regression_legacy_external_days_defaulted_visible.py",
          "lineStart": 96,
          "lineEnd": 130,
          "symbol": "main"
        },
        {
          "path": "tests/regression_warmstart_failure_surfaces_degradation.py",
          "lineStart": 107,
          "lineEnd": 138,
          "symbol": "main"
        },
        {
          "path": "tests/regression_schedule_summary_end_date_type_guard.py",
          "lineStart": 31,
          "lineEnd": 72,
          "symbol": "_build_summary_with_end_date"
        },
        {
          "path": "tests/regression_dict_cfg_contract.py",
          "lineStart": 216,
          "lineEnd": 252,
          "symbol": "_run_summary_case"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_summary.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "tests/regression_schedule_summary_freeze_state_contract.py"
        },
        {
          "path": "tests/regression_due_exclusive_consistency.py"
        },
        {
          "path": "tests/regression_legacy_external_days_defaulted_visible.py"
        },
        {
          "path": "tests/regression_warmstart_failure_surfaces_degradation.py"
        },
        {
          "path": "tests/regression_schedule_summary_end_date_type_guard.py"
        },
        {
          "path": "tests/regression_dict_cfg_contract.py"
        }
      ],
      "reviewedModules": [
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/schedule_orchestrator.py",
        "core/services/scheduler/schedule_summary.py",
        "tests/regression_schedule_summary_freeze_state_contract.py",
        "tests/regression_due_exclusive_consistency.py",
        "tests/regression_legacy_external_days_defaulted_visible.py",
        "tests/regression_warmstart_failure_surfaces_degradation.py",
        "tests/regression_schedule_summary_end_date_type_guard.py",
        "tests/regression_dict_cfg_contract.py"
      ],
      "recommendedNextAction": "先修订批次 B 的拆分边界与回归矩阵，再开始实现。",
      "findingIds": [
        "schedule-summary-scope-insufficient",
        "schedule-summary-regression-gap"
      ]
    },
    {
      "id": "round3",
      "title": "第三轮：批次更新 / 模板协调 / Excel 导入链深审",
      "status": "completed",
      "recordedAt": "2026-04-04T15:44:26.175Z",
      "summaryMarkdown": "### 引用链复核\n- 页面批量修改链：`web/routes/scheduler_batches.py:_bulk_update_one_batch()` → `BatchService.update()`。\n- 页面重建工序链：`web/routes/scheduler_batches.py:generate_ops()` → `BatchService.create_batch_from_template()` → `BatchService.create_batch_from_template_no_tx()` → `batch_template_ops.create_batch_from_template_no_tx()`。\n- Excel 确认导入链：`web/routes/scheduler_excel_batches.py:excel_batches_confirm()` → `BatchService.import_from_preview_rows()` → `batch_excel_import.import_batches_from_preview_rows()` → `_apply_row_no_tx()` → `svc.update_no_tx()` / `svc.create_no_tx()` / `svc.create_batch_from_template_no_tx()`。\n\n### 实测与事实\n- 实跑 `tests/regression_batch_template_autobuild_same_tx.py tests/regression_batch_service_strict_mode_template_autoparse.py tests/regression_batch_service_legacy_template_resolver_rejects_strict_mode.py tests/regression_batch_excel_import_reject_part_change_without_rebuild.py tests/regression_batch_import_unchanged_no_rebuild.py tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py`，结果 **6 passed**。\n- `BatchService` 当前总长 564 行，其中 `update()` 占 330-409 行，单独外提已足以让主文件降到 500 行以下。\n- 但 plan 锁定的复杂度热点之一 `BatchService.create_batch_from_template_no_tx()` 现在只是 528-555 行的薄转调；实际模板协调逻辑已经下沉在 `batch_template_ops.py:75-133`。\n- 与 plan 风险说明最相关的“改图号但不重建工序 / Excel strict 模式硬失败 / unchanged 行不得误触发写入”并不经过 `BatchService.update()`，而是落在 `batch_excel_import.py:_apply_row_no_tx()` 里。\n\n### 轮次结论\n- 批次 C 目前把“真实复杂链路”和“白名单陈旧条目”混在了一起：如果目的是清理架构账本，`create_batch_from_template_no_tx` 的白名单可以直接删；如果目的是守住 Excel 导入与模板协调语义，则必须把 `batch_excel_import.py` 纳入变更范围。",
      "conclusionMarkdown": "批次 C 需要重写目标文件清单：`batch_service.py` 以 `update()` 收口为主，Excel/模板语义则转到 `batch_excel_import.py + batch_template_ops.py`。",
      "evidence": [
        {
          "path": "core/services/scheduler/batch_service.py",
          "lineStart": 330,
          "lineEnd": 409,
          "symbol": "BatchService.update"
        },
        {
          "path": "core/services/scheduler/batch_service.py",
          "lineStart": 466,
          "lineEnd": 555,
          "symbol": "BatchService.create_batch_from_template / create_batch_from_template_no_tx"
        },
        {
          "path": "core/services/scheduler/batch_template_ops.py",
          "lineStart": 75,
          "lineEnd": 133,
          "symbol": "create_batch_from_template_no_tx"
        },
        {
          "path": "core/services/scheduler/batch_excel_import.py",
          "lineStart": 37,
          "lineEnd": 115,
          "symbol": "_apply_row_no_tx / import_batches_from_preview_rows"
        },
        {
          "path": "web/routes/scheduler_batches.py",
          "lineStart": 292,
          "lineEnd": 309,
          "symbol": "_bulk_update_one_batch"
        },
        {
          "path": "web/routes/scheduler_batches.py",
          "lineStart": 380,
          "lineEnd": 403,
          "symbol": "generate_ops"
        },
        {
          "path": "web/routes/scheduler_excel_batches.py",
          "lineStart": 354,
          "lineEnd": 360,
          "symbol": "excel_batches_confirm"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 549,
          "lineEnd": 550,
          "symbol": "known_violations"
        },
        {
          "path": "tests/regression_batch_excel_import_reject_part_change_without_rebuild.py",
          "lineStart": 58,
          "lineEnd": 79,
          "symbol": "test_batch_excel_import_rejects_part_change_without_rebuild"
        },
        {
          "path": "tests/regression_batch_import_unchanged_no_rebuild.py",
          "lineStart": 66,
          "lineEnd": 89,
          "symbol": "main"
        },
        {
          "path": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py",
          "lineStart": 64,
          "lineEnd": 86,
          "symbol": "main"
        },
        {
          "path": "core/services/scheduler/batch_service.py"
        },
        {
          "path": "core/services/scheduler/batch_template_ops.py"
        },
        {
          "path": "core/services/scheduler/batch_excel_import.py"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        },
        {
          "path": "web/routes/scheduler_excel_batches.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "tests/regression_batch_excel_import_reject_part_change_without_rebuild.py"
        },
        {
          "path": "tests/regression_batch_import_unchanged_no_rebuild.py"
        },
        {
          "path": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py"
        }
      ],
      "reviewedModules": [
        "core/services/scheduler/batch_service.py",
        "core/services/scheduler/batch_template_ops.py",
        "core/services/scheduler/batch_excel_import.py",
        "web/routes/scheduler_batches.py",
        "web/routes/scheduler_excel_batches.py"
      ],
      "recommendedNextAction": "先 revision 批次 C 的文件范围与完成标准，再进入实现。",
      "findingIds": [
        "batch-plan-mistargeted-hotspot",
        "batch-excel-chain-out-of-scope"
      ]
    }
  ],
  "findings": [
    {
      "id": "plan-baseline-drift",
      "severity": "high",
      "category": "maintainability",
      "title": "批次A与当前适应度账本已脱节",
      "descriptionMarkdown": "plan 仍把“为超长白名单新增自校验、移除 schedule_service 超长登记”当作待执行动作，但当前代码里这两件事都已经完成：`test_known_oversize_entries_still_exceed_limit()` 已存在，`_known_oversize_files()` 也已不含 `schedule_service.py`。继续按原批次执行会造成重复劳动，并且掩盖一个更真实的问题——高复杂度白名单里仍残留 `schedule_service.py:_run_schedule_impl` 这类已不再超阈值的陈旧登记。",
      "recommendationMarkdown": "把批次 A revision 为“账本陈旧项清理”：先清复杂度白名单里的 `schedule_service.py:_run_schedule_impl`，再批量检查是否还存在类似 stale 项。",
      "evidence": [
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 43,
          "lineEnd": 56,
          "symbol": "_known_oversize_files"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 479,
          "lineEnd": 486,
          "symbol": "test_known_oversize_entries_still_exceed_limit"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 567,
          "lineEnd": 568,
          "symbol": "known_violations"
        },
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 271,
          "lineEnd": 396,
          "symbol": "run_schedule / _run_schedule_impl"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        }
      ],
      "relatedMilestoneIds": [
        "round1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "schedule-summary-scope-insufficient",
      "severity": "high",
      "category": "maintainability",
      "title": "批次B当前拆分边界不足以移除 schedule_summary 超长登记",
      "descriptionMarkdown": "`schedule_summary.py` 当前共有 923 行，而 plan 计划外提的冻结/退化热点大致位于 385-685 行。即便这些段落全部迁出，主文件仍会保留 1-384 与 688-921 两块，总量仍明显高于 500 行门禁。与此同时，`build_result_summary()` 当前复杂度为 57；只把冻结/退化计算外提，并不能自动证明它会降到 ≤15。按现 scope 执行，最可能出现的结果是“模块拆了一部分，但 oversize 与 complexity 白名单仍删不掉”。",
      "recommendationMarkdown": "把批次 B revision 为“两段式拆分”：第一步先把冻结/退化/告警拼装整体外提；第二步再把 `build_result_summary()` 中的摘要对象装配与尾部 `algo_dict` 补丁拆成独立构造器，确保同时满足 500 行门禁与复杂度门禁。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_summary.py",
          "lineStart": 385,
          "lineEnd": 921,
          "symbol": "_extract_freeze_warnings / _freeze_meta_dict / _summary_degradation_state / build_result_summary"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 467,
          "lineEnd": 476,
          "symbol": "test_file_size_limit"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 569,
          "lineEnd": 601,
          "symbol": "known_violations"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py",
          "lineStart": 147,
          "lineEnd": 178,
          "symbol": "orchestrate_schedule_run"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_summary.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "tests/regression_schedule_summary_freeze_state_contract.py"
        },
        {
          "path": "tests/regression_due_exclusive_consistency.py"
        },
        {
          "path": "tests/regression_legacy_external_days_defaulted_visible.py"
        },
        {
          "path": "tests/regression_warmstart_failure_surfaces_degradation.py"
        },
        {
          "path": "tests/regression_schedule_summary_end_date_type_guard.py"
        },
        {
          "path": "tests/regression_dict_cfg_contract.py"
        }
      ],
      "relatedMilestoneIds": [
        "round2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "schedule-summary-regression-gap",
      "severity": "medium",
      "category": "test",
      "title": "批次B的必跑回归清单遗漏直接调用 summary 合同的用例",
      "descriptionMarkdown": "当前 plan 只列出一部分 `schedule_summary` 回归，但仓库里还有多组直接调用 `build_result_summary()` 的测试，分别覆盖冻结硬约束开关、交期边界一致性、历史外协周期回退可见性、OR-Tools 预热失败退化、`end_date` 类型守卫、dict/object 配置合同。如果只跑 plan 现有清单，`result_summary` 的若干细粒度合同可能被遗漏。",
      "recommendationMarkdown": "把所有直接调用 `build_result_summary()` 的回归并入批次 B 的必跑清单，至少覆盖冻结状态、交期边界、退化计数、配置快照、类型守卫五类合同。",
      "evidence": [
        {
          "path": "tests/regression_schedule_summary_freeze_state_contract.py",
          "lineStart": 61,
          "lineEnd": 104,
          "symbol": "test_schedule_summary_freeze_state_controls_hard_constraints"
        },
        {
          "path": "tests/regression_due_exclusive_consistency.py",
          "lineStart": 80,
          "lineEnd": 107,
          "symbol": "main"
        },
        {
          "path": "tests/regression_legacy_external_days_defaulted_visible.py",
          "lineStart": 96,
          "lineEnd": 130,
          "symbol": "main"
        },
        {
          "path": "tests/regression_warmstart_failure_surfaces_degradation.py",
          "lineStart": 107,
          "lineEnd": 138,
          "symbol": "main"
        },
        {
          "path": "tests/regression_schedule_summary_end_date_type_guard.py",
          "lineStart": 31,
          "lineEnd": 72,
          "symbol": "_build_summary_with_end_date"
        },
        {
          "path": "tests/regression_dict_cfg_contract.py",
          "lineStart": 216,
          "lineEnd": 252,
          "symbol": "_run_summary_case"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_summary.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "tests/regression_schedule_summary_freeze_state_contract.py"
        },
        {
          "path": "tests/regression_due_exclusive_consistency.py"
        },
        {
          "path": "tests/regression_legacy_external_days_defaulted_visible.py"
        },
        {
          "path": "tests/regression_warmstart_failure_surfaces_degradation.py"
        },
        {
          "path": "tests/regression_schedule_summary_end_date_type_guard.py"
        },
        {
          "path": "tests/regression_dict_cfg_contract.py"
        }
      ],
      "relatedMilestoneIds": [
        "round2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "batch-plan-mistargeted-hotspot",
      "severity": "high",
      "category": "maintainability",
      "title": "批次C误把陈旧白名单项当成当前复杂热点",
      "descriptionMarkdown": "plan 仍把 `core/services/scheduler/batch_service.py:create_batch_from_template_no_tx` 当成需要继续拆分的复杂函数，但当前 `BatchService.create_batch_from_template_no_tx()` 已经只剩一层薄包装；真正的模板协调逻辑位于 `core/services/scheduler/batch_template_ops.py:create_batch_from_template_no_tx`。继续按旧目标推进，会把真正的实现热点与陈旧白名单项混为一谈。",
      "recommendationMarkdown": "把批次 C 拆成两个子目标：一是直接清理 `batch_service.py:create_batch_from_template_no_tx` 的复杂度白名单；二是把真正的模板协调治理放在 `batch_template_ops.py`（必要时连同 `batch_excel_import.py`）里完成。",
      "evidence": [
        {
          "path": "core/services/scheduler/batch_service.py",
          "lineStart": 528,
          "lineEnd": 555,
          "symbol": "BatchService.create_batch_from_template_no_tx"
        },
        {
          "path": "core/services/scheduler/batch_template_ops.py",
          "lineStart": 75,
          "lineEnd": 133,
          "symbol": "create_batch_from_template_no_tx"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 549,
          "lineEnd": 550,
          "symbol": "known_violations"
        },
        {
          "path": "core/services/scheduler/batch_service.py"
        },
        {
          "path": "core/services/scheduler/batch_template_ops.py"
        },
        {
          "path": "core/services/scheduler/batch_excel_import.py"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        },
        {
          "path": "web/routes/scheduler_excel_batches.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "tests/regression_batch_excel_import_reject_part_change_without_rebuild.py"
        },
        {
          "path": "tests/regression_batch_import_unchanged_no_rebuild.py"
        },
        {
          "path": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py"
        }
      ],
      "relatedMilestoneIds": [
        "round3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "batch-excel-chain-out-of-scope",
      "severity": "high",
      "category": "test",
      "title": "批次C的风险说明主要发生在 Excel 导入链，但计划文件清单未纳入 batch_excel_import.py",
      "descriptionMarkdown": "plan 列出的回归里，多数都命中 `BatchService.import_from_preview_rows()` 再进入 `batch_excel_import.import_batches_from_preview_rows()`。其中“改图号必须开启自动生成工序”“UNCHANGED 行不得触发写入”“strict_mode 失败后不得残留批次/工序”都发生在 `_apply_row_no_tx()` 这一层，而不是 `BatchService.update()`。如果批次 C 不把 `batch_excel_import.py` 纳入变更范围，那么 plan 的测试集与改动对象会继续错位。",
      "recommendationMarkdown": "把 `core/services/scheduler/batch_excel_import.py` 加入批次 C 的文件清单与必跑回归说明；若只想消除 `batch_service.py` 超长债务，则应把 Excel 语义保护明确标成“受影响链路验证”，而不是默认由 `update()` 重构顺带覆盖。",
      "evidence": [
        {
          "path": "core/services/scheduler/batch_excel_import.py",
          "lineStart": 37,
          "lineEnd": 115,
          "symbol": "_apply_row_no_tx / import_batches_from_preview_rows"
        },
        {
          "path": "web/routes/scheduler_excel_batches.py",
          "lineStart": 354,
          "lineEnd": 360,
          "symbol": "excel_batches_confirm"
        },
        {
          "path": "tests/regression_batch_excel_import_reject_part_change_without_rebuild.py",
          "lineStart": 58,
          "lineEnd": 79,
          "symbol": "test_batch_excel_import_rejects_part_change_without_rebuild"
        },
        {
          "path": "tests/regression_batch_import_unchanged_no_rebuild.py",
          "lineStart": 66,
          "lineEnd": 89,
          "symbol": "main"
        },
        {
          "path": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py",
          "lineStart": 64,
          "lineEnd": 86,
          "symbol": "main"
        },
        {
          "path": "core/services/scheduler/batch_service.py"
        },
        {
          "path": "core/services/scheduler/batch_template_ops.py"
        },
        {
          "path": "core/services/scheduler/batch_excel_import.py"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        },
        {
          "path": "web/routes/scheduler_excel_batches.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "tests/regression_batch_excel_import_reject_part_change_without_rebuild.py"
        },
        {
          "path": "tests/regression_batch_import_unchanged_no_rebuild.py"
        },
        {
          "path": "tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py"
        }
      ],
      "relatedMilestoneIds": [
        "round3"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:ed1e4ebcdd6a0fae51081d00a326d104aa261a1dc542c076fa1dab29c06e49bb",
    "generatedAt": "2026-04-04T15:44:34.823Z",
    "locale": "zh-CN"
  }
}
```
