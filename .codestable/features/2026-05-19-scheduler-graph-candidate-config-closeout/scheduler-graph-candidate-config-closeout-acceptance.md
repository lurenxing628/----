---
doc_type: feature-acceptance
feature: 2026-05-19-scheduler-graph-candidate-config-closeout
roadmap: networkx-scheduler-graph-introduction
roadmap_item: scheduler-graph-candidate-config-closeout
status: accepted
summary: PR-7e 已完成默认候选比较、配置字段、临时时间上限、清理策略和性能守卫的代码级收口
tags: [scheduler, graph, networkx, candidate, config]
---

# PR-7e 验收记录

## 结论

PR-7e 代码级收口已完成。

现在正式排产默认开启方案比较：系统会先跑原算法，再跑多档重点工序优先方案，并按配置自动选择最终采用方案。`off/report` 仍保留给排障和回滚，不跑候选比较。

## 已完成范围

- 新增并贯通 `graph_candidate_weight_count`、`graph_selection_policy`、`graph_overdue_tolerance_count`、`graph_tardiness_tolerance_ratio`。
- 新库默认 `graph_analysis_mode=on`；旧库已有 `off/report/on` 时不覆盖。
- 旧 preset 缺 PR-7e 字段时补默认值，不拒绝旧方案，也不覆盖用户已保存值。
- `run_time_budget_seconds` 作为本次排产临时时间上限，只走 run route 和输入收集，不写回高级设置。
- `graph_analysis_mode=on` 默认进入候选比较；`off/report` 仍只跑单方案。
- 主链先保留图检查合同：`on + block=yes + 有环` 仍在分配 version 前阻断；`on + block=no + 有环` 仍允许候选试跑，但重点工序候选内部按普通排法处理。
- 分析页只在候选摘要和候选明细完整时显示方案对比；没有开启或记录不完整时显示中文提示。
- 甘特图等页面把关系线说成“工序关系线”，不再让用户误以为这是切换重点工序方案。
- 新增 v11 索引和清理逻辑，孤儿候选通过 FK cascade 清 rows / selection，不删除正式 `ScheduleHistory` 或 `Schedule`。
- Python 3.8 / Win7 / 离线交付守卫覆盖本轮主要 Python 和前端文件。

## 修复过的阻塞问题

- 对抗审核发现：缺候选明细时分析页会假装展示完整方案对比。已改为记录不完整时只提示，不展示假表或方案链接。
- 对抗审核发现：Python 3.8 守卫扫描文件不全。已补全本轮主要触及文件。
- 对抗审核发现：性能测试解释的是测试手写 SQL，不是真实服务 SQL。已改为抓 `get_plan_time_span()` 实际执行 SQL 再做 `EXPLAIN QUERY PLAN`。
- 对抗审核发现：`on + 有环 + block=no` 的旧图合同和默认候选链路容易冲突。已让主链先保留阻断检查，再继续默认候选比较。

## 验证

- 浏览器验证：
  - 临时库：`/tmp/aps-pr7e-browser.tMI6Op/aps.db`。
  - 配置页：真实浏览器打开 `/scheduler/config`，页面显示“默认参与排产”“系统会先排普通方案，再试几档重点工序优先方案”等中文文案，未发现英文术语直出。
  - 分析页：真实浏览器打开 `/scheduler/analysis?version=2`，可见“方案对比”，三行分别是“最终采用 / 原算法最好 / 重点工序优先方案最好”，并显示自动采用原因。
  - 旧历史：手工造 `version=50` 无候选历史，分析页显示“本次没有开启方案对比，只生成了最终采用方案”，没有 `baseline_best` / `critical_best` 切换链接。
  - 周计划和资源排班：`adopted / baseline_best / critical_best` 三个角色页面均返回 200，页面上对应角色高亮显示，无 Traceback。
- 压力数据验证：
  - 正式排产 30 个批次、120 道工序，版本 2 成功。
  - 数据库对账：`ScheduleCandidate` 写入 6 条，包含 1 个 baseline 和 5 个重点工序优先候选；`ScheduleCandidateSelection` 写入 adopted / baseline_best / critical_best；`ScheduleCandidateRows` 写入 120 条代表方案明细；正式 `Schedule` 写入 120 条 adopted 明细。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_config_contract.py tests/regression_scheduler_candidate_py38_contract.py tests/regression_scheduler_candidate_performance_guard.py tests/regression_scheduler_candidate_analysis_contract.py tests/regression_migrate_v9_graph_config_defaults.py tests/regression_scheduler_graph_on_mode_contract.py`
  - 结果：61 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_*.py tests/regression_scheduler_graph_auto_selection_contract.py tests/regression_scheduler_graph_on_mode_contract.py tests/regression_scheduler_graph_cycle_policy_contract.py tests/scheduler_graph/test_ready_queue.py tests/scheduler_graph/test_metrics_impact.py tests/scheduler_graph/test_analysis_service.py`
  - 结果：191 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m py_compile` 覆盖本轮关键修改文件。
  - 结果：passed。
- `git diff --check`
  - 结果：passed。
- `node --check static/js/gantt.js && node --check static/js/gantt_contract.js`
  - 结果：passed。

## 最终收尾说明

- 本文件记录提交前已经完成的 targeted tests、浏览器验证和压力数据验证。
- 提交后的 clean-worktree 质量门禁结果以最终交付说明为准，避免在 dirty worktree 下冒充干净证明。
