---
doc_type: audit-finding
audit: 2026-05-21-networkx-full-browser-stress
finding_id: analysis-ready-wording
nature: ux-copy
severity: P2
confidence: high
status: open
suggested_action: cs-issue
last_deep_trace: 2026-05-21
---

# Finding 04：分析页直接使用 ready 英文术语，调度员不容易理解

## 现象

分析页“资源卡点”里出现：

```text
首波 ready 工序里有 7 道暂时无法匹配到可用设备。
```

用户现场批注：这里用了英文术语，而且整体晦涩难懂，让调度员很难看懂。

## 操作步骤

1. 打开 `/scheduler/analysis?version=15`。
2. 查看“资源卡点”区域。

## 实际表现

页面混用“首波 ready 工序”“候选设备”“匹配”等词。对开发者能理解，但调度员不一定知道 ready 是什么。

## 期望表现

改成业务白话，例如：

```text
第一批已经满足前置条件、可以开始安排的工序里，有 7 道暂时找不到可用设备。
```

或把指标名改为：

- “第一批可安排工序”
- “能找到候选设备的工序”
- “暂时排不上设备的工序”

## 问题类型

文案难懂。

## 严重程度

轻微但建议修。它不阻断排产，但会明显增加理解成本。

## 证据

- 浏览器页面：`http://127.0.0.1:61661/scheduler/analysis?version=15`
- 截图：`/tmp/aps-networkx-full-browser-stress.h88s1vh4/browser-artifacts/screenshots/analysis-v15-visible.png`

## 追加根因追踪（2026-05-21）

根因不是模板固定写死了英文，而是分析页 viewmodel 把算法内部词直接拼成了前台文案。模板只是展示 `section.summary`、`item.label`、`item.message` 和 `item.details`。

调用链：

- 分析页入口 [web/routes/domains/scheduler/scheduler_analysis.py](/Users/lurenxing/Documents/GitHub/----/web/routes/domains/scheduler/scheduler_analysis.py:14) 进入 `analysis_page()`。
- [web/viewmodels/scheduler_analysis_vm.py](/Users/lurenxing/Documents/GitHub/----/web/viewmodels/scheduler_analysis_vm.py:98) 的 `build_analysis_context()` 调 `build_diagnostic_sections()`。
- [web/viewmodels/scheduler_analysis_diagnostics.py](/Users/lurenxing/Documents/GitHub/----/web/viewmodels/scheduler_analysis_diagnostics.py:42) 把 `resource_bottleneck` 加进诊断区。
- [web/viewmodels/scheduler_analysis_diagnostic_health.py](/Users/lurenxing/Documents/GitHub/----/web/viewmodels/scheduler_analysis_diagnostic_health.py:167) 的 `_resource_matching_summary()` 生成“首波 ready 工序里有 X 道...”。
- [web/viewmodels/scheduler_analysis_diagnostic_health.py](/Users/lurenxing/Documents/GitHub/----/web/viewmodels/scheduler_analysis_diagnostic_health.py:277) 的 `build_resource_bottleneck_section()` 从 `resource_public` 读取资源匹配计数。
- [templates/scheduler/analysis.html](/Users/lurenxing/Documents/GitHub/----/templates/scheduler/analysis.html:28) include 诊断区模板。
- [templates/scheduler/analysis_parts/_diagnostic_sections.html](/Users/lurenxing/Documents/GitHub/----/templates/scheduler/analysis_parts/_diagnostic_sections.html:15) 负责渲染，文案源头不在模板。

关键变量：

- `ready_operation_count`：第一波已经满足前置条件的工序数。v15 临时库结果是 `9`。
- `matched_operation_count`：已匹配到设备的工序数。v15 是 `2`。
- `unmatched_operation_count`：未匹配到设备的工序数。页面里的 `7` 就来自这个字段。
- `operation_with_candidate_count`：有候选设备的工序数。
- `bottleneck_machine_count`：可能被争用的瓶颈设备数。v15 是 `2`。
- 前台还有其他暴露点：[web/viewmodels/scheduler_analysis_diagnostic_health.py](/Users/lurenxing/Documents/GitHub/----/web/viewmodels/scheduler_analysis_diagnostic_health.py:224) 的“首波 ready 工序”、[web/viewmodels/scheduler_analysis_diagnostic_health.py](/Users/lurenxing/Documents/GitHub/----/web/viewmodels/scheduler_analysis_diagnostic_health.py:257) 的“首波 ready 工序中...”、[web/viewmodels/scheduler_analysis_diagnostic_delay_impact.py](/Users/lurenxing/Documents/GitHub/----/web/viewmodels/scheduler_analysis_diagnostic_delay_impact.py:274) 的“未匹配 ready 工序样本”。

## 建议修复方向

页面面向调度员展示时，不直接暴露 `ready` 这类算法词。后端结果字段可以先保留 `ready_operation_count`，因为它已经被图分析报告和回归测试使用；前台最小修复点应放在 [web/viewmodels/scheduler_analysis_diagnostic_health.py](/Users/lurenxing/Documents/GitHub/----/web/viewmodels/scheduler_analysis_diagnostic_health.py:167) 和 [web/viewmodels/scheduler_analysis_diagnostic_delay_impact.py](/Users/lurenxing/Documents/GitHub/----/web/viewmodels/scheduler_analysis_diagnostic_delay_impact.py:271) 附近，把展示文案改成“第一批已满足前置条件、可以安排的工序”这类白话。

需要补文案回归：分析页诊断区渲染结果不应出现 `ready` 或“未匹配 ready 工序样本”，并应出现可读中文说明。
