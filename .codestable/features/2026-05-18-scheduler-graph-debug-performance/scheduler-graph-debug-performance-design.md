---
doc_type: feature-design
feature: 2026-05-18-scheduler-graph-debug-performance
requirement:
roadmap: networkx-scheduler-graph-introduction
roadmap_item: scheduler-graph-debug-performance
status: approved
summary: PR-4 只补 report 模式进入 on 模式前的性能、诊断和真实链路证据
tags: [scheduler, graph, networkx, performance, diagnostics]
---

# scheduler-graph-debug-performance 设计方案

## 1. 目标

本 feature 执行 roadmap `networkx-scheduler-graph-introduction` 的 PR-4：`scheduler-graph-debug-performance`。

大白话说，这一步不是让图开始管排产，而是先证明“图分析只是在旁边看一眼、写一份报告”。如果这一步不能证明性能、诊断摘要、冻结窗口、OperationLogs 都稳，后面的 PR-5 就不能放心把图接进候选队列。

## 2. 范围

- 新增 2000 节点 basic report 性能护栏。
- 生成并提交 `evidence/scheduler_graph/performance_2000_nodes.txt`。
- diagnostics 增加长文本截断，避免单条 warning 把摘要撑大。
- 继续保持 `warning.data` 的 JSON 安全投影。
- 补真实服务级 off/report/on 对比，覆盖冻结窗口 seed 真实链路。
- 补 OperationLogs known graph error 小摘要检查。
- 回填 roadmap / items.yaml / feature acceptance。

## 3. 明确不做

- 不实现 PR-5 的有环安全门。
- 不实现 ready 队列。
- 不实现图评分。
- 不让 `graph_analysis_mode=on` 改变排产行为；本阶段仍是 `effective_mode="report_only"`。
- 不改 `schedule_optimizer.py`、GreedyScheduler、SGS、`ready_queue.py`、`scoring.py`。
- 不改 rows、best_order、selected_batch_ids、freeze_window、resource_pool、seed_results、frozen_op_ids、validated_schedule_payload、schedule_rows 的业务语义。
- 不新增管理员 debug HTTP 接口。
- 不新增页面按钮。
- 本阶段不实现 `graph_debug_export` 文件导出；调试导出不是 PR-4 必须证据。

## 4. 实现决策

- 性能护栏只卡 basic report，不把完整 `node_metrics` / `downstream_critical_minutes` 拉进 report 默认链路。
- 2000 节点性能测试构造 100 个批次、每批 20 道工序，共 2000 节点、1900 条同批次前后置边。
- 性能测试跑 3 次，断言平均耗时和最大耗时都在护栏内。
- evidence 文件作为本次实测证据提交；pytest 只读取并核对文件存在和口径，不在每次运行时重写 tracked 文件，避免跑完门禁后工作区变脏。
- diagnostics 长字符串只保留采样、长度和截断标记，不把大段文本完整写进 result_summary。
- frozen/seed 真实链路用 `ScheduleService.run_schedule()` 先生成上一版本，再开启冻结窗口跑 off/report/on 三套数据库对比。
