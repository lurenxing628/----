---
doc_type: roadmap
slug: dependency-cycle-governance
status: active
created: 2026-07-10
last_reviewed: 2026-07-11
tags: [architecture, import-cycle, callgraph, quality-gate, refactor]
related_requirements: []
related_architecture: [service-scheduler, ARCHITECTURE]
---

# 循环依赖与依赖边界治理路线

## 1. 背景

起点扫描显示 6 组生产目录硬依赖圈、测试目录另有 1 组，纯显式 import 文件图没有 hard SCC；但旧工具没有建 Python 父包 `__init__` 初始化链，也漏掉顶层入口和插件，所以“文件环为 0”不能当加载安全证明。2026-07-10 工具阶段首次补齐该语义并接入双基线与正式门禁；当时记录为生产 749 模块、含测试 1442 模块、6/7 个 hard 目录 SCC、9 个父包感知 hard 文件加载 SCC、0 个纯显式 hard 文件 SCC。

2026-07-11 复审确认首次工具闭环仍是暂定结果：当前重跑已是 750/1443 模块，scheduler A1 四目录圈仍有 49 条圈内模块边；动态导入别名重绑定会制造假 hard 文件环，调用图的简化类型推断会制造假确信循环，非法 UTF-8 又被 `errors="replace"` 静默吞掉；9/10 调用图快照与当前重跑不一致，`artifact_sha256` 当前 17 项中有 8 项漂移。因此 A1 暂停在 `planned`，先按 KISS 原则完成两项工具返修和一次终态证据重建，再继续 A1 至 A6 与测试辅助代码解耦。

## 2. 范围与明确不做

### 本 roadmap 覆盖

- 修正调用图复杂接收者误连，并保留真实受控递归；非直接 `self` 的属性调用不再由半套类型推断提升为确信边。
- 补全 import AST 语句体遍历，显式报告无法静态解析的动态导入，并阻止 importlib 别名被重绑定后制造假边。
- 将生产与“生产+测试”两次循环扫描接入正式质量门禁。
- 基线升级为按圈成员和圈内规范化有向模块边共同校验，并严格阻断缺失、损坏、版本不支持和源码解析失败。
- 在工具代码冻结后重建调用图、双基线、哈希清单与事实文档，形成可重复的终态证明。
- 同步当前架构和审计事实，不把目录 SCC 写成已经发生的文件加载死循环。
- 依次拆除 A1、A2、A3、A4、A5、A6 和测试目录硬依赖圈。

### 明确不做

- 不改变数据库表结构、迁移版本的历史业务含义、事务边界或旧库升级结果。
- 不改变排产算法结果、候选排序、评分、资源匹配、公开页面载荷、路由地址和导出内容。
- 不用函数内导入、条件导入或吞错来伪造“循环清零”。
- 不用 `--update-baseline`、刷新快照或改文档数字让失败测试表面变绿；语义反例未通过前禁止刷新证据。
- 不继续扩张简化类型推断器，不新增跨作用域值流、完整符号执行或第三方静态分析依赖。
- 不保留 `errors="replace"`、广泛吞错或静默降级来伪造“解析错误为 0”。
- 不引入新大型依赖、云服务、外部网页资源或 Python 3.8 不支持的语法。
- 不把现有 `test_architecture_fitness.py` 架构规则删掉或弱化。
- 不在未获授权时提交、推送或创建拉取请求。

## 3. 模块拆分（概设）

```text
依赖治理
├── T1 调用图可信度：保留接收者身份，确信边必须有证据
├── T2 import 扫描可信度：完整语句上下文 + 动态导入盲区清单
├── T3 基线与正式门禁：双基线、圈内边、fail-closed、收据与长门禁
├── D1 当前事实文档：架构只写已落地事实，审计保留历史性质
├── R1 scheduler A1：根/config/run/summary 单向依赖
├── R2 foundation A2：errors、models、migrations、shared 单向依赖
└── R3 remaining：A3-A6 与 tests 分组解耦
```

### T1 · 调用图可信度

