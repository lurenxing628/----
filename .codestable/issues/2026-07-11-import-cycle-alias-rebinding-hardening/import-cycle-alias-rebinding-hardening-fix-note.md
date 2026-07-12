---
doc_type: issue-fix
issue: 2026-07-11-import-cycle-alias-rebinding-hardening
path: fast-track
fix_date: 2026-07-11
status: fixed
severity: P1
root_cause_type: logic
roadmap: dependency-cycle-governance
roadmap_item: import-cycle-alias-rebinding-hardening
tags: [import-cycle, importlib, ast, quality-gate]
---

# 动态导入别名重绑定假循环修复记录

## 1. 问题描述

import-cycle 扫描器会先用整棵 AST 的 `ast.walk()` 收集 `importlib` 及其加载函数别名，再用这一份全局别名表解析所有动态调用。别名后来被参数、赋值、循环目标等名字绑定覆盖时，扫描器仍把 `loader.import_module("pkg.b")` 当成真实动态 import 边。

最小反例中，`pkg.a` 先把 `loader` 从 `importlib` 重绑定为普通对象，再调用同名方法；配合 `pkg.b -> pkg.a` 的真实静态边，旧扫描器会制造不存在的 `pkg.a <-> pkg.b` 显式 hard 文件 SCC。

本问题是依赖治理证据错误，不代表业务运行已经发生循环导入故障；但它会误导后续 A1 解耦，所以按 P1 工具可信度缺口处理。前序审查已定位单一根因并确认 KISS 合同，本次走 fast-track，不重复建立 report / analysis。

## 2. 根因

- `tools/import_cycle_analysis.py:132` 原先按整棵 AST 汇总动态加载器别名，丢失词法作用域和遮蔽关系。
- 动态调用解析只检查“这个名字是否曾经来自 importlib”，没有检查当前作用域中是否存在参数、赋值、循环目标、`with as`、`except as`、函数/类定义或 `del` 等重绑定。
- 不可证明的调用没有进入 unresolved，而是被错误提升为 resolved hard/lazy/cond 边，最终参与 SCC 计算。

## 3. 修复方案

本次只增加扫描器需要的最小词法绑定判断，不做跨语句值流或完整符号执行：

- 在模块、函数、lambda 和类作用域内分别收集名字绑定；嵌套作用域不会污染外层，类体本地别名也不会泄漏到方法作用域。
- 只有来源能直接证明为 `importlib`、`importlib.util`、`import_module`、`spec_from_file_location` 或未遮蔽 `__import__`，且同一作用域没有其它重绑定时，调用才可解析。
- `import importlib` 与 `import importlib.metadata` / `import importlib.util` 共同绑定同一个根包属于一致证据，继续保留为可信别名。
- 参数、普通赋值、调用前后重绑定、循环目标、`with/except` 目标、函数/类定义、删除和直接 `import_module` 别名重绑定都会使该名字失效。
- 失效后仍能看出是动态加载器候选的调用，不再画 import 边，而是写入带 `context`、`line` 和表达式的 unresolved 记录，例如：

```text
unproven loader binding: loader.import_module('pkg.b')
```

- 条件、异常、循环和 with 分支中的别名状态按分支隔离；没有实现分支合流推断，不能直接证明时保持 unresolved。

## 4. 改动文件清单

- `tools/import_cycle_analysis.py`
  - 增加作用域内名字绑定与可信加载器来源判定。
  - 动态导入 visitor 按词法作用域维护别名，遮蔽后输出 unresolved。
- `tests/gate_meta/test_import_cycle_scanner.py`
  - 锁住外层可信别名不被嵌套参数误伤、本地可信别名仍可解析。
  - 覆盖普通赋值、调用后重绑定、直接函数别名、循环、with、except、函数/类定义、删除、参数和 `__import__` 遮蔽。
  - 用临时双模块证明重绑定别名不再制造显式 hard 文件 SCC。
  - 锁住 `importlib` 与其 metadata/util 子模块共同导入不回退。
- `.codestable/roadmap/dependency-cycle-governance/`
  - 第 7 项回填完成状态和本 issue 路径。
- `.codestable/issues/2026-07-11-import-cycle-alias-rebinding-hardening/`
  - 本 fast-track 修复记录。

没有修改或刷新两份 import-cycle 基线、调用图快照、checkup 数字或业务代码。

## 5. 验证结果

### 失败测试先行

实现前先新增三类回归并运行：

```text
3 failed, 11 deselected
```

失败分别命中：嵌套参数遮蔽仍被解析、9 类名字重绑定仍被解析、重绑定别名仍制造 `pkg.a <-> pkg.b` 假 SCC。说明测试不是事后补绿。

### 修复后定向验证

已通过：

- `tests/gate_meta/test_import_cycle_scanner.py`：`14 passed`。
- 扫描器 + v2 基线：`26 passed`。
- 扫描器、v2 基线、正式计划、registry 与 long-gate 定向回归：`180 passed`。
- 生产正式命令：
  - `.venv/bin/python -m tools.scan_import_cycles --fail-on-new-cycle --quiet-when-clean`
  - 返回 0，quiet 模式无输出。
- 生产 + 测试正式命令：
  - `.venv/bin/python -m tools.scan_import_cycles --include-tests --fail-on-new-cycle --quiet-when-clean`
  - 返回 0，quiet 模式无输出。
- Ruff：通过。
- Pyright tools 配置：`0 errors, 0 warnings`。
- Python 3.8.10 兼容语法扫描：2 个目标文件、0 发现。
- `git diff --check`：通过。

两条正式命令第一次执行曾暴露 `import importlib` 与 `import importlib.metadata` / `importlib.util` 的同源重复绑定被过度保守降级；修正为“同名绑定来源种类一致即可证明”并补测试后，双 scope 均在不刷新基线的前提下通过。

## 6. 遗留事项与边界

- 本 issue 只修动态加载器别名重绑定假边；没有清理当前 6/7 个 hard 目录 SCC，也没有实施 scheduler A1。
- 调用图 typed 假确信边和严格 UTF-8 问题仍由 roadmap 第 8 项 `callgraph-confidence-kiss-hardening` 单独处理。
- 快照、双基线、哈希和事实文档统一重建仍由第 9 项 `dependency-proof-rebuild-and-closure` 承接；本次禁止提前刷新。
- 工作区原本已有大量未提交改动，因此这里只能提供本轮局部验证，不能声称 clean-worktree proof。
- 未提交、未推送、未创建 PR。

## 7. 后续证据状态

2026-07-11 第 9 项 `dependency-proof-rebuild-and-closure` 已用最终 scanner 生成生产和含测试候选 v2 基线；两份候选文件分别与正式基线逐字节一致，证明现有 SCC、圈内边和 unresolved 身份没有被本修复偷偷改变。正式 CLI 已受控重写双基线并纳入最终 artifact SHA；当前仍是 dirty-worktree 局部证明。
