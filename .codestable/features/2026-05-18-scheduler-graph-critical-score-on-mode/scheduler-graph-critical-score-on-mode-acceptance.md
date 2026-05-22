---
doc_type: feature-acceptance
feature: 2026-05-18-scheduler-graph-critical-score-on-mode
roadmap: networkx-scheduler-graph-introduction
roadmap_item: scheduler-graph-critical-score-on-mode
status: accepted
accepted_at: 2026-05-18
---

# scheduler-graph-critical-score-on-mode 验收记录

## 1. 完成范围

- 新增 `GraphScoringContractError`、`graph_score_bonus()`、`graph_priority_key_component()`。
- `graph/scoring.py` 保持纯函数边界，不 import NetworkX，不读配置、数据库、日志或排产状态。
- `schedule_graph_report.py` 在 `on + DAG + 图评分权重大于 0` 时计算 full `node_metrics`。
- `schedule_graph_dispatch_context.py` 在 service/run 层预先转成 `graph_priority_key_by_op_id`，并准备 ready 上下文。
- `graph_critical_weight=0` 且 `graph_impact_weight=0` 时显式写 `score_weights_zero`，不算 full 指标，不拼图 key。
- SGS 只拼普通 tuple，不反向 import scheduler service。
- `sgs_graph.py` 承接图 ready 上下文校验和阻断传播，避免 `sgs.py` 超过架构门禁文件大小。
- 图分量拼接保留旧 `score_penalty` 第一位，避免超窗惩罚被图分数盖掉。
- 配置页和配置说明从“预留、不改变排产结果”更新为“on 且图可用时参与 ready 候选排序”。
- result_summary 只增加 `score_enabled`、`score_metric_status`、`score_weight_summary` 等小字段；diagnostics 只增加少量 `graph_score_sample`。
- OperationLogs 继续只拿 public `algo` 小摘要，不拿 diagnostics。
- 更新 2000 节点性能证据，补 full/on-score 路径。
- 更新 `.codestable/architecture/ARCHITECTURE.md`，让架构现状反映 PR-6 已接入图评分。

## 2. 明确未做

- 没有实现 PR-7 多权重候选试跑。
- 没有实现自动择优。
- 没有新增候选表、候选仓库、候选落库事务。
- 没有修改 `schema.sql` 或 migrations。
- 没有新增页面按钮、页面路由、甘特图切换、周计划切换或导出切换。
- 没有把完整 `node_metrics`、完整关键路径、完整拓扑序、nodes、edges、raw graph 写进 summary 或 OperationLogs。
- 没有绕过 `build_dispatch_key()` 去改 `batch_order`、`best_order`、`selected_batch_ids` 或最终落库 rows。

## 3. 验收核对

- bonus 越大，图 key 越小，SGS 越优先。
- 缺 `is_on_critical_path`、`impact_count`、`downstream_critical_minutes` 或坏字段时抛合同错误，不当 0 分。
- `on + DAG + 权重大于 0` 只跑一次 full graph summary，不 basic + full 跑两遍。
- `on + DAG + 权重全 0` 继续 PR-5 ready 队列，不启用图评分。
- 关键路径候选、影响后续更多候选、后续关键工作量更大候选都能在 ready 候选内更靠前。
- SLACK / CR / ATC 原 dispatch key 方向保持。
- `score_penalty` 仍是第一位。
- missing graph key 直接报 `ValidationError`，不静默回旧评分。
- report/off 不准备 graph score context。
- `on + 有环 + block=no` 不启用 ready 队列或图评分，继续旧 SGS。
- summary 和 OperationLogs 不泄漏完整图数据。
- `rg -n "core\\.services" core/algorithms` 无匹配，算法层没有反向依赖 service。

## 4. 已跑验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/scheduler_graph/test_graph_scoring.py`：22 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_graph_on_mode_contract.py`：32 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_graph_cycle_policy_contract.py tests/scheduler_graph/test_ready_queue.py`：33 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_graph_report_mode_contract.py tests/regression_scheduler_graph_report_mode_service_contract.py tests/regression_scheduler_graph_summary_contract.py tests/regression_scheduler_graph_operation_logs_contract.py`：20 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_sgs_internal_scoring_matches_execution.py tests/test_sgs_total_hours_cache.py`：12 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_config_spec_sync_contract.py tests/regression_scheduler_config_route_contract.py`：31 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_mirror_template_sync.py tests/regression_config_field_spec_contract.py`：8 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/scheduler_graph/test_graph_performance.py`：3 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold tests/test_architecture_fitness.py::test_file_size_limit tests/test_architecture_fitness.py::test_greedy_refactor_files_stay_under_quality_gate_limits tests/test_greedy_refactor_contracts.py::test_refactored_files_and_entry_functions_stay_under_quality_gate`：4 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/graph/scoring.py core/services/scheduler/run/schedule_graph_report.py core/algorithms/greedy/dispatch/sgs.py core/algorithms/greedy/dispatch/sgs_scoring.py core/algorithms/dispatch_rules.py tests/scheduler_graph/test_graph_scoring.py tests/regression_scheduler_graph_on_mode_contract.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/services/scheduler/graph/scoring.py core/services/scheduler/run/schedule_graph_report.py core/algorithms/greedy/dispatch/sgs.py core/algorithms/greedy/dispatch/sgs_scoring.py core/algorithms/dispatch_rules.py`：0 errors。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/networkx-scheduler-graph-introduction/networkx-scheduler-graph-introduction-items.yaml --yaml-only`：通过。
- `git diff --check`：通过。
- `rg -n "core\\.services" core/algorithms`：无匹配。

## 5. 架构归并

- 已更新 `.codestable/architecture/ARCHITECTURE.md` 的排产工序图分析现状。
- 归并内容：`on` 模式现在包含 PR-5 ready 队列和 PR-6 图评分；full `node_metrics` 在 service 层转为 `graph_priority_key_by_op_id`，算法层只拼普通 tuple；PR-7 的候选池、多权重试跑、自动择优和落库仍未实现。

## 6. requirement 回写

- 本 feature 来自 roadmap 技术阶段，未关联单独 requirement。
- 本次不新建 requirement；用户可见配置说明已在配置页同步。

## 7. roadmap 回写

- 已将 `scheduler-graph-critical-score-on-mode` 从 `planned` 更新为 `done`。
- 已将 items.yaml 的 `feature` 指向 `.codestable/features/2026-05-18-scheduler-graph-critical-score-on-mode/`。
- 已在 roadmap 主文档表格和变更记录补 PR-6 完成记录。

## 8. attention.md 候选

- 本 feature 未暴露需要补入 `.codestable/attention.md` 的新环境或命令约定。

## 9. PR-7 交接边界

- PR-7 可以继承：PR-6 已证明 on+DAG+权重大于 0 时，SGS ready 候选会按图关键程度参与排序；0 权重会回到 PR-5 ready 队列行为；summary/log 不泄漏完整图数据。
- PR-7 不能继承：多权重候选哪一档最好、自动择优能否稳定选 adopted、候选摘要/明细/代表方案切换/同事务落库。

## 10. Proof 口径

- 本轮为 dirty-worktree targeted proof。
- 尚未本地 commit，因此不能称为 clean-worktree proof。
- 如需 clean-worktree proof，需要先按用户要求本地提交，再运行 `scripts/run_quality_gate.py --require-clean-worktree`。