- **职责**：调用点保留接收者、方法名和行号；只有直接 `self.method()`、明确本地/导入函数和明确导入模块属性依靠语法证据进入确信图，其它属性接收者统一保留为 ambiguous；嵌套 def/lambda 独立建点；源码解码或解析失败必须明确阻断。
- **承载条目**：`callgraph-receiver-resolution`、`callgraph-confidence-kiss-hardening`。
- **触碰代码**：`.codestable/checkup/scripts/callgraph_extract.py`、`callgraph_call_sites.py`、`callgraph_function_index.py`、`callgraph_type_index.py` 和调用图回归测试；不顺手改数据流与风险报告职责。

### T2 · import 扫描可信度

- **职责**：统一静态 import 与 `import_module`/`__import__`/文件加载器的执行上下文，覆盖函数、类、条件、异常、循环和 with 语句体；解析相对字面量、显式建父包初始化边；只有词法绑定可证明且未重绑定的动态加载器才解析，其他目标进入可回潮未解析清单。
- **承载条目**：`import-cycle-scan-completeness`、`import-cycle-alias-rebinding-hardening`。
- **触碰代码**：`tools/import_cycle_analysis.py`、必要时最小调整 `tools/scan_import_cycles.py` 和扫描测试；不新增通用数据流框架。

### T3 · 基线、正式门禁与终态证明

- **职责**：生产与含测试各有一份明确基线；同一 SCC 成员内新增有向模块边也失败；正式计划、命令哈希、收据、重放、长门禁和测试注册表保持一致；工具冻结后再统一生成快照、双基线和哈希清单，并证明连续两次输出一致。
- **承载条目**：`import-cycle-quality-gate-integration`、`import-cycle-fail-closed`、`import-cycle-edge-baseline-v2`、`dependency-proof-rebuild-and-closure`。
- **触碰代码/证据**：`tools/import_cycle_baseline.py`、`tools/quality_gate_shared.py`、`tools/long_gate_manifest.py`、测试注册表、门禁元测试、调用图快照、双基线和 checkup 哈希清单。

### D1 · 当前事实文档

- **职责**：在工具可信后更新“当前是什么”，不写尚未实施的目标态；首次事实刷新保留为历史，终态证明阶段再按最终工具口径校正数字与状态。
- **承载条目**：`dependency-architecture-facts-refresh`、`dependency-proof-rebuild-and-closure`。
- **触碰代码/文档**：scheduler 架构文档、两份专项审计、checkup README/baseline、工具 issue 及必要索引描述。

### R1 · scheduler A1

- **职责**：把纯合同、字段集合、数字处理和兼容入口放到不反向依赖执行/汇总/配置实现的归属；保持排产、配置、摘要和持久化行为不变。
- **承载条目**：`scheduler-a1-decoupling`。

### R2 · foundation A2

- **职责**：先设计并复审 errors、shared、models、migrations 和事件数据合同的最低依赖层，再实施不改变数据与迁移语义的移动。
- **承载条目**：`foundation-a2-decoupling`。

### R3 · remaining

- **职责**：A3 算法、A4 路由、A5 插件、A6 报表和测试辅助代码各自独立核查、实现、验证，不合成无法审查的大搬迁。
- **承载条目**：`remaining-cycles-decoupling`。

## 4. 模块间接口契约 / 共享协议（架构层详设）

### 4.1 调用点接收者合同

**方向**：AST 提取 → 保守消解 → 调用边输出。

**内部合同**：属性调用至少保留以下信息，等价实现可以使用 tuple 或 dataclass，但不能只留下最后一个方法名。

```text
receiver_text: "self" | "self.repo" | "repo" | "factory()" | 其他规范化表达
method_name:   str
line:          int
```

约束：

- `(receiver_text, method_name, line)` 是最小调用点身份；同一接收者和方法出现在不同行时不得在提取阶段折叠掉行号。
- 只有接收者精确为 `self`，才能按当前类方法生成 `kind=self, ambiguous=false`。
- 明确本地函数、明确导入函数和明确导入模块属性可以依靠直接语法来源生成确信边。
- `self.<attr>.<method>`、`repo.<method>`、`factory().<method>` 等其它属性接收者统一生成 `kind=attr, ambiguous=true`；不再由参数注解、局部赋值、构造调用或返回注解提升为 `kind=typed, ambiguous=false`。
- 不得为恢复 typed 边继续扩张 `for/with/except/解包/推导式/闭包` 等半套类型或值流推断；宁可少消解，不画错边。
- 不得用“过滤所有同名方法”消除误报；真实 `self.method()` 和已知受控递归仍须存在。
- 源文件严格按 UTF-8 读取；`OSError`、`UnicodeError`、`SyntaxError` 均进入明确错误并在可信扫描模式阻断，禁止 `errors="replace"`。
- `cycle_count` 的公开说明固定为“长度 2-8、最多 200 条的确信边简单循环记录数”，不得称 SCC 数。

