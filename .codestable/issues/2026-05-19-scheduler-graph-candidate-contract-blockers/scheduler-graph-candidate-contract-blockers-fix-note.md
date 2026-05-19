---
doc_type: issue-fix
issue: 2026-05-19-scheduler-graph-candidate-contract-blockers
path: fast-track
fix_date: 2026-05-19
severity: P1
tags: [scheduler, graph, candidate, contract, pr7, python38]
---

# PR7 候选方案合同阻塞问题修复记录

## 1. 问题描述

PR-7a 到 PR-7d 已经进入完成状态后，复审又发现 3 个会影响候选方案可信度的阻塞问题：

- 关键链健康度判断太宽，几十秒或单个指标的小变化就可能把候选方案判成 `better`。
- 候选 runner 没把 `strict_mode=True` 传给配置快照校验，并且会把未知 `TypeError` / `RuntimeError` 这类合同错误吞成单个候选失败。
- plan_role 查询用 inner join 把坏 selection 过滤掉，导致 selection 指向不存在候选、或者 selection 集合缺少 adopted 时，看起来像正常 fallback 到最终采用方案。

这次修复只处理 PR-7a 到 PR-7d 的候选合同阻塞问题，不启用、不补做 PR-7e。

## 2. 根因

3 个问题的根因分别在不同边界：

- `schedule_candidate_health.py` 用固定 0.01 小时作为 neutral tolerance，并且 `score > 0` 就判 `better`，没有按基准链路规模做相对判断。
- `schedule_candidate_runner.py` 入口虽然接收 `strict_mode`，但配置快照校验固定传 `False`；候选运行捕获边界又写成 `except Exception`，把不该吞的合同错误变成 failed candidate。
- `schedule_plan_query_repo.py` 用 `JOIN ScheduleCandidate` 查询角色选项，坏 selection 会被 SQL 提前过滤；`schedule_plan_query_service.py` 看到空结果或缺 adopted 时又补默认 adopted，无法区分老数据和坏 PR7 数据。

## 3. 修复方案

本轮按最小范围修复：

- 关键链健康度的 finish / wait 改成按 baseline 值计算 5% 相对阈值；只有 reference 为 0 或缺失时才用原来的 fallback 小阈值。
- 健康度状态改成 `score >= 2` 才是 `HEALTH_BETTER`，`score <= -2` 才是 `HEALTH_WORSE`，中间都算 `HEALTH_SAME`。
- 候选 runner 的配置快照校验改成真实传入 `strict_mode=bool(strict_mode)`。
- 新增 `CandidateTrialFailure` 作为明确的“单个候选可以记 failed”的异常；runner 只捕获这个异常，不再宽泛捕获未知异常。
- plan_role 查询从 inner join 改成 left join，同时保留 `selection_candidate_id` 和 `resolved_candidate_id`，让 service 能看见 selection 指向的候选是否存在。
- service 只在完全没有 selection 时保留 legacy fallback；只要有 selection 但候选不存在，或者 selection 集合缺少 adopted，就直接报错。

## 4. 改动文件清单

- `core/services/scheduler/run/schedule_candidate_health.py`
- `core/services/scheduler/run/schedule_candidate_runner.py`
- `core/services/scheduler/schedule_plan_query_service.py`
- `data/repositories/schedule_plan_query_repo.py`
- `tests/regression_scheduler_candidate_health_contract.py`
- `tests/regression_scheduler_candidate_runner_contract.py`
- `tests/regression_scheduler_candidate_plan_query_contract.py`
- `.codestable/issues/2026-05-19-scheduler-graph-candidate-contract-blockers/scheduler-graph-candidate-contract-blockers-fix-note.md`

## 5. 验证结果

