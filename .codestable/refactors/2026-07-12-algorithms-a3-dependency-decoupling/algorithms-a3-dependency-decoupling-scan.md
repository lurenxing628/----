---
doc_type: refactor-scan
refactor: 2026-07-12-algorithms-a3-dependency-decoupling
status: user-reviewed
scope: core/algorithms、core/algorithms/greedy、core/algorithms/greedy/dispatch 的 A3 hard 目录 SCC、直接生产消费方与 15 个算法/图模式合同测试
summary: 三条结构项；中风险 1、高风险 2；只有三项组合才能在保留 core.algorithms.GreedyScheduler 的前提下清除 A3
---

# algorithms A3 dependency decoupling scan

## 1. 总览

- 扫描范围：A3 的三个目录、42 条圈内 hard 边、父包初始化感知的 21 成员 / 94 边文件 SCC，以及 `GreedyScheduler` 根入口、日期解析、排序/类型合同、dispatch 执行模块和直接测试。
- 发现 3 条结构项：日期解析合同归位 1 条、dispatch 运行时边界拆分 1 条、公共算法合同中立化 1 条；没有性能、可读性、页面目视或数据库改动项。
- 按风险：中 1 / 高 2。
- 建议先做：**A3-01**。它是唯一已独立证明完整算法测试和调用图均不漂移的原子项，但单独做完 A3 仍存在。
- 建议慎做 / 后做：**A3-02 + A3-03** 必须作为兼容闭环一起设计、分步实施；当前组合原型证明方向可行，但约 50 个生产文件，尚未完成最终调用图全边映射，不能把粗原型直接照搬进生产代码。
- 选择语义：只选 A3-01 是合法的局部重构；要在不破坏 `core.algorithms.GreedyScheduler` 的前提下清除 A3，需要 A3-01、A3-02、A3-03 全选。若希望退役根入口，应改走 architecture/decision/feature，不属于本 refactor。
- 验证责任：三项均为 AI 自证；没有页面变化，不需要 HUMAN 目视。实现阶段仍须逐步人工放行。

### 前置检查说明

普通 `cs-refactor` 的前置检查不是“七条全过”：

- 第 3 条“跨模块”命中：A3 本身就是 `algorithms ⇄ greedy ⇄ dispatch` 的目录边界问题。
- 第 6 条“超过 15 文件 / 3000 行”命中：完整兼容闭环的 v2 粗原型已达 47 个 Python 文件、17 个新文件、`+1541 / -1368`，补齐生产直连和边界测试后会超过 50 文件。
- 本 scan 继续的唯一依据是 `dependency-cycle-governance` roadmap 已在 R3 和 §4.6 做过架构层预路由，明确要求 A3 独立核查，并冻结旧公开函数/类签名、允许单向叶子层、要求双 scope 与正逆序导入证明。本阶段只负责把 A3 拆成可选择切点，不授权实现。
- 第 1 条在“保留根入口”的兼容路线下不命中；若选择退役根入口则立即命中行为改动，退出 refactor。
- 第 2 条不命中：当前起点 15 文件专项 **120 passed**，完整 `tests/algorithm` **550 passed**。
- 第 4、5 条不命中：不是风格口味，也不是生成物或第三方代码。
- 第 7 条不命中：按根因恰好得到三条结构项，不额外凑项。

## 2. 当前事实与精确切边

当前起点是 clean HEAD `582a588c8adda314584052b870ace00628a722c7`。SCIP 索引已在该 HEAD 重建；两条临时扫描与正式 v2 基线逐 SCC 成员、逐圈内边核对一致，不是只比较数量。

| scope | 模块 | hard 目录 SCC | 父包感知 hard 文件 SCC | 纯显式 hard 文件 SCC | unresolved | parse error |
|---|---:|---:|---:|---:|---:|---:|
| production | 763 | 4 | 9 | 0 | 6 | 0 |
| production-and-tests | 1458 | 5 | 9 | 0 | 44 | 0 |

A3 在两个 scope 中身份完全相同：

```text
core/algorithms
core/algorithms/greedy
core/algorithms/greedy/dispatch
```

42 条圈内边按方向分解如下：

| 方向 | 条数 | 主要根因 |
|---|---:|---|
| algorithms → greedy | 5 | 根包 eager export `GreedyScheduler` 1 条；四个父层模块反借 `greedy.date_parsers` 4 条 |
| greedy → algorithms | 17 | greedy 反借 types、sort、ordering、dispatch_rules、value_domains 等父层合同 |
| greedy → dispatch | 2 | `run_state` 依赖 `dispatch.runtime_state`；`scheduler` 依赖 dispatch 公开入口 |
| dispatch → greedy | 10 | dispatch 反借 run context/state、auto assign、internal slot、date parser |
| dispatch → algorithms | 8 | dispatch 反借 ordering、types、value domains 等父层合同 |

