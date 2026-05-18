---
doc_type: feature-acceptance
feature: 2026-05-18-scheduler-graph-ready-queue-on-mode
roadmap: networkx-scheduler-graph-introduction
roadmap_item: scheduler-graph-ready-queue-on-mode
status: accepted
accepted_at: 2026-05-18
---

# scheduler-graph-ready-queue-on-mode 验收记录

## 1. 完成范围

- 实现 PR-5 阶段 11 有环安全门。
- 实现只处理普通 Python 数据的 ready 队列 helper；实际实现位于 `core/algorithms/greedy/dispatch/ready_queue.py`，`core/services/scheduler/graph/ready_queue.py` 保留兼容导出。
- 在 optimizer 前准备 `graph_ready_context`，并让排产和 `result_summary` 共用同一份图分析结论。
- 沿 `schedule_orchestrator.py`、`schedule_optimizer.py`、`schedule_optimizer_steps.py`、`optimizer_local_search.py`、`GreedyScheduler.schedule()`、`dispatch_sgs()` 传递 `graph_ready_context`。
- 在 `graph_analysis_mode=on + DAG` 时启用图 ready 队列筛 SGS 候选。
- 有 `graph_ready_context` 时强制 optimizer 使用 SGS，避免 public 摘要声称 ready 队列已启用但实际跑了 `batch_order`。
- 无 `graph_ready_context` 时，旧 SGS `_collect_sgs_candidates()` 路径保持。
- frozen / seed 工序只作为已固定前置释放后继，不重复进入 candidates，也不重复写 schedule rows。
- 前置工序排产失败时，图后继不会被释放，并会计入失败数和中文错误说明。
- 同步配置说明文字，避免 `on` 仍被描述成 “report-only” 或 “ready 队列后续接入”。

## 2. 明确未做

- 没有实现图评分。
- 没有把关键路径、影响范围、后续关键工作量接入评分。
- 没有改变 `_score_external_candidate()`、`_score_internal_candidate()`、`build_dispatch_key()`。
- 没有改变资源匹配、外协组合并、内部工时估算、SLACK/CR/ATC 评分方向。
- 没有新增候选池、多权重试跑、自动择优或候选落库。
- 没有新增页面按钮、页面路由或数据库表。
- 没有让算法层反向依赖 scheduler service；ready 队列 helper 已下沉到算法包。
- 没有证明 PR-6 的图评分方向是正确的。

## 3. 验收核对

- `report + 有环` 只提示，不阻止排产。
- `on + block=yes + 有环` 在 version 分配前阻止排产，并返回中文业务错误和结构化详情。
- `on + block=no + 有环` 不启用图 ready 队列，继续原排产逻辑，并在 public 摘要里写清图增强未启用。
- known graph error 不伪装成有环。
- unknown graph error 不静默吞掉。
- `ready_queue.py` 不导入 NetworkX，不读数据库、不读配置、不调用评分或资源匹配。
- `on + DAG` 的 public 摘要写 `effective_mode="graph_ready_queue"`、`ready_queue_enabled=true`。
- `on + DAG` 的实际 optimizer 路径使用 SGS，并把 ready 队列作为候选资格来源。
- 无 graph context 时旧 SGS 行为保持。
- failed / blocked 语义完整：前置失败时后继跳过有错误说明，跨批次后继会计入失败，同批次后继不重复计数。

## 4. 已跑验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_graph_cycle_policy_contract.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/scheduler_graph/test_ready_queue.py tests/regression_scheduler_graph_on_mode_contract.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_graph_report_mode_contract.py tests/regression_scheduler_graph_report_mode_service_contract.py tests/regression_scheduler_graph_summary_contract.py tests/regression_scheduler_graph_operation_logs_contract.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_sgs_internal_scoring_matches_execution.py tests/test_sgs_total_hours_cache.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check ...`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright ...`：通过。
- `.codestable/tools/validate-yaml.py --yaml-only`：通过。

## 5. PR-6 交接边界

- PR-6 可以继承：PR-5 已经证明 `on + DAG` 能把 ready 资格交给 SGS 候选集合。
- PR-6 不能继承：PR-5 没有证明任何图评分方向、权重含义、关键路径评分、影响范围评分或原 SLACK/CR/ATC 语义保持。
- PR-6 必须重新证明：新增图评分以后，不会破坏现有评分方向、资源匹配、外协组合并、内部工时估算和代表结果选择。

## 6. 对抗审查

- 阶段 11 实现前只读核实：Subagent 确认安全门位置、错误分类和 version 分配边界。
- 阶段 11 实现后对抗审查：发现旧合同测试签名、配置说明旧口径、结构化 cycle details、页面配置提示旧文案等阻塞问题，均已修复并复审清零。
- 阶段 12a 实现前只读核实：Subagent 确认 ready_queue 必须纯 Python、不能读取图对象或业务服务。
- 阶段 12a 实现后对抗审查：发现缺失 predecessor key、None 集合、blocked/done 重叠、坏 sort key 等阻塞问题，均已修复并复审清零。
- 阶段 12b/12c 实现前只读核实：Subagent 确认 graph context 必须在 optimizer 前准备，并与 summary 共用同一份结果。
- 阶段 12b/12c 实现后对抗审查：发现旧 report 合同测试节点构造问题，已修复并复审清零。
- 阶段 12d 实现后对抗审查：发现 public 摘要与实际 dispatch mode 不一致、前置失败后继漏统计两个阻塞问题，均已修复并复审清零。
- 保留的非阻塞口径：传递性后继错误说明当前统一写“依赖的上游失败工序”，可读但不是最细的直接前序说明；后续如果需要更精确，可以再增强文案。

## 7. Proof 口径

- 本记录绑定 PR-5 的 targeted exit checks。
- 本轮未做本地 commit，因此当前不能称为 clean-worktree proof。
- 如果要拿 clean-worktree proof，需要先处理全部未提交改动，再运行 `scripts/run_quality_gate.py --require-clean-worktree`。
