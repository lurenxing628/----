---
doc_type: refactor-design
refactor: 2026-07-12-algorithms-a3-dependency-decoupling
status: approved
scope: algorithms A3 的日期/公共合同、greedy/dispatch 共享运行时、根 GreedyScheduler 兼容入口及双基线/调用图证据
summary: 用 sibling algorithm_contracts 与 algorithm_runtime 叶子移除全部返回边，保留 algorithms → greedy → dispatch 主链、旧路径 identity 和真实 patch 模块状态
---

# algorithms A3 dependency decoupling refactor design

## 1. 本次范围

执行用户已勾选的 **A3-01 + A3-02 + A3-03**，目标是在不改变算法行为和根公开入口的前提下，消除：

```text
core/algorithms ⇄ core/algorithms/greedy ⇄ core/algorithms/greedy/dispatch
```

目标依赖方向：

```text
core.algorithms ──> core.algorithms.greedy ──> core.algorithms.greedy.dispatch
      │                        │                            │
      └────────────────────────┴────────────────────────────┼──> core.algorithm_contracts
                                                           └──> core.algorithm_runtime
                                                                    │
                                                                    └──> core.algorithm_contracts
```

约束解释：

- `core.algorithms` 根包继续 eager export `GreedyScheduler`；`core/algorithms/__init__.py` 不改。
- greedy 继续是排产器 façade，dispatch 继续是 batch-order/SGS 的 canonical 执行模块。
- `core.algorithm_contracts` 只承载纯合同、值对象、排序和日期规则。
- `core.algorithm_runtime` 只承载 greedy/dispatch 共用的无服务层反向依赖运行时状态与 helper。
- 两个新 sibling package 都不得反向 import `core.algorithms` 或 `core.services`；`__init__.py` 保持空聚合，不从子模块 re-export。
- 旧 import 路径继续可用，但只做显式同对象 re-export；生产函数调用方直连 canonical 叶子，避免兼容 wrapper 遮挡调用图。

### 1.1 design 相对 scan 粗原型的收敛

本 design 不直接照搬 `root-compatible-contract-leaf-v2`，而是在 `/tmp/a3-prototypes-20260712/root-compatible-split-leaves` 做了五项收敛：

1. 把纯合同与运行时实现拆成两个 sibling package：`core.algorithm_contracts` 与 `core.algorithm_runtime`。不再把 338 行 `internal_slot` 等运行时实现放进名为 contracts 的目录。
2. 删除无人使用的中间 `core.algorithms.date_parsers` wrapper。旧 `core.algorithms.greedy.date_parsers` 直接 re-export 最终 canonical，避免永久两跳兼容。
3. 新叶子直接依赖 A2 已建立的 `core.errors.ValidationError`，不再经过 `core.infrastructure.errors` 兼容路径。
4. 补齐 7 个被调用图识别出的生产函数调用方直连 canonical：`evaluation.py`、`ortools_bottleneck.py`、`optimizer_graph_ready_v2_features.py`、`optimizer_neighborhood_move_support.py`、`schedule_optimizer.py`、`greedy/internal_operation.py`、`greedy/run_context.py`。
5. `greedy.algo_stats` 不整模块搬空：只把 dispatch/runtime 所需的计数合同下沉；`snapshot_algo_stats`、`merge_algo_stats` 与模块全局 `deepcopy` 留在旧 canonical 模块，保住现有 monkeypatch 行为。

精简直连原型规模为 49 个生产 Python 文件，其中 16 个新叶子文件，约 `+1543 / -1375`；实施时再新增 1 个 A3 边界测试文件。绝大多数现有文件只改 import 或变为显式 re-export，真正搬动的是现有实现，不重写算法。

总风险为高：范围超过普通单次 refactor 上限，且触及排产主链类型、排序、派工状态和模块级 patch 控制点。风险由七个独立退出步骤控制，不允许把 49 文件一次性改完再统一排错。

本 design 不包含 `git commit`、push 或 PR；提交与 clean-HEAD 最终证明需要单独明确授权。

### 1.2 明确不做

