---
doc_type: issue-analysis
issue: 2026-07-10-dependency-governance-tooling-trust
status: resolved
root_cause_type: data-model-and-fail-open
summary: 工具在 AST 调用点和循环基线中丢失身份信息，正式模式又没有把不完整证据视为失败
tags: [callgraph, import-cycle, baseline, quality-gate]
---

# 依赖治理工具可信度根因分析

## 1. 问题代码定位

- `.codestable/checkup/scripts/callgraph_extract.py:138-143`：`_call_name()` 对属性调用只返回最后一个 `attr`。
- `.codestable/checkup/scripts/callgraph_extract.py:146-160`：`_calls()` 把所有属性调用压成方法名集合。
- `.codestable/checkup/scripts/callgraph_extract.py:286-294`：只要方法名属于当前类，就生成 `kind=self, ambiguous=false`，没有核对接收者是否真是 `self`。
- `.codestable/checkup/scripts/callgraph_type_index.py:111-158`：只推断简单变量；`self.repo` 等多层接收者计入总数但不能解析。
- `.codestable/checkup/scripts/callgraph_extract.py:407-414,448`：`cycle_count` 来自长度 2-8、最多 200 条的 `networkx.simple_cycles()` 记录，不是 SCC 组数。
- `tools/import_cycle_analysis.py:15-32`：静态 import 分类漏掉循环、`AsyncWith` 等语句体；函数内 `if/try` 还会把外层 lazy 改写成 cond。
- `tools/import_cycle_analysis.py:63-84`：动态导入只返回固定字符串目标，非固定表达式没有记录，也没有复用完整上下文分类。
- `tools/import_cycle_baseline.py:33-40`：基线身份只有排序成员字符串。
- `tools/import_cycle_baseline.py:43-51`：读取时不校验 schema version、scope 和字段结构。
- `tools/scan_import_cycles.py:217-224`：广泛捕获扫描异常并只记 parse_errors；正式模式未检查 parse_errors。
- `tools/scan_import_cycles.py:328-337,359-377`：基线缺失只提示，返回码仍为 0。
- `tools/quality_gate_shared.py:706-844`：共享正式计划没有循环扫描。
- `tools/long_gate_manifest.py:118-155`：当前也没有循环扫描的稳定 entry 分类和 scope。

## 2. 正常路径与失败路径

### 正常路径

AST 调用点保留接收者 → 类型索引在有证据时定位类方法 → 未能定位的边保持不确定 → 只用确信边计算受限简单循环；import AST 完整分类 → 产出解析错误和动态盲区 → 与 scope 匹配的 v2 基线比较成员及圈内边 → 正式计划执行两次扫描并写入收据/哈希/重放证明。

### 当前失败路径

属性调用先丢掉接收者 → 当前类存在同名方法就误画确信 `self` 边 → 假边参与简单循环；import 语句体或动态表达式没有进入证据 → 基线又只比较成员 → 正式计划未运行扫描，即使手工加 `--fail-on-new-cycle`，缺基线和 parse error 仍可能返回成功。

## 3. 根因

1. **身份信息过早丢失**：调用点在解析前被压缩成“方法尾名”，后续无法区分直接 `self` 和对象成员。
2. **上下文模型不完整**：静态 import 和动态 import 使用两套不一致的遍历逻辑，外层 lazy/typeonly 也没有优先级规则。
3. **基线数据模型信息不足**：只存 SCC 成员，无法表达圈内债务增量，也无法验证生产/测试 scope。
4. **正式模式 fail open**：缺基线、格式错误和扫描不完整没有统一当成“不能证明安全”。
5. **正式计划证明链未接入**：命令计划、long-gate 分类、注册表和门禁元测试没有把循环扫描当正式规则。

## 4. 影响面评估

- 调用图：扇入/扇出、循环记录、孤岛和人工审查优先级会被假边污染；当前确认 12 条假循环。
- import 扫描：可能漏边，但当前已知漏边未改变 6/7 圈集合；修复后数量必须重新解释。
- 正式门禁：新增目录反向边、基线删除或源码语法损坏存在放行风险。
- 结构重构：A1-A6 如果使用错误工具验收，可能误删真实递归或把未清理的依赖写成已完成。
- 业务/数据：工具修复本身不应改变排产业务、数据库、事务、迁移或网页载荷。

严重程度维持 P1：不是已证实运行故障，但属于治理与正式门禁可信度缺口。

## 5. 修复方案

### 方案 A：仅过滤已知 12 条边

- 做法：按类名/方法名黑名单排除。
- 优点：改动最小。
- 缺点：同类新误报继续出现，也可能删掉真实 `self` 调用；没有修扫描和门禁根因。
- 结论：拒绝。

### 方案 B：保留接收者身份 + 统一上下文 + v2 双基线 + 正式门禁（选定）

- 做法：属性调用保留完整接收者；只把直接 `self` 视为 self 边，类型索引补 `self.<attr>` 并在未知重赋值时失效；import alias/嵌套 callable 单独消解；动态 import 与静态 import 共用上下文语义，补父包初始化和入口/插件 scope；基线保存 roots/加载语义、成员、圈内模块边和未解析动态导入并带 scope/version；正式模式 fail closed；两条扫描进入共享计划和 long-gate。
- 优点：按根因修，既消误报又不删真实递归，能阻断同成员新增边，证明链完整。
- 缺点：涉及多个工具和门禁元测试，需要分阶段回归。
- 影响文件：报告第 1 节所列工具、双基线、门禁注册表与测试。

### 方案 C：引入第三方静态分析平台替换现有工具

- 优点：可能提供更强类型推断。
- 缺点：破坏 Win7/Python 3.8/离线约束，引入大依赖，迁移成本高，也不能自动解决项目目录基线语义。
- 结论：拒绝。

**用户确认**：用户在本轮任务中已明确要求按方案 B 连续执行，不需要阶段间重复询问；只有触及数据库格式、公开接口、排产业务行为或重大架构二选一时暂停。

## 6. 实施后核对

- 该 issue 完成时的阶段调用图快照：7314 callable（316 个嵌套 def/lambda）、25299 输出边、11320 确信边、8 条受限真实简单循环；`ensure_schema` 的数据库 bootstrap/migration alias 边已恢复。
- 该阶段生产扫描：749 模块、6 hard 目录 SCC、9 父包感知 hard 文件加载 SCC、0 纯显式 hard 文件 SCC、14/5 个父包感知/纯显式 runtime 文件 SCC、6 个既有未解析动态加载站点。
- 该阶段含测试扫描：1442 模块、7 hard 目录 SCC，使用独立基线；测试专属四目录 SCC 仍是结构耦合，不写成文件死循环。
- 该阶段工具与门禁定向验证：181 passed，Ruff 通过，`pyrightconfig.tools.json` 为 0 errors；两条正式 fail-on-new-cycle 命令均通过。
- **2026-07-11 后续终态校正**：第 7、8、9 项已把动态别名重绑定、typed 假确信和证据漂移继续收敛；当前正式快照为 7329 callable、25772 输出边、10152 确信边、15620 模糊边、typed 0，生产/含测试为 750/1443 模块和 6/7 个 hard 目录 SCC。上面数字保留为本 issue 当时证据，不再代表当前事实。
- 三路起点只读审查提出的正式门禁、fail-open、接收者误连、alias/嵌套 callable、父包初始化、scope 与基线弱签名问题均已纳入修复。修后复审另行记录；当前工作区未提交，不能声称 clean proof。