父包初始化感知的 A3 文件 SCC 是 21 成员 / 94 边；两个 scope 相同。纯显式 hard 文件 SCC 为 0，说明当前文件环主要由 Python 父包初始化语义放大，但不是假环，也不能靠忽略父包边来消失。

### 2.1 五条 algorithms → greedy 边

1. `core.algorithms -> core.algorithms.greedy`：`core/algorithms/__init__.py:13` eager export `GreedyScheduler`。
2. `dispatch_rules -> greedy.date_parsers`。
3. `evaluation -> greedy.date_parsers`。
4. `ordering -> greedy.date_parsers`。
5. `ortools_bottleneck -> greedy.date_parsers`。

因此只移动日期解析最多处理其中 4 条；根入口仍保留第 5 条。

### 2.2 greedy ↔ dispatch 返回路径

- greedy → dispatch 两条：`run_state -> dispatch.runtime_state`、`scheduler -> dispatch.__init__`。
- dispatch → greedy 十条集中在 `run_context`、`run_state`、`auto_assign`、`internal_slot`、`date_parsers`。
- 正确方向应保留为 `greedy façade → dispatch implementation`；要删除的是 dispatch 对 greedy 运行时细节的反借，而不是把 dispatch 实现复制到 greedy。

## 3. 公开兼容合同

### 3.1 `core.algorithms.GreedyScheduler` 不是可随手删除的内部别名

AST 统计到 35 条 `from core.algorithms import GreedyScheduler`，分布于 30 个文件：

- 生产 2 条：`optimizer_proof_oracle.py`、`schedule_optimizer.py`；
- tests/support/scripts 32 条；
- CodeStable 实验脚本 1 条。

当前 Python 3.8 合同包括：

- `core.algorithms.GreedyScheduler is core.algorithms.greedy.GreedyScheduler`；
- 同时与 `core.algorithms.greedy.scheduler.GreedyScheduler` 为同一对象；
- `__module__ == "core.algorithms.greedy.scheduler"`；
- 根包 `__all__` 含 `GreedyScheduler`；
- 构造签名、`schedule` 签名、继承覆写和正逆序独立进程导入均成立。

仓内未发现 pickle/cloudpickle/dill、`__module__` 断言、字符串模块路径反射或按旧文件路径加载，但仓外消费者未知。按 roadmap §4.6，根入口默认作为公开兼容 API 冻结。

### 3.2 dispatch 兼容不能只看函数 identity

AST 统计到 31 条直接 dispatch import，分布于 14 个文件；唯一生产消费方 `core/services/scheduler/graph/ready_queue.py` 没有形成 A3 反向边，原型也不需要移动，继续排除。

至少有 17 个与 A3 移动相关、必须保持真实模块状态的 patch 合同：

- 既有 16 个精确目标覆盖 `dispatch.sgs`、`dispatch.sgs_scoring`、`estimate_internal_slot`、`build_dispatch_key`、`validate_internal_hours_for_mode`、`_score_internal_candidate` 和 scheduler 内的 `dispatch_batch_order`；
- 完整算法原型额外暴露 `core.algorithms.greedy.algo_stats.deepcopy` 的模块全局 monkeypatch 合同。

因此“旧模块 re-export 同名函数”不等于兼容。patch 必须改到真实执行模块使用的同一份全局状态；否则测试可能仍能 import，却绕过补丁执行错误路径。

## 4. 临时原型结论

所有试改均位于 `/tmp/a3-prototypes-20260712/`，没有把候选写进主工作树。

### 4.1 日期解析原子原型：成立，但不足以单独消圈

`date-only` 把 canonical 日期解析实现上移，旧 `greedy.date_parsers` 显式同对象 re-export，并让生产调用方直连 canonical：

- production / with-tests 的 A3 都从 3 成员 / 42 边降到 3 成员 / 40 边；
- 父包感知文件 SCC 从 21 / 94 缩到 21 / 92；
- 日期旧新路径 identity 成立；完整 `tests/algorithm` **550 passed**；
- 调用图与起点完全相同：7329 callable、25786 edges、10166 confident、15620 ambiguous、8 cycles、193 islands；
- 原型规模 10 个 Python 文件、1 个新文件、`+60 / -54`。

