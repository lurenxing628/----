---
doc_type: roadmap-draft
roadmap: p1-scheduler-debt-cleanup
status: current
created: 2026-04-28
last_reviewed: 2026-04-28
---

# P1 scheduler debt cleanup M0 事实源映射

## 1. 结论

M0 本轮只做事实源和证明口径收口，没有改运行时代码、门禁脚本、pytest 收集钩子或台账写入逻辑。

本轮用 `rg -uuu` 在当前工作树里搜索 `P1-8` 到 `P1-25`，并排除 `.git/` 元数据和本 roadmap 目录自引用后，没有找到独立命中；这些旧 P1 编号目前只能视为本路线图整理出来的标签，不能当成旧仓库里已经存在的原生债务编号。

后续 PR 可以处理的是下面表格里的“当前事实源”。如果某一行写着“旧编号来源证据不足”，意思是：不能写“P1-x 已确认存在”，只能写“当前 PR 处理这些代码、台账或测试事实”。

## 2. 搜索和证明口径

本轮确认过的入口：

- `rg -uuu -n "P1-(8|9|10|11|12|13|14|15|16|17|18|19|20|21|22|23|24|25)" --glob '!.git/**' --glob '!codestable/**' .`：无输出，说明当前工作树除 `.git/` 元数据和 CodeStable 自引用外未找到独立 P1 编号来源。
- `rg -uuu -n "P1-(8|9|10|11|12|13|14|15|16|17|18|19|20|21|22|23|24|25)" codestable/roadmap/p1-scheduler-debt-cleanup`：只命中当前路线图和 items。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`：通过，`active_xfail_count=5`、`collected_count=700`、`collection_error_count=0`、`unexpected_failure_count=0`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，`test_debt_count=5`。

上面两条 proof 是当前点位的债务口径检查，不是 clean quality gate；只有在干净工作区跑过 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree`，才能声称 clean proof。

full-test-debt 的事实源是 `开发文档/技术债务治理台账.md` 的 `test_debt.entries`。当前 5 条 active xfail 都是 operator-machine/personnel 相关：

- `tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors`
- `tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error`
- `tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error`
- `tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error`
- `tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows`

所以 scheduler P1-8 到 P1-25 默认都不计入 full-test-debt 减少。只有关闭上述 active xfail 中的具体 `debt_id/nodeid`，并通过 `tools/check_full_test_debt.py` 与 `scripts/sync_debt_ledger.py check`，才允许写“full-test-debt 减少”。

## 3. 编号到当前事实源映射

