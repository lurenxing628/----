---
doc_type: issue-fix
issue: 2026-07-10-dependency-governance-tooling-trust
path: standard
fix_date: 2026-07-10
tags: [callgraph, import-cycle, quality-gate, baseline, proof]
---

# 依赖治理工具可信度修复记录

## 1. 问题描述

起点依赖治理证据有五类根因缺口：调用图把复杂接收者错连为当前类同名方法，import alias 与嵌套 callable 断边/错归属；import 扫描漏语句体、相对动态导入、父包初始化、顶层入口与插件；单基线只比较 SCC 成员且缺 scope；正式模式对缺基线和 parse error 放行；正式质量门禁没有执行循环扫描。

这些问题没有证明业务已经故障，但会让 A1-A6 解耦建立在错误数字上，因此先于结构重构修复。

## 2. 根因修复

### 2.1 调用图

- 属性调用保留完整接收者文本，只有直接 `self.method()` 才画当前类 `self` 确信边。
- `self.attr`、参数/局部注解、构造赋值和唯一返回注解只在类型唯一时提升 typed 边；未知或冲突重赋值会使推断失效。
- imported-bare/alias 按 import 声明来源精确定位，不再退化为全仓同名匹配。
- 嵌套 def/lambda 建独立 callable 节点，外层遍历不再吞入其执行体；lambda 定义关系保持为 ambiguous。
- 数据流、call-site、函数索引、类型索引按职责拆成 leaf helper；主脚本 500 行门禁内为 466 行。
- `cycle_count` 明确为确信边上长度 2-8、最多 200 条的简单循环记录，不称 SCC。

### 2.2 import 扫描

- 静态分类覆盖 function/async function、class、if、try/except/else/finally、for/async for、while、with/async with，并保持 lazy/typeonly 外层优先级。
- 动态扫描支持绝对/相对字面量 `import_module`、importlib/import_module/spec loader alias、name/package 关键字、`__package__`/`__name__` 与 `__import__`；变量、拼接、f-string 和文件 loader 生成未解析证据。
- 生产非测试 scope 纳入 `plugins` 和顶层 `*.py` 入口；含测试另加 `tests`。
- 显式建 Python 父包 `__init__.py` 初始化边，并同时报告：
  - 父包感知 hard/runtime 文件 SCC；
  - 纯显式 import hard/runtime 文件 SCC。
- JSON/文本输出包含 parse error、未解析动态导入、父包初始化边、runtime 文件 SCC 成员和边，不再只有计数。

### 2.3 v2 双基线与 fail-closed

- 两份基线：
  - `.codestable/checkup/import_cycles_production_baseline.json`
  - `.codestable/checkup/import_cycles_with_tests_baseline.json`
- 基线锁定 `schema_version=2`、scope、scan roots、文件加载语义、hard 目录/文件 SCC 成员、圈内规范化模块边和未解析动态导入。
- 同成员新增边、新 SCC、新未解析动态导入 callsite 失败；删边、整圈消失和 SCC 缩小为旧成员/旧边子集允许。
- 缺失/损坏/旧版/未来版/字段错误/scope 或 roots 不符/文件语义变化/源码解析失败/扫描异常均 fail closed，工具错误码为 2。
- 基线先生成到 `/tmp` 并核对成员、边集、双 scope 一致性和 SHA256，再受控写回；没有用直接刷新掩盖差异。

### 2.4 正式质量门禁

正式共享计划从 17 步增为 19 步，在 Ruff 后、全测试收集前固定执行：

```text
python -m tools.scan_import_cycles --fail-on-new-cycle --quiet-when-clean
python -m tools.scan_import_cycles --include-tests --fail-on-new-cycle --quiet-when-clean
```

两条命令已进入：

- 默认计划顺序与不可删除证明；
- 命令计划哈希、逐步 receipt、stdout/stderr 日志哈希、续跑与重放；
- `import_cycles_production` / `import_cycles_with_tests` 两个 long-gate 稳定 entry 及各自 fingerprint scope；
- `QUALITY_GATE_TOOL_PATHS` / `QUALITY_GATE_SOURCE_FILES`；
- required test registry 与 quality_gate 分组；
- `pyrightconfig.tools.json`。

## 3. 该 issue 完成时的机器事实（历史阶段快照）

> 下面数字保留当时验证记录；2026-07-11 第 7-9 项已进一步收敛工具语义并重建终态证据，当前事实见文末补记和 checkup README。

### 调用图