结论：A3-01 是干净的原子项，但不能宣称它清除了 A3。

### 4.2 单独处理根入口：两种小方案都不成立

- 直接删除根 eager export：A3 仅 42 → 41，仍是同一个三成员 SCC；35 条仓内 import 和潜在仓外 API 立即破坏。
- 增加静态 re-export shim：公开 identity 可保留，但 `algorithms → greedy` 依赖仍存在；A3 仍是 3 / 42，父包文件 SCC 反而扩大到 22 / 97。
- 动态 `__getattr__`、函数内 import 或 `TYPE_CHECKING` 遮边不作为方案；它们不满足本任务的静态依赖治理和可追溯要求。

### 4.3 扁平化 dispatch：函数相同、模块状态分叉，否决

`dispatch-flatten-only` 让 dispatch 目录退出目录 SCC，但剩余 `algorithms ⇄ greedy` 仍为 2 成员 / 30 边。更关键的是 4 个代表性 monkeypatch 合同失败：旧 `dispatch.sgs` / `sgs_scoring` 上的 patch 不再影响新 canonical 实现。

结论：不把 dispatch 实现复制/扁平化到 greedy，不用“同名函数能 import”伪装兼容。

### 4.4 保留根入口的完整兼容原型：结构可行，但仍不是最终设计

`root-compatible-contract-leaf-v2` 使用原型名 `core/algorithm_contracts` 承载低依赖合同和最小 dispatch runtime；旧 `core.algorithms.*` 路径显式 re-export，根 `GreedyScheduler` 保持原实现和 eager export。v1 完整算法测试先暴露 `greedy.algo_stats.deepcopy` patch 失效；v2 改为只下沉 dispatch 真正需要的计数合同，`snapshot_algo_stats` / `merge_algo_stats` 和 `deepcopy` 继续由旧 canonical 模块承载。

v2 结果：

| scope | 模块 | hard 目录 SCC | A3 | 父包感知 A3 文件 SCC |
|---|---:|---:|---|---|
| production | 780 | 3 | 消失 | 9 成员 / 28 边 |
| production-and-tests | 1475 | 4 | 消失 | 9 成员 / 28 边 |

并且：

- A4、A5、A6、tests 的成员和圈内边逐项不变；无新增目录 SCC；unresolved 仍为 6 / 44，parse error 0，纯显式 hard 文件 SCC 0；
- 原 A3 文件 SCC 从 21 / 94 严格缩成其成员子集 9 / 28；
- Python 3.8 旧→新、新→旧两个独立进程均保持根 `GreedyScheduler` identity、`__all__`、`__module__`、构造和 `schedule` 签名；日期、排序、类型和 dispatch 旧新对象 identity 成立；
- 15 文件 A3 专项 **120 passed**；完整 `tests/algorithm` **550 passed**；
- 粗原型已达 47 个 Python 文件、17 个新文件、`+1541 / -1368`。至少还有 7 个生产文件需要在设计中决定是否直连 canonical 并补齐路径映射，因此最终范围会超过 50 文件。

调用图仍是当前阻塞证据：

- 起点：7329 callable / 25786 edges / 10166 confident / 15620 ambiguous；
- v2：7337 callable / 25787 edges / 10160 confident / 15627 ambiguous；
- 路径映射后，起点 7329 个 callable 全部有对应项，另有 8 个 `_LegacyDispatchContext` adapter callable；
- 全边集仍有 17 条旧边未一一对应、18 条新边，按端点计为 13 条旧 / 14 条新。部分只是 local→import 分类变化，部分是合理 adapter 替换，但仍有日期、priority、ordering 和 auto-assign 调用被兼容路径遮挡。

结论：已证明“保留根入口 + 静态显式依赖 + 清除 A3”并非不可能；尚未证明当前粗原型满足最终调用图零丢失/逐边解释，不能直接进入 apply。

## 5. 条目

### A3-01 把日期解析合同移出 greedy ✓

