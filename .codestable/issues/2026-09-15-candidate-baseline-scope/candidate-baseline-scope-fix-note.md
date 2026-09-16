# 旧正式计划工序导致候选分析误报资料损坏

- 日期：2026-09-15。
- 范围：已授权的工作台手动验收缺陷修复。保留已有工作区改动；未运行全门禁、`run_quality_gate` 或整仓测试；未构建静态资源、重启服务或操作浏览器。

## 现象与根因

5005 手动验收候选 `dc31eb312fb33ef3dd1be44afd8fb408ac3320d7a07bfcad` 选了 23 批、62 道工序。入场同时保留了 6 道此前正式计划工序的执行资料，总共 68 条执行投影。这 6 道来自 v3 的 `QA-20260509-B07/B11`，最新 v14 只包含 18 条安排。

`run_jobs_facts.run_execution_projections` 按“选定工序 + 各工序最后一次正式安排”捕获执行资料；此前 `AdmissionBaseline._execution` 却按“选定工序 + 最新版本安排”检查投影集合，因而把合法的历史执行资料当作多余记录，抛出 `candidate_baseline_invalid`。未选中旧工序的新增真实排产测试在修复前复现失败，选中旧工序的对照用例原本通过。

## 修改

- `core/services/workbench/run_candidate_baseline.py:139`：从 SHA-256 已校验的入场归档 `Schedule` 推导截至基准版本曾有正式安排的工序，按永久工序身份补齐预期执行集合。
- `core/services/workbench/run_candidate_baseline.py:158`：继续要求投影集合完全相等；继续核对所选工序与入场处置回执、当前任务归属以及归档报工推导的执行数值。旧版本工序在最新版本没有安排时，其 `current_task_ref` 必须仍为空。
- 对照表仍只表示入场时最新正式版本。历史执行工序没有被伪装为该版本对照行，不读取当前业务表补历史，也不修改已保存的排产资料。

## 验证

运行：

```text
.venv/bin/python -m pytest tests/workbench/test_run_candidate_baseline_queries.py tests/workbench/test_run_candidate_baseline_integrity.py tests/workbench/test_run_candidate_baseline_api.py -q
64 passed in 16.77s
```

- 新增 2 个跨版本正例覆盖旧工序选中/未选中、完整分析读取，以及之后新增正式版本、删除现场旧安排仍不改变归档分析。
- 新增 5 个负例覆盖老正式工序执行投影缺失、额外工序、重复投影、完成数量被改、伪造当前任务；均被明确拒绝。保留原有缺失资料、摘要校验、执行回执冲突与只读 API 回归。
- 定向 `git diff --check` 通过。
- 实际 5005 库以 SQLite `mode=ro` 与 `PRAGMA query_only=ON` 调用完整 `read_candidate_analysis` 成功：原候选 62 条任务、68 条执行投影，v14 对照仍为 18 条；`current_entities_consulted=false`、连接 `total_changes=0`。详见同目录 `readonly-existing-candidate.json`。

产品和测试已冻结。浏览器复查由主代理统一重启后继续；本记录是当前脏工作区中的专项验证，不是全门禁或 clean-worktree proof。
