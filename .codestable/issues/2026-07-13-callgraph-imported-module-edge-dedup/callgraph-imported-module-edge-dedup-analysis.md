---
doc_type: issue-analysis
issue: 2026-07-13-callgraph-imported-module-edge-dedup
status: confirmed
root_cause_type: logic
related: [callgraph-imported-module-edge-dedup-report.md]
tags: [callgraph, tooling, evidence, kiss]
---

# Imported-module 调用图边双计根因分析

## 1. 问题定位

| 关键位置 | 说明 |
|---|---|
| `.codestable/checkup/scripts/callgraph_call_sites.py:67-89` | 同一属性调用同时进入完整 `attr` 集与 direct-name `module_attr` 集。 |
| `.codestable/checkup/scripts/callgraph_extract.py:200-209` | imported-module 规则产出确信边，但不返回已消费 callsite。 |
| `.codestable/checkup/scripts/callgraph_extract.py:171-186` | 通用 attr 规则再次按方法名扩展同一 callsite。 |
| `.codestable/checkup/scripts/callgraph_extract.py:231-252` | `_resolve_edges` 无条件依次调用两个分支，没有互斥。 |
| `.codestable/checkup/scripts/callgraph_extract.py:256-268` | fan 统计按 edge record 逐条累加，双记录会实际影响指标。 |
| `tests/gate_meta/test_callgraph_receiver_resolution.py:103-109` | 测试只断言确信边存在，没有断言模糊副本不存在。 |

`.codestable/checkup/scripts/` 不在 symbol-locator 常规 SCIP 索引根中，本次影响面以直接源码、AST 最小复现和正式 `edges.json` 统计核对。

## 2. 失败路径还原

**正常路径**：AST callsite 保留 `(receiver, method, line)` → imported-module alias 精确命中 → 输出一条确信边 → 该 callsite 不再进入模糊候选。

**失败路径**：`collect_calls` 把同一 callsite 同时放入 `attr` / `module_attr` → `_add_imported_module_attr_edges` 产出确信边 → `_add_attr_edges` 再按同名函数全局扩展模糊边 → `_fan_counts` 双计。

**分叉点**：`.codestable/checkup/scripts/callgraph_extract.py:250-252` - 两套 resolver 并列执行，却没有“已解析 callsite”回执。

## 3. 根因

**根因类型**：逻辑错误。

**根因描述**：调用点提取为了不同消解策略保留了两种视图，但消解阶段把它们当成两批独立调用。工具没有以 callsite 身份协调精确与模糊分支，导致“精确结果补充模糊结果”而不是“精确结果取代模糊候选”。

**是否有多个根因**：单一主因。测试只验证精确边存在、不验证分支互斥，是该问题能进入正式快照的覆盖缺口。

## 4. 影响面

- **影响范围**：direct imported-module 属性调用的 edge records、fan-in/out、high-fan-in 和风险排序。
- **潜在受害模块**：调用图生成物、checkup baseline 数字、引用调用图计数的架构/issue/refactor 文档。
- **数据完整性风险**：无业务数据风险；风险是治理证据失真。
- **严重程度复核**：维持 P2。确信 cycle 图不受模糊副本影响，但工具闭环数字需修正。

## 5. 修复方案

### 方案 A：最终输出阶段按 source/target 去重

- **做什么**：生成全部 edges 后统一去重，确信边覆盖模糊边。
- **优点**：代码短。
- **缺点 / 风险**：会误合并“直接调用”和“函数引用”等不同真实证据，掩盖根因；edge kind 语义不清。
- **影响面**：`callgraph_extract.py`、全部生成物。

### 方案 B：按 callsite 让精确与模糊分支互斥（选定）

- **做什么**：让 `_add_imported_module_attr_edges` 返回成功解析的 `(receiver, method, line)` 集；调用通用 `_add_attr_edges` 前从原 attr 集中扣除。
- **优点**：直接修根因，保留其它不同类型的边证据；利用本轮已新增的完整 callsite 身份，KISS 且影响面窄。
- **缺点 / 风险**：会改变正式调用图计数和若干排序，需要受控重建快照/哈希并解释差异。
- **影响面**：`callgraph_extract.py`、`test_callgraph_receiver_resolution.py`、调用图生成物和 checkup baseline。

### 方案 C：保留双记录，只重命名指标

- **做什么**：把 `total_edges` 改称 edge records，fan 指标继续双计并在文档解释。
- **优点**：不刷新快照结构。
- **缺点 / 风险**：保留无价值噪音，热点排序仍被污染，不符合 KISS。
- **影响面**：工具说明和所有引用文档。

### 推荐方案

**推荐并选定方案 B**。它只让同一 callsite 的精确/模糊分支互斥，不做全局粗暴去重，最小且不损失其它证据。用户在审计结论后明确回复“按照你的意见修吧”，已确认按推荐方案实施。
