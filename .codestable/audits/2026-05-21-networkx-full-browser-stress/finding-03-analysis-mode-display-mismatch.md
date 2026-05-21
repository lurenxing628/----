---
doc_type: audit-finding
audit: 2026-05-21-networkx-full-browser-stress
finding_id: analysis-mode-display-mismatch
nature: frontend-display
severity: P1
confidence: high
status: open
suggested_action: cs-issue
last_deep_trace: 2026-05-21
---

# Finding 03：深度优化已开启，但分析页显示“计算模式：快速模式”

## 现象

用户指出 90 秒深度优化上限没有被用满。进一步核对时发现，分析页版本概览里显示“计算模式：快速模式”，但该版本实际配置里已经开启深度优化、候选对比和 90 秒上限。

## 操作步骤

1. 在高级设置中设置：
   - `algo_mode=improve`
   - `objective=min_tardiness`
   - `time_budget_seconds=90`
   - `graph_analysis_mode=on`
   - `graph_candidate_weight_count=7`
2. 运行 v15 模拟排产。
3. 打开 `/scheduler/analysis?version=15`。

## 实际表现

分析页展示：

```text
计算模式
快速模式
优化目标
最少拖期小时
计算时间上限
90 秒
实际用时
81 毫秒
```

## 期望表现

如果实际走的是深度优化或候选对比，应显示成调度员能理解的真实模式，例如“深度优化（已比较重点工序优先方案）”。如果页面想表达的是“本次很快算完”，也不应该写成“快速模式”。

## 问题类型

页面展示错误、文案误导。

## 严重程度

明显影响使用。用户会以为深度优化根本没生效。

## 证据

只读 SQL 复核 v15：

```text
algo.config_snapshot.algo_mode = improve
algo.config_snapshot.objective = min_tardiness
algo.config_snapshot.time_budget_seconds = 90
algo.config_snapshot.graph_analysis_mode = on
algo.candidate_comparison.planned_candidate_count = 8
algo.candidate_comparison.completed_candidate_count = 8
algo.candidate_comparison.adopted_candidate_key = graph_w1_of_7
```

追加核对：

```text
ScheduleConfig.algo_mode = improve
ScheduleConfig.ortools_enabled = yes
ScheduleConfig.ortools_time_limit_seconds = 30
ScheduleConfig.graph_analysis_mode = on

v15 result_summary.algo.mode = greedy
v15 result_summary.algo.config_snapshot.algo_mode = improve
v15 result_summary.algo.graph_analysis.status = available
v15 result_summary.algo.graph_analysis.effective_mode = graph_ready_queue
v15 result_summary.algo.candidate_comparison.planned_candidate_count = 8
v15 result_summary.algo.candidate_comparison.completed_candidate_count = 8
v15 result_summary.algo.candidate_comparison.time_budget_reached = false
```

当前环境还有一个相关但不同的问题：服务启动日志里 `ortools_probe / 深度优化环境检测` 插件是 `enabled=no, loaded=no`；用服务同路径 Python 3.8 直接导入 `ortools` 失败。也就是说，OR-Tools 这个“深度优化高质量起点”组件当前确实不可用或未启用探测。

但这不是分析页显示“快速模式”的直接原因。直接原因是：

- 分析页模板用 `selected_summary.algo.mode` 显示“计算模式”：`templates/scheduler/analysis_parts/_selected_overview.html`。
- 标签映射把 `greedy` 翻成“快速模式”：`web/viewmodels/scheduler_analysis_overview.py`。
- 候选对比链路会把候选配置替换成 `algo_mode="greedy"`，再把被采用候选的 `algo_mode` 写进 `result_summary.algo.mode`：`core/services/scheduler/run/schedule_candidate_runner.py`。
- 真正能表达用户本次设置的是 `result_summary.algo.config_snapshot.algo_mode = improve`，以及 `candidate_comparison` 已经完成 8 个候选。

所以页面现在混用了两个概念：`algo.mode=greedy` 更像“本轮候选内部使用的基础启发式算法”，不是用户在高级设置里选择的“精细计算/快速计算”。

同轮对照：

- v10 设置 1 秒上限后，`time_budget_reached=true`，只完成 1 个候选，跳过 7 个候选。
- v9/v12 设置 90 秒上限后，候选全部算完，因此不会继续空跑到 90 秒。

## 追加根因追踪（2026-05-21）

调用链：

