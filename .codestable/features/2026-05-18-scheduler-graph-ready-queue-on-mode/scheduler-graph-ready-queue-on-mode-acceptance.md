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
- `on + block=no + 有环` 时强制使用旧 SGS 候选逻辑，但 `graph_ready_context` 保持为空，避免误启用图 ready 队列。
- 无 `graph_ready_context` 时，旧 SGS `_collect_sgs_candidates()` 路径保持。
- ready 队列 helper 会拒绝像图对象一样带 `nodes/edges` 的输入，也会拒绝字符串/bool 排序 key，避免把图对象或真假值悄悄当普通 op_id/整数使用。
- SGS 边界会在转集合前拒绝图对象和图对象样子的输入，包括 `schedulable_op_ids`、`fixed_op_ids`，以及前后置映射里的嵌套集合。
- 直接调用 `GreedyScheduler.schedule()` 时，`graph_ready_context` 只能配 SGS；如果配 `batch_order` 会直接报错，避免 ready 队列被悄悄忽略。
- `graph_dispatch_mode_override` 只允许内部传入 `sgs`，其他值会直接报错。
- SGS 边界会把前后置映射标准化后写回运行态，避免校验和后续阻断使用两套口径。
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
- `on + block=no + 有环` 不启用图 ready 队列，继续旧 SGS 候选逻辑，并在 public 摘要里写清图增强未启用。
- known graph error 不伪装成有环。
- unknown graph error 不静默吞掉。
- `ready_queue.py` 不导入 NetworkX，不读数据库、不读配置、不调用评分或资源匹配。
- ready queue / SGS 边界会拒绝图对象、图对象样子的嵌套集合、字符串排序 key 和 bool 排序 key。
- `on + DAG` 的 public 摘要写 `effective_mode="graph_ready_queue"`、`ready_queue_enabled=true`。
- `on + DAG` 的实际 optimizer 路径使用 SGS，并把 ready 队列作为候选资格来源。
- 无 graph context 时旧 SGS 行为保持。
- failed / blocked 语义完整：前置失败时后继跳过有错误说明，跨批次后继会计入失败，同批次后继不重复计数。

## 4. 已跑验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/scheduler_graph/test_ready_queue.py tests/regression_scheduler_graph_on_mode_contract.py tests/regression_scheduler_graph_cycle_policy_contract.py tests/regression_scheduler_graph_report_mode_contract.py tests/regression_scheduler_graph_report_mode_service_contract.py tests/regression_scheduler_graph_summary_contract.py tests/regression_scheduler_graph_operation_logs_contract.py`：72 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_sgs_internal_scoring_matches_execution.py tests/test_sgs_total_hours_cache.py`：10 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_config_route_contract.py tests/regression_config_field_spec_contract.py tests/test_schedule_optimizer_strict_mode_signature_cache.py`：47 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/regression_schedule_orchestrator_contract.py`：OK。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/run/schedule_graph_report.py core/services/scheduler/run/schedule_orchestrator.py core/services/scheduler/run/schedule_optimizer.py core/services/scheduler/run/schedule_optimizer_steps.py core/services/scheduler/run/optimizer_local_search.py core/services/scheduler/graph/ready_queue.py core/algorithms/greedy/scheduler.py core/algorithms/greedy/dispatch/ready_queue.py core/algorithms/greedy/dispatch/sgs.py core/algorithms/greedy/dispatch/sgs_scoring.py tests/regression_scheduler_graph_cycle_policy_contract.py tests/scheduler_graph/test_ready_queue.py tests/regression_scheduler_graph_on_mode_contract.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/services/scheduler/run/schedule_graph_report.py core/services/scheduler/run/schedule_orchestrator.py core/services/scheduler/run/schedule_optimizer.py core/services/scheduler/run/schedule_optimizer_steps.py core/services/scheduler/run/optimizer_local_search.py core/services/scheduler/graph/ready_queue.py core/algorithms/greedy/scheduler.py core/algorithms/greedy/dispatch/ready_queue.py core/algorithms/greedy/dispatch/sgs.py core/algorithms/greedy/dispatch/sgs_scoring.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/networkx-scheduler-graph-introduction/networkx-scheduler-graph-introduction-items.yaml --yaml-only`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --dir .codestable/features/2026-05-18-scheduler-graph-ready-queue-on-mode --yaml-only`：通过。

## 5. PR-6 交接边界

- PR-6 可以继承：PR-5 已经证明 `on + DAG` 能把 ready 资格交给 SGS 候选集合。
- PR-6 不能继承：PR-5 没有证明任何图评分方向、权重含义、关键路径评分、影响范围评分或原 SLACK/CR/ATC 语义保持。
- PR-6 必须重新证明：新增图评分以后，不会破坏现有评分方向、资源匹配、外协组合并、内部工时估算和代表结果选择。

## 6. 对抗审查

- 阶段 11 实现前只读核实：Subagent 确认安全门位置、错误分类和 version 分配边界。
- 阶段 11 实现后对抗审查：发现 `on + block=no + 有环` 的 public 摘要写“继续旧 SGS”，但实际可能继续配置里的 `batch_order`；已通过 `graph_dispatch_mode_override="sgs"` 修复，并复审清零。
- 阶段 12a 实现前只读核实：Subagent 确认 ready_queue 必须纯 Python、不能读取图对象或业务服务。
- 阶段 12a 实现后对抗审查：未发现阻塞问题；按非阻塞建议补强图对象误传和 bool sort key 合同，复审无阻塞。
- 阶段 12b/12c 实现前只读核实：Subagent 确认 graph context 必须在 optimizer 前准备，并与 summary 共用同一份结果。
- 阶段 12b/12c 实现后对抗审查：发现旧 report 合同测试节点构造问题，已修复并复审清零。
- 阶段 12d 实现后对抗审查：未发现阻塞问题；按非阻塞建议把前后置映射标准化结果写回运行态，并复审无阻塞。
- 非阻塞建议收口：补了 `graph_ready_context + 非 SGS` 直接报错、`graph_dispatch_mode_override` 合法值校验、`sort_key_by_op_id` 字符串/bool key 合同、SGS 嵌套前后置图对象拒绝。
- 最后一轮对抗复审：发现 SGS 前后置嵌套集合仍可能在 ready_queue 前误吞图对象；已在 `_normalize_link_map()` 转集合前拒绝，并补 predecessor/successor 两类测试，复审阻塞清零。

## 7. Proof 口径

- 本记录绑定 PR-5 的 targeted exit checks。
- 本轮未做本地 commit，因此当前不能称为 clean-worktree proof。
- 如果要拿 clean-worktree proof，需要先处理全部未提交改动，再运行 `scripts/run_quality_gate.py --require-clean-worktree`。
