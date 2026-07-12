---
doc_type: issue-report
issue: 2026-07-10-dependency-governance-tooling-trust
status: resolved
severity: P1
summary: 调用图、循环扫描、循环基线和正式质量门禁存在误报、漏报与放行缺口，导致依赖治理证据不可信
tags: [callgraph, import-cycle, quality-gate, tooling]
---

# 依赖治理工具可信度问题报告

## 1. 问题现象

- 当前调用图报告 20 条函数简单循环记录，其中 12 条由 `self.repo.get()`、`self.batch_repo.create()`、`snapshot.to_dict()` 等复杂接收者被错认成当前类 `self` 方法造成。
- import 扫描没有进入 `for`、`async for`、`while`、`async with` 等语句体，且非固定字符串动态导入会被静默忽略。
- 当前循环基线只保存 SCC 成员；成员不变时新增反向模块边仍可通过。
- 基线不存在时 `--fail-on-new-cycle` 只提示后成功；源码解析失败也不会在该正式模式明确阻断。
- `scripts/run_quality_gate.py` 的共享正式命令计划没有生产和含测试的全仓循环扫描。

## 2. 复现步骤

1. 读取 `.codestable/checkup/latest/callgraph/cycles.json`，可见 20 条记录以及 12 条已知复杂接收者误报。
2. 查看 `.codestable/checkup/scripts/callgraph_extract.py:138-143,286-294`，属性调用只保留方法尾名，并按同名当前类方法直接画 `self` 确信边。
3. 查看 `tools/import_cycle_analysis.py:15-32`，可见语句分类没有循环和 `AsyncWith` 分支。
4. 用临时源码把 import 放入上述语句体，调用 `scan()`，缺失结构不会产生预期边。
5. 用不存在的 `--baseline` 执行 `python -m tools.scan_import_cycles --fail-on-new-cycle`，当前实现提示“跳过新增判定”并返回 0。
6. 查看 `tools/quality_gate_shared.py:706-844` 的共享命令计划，找不到 `tools.scan_import_cycles`。

## 3. 期望行为与实际行为

### 期望

- 只有能确认真实接收者时才产生确信调用边；复杂接收者不误连，真实递归保留。
- 所有要求的语句体都按执行时机分类；无法解析的动态导入进入明确清单。
- 正式模式对缺失/损坏/不支持基线、源码解析失败和扫描异常 fail closed。
- SCC 成员不变但新增圈内有向模块边时门禁失败。
- 生产与含测试扫描使用独立基线，并进入正式命令计划的哈希、收据、重放和长门禁证明。

### 实际

- 复杂接收者被最后一个方法名折叠，产生 12 条假确信循环。
- 部分语句体和非固定动态导入没有证据记录。
- 缺基线、解析失败或成员不变的新边可能被正式模式放行。
- 正式门禁没有执行全仓循环扫描。

## 4. 环境信息

- 分支：`feat/default-light-improve-sgs`
- 起点 HEAD：`cd6cdf43798e3c6321370e4fceb7150bbe4cef3c`
- 起点生产扫描：741 模块、0 解析失败、6 硬目录圈、0 硬文件圈、2 延迟/条件目录圈、5 运行时文件圈。
- 起点含测试扫描：1431 模块、0 解析失败、7 硬目录圈、0 硬文件圈。
- 目标兼容：Python 3.8、Win7 x64、离线交付。

## 5. 严重程度与优先级

P1。当前没有证据表明业务运行已经故障，但正式门禁可能放过新增结构债，调用图又会把误报当真实调用链；这会直接误导后续 A1-A6 解耦和审查结论，应先于结构重构修复。

## 6. 2026-07-10 解决状态

已按根因修复并进入正式证明链：

- 调用图保留完整接收者，未知重赋值不提升 typed 边；import alias 按声明来源消解，嵌套 def/lambda 独立建点。12 条已知假循环消失，8 条已知真实递归保留。
- import 扫描补齐语句体、相对字面量动态导入、`__import__`/文件加载器报告、父包初始化、顶层入口和插件 scope；同时输出父包感知与纯显式文件 SCC 双口径。
- v2 双基线锁定 schema/scope/roots/文件加载语义、圈成员、圈内规范化边和未解析动态导入；缺失、损坏、scope 漂移、parse error 与扫描异常全部 fail closed。
- 两条扫描命令已加入共享正式计划并成为不可删除证明，接入命令哈希、逐步收据、重放、required registry、Pyright 与 long-gate 稳定 entry。
- 当前验证属于未提交脏工作区局部证明，不是 clean-worktree proof；详细文件和测试证据见同目录 fix-note。