### 4.2 import 执行上下文合同

**方向**：AST 分类 → 模块/目录边 → SCC 报告。

```text
context ∈ {hard, cond, lazy, typeonly}
resolved dynamic import = {target: str, context: context, line: int}
unresolved dynamic import = {file: str, line: int, context: context, expression: str}
```

约束：

- 模块或类加载期的 `for/async for/while/with/async with` 继承外层上下文。
- 函数/异步函数内部任何嵌套结构都保持 `lazy`；条件/try 不能把它错误改成 `cond`。
- 非 `TYPE_CHECKING` 顶层条件/try 为 `cond`；`TYPE_CHECKING` 正分支为 `typeonly`，else 继承外层运行时上下文。
- 只解析固定字符串目标；变量、拼接、调用结果等进入未解析清单，不猜模块名。
- 动态加载器名称只有在词法作用域链能证明来自 `importlib`/`importlib.util`/未遮蔽的 `__import__`，且参数、赋值、循环目标、with/except 目标、函数/类定义或删除没有重绑定该名称时才可解析。
- 无法证明别名来源或存在任意重绑定时，调用必须进入未解析清单，不得继续画动态 import 边；不做跨语句值流和完整符号执行。
- 扫描 JSON 保留现有环类别，并新增明确的未解析动态导入字段。

### 4.3 循环基线 v2 合同

**方向**：扫描结果 → 基线比较 → 正式门禁。

```json
{
  "schema_version": 2,
  "scope": "production | production-and-tests",
  "scan_roots": ["core", "web", "data", "desktop", "plugins", "tools", "scripts", "*.py"],
  "file_cycle_semantics": "explicit import edges plus implicit parent-package __init__ loading edges",
  "hard_dir_cycles": [
    {"members": ["..."], "edges": ["source.module -> target.module"]}
  ],
  "hard_file_cycles": [
    {"members": ["..."], "edges": ["source.module -> target.module"]}
  ],
  "unresolved_dynamic_imports": ["file|line|context|expression"]
}
```

约束：

- 圈身份由排序后的成员确定；圈内边由排序去重后的“来源模块 → 目标模块”确定，不含行号。
- 同成员新增边失败；删边、整圈消失、SCC 缩小为旧成员/旧边子集允许；全新圈或缩小后新增边失败。
- 生产基线 scope 和含测试基线 scope 不可互换；`scan_roots` 或文件加载语义变化也必须 fail closed。
- 新增未解析动态导入 callsite 失败；签名含 file/line/context/expression，不把同文件同表达式多站点折叠。
- v1、缺失、损坏 JSON、不支持版本、字段类型错误在正式模式下都非零退出，并带文件和处理办法。
- `--update-baseline` 不是正式门禁命令；刷新前必须先人工看差异。

### 4.4 正式质量门禁命令合同

正式计划必须同时包含并按固定顺序执行：

```text
python -m tools.scan_import_cycles --fail-on-new-cycle --quiet-when-clean
python -m tools.scan_import_cycles --include-tests --fail-on-new-cycle --quiet-when-clean
```

约束：

- 两条命令各自选取 scope 匹配的默认基线。
- 删除任一命令，门禁元测试必须失败。
- 两条命令进入命令计划哈希、逐步收据、失败续跑判断、重放和 long-gate manifest；long-gate 必须识别成两个稳定 entry，而不是 `unknown`。
- 现有架构适应度检查继续保留。

### 4.5 终态证据重建合同

**方向**：冻结工具代码 → 临时双跑 → 人工核差异 → 写入正式证据 → 哈希自检 → clean HEAD 门禁。

约束：