- 不退役、延迟化或动态化 `core.algorithms.GreedyScheduler`。
- 不修改 `GreedyScheduler` 类定义位置、构造签名、`schedule` 签名或 `__module__`。
- 不把 dispatch 实现扁平化/复制到 greedy，不把旧 dispatch 模块降级成只转发函数的假兼容层。
- 不新增 `core.algorithms.date_parsers` 中间入口。
- 不用函数内 import、`TYPE_CHECKING`、动态 `__getattr__` 或吞错隐藏依赖。
- 不改排产顺序、日期解释、资源选择、时隙估算、统计计数、图模式、异常文本、配置、数据库或页面行为。
- 不移动 `core/services/scheduler/graph/ready_queue.py`；它是单向消费方，不构成 A3 返回边。
- 不处理 A4/A5/A6/tests SCC，不顺手推进算法插件化或新算法能力。

## 2. 前置依赖与冻结合同

### 2.1 起点证据

- 起点 HEAD：`582a588c8adda314584052b870ace00628a722c7`。
- production：763 模块 / 4 个 hard 目录 SCC；production-and-tests：1458 模块 / 5 个 SCC。
- A3：双 scope 均为 3 成员 / 42 条圈内边；父包初始化感知文件 SCC 为 21 成员 / 94 边。
- unresolved 为 6 / 44，parse error 为 0；纯显式 hard 文件 SCC 为 0。
- 当前 HEAD 的 SCIP 已重建；A3 精确边、关键函数上下游、AST import/patch 合同已记录在 scan 引用的 `/tmp` 证据中。
- 当前 HEAD 起点测试：15 文件 A3 专项 `120 passed`；完整 `tests/algorithm` `550 passed`。

### 2.2 新物理边界

| package | 文件 | 职责 | 禁止依赖 |
|---|---|---|---|
| `core.algorithm_contracts` | `date_parsers.py` | `parse_date`、`parse_datetime`、`due_exclusive` | `core.algorithms`、`core.services`、`core.algorithm_runtime` |
|  | `dispatch_rules.py` | dispatch Enum/输入合同/规则解析/派工 key | 同上 |
|  | `ordering.py` | 批次归一、排序输入与 key | 同上；错误类型直连 `core.errors` |
|  | `priority_constants.py` | 优先级常量、归一和权重 | 同上 |
|  | `sort_strategies.py` | `BatchForSort`、`SortStrategy`、策略实现/工厂 | 同上 |
|  | `types.py` | `ScheduleResult`、`ScheduleSummary` | 同上 |
|  | `value_domains.py` | INTERNAL/EXTERNAL/MERGED 值域 | 同上 |
| `core.algorithm_runtime` | `algo_stats.py` | `_empty_stats`、`_strict_int`、make/ensure/increment 计数合同 | `core.algorithms`、`core.services` |
|  | `auto_assign_contract.py` | `AutoAssignAttempt`、reason 常量、结果归一 | 同上 |
|  | `downtime.py` | timeline overlap/occupy helper | 同上 |
|  | `internal_slot.py` | 内部时隙估算、工时校验及结果对象 | 同上；错误类型直连 `core.errors` |
|  | `run_state.py` | `ScheduleRunState` | 同上；可单向依赖 `algorithm_contracts` |
|  | `runtime_state.py` | busy-hours 与 machine-last-state helper | 同上 |
|  | `dispatch_context.py` | dispatch 所需最小上下文适配与 legacy adapter | 同上；只依赖本 runtime 叶子 |

两个 package 的 `__init__.py` 只保留空文件或 docstring。调用方必须 import 具体模块，不建立新的聚合根入口。

### 2.3 旧路径兼容矩阵

