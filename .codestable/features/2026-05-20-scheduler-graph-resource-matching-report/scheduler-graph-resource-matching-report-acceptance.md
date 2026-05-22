---
doc_type: feature-acceptance
feature: 2026-05-20-scheduler-graph-resource-matching-report
roadmap: networkx-scheduler-graph-introduction
roadmap_item: scheduler-graph-resource-matching-report
status: accepted
summary: PR-8 已完成资源匹配 report-only 分析，结果只进入报告，不改变排产
tags: [scheduler, graph, networkx, resource-matching, report]
---

# PR-8 验收记录

## 结论

PR-8 代码级实现已完成。

现在系统在 `graph_analysis_mode=report` 或 `on` 时，会额外分析“首波 ready 工序”和 `candidate_machine_ids` 之间的设备最大匹配。这个结果只进入 `result_summary` 报告，不参与排产、不改变派工、不改变候选方案。

## 已完成范围

- 新增 `core/services/scheduler/graph/resource_matching.py`：
  - 只接收 `OperationGraphNode` ready 节点。
  - 运行时懒加载 NetworkX。
  - 构造 ready 工序和候选设备的二分图。
  - 调用 `nx.bipartite.maximum_matching` 后只保留工序侧映射。
  - 生成 public 小摘要和 diagnostics 采样。
- 在 run 层增加：
  - `build_first_wave_ready_nodes(...)`
  - `build_graph_resource_matching_projection(...)`
- 这两个 helper 的具体实现放在 `schedule_graph_resource_matching_context.py`，`schedule_graph_dispatch_context.py` 只保留轻量入口，避免文件超过 500 行架构门禁。
- 同时把 `schedule_graph_report.py` 里的 warning / node_metrics 采样 helper 下沉到 `schedule_graph_projection_helpers.py`，让 report 文件也回到 500 行以内。
- 在 `schedule_graph_report.py` 接入：
  - `result_summary.algo.graph_analysis.resource_matching`
  - `result_summary.diagnostics.graph_analysis.resource_matching`
- 增加回归测试：
  - `tests/scheduler_graph/test_resource_matching.py`
  - `tests/regression_scheduler_graph_resource_matching_report_contract.py`
  - 补强 `tests/scheduler_graph/test_graph_dispatch_context.py`
  - 补强 `tests/regression_scheduler_graph_operation_logs_contract.py`

## 明确未做

- 不改排产 rows、best_order、attempts、resource_pool 或 resource assignment。
- 不改 SGS 候选排序，不改图评分，不改候选 runner。
- 不落 ScheduleCandidate，不改候选表，不改 schema，不加 migration。
- 不新增配置，不新增页面入口，不改模板。
- 不做人力匹配，不做最小费用流。
- 不把没有候选设备的工序回退成全量设备。

## 输出和日志边界

- public 只放状态和计数，不放样本。
- diagnostics 才放 `matches_sample`、`unmatched_operation_ids_sample`、`bottleneck_machine_ids_sample`。
- OperationLogs 只能看到 public.resource_matching 的状态和计数。
- OperationLogs 不能看到 diagnostics、matches_sample、unmatched sample、bottleneck sample、raw、resource_pool 或 nx.Graph。

## 对抗审查结果

- 第一阶段对抗审查发现：测试曾经押注 NetworkX 在多个合法最大匹配里具体选哪一个，存在不稳定证明。
  - 已修复：测试只断言最大匹配数量、未匹配数量、瓶颈设备方向和 public/diagnostics 边界。
  - 复审结果：OK，`PYTHONHASHSEED=0..5` 六次复跑均通过。
- 第二阶段对抗审查结果：OK。
  - off 模式不提前 import resource_matching 或 NetworkX。
  - first-wave ready 按 fixed/seed predecessor 公式计算，并按 nodes 原始顺序返回。
  - 非 DAG、图增强不可用和合同错误不会运行最大匹配。
- 第三阶段对抗审查结果：OK。
  - report/on 不改变排产 rows、best_order、attempts、improvement_trace、分配映射和 resource_pool。
  - public 只放状态和计数，样本只在 diagnostics。
  - OperationLogs 只复制 public.resource_matching 计数字段，不读取 diagnostics。
  - NetworkX 不可用走顶层 unavailable，不伪造 nested resource_matching。

## 已通过验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/scheduler_graph/test_resource_matching.py`
  - 结果：10 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/scheduler_graph/test_graph_dispatch_context.py tests/scheduler_graph/test_resource_matching.py`
  - 结果：23 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_graph_resource_matching_report_contract.py tests/regression_scheduler_graph_operation_logs_contract.py`
  - 结果：7 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_graph_lazy_runtime_contract.py tests/scheduler_graph/test_nx_runtime.py`
  - 结果：5 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_graph_report_mode_contract.py tests/regression_scheduler_graph_on_mode_contract.py tests/regression_scheduler_graph_summary_contract.py`
  - 结果：54 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check ...`
  - 结果：passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/services/scheduler/graph/resource_matching.py core/services/scheduler/run/schedule_graph_dispatch_context.py core/services/scheduler/run/schedule_graph_resource_matching_context.py core/services/scheduler/run/schedule_graph_projection_helpers.py core/services/scheduler/run/schedule_graph_report.py`
  - 结果：0 errors。

## 证据不足

- Win7 实机或虚拟机离线证据本轮未跑。
- Win7 证据不足，由 PR-9 承接。
- 最终 clean-worktree quality gate 需要在代码、测试、CodeStable 文档、roadmap/items 全部落盘并提交后再跑；最终结果以本轮交付说明为准。
