---
doc_type: feature-acceptance
feature: 2026-04-28-schedule-input-external-merge-contract
status: accepted
created: 2026-04-28
last_reviewed: 2026-04-28
roadmap: p1-scheduler-debt-cleanup
roadmap_item: schedule-input-external-merge-contract
---

# 排产输入与外协组合并合同验收

## 1. 验收结论

M1 已完成。它解决的不是“排产输入已经坏掉”的问题，而是把外协组合并这条关键行为从散落实现里固定下来，并把两个复杂度登记压回阈值内。

本次关闭：

- P1-8：`_build_algo_operations_outcome` 复杂度登记已由台账同步脚本移除。
- P1-9：`lookup_template_group_context_for_op` 复杂度登记已由台账同步脚本移除。

本次补证：

- P1-10：外协组合并行为已有 builder、lookup、service-summary 三层合同测试；它不是 full-test-debt，也不是复杂度登记项，所以只写“测试覆盖补齐”。

本次没有关闭 full-test-debt。当前 active xfail 仍是 5 条 operator-machine/personnel 相关登记。

## 2. 代码改动

- `core/services/scheduler/run/schedule_input_builder.py`：把外协组合并字段装配拆成小 helper，保留原有 strict/non-strict 语义、事件 code、字段形状和 `build_algo_operations(..., strict_mode, return_outcome)` 签名。
- `core/services/scheduler/run/schedule_template_lookup.py`：把模板缺失、外部组缺失、模板组分类拆成小 helper，保留 `TemplateGroupLookupOutcome` 的对外形状。
- `core/services/scheduler/run/schedule_input_contracts.py`：只读参照，没有修改。
- `开发文档/技术债务治理台账.md`：由 `scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 自动刷新，复杂度登记从 44 条降到 42 条。

本次没有修改页面、落库、冻结窗口、停机区间、runtime/plugin、质量门禁工具。

## 3. 测试改动

- `tests/test_schedule_input_builder_external_merge_contract.py`：覆盖内部工序不查模板、外协无组、`separate`、有效 `merged`、模板缺失、外部组缺失、非法 `total_days` 的 strict/non-strict 行为。
- `tests/test_schedule_template_lookup_contract.py`：覆盖模板缺失、无 `ext_group_id`、外部组缺失、`merged`/`separate`、缓存命中、strict fail fast。
- `tests/test_schedule_service_input_merge_context_contract.py`：让 `ScheduleService.run_schedule()` 真走 collector 和 input builder，再进入 summary，确认 `merge_context_degraded` 不会被普通 `input_fallback` 吞掉。

## 4. 已运行验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --dir codestable/roadmap/p1-scheduler-debt-cleanup`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_schedule_input_builder_external_merge_contract.py tests/test_schedule_template_lookup_contract.py tests/test_schedule_service_input_merge_context_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_schedule_input_builder_strict_hours_and_ext_days.py tests/regression_schedule_input_builder_template_missing_surfaces_event.py tests/regression_schedule_input_collector_contract.py tests/regression_schedule_input_collector_legacy_compat.py tests/regression_schedule_summary_merge_context_degraded_code.py tests/regression_schedule_summary_input_fallback_contract.py tests/test_sp05_path_topology_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/regression_external_merge_mode_case_insensitive.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_greedy_refactor_contracts.py tests/test_architecture_fitness.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/regression_legacy_external_days_defaulted_visible.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_schedule_service_facade_delegation.py tests/regression_schedule_orchestrator_contract.py tests/regression_optimizer_public_summary_projection_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/run/schedule_input_builder.py core/services/scheduler/run/schedule_template_lookup.py tests/test_schedule_input_builder_external_merge_contract.py tests/test_schedule_template_lookup_contract.py tests/test_schedule_service_input_merge_context_contract.py`
- `git diff --check`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree`

最终干净工作区门禁已通过；门禁收集到 719 个测试，full-test-debt proof 仍是 5 条 active xfail、0 条 unexpected failure。

## 5. 无新增兜底核对

本次生产代码没有新增业务兜底。新增 helper 只是把原入口里已有的判断搬出去：

- 外协无模板、缺外部组、非法 `total_days` 的 strict/non-strict 结果保持原样。
- 旧的可见退化事件继续保留，不新增 legacy private lookup。
- `BuildOutcome`、`TemplateGroupLookupOutcome`、`OpForScheduleAlgo` 对外形状保持不变。

## 6. CodeStable 回填

- roadmap 的 M1 和 PR-1 段落已写入执行结果。
- `drafts/p1-debt-source-map.md` 已更新 P1-8/P1-9/P1-10 状态。
- `p1-scheduler-debt-cleanup-items.yaml` 已把 PR-1 改为 `done`。
- PR-2 头部已写清 M1 已完成内容，以及 PR-2 不能继承的 proof 边界。

## 7. 后续承接

M2 从冻结窗口当前事实重新开始。不能把 M1 的外协组合并测试、full-test-debt 检查或复杂度关闭结论直接当作冻结窗口 proof。