| 旧路径 | canonical | 兼容方式 |
|---|---|---|
| `core.algorithms.greedy.date_parsers` | `core.algorithm_contracts.date_parsers` | 全部公开函数显式同对象 re-export |
| `core.algorithms.dispatch_rules` | `core.algorithm_contracts.dispatch_rules` | Enum/dataclass/解析函数/key builder 显式 re-export |
| `core.algorithms.ordering` | `core.algorithm_contracts.ordering` | 排序输入与 helper 显式 re-export |
| `core.algorithms.priority_constants` | `core.algorithm_contracts.priority_constants` | 常量与函数显式 re-export |
| `core.algorithms.sort_strategies` | `core.algorithm_contracts.sort_strategies` | Enum、类、工厂显式 re-export |
| `core.algorithms.types` | `core.algorithm_contracts.types` | 两个 dataclass 显式 re-export |
| `core.algorithms.value_domains` | `core.algorithm_contracts.value_domains` | 值域常量显式 re-export |
| `core.algorithms.greedy.downtime` | `core.algorithm_runtime.downtime` | 全部现有函数显式 re-export |
| `core.algorithms.greedy.internal_slot` | `core.algorithm_runtime.internal_slot` | dataclass/校验/估算函数显式 re-export |
| `core.algorithms.greedy.run_state` | `core.algorithm_runtime.run_state` | `ScheduleRunState` 同对象 re-export |
| `core.algorithms.greedy.dispatch.runtime_state` | `core.algorithm_runtime.runtime_state` | 两个 helper 同对象 re-export |
| `core.algorithms.greedy.auto_assign` | `core.algorithm_runtime.auto_assign_contract` + 原实现 | reason 常量、`AutoAssignAttempt`、结果归一从新叶子导入；自动派工实现仍在旧模块 |
| `core.algorithms.greedy.algo_stats` | `core.algorithm_runtime.algo_stats` + 原实现 | make/ensure/increment 与内部计数 helper 同对象导入；snapshot/merge/deepcopy 留在旧模块 |
| `core.algorithms.greedy.dispatch.*` | 原路径不变 | 继续是 canonical 执行模块，不做 wrapper |

`core.algorithms.__init__` 继续通过旧 `sort_strategies` / `types` wrapper 和 greedy 导出原有根 API。根包不直接 import 新 sibling leaves，避免改变仓内外调用代码。

### 2.4 公开 API 与对象合同

必须冻结：

- `core.algorithms.GreedyScheduler is core.algorithms.greedy.GreedyScheduler is core.algorithms.greedy.scheduler.GreedyScheduler`。
- `GreedyScheduler.__module__ == "core.algorithms.greedy.scheduler"`。
- 根 `__all__` 继续包含 `GreedyScheduler`、`BatchForSort`、`SortStrategy`、`StrategyFactory`、`ScheduleResult`、`ScheduleSummary`。
- `GreedyScheduler` 构造签名、`schedule` 签名、继承覆写和返回四元组语义不变。
- 兼容矩阵中的旧/新 Enum、dataclass、类、函数均为 `is` 同一对象；字段顺序、默认值、Enum 值、常量内容、函数签名、异常类型/文本不变。
- 旧优先、新优先两个独立 Python 3.8 进程都可导入，且对象 identity 不受导入顺序影响。

被移动对象自然 `__module__` 指向新的 canonical 路径；不运行时改写 `__module__` 伪装旧位置。仓内未发现 pickle/cloudpickle/dill、旧 `__module__` 断言、字符串反射或按源码路径加载；旧模块仍能解析旧 pickle 所引用的名称。唯一明确冻结原 `__module__` 的公开类是未移动的根 `GreedyScheduler`。

### 2.5 模块状态与 monkeypatch 合同

- `dispatch.batch_order`、`dispatch.sgs`、`dispatch.sgs_scoring` 和 scheduler 模块继续执行自身函数体；测试 patch 的模块 globals 必须仍是实际执行读取点。
- `estimate_internal_slot`、`build_dispatch_key`、`validate_internal_hours_for_mode`、`_score_internal_candidate` 和 scheduler 中 `dispatch_batch_order` 的现有 patch 路径不得变成“能 patch 但执行不读”。
- `greedy.algo_stats.deepcopy` 必须继续存在于旧模块，并被旧模块内的 `snapshot_algo_stats` / `merge_algo_stats` 真实读取。
- `ScheduleRunContext` 继续定义在 `greedy.run_context`。它本身满足 dispatch 所需方法合同，不移动类定义。
- `core.algorithm_runtime.dispatch_context.ensure_dispatch_context` 只为旧式直接 dispatch 调用构造 `_LegacyDispatchContext`；不得复制 SGS、时隙估算或自动派工算法。
- 任何现有 patch 合同失败都是 blocker，不能用改测试 patch 新路径掩盖兼容破坏。

### 2.6 import-cycle 终态合同

精简原型在未新增边界测试时为：

