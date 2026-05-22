---
doc_type: feature-acceptance
feature: 2026-05-18-scheduler-graph-candidate-schema-query
roadmap: networkx-scheduler-graph-introduction
roadmap_item: scheduler-graph-candidate-schema-query
status: accepted
accepted_at: 2026-05-18
---

# scheduler-graph-candidate-schema-query 验收记录

## 1. 完成范围

- 新增 `ScheduleCandidate`、`ScheduleCandidateRows`、`ScheduleCandidateSelection` 三张表。
- 新增 `core/infrastructure/migrations/v10.py`，并把当前 schema 版本升到 10。
- 新库和 v9 旧库都能得到三张候选表、索引和约束。
- `ScheduleCandidate.status` 只允许 `completed`、`failed`、`skipped`、`not_run`，不把 `adopted` 混进运行状态。
- `ScheduleCandidateSelection.role` 只允许 `adopted`、`baseline_best`、`critical_best`。
- `ScheduleCandidate.version` 没有外键到 `ScheduleHistory(version)`，避免绑到非唯一历史版本列。
- 新增候选模型和候选仓库，候选摘要、候选明细、角色映射可以按 version / candidate_key / role 写入和读取。
- `create_candidates()` 逐条插入拿 id，不依赖 `executemany.lastrowid`。
- `schedule_detail_query.py` 支持传入 plan rows CTE，让同一套明细 join 字段可复用到 `Schedule` 和 `ScheduleCandidateRows`。
- 新增 `SchedulePlanQueryService` 和 plan query repo：
  - `adopted` 永远从 `Schedule` 读。
  - `baseline_best` / `critical_best` 指向 `candidate_rows` 时从 `ScheduleCandidateRows` 读。
  - 合法 role 在旧历史里没有 selection 时，可见 fallback 到 adopted。
  - 未知 `plan_role` 直接报错。
  - selection 指向 `candidate_rows` 时，必须 `detail_saved=yes` 且实际存在候选明细，否则直接报错，不返回空成功。
- 补两份回归合同测试：候选表 schema 合同和统一方案查询合同。

## 2. 明确未做

- 没有实现 PR-7b 的候选生成、候选运行、关键链健康计算或自动择优。
- 没有修改 `optimize_schedule()` 主流程。
- 没有新增 `candidate_trial_mode`。
- 没有实现 PR-7c 的 `Schedule` / `ScheduleHistory` / 候选表同事务总入口。
- 没有改 `/scheduler/run` 路由。
- 没有改甘特图、周计划、资源派工、报表、导出或页面切换。
- 没有实现 PR-7e 的配置字段、时间预算、清理策略或性能证据。
- 没有引入 NetworkX import、新依赖、新数据库、后台续跑、多进程或 Python 3.9+ 语法。

## 3. 验收核对

- 新库 schema 能直接包含三张候选表和索引。
- v9 旧库迁移到当前版本后能补出三张候选表，旧数据不丢。
- 候选表 CHECK / UNIQUE / 外键 cascade 合同有效。
- `ScheduleCandidate.version` 不依赖 `ScheduleHistory(version)`。
- 候选仓库可以往返读取 candidate、rows 和 selection。
- `adopted` 查询沿用 `Schedule`，返回旧明细字段形状。
- `baseline_best` 指向 `candidate_rows` 时，返回同一字段形状，但数据来自候选明细。
- 合法但旧历史缺失的 `critical_best` 能返回 `fallback_to_adopted` 和可见中文 message。
- 拼错的 `plan_role` 直接报错。
- `candidate_rows` selection 没有保存明细或没有真实 rows 时直接报错，不静默返回空列表。

## 4. 已跑验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_schema_contract.py tests/regression_scheduler_candidate_plan_query_contract.py`：8 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/infrastructure/migrations/v10.py core/infrastructure/migrations/__init__.py core/infrastructure/migration_state.py core/models/schedule_candidate.py data/repositories/schedule_candidate_repo.py data/repositories/schedule_plan_query_repo.py data/repositories/schedule_detail_query.py core/services/scheduler/schedule_plan_query_service.py tests/regression_scheduler_candidate_schema_contract.py tests/regression_scheduler_candidate_plan_query_contract.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/infrastructure/migrations/v10.py core/infrastructure/migrations/__init__.py core/infrastructure/migration_state.py core/models/schedule_candidate.py data/repositories/schedule_candidate_repo.py data/repositories/schedule_plan_query_repo.py data/repositories/schedule_detail_query.py core/services/scheduler/schedule_plan_query_service.py tests/regression_scheduler_candidate_schema_contract.py tests/regression_scheduler_candidate_plan_query_contract.py`：0 errors。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/networkx-scheduler-graph-introduction/networkx-scheduler-graph-introduction-items.yaml --yaml-only`：通过。
- `git diff --check`：通过。

## 5. 对抗审核

- 第一轮实现后审核结论：BLOCKED。
- 发现的问题：selection 指向 `candidate_rows` 时，如果没有真实候选明细，查询会返回空结果，容易被误当成功。
- 修复方式：`SchedulePlanQueryService` 对 `candidate_rows` 增加 `detail_saved=yes` 和真实 rows 存在校验，并补两条回归测试。
- 复审结论：CLEAR，无阻塞问题。

## 6. roadmap 回写

- 已将 `scheduler-graph-candidate-schema-query` 从 `in-progress` 更新为 `done`。
- 已将 items.yaml 的 `feature` 指向 `.codestable/features/2026-05-18-scheduler-graph-candidate-schema-query/`。
- 已在 roadmap 主文档当前指针写明：下一步进入 PR-7b。
- 已保留用户确认的 PR-8 `scheduler-graph-resource-matching-report` 细化蓝本。

## 7. PR-7b 交接边界

- PR-7b 可以继承：候选表、候选仓库、统一方案查询服务、候选 rows 查询字段形状、候选明细缺失时显式报错。
- PR-7b 不能继承：候选生成、串行候选运行、关键链健康计算、自动择优、同事务持久化、页面方案切换、配置字段或性能证据。

## 8. Proof 口径

- 本轮为 dirty-worktree targeted proof。
- 尚未本地 commit，因此不能称为 clean-worktree proof。
- 如需 clean-worktree proof，需要先按用户要求本地提交，再运行 `scripts/run_quality_gate.py --require-clean-worktree`。
