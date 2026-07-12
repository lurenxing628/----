---
doc_type: issue-fix
issue: 2026-07-11-callgraph-confidence-kiss-hardening
path: standard
fix_date: 2026-07-11
status: fixed
severity: P1
root_cause_type: data-model-and-fail-open
related: [callgraph-confidence-kiss-hardening-analysis.md]
roadmap: dependency-cycle-governance
roadmap_item: callgraph-confidence-kiss-hardening
tags: [callgraph, confidence, utf-8, quality-gate]
---

# 调用图确信边与源码读取可信度修复记录

## 1. 实际采用方案

采用 analysis 中确认的方案 B：删除非直接 `self` 属性调用的 typed 确信提升，只保留直接语法能够证明的确信边，同时补齐调用点行号和严格 UTF-8 fail-closed。

### 1.1 调用点身份

- 属性调用由 `(receiver_text, method_name)` 改为 `(receiver_text, method_name, line)`。
- 同一接收者和方法出现在不同源码行时不再在提取阶段折叠。
- 边输出仍按唯一函数关系计数：直接 `self` 和导入模块属性的重复调用站点不会重复制造同一关系边。

### 1.2 确信边 KISS 合同

保留以下直接语法确信边：

- 直接 `self.method()`，且方法属于当前类；
- 明确本地函数；
- 明确导入函数 / alias；
- 明确导入模块属性。

以下接收者统一保留为 `kind=attr, ambiguous=true`：

- `self.repo.method()`；
- `repo.method()`；
- `factory().method()`；
- 其它不能从调用语法直接证明具体对象的方法调用。

删除了 `callgraph_type_index.py`、`_merge_typed()` 和 class-bases 类型推断链；不再维护参数注解、局部赋值、构造调用、返回注解或 `self.<attr>` 的半套值流推断。`summary.json` 继续保留 `typed_edges` 字段以维持输出结构，但值固定由实际边统计为 0。

### 1.3 源码读取 fail-closed

- 去掉 `errors="replace"`，源码严格按 UTF-8 读取。
- `OSError`、`UnicodeError`、`SyntaxError` 都进入明确错误列表。
- 主流程在解析错误存在时先抛出 `RuntimeError`，不会继续生成本次可信调用图。

## 2. 改动文件清单

### 调用图实现

- `.codestable/checkup/scripts/callgraph_call_sites.py`
  - 属性调用点增加行号。
- `.codestable/checkup/scripts/callgraph_extract.py`
  - 严格 UTF-8；删除 typed 合并主链；适配三元调用点并保持关系边去重。
- `.codestable/checkup/scripts/callgraph_function_index.py`
  - 删除仅供旧类型推断使用的 class-bases 索引。
- `.codestable/checkup/scripts/callgraph_type_index.py`
  - 删除，不保留兼容 shim 或静默回退。

### 门禁与类型检查清单

- `pyrightconfig.tools.json`
- `tools/quality_gate_shared.py`
- `tests/gate_meta/test_quality_gate_registry_split_scope_contract.py`

三处同步移除已删除的 type-index 路径，继续保持 Pyright include、正式工具清单和 long-gate scope 一致。

### 回归与 CodeStable 记录

- `tests/gate_meta/test_callgraph_receiver_resolution.py`
- `.codestable/issues/2026-07-11-callgraph-confidence-kiss-hardening/`
- `.codestable/roadmap/dependency-cycle-governance/`

没有修改 `.codestable/checkup/latest/callgraph/*.json`、`.codestable/checkup/baseline.json`、两份 import-cycle 基线或业务代码。

## 3. 验证结果

### 3.1 失败测试先行

实现前运行新增合同，得到稳定的 6 个失败：

- 四元接收者测试仍返回二元 tuple；
- 同形调用点在不同行被折叠；
- 参数/`self.attr` 等接收者仍产生 typed 确信边；
- `for` 目标重绑定仍拼出双向 typed 假循环；
- 非法 UTF-8 仍返回 AST 且错误为空；
- 全量调用图仍报告 `typed_edges=1179`。

### 3.2 修复后回归

已通过：

- 调用图专项合同：`14 passed`。
- 调用图、import-cycle、v2 基线、正式计划、registry 与 long-gate 定向回归：`194 passed`。
- 生产正式 import-cycle 命令返回 0：
  - `.venv/bin/python -m tools.scan_import_cycles --fail-on-new-cycle --quiet-when-clean`
- 含测试正式 import-cycle 命令返回 0：
  - `.venv/bin/python -m tools.scan_import_cycles --include-tests --fail-on-new-cycle --quiet-when-clean`
- Ruff：通过。
- Pyright tools：`0 errors, 0 warnings`。
- Python 3.8.10 兼容语法扫描：4 个目标文件、0 发现。

含测试正式命令首次复核时发现，本测试文件新增 `pytest` import 导致既有 `spec_from_file_location()` unresolved 站点从第 24 行漂移到第 26 行。没有刷新基线，而是移除不必要的 pytest 依赖并用显式 `try/except` 断言，使调用点恢复第 24 行；随后正式命令通过。

### 3.3 独立临时目录双跑

调用图连续输出到两个独立临时目录；10 个 JSON 文件集合和逐文件 SHA256 完全一致，未覆盖仓库快照。当前临时结果：

- callable：7329；
- 输出边：25772；
- 确信边：10152；
- ambiguous 边：15620；
- typed 边：0；
- 长度 2-8、最多 200 条的确信边简单循环记录：8；
- parse errors：0。

确信边下降、ambiguous 边上升是删除不完整类型推断后的预期保守收敛，不通过刷新快照把差异提前写成终态事实。

## 4. 遗留事项

- 仓库中的调用图快照、`baseline.json` 和 `artifact_sha256` 仍是旧工具口径；其中旧 baseline 仍提及已删除的 `callgraph_type_index.py`。这是第 9 项证据重建前的明确中间状态，不在本 issue 内提前修补。
- 第 9 项 `dependency-proof-rebuild-and-closure` 需要重新双跑、人工核对边与循环差异，再统一刷新快照、哈希和事实文档。
- 当前真实 6/7 个 hard 目录 SCC 以及 scheduler A1 四目录圈仍未结构清零；不得直接跳到 A1。
- 工作区原本已有大量未提交改动，本次只有局部验证，不能声称 clean-worktree proof。
- 未调用 subagent，未提交、未推送、未创建 PR。

## 5. 后续证据状态

2026-07-11 第 9 项 `dependency-proof-rebuild-and-closure` 已按本 issue 产出的最终工具双跑：两个独立临时目录的 10 个 JSON 逐文件 SHA256 完全一致，并已受控覆盖正式调用图快照；`baseline.json` 已移除 `callgraph_type_index.py`，当前机器数字与上文临时结果一致。重建动作最初发生在脏工作区，但用户随后授权提交，最终 19 步门禁已在 clean HEAD 上无缓存、无续跑通过；上方遗留事项保留本 issue 独立完成时的历史状态。
