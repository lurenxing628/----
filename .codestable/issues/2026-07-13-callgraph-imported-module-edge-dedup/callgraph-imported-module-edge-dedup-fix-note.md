---
doc_type: issue-fix
issue: 2026-07-13-callgraph-imported-module-edge-dedup
path: standard
fix_date: 2026-07-13
status: fixed
severity: P2
root_cause_type: logic
related: [callgraph-imported-module-edge-dedup-analysis.md]
tags: [callgraph, tooling, evidence, kiss]
---

# Imported-module 调用图边双计修复记录

## 1. 实际采用方案

采用 analysis 选定的方案 B：以 callsite 身份让 imported-module 精确消解和通用 attr 模糊消解互斥。

- `_add_imported_module_attr_edges()` 在生成 `module_import_attr, ambiguous=false` 后，返回成功解析的 `(receiver, method, line)` 集合。
- `_resolve_edges()` 在调用 `_add_attr_edges()` 前，从完整 attr callsite 集中扣除这些已解析项。
- 不做最终 source/target 粗暴去重；不同真实证据类型（例如 direct call 与 function reference）仍可各自保留。
- fan-in/fan-out 继续按 edge record 口径计算，但同一 imported-module callsite 不再同时进入精确和模糊两套记录。

## 2. 改动文件清单

### 工具与测试

- `.codestable/checkup/scripts/callgraph_extract.py`
  - 精确 resolver 返回已消费 callsite；通用 attr resolver 只处理剩余项。
- `tests/gate_meta/test_callgraph_receiver_resolution.py`
  - 在原 imported-module 精确解析测试中，同时断言同端点最终只有唯一确信记录。

### 重建证据

- `.codestable/checkup/latest/callgraph/articulation_points.json`
- `.codestable/checkup/latest/callgraph/dynamic_unresolved.json`
- `.codestable/checkup/latest/callgraph/edges.json`
- `.codestable/checkup/latest/callgraph/functions.json`
- `.codestable/checkup/latest/callgraph/islands.json`
- `.codestable/checkup/latest/callgraph/summary.json`
- `.codestable/checkup/baseline.json`
- `.codestable/checkup/README.md`

`cycles.json`、`dataflow_nodes.json`、`high_fan_in.json`、`risk_dataflow.json` 的候选 SHA 与旧正式文件相同，因此没有制造无意义改动。baseline 的 25 项 artifact SHA 已全部重算。

### 事实文档

- A3 apply notes、循环依赖审计、模块架构审计
- 本轮未推送提交 audit
- 本 issue 的 report / analysis / fix-note

## 3. 验证结果

### 3.1 失败测试先行

新增断言在旧实现上稳定失败，实际多出：

```text
main.py::run -> helpers.py::actual  kind=attr  ambiguous=True
```

修复后同一最小输入只保留：

```text
main.py::run -> helpers.py::actual  kind=module_import_attr  ambiguous=False
```

### 3.2 独立双跑与差异解释

调用图分别输出到两个独立临时目录：

- `/tmp/aps-review-callgraph-run1-PB8Wmv`
- `/tmp/aps-review-callgraph-run2-kdpbIl`

两边均有同一组 10 个 JSON，逐文件 SHA256 全部相同。

相对旧正式快照：

- edge records：25798 → 25688；
- confident：10171 → 10172；
- ambiguous：15627 → 15516；
- callable：7337 → 7337，零丢失/零新增；
- cycle：8 → 8；
- island：193 → 195；
- dynamic unresolved：685 → 685；
- parse errors：0。

逐条 Counter 核对得到：

- 删除 111 条，全部是 `kind=attr, ambiguous=true`；
- 111 条全部能由同 source / 同方法名的 `module_import_attr` 确信边解释，未解释删除为 0；
- 新增仅 1 条 sibling issue 带来的 `schedule_internal → validate_internal_hours_for_mode, kind=import, ambiguous=false`；
- 旧快照中 `module_import_attr` 与 `attr` 同 source/target 重叠 88 组，修复后为 0；
- 新快照 25688 records 与 25679 唯一端点边相差 9。逐项均为 function-reference 与 import/self/attr 等不同证据类型，不是同 callsite 精确/模糊双消解。

### 3.3 正式快照、哈希与门禁

- 以已核对的 run-1 覆盖正式 10 JSON；逐文件复核与候选相同。
- `baseline.json` 当前数字与 `summary.json` 完全对齐。
- baseline 记录的 25 项 artifact SHA256 全部复算匹配。
- 生产与含测试双 scope import-cycle 门禁均返回 0，循环基线无需刷新。
- 完整 `tests/algorithm` + receiver-resolution：574 passed。
- 完整质量门禁 19/19 receipts returncode 0，4734 collected、unexpected failure 0、required 253 targets / 2467 nodeids。
- manifest=`passed_but_unbound`、tracked drift=false；当前没有 clean-worktree proof。

## 4. 遗留事项

- 剩余 9 组同端点多种 record 是不同证据语义，不在本 issue 中用全局去重抹掉；如未来要把 records 与唯一依赖边拆成两套公开指标，应另开设计事项，不在 bug 修复中扩域。
- 修复尚未 commit、未 push；当前 `clean_worktree_proof=false`。
- 若用户授权 scoped commit，提交后需在固定干净 HEAD 重跑完整门禁，成功后再建议 push。
- 没有未解释的调用图漂移，也没有其它代码 blocker。
