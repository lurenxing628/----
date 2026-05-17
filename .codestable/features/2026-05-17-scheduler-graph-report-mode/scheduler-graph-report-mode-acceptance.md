---
doc_type: feature-acceptance
feature: 2026-05-17-scheduler-graph-report-mode
roadmap: networkx-scheduler-graph-introduction
roadmap_item: scheduler-graph-report-mode
status: accepted
accepted_at: 2026-05-17
---

# scheduler-graph-report-mode 验收记录

## 1. 完成范围

- 已在 `schedule_orchestrator.py` 接入 `maybe_analyze_schedule_graph()`。
- `maybe_analyze_schedule_graph()`、graph 模式判断、错误投影和采样投影已收在 `schedule_graph_report.py`，让 orchestrator 保持在架构门禁文件大小阈值内。
- 接入点在原排产算法已经完成、`validated_schedule_payload` 已经生成之后，图分析只作为旁路报告运行。
- `graph_analysis_mode=off` 不导入 graph 模块，不要求 NetworkX，不写 `graph_analysis`。
- `graph_analysis_mode=report` 会调用 `build_operation_nodes_from_rows()`、`ScheduleGraphAnalysisService.analyze_linear_batches()` 和 `graph_summary_to_dict()`，并输出 public 小摘要和 diagnostics 采样。
- `graph_analysis_mode=on` 在本阶段只按 report-only 输出摘要，公开字段写 `effective_mode="report_only"`。
- `SummaryBuildContext` 新增 `graph_analysis_public` 和 `graph_analysis_diagnostics` 两个普通 dict 字段。
- `result_summary["algo"]["graph_analysis"]` 只写 public 小摘要。
- `result_summary["diagnostics"]["graph_analysis"]` 只写采样诊断。
- OperationLogs 继续沿用现有 `detail["algo"]` 路径，只能看到 `algo.graph_analysis` 小摘要。

## 2. 明确未做

- 没有改 `schedule_optimizer.py`。
- 没有改 `core/algorithms/greedy/scheduler.py`。
- 没有改 SGS 候选集合。
- 没有改 SGS 评分。
- 没有改 `seed_results`。
- 没有改冻结窗口。
- 没有改 `validated_schedule_payload`。
- 没有改落库 `schedule_rows`。
- 没有新增页面、按钮或调试接口。
- 没有做 `graph_debug_export` 文件导出。
- 没有做 2000 节点性能证据。
- 没有做 PyInstaller / Win7 打包验证。
- 没有运行提交后的 clean-worktree final quality gate。

## 3. 只读核实

- 调用链核实结果：`ScheduleService.run_schedule` 收集输入后进入 `orchestrate_schedule_run()`，再调用 optimizer 和 `build_validated_schedule_payload()`，之后才创建 `SummaryBuildContext`。
- summary 核实结果：`build_result_summary()` 会先组装 algo，再通过 `project_public_algo_summary()` 投影公开字段；diagnostics 由 summary assembly 合并。
- OperationLogs 核实结果：`schedule_persistence.py` 当前只把 `result_summary_obj.get("algo")` 放进日志 detail，因此只要 algo.graph_analysis 是小摘要，日志就不会看到完整图。
- graph 模块核实结果：阶段 9 已提供 `input_adapter`、`analysis_service`、`exporter` 和懒加载 NetworkX 入口，阶段 10 不需要重写图算法。

## 4. 验收核对

- off 模式不 import graph 模块，不要求 NetworkX，不写 graph_analysis。
- report 模式读取 `schedule_input.cfg`、完整 `algo_ops`、`algo_ops_to_schedule` 计数、`batches`、`resource_pool`、`frozen_op_ids` 和 `seed_results` 计数；冻结工序只作为图节点标记，不重新参与排产评分。
- on 模式在本阶段只输出 report-only 摘要。
- public 小摘要不包含 `topological_order_sample`、`critical_path_sample`、`node_metrics_sample`、`nodes`、`edges`、`raw`。
- diagnostics 不包含完整 `topological_order`、完整 `node_metrics`、`nodes`、`edges`、`raw`。
- OperationLogs detail 中没有 `diagnostics.graph_analysis`，也递归搜不到完整图字段。
- NetworkX 不可用时输出 `status="unavailable"` 和 `reason="networkx_unavailable"`。
- 图输入合同错误时输出 `status="input_error"` 和 `reason="graph_input_contract_error"`。
- 图构建合同错误时输出 `status="build_error"` 和 `reason="graph_build_contract_error"`。
- 未知异常不会被吞成空报告。
- 阶段 0 三个 baseline case 在 report 模式下排产结果不变。