| old_p1 | 当前归属 PR | 债务类型 | 当前事实源 | 当前状态 | 是否纳入路线图处理 | 是否计入 full-test-debt 减少 | 下一步动作 | 证据结论 |
|---|---|---|---|---|---|---|---|---|
| P1-8 | PR-1 | complexity, test_coverage | 原事实源是 `_build_algo_operations_outcome` 复杂度登记；本轮已把判断拆到小 helper，`scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 已把该复杂度登记移出受控结构块。 | fixed-by-M1 | 是 | 否 | 已关闭复杂度登记；后续只按新增合同测试守住行为。 | 旧编号来源证据不足；当前复杂度事实源已解除，不等于 full-test-debt 减少。 |
| P1-9 | PR-1 | complexity, test_coverage | 原事实源是 `lookup_template_group_context_for_op` 复杂度登记；本轮已把缺模板、缺外部组等判断拆到小 helper，`scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 已把该复杂度登记移出受控结构块。 | fixed-by-M1 | 是 | 否 | 已关闭复杂度登记；后续只按模板查询合同测试守住行为。 | 旧编号来源证据不足；当前复杂度事实源已解除，不等于 full-test-debt 减少。 |
| P1-10 | PR-1 | test_coverage | `core/services/scheduler/run/schedule_input_builder.py` 的外协组合并字段和退化事件仍是代码事实；本轮新增 builder、lookup、service-summary 链路测试直接覆盖。 | evidence-locked-by-M1 | 是 | 否 | 合同测试已补齐；不是台账登记项，后续只观察是否被新改动打破。 | 旧编号来源证据不足；有代码事实但不是 full-test-debt 或复杂度登记项。 |
| P1-11 | PR-6 | complexity, test_coverage | `开发文档/技术债务治理台账.md:541` 登记 `build_validated_schedule_payload` 复杂度；`core/services/scheduler/run/schedule_persistence.py:135` 是当前实现入口。 | open | 是 | 否 | PR-6 处理落库 payload 复杂度和合同。 | 旧编号来源证据不足；当前事实源成立。 |
| P1-12 | PR-6 | test_coverage | `core/services/scheduler/run/schedule_persistence.py:195` 到 `200` 固定 out-of-scope、invalid、no-actionable 错误优先级。 | evidence-only | 是 | 否 | PR-6 可补错误优先级测试。 | 旧编号来源证据不足；有代码事实但不是台账登记项。 |
| P1-13 | PR-6 | test_coverage | `core/services/scheduler/run/schedule_persistence.py:388` 到 `400` 是 `simulate` 和 auto-assign persist 当前写回入口。 | evidence-only | 是 | 否 | PR-6 可补 simulate/auto_assign_persist 合同测试。 | 旧编号来源证据不足；有代码事实但不是台账登记项。 |
| P1-14 | PR-2 | complexity, test_coverage | `开发文档/技术债务治理台账.md:515` 登记 `build_freeze_window_seed` 复杂度；`core/services/scheduler/run/freeze_window.py:235` 是当前实现入口。 | open | 是 | 否 | PR-2 处理冻结窗口状态合同。 | 旧编号来源证据不足；当前事实源成立。 |
| P1-15 | PR-2 | test_coverage | `.limcode/plans/20260405_技术债务最终合并修复plan/subplans/SP07_排产主链边界收口.md:41` 到 `45` 记录 freeze/seed 语义；`core/services/scheduler/run/freeze_window.py:93` 到 `109` 是当前 application status 入口；M2 已补 `freeze_disabled_reason`、`config_degraded`、summary 公开形状和分析页展示测试。 | evidence-locked-by-M2 | 是 | 否 | 合同测试已补齐；后续只观察是否被新改动打破。 | 旧编号来源证据不足；当前冻结窗口状态合同已由 M2 锁住，不等于 full-test-debt 减少，也不代表 P1-14 复杂度关闭。 |
| P1-16 | PR-3 | complexity, test_coverage | `开发文档/技术债务治理台账.md:502` 登记 `load_machine_downtimes` 复杂度；`core/services/scheduler/resource_pool_builder.py:118` 是当前实现入口。 | open | 是 | 否 | PR-3 处理 downtime load 合同。 | 旧编号来源证据不足；当前事实源成立。 |
| P1-17 | PR-3 | complexity, test_coverage | `开发文档/技术债务治理台账.md:489` 登记 `extend_downtime_map_for_resource_pool` 复杂度；`core/services/scheduler/resource_pool_builder.py:261` 是当前实现入口。 | open | 是 | 否 | PR-3 处理候选资源停机扩展合同。 | 旧编号来源证据不足；当前事实源成立。 |
| P1-18 | PR-7 | complexity, ui_contract, test_coverage | `开发文档/技术债务治理台账.md:671` 登记 `scheduler_run.run_schedule` 复杂度；`web/routes/domains/scheduler/scheduler_run.py:55` 是当前 route 入口。 | open | 是 | 否 | PR-7 处理 `/scheduler/run` view result。 | 旧编号来源证据不足；当前事实源成立。 |
| P1-19 | PR-8 | complexity, ui_contract, test_coverage | `开发文档/技术债务治理台账.md:658` 登记 `batches_page` 复杂度；`web/routes/domains/scheduler/scheduler_batches.py:39` 是当前页面入口。 | open | 是 | 否 | PR-8 处理 batches_page viewmodel。 | 旧编号来源证据不足；当前事实源成立。 |
| P1-20 | PR-9 | oversize, startup_regression | `开发文档/技术债务治理台账.md:136` 登记 `web/bootstrap/launcher.py` 超长文件；`.limcode/plans/20260405_技术债务最终合并修复plan/subplans/SP03_启动链静默回退专项.md:42` 到 `44` 把 launcher 归为 C 类台账化热点。 | open | 是 | 否 | PR-9 先作为支线，不插入排产主链。 | 旧编号来源证据不足；当前事实源成立。 |
| P1-21 | PR-9 | complexity, startup_regression | `开发文档/技术债务治理台账.md:593` 登记 `_classify_runtime_state` 复杂度；`web/bootstrap/launcher.py:999` 是当前实现入口。 | open | 是 | 否 | PR-9 处理 runtime state 分类，必须有启动链专项测试。 | 旧编号来源证据不足；当前事实源成立。 |
| P1-22 | PR-9 | complexity, startup_regression | `开发文档/技术债务治理台账.md:606` 登记 `_list_aps_chrome_pids` 复杂度；`开发文档/技术债务治理台账.md:632` 登记 `stop_runtime_from_dir` 复杂度；`web/bootstrap/launcher.py:1140` 是 stop runtime 入口。 | open | 是 | 否 | PR-9 处理 Chrome/stop runtime，不能模糊写成 plugin。 | 旧编号来源证据不足；当前事实源成立。 |
| P1-23 | PR-9 | complexity, startup_regression | `开发文档/技术债务治理台账.md:645` 登记 `web/bootstrap/plugins.py::_apply_enabled_sources` 复杂度；`web/bootstrap/plugins.py:49` 是当前实现入口。 | open | 是 | 否 | PR-9 处理 plugin enabled source 合同。 | 旧编号来源证据不足；当前事实源成立。 |
| P1-24 | PR-9 | silent_fallback, startup_regression | `开发文档/技术债务治理台账.md:2694` 到 `2804` 记录 plugin fallback 条目，多数状态为 `fixed`。 | mostly-fixed | 否 | 否 | PR-9 执行前只能复核是否有仍 open 的 plugin fallback，不能默认当作未修债务。 | 旧编号来源证据不足；当前事实源多为已修记录。 |
| P1-25 | PR-9 | unknown | items 只把 P1-25 放进 runtime/plugin/infra 支线，没有找到独立路径、台账条目或测试 nodeid。 | evidence-insufficient | 否 | 否 | 不得开修；先补具体事实源，或从后续执行范围移除。 | 当前工作树证据不足。 |