| scope | 模块 | hard 目录 SCC | A3 | A3 相关父包文件 SCC | unresolved | parse error |
|---|---:|---:|---|---|---:|---:|
| production | 779 | 3 | 消失 | 8 成员 / 24 边 | 6 | 0 |
| production-and-tests | 1474 | 4 | 消失 | 8 成员 / 24 边 | 44 | 0 |

实施新增一个测试模块后，终态预期为 production **779 模块 / 3 SCC**、production-and-tests **1475 模块 / 4 SCC**。硬约束：

- 双 scope 只删除 A3 的 3 成员 / 42 边目录块；A4/A5/A6/tests 的成员和圈内边逐项完全相同。
- 不新增目录 SCC；unresolved 仍为 6 / 44，parse error 0。
- 父包感知 hard 文件 SCC 总数仍为 9，纯显式 hard 文件 SCC 仍为 0。
- A3 相关父包文件 SCC 从 21 / 94 严格缩成原成员/边的 8 / 24 子集。
- runtime 文件 SCC 仍为 13，纯显式 runtime 文件 SCC 仍为 4。
- `core.algorithm_contracts`、`core.algorithm_runtime` 不得出现在任何 hard 目录 SCC 中。

### 2.7 调用图终态与允许差异

精简直连原型调用图双跑 10 个 JSON 文件集合和逐文件 SHA256 完全一致。预期正式调用图：

- 7337 callable；
- 25798 total edges；
- 10171 confident / 15627 ambiguous / typed 0；
- 8 个受限简单循环、193 islands；
- dynamic unresolved 685。

相对起点 7329 callable / 25786 edges：

1. 起点 7329 个 callable 通过路径映射全部有对应项，零旧 callable 丢失。
2. 新增 8 个 callable，全部来自 `_LegacyDispatchContext` 七个方法 + `ensure_dispatch_context`，不得再出现其它无解释新增 callable。
3. 全边比较在路径映射后有 6 条旧记录不再逐字相同、18 条新增记录：
   - 4 条旧 `local` 边变为相同端点的 `import` 边，来源是 algo-stats helper 下沉，不是调用丢失；
   - 2 条旧端点 `dispatch_batch_order/dispatch_sgs → ensure_run_context` 被明确替换为 `→ ensure_dispatch_context`；
   - 14 条新增端点全部是上述 8 个 adapter callable 的内部/接入边。
4. dynamic unresolved 从 680 → 685 的 5 个新增点只能来自 legacy adapter 的显式 callback 调用；import-cycle unresolved 不得增加。

最终实现若偏离这些计数，必须重新做全函数/全边映射并解释；不能仅因测试通过就刷新正式调用图。

### 2.8 dead-code 与平台合同

- dead-code 基线只迁移两个已绑定身份：
  - `core/algorithms/sort_strategies.py::WeightedStrategy.__init__` → `core/algorithm_contracts/sort_strategies.py::WeightedStrategy.__init__`；
  - `core/algorithms/types.py::ScheduleSummary.__post_init__` → `core/algorithm_contracts/types.py::ScheduleSummary.__post_init__`。
- 不全量 refresh dead-code 基线；quick 扫描不得出现 A3 新增候选。
- 新文件只使用 Python 3.8 语法和现有标准库/依赖；不改变 Win7 x64、离线交付或打包边界。

## 3. 执行顺序

### 步骤 1：锁定 A3 公开边界与模块状态

- **引用方法**：M-L1-04 Characterization Test。
- **具体操作**：新增 `tests/algorithm/test_algorithms_a3_dependency_boundary.py`，冻结 §2.3—§2.6：根 `GreedyScheduler` identity/`__module__`/签名/继承，合同与 runtime 旧新路径 identity，两个 leaf `__init__` 无聚合导出，旧/新正逆序独立 Python 3.8 import，生产 import 方向，algo-stats `deepcopy` patch，A3 SCC 消失及新叶子不入圈。现有 dispatch patch 行为继续由专项测试承接，不在边界测试里复制整套业务用例。
- **退出信号**：当前旧行为断言通过；依赖新路径和消圈的断言只因新模块尚不存在/A3 尚存在而按预期失败，不得有无关失败。
- **验证责任**：AI 自证。
- **回滚**：删除新增测试；生产代码仍未改。

