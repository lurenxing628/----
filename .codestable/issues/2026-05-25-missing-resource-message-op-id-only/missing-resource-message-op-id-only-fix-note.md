---
doc_type: issue-fix
issue: 2026-05-25-missing-resource-message-op-id-only
status: fixed
path: fast-track
fix_date: 2026-05-25
tags: [scheduler, sgs, validation-message]
---

# 缺设备或人员只显示内部工序编号修复记录

## 1. 问题描述

排产走 SGS 智能派工评分时，如果自制工序缺设备或人员，页面只提示内部数据库工序编号，例如“工序编号=131”。调度员无法直接知道是哪一个批次、哪一道工序、哪个工种，以及具体缺设备还是缺人员。

## 2. 根因

`core/algorithms/greedy/dispatch/sgs_scoring.py` 的 `_score_internal_candidate()` 能拿到算法工序对象。这个对象里已经有 `batch_id`、`op_code`、`seq`、`op_type_name`、`machine_id`、`operator_id`。但原来的 `ValidationError` 只把内部 `op_id` 拼进消息，也没有写 `details.user_message`，所以 `/scheduler/run` 和 `/scheduler/simulate` 页面只能展示这条难懂的原始消息。

## 3. 修复方案

在 SGS 评分阶段发现缺资源时，先用当前工序对象组装一条调度员能看懂的中文消息。消息包含批次号、工序号、顺序、工种名和缺失字段；同时把这条消息放入 `details["user_message"]`，供两个页面入口直接展示。内部 `op_id` 保留在 `details` 里，方便日志和排查，但不再作为前台唯一提示。

## 4. 改动文件清单

- `core/algorithms/greedy/dispatch/sgs_scoring.py`
- `tests/regression_scheduler_missing_resource_message.py`

## 5. 验证结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_missing_resource_message.py` 通过，5 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_sgs_atc_penalize_missing_resources.py tests/regression_sgs_scoring_fallback_unscorable.py` 通过，3 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_scheduler_run_view_result_contract.py::test_scheduler_run_route_flashes_missing_resource_user_message tests/regression_scheduler_run_surfaces_resource_pool_warning.py::test_scheduler_simulate_missing_completion_status_with_errors_stays_on_batches_page tests/regression_scheduler_user_visible_messages.py::test_scheduler_template_validation_fields_accept_explicit_public_user_message` 通过，4 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/algorithms/greedy/dispatch/sgs_scoring.py tests/regression_scheduler_missing_resource_message.py` 通过。

## 6. 遗留事项

当前工作区在本次修复前已有大量未提交改动，因此这次验证不是 clean-worktree proof。本次只新增和修改上述文件，未清理或回退其它已有改动。
