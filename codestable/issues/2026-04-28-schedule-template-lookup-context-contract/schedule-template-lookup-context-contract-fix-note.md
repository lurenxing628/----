---
doc_type: issue-fix
issue: 2026-04-28-schedule-template-lookup-context-contract
path: fast-track
fix_date: 2026-04-28
tags: [scheduler, external-merge, input-contract]
---

# 排产模板组上下文合同修复记录

## 1. 问题描述

深度 review 发现，排产输入在重建外协组合并上下文时，只判断模板工序和外部组是否能查到。

如果模板工序已经被逻辑删除、模板指向了别的图号的外部组、或者当前工序号不在外部组范围内，`lookup_template_group_context_for_op()` 仍会把它当成健康组合并上下文。

## 2. 根因

`BatchOperations` 不保存 `ext_group_id`，所以排产输入只能通过 `Batch.part_no + BatchOperation.seq` 回查当前 `PartOperations` 模板，再用模板上的 `ext_group_id` 查 `ExternalGroups`。

根因不是仓储层 `get()` 写错，也不是 builder 该再补一层判断，而是这个重建上下文的 lookup 层没有守住三条事实边界：

- 模板工序必须仍是 `active`。
- 外部组必须属于当前批次对应的图号。
- 当前工序号必须落在外部组的 `start_seq..end_seq` 范围内。

## 3. 修复方案

修复集中在 `core/services/scheduler/run/schedule_template_lookup.py`：

- 模板存在但状态不是 `active` 时，非 strict 返回 `template_missing` 退化事件，strict 直接抛 `ValidationError(field="template")`。
- 外部组存在但图号不匹配或范围不覆盖当前工序时，非 strict 返回 `external_group_missing` 退化事件，strict 直接抛 `ValidationError(field="ext_group_id")`。
- 不修改仓储层、不修改 builder、不新增公开退化 code，继续沿用已有 summary 和页面降级文案通道。
- 第二轮验证里 `full-test-debt` 抓到 lookup 主函数复杂度升高，所以又把主入口拆成“小函数校验 + 主流程编排”：主入口只负责串起批次、模板、外部组三步，具体合同判断落在局部 helper 里。

## 4. 改动文件清单

- `core/services/scheduler/run/schedule_template_lookup.py`
- `tests/test_schedule_template_lookup_contract.py`
- `tests/test_schedule_input_builder_external_merge_contract.py`
- `codestable/issues/2026-04-28-schedule-template-lookup-context-contract/schedule-template-lookup-context-contract-fix-note.md`

## 5. 验证结果

- 红灯验证：补测试后，修复前 `tests/test_schedule_template_lookup_contract.py tests/test_schedule_input_builder_external_merge_contract.py` 出现 12 个失败，能复现坏上下文被当成健康结果的问题。
- 修复后：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_schedule_template_lookup_contract.py tests/test_schedule_input_builder_external_merge_contract.py` 通过，30 passed。
- 相关回归：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_schedule_template_lookup_contract.py tests/test_schedule_input_builder_external_merge_contract.py tests/test_schedule_service_input_merge_context_contract.py tests/regression_schedule_summary_merge_context_degraded_code.py tests/regression_schedule_summary_input_fallback_contract.py tests/regression_schedule_input_builder_template_missing_surfaces_event.py tests/test_schedule_input_builder_strict_hours_and_ext_days.py tests/regression_external_merge_mode_case_insensitive.py` 通过，41 passed。
- 静态检查：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/run/schedule_template_lookup.py tests/test_schedule_template_lookup_contract.py tests/test_schedule_input_builder_external_merge_contract.py` 通过。
- 类型检查：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/services/scheduler/run/schedule_template_lookup.py` 通过，0 errors。
- 复杂度回归：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold` 通过，1 passed。
- full-test-debt：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py` 通过，731 collected，5 个已登记 xfail，0 unexpected failure。
- 治理台账：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check` 通过。
- CodeStable issue 文档校验：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --dir codestable/issues` 通过。
- 空白检查：`git diff --check` 通过。

## 6. 遗留事项

本次没有改 `get_template_and_group_for_op()` 的 tuple 兼容包装。它仍会丢掉结构化退化事件，只把不可用上下文表现成“没有模板或没有组”。这不影响本次排产输入修复，但如果后续要让页面提示也展示具体原因，可以另开 issue 让调用方直接消费 `TemplateGroupLookupOutcome`。