- **位置**：`core/algorithms/greedy/date_parsers.py:1-49`；`dispatch_rules.py:8`、`evaluation.py:9`、`ordering.py:9`、`ortools_bottleneck.py` 及其它直接生产调用方。
- **分类**：结构。
- **现状**：`parse_date`、`parse_datetime`、`due_exclusive` 是不依赖 greedy 调度状态的纯解析合同，却由四个 algorithms 父层模块反借，贡献 5 条 `algorithms → greedy` 中的 4 条。
- **问题**：纯日期合同放在执行子包，使父层模块必须初始化 greedy；独立原型证明移动后 A3 仍存在，但圈内边 42 → 40、父包文件边 94 → 92。
- **建议**：把 canonical 日期实现放到不依赖 greedy 的单向合同模块；旧 `core.algorithms.greedy.date_parsers` 保留同对象显式 re-export，所有生产调用方直连 canonical。若同时选择 A3-03，design 直接落到最终中立合同层，避免先上移再二次搬迁。
- **建议映射的方法**：M-L1-01 Parallel Change + M-L2-04 Move Function + M-L3-06 Layer Rectification。
- **风险**：中；实现仅 49 行且原型全绿，但日期边界、空值/非法值、exclusive due 语义和旧新对象 identity 都是业务合同。
- **验证**：AI 自证（新增旧/新路径 identity、签名和正逆序导入合同；日期/交期/排序专项；15 文件 A3 专项；完整 `tests/algorithm`；双 scope 扫描；调用图路径映射）。
- **范围**：独立原型约 10-12 个生产 Python 文件、1 个边界测试，约 60 行搬移/兼容代码；单独实施不清除 A3。

### A3-02 抽出 dispatch 最小运行时合同 ✓

- **位置**：`core/algorithms/greedy/{run_context,run_state,auto_assign,internal_slot,downtime,algo_stats}.py`，`greedy/dispatch/{batch_order,runtime_state,sgs,sgs_scoring,resource_validation}.py`。
- **分类**：结构。
- **现状**：greedy 通过 scheduler/run-state 正向调用 dispatch；dispatch 又反借 greedy 的上下文、状态、自动分配和内部时隙实现，形成 2 条正向边 + 10 条返回边。多个旧模块全局还是测试 patch 的真实控制点。
- **问题**：直接扁平化虽能让 dispatch 退出目录 SCC，却让至少 4 个代表性 patch 失效；粗共享叶子若仍放在 `core/algorithms/` 内，又会被根 eager export 拉进更大的四目录 SCC。
- **建议**：保留现有 dispatch 模块为 canonical 执行模块，建立 algorithms 目录之外的最小 runtime 合同，只下沉 dispatch 真正需要的 state/context/helper；greedy façade 正向调用 dispatch。不要整模块机械搬移 patchable 状态：例如只下沉计数合同，`greedy.algo_stats` 的 snapshot/merge/deepcopy 继续由旧 canonical 模块承载。
- **建议映射的方法**：M-L1-01 Parallel Change + M-L3-06 Layer Rectification + M-L3-07 Single Responsibility Split。
- **风险**：高；涉及真实执行状态、资源占用、异常计数和模块级 monkeypatch。函数 identity 相同仍可能因模块 globals 分叉而行为不同。
- **验证**：AI 自证（逐个冻结至少 17 个 patch 目标；旧模块对象与真实执行目标一致；dispatch 主循环、内部时隙、自动分配、run-state、graph-on 合同；15 文件专项与完整算法测试；Python 3.8 正逆序导入；双 scope；adapter 和旧边逐项调用图映射）。
- **范围**：预计 20-30 个生产文件、约 900-1100 行实现搬移/最小拆分 + 1 个共用边界测试；必须与 A3-03 的中立层边界一起设计，不能按粗原型直接实施。

### A3-03 把反借的公共算法合同移到中立层 ✓

- **位置**：`core/algorithms/{types,sort_strategies,ordering,dispatch_rules,priority_constants,value_domains}.py`，以及 greedy/dispatch 和 scheduler run 的直接生产调用方；根包 `core/algorithms/__init__.py:13` 保持不动。
- **分类**：结构。
- **现状**：根包为兼容而保留 `algorithms → greedy` eager export；greedy/dispatch 又以 25 条边反借 algorithms 内的类型、排序、派工规则和值域合同。只要这些返回路径仍在，根入口与消圈无法同时成立。
- **问题**：静态 shim 不会删除 `algorithms → greedy`；删除根入口又是公开行为改动。兼容路线必须让 greedy/dispatch 依赖 algorithms 目录之外的低依赖合同，才能形成单向结构。
- **建议**：把上述低依赖公共合同的 canonical 实现移到 algorithms 目录之外的中立叶子（原型名 `core/algorithm_contracts`，最终命名在 design 确认）；旧 `core.algorithms.*` 路径显式同对象 re-export；生产调用方按调用图可见性直连 canonical。根 `GreedyScheduler`、`__all__`、类定义位置和 eager export 保持不变。
- **建议映射的方法**：M-L1-01 Parallel Change + M-L2-04 Move Function + M-L3-06 Layer Rectification。
- **风险**：高；六组合同被算法、scheduler、tests/support 广泛消费，且完整闭环总范围超过普通单次 scan 上限。旧路径、对象 identity、dataclass/Enum 值、签名、排序键、错误文本和外部消费者兼容都必须冻结。
- **验证**：AI 自证（根 `GreedyScheduler` identity/`__module__`/`__all__`/签名/继承；全部旧新类型、Enum、函数 identity；正逆序新进程导入；15 文件专项、完整算法测试；双 scope 只删除 A3；调用图 7329 个旧 callable 全映射且每条旧边保留或有经批准的 adapter 替代）。
- **范围**：本项本身预计 15-25 个生产文件、约 500-800 行合同搬移/兼容；与 A3-01/A3-02 合并闭环的 v2 粗原型为 47 个 Python 文件，最终预计 50+ 文件和 1 个共用边界测试，design 必须拆成多步放行。

