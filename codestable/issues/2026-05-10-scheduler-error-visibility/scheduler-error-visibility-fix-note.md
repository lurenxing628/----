---
doc_type: issue-fix
issue: 2026-05-10-scheduler-error-visibility
status: completed
clean_proof_status: passed
path: fast-track
fix_date: 2026-05-10
tags: [scheduler, ui, error-message, auto-assign, python38]
---

# 排产错误提示可见性修复记录

## 1. 问题描述

浏览器排产测试里，复杂批次出现部分成功或失败时，页面原来只提示“排产执行遇到问题，请联系管理员查看日志。”。

对新用户来说，这句话没有告诉他到底该补设备、补人员、改日期，还是改工时，所以用户只能反复试。

继续下钻后，又确认了几个连带问题：

- 历史记录里只保留了错误样例，不保留完整错误清单，用户点进历史后仍然看不全。
- 缺设备/人员这类错误没有整理成表格，用户不知道具体该去补哪道工序。
- 自动补设备/人员成功后的工序，仍可能被旧的“缺资源扫描结果”误标成“需要补设备/人员”。
- 批次页批量操作没有选中任何批次时，可以点删除/备注；用回车提交时也绕得过前端提示。
- 未知优先级被显示成“普通”，用户会以为系统真的按普通优先级处理了。

## 2. 根因

底层排产算法已经能写出明确原因，例如“自制工序未补全设备或人员，无法排产：工序 UX-0510-E01_05”。

真正断掉的是“错误从底层一路传到页面”的链路：

- 保存排产结果时，`result_summary` 只保存 `errors_sample`，没有保存完整 `errors`，所以历史页和分析页没有足够材料可展示。
- 展示层为了防止内部错误泄露，把所有原始错误都压成同一句泛提示，结果把安全、可操作的业务错误也挡住了。
- 缺资源扫描发生在自动补资源之前，如果后面自动补成功，旧扫描结果没有按最终排产结果重新过滤，就会留下假阳性。
- 大结果保护只关心总体大小，缺少对完整错误列表和缺资源明细的可控裁剪规则。
- 批量表单的空选择校验只覆盖普通点击，没有覆盖回车提交和全选后清提示的交互细节。

## 3. 修复方案

- 排产保存时把完整安全错误列表写入 `result_summary.errors`，继续保留 `errors_sample` 作为摘要。
- 展示层区分两类错误：已知安全的业务错误直接给用户看；含路径、堆栈、数据库、密码等敏感痕迹的错误仍替换成泛提示。
- 历史页、分析页、周计划页、批次页都显示“查看 N 条错误”，不再只显示前几条。
- 缺设备/人员明细按“批次 / 工序 / 缺什么 / 去补充”展示，让用户能直接跳去补数据。
- 缺资源明细只保留最终仍未排入、仍缺资源的工序；自动补成功并已经排入的工序不再提示用户去补。
- 大结果保护会裁剪超大的 `errors` 和缺资源明细，同时保留总数、样例和“已截断”标记，避免页面和历史快照被大列表拖垮。
- 批次页批量删除/备注增加空选择提示，点击和回车都能拦住；全选后会清掉旧提示。
- 未知优先级显示为“未知”，不再伪装成“普通”。

二次安全收口：

- 用户可见错误已从 raw string 展示收紧为 `public_error_details` 结构化合同；`result_summary.errors` 继续保留，但只保存 public-safe message，不再保存原始内部错误。
- 历史 legacy 错误只通过严格正则 fallback 展示；含路径、堆栈、数据库、token、apikey 或内部字段尾巴的内容会泛化。
- 缺设备/人员明细的最终过滤已绑定 validator 输出的 `scheduled_op_ids`，optimizer raw results 中出现但未通过校验的工序仍会提示用户补资源。
- `errors`、`public_error_details` 和 `missing_internal_resource_ops` 已有独立 size guard 预算，minimal summary 对缺资源字段做限长与字段级清洗。
- 历史页、分析页、周计划页、批次页会显式提示错误列表或缺资源明细已截断。

## 4. 改动范围

- 排产运行和持久化：`core/services/scheduler/run/schedule_orchestrator.py`、`core/services/scheduler/run/schedule_persistence_errors.py`
- 排产摘要组装和大小保护：`core/services/scheduler/summary/schedule_summary_assembly.py`、`core/services/scheduler/summary/schedule_summary_types.py`、`core/services/scheduler/summary/summary_size_guard.py`
- 页面展示模型：`web/viewmodels/scheduler_summary_display.py`、`web/routes/enum_display.py`
- 页面模板和交互：`templates/scheduler/*.html`、`templates/system/history.html`、`web_new_test/templates/scheduler/*.html`、`static/js/scheduler_form_feedback.js`
- 用户说明：`web/viewmodels/page_manuals_system_history.py`
- 回归测试：新增和更新排产错误展示、缺资源明细、结果大小保护、批量表单交互、优先级显示相关测试。

## 5. 对抗性审查补出来的边界

- 后端审查指出：不能直接拿“自动补资源之前”的缺资源列表展示给用户，否则自动补成功的工序会被误报。已改为按最终排产结果过滤。
- 后端审查指出：完整错误列表可能很大。已补大小保护合同，超过限制时保留计数、样例和截断标记。
- 后端审查指出：安全前缀不能等于整条消息都安全。已增加敏感关键词拦截，避免把内部路径、堆栈、数据库等尾巴露给用户。
- 前端审查指出：批量操作回车提交会绕过空选择提示。已在回车路径补拦截。
- 前端审查指出：空选择报错后再全选，旧报错可能不消失。已改为全选/勾选后延迟检查并清除提示。