- 动态别名假环、调用图假确信环和非法 UTF-8 三个反例未通过前，禁止刷新调用图快照、双基线和文档数字。
- 调用图先输出到两个独立临时目录；文件集合和逐文件 SHA256 必须完全相同，才能覆盖 `.codestable/checkup/latest/callgraph/`。
- 双 scope import 扫描的 SCC、圈内边和 unresolved 差异必须人工逐项解释；只有语义修正导致的可信变化才允许受控刷新基线。
- `.codestable/checkup/baseline.json` 必须在所有工具和证据文件最终冻结后计算；`artifact_sha256` 当前清单逐项匹配，记录的模块/函数/边计数与重跑结果一致。
- 证据刷新后若任一工具、基线或快照再次变化，本次闭环立即失效，必须从临时双跑重新开始。
- 只有提交后的干净最终 HEAD 运行完整质量门禁成功，才能声称 clean-worktree proof；脏工作区只记录局部验证。

### 4.6 结构重构兼容合同

- 所有旧的业务公开函数/类签名、路由地址、JSON/Excel 字段、错误码和数据库迁移版本保持不变。
- 允许在单向叶子层新增内部模块；兼容转出若会重新形成依赖圈则不得永久保留。
- 老迁移可以改 import 指向同语义纯合同，但不得改迁移 SQL、默认值、写入顺序或异常表现。
- 每组完成后必须用生产与含测试扫描、正逆序新进程导入和该域合同测试证明。

## 5. 子 feature 清单

1. **callgraph-receiver-resolution** — 修正复杂接收者误连，保留真实递归并校正循环计数口径。
   - 所属模块：T1
   - 依赖：无
   - 状态：completed
   - 对应 feature：未启动（由 issue `2026-07-10-dependency-governance-tooling-trust` 承接）

2. **import-cycle-scan-completeness** — 补全语句体和动态导入上下文扫描。
   - 所属模块：T2
   - 依赖：`callgraph-receiver-resolution`
   - 状态：completed
   - 对应 feature：已由同一工具 issue 完成

3. **import-cycle-quality-gate-integration** — 将生产和含测试扫描接入正式命令计划及证明链。
   - 所属模块：T3
   - 依赖：`import-cycle-scan-completeness`
   - 状态：completed
   - 对应 feature：已由工具 issue 完成

4. **import-cycle-fail-closed** — 正式模式严格阻断基线与解析错误和扫描异常。
   - 所属模块：T3
   - 依赖：`import-cycle-quality-gate-integration`
   - 状态：completed
   - 对应 feature：已由工具 issue 完成

5. **import-cycle-edge-baseline-v2** — 双基线升级到成员+圈内边并完成差异核对。
   - 所属模块：T3
   - 依赖：`import-cycle-fail-closed`
   - 状态：completed
   - 对应 feature：已由工具 issue 完成

6. **dependency-architecture-facts-refresh** — 按可信扫描结果更新架构与审计事实口径。
   - 所属模块：D1
   - 依赖：`import-cycle-edge-baseline-v2`
   - 状态：completed
   - 对应 feature：未启动

7. **import-cycle-alias-rebinding-hardening** — 消除 importlib 别名遮蔽/重绑定产生的假 hard import 边，不确定目标统一显式进入 unresolved 清单。
   - 所属模块：T2
   - 依赖：`import-cycle-scan-completeness`
   - 状态：completed
   - 对应 feature：已由 issue `2026-07-11-import-cycle-alias-rebinding-hardening` 完成

8. **callgraph-confidence-kiss-hardening** — 取消非直接 `self` 属性调用的 typed 确信提升，补调用点行号并让解码/解析失败明确阻断。
   - 所属模块：T1
   - 依赖：`callgraph-receiver-resolution`
   - 状态：completed
   - 对应 feature：已由 issue `2026-07-11-callgraph-confidence-kiss-hardening` 完成

9. **dependency-proof-rebuild-and-closure** — 冻结工具后双跑重建调用图、双基线、哈希和事实文档，形成可复现终态证明。
   - 所属模块：T1/T2/T3/D1
   - 依赖：`import-cycle-edge-baseline-v2`、`dependency-architecture-facts-refresh`、`import-cycle-alias-rebinding-hardening`、`callgraph-confidence-kiss-hardening`
   - 状态：completed
   - 对应 issue：`2026-07-11-dependency-proof-rebuild-and-closure`

