---
doc_type: feature-acceptance
feature: 2026-05-18-scheduler-graph-debug-performance
roadmap: networkx-scheduler-graph-introduction
roadmap_item: scheduler-graph-debug-performance
status: accepted
accepted_at: 2026-05-18
---

# scheduler-graph-debug-performance 验收记录

## 1. 完成范围

- 新增 `tests/scheduler_graph/test_graph_performance.py`，用 100 个批次、每批 20 道工序验证 2000 节点 basic report 性能。
- 新增 `evidence/scheduler_graph/performance_2000_nodes.txt`，记录本机 3 次实测结果、阈值、节点数、边数、摘要大小和 basic report 口径。
- `schedule_graph_report.py` 对 diagnostics 里的长 warning message 和长字符串 warning.data 做采样、长度和截断标记。
- `tests/regression_scheduler_graph_report_mode_service_contract.py` 增加真实服务级 frozen/seed 场景：先跑上一版本，再开启冻结窗口，分别对比 off/report/on。
- `tests/regression_scheduler_graph_operation_logs_contract.py` 增加 known graph error 小摘要检查，确认 OperationLogs 只保留 public reason/message。
- `tests/regression_scheduler_graph_summary_contract.py` 增加长文本 JSON 安全投影测试。

## 2. 明确未做

- 没有实现 PR-5 的有环安全门。
- 没有实现 ready 队列。
- 没有实现图评分。
- 没有让 `graph_analysis_mode=on` 改变排产行为；本阶段仍是 `effective_mode="report_only"`。
- 没有修改 `schedule_optimizer.py`、GreedyScheduler、SGS、`ready_queue.py`、`scoring.py`。
- 没有修改 rows、best_order、selected_batch_ids、freeze_window、resource_pool、seed_results、frozen_op_ids、validated_schedule_payload、schedule_rows 的业务语义。
- 没有新增管理员 debug HTTP 接口。
- 没有新增页面按钮。
- 没有实现 `graph_debug_export` 文件导出。本 PR 先完成证据关口，调试导出保留为后续附属能力。

## 3. 验收核对

- 2000 节点、1900 条边的 basic report 通过性能护栏。
- basic report 明确不计算完整 `node_metrics` / `downstream_critical_minutes`，diagnostics 写 `node_metrics_status="skipped_basic_report"`。
- diagnostics 只写 sample / count / truncated / status，不写完整 nodes、edges、raw、完整 node_metrics。
- warning.data 和长文本 warning message 保持 JSON 可序列化，并有截断标记。
- known graph error 在 public 小摘要顶层可见。
- OperationLogs 不写 diagnostics、nodes、edges、raw、完整 node_metrics、完整 topological_order。
- 真实服务级 off/report/on 普通场景 rows 和 summary counts 不变。
- 真实服务级 off/report/on frozen/seed 场景 rows、best_order、selected_batch_ids、freeze_window、resource_pool 不变；report/on 只新增 graph_analysis 小摘要。

## 4. 已跑验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/scheduler_graph/test_graph_performance.py`：通过，2 passed。
- `test -f evidence/scheduler_graph/performance_2000_nodes.txt`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_graph_report_mode_contract.py tests/regression_scheduler_graph_report_mode_service_contract.py tests/regression_scheduler_graph_summary_contract.py tests/regression_scheduler_graph_operation_logs_contract.py`：通过，20 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/scheduler_graph/test_exporter.py tests/scheduler_graph/test_analysis_service.py tests/scheduler_graph/test_metrics_critical_path.py tests/scheduler_graph/test_metrics_impact.py`：通过，25 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_graph_config_bootstrap_contract.py tests/regression_migrate_v9_graph_config_defaults.py tests/regression_scheduler_config_spec_sync_contract.py`：通过，7 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/run/schedule_graph_report.py core/services/scheduler/graph tests/scheduler_graph tests/regression_scheduler_graph_report_mode_contract.py tests/regression_scheduler_graph_summary_contract.py tests/regression_scheduler_graph_operation_logs_contract.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/services/scheduler/run/schedule_graph_report.py core/services/scheduler/graph`：通过，0 errors，0 warnings。
- `git diff --check`：通过。

## 5. Proof 口径

- 当前记录已绑定 roadmap 要求的 PR-4 exit checks。
- clean-worktree proof 只有在所有代码、测试、evidence、roadmap/items/feature 记录都提交或处理后，再运行 `scripts/run_quality_gate.py --require-clean-worktree` 才能成立。

## 6. Roadmap 回写

- `scheduler-graph-debug-performance` 已从 `planned` 回填为 `done`。
- items.yaml 已绑定本 feature 目录。
- roadmap 主文档变更记录已补充 PR-4 实际完成范围和未做范围。

## 7. 对抗审查

- 第一轮实现前只读探索：4 个 Subagent，结论一致，PR-4 缺口集中在性能证据、真实服务级 frozen/seed 对比和 CodeStable 回填，不应进入 PR-5/PR-6。
- 实现后对抗审查：3 个只读 Subagent。
- 审查结论：没有发现改变排产主链、提前实现 PR-5/PR-6、宽泛吞错、OperationLogs 泄漏完整图或 Python 3.8/Win7 越界的阻塞性代码问题。
- 审查建议：补齐 warning message 的原始长度字段。已补 `message_length` 并复跑相关测试。
- 共同保留口径：当前未做本地提交，因此没有 clean-worktree proof；后续如果要拿 clean proof，必须先处理全部未提交文件，再跑 `scripts/run_quality_gate.py --require-clean-worktree`。