- 高级设置页面字段来自 [templates/scheduler/config.html](/Users/lurenxing/Documents/GitHub/----/templates/scheduler/config.html:136)、[templates/scheduler/config.html](/Users/lurenxing/Documents/GitHub/----/templates/scheduler/config.html:191)、[templates/scheduler/config.html](/Users/lurenxing/Documents/GitHub/----/templates/scheduler/config.html:225) 和 [templates/scheduler/_config_switches.html](/Users/lurenxing/Documents/GitHub/----/templates/scheduler/_config_switches.html:28)。
- 保存入口 [web/routes/domains/scheduler/scheduler_config.py](/Users/lurenxing/Documents/GitHub/----/web/routes/domains/scheduler/scheduler_config.py:474) 收集 `algo_mode/time_budget_seconds/graph_analysis_mode/ortools_enabled`。
- 配置落库在 [core/services/scheduler/config/config_page_save_service.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/config/config_page_save_service.py:279) 和 [core/services/scheduler/config/config_page_save_service.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/config/config_page_save_service.py:319)。
- 排产读取设置在 [core/services/scheduler/schedule_service.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/schedule_service.py:192) 和 [core/services/scheduler/run/schedule_input_collector.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/run/schedule_input_collector.py:190)。
- 候选比较启用条件在 [core/services/scheduler/run/schedule_orchestrator.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/run/schedule_orchestrator.py:208)，实际运行候选对比在 [core/services/scheduler/run/schedule_orchestrator.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/run/schedule_orchestrator.py:327)。
- 关键改写点在 [core/services/scheduler/run/schedule_candidate_runner.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/run/schedule_candidate_runner.py:387)：`_candidate_cfg()` 会 `replace(base_cfg, algo_mode="greedy", ...)`，所以每个候选内部的 `candidate_cfg.algo_mode` 变成 `greedy`。
- 被采用候选的 `algo_mode` 进入 `SummaryBuildContext.ctx.algo_mode`，位置在 [core/services/scheduler/run/schedule_orchestrator.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/run/schedule_orchestrator.py:378)。
- [core/services/scheduler/summary/schedule_summary_assembly.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/summary/schedule_summary_assembly.py:288) 到 [core/services/scheduler/summary/schedule_summary_assembly.py](/Users/lurenxing/Documents/GitHub/----/core/services/scheduler/summary/schedule_summary_assembly.py:296) 把 `ctx.algo_mode` 写成 `result_summary.algo.mode`。
- 分析页读取历史摘要在 [web/routes/domains/scheduler/scheduler_analysis_read.py](/Users/lurenxing/Documents/GitHub/----/web/routes/domains/scheduler/scheduler_analysis_read.py:21)。
- 模板 [templates/scheduler/analysis_parts/_selected_overview.html](/Users/lurenxing/Documents/GitHub/----/templates/scheduler/analysis_parts/_selected_overview.html:9) 直接读 `algo.mode`，映射在 [web/viewmodels/scheduler_analysis_overview.py](/Users/lurenxing/Documents/GitHub/----/web/viewmodels/scheduler_analysis_overview.py:26) 把 `greedy` 翻成“快速模式”。

关键变量：

- `ScheduleConfig.algo_mode=improve`：用户选择的精细计算。
- `candidate_cfg.algo_mode=greedy`：候选比较内部强制使用的基础算法。
- `ctx.algo_mode=greedy`：最终采用候选传给摘要的模式。
- `result_summary.algo.mode=greedy`：页面当前误用的字段。
- `result_summary.algo.config_snapshot.algo_mode=improve`：更能代表用户本次设置的字段。
- `ortools_enabled=yes`：配置已开，但候选比较路径把候选改成 `greedy` 后，OR-Tools warm-start 不会进入。

OR-Tools 结论：

- OR-Tools 未安装/探测插件未启用，不是“快速模式”这句显示错的直接原因。
- 直接原因是页面读了候选内部的 `algo.mode`。
- 相关问题仍然存在：[plugins/ortools_probe_plugin.py](/Users/lurenxing/Documents/GitHub/----/plugins/ortools_probe_plugin.py:1) 默认探测插件未启用；[core/algorithms/ortools_bottleneck.py](/Users/lurenxing/Documents/GitHub/----/core/algorithms/ortools_bottleneck.py:43) 导入 `ortools` 失败时会返回 `None`，用户不一定能看到“高质量起点不可用”的明确提醒。

## 建议修复方向

分析页的“计算模式”不应直接用 `algo.mode`。应优先来自本次历史摘要里的 `algo.config_snapshot.algo_mode`，并结合候选对比状态显示真实中文，例如“精细计算（已比较 8 个方案）”。另补回归：`config_snapshot.algo_mode=improve` 且候选对比完成时，页面不能显示“快速模式”。

另外建议单独补一个提示：当 `ortools_enabled=yes` 但 OR-Tools 组件不可导入时，页面或排产结果要明确告诉用户“深度优化组件未安装/不可用，已继续用普通候选对比完成排产”，不要静默让用户猜。