- 基线验证：修复前，PR7 相关 48 个现有测试通过，说明本轮 blocker 是缺少合同覆盖，不是已有测试已经红。
- 红灯验证：新增测试后，修复前出现 7 个失败，分别覆盖关键链小幅改善误判、单信号误判、runner strict_mode 未传递、TypeError / RuntimeError 被吞、dangling selection 静默 fallback、缺 adopted selection 静默 fallback。
- 核心修复后：`.venv/bin/python -m pytest tests/regression_scheduler_candidate_health_contract.py tests/regression_scheduler_candidate_runner_contract.py tests/regression_scheduler_candidate_plan_query_contract.py -q` 通过，25 passed。
- 自动择优周边：`.venv/bin/python -m pytest tests/regression_scheduler_candidate_health_contract.py tests/regression_scheduler_graph_auto_selection_contract.py -q` 通过，12 passed。
- runner / orchestrator 周边：`.venv/bin/python -m pytest tests/regression_scheduler_candidate_runner_contract.py tests/regression_schedule_orchestrator_contract.py -q` 通过，10 passed。
- plan_role 页面/报表链路：`.venv/bin/python -m pytest tests/regression_scheduler_candidate_gantt_plan_role_contract.py tests/regression_scheduler_candidate_week_plan_contract.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_scheduler_candidate_analysis_contract.py -q` 通过，15 passed。
- 保存和摘要链路：`.venv/bin/python -m pytest tests/regression_scheduler_candidate_persistence_contract.py tests/regression_scheduler_candidate_summary_contract.py tests/regression_schedule_orchestrator_contract.py -q` 通过，7 passed。
- 周边合同：`.venv/bin/python -m pytest tests/regression_schedule_service_passes_algo_stats_to_summary.py tests/regression_schedule_service_reschedulable_contract.py tests/test_schedule_service_input_merge_context_contract.py -q` 通过，4 passed。
- PR7 候选全量：`.venv/bin/python -m pytest tests/regression_scheduler_candidate_*.py tests/regression_scheduler_graph_auto_selection_contract.py -q` 通过，58 passed。
- 配置边界：`.venv/bin/python -m pytest tests/regression_scheduler_config_spec_sync_contract.py tests/regression_config_field_spec_contract.py tests/regression_graph_config_bootstrap_contract.py tests/regression_migrate_v9_graph_config_defaults.py tests/regression_scheduler_config_route_contract.py tests/regression_scheduler_graph_report_mode_service_contract.py tests/regression_scheduler_graph_on_mode_contract.py -q` 通过，83 passed。
- 空白检查：`git diff --check` 通过。
- 全量 pytest：`.venv/bin/python -m pytest` 运行到结束，结果是 3001 passed、1 failed；失败节点是 `tests/test_sp05_path_topology_contract.py::test_sp05_service_topology_and_strong_compatibility`，表现为旧兼容模块和新模块的类对象 identity 在全量顺序下不一致。单独复跑该节点通过，`tests/test_sp05_path_topology_contract.py` 全文件 13 passed。
- QualityGate：`.venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree --long-gate-cache` 跑完 13 步，long gate executed=9、failed=0，`collect-only` 收集 3002 个测试，`full-test-debt` 显示 `unexpected_failure_count=0`、`collection_error_count=0`、`active_xfail_count=0`，`ruff check`、`pyright`、架构 fitness、required regressions、技术债台账、启动运行时回归和 quickref/routes 都通过；因为工作区不是干净状态，manifest 状态是 `passed_but_unbound`，脚本退出码为 2，不能当作 clean-worktree proof。

以上验证是在当前 dirty worktree 上的 targeted proof，不是 clean-worktree proof；工作区里还有本轮开始前已经存在的图排产相关未提交改动。

## 6. 未做事项

- 没有启用 PR-7e。
- 没有新增 `candidate_comparison_enabled` 默认配置。
- 没有把 PR-7e 从 `planned` 改成 `done` 或 `in-progress`。
- 没有新增配置页字段、临时时间上限 UI、旧 preset 补字段、候选清理策略或性能守卫。
- 没有改旧的 off / report / on 排产入口合同。

