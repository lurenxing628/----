---
doc_type: issue-fix
issue: 2026-06-01-workbench-first-round-deep-chain-hardening
status: done
path: fast-track
fix_date: 2026-06-01
tags: [aps, workbench, dashboard, resource-dispatch, execution-feedback]
---

# 工作台前 3 项引用链下钻加固记录

## 1. 问题描述

用户要求复查 `aps-frontend-workbench` roadmap 第 1~3 项是否真的沿引用链下钻到根因。本轮用 4 个只读 SubAgent 分别审了第 1 项、第 2 项、第 3 项和第 1~3 项横向链路。

审查结论是主链路成立，但发现两个需要补的底层问题：

- 现场记录直连写入接口已经要求完整资源派工查询上下文，但没有确认 `op_id + schedule_id + batch_id` 真的属于当前查询结果。
- 首页值班台读取今日正式计划失败时，原来只返回空列表，会让页面看起来像“今天没有现场情况待确认”，而不是提示“今日计划暂时读不到”。

## 2. 根因

- `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py` 的 `_request_plan_identity_payload()` 只取 `plan_identity`，后续服务层会校验正式方案和任务自洽，但没有把任务反查到本次资源派工查询返回的 `rows`。
- `web/routes/dashboard.py` 的 `_load_today_rows()` 出错时只返回 `[]`；`web/viewmodels/dashboard_workbench.py` 只知道没有今日行，不知道这是读取失败。

## 3. 修复方案

- 在现场记录写入路由里，确认当前查询已经是最新正式可写方案后，再检查提交的 `op_id + schedule_id + batch_id` 是否存在于当前资源派工查询结果；不存在则返回 `schedule_mismatch`，不写现场事件。
- 正式可写场景下，`schedule_id` 或 `batch_id` 缺任何一个都不再放行给后续服务层补齐，而是在路由层直接拒绝，避免 `/actual` 直连绕过查询归属校验。
- 让首页路由把“今日正式计划读取失败”的中文原因传给首页 ViewModel；ViewModel 把它渲染成数据缺口，不再静默当成没有现场待确认。

## 4. 改动文件清单

- `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py`
- `web/routes/dashboard.py`
- `web/viewmodels/dashboard_workbench.py`
- `tests/regression_operation_execution_feedback_routes.py`
- `tests/regression_dashboard_workbench_contract.py`

## 5. 验证结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_feedback_routes.py::test_write_post_rejects_task_outside_current_dispatch_query tests/regression_dashboard_workbench_contract.py::test_dashboard_workbench_today_rows_failure_does_not_fake_empty_site_gap tests/regression_operation_execution_feedback_routes.py::test_write_post_requires_query_plan_identity_and_batch_match tests/regression_dashboard_workbench_contract.py::test_dashboard_workbench_execution_fact_failure_does_not_fake_site_gap -vv --tb=short -p no:cacheprovider`：4 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_feedback_routes.py::test_actual_post_rejects_outside_query_even_when_batch_id_is_missing tests/regression_operation_execution_feedback_routes.py::test_write_post_rejects_task_outside_current_dispatch_query tests/regression_operation_execution_feedback_routes.py::test_write_post_rejects_candidate_preview_and_history_query_context tests/regression_operation_execution_feedback_routes.py::test_write_post_requires_query_plan_identity_and_batch_match -vv --tb=short -p no:cacheprovider`：4 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_workbench_links_contract.py tests/regression_workbench_nav_entry_contract.py tests/regression_dashboard_workbench_contract.py tests/regression_aps_workbench_first_round_flow_contract.py tests/regression_operation_execution_feedback_routes.py tests/regression_resource_dispatch_site_records_frontend_contract.py -p no:cacheprovider`：51 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py web/routes/dashboard.py web/viewmodels/dashboard_workbench.py tests/regression_operation_execution_feedback_routes.py tests/regression_dashboard_workbench_contract.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py web/routes/dashboard.py web/viewmodels/dashboard_workbench.py tests/regression_operation_execution_feedback_routes.py tests/regression_dashboard_workbench_contract.py`：0 findings。
- `git diff --check`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree`：16/16 步完成，功能检查通过；因为当前工作区未提交，manifest 标记为 `passed_but_unbound`，不能当作 clean-worktree 最终证明。

## 5.1 SubAgent 复审

- 第 1 轮只读复查 4 个 SubAgent：
  - `Volta 019e8213-ade0-7980-8c70-d2f6b5dadd79`：发现现场记录写入未校验任务属于当前查询结果；已关闭。
  - `Nietzsche 019e8214-1083-7052-bd13-eb0e5d1520cd`：确认顶层计划工作台入口按设计是无上下文只读入口；已关闭。
  - `Confucius 019e8214-10fe-7122-b5c8-3f2f07b3ae6e`：发现今日计划读取失败会静默变成没有现场缺口；已关闭。
  - `Gauss 019e8214-1171-7803-9994-3ae6bbfaa4fe`：确认第 1~3 项最窄主链路成立，并指出旧“常用工作区”仍是无上下文旁路；已关闭。
- 第 2 轮改后复审：
  - `Chandrasekhar 019e821f-2edd-73a0-8b24-0bce59c19b7e`：首页数据缺口链路 OK；已关闭。
  - `Kepler 019e821f-2e62-7c83-b1ad-ab9f9fd77db8`：发现 `/actual` 缺 `batch_id` 可绕过第一版校验；已关闭。
  - `Copernicus 019e8225-0ad3-7d72-9b9a-9241e623218b`：确认第二版写接口校验无必须改绕过点；已关闭。

## 5.2 Claude Code 复审

- delegate 会话：`claude-first-round-deep-chain-hardening-review-20260601-155449-53282`，已读完结果后停止并移除桥接记录。
- Claude Code SubAgent 证明：
  - `Shannon`：角色为首页“今日计划读取失败→数据缺口”链路与优先级复审，`model: opus`，结论 OK，无缺陷。
  - `Turing`：角色为写接口三元组归属校验正确性与全路由覆盖复审，`model: opus`，结论 OK，无 P0/P1。
- Claude Code 复审结论：阻塞项 0；确认归属校验不是死代码，`/start` 与 `/actual` 都覆盖，缺 `batch_id` / `schedule_id` 不再绕过，首页数据缺口优先级未被破坏。
- 清理结果：本轮 Claude delegate 和旧的 `claude-gantt-detail-review-20260601-141121-85106` delegate 都已停止并移除 env 记录；delegate 列表为空；只保留默认 `claude-visible` tmux 会话；桥接遗留 Terminal 空窗口已关闭。

## 6. 遗留事项

- 第 2 项顶层菜单按设计是无上下文只读入口；如果以后要求从任意页面顶栏带当前版本、方案和日期，需要把 `templates/components/ui_macros.html` 的 `workbench_nav_menu()` 改成接收 `WorkbenchLink` 列表。
- 首页旧“常用工作区”仍是无上下文链接，不属于第 1~3 项最窄工作台主链；如果后续要求首页所有入口都带上下文，应另开小任务处理。
