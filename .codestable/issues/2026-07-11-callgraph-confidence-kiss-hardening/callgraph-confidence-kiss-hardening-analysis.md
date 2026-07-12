---
doc_type: issue-analysis
issue: 2026-07-11-callgraph-confidence-kiss-hardening
status: confirmed
root_cause_type: data-model-and-fail-open
related: [callgraph-confidence-kiss-hardening-report.md]
roadmap: dependency-cycle-governance
roadmap_item: callgraph-confidence-kiss-hardening
tags: [callgraph, confidence, typed-edge, utf-8]
---

# 调用图确信边与源码读取可信度根因分析

## 1. 问题定位

| 关键位置 | 说明 |
|---|---|
| `.codestable/checkup/scripts/callgraph_call_sites.py:11-13,67-88` | 属性调用使用二元 tuple 的 set，保存接收者和方法名但丢掉 `line`，同一调用形状会提前折叠。 |
| `.codestable/checkup/scripts/callgraph_extract.py:59-64` | 以 `errors="replace"` 读取源码，非法 UTF-8 不会抛出 `UnicodeError`。 |
| `.codestable/checkup/scripts/callgraph_extract.py:255-275,447-453` | 主流程调用类型索引，并把命中的 attr 模糊边改写成 `typed` 确信边。 |
| `.codestable/checkup/scripts/callgraph_type_index.py:184-212` | 变量类型只处理部分参数、注解和赋值；`for/with/except/解包/推导式` 等名字绑定不会使旧类型失效。 |
| `.codestable/checkup/scripts/callgraph_type_index.py:255-305` | 类型推断结果直接生成 typed 边，并可删除同名 attr 模糊候选。 |

symbol-locator 已按项目规则执行，但 `.codestable/checkup/scripts/` 不在其常规源码索引根，四个目标符号均未命中；影响面改用直接调用检索、AST 合同测试和临时目录全量提取补足。

## 2. 失败路径还原

**正常路径**：AST 提取调用点并保留接收者、方法和行号 → 直接 `self`、本地函数、导入函数、导入模块属性按语法证据生成确信边 → 其它属性调用保留为 ambiguous → 只用确信边计算受限简单循环；源码解码或解析失败时明确阻断，不写可信产物。

**失败路径 A（typed 假循环）**：参数注解先把 `repo` 记为 `Repository` → `for repo in items` 的重绑定未被类型索引处理 → 后续 `repo.get()` 仍被定位为 `Repository.get` → `_merge_typed()` 将 attr 模糊边升级为确信边 → 与反向 typed 边拼成不存在的确信循环。

**失败路径 B（调用点证据丢失）**：两个不同行的 `repo.get()` → `collect_calls()` 写入 `Set[Tuple[str, str]]` → 第二个调用与第一个相同而被集合折叠 → 后续无法知道有两个调用站点及各自行号。

**失败路径 C（静默解码）**：非法字节 → UTF-8 解码以 replacement character 替换 → `ast.parse()` 仍成功 → parse errors 为空 → 主流程继续写调用图并声称源码可解析。

**分叉点**：属性调用在“直接语法证据”和“推断类型”之间没有清晰边界，同时源码读取选择了容错替换而不是可信扫描所需的严格失败。

## 3. 根因

**根因类型**：数据模型不足 + fail-open。

**根因描述**：

1. 调用点身份缺少行号，证据在解析前被压缩。
2. 类型索引试图用不完整的值流规则把普通属性调用升级成确定事实；要让它正确，必须继续实现更多 Python 绑定和控制流语义，超出该工具的 KISS 边界。
3. 源码读取把数据损坏当成可恢复展示问题，而调用图需要的是“不能完整读取就不能证明”的 fail-closed 语义。

**是否有多个根因**：是。调用点数据模型、typed 提升策略和源码读取各自独立，但都会污染“可信调用图”的结论。

## 4. 影响面

- **影响范围**：调用图的确信边、确信扇入扇出、受限简单循环、人工审查优先级和 parse error 统计。
- **潜在受害模块**：所有使用参数注解、局部构造或 `self.<attr>` 的业务服务；后续 scheduler A1-A6 解耦会读取这些图证据。
- **不受影响**：APS 业务运行、数据库格式、事务、迁移、页面载荷和路由；本 issue 只改离线治理工具。
- **数据完整性风险**：不改业务数据；风险是治理证据失真和错误重构决策。
- **严重程度复核**：维持 P1。

## 5. 修复方案

### 方案 A：扩完整类型/值流推断

- **做什么**：继续补 `for/with/except/解包/推导式/闭包/分支合流` 等 Python 绑定语义，再保留 typed 提升。
- **优点**：理论上可继续获得部分确定属性边。
- **缺点 / 风险**：会演变为半个静态分析器；实现和证明成本高，仍容易在未覆盖语义上画错边。
- **影响面**：持续扩张 `callgraph_type_index.py` 和测试矩阵。
- **结论**：拒绝，不符合 KISS。

### 方案 B：删除 typed 提升，只保留直接语法确信边（选定）

- **做什么**：
  - 调用点改为 `(receiver_text, method_name, line)`。
  - 删除类型索引和 `_merge_typed()` 主链；非直接 `self` 属性调用全部保持 ambiguous。
  - 保留直接 `self.method()`、明确本地函数、明确导入函数和明确导入模块属性的确信边。
  - 严格 UTF-8 读取，并把 `OSError`、`UnicodeError`、`SyntaxError` 汇总后在写产物前阻断。
  - 保留 `typed_edges` 摘要字段但值归零，避免无必要的输出 schema 破坏。
- **优点**：删除错误确定性，规则可由直接 AST 证据解释，代码和测试显著收敛。
- **缺点 / 风险**：确信边数量会下降，部分真实对象方法只能作为 ambiguous 候选；这是有意的保守结果。
- **影响面**：call-site、extract、function-index、type-index、Pyright/质量门禁工具清单及定向测试；不改 dataflow/risk 模块。

### 方案 C：引入第三方全量静态分析平台

- **做什么**：用外部类型/调用图引擎替换当前解析。
- **优点**：可能获得更完整的类型语义。
- **缺点 / 风险**：新增大依赖和工具链，破坏 Python 3.8 / Win7 / 离线约束，且仍需适配项目输出合同。
- **结论**：拒绝。

### 确认

采用方案 B。该合同已在 dependency-cycle-governance roadmap 评审中明确，用户在接受第 7 项后指示“继续 8 项”，视为对本项既定 KISS 方案的继续执行授权。