## 7. 复审补充修复（2026-05-19）

本次复审又补抓到 2 个候选方案合同问题，仍然只收在 PR7a 到 PR7d 的边界里，不接 PR7e：

- 甘特图和资源派工切换到 `baseline_best` / `critical_best` 时，任务行已经来自候选方案，但超期标记还在读最终采用方案的 `ScheduleHistory.result_summary`，会把 adopted 的超期批次误贴到候选方案上。
- 候选 runner 给 health 评分传入的是 public、diagnostics、health_context 混合后的字典，虽然 health 内部已经防住 sample，但 runner 边界仍然太宽，未来容易把展示用 sample 重新带进决策。

实际修复：

- `SchedulePlanQueryService` 增加 `list_plan_overdue_base_rows()`，统一按 effective plan 解析 source table 和 candidate id。
- 新增 `plan_overdue_markers.py`，复用报表的 `compute_overdue_buckets()` 口径，把 plan rows 转成页面 marker 需要的超期批次集合。
- `GanttService` 和 `ResourceDispatchService` 在 adopted 时继续读历史摘要；在候选方案时改为按当前 effective plan rows 重新计算超期 marker。候选 marker 计算失败时只返回 degraded 提醒，不回退 adopted marker。
- `ResourceDispatchService` 查询 dispatch rows 时也使用 effective role，避免合法但缺失的 `critical_best` 已经 fallback 到 adopted 后，rows 和 marker 使用不同角色。
- `schedule_candidate_runner.py` 改为只把私有 `graph_health_context` 传入 health，不再 merge `graph_analysis_public` / `graph_analysis_diagnostics`。

补充测试：

- 甘特图新增候选方案超期正向测试，并新增 adopted 历史有超期但候选不超期时不标红的反向测试。
- 资源派工新增候选方案超期正向测试，并新增不复用 adopted 历史超期的反向测试。
- PlanQueryService 新增 overdue base rows 随 plan_role 切换的测试。
- Candidate runner 新增 diagnostics sample 不影响 health，以及缺少 `graph_health_context` 时不从 diagnostics sample 兜底的测试。

补充验证：

- `.venv/bin/python -m pytest -q tests/regression_scheduler_candidate_plan_query_contract.py tests/regression_scheduler_candidate_gantt_plan_role_contract.py tests/regression_scheduler_candidate_resource_dispatch_contract.py` 通过，20 passed。
- `.venv/bin/python -m pytest -q tests/regression_scheduler_candidate_health_contract.py tests/regression_scheduler_candidate_runner_contract.py tests/regression_scheduler_graph_auto_selection_contract.py` 通过，28 passed。
- `.venv/bin/python -m pytest -q tests/regression_scheduler_candidate_*.py tests/regression_scheduler_graph_auto_selection_contract.py tests/regression_scheduler_graph_on_mode_contract.py tests/scheduler_graph/test_ready_queue.py tests/scheduler_graph/test_metrics_impact.py tests/scheduler_graph/test_analysis_service.py` 通过，169 passed。
- `.venv/bin/python -m ruff check core/services/scheduler/schedule_plan_query_service.py core/services/scheduler/plan_overdue_markers.py core/services/report/report_engine.py core/services/scheduler/gantt_service.py core/services/scheduler/resource_dispatch_service.py core/services/scheduler/run/schedule_candidate_runner.py core/services/scheduler/run/schedule_candidate_health.py tests/regression_scheduler_candidate_plan_query_contract.py tests/regression_scheduler_candidate_gantt_plan_role_contract.py tests/regression_scheduler_candidate_resource_dispatch_contract.py tests/regression_scheduler_candidate_runner_contract.py` 通过。
- `git diff --check` 通过。

说明：本次没有跑 clean-worktree QualityGate；当前仍是带本轮未提交改动的工作区验证。