### 步骤 2：建立纯 algorithm_contracts 叶子

- **引用方法**：M-L1-01 Parallel Change、M-L2-04 Move Function、M-L3-06 Layer Rectification。
- **具体操作**：
  1. 新增空聚合 `core/algorithm_contracts/__init__.py` 和 §2.2 的七个纯合同模块，按现有源码搬移实现，不改函数体、值或文本。
  2. `ordering.py` 的 `ValidationError` 直连 `core.errors`。
  3. 旧 `core.algorithms.{dispatch_rules,ordering,priority_constants,sort_strategies,types,value_domains}` 与 `greedy.date_parsers` 改为显式 re-export；不新增 `core.algorithms.date_parsers`。
  4. greedy/dispatch 及生产函数调用方直连 canonical；其中调用图重点文件为 `evaluation.py`、`ortools_bottleneck.py`、`optimizer_graph_ready_v2_features.py`、`optimizer_neighborhood_move_support.py`、`schedule_optimizer.py`。
  5. `core/algorithms/__init__.py` 保持逐字不变，通过旧 wrapper 继续提供根 API。
- **退出信号**：日期/排序/派工规则/类型 identity 与签名合同通过；根 API 不变；A3 的 algorithms 返回边显著收缩且无新 SCC；本步骤移动 callable 按路径映射零丢失，无 wrapper 遮挡的生产函数边。
- **验证责任**：AI 自证。
- **回滚**：恢复旧模块实现和生产 import，删除 `core/algorithm_contracts`。

### 步骤 3：建立 algorithm_runtime 共享运行时叶子

- **引用方法**：M-L1-01 Parallel Change、M-L2-04 Move Function、M-L3-07 Single Responsibility Split。
- **具体操作**：
  1. 新增空聚合 `core/algorithm_runtime/__init__.py`，搬移 downtime、internal-slot、run-state 和 dispatch runtime-state 实现；`internal_slot.ValidationError` 直连 `core.errors`。
  2. 抽出 auto-assign 的 dataclass、reason 常量和结果归一 helper；自动派工搜索实现仍留在 `greedy.auto_assign`。
  3. 只下沉 algo-stats 的计数合同；旧 `greedy.algo_stats` 保留 snapshot/merge/deepcopy 实现并显式导入共享计数 helper。
  4. 旧 downtime/internal-slot/run-state/dispatch-runtime-state 模块改为显式同对象 re-export。
  5. greedy 与 scheduler 的计数、时隙、状态函数调用方直连 runtime canonical；`greedy/internal_operation.py`、`greedy/run_context.py` 的 `auto_assign_attempt_from_result` 也直连新合同。
- **退出信号**：runtime identity/签名、工时校验、时隙、run-state、auto-assign、algo-stats 专项通过；`greedy.algo_stats.deepcopy` patch 仍命中真实执行；新 runtime 不 import algorithms/services；无新 SCC或无解释调用图边丢失。
- **验证责任**：AI 自证。
- **回滚**：恢复旧模块实现/import，删除 `core/algorithm_runtime`；合同叶子步骤可独立保留或一并回滚。

### 步骤 4：把 dispatch 切到最小上下文边界

- **引用方法**：M-L1-01 Parallel Change、M-L3-06 Layer Rectification。
- **具体操作**：
  1. 新增 `core.algorithm_runtime.dispatch_context` 的 `ensure_dispatch_context` 与 `_LegacyDispatchContext`；只适配 calendar/logger/stats 和四个既有 callback，不实现排产算法。
  2. `dispatch.batch_order` / `dispatch.sgs` 入口改用 `ensure_dispatch_context`；run-state、internal-slot、date、types、ordering、dispatch rules 全部直连 sibling leaves。
  3. `dispatch.sgs_scoring` / `resource_validation` 同步直连 canonical；dispatch 模块本身继续是执行主体。
  4. `ScheduleRunContext` 留在 greedy，继续由 scheduler 构造；它已满足 dispatch 方法合同，无需 wrapper 或类搬移。
- **退出信号**：至少 17 个已识别 patch 合同全部通过；batch-order、SGS、内部时隙、自动派工、graph-on 行为不变；A3 从双 scope 消失，A4/A5/A6/tests 不变；两条 context 旧边有明确 adapter 替代，无其它旧端点丢失。
- **验证责任**：AI 自证。
- **回滚**：恢复 dispatch import/context coercion，删除 adapter；步骤 2/3 的叶子可独立存在但 A3 会恢复，不能误报完成。

