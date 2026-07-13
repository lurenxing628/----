---
doc_type: issue-report
issue: 2026-07-13-callgraph-imported-module-edge-dedup
status: confirmed
severity: P2
summary: 一个 imported-module 属性调用被调用图同时记录为确信边和模糊边
tags: [callgraph, tooling, evidence, kiss]
---

# Imported-module 调用图边双计 Issue Report

## 1. 问题现象

调用图处理 `import module as alias` 后的 `alias.function()` 时，同一 source/target 会同时出现一条 `module_import_attr, ambiguous=false` 和一条 `attr, ambiguous=true` 记录。正式快照中至少有 92 组这样的双记录，fan-in/fan-out 和总边记录数被重复抬高。

## 2. 复现步骤

1. 准备 `helpers.py`，定义 `actual()`。
2. 准备 `main.py`，通过 `import helpers as helper_module` 后调用 `helper_module.actual()`。
3. 用 `.codestable/checkup/scripts/callgraph_extract.py` 的 `_collect` / `_resolve_edges` 解析。
4. 观察到 `main.py::run -> helpers.py::actual` 同时输出确信和模糊两条记录。

复现频率：稳定，100%。

## 3. 期望 vs 实际

**期望行为**：同一个 callsite 一旦被 imported-module 规则精确解析，就不应再进入通用 attr 模糊候选分支。

**实际行为**：精确分支和模糊分支都消费同一批属性调用，随后 `_fan_counts` 分别累计。

## 4. 环境信息

- 涉及模块 / 功能：CodeStable 调用图提取、架构证据和风险排序
- 相关文件 / 函数：`.codestable/checkup/scripts/callgraph_extract.py::_resolve_edges`
- 运行环境：当前开发分支 `feat/default-light-improve-sgs`，`HEAD=6433599d`
- 其他上下文：由未推送提交审计发现；工具闭环提交为 `9417bde3`

## 5. 严重程度

**P2** - 不影响业务运行，也不新增确信 import SCC；但会污染正式调用图指标和架构证据，应在继续引用这些数字前修复。

## 备注

来源审计：`.codestable/audits/2026-07-13-unpushed-dependency-governance-review/finding-02.md`。
