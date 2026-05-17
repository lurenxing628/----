---
doc_type: feature-design
feature: 2026-05-17-scheduler-graph-report-mode
requirement:
roadmap: networkx-scheduler-graph-introduction
roadmap_item: scheduler-graph-report-mode
status: approved
summary: 接入 graph_analysis_mode=report 的排产工序图旁路报告，不改变排产结果
tags: [scheduler, graph, networkx, summary, operation-logs]
---

# scheduler-graph-report-mode 设计方案

## 1. 目标

本 feature 执行 roadmap `networkx-scheduler-graph-introduction` 的阶段 10 / PR-3：在原排产已经算完之后，旁路运行工序图分析，并把一份小摘要写进本次排产结果。

大白话说，排产仍然按原来的算法排，图分析只是在旁边看一眼工序前后关系，然后把“有多少节点、多少边、是不是有环、关键路径有多长”这些摘要放进结果里。它不能反过来影响排产顺序、候选集合、评分、冻结窗口或落库明细。

## 2. 决策与边界

- `graph_analysis_mode=off`：不分析，不导入 `core.services.scheduler.graph`，不要求安装 NetworkX，不写 `graph_analysis`。
- `graph_analysis_mode=report`：只读分析，写 `result_summary["algo"]["graph_analysis"]` 和 `result_summary["diagnostics"]["graph_analysis"]`，不改变排产结果。
- `graph_analysis_mode=on`：本阶段先按 report-only 处理，公开摘要里写 `effective_mode="report_only"`，不接 ready 队列，也不接评分。
- 接入点放在 `schedule_orchestrator.py` 中，位置是 `optimize_schedule_fn(...)` 和 `build_validated_schedule_payload(...)` 都完成之后、`SummaryBuildContext(...)` 创建之前。
- 图报告判断、错误投影和采样投影放在 `schedule_graph_report.py`。这个文件仍属于排产 run 层，只服务阶段 10 的旁路 report 模式，避免把 orchestrator 撑过架构门禁文件大小阈值。
- 2026-05-18 加固后，图输入只来自 `schedule_input.cfg`、完整 `schedule_input.algo_ops`、`schedule_input.algo_ops_to_schedule` 计数、`schedule_input.batches`、`schedule_input.resource_pool`、`schedule_input.frozen_op_ids` 和 `schedule_input.seed_results` 计数，不重新查数据库。
- `SummaryBuildContext` 只承载两个普通 dict：`graph_analysis_public` 和 `graph_analysis_diagnostics`。
- OperationLogs 不新增图日志写入器，继续沿用现有 `detail["algo"]` 小摘要路径。

## 3. 明确不做

- 不改 `schedule_optimizer.py`。
- 不改 `core/algorithms/greedy/scheduler.py`。
- 不改 SGS 候选集合和 SGS 评分。
- 不改 `seed_results`。
- 不改冻结窗口。
- 不改 `validated_schedule_payload`。
- 不改落库 `schedule_rows`。
- 不新增页面、按钮或调试接口。
- 不做 `graph_debug_export` 文件导出。
- 不做性能测试阶段和 Win7 打包阶段。
- 不把 NetworkX 缺失、版本不对、图输入合同错误伪装成成功。
- 不捕获未知异常后返回空报告。

## 4. 输出合同

公开小摘要写入：

```text
result_summary["algo"]["graph_analysis"]
OperationLogs.detail["algo"]["graph_analysis"]
```

采样诊断写入：

```text
result_summary["diagnostics"]["graph_analysis"]
```

公开小摘要只允许包含模式、状态、节点数、边数、DAG 状态、关键路径长度、warning 数、cycle edge 数、耗时，以及 2026-05-18 加固新增的 `input_scope`、`total_algo_op_count`、`reschedulable_unfrozen_op_count`、`frozen_node_count`、`seed_result_count`。采样诊断只允许包含 sample / count / truncated 这类小字段；`warning.data` 必须先投影成 JSON 可保存的小对象，列表要带样本、总数和截断标记。

禁止进入 `result_summary` 或 OperationLogs 的内容：

- 完整 nodes。
- 完整 edges。
- 完整 node_metrics。
- 完整 topological_order。
- raw 原始对象。
- nx.DiGraph 对象。

## 5. 错误口径

- NetworkX 不可用：公开摘要写 `status="unavailable"`、`reason="networkx_unavailable"`。
- 图输入合同错误：公开摘要写 `status="input_error"`、`reason="graph_input_contract_error"`。
- 图构建合同错误：公开摘要写 `status="build_error"`、`reason="graph_build_contract_error"`。
- 未知异常：不吞掉，让测试和开发者直接看到。
- 有环：不是 Python 异常；report 模式只写 warning 和 cycle edge 采样，不阻止排产。

## 6. 验收方式

- 用三份新增回归测试锁住 report 模式、summary 字段和 OperationLogs 小摘要合同。
- 复跑现有排产编排、summary size guard、graph lazy runtime 和 `tests/scheduler_graph`。
- 用阶段 0 三个 baseline case 在 `graph_analysis_mode=report` 下对比，确认排产结果不变。
- 用 ruff 和 pyright 检查 Python 3.8 / Win7 兼容写法。
