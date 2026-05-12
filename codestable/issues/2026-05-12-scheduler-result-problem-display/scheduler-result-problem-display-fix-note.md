---
doc_type: issue-fix
issue: scheduler-result-problem-display
status: fixed
severity: medium
root_cause_type: ui-contract
tags:
  - scheduler
  - quality-gate
  - week-plan
  - history
---

# 排产结果问题提示修复记录

## 1. 问题描述

最近 4 个本地提交准备推送时，Git 的 pre-push 钩子会先跑 APS 质量门禁。门禁第 2 步 `tools/check_full_test_debt.py` 失败，失败节点是：

- `tests/test_architecture_fitness.py::test_no_silent_exception_swallow`

这个测试发现 `web/viewmodels/scheduler_summary_display.py` 里新增了一个没有登记的静默吞错点。

## 2. 根因

提交 `13c1ffc7 收紧排产完成状态缺失时的展示推断` 的目的本身是对的：旧排产摘要可能没有 `completion_status`，如果摘要里同时带着 `error_count`、`errors`、`errors_sample` 或 `public_error_details`，页面不能再只看数量就把结果说成成功。

问题出在实现方式：`_has_summary_errors()` 直接 `int(summary.get("error_count") or 0)`，再用 `except Exception: pass` 忽略解析失败。这样会让坏的 `error_count` 悄悄滑过去，也踩中了项目的“不能新增静默吞错”架构规则。

另外，原来给用户看的“完成状态未知”也不够明确。这个场景不是普通的不知道，而是排产摘要里已有错误或形态不可信，用户应该看到“排产结果有问题，需要检查”。

## 3. 修复方案

- 把 `error_count` 判断改成显式分支，不再靠抛异常再吞掉异常。
- 数字、数字字符串、`1.0` 这类值按数字判断；非空但不像数字的 `error_count` 当成摘要不可信，阻止页面继续推断为成功。
- 内部状态值仍保留 `unknown`，避免破坏历史数据合同；所有用户可见文案改成“排产结果有问题，需要检查”或短标签“有问题，需检查”。
- 同步更新回归测试，让后续修改不能再退回“完成状态未知”或静默吞错。

## 4. 改动文件清单

- `web/viewmodels/scheduler_summary_display.py`
- `web/viewmodels/scheduler_summary_status.py`
- `web/viewmodels/scheduler_run_view_result.py`
- `web/routes/domains/scheduler/scheduler_week_plan.py`
- `web/viewmodels/scheduler_history_summary.py`
- `web/viewmodels/scheduler_degradation_presenter.py`
- `tests/test_scheduler_summary_display_status_contract.py`
- `tests/test_scheduler_run_view_result_contract.py`
- `tests/regression_scheduler_run_surfaces_resource_pool_warning.py`
- `tests/regression_scheduler_week_plan_summary_observability.py`

## 5. 验证结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture_fitness.py::test_no_silent_exception_swallow tests/test_scheduler_summary_display_status_contract.py tests/test_scheduler_run_view_result_contract.py tests/regression_scheduler_run_surfaces_resource_pool_warning.py::test_scheduler_simulate_unknown_result_stays_on_batches_page tests/regression_scheduler_run_surfaces_resource_pool_warning.py::test_scheduler_simulate_non_dict_summary_does_not_crash_or_leak tests/regression_scheduler_run_surfaces_resource_pool_warning.py::test_scheduler_simulate_missing_completion_status_with_errors_stays_on_batches_page tests/regression_scheduler_run_surfaces_resource_pool_warning.py::test_scheduler_simulate_explicit_unknown_with_success_counts_stays_on_batches_page tests/regression_scheduler_week_plan_summary_observability.py::test_build_summary_display_state_does_not_infer_success_for_simulated_without_summary tests/regression_scheduler_week_plan_summary_observability.py::test_build_summary_display_state_respects_persisted_unknown_before_counts --tb=short`：`47 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture_fitness.py::test_file_size_limit tests/test_architecture_fitness.py::test_no_silent_exception_swallow tests/test_scheduler_summary_display_status_contract.py --tb=short`：`7 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check ...`：通过
- `git diff --check`：通过
- 排产展示链里已不再出现“完成状态未知”“模拟排产完成状态未知”“排产完成状态未知”。

## 6. 遗留事项

- `tools/check_full_test_debt.py` 当前每次都会重新跑完整测试并分类，推送前等待时间过长。建议单独开一条门禁加速改造：用源码、测试目录、门禁配置、Python 版本、pytest 参数和上次结果做指纹缓存；只有指纹完全一致时才复用上次 full-test-debt 结果，否则仍然重跑，避免为了提速牺牲真实性。
- 本次为避免继续浪费等待时间，已按用户反馈停止正在运行的 full-test-debt 全量检查；因此当前验证不是 clean-worktree 质量门禁证明。