二次对抗性审查补出来的边界：

- 字符串前缀不是安全边界。已新增 `core/models/scheduler_public_errors.py`，只把结构化、清洗后的 public error 写入可访问摘要；legacy raw string 必须 fullmatch 白名单正则。
- “optimizer 结果里有 op_id”不等于“最终可落库”。缺资源过滤已优先使用 `ValidatedSchedulePayload.scheduled_op_ids`。
- 大列表不应挂靠 selected ids / overdue items 才裁剪。已给 errors 和缺资源明细独立裁剪 tier，并同步裁剪 `public_error_details`。
- 模板转义不能解决内部信息展示问题。缺资源 sample 与 viewmodel 均做字段限长、去换行和 missing fields allowlist。

## 6. 验证结果

已通过：

```bash
node --check static/js/scheduler_form_feedback.js
```

结果：通过。

```bash
.venv/bin/python -m ruff check core/services/scheduler/run/schedule_orchestrator.py core/services/scheduler/run/schedule_persistence_errors.py core/services/scheduler/summary/schedule_summary_assembly.py core/services/scheduler/summary/schedule_summary_types.py core/services/scheduler/summary/summary_size_guard.py web/viewmodels/scheduler_summary_display.py web/routes/enum_display.py web/viewmodels/page_manuals_system_history.py tests/regression_scheduler_user_visible_messages.py tests/regression_scheduler_summary_result_summary_contract.py tests/regression_schedule_summary_size_guard_large_lists.py tests/regression_scheduler_ui_range_feedback_contract.py tests/regression_scheduler_run_entry_layout_contract.py tests/regression_scheduler_batches_presenter_contract.py tests/test_enum_display_consistency.py tests/test_architecture_fitness.py
```

结果：通过。

```bash
.venv/bin/python -m pytest tests/regression_scheduler_user_visible_messages.py tests/regression_scheduler_summary_result_summary_contract.py tests/regression_schedule_summary_size_guard_large_lists.py tests/regression_scheduler_ui_range_feedback_contract.py tests/regression_scheduler_run_entry_layout_contract.py tests/regression_scheduler_batches_presenter_contract.py tests/test_enum_display_consistency.py tests/test_scheduler_batches_page_viewmodel.py tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold -q
```

结果：`102 passed`。

浏览器复验：

- 打开 `http://127.0.0.1:5063/scheduler/batches`，不选批次直接点批量删除，会在页面内提示“请先选择至少一个批次”。
- 在批量备注输入框按回车，也会留在当前页并显示同一条提示，不会误提交。
- 全选批次后，旧的空选择提示会消失，选中数显示为 8。
- 使用复杂缺资源排产数据生成 `v10` 部分成功历史后，`/system/history?version=10` 和 `/scheduler/analysis?version=10` 都显示“查看 6 条错误”和“需要补设备/人员：16 道工序”。
- 展开明细后，页面能看到每条缺资源错误，并能看到“批次 / 工序 / 缺设备、人员 / 去补充”的表格。
- 浏览器控制台没有出现前端报错。

全量质量门禁：

```bash
.venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree
```

结果：检查项全部跑完，但最终状态是 `passed_but_unbound`。

大白话解释：门禁里的测试、类型检查、风格检查和合同检查都已经跑过；但是因为当前工作区还有未提交改动，门禁不会把这次结果盖章成“绑定到某个干净提交的最终证明”。如果后续需要正式收口，提交后需要再跑一次不带 dirty 状态的质量门禁。

二次安全收口定点验证：

```bash
node --check static/js/scheduler_form_feedback.js
node --check static/js/gantt_boot.js
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_user_visible_messages.py tests/regression_scheduler_summary_result_summary_contract.py tests/regression_schedule_summary_size_guard_large_lists.py tests/regression_scheduler_ui_range_feedback_contract.py tests/regression_scheduler_run_entry_layout_contract.py tests/regression_scheduler_batches_presenter_contract.py tests/test_scheduler_run_view_result_contract.py tests/test_scheduler_batches_page_viewmodel.py tests/test_enum_display_consistency.py
```

结果：`129 passed`。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/models/scheduler_public_errors.py core/services/scheduler/run/schedule_persistence_errors.py core/services/scheduler/run/schedule_orchestrator.py core/services/scheduler/summary/schedule_summary_assembly.py core/services/scheduler/summary/schedule_summary_types.py core/services/scheduler/summary/summary_size_guard.py web/viewmodels/scheduler_summary_display.py tests/regression_scheduler_user_visible_messages.py tests/regression_scheduler_summary_result_summary_contract.py tests/regression_schedule_summary_size_guard_large_lists.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.gate.json
git diff --check
```

结果：ruff 通过；pyright `0 errors, 6 warnings`（既有 `core/services/scheduler/__init__.py` `__all__` warning）；`git diff --check` 通过。

干净工作区总门禁：本轮代码提交后需执行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

结果：已在提交后用干净工作区复跑 `--require-clean-worktree` 作为最终证明；若后续再次改动本文件或相关代码，需要重新跑门禁。