10. **scheduler-a1-decoupling** — 消除 scheduler 根/config/run/summary 四方硬目录圈。
   - 所属模块：R1
   - 依赖：`dependency-proof-rebuild-and-closure`
   - 状态：planned
   - 对应 feature：未启动（走独立 refactor；现有 checklist 在前置完成前不执行）

11. **foundation-a2-decoupling** — 设计、双轨复审并实施 infrastructure/migrations/models/shared 解耦。
   - 所属模块：R2
   - 依赖：`scheduler-a1-decoupling`
   - 状态：planned
   - 对应 feature：未启动（走独立 refactor）

12. **remaining-cycles-decoupling** — 按 A3、A4、A5、A6、tests 五个批次清零剩余硬目录圈。
   - 所属模块：R3
   - 依赖：`foundation-a2-decoupling`
   - 状态：planned
   - 对应 feature：未启动（每批走独立 refactor）

**最小闭环**：第 1-6 条保留为首次工具接线历史，但 2026-07-11 复审证明其不足以支撑可信收口。第 7、8 条语义反例通过后，第 9 条已完成临时双跑、正式证据重建、哈希自检和 clean HEAD 19 步门禁，当前最小闭环已经成立。A1 前置因此解除，但 A1 仍是独立 planned refactor，本轮不继续实施。

## 6. 排期思路

按“先语义、后证据、再业务结构”推进：先完成 `import-cycle-alias-rebinding-hardening`，再完成 `callgraph-confidence-kiss-hardening`，避免两套扫描器同时大改导致证据难归因；随后用 `dependency-proof-rebuild-and-closure` 一次性重建快照、双基线、哈希和事实文档。A1 只依赖该终态证明，不再直接接在首次事实刷新后。A2 继续在 A1 后设计和双轨复审，因为它触及迁移、错误类型和运行时模型；剩余各组不并成一次大搬迁。

## 7. 观察项

- 当前 `rg` 在本机 PATH 中不可用，本轮搜索使用 `git grep`/`grep`；这不改变代码或交付环境。
- 本轮按用户要求不调用 subagent；规划与后续执行均由主代理单线推进。
- `.codestable/checkup/scripts/` 不在当前 symbol-locator 的常规源码索引根中；调用图工具自身的影响面以 AST 合同测试、直接 grep 和临时目录全量提取补足，不把索引未命中当“无人调用”。
- 依赖治理批次已在用户明确授权后提交；完整 19 步质量门禁在 clean HEAD 上无缓存、无续跑通过，可声称本批机械证据的 clean-worktree proof。历史决定考古水位线仍未推进。
- 现有 A1 refactor design/checklist 保留，五步继续保持 pending；启动 A1 时先以当前正式生产基线重新核对 49 条起点边，不把前置解除等同自动开工。

## 8. 变更日志

- 2026-07-11：完成 `dependency-proof-rebuild-and-closure`；调用图双临时目录 10 JSON 逐文件 SHA 一致，双 scope 候选基线与正式文件逐字节一致，25 项 artifact 哈希全匹配；用户授权提交后，clean HEAD 完整 19 步门禁无缓存、无续跑通过，收集 4712 项且 full-test-debt unexpected failure 为 0。A1 仍保持 planned。
- 2026-07-11：完成 `callgraph-confidence-kiss-hardening` 独立 issue；删除 typed 属性接收者推断，调用点保留行号，源码严格 UTF-8 fail-closed；临时双跑稳定但未提前刷新快照和哈希。
- 2026-07-11：完成 `import-cycle-alias-rebinding-hardening` 独立 issue；动态加载器只在词法来源可证明且未重绑定时生成边，不确定调用进入 unresolved，双 scope 正式命令在未刷新基线时通过。
- 2026-07-11：根据工作区复审新增动态导入别名重绑定、调用图 KISS 收敛和终态证据重建三项；接口契约改为非直接 `self` 属性调用保持 ambiguous、严格 UTF-8 fail-closed，并把 A1 前置改为终态证明闭环。既有 completed 条目保留历史状态，不回退终态。