### 步骤 5：完成兼容与调用图闭环

- **引用方法**：M-L1-01 Parallel Change、M-L3-06 Layer Rectification。
- **具体操作**：
  1. 跑新增 A3 边界测试、15 文件专项和完整 `tests/algorithm`；逐项确认根 API、旧新 identity、导入顺序和 patch 模块状态。
  2. 双 scope 输出临时 JSON，按 §2.6 逐 SCC 成员和圈内边核对，不比较数量后直接下结论。
  3. 调用图输出两个独立临时目录，比较 10 文件集合/SHA；按 §2.7 映射 7329 个旧 callable、全部旧边、两条 adapter 替代和 14 条新增 adapter 端点。
  4. 若出现原型清单外的 wrapper 遮边，补生产调用方直连后重跑；不接受“测试绿但调用图少边”。
- **退出信号**：边界/算法/图模式测试全绿；双 scope 只删除 A3；调用图双跑确定，旧 callable 零丢失，旧边全部保留或落入批准的六条差异/adapter 替代表，无未解释漂移。
- **验证责任**：AI 自证。
- **回滚**：任何合同或映射失败都回到步骤 2-4 修正/回退，不刷新正式证据掩盖。

### 步骤 6：收紧正式证据并同步当前事实

- **引用方法**：M-L3-06 Layer Rectification。
- **具体操作**：
  1. 生成双候选 v2 基线；确认只删除 A3 目录块、A3 文件 SCC 严格缩为 8 / 24、其余记录不变后覆盖正式双基线，并跑两条 `--fail-on-new-cycle`。
  2. 用步骤 5 已验证的确定性候选覆盖正式调用图 10 JSON；记录 8 个 adapter callable 与全部允许边差异。
  3. 只迁移 §2.8 两个 dead-code 路径身份，跑 quick 扫描，不全量 refresh。
  4. 更新 `.codestable/checkup/baseline.json`、checkup README、相关 architecture/audits、dependency-cycle-governance roadmap/items 和 apply notes；架构文档只写已经落地的现状。
- **退出信号**：正式基线、调用图、dead-code、artifact SHA 和事实文档全部与最终源码一致；正式循环门禁通过；roadmap 在实现与提交前证明完成前不标 completed。
- **验证责任**：AI 自证。
- **回滚**：业务代码不回滚时，证据必须按当前源码重新生成；若差异无法解释，停止并回退实现，不得保留虚假基线。

### 步骤 7：提交前与 clean-HEAD 证明

- **引用方法**：M-L1-04 Characterization Test、M-L3-06 Layer Rectification。
- **具体操作**：跑 A3 边界、15 文件专项、完整 `tests/algorithm`、ready-queue/graph/calendar 直接合同；再跑 Ruff、Pyright gate/tools、Python 3.8 变更范围扫描、双 scope 正式循环门禁和允许脏工作区的无缓存/无续跑完整质量门禁。全部通过后停下请求 commit 授权；获授权提交后，在固定最终 HEAD 运行 `--require-clean-worktree --no-long-gate-cache --no-resume`。
- **退出信号**：专项、静态检查和完整门禁全部通过；只有提交后的最终 HEAD 工作区前后均干净，才能记录 clean-worktree proof。未获 commit 授权时只记录局部/dirty-worktree 证明。
- **验证责任**：AI 自证；commit、push、PR 均由 HUMAN 单独授权。
- **回滚**：提交前按步骤逆序恢复；提交后只创建独立 revert，不改写历史。

## 4. 风险与看点