- callable：7314（含 316 个嵌套 def/lambda）
- 输出边：25299
- 确信边：11320
- 模糊边：13979
- typed 边：1198
- 受限真实简单循环：8
- parse errors：0
- 12 条已知复杂接收者假循环均消失；数据库 `ensure_schema` 的 bootstrap/migration import alias 边已恢复。

### import 扫描

生产非测试：

- 模块 749，parse error 0
- hard 目录 SCC 6
- 父包感知 hard 文件加载 SCC 9
- 纯显式 hard 文件 SCC 0
- 父包感知 runtime 文件 SCC 14
- 纯显式 runtime 文件 SCC 5
- 未解析动态加载 6

含测试：

- 模块 1442，parse error 0
- hard 目录 SCC 7（多出既有 tests 四目录结构圈）
- 父包感知 hard 文件加载 SCC 9
- 纯显式 hard 文件 SCC 0

A1-A6/tests 尚未结构清零；这里完成的是可信测量与防回潮合同。

## 4. 主要改动文件

- 调用图：`.codestable/checkup/scripts/callgraph_{extract,call_sites,dataflow,function_index,type_index}.py`
- 调用图快照：`.codestable/checkup/latest/callgraph/*.json`
- import 分析：`tools/import_cycle_analysis.py`、`tools/import_cycle_graph.py`、`tools/scan_import_cycles.py`
- 基线：`tools/import_cycle_baseline.py`、两份 `import_cycles_*_baseline.json`
- 正式门禁：`tools/quality_gate_shared.py`、`scripts/run_quality_gate.py`、`tools/long_gate_manifest.py`
- registry/type proof：`tools/test_registry_data.py`、`tools/test_registry_groups_scheduler.py`、`pyrightconfig.tools.json`
- 回归：`tests/gate_meta/test_callgraph_receiver_resolution.py`、`test_import_cycle_scanner.py`、`test_import_cycle_baseline.py` 及现有门禁/long-gate/registry 元测试
- 文档：checkup README/baseline、scheduler 架构、循环与模块审计、依赖治理 roadmap

## 5. 验证结果

已通过：

- 调用图、扫描器、基线、正式门禁、long-gate、registry 定向回归：`181 passed`
- 调用图单组最终回归：`9 passed`
- 扫描器 + 基线最终回归：`19 passed`
- 生产与含测试两条正式 `--fail-on-new-cycle --quiet-when-clean`：均返回 0
- `ruff check`：通过
- `pyright -p pyrightconfig.tools.json`：0 errors, 0 warnings
- Python 3.8.10 语法扫描：相关工具/测试 0 发现
- `git diff --check`：通过
- 临时调用图与仓库刷新快照 10 个 JSON SHA256 逐文件一致

三路起点只读审查均已真实等待并读取：工具/门禁定向审查、A1/A2 调用链审查、全仓盲审。它们提出的 B1/B2/H1-H5 中，正式门禁、fail-open、接收者误连、alias/嵌套 callable、父包初始化、scope 和弱基线问题均已修复。通用子代理接口没有暴露具体模型槽，不能从接口证明其型号。

## 6. 未声称完成

- 当前工作区含本轮未提交改动，因此上述验证是脏工作区局部证明，不是 clean-worktree proof。
- 未提交、未推送、未创建 PR。
- A1-A6 和 tests 目录结构圈仍待后续独立 refactor；本 issue 不改变数据库格式、迁移语义、事务范围、排产结果、公开载荷、路由或导出合同。

## 7. 2026-07-11 终态证据重建补记

后续 issue `2026-07-11-import-cycle-alias-rebinding-hardening`、`2026-07-11-callgraph-confidence-kiss-hardening` 和 `2026-07-11-dependency-proof-rebuild-and-closure` 已完成提交前证据重建：

- 删除 `callgraph_type_index.py` 和 typed 确信提升；正式调用图快照为 7329 callable、25772 输出边、10152 确信边、15620 模糊边、typed 0、8 条受限简单循环。
- 两个独立临时调用图目录各 10 个 JSON，逐文件 SHA256 完全一致后才覆盖正式快照。
- 生产/含测试当前为 750/1443 模块、6/7 个 hard 目录 SCC；候选双基线与正式文件逐字节一致，SCC、圈内边和 unresolved 均无增删。
- `baseline.json` 已移除被删除的 type-index 哈希并绑定完整 10 个调用图 JSON；仍明确是 dirty-worktree 局部证明，不是 clean-worktree proof。
