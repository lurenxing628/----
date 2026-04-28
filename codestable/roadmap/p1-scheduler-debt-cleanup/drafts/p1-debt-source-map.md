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
- M0 当时的 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`：通过，`active_xfail_count=5`、`collected_count=700`、`collection_error_count=0`、`unexpected_failure_count=0`。
- M3 二次 review 后复核 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`：通过，`active_xfail_count=5`、`collected_count=744`、`collection_error_count=0`、`unexpected_failure_count=0`。
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
| P1-11 | PR-6 | complexity, test_coverage | 原事实源是 `complexity:core-services-scheduler-run-schedule_persistence-build_validated_schedule_payload` 登记；本轮已把 `build_validated_schedule_payload()` 的既有判断原样搬到私有 helper，`scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 已把该复杂度登记移出受控结构块。 | fixed-by-M5 | 是 | 否 | 已关闭复杂度登记；后续只按新增合同测试守住行为。 | 旧编号来源证据不足；当前复杂度事实源已解除，不等于 full-test-debt 减少。 |
| P1-12 | PR-6 | test_coverage | `core/services/scheduler/run/schedule_persistence.py` 中落库前错误优先级合同固定 out-of-scope、invalid、no-actionable 的先后关系；本轮新增 PR-6 专项测试覆盖 out-of-scope 与 invalid 同时出现、invalid 与有效行同时出现、全部非法但无可落库行。 | evidence-locked-by-M5 | 是 | 否 | 合同测试已补齐；不是台账登记项，后续只观察是否被新改动打破。 | 旧编号来源证据不足；有代码事实但不是 full-test-debt 或复杂度登记项。 |
| P1-13 | PR-6 | test_coverage | `core/services/scheduler/run/schedule_persistence.py` 中 `simulate` 和 auto-assign persist 写回合同仍是当前事实源；本轮新增 PR-6 专项测试覆盖 simulate 不改真实状态和资源、`auto_assign_persist=no`、外协隔离、已有资源不覆盖、只补空字段和 missing set 门控。 | evidence-locked-by-M5 | 是 | 否 | 合同测试已补齐；不是台账登记项，后续只观察是否被新改动打破。 | 旧编号来源证据不足；有代码事实但不是 full-test-debt 或复杂度登记项。 |
| P1-14 | PR-2 | complexity, test_coverage | `开发文档/技术债务治理台账.md` 的 `complexity:core-services-scheduler-freeze_window-build_freeze_window_seed` 登记仍在；当前入口是 `core/services/scheduler/run/freeze_window.py` 的 `build_freeze_window_seed`。 | open | 是 | 否 | PR-2 处理冻结窗口状态合同。 | 旧编号来源证据不足；当前事实源成立。 |
| P1-15 | PR-2 | test_coverage | `.limcode/plans/20260405_技术债务最终合并修复plan/subplans/SP07_排产主链边界收口.md` 记录 freeze/seed 语义；当前入口是 `core/services/scheduler/run/freeze_window.py` 的冻结窗口状态写入；M2 已补 `freeze_disabled_reason`、`config_degraded`、summary 公开形状和分析页展示测试。 | evidence-locked-by-M2 | 是 | 否 | 合同测试已补齐；后续只观察是否被新改动打破。 | 旧编号来源证据不足；当前冻结窗口状态合同已由 M2 锁住，不等于 full-test-debt 减少，也不代表 P1-14 复杂度关闭。 |
| P1-16 | PR-3 | complexity, test_coverage | 原事实源是 `load_machine_downtimes` 复杂度登记；M3 已把停机读取重复流程收口到内部 helper，`scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 已把该复杂度登记移出受控结构块；新增测试覆盖读取成功、无记录、整体失败、单设备失败保留健康设备。 | fixed-by-M3 | 是 | 否 | 已关闭复杂度登记并补合同测试；后续只观察是否被新改动打破。 | 旧编号来源证据不足；当前复杂度事实源已解除，不等于 full-test-debt 减少。 |
| P1-17 | PR-3 | complexity, test_coverage | 原事实源是 `extend_downtime_map_for_resource_pool` 复杂度登记；M3 已把资源池候选设备停机扩展复用同一读取 helper，`scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 已把该复杂度登记移出受控结构块；新增测试覆盖候选设备补停机、无停机不加空 key、部分失败保留成功设备和 collector 真实链路。 | fixed-by-M3 | 是 | 否 | 已关闭复杂度登记并补合同测试；后续只观察是否被新改动打破。 | 旧编号来源证据不足；当前复杂度事实源已解除，不等于 full-test-debt 减少。 |
| P1-18 | PR-7 | complexity, ui_contract, test_coverage | 原事实源是 `complexity:web-routes-domains-scheduler-scheduler_run-run_schedule` 登记；M6 已新增 `RunScheduleViewResult`，让 route 不再直接拆 summary/overdue 展示细节，`scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 已把该复杂度登记移出受控结构块。 | fixed-by-M6 | 是 | 否 | 已关闭复杂度登记并补 `/scheduler/run` 用户可见合同测试；后续只按新增测试守住行为。 | 旧编号来源证据不足；当前复杂度和页面合同事实源已收口，不等于 full-test-debt 减少。 |
| P1-19 | PR-8 | complexity, ui_contract, test_coverage | 原事实源是 `complexity:web-routes-domains-scheduler-scheduler_batches-batches_page` 登记；PR-8 已新增 `SchedulerBatchesPageViewModel`，让 route 不再直接拼批次行、配置面板和最近历史面板，`scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 已把该复杂度登记移出受控结构块。 | fixed-by-M6-PR-8 | 是 | 否 | 已关闭复杂度登记并补 `/scheduler/` 批次首页用户可见合同测试；后续只按新增测试守住行为。 | 旧编号来源证据不足；当前复杂度和页面合同事实源已收口，不等于 full-test-debt 减少。 |
| P1-20 | M7-A | oversize, startup_regression | 原事实源是 `oversize:web-bootstrap-launcher`；M7-A 后 `web/bootstrap/launcher.py` 从 1204 行降到 177 行，具体职责下沉到 `launcher_network.py`、`launcher_paths.py`、`launcher_processes.py`、`launcher_contracts.py`、`launcher_stop.py`，新模块仍在 `web/bootstrap/**/*.py` 扫描范围内。 | fixed-by-M7-A | 是 | 否 | 已关闭 launcher 超长登记；后续只按启动链测试和台账守住。 | 旧编号来源证据不足；当前 oversize 事实源已解除，不等于 full-test-debt 减少。 |
| P1-21 | M7-A | complexity, startup_regression | 原事实源是 `complexity:web-bootstrap-launcher-_classify_runtime_state`；M7-A 已把 runtime 状态分类拆到 `launcher_stop.py` 的小函数组合，受控刷新后旧复杂度登记移除。 | fixed-by-M7-A | 是 | 否 | 已关闭 runtime state 分类复杂度登记，并由启动链专项测试守住。 | 旧编号来源证据不足；当前复杂度事实源已解除。 |
| P1-22 | M7-A | complexity, startup_regression | 原事实源是 `complexity:web-bootstrap-launcher-_list_aps_chrome_pids` 和 `complexity:web-bootstrap-launcher-stop_runtime_from_dir`；M7-A 已拆 Chrome pid 查询、输出解析、停止复查和 runtime stop 主流程，并修正 APS Chrome 按旧 pid 误报失败的问题。复审后继续收紧到只认真实 `--user-data-dir` 参数，runtime 强杀必须先确认 pid 的真实可执行文件。 | fixed-by-M7-A | 是 | 否 | 已关闭 Chrome/stop runtime 复杂度登记；同批处理了 `acquire_runtime_lock` 这个 launcher 复杂度兄弟项。 | 旧编号来源证据不足；当前复杂度事实源已解除。 |
| P1-23 | M7-B | complexity, startup_regression | 原事实源是 `complexity:web-bootstrap-plugins-_apply_enabled_sources`；M7-B 已拆成来源判定、公开状态行整理、整体来源汇总三个小函数，并补真实插件默认关闭合同测试。 | fixed-by-M7-B | 是 | 否 | 已关闭 plugin enabled-source 复杂度登记，并用测试锁住默认关闭、来源汇总和错误脱敏。 | 旧编号来源证据不足；当前复杂度事实源已解除。 |
| P1-24 | M7-B | silent_fallback, startup_regression | M7-B 复核后未发现可包装成 open bug 的 plugin fallback；系统页补充 telemetry 和 conflict 可见信息，但不把 fixed/baseline 历史记录写成新修复。 | rechecked-by-M7-B | 否 | 否 | 继续按台账 fixed/baseline 状态观察；如果后续出现 open plugin fallback，再另开具体问题。 | 旧编号来源证据不足；当前事实源多为已修或基线记录，本轮只复核。 |
| P1-25 | M7-0 | unknown | 深挖后仍没有找到独立路径、台账条目或测试 nodeid。 | evidence-insufficient | 否 | 否 | 不得开修；已从 M7-A/M7-B 执行范围移除。 | 当前工作树证据不足。 |

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

## 8. PR-3 / M3 执行结果

M3 已按 PR-3 范围完成，结论如下：

- P1-16：`load_machine_downtimes` 已从复杂度登记中移除；新增停机读取成功、无记录、整体失败、单设备失败保留健康设备的合同测试。
- P1-17：`extend_downtime_map_for_resource_pool` 已从复杂度登记中移除；新增资源池候选设备补停机、无停机不加空 key、部分失败保留成功设备和 collector 真实链路测试。
- `MachineDowntimeRepository.list_active_after()` 已有真实查询测试，固定 active 行、结束时间晚于排产开始时间、跨过排产开始时间的记录、`start_time ASC, id ASC` 排序。
- 二次 review 后补齐边界测试：逐设备查询全部失败时仍按 partial count/sample 暴露，extend 查询前整体失败时保留原 `downtime_map` 并写 `DOWNTIME_EXTEND_FAILED_MESSAGE`。
- `scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 后，高复杂度登记从 42 降到 40；这是 complexity 改善，不是 full-test-debt 减少。
- 本轮没有关闭 active full-test-debt；二次 review 后 `tools/check_full_test_debt.py` 通过，仍是 5 条 operator-machine/query service 相关 xfail，`collected_count=744`。
- 本轮没有修改冻结窗口、优化器、落库、页面、runtime/plugin 或质量门禁工具。

## PR-6 / M5 执行回填

- P1-11 已按 complexity 关闭：`build_validated_schedule_payload()` 既有判断被原样搬到私有 helper，`scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 后高复杂度登记从 40 降到 39。
- P1-12 已按 test_coverage 锁证：新增测试覆盖 out-of-scope 优先、invalid + 有效行、全部非法但无可落库行三类错误边界。
- P1-13 已按 test_coverage 锁证：新增测试覆盖 simulate 不改真实状态和资源、`auto_assign_persist=no` 不补资源、外协不写 internal 资源、已有资源不覆盖、只补空字段、missing set 不包含时不写回。
- 本轮没有新增写前重读数据库工序的特殊检查；旧对象覆盖风险只作为观察项保留。
- 本轮没有改 summary、result_summary、schema、页面、route、viewmodel、repo、runtime/plugin 或质量门禁工具。
- 本轮没有减少 full-test-debt；`tools/check_full_test_debt.py` 通过，仍是 5 条 operator-machine/query service 相关 xfail，`collected_count=748`。
