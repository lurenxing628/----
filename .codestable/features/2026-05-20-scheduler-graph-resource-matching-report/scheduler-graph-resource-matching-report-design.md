---
doc_type: feature-design
feature: 2026-05-20-scheduler-graph-resource-matching-report
roadmap: networkx-scheduler-graph-introduction
roadmap_item: scheduler-graph-resource-matching-report
status: approved
summary: PR-8 只做资源匹配 report-only 分析，不改排产结果
tags: [scheduler, graph, networkx, resource-matching, report]
---

# scheduler-graph-resource-matching-report 设计方案

## 目标

本 feature 执行 PR-8。

大白话说，前面几轮已经让系统能看懂工序之间的前后关系，也能在 `on` 模式里把第一波 ready 工序交给排产器。PR-8 不让图分析去替用户派工，只在报告里回答一个窄问题：第一波 ready 工序按当前 `candidate_machine_ids` 来看，最多能同时匹配多少台设备，哪些工序没有匹配上，哪些设备可能是候选设备层面的瓶颈。

## 范围

- 新增 `core/services/scheduler/graph/resource_matching.py`，只做二分图最大匹配和结果投影。
- 资源匹配只看设备维度，只读取 `OperationGraphNode.candidate_machine_ids`。
- `report` 和 `on` 模式共用 first-wave ready 口径，具体协调代码放在 `schedule_graph_resource_matching_context.py`，`schedule_graph_dispatch_context.py` 保留轻量入口，避免 run 层文件超过架构门禁：
  - 待排工序来自 `algo_ops_to_schedule`。
  - 已固定工序来自 `frozen_op_ids` 和 `seed_results`。
  - 工序前置来自图边生成的 predecessor map。
  - 返回 ready 节点时保持 `nodes` 原始顺序。
- public 摘要只写 `status/reason` 和计数字段。
- 样本只写进 `diagnostics.graph_analysis.resource_matching`。
- OperationLogs 继续只复制 `algo.graph_analysis` public 小摘要，不能看到 diagnostics 或样本。

## 明确不做

- 不改排产 rows、best_order、attempts、资源分配或 SGS 候选排序。
- 不改 `schedule_optimizer.py`、SGS、候选 runner、候选持久化、资源派工服务。
- 不新增配置项、不改 schema、不加 migration、不落候选表。
- 不新增页面入口、不改模板、不引入外部前端资源。
- 不做人力匹配，不做最小费用流，不复制真实派工器的日历、停机、冻结窗口和人员约束。
- 没有候选设备时不回退成全量设备。
- NetworkX 不可用时不在 resource_matching 里伪造 empty 或 available，沿用顶层 `graph_analysis.status="unavailable"`。

## 输出合同

public 路径：

```text
result_summary.algo.graph_analysis.resource_matching
```

只允许状态和计数：

```text
status
reason
ready_operation_count
operation_with_candidate_count
machine_count
edge_count
matched_operation_count
unmatched_operation_count
bottleneck_machine_count
```

diagnostics 路径：

```text
result_summary.diagnostics.graph_analysis.resource_matching
```

只允许采样、数量和截断标记，例如：

```text
matches_sample
matches_count
matches_truncated
unmatched_operation_ids_sample
unmatched_operation_count
bottleneck_machine_ids_sample
bottleneck_machine_count
warnings_sample
warning_count
```

## 异常和状态口径

- ready 工序非空且分析完成：`status="available"`，`reason="ok"`。
- ready 工序为空：`status="empty"`，`reason="empty_ready_set"`。
- 图不是 DAG：`status="skipped"`，`reason="graph_not_dag"`，不运行最大匹配。
- `on` 模式图增强不可用：`status="skipped"`，`reason` 使用已有禁用原因或 `graph_enhancement_disabled`，不运行最大匹配。
- resource matching 输入合同错误：`status="error"`，`reason="graph_resource_matching_contract_error"`。
- 未知异常继续暴露，不包成成功。
- NetworkX 不可用走顶层 `graph_analysis.status="unavailable"` 和 `reason="networkx_unavailable"`。

## 验收口径

- `resource_matching.py` 模块导入时不 import NetworkX。
- `resource_matching.py` 不 import scheduler run、optimizer、SGS、repo 或 Flask。
- 最大匹配只保留工序侧映射，不把设备侧反向映射写进结果。
- public 不包含 `matches_sample`、`unmatched_operation_sample`、`unmatched_operation_ids_sample`、`bottleneck_machine_sample`、`bottleneck_machine_ids_sample`。
- diagnostics 不包含 `raw`、`resource_pool`、`nx.Graph`、完整候选池或完整图对象。
- report/on 只多出报告字段，不改变排产结果。
- OperationLogs 只看到 public 计数字段，不看到 diagnostics 或样本。