## 4. 后续 PR 禁止项

- 禁止后续 PR 只引用旧 P1 编号直接开修；必须引用本表里的当前事实源。
- 禁止新增 active xfail，禁止把排产问题登记成 full-test-debt 来消化失败。
- 禁止把复杂度减少、静默回退减少、测试覆盖增加、页面合同补测、启动链专项通过，说成 full-test-debt 减少。
- 禁止修改 `tools/test_registry.py`、`tools/quality_gate_shared.py`、`tools/test_debt_registry.py`、`tools/check_full_test_debt.py`、`tools/collect_full_test_debt.py`、`tests/conftest.py`、`tests/main_style_regression_runner.py`、`scripts/run_quality_gate.py`、`scripts/sync_debt_ledger.py` 的运行逻辑来让 M0 变绿。
- 禁止新增 `if/fallback/兜底/静默回退` 逻辑；如果后续 PR 觉得必须新增，先停下来说明原因，不得直接改。
- 禁止声称 clean proof，除非在干净工作区跑过 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree`。

## 5. PR-1 承接摘要

PR-1 只能承接 P1-8、P1-9、P1-10 的当前事实源：

- `_build_algo_operations_outcome` 复杂度登记和当前实现入口。
- `lookup_template_group_context_for_op` 复杂度登记和当前实现入口。
- 外协组合并字段的代码事实和合同测试缺口。

PR-1 不允许处理页面、落库、冻结、停机、runtime、plugin，也不允许写“full-test-debt 已减少”。如果 PR-1 执行时发现必须改证明工具或新增兜底，应立即停下另开任务。

## 6. PR-1 / M1 执行结果

M1 已按 PR-1 范围完成，结论如下：

- P1-8：`_build_algo_operations_outcome` 的复杂度登记已被脚本移除；这是 complexity 债务关闭，不是 full-test-debt 减少。
- P1-9：`lookup_template_group_context_for_op` 的复杂度登记已被脚本移除；这是 complexity 债务关闭，不是 full-test-debt 减少。
- P1-10：外协组合并合同已由新增测试锁住，包括内部工序不查模板、外协无组、`separate`、有效 `merged`、模板缺失、外部组缺失、非法 `total_days` 的 strict/non-strict 行为，以及服务汇总层保留 `merge_context_degraded` 且不混入普通 `input_fallback`。
- 本轮没有关闭 active full-test-debt；`tools/check_full_test_debt.py` 通过后仍是 5 条 operator-machine/personnel 相关 xfail。
- 本轮没有修改页面、落库、冻结窗口、停机区间、runtime/plugin 或质量门禁工具。

## 7. PR-2 / M2 执行结果

M2 已按 PR-2 范围完成，结论如下：

- P1-14：`build_freeze_window_seed` 的复杂度仍为 26/15，保持 open，没有运行台账自动刷新移除该登记。
- P1-15：冻结窗口状态合同已由新增测试锁住，包括普通 disabled 原因、配置读取降级、strict fail closed、summary 不把 degraded 伪装成 disabled，以及分析页不把 `enabled=no + freeze_state=degraded` 显示成普通未启用。
- 本轮没有关闭 active full-test-debt；`tools/check_full_test_debt.py` 通过后仍是 5 条 operator-machine/query service 相关 xfail。
- 本轮没有修改停机区间、资源池、落库、runtime/plugin 或质量门禁工具。
- 本轮已补录 CodeStable feature 承接：`codestable/features/2026-04-28-freeze-window-disabled-contract/`。
