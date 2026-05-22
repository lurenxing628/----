---
doc_type: feature-acceptance
feature: 2026-05-18-scheduler-graph-candidate-runner-selection
requirement:
roadmap: networkx-scheduler-graph-introduction
roadmap_item: scheduler-graph-candidate-runner-selection
status: accepted
summary: PR-7b 已完成内存候选生成、串行运行、自动择优和关键链健康计算，未接持久化和页面
tags: [scheduler, graph, networkx, candidate, selection]
---

# scheduler-graph-candidate-runner-selection 验收记录

## 结论

PR-7b 已完成。

大白话说，现在系统已经有一套“还不落库”的候选比较能力：同一份排产输入下，先跑原算法 baseline，再串行跑 3 / 5 / 7 档关键链权重候选；每个候选先按自己的临时配置准备图 ready 上下文，再交给优化器；最后按 `score_only` 或 `balanced` 策略在内存里选出采用方案。

本阶段没有把候选写进 `ScheduleCandidate` 表，没有改 `/scheduler/run` 主入口，没有改页面、导出或报表切换。这些继续由 PR-7c / PR-7d / PR-7e 承接。

## 已完成范围

- 新增 `schedule_candidate_specs.py`：稳定生成 `baseline + N 档 critical_chain`，默认 5 档，支持 3 / 5 / 7，候选 key 可复现。
- 新增 `schedule_candidate_health.py`：用纯函数按小时口径计算关键链健康，指标不足时返回 `unavailable`，不读库，不拿 NetworkX 图对象。
- 新增 `schedule_candidate_selection.py`：实现 `score_only` 和 `balanced`，raw score 复用 `OptimizationOutcome.best_score`，tuple 越小越好。
- 新增 `schedule_candidate_runner.py`：baseline 先跑，整次候选比较共用一个总 deadline，未启动候选标为 `skipped`，普通候选内部异常记为 `failed`，所有候选失败时直接阻断。
- runner 不走 `orchestrate_schedule_run()`，不分配正式 version，不调用 `persist_schedule()`。
- runner 进入优化器前用内存态 trial 配置锁住当前 `sort_strategy` / `dispatch_mode` / `dispatch_rule`，避免把候选试跑扩成多策略组合搜索。
- `ValidationError` 一律原样抛出，避免图上下文、输入、配置或数据范围错误被吞成“候选失败后选 baseline 成功”。

## 明确未做

- 未实现 PR-7c 的主链同事务持久化。
- 未写 `ScheduleCandidate` / `ScheduleCandidateRows` / `ScheduleCandidateSelection`。
- 未改甘特图、周计划、资源派工、分析页、独立报表或导出里的 `plan_role`。
- 未新增配置页字段、清理策略、性能守卫或候选续跑。
- 未修改用户正在并行处理的 PR-6 图指标文件。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_generation_contract.py tests/regression_scheduler_candidate_health_contract.py tests/regression_scheduler_graph_auto_selection_contract.py tests/regression_scheduler_candidate_runner_contract.py`
  - 结果：19 passed
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_schema_contract.py tests/regression_scheduler_candidate_plan_query_contract.py tests/regression_scheduler_candidate_generation_contract.py tests/regression_scheduler_candidate_health_contract.py tests/regression_scheduler_graph_auto_selection_contract.py tests/regression_scheduler_candidate_runner_contract.py`
  - 结果：27 passed
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_graph_on_mode_contract.py tests/test_sgs_internal_scoring_matches_execution.py tests/test_sgs_total_hours_cache.py`
  - 结果：45 passed
- `ruff check` 覆盖 PR-7b 新增实现和测试。
  - 结果：passed
- `pyright` 覆盖 PR-7b 新增实现和测试。
  - 结果：0 errors
- `git diff --check`
  - 结果：passed

## 对抗审核

- 设计阶段第一轮发现：runner 不能只调用 `optimize_schedule()`，必须先用候选配置准备图上下文。已修复并复审。
- 设计阶段第二轮发现：`algo_mode="greedy"` 不能独自锁住派工规则，trial 模式必须显式锁住排序、派工方式、派工规则三个轴。已修复并复审。
- 实现阶段发现：图上下文 `ValidationError` 会被当成单候选失败吞掉，baseline 仍可能被选中。已改为 `ValidationError` 直接 fail-fast，并补合同测试，复审结论 CLEAR。

## 后续承接

下一步是 PR-7c：把 PR-7b 的内存候选结果接入正式排产主链，在 adopted payload 校验后分配正式 version，并把 `Schedule`、`ScheduleHistory`、候选摘要、代表方案明细和角色映射同事务写入。