- **根 API 被误删**：`core/algorithms/__init__.py` 必须零 diff；不能为少一条边删除 `GreedyScheduler`。
- **合同包变成杂物包**：纯合同与运行时实现分包；两个 `__init__` 不聚合导出，禁止后续随手塞 service/DB 逻辑。
- **旧模块假兼容**：dispatch 与 algo-stats 是模块状态合同，不是只看函数 `is`；patch 必须影响真实执行。
- **adapter 扩大动态盲区**：只接受 §2.7 已列的 5 个 callback unresolved 和 8 个 adapter callable；任何额外动态分发需停下复审。
- **wrapper 遮挡调用图**：函数生产调用方直连 canonical；旧路径主要服务仓外兼容、class/Enum import 和测试。
- **自然 `__module__` 改变**：移动对象采用新 canonical 模块名，不伪装；根 `GreedyScheduler` 因未移动而保持旧值。
- **父包初始化放大**：新 sibling 根 `__init__` 空聚合；不用 `from package import Symbol` 触发额外入口边。
- **范围失控**：49 个生产文件是上限基准；发现额外业务函数改写、算法语义变更或新的公共 API 时停止并回 design，不顺手扩展。
- **证据刷新顺序**：业务代码和边界测试冻结后才生成调用图/双基线/哈希；之后源码变化必须重跑。
- **平台约束**：只用 Python 3.8 和既有依赖，不新增运行时、云服务、网络加载或现代 Windows 专属能力。

## 5. 双轨复审

### 5.1 定向合同复审

按用户已选择的三项和 scan 已知风险逐项复核：

- A3-01：日期 canonical 直接落最终 `algorithm_contracts`，旧 greedy 路径单跳 identity-compatible，不新增中间入口。
- A3-02：dispatch 保持 canonical；共享运行时移到 sibling leaf；algo-stats patchable 状态保留在旧模块。
- A3-03：根 `GreedyScheduler` 与 `core.algorithms.__init__` 不动；返回边通过合同/运行时叶子移除，而非隐藏 import。
- 公开对象、签名、字段/Enum/常量、异常文本和导入顺序均有新增边界测试与现有专项承接。
- 15 文件专项和完整算法测试已在精简终态原型分别通过 `120 passed`、`550 passed`。

结论：三项合同均有具体实现边界和退出信号，未发现需改行为才能实施的 blocker。

### 5.2 调用链、模块状态与证据盲审

不从原粗原型结论出发，重新沿 package 职责、生产 import、monkeypatch、父包初始化和调用图检查，发现并纳入：

1. **contracts/runtime 命名失真**：已拆成两个 sibling package。
2. **多余 date wrapper**：`core.algorithms.date_parsers` 无消费方，已从设计删除；终态模块数从 780/1475（无边界测试）降为 779/1474，A3 文件 SCC从 9 / 28 进一步缩到 8 / 24。
3. **A2 wrapper 回借**：ordering/internal-slot 改直连 `core.errors`。
4. **algo-stats 模块状态**：粗原型完整算法测试曾暴露 `deepcopy` patch 失效；部分下沉方案已在终态原型修正并通过 550 项算法测试。
5. **7 个生产调用方遮边**：补 direct-canonical 后 confident 10160 → 10171，旧 callable 全映射；不把 wrapper 造成的少边当“结构变简单”。
6. **dispatch context 替代**：只有两条旧 `ensure_run_context` 端点被 `ensure_dispatch_context` 替代；其余旧端点无丢失。8 个新 adapter callable、14 条新端点和 5 个 dynamic unresolved 已显式列入批准范围。
7. **确定性**：精简直连调用图两次独立输出的 10 个 JSON 逐文件 SHA 完全一致；删除无函数的中间 wrapper 后 SHA 仍逐字相同。
8. **正式证据边界**：全部原型只在 `/tmp`；本 design 不更新正式基线、正式调用图、roadmap 状态或生产代码。

结论：当前 approved design 的已知设计 blocker 为 0。实现期间若终态超出 §2.6/§2.7 的 SCC、callable、边或 unresolved 白名单，视为新 blocker，必须停下回 design。

## 6. 用户 checkpoint

- 2026-07-12：用户整体批准本 design 的四项决策：两个 sibling leaf、旧路径 identity / 新 canonical `__module__`、调用图允许差异口径和步骤 1-7。
- 用户本次明确选择“批准并生成 checklist”：允许把 `status` 更新为 `approved` 并生成/校验执行清单。
- 本次批准**不包含 apply**：不创建 apply-notes，不修改生产代码、正式基线/调用图、roadmap 或 Git 历史。
- 后续进入 apply、`git commit`、clean-HEAD proof、push 和 PR 均继续单独请求明确授权。
