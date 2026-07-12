---
doc_type: issue-report
issue: 2026-07-11-callgraph-confidence-kiss-hardening
status: confirmed
severity: P1
summary: 调用图把非直接 self 属性调用提升为 typed 确信边、丢失调用点行号，并静默替换非法 UTF-8 字节
roadmap: dependency-cycle-governance
roadmap_item: callgraph-confidence-kiss-hardening
tags: [callgraph, confidence, utf-8, quality-gate]
---

# 调用图确信边与源码读取可信度问题报告

## 1. 问题现象

调用图当前仍存在三类不能作为可信证据的表现：

- `self.repo.method()`、`repo.method()` 和 `factory().method()` 等非直接 `self` 属性调用会被提升为 `kind=typed, ambiguous=false`，从而进入确信图、扇入扇出和简单循环计算。
- 属性调用点只保存 `(receiver_text, method_name)`；同一接收者和方法出现在多行时会在提取阶段折叠，无法保留每个调用点的行号证据。
- 源文件包含非法 UTF-8 字节时仍能得到 AST，错误清单为空，可信扫描不会阻断。

这些表现会让调用图把推断结果写成确定事实，也会把损坏源码报告成“解析错误为 0”。

## 2. 复现步骤

1. 构造两个带参数类型注解的方法，让 `Repository.get()` 调用 `Service.inspect()`，`Service.inspect()` 内先用 `for repo in items` 覆盖参数 `repo: Repository`，再调用 `repo.get()`。
2. 运行当前调用图消解，观察两条调用均可进入 typed 确信边并形成不存在的双向确信循环。
3. 构造一个函数，在两个不同行分别调用同一个 `repo.get()`；运行 `collect_calls()`，观察属性调用集合只剩一个 `("repo", "get")`。
4. 创建含非法 UTF-8 字节的临时 `.py` 文件并调用 `_parse_file()`；观察当前实现返回非空 AST，错误字符串为空。

复现频率：稳定。

## 3. 期望 vs 实际

**期望行为**：

- 只有直接 `self.method()`、明确本地函数、明确导入函数和明确导入模块属性依靠直接语法证据生成确信边。
- 其它属性接收者统一保持 `kind=attr, ambiguous=true`，不靠参数注解、局部赋值、构造调用或返回注解提升。
- 属性调用点至少保留 `(receiver_text, method_name, line)`，不同行不得在提取阶段折叠。
- 源码严格按 UTF-8 读取；`OSError`、`UnicodeError`、`SyntaxError` 都进入明确错误并阻断可信输出。

**实际行为**：

- 半套类型推断仍会制造 typed 确信边和假确信循环。
- 调用点行号在进入边消解前丢失。
- `errors="replace"` 把非法字节静默替换，解析错误仍显示为空。

## 4. 环境信息

- 涉及模块：CodeStable 调用图提取与依赖治理证明链。
- 相关文件：
  - `.codestable/checkup/scripts/callgraph_call_sites.py`
  - `.codestable/checkup/scripts/callgraph_extract.py`
  - `.codestable/checkup/scripts/callgraph_function_index.py`
  - `.codestable/checkup/scripts/callgraph_type_index.py`
  - `tests/gate_meta/test_callgraph_receiver_resolution.py`
- 运行环境：本地 dirty workspace，目标工具继续兼容 Python 3.8。
- 约束：本 issue 不刷新调用图快照、checkup baseline 或 artifact 哈希；终态证据统一由 roadmap 第 9 项重建。

## 5. 严重程度

**P1**。没有证据表明 APS 业务运行故障，但调用图会直接影响后续 A1-A6 解耦的审查依据；假确信边和静默解码会使“可信调用图”结论失真，应在结构重构前修复。

## 备注

本报告对应 roadmap 第 8 项。用户已接受第 7 项闭环并明确要求继续第 8 项；报告中的现象、范围和期望合同已在前序 roadmap 评审中确认。