## 5. 验证结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_graph_report_mode_contract.py tests/regression_scheduler_graph_report_mode_service_contract.py tests/regression_scheduler_graph_summary_contract.py tests/regression_scheduler_graph_operation_logs_contract.py`：通过，17 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_schedule_orchestrator_contract.py tests/regression_schedule_service_facade_delegation.py tests/regression_scheduler_summary_result_summary_contract.py tests/regression_schedule_summary_size_guard_large_lists.py tests/regression_scheduler_graph_lazy_runtime_contract.py`：通过，12 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/scheduler_graph`：通过，151 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/run/schedule_orchestrator.py core/services/scheduler/summary core/services/scheduler/graph tests/regression_scheduler_graph_report_mode_contract.py tests/regression_scheduler_graph_summary_contract.py tests/regression_scheduler_graph_operation_logs_contract.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/services/scheduler/run/schedule_orchestrator.py core/services/scheduler/run/schedule_graph_report.py core/services/scheduler/summary core/services/scheduler/graph`：通过，0 errors，0 warnings。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold tests/test_architecture_fitness.py::test_file_size_limit`：通过，2 passed。
- 阶段 0 baseline 对比：`case_001_normal`、`case_002_urgent`、`case_003_external` 均通过；report 模式只新增 graph_analysis 摘要，没有改变排产 rows、best_order、selected_batch_ids、freeze_window 或 resource_pool 公开状态。

## 6. Proof 口径

- 本验收记录证明阶段 10 相关代码、测试、baseline 对比、ruff 和 pyright 已通过。
- 2026-05-18 阶段 10 图报告加固已补充 P1/P2/P3 证据口径：basic metrics、frozen/seed scope、`warning.data` 深层 JSON 安全投影、known graph error 顶层 warning、P3 exporter/config/fail-fast 均已纳入追踪。
- 2026-05-18 追加服务级真实路径回归：同一份最小排产数据分别以 off/report/on 跑 `ScheduleService.run_schedule()`，确认 Schedule 行、summary counts 不变；report/on 只新增图报告，且 basic report 不生成全量 `node_metrics`。
- 当前没有 clean-worktree final proof，因为阶段 10 的代码和 CodeStable 回填尚未提交。
- `scripts/run_quality_gate.py --require-clean-worktree` 必须等本阶段改动提交、工作区干净后再跑，不能用当前 dirty worktree 冒充 clean proof。

## 7. Roadmap 回写

- `.codestable/roadmap/networkx-scheduler-graph-introduction/networkx-scheduler-graph-introduction-items.yaml` 中 `scheduler-graph-core-module` 已标记为 `done`。
- `.codestable/roadmap/networkx-scheduler-graph-introduction/networkx-scheduler-graph-introduction-items.yaml` 中 `scheduler-graph-report-mode` 已标记为 `done`，并绑定本 feature 目录。
- roadmap 主文档阶段 10 验收清单已按实际验证结果勾选，保留提交后 clean-worktree quality gate 未完成状态。
- `.codestable/architecture/ARCHITECTURE.md` 已补充当前排产工序图 report 模式的架构现状。

## 8. AGENTS.md 候选

- 本 feature 没有暴露必须写入 AGENTS.md 的新长期规则。
- 后续维护提醒：在进入 on 模式 ready 队列或评分阶段前，仍要保持 report 模式不改变排产结果这一条边界。

## 9. 遗留

- 后续 PR-4 已从“调试导出和性能证据”调整为“性能护栏 + diagnostics 加固 + 真实集成证明”：先证明 2000 节点性能、采样诊断、warning 顶层可见性、真实排产链路和配置 fail-fast 都稳，再考虑受控导出。
- PR-5 on 模式 ready 队列仍被 PR-4 证据阻塞。PR-5 不能只承接“report 模式字段存在”，必须承接“report 模式在性能、diagnostics、frozen/seed scope 和真实集成链路上都有证明”。
- 后续阶段 11 处理有环阻止策略，但不能替代 PR-4 的性能和 diagnostics 证明。
- 后续阶段 12 / 13 才能让 on 模式接 ready 队列和评分。
- 提交后仍需要在干净工作区运行最终 quality gate。