## 6. 明确不做 / 非候选路线

- 不暗中删除 `core.algorithms.GreedyScheduler`。若用户选择退役，需先定义 deprecation/迁移/版本策略，转 `cs-arch` + `cs-decide`，必要时走 feature；不能在 refactor 中伪装成行为等价。
- 不用静态小 shim 冒充消圈；原型已证明 A3 仍为 3 / 42。
- 不用动态 `__getattr__`、函数内 import、`TYPE_CHECKING` 或吞错来隐藏 hard 边。
- 不扁平化/复制 dispatch 实现到 greedy；原型已证明旧模块 globals 和 monkeypatch 会分叉。
- 不移动 `core/services/scheduler/graph/ready_queue.py`；它是 dispatch 的单向生产消费方，不构成 A3 返回边。
- 不改排产算法、排序结果、资源选择、图模式、日期语义、统计计数、异常文本、数据库、配置或页面行为。
- 不在 scan 阶段更新正式双基线、正式调用图、dead-code 基线、roadmap/items 或架构现状；候选证据只放 `/tmp`。
- 不创建 design、checklist、apply-notes，不修改生产代码，不 commit、push 或创建 PR。

## 7. 用户选择（已确认）

- 2026-07-12：用户选择 **A3-01 + A3-02 + A3-03 全部进入 design**，采用保留根 `GreedyScheduler` API 的高成本兼容路线。
- 选择约束：design 必须把三项拆成可独立验证、逐步放行的执行步骤，补齐调用图全边映射，并再次交用户整体审批。
- 本次选择只放行下一阶段 design 起草；不授权 apply、生产代码修改、正式基线/调用图刷新、roadmap 状态修改或 Git 提交。

## 8. 起点与原型验证记录

- 起点 HEAD：`582a588c8adda314584052b870ace00628a722c7`；测试前后工作树均干净。
- SCIP：当前 HEAD 已重建；`parse_date` / `parse_datetime` / `due_exclusive`、`dispatch_batch_order`、`dispatch_sgs` 均精确定位，类 `GreedyScheduler` 的函数定位器未命中由 AST/git grep 补齐，未把“类未命中”误判为无人使用。
- 当前扫描：`/tmp/a3-current-production.json`、`/tmp/a3-current-with-tests.json`、`/tmp/a3-current-identities.json`；A3/A4/A5/A6/tests 与正式 v2 基线逐项一致。
- 原型：`/tmp/a3-prototypes-20260712/`；兼容 v2 双 scope 为 `root-compatible-contract-leaf-v2-*.json`，临时调用图为 `callgraph-root-compatible-contract-leaf-v2/`。
- 当前 HEAD 15 文件专项：**120 passed in 0.76s**。
- 当前 HEAD 完整算法测试：**550 passed in 7.92s**。
- 日期原子原型完整算法测试：**550 passed in 7.51s**。
- 兼容 v2 原型 15 文件专项：**120 passed in 1.89s**；完整算法测试：**550 passed in 25.84s**。
- 过程偏离：调用图脚本不支持 `--help`，一次误按当前 HEAD 重生成正式调用图目录；未把任何原型写入正式目录。随后将 10 个 JSON 逐文件与 HEAD blob 做字节比较，全部相同，`git diff` 和 `git status` 均为空。之后所有候选调用图只输出到 `/tmp`。
- 本 scan 是本阶段唯一新增文件；正式双基线、正式调用图内容、dead-code 基线、roadmap/items、架构文档和生产代码均无内容差异。
