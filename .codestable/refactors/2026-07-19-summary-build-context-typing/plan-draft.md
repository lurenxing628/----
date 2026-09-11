# U01 实施计划草案：SummaryBuildContext 类型合同补齐（contracts 层，纯注解改动）

> 状态：draft（未实施）。来源：2026-07-19 debt-recheck-ultra 审计（.codestable/audits/2026-07-19-debt-recheck-ultra/，条目 U01）确认的 medium 存量债；本计划由 Plan subagent 探索产出、主代理落盘。
> 实施前需用户拍板 4 个决策点（D1-D4，见第 6 节）。约束：Python 3.8 / Win7 离线、纯注解不改行为、不得把重依赖引回 contracts 叶层、不得复活 A1 已拆的依赖圈。

## 0. 结论速览

- 38 个字段中 19 个已有具体类型（`int`/`str`/`datetime`/`List[str]`/`Set[int]` 等），无需动。
- 可安全补具体类型的：`end_date`、`input_build_outcome`（第 1 批，纯 stdlib/已有 import）；`batches`、`operations`、`results`、`summary`、`used_strategy`（第 2 批，引 core.models / core.algorithm_contracts 轻叶子，已验证无圈）。
- 必须保守的：`cfg`（被 dict/对象双态合同测试锁死 + 唯一具体类型在 config 层会引层间依赖）、`best_metrics`（唯一定义在重的 core.algorithms 子树，单列决策点）、12 个 `Dict[str, Any]` 元数据字段（真实异构 JSON 载荷，逐个论证后维持现状 + 文档注释）。
- 行为不变：文件首行有 `from __future__ import annotations`（contracts/schedule_summary_types.py:1），注解全是惰性字符串；全仓 core/web/data 无任何 `get_type_hints` 运行时调用（grep 零命中），frozen dataclass 生成的 `__init__` 不做类型校验，故测试里的 SimpleNamespace 鸭子构造运行时零影响。
- 不加运行时校验（决策点 D1 论证见第 6 节）。

## 1. 逐字段考证

### 1.1 构造点普查（方法与结果）

`python3 -m tools.symbol_locator callers SummaryBuildContext` 返回"未找到函数"（该工具面向函数，dataclass 构造不入图）——census 实际以 `grep -rn "SummaryBuildContext("` 完成，共 11 个构造点：

**生产构造点（2 个）：**
1. `core/services/scheduler/run/schedule_orchestrator.py:316-360` —— 主链唯一真实构造点，实参来自 `ScheduleRunInput`（core/services/scheduler/run/schedule_input_collector.py:27-67）与 `_NormalizedOptimizerOutcome`（schedule_orchestrator.py:63-79，归一自 `OptimizationOutcome`，core/services/scheduler/run/schedule_optimizer.py:41-55）。
2. `core/services/scheduler/summary/schedule_summary.py:116` —— `SummaryBuildContext(**ctx_kwargs)` 兼容 kwargs 通道；有测试实际走此路（tests/schedule/summary/test_schedule_summary_end_date_type_guard.py:38-44 直接以 kwargs 调 `build_result_summary`）。

**测试构造点（9 处 / 6 文件）：** tests/schedule/summary/test_schedule_summary_v11_contract.py:99、tests/schedule/summary/test_scheduler_summary_result_summary_contract.py:110、tests/algorithm/test_due_exclusive_consistency.py:66、tests/algorithm/test_optimizer_public_summary_projection_contract.py:41,120,552,626、tests/algorithm/test_dict_cfg_contract.py:224、tests/scheduler_graph/test_scheduler_graph_summary_contract.py:126。另有 tests/schedule/service/test_schedule_orchestrator_contract.py:330-339 对生产构造出的实例做字段断言。

**改写点：** `dataclasses.replace(ctx, cfg=...)` 于 schedule_summary.py:119、122-129（cfg 在消费端被重绑为 config 快照）。

### 1.2 字段裁决表

**A 类：已具体、不动（19 个）**
`version:int`、`normalized_batch_ids:List[str]`、`start_dt:datetime`、`algo_mode:str`、`objective_name:str`、`time_budget_seconds:int`、`best_score:Optional[Tuple[float,...]]`、`best_order:List[str]`、`frozen_op_ids:Set[int]`、`missing_internal_resource_op_ids:Optional[Set[int]]`、`scheduled_op_ids:Optional[Set[int]]`、`readiness_gate_enabled:bool`、`algo_warnings:Optional[List[str]]`、`execution_snapshot_revision:Optional[str]`、`execution_snapshot_op_ids:Optional[List[int]]`、`execution_snapshot_op_count:int`、`simulate:bool`、`t0:float`、`attempts/improvement_trace:List[Dict[str,Any]]`（后两个是真实异构 trace 记录，见 C 类论证）。

**B 类：可标具体类型**

| 字段 | 现注解 | 目标注解 | 真实来源证据 | 消费端证据 |
|---|---|---|---|---|
| `end_date` | `Optional[Any]` | `Optional[Union[date, str]]` | 生产传 `Optional[date]`（schedule_input_collector.py:30 `end_date_norm: Optional[date]`；orchestrator:321）；**str 形态被回归测试锁死**：test_schedule_summary_end_date_type_guard.py:70-71 断言字符串 "2026-02-10" 原样保留 | serialize_end_date 显式处理 str/date/None（schedule_summary.py:88-101）；assembly:433 |
| `input_build_outcome` | `Optional[BuildOutcome[Any]]` | `Optional[BuildOutcome[List[Any]]]` | schedule_input_collector.py:43 `algo_input_outcome: BuildOutcome[List[Any]]`；orchestrator:341 | schedule_summary.py:142 `_input_build_state(ctx.input_build_outcome)` |
| `batches` | `Dict[str, Any]` | `Dict[str, Batch]` | schedule_input_collector.py:38 `batches: Dict[str, Batch]`；orchestrator:322 | summary_runtime_state.py:176,181-184（keys 遍历 + getattr 鸭子读） |
| `operations` | `List[Any]` | `List[BatchOperation]` | schedule_input_collector.py:39；orchestrator:323 | schedule_summary_freeze.py:89-96 读 `op.id`/`op.batch_id`，与 core/models/batch_operation.py:34-36 字段吻合 |
| `results` | `List[Any]` | `List[ScheduleResult]` | `OptimizationOutcome.results: List[ScheduleResult]`（schedule_optimizer.py:42），两条归一路径 orchestrator:87,106 | schedule_summary_assembly.py:58-82 getattr `end_time/batch_id/op_id`，与 core/algorithm_contracts/types.py:11-25 吻合 |
| `summary` | `Any` | `Optional[ScheduleSummary]` | schedule_optimizer.py:43 注释即写明 "ScheduleSummary（来自算法模块）"；候选路径可为 None（orchestrator:107 `getattr(..., "summary", None)`），None 被显式处理（orchestrator:209-211；schedule_summary_freeze.py:72-79 全 getattr 安全） | 类定义 core/algorithm_contracts/types.py:29-49 |
| `used_strategy` | `Any` | `SortStrategy`（非 Optional） | schedule_optimizer.py:44 `used_strategy: SortStrategy`；类定义 core/algorithm_contracts/sort_strategies.py:18 | **消费端硬性要求非 None 且有 .value**：schedule_summary_assembly.py:428 直接 `ctx.used_strategy.value`（无 getattr 兜底）。若标 Optional，pyright basic 会在消费端报 Optional 成员访问，迫使改生产代码 → 违反纯注解原则，故标非 Optional。候选路径理论可产 None（orchestrator:108 getattr 默认 None），届时 assembly:428 照旧 AttributeError fail-loud，行为不变 |

**C 类：保守处理（维持现注解 + 补文档注释）**

| 字段 | 裁决 | 证据 |
|---|---|---|
| `cfg` | 保持 `Any`，补注释说明三态合同 | ① dict/属性对象双态被合同测试锁死：test_dict_cfg_contract.py:257-299 要求 dict 与 SimpleNamespace cfg 行为一致，且经 ctx 进 summary（:224）；② 消费端在 replace 后变为 config 层 `ScheduleConfigSnapshot`（schedule_summary.py:122-129 → config_snapshot.py:337-347），同一字段生命周期内有两种真实类型；③ 唯一准确的具体类是 `core/services/scheduler/config/config_snapshot.py:26`——config 是 A1 SCC 成员目录（boundary test `_A1_MEMBERS` 含 config），contracts 引它违背叶子定位；core/models 有"双栈锁步"孪生类（core/models/schedule_config_runtime_snapshot.py:9），但它是**不同的类**，运行时实例不是它，标它就是撒谎 |
| `best_metrics` | 决策点 D2（默认：TYPE_CHECKING 引 `ScheduleMetrics`；保守备选：维持 Any） | 唯一定义在 core/algorithms/evaluation.py:41；import 会触发 core/algorithms/__init__.py 加载 GreedyScheduler 全家（core/algorithms/__init__.py:13-15）。无圈（core/algorithms 全目录 grep 无任何 core.services import；evaluation.py:97 的 config 引用走的是 core.models.schedule_config_runtime 惰性 import），但违背"contracts 轻叶子"精神。消费全鸭子：summary_visible_degradation.py:15-26 `metrics.to_dict()` try 包裹、schedule_summary_degradation._metric_int getattr。测试用**真** ScheduleMetrics（v11 contract 测试头部直接 import） |
| `used_params`、`search_report`、`algo_stats`、`freeze_meta`、`downtime_meta`、`resource_pool_meta`、`graph_analysis_public`、`graph_analysis_diagnostics`、`candidate_comparison_public`、`attempts`、`improvement_trace` | 维持 `Dict[str, Any]` 族 | 均为多产地 dict 字面量拼装的异构 JSON 载荷，例：downtime_meta 空 dict 起手逐处 mutate（schedule_input_runtime_support.py:85-111）；candidate_comparison_public 由 getattr 投影拼 dict（schedule_candidate_runner→schedule_candidate_summary.py:141-153）。TypedDict 化需跨 5+ 生产模块同步维护且仓内**无 TypedDict 先例**（全仓 core 只有 Protocol 先例：operation_execution_feedback_actions.py:18、schedule_optimizer_steps.py:37 等 4 处） |
| `warning_merge_status` | 决策点 D3（默认维持；可选 TypedDict） | 形状固定三键：orchestrator:200-204,229（summary_merge_attempted:bool / summary_merge_failed:bool / summary_merge_error:Optional[str]），且被 test_schedule_orchestrator_contract.py:335-339 锁死。是唯一"值得 TypedDict"的候选，但同上无先例，默认不做 |

## 2. 依赖圈安全

### 2.1 contracts 层现行 import 白名单（现状 + A1 裁决）

现有全部 import（grep 该目录 5 文件）：stdlib、`typing`、`core.models.public_identifier_redaction`（optimizer_public_safety.py:5）、`core.models.scheduler_degradation_messages`（optimizer_public_safety.py:6）、`core.models.public_identifier_redaction`（graph_public_summary.py:5）、`core.services.common.build_outcome`（schedule_summary_types.py:8）。

A1 设计裁决（.codestable/refactors/2026-07-10-scheduler-a1-dependency-decoupling/scheduler-a1-dependency-decoupling-refactor-design.md）：
- contracts 是"neutral contracts"叶层，用于单向化 run⇄summary（design.md:6, :51-54）；
- "兼容 wrapper 只能从新叶子导入，不能让新叶子反向 import wrapper"（design.md:66）；
- "`contracts/__init__.py` 保持空/无重导出"（design.md:67）——本次不动 `__init__.py`；
- "不改 dataclass 字段、默认值、Enum 值"（design.md:68）——本次只改注解，字段名/序/默认值不动；
- "扫描验收看目录 SCC 成员/边，不用函数内 import 或 TYPE_CHECKING 掩盖 hard 边"（design.md:69）——该裁决语境是 A1 验收时不得用 TYPE_CHECKING 把**圈内真实运行时依赖**藏起来。本计划第 2 批的新 import 全部走**运行时 hard import**（不藏）；唯一建议走 TYPE_CHECKING 的是 D2 的 `ScheduleMetrics`，它不在任何 SCC、也不是被掩盖的运行时依赖（contracts 运行时根本不用它），属类型引用而非依赖倒置——此解读在 D2 单列，由用户裁决。

### 2.2 每个新 import 的无圈论证

| 新 import | 反向依赖检查 | 结论 |
|---|---|---|
| `datetime.date` | stdlib | 无风险 |
| `core.models.batch` / `core.models.batch_operation` | core/models 全目录 grep 无任何 `core.services` import（零命中）；两模块只依赖 `._helpers` 与 `.enums`（batch.py:6-7、batch_operation.py:6-15）。contracts→core.models 边已有先例（optimizer_public_safety.py:5-6） | 无圈 |
| `core.algorithm_contracts.types`（ScheduleResult, ScheduleSummary）、`core.algorithm_contracts.sort_strategies`（SortStrategy） | core/algorithm_contracts 全目录 grep 无 `core.services` import（零命中）；包 `__init__.py` 仅 docstring；types.py 只依赖 `.value_domains`（types.py:7），sort_strategies.py 只依赖 stdlib + `.priority_constants`（sort_strategies.py:9-15） | 无圈，且轻 |
| （D2）`core.algorithms.evaluation.ScheduleMetrics` | core/algorithms 全目录 grep 无 `core.services` import；但包 `__init__` 拉起 GreedyScheduler（core/algorithms/__init__.py:13） | 无圈但重 → TYPE_CHECKING 或不做 |

**明确禁止**：import `core.services.scheduler.{config,run,summary}` 任何模块（config 虽当前不引 contracts，但它在 boundary test 的 `_A1_MEMBERS` 集合内，contracts→config 一旦 config 未来引 contracts 即成圈，且立即违背叶子定位）。

### 2.3 验证方法（每批必跑）

1. `python3 -m pytest tests/schedule/service/test_scheduler_a1_dependency_boundary.py` —— 四合一：旧/新路径对象 identity（test:72-104）、7 个关键签名冻结（test:107-122）、正逆序干净解释器导入（test:125-139）、A1 目录 SCC 缺席（test:142-153，内部跑 `tools.scan_import_cycles --json`）。
2. `python3 -m tools.scan_import_cycles --json` 人工核对 contracts 不进任何 SCC（A1 验收基线：761 模块 / 5 个 hard 目录 SCC）；正式口径可加 `--fail-on-new-cycle` 对 v2 基线比对。
3. 扫描器分类口径：TYPE_CHECKING 块归 `typeonly`，"运行时不执行,不计入耦合"（tools/scan_import_cycles.py docstring :12/:28）——D2 若采纳，机器验收不受影响，需靠人工遵守 2.1 的裁决解读。
4. symbol_locator 对类不可用（1.1 已证），不作为圈验证手段；模块级以 scanner + boundary test 为准。

## 3. 分步实施计划

### 第 0 批：基线固定（不改代码）
- 跑一遍 boundary test、`tools.scan_import_cycles --json`、`python -m pyright -p pyrightconfig.gate.json`、目标 pytest 套件，记录绿基线。
- 注意 attention.md 裁决：symbol_locator/dead-code 门禁的已知误报口径（.codestable/attention.md "命令与脚本陷阱"节）。

### 第 1 批：零风险（stdlib + 已有 import 收紧 + 文档注释）
改动仅 contracts/schedule_summary_types.py：
- `end_date: Optional[Any]` → `Optional[Union[date, str]]`（补 `from datetime import date`；**不要**只标 `Optional[date]`，会与 end_date type guard 测试锁的 str 合同矛盾）；
- `input_build_outcome: Optional[BuildOutcome[Any]]` → `Optional[BuildOutcome[List[Any]]]`；
- `cfg` 保持 `Any`，加行内注释：三态（dict / 属性对象 / config 层 ScheduleConfigSnapshot，消费端 schedule_summary.py:122-129 统一归一）+ 为何不标具体类（层间禁令）。
- 验证：2.3 全套 + `pytest tests/schedule/summary/ tests/algorithm/test_dict_cfg_contract.py tests/algorithm/test_due_exclusive_consistency.py` + pyright 双配置 + `python3 -m tools.scan_py38plus_syntax` + ruff。

### 第 2 批：轻叶子具体类型（5 个字段）
- 新增运行时 import：`from core.models.batch import Batch`、`from core.models.batch_operation import BatchOperation`、`from core.algorithm_contracts.types import ScheduleResult, ScheduleSummary`、`from core.algorithm_contracts.sort_strategies import SortStrategy`；
- `batches: Dict[str, Batch]`、`operations: List[BatchOperation]`、`results: List[ScheduleResult]`、`summary: Optional[ScheduleSummary]`、`used_strategy: SortStrategy`；
- 建议拆两小步提交：先 `operations`+`batches`（core.models），再 `results`+`summary`+`used_strategy`（algorithm_contracts），每步独立跑 boundary test + scanner，坏了单步回滚；
- 试点验证（本批第一步做）：改后先只跑 `python -m pyright -p pyrightconfig.json`（含 tests 的默认配置）确认 SimpleNamespace 假对象产生的诊断量级，再决定是否对 `results`/`summary`/`used_strategy` 降级为 Protocol 方案（见 5.2；gate 配置不含 tests，不会挡门禁，此试点只关 IDE 噪音）。

### 第 3 批：决策点批（逐项经用户拍板后执行）
- D2：`best_metrics` → `Optional[ScheduleMetrics]`，`if TYPE_CHECKING:` 块引入 + 字符串注解。若按严格口径读 design.md:69，则维持 `Optional[Any]` + 注释指向 core/algorithms/evaluation.py:41。
- D3：`warning_merge_status` TypedDict（默认不做）。
- D4：注解快照测试（见第 4 节）。

### 各批公共验证清单
```
python3 -m pytest tests/schedule/service/test_scheduler_a1_dependency_boundary.py \
  tests/schedule/service/test_schedule_orchestrator_contract.py \
  tests/schedule/summary/ tests/algorithm/test_dict_cfg_contract.py \
  tests/algorithm/test_due_exclusive_consistency.py \
  tests/algorithm/test_optimizer_public_summary_projection_contract.py \
  tests/scheduler_graph/test_scheduler_graph_summary_contract.py
python3 -m tools.scan_import_cycles --json     # contracts 不进 SCC
python -m pyright -p pyrightconfig.gate.json   # gate 口径（core，不含 tests）
python3 -m tools.scan_py38plus_syntax          # 3.8 语法门禁
ruff check core/services/scheduler/contracts/
```

## 4. 测试策略

### 4.1 现有锁定（不需重写，只需保绿）
- **构造/消费行为**：第 1.1 节 6 个测试文件 9 个构造点 + orchestrator contract 对 ctx 实例断言（test:330-339）+ kwargs 通道（end_date type guard）+ dict cfg 双态合同 + v11 摘要合同 + 投影合同 + 图摘要合同 + due exclusive 一致性。其中多份在 gate 必跑注册表内（tools/test_registry_data.py:185 v11、`QUALITY_GATE_GUARD_TESTS` 含 orchestrator contract / due_exclusive 等）。
- **合同层边界**：boundary test 四合一（见 2.3）。

### 4.2 新增测试建议（D4，建议做，成本低）
新增一个注解快照测试（放 tests/schedule/service/ 与 boundary test 同目录），锁 `SummaryBuildContext.__annotations__` 的**原始字符串** dict 全量相等，防止未来重构退回 `Any`：
- 先例：tests/schedule/service/test_schedule_service_facade_delegation.py:28-33 已用 `get_type_hints(...)==List[ScheduleSeedRow]` 锁仓储返回注解；
- **必须用 `__annotations__` 原始字符串而非 `get_type_hints`**：若 D2 采纳 TYPE_CHECKING import，`get_type_hints` 运行时解析会 NameError（PEP 563 下 `__annotations__` 是字符串，天然可比对）；
- 是否注册进 gate required 列表（tools/test_registry_data.py）单独问用户——改注册表属于门禁配置变更。

## 5. 风险与回滚

### 5.1 大文件门禁
`FILE_SIZE_LIMIT = 500`（tools/quality_gate_shared.py:223）。目标文件现 139 行；全部批次合计新增约 10-25 行。上限余量 ~330 行，无风险。schedule_summary.py（221 行）、schedule_orchestrator.py（415 行）本计划**不改动**（415 已贴近门禁，是不动它的额外理由）。

### 5.2 测试鸭子假对象"误伤"核实
- **运行时：确证无伤。** ① frozen dataclass 生成的 `__init__` 不校验类型；② `from __future__ import annotations`（contracts 文件 :1）使所有注解为惰性字符串；③ 全仓 core/web/data grep `get_type_hints` 零命中；④ `dataclasses.replace`/`fields()` 不解析注解。8 个用 SimpleNamespace 的测试文件运行时行为不变。
- **静态门禁：确证不挡。** 正式门禁 pyright 只跑 `pyrightconfig.gate.json`（include 仅 app/core/data/web，无 tests，gate.json:2-9）与 `pyrightconfig.tools.json`（tools/quality_gate_shared.py:106-107；long_gate_manifest.py:143-145 锁死这两个 -p 调用）。
- **IDE 噪音：确证存在、可接受或可规避。** 默认 `pyrightconfig.json` include 含 tests（:8）。SimpleNamespace 赋给 `Dict[str, Batch]` 在 basic 模式必报 reportArgumentType。规避备选：对 `results`/`summary`/`used_strategy` 改用文件内 Protocol（仓内 Protocol 先例充分）；但 SimpleNamespace 是否满足 pyright 的 Protocol 匹配：证据不足，故第 2 批安排试点先验，若 Protocol 也报，则在"接受 IDE 噪音"与"该三字段维持 Any"之间由用户择一。
- **注解快照测试与 TYPE_CHECKING 的互斥**：见 4.2，已用 `__annotations__` 方案规避。

### 5.3 回滚
每批一个独立 commit、只动一个文件（+可选新测试文件），`git revert` 单批即回滚；无数据迁移、无接口变更、无字段序变化（design.md:68 的 dataclass 字段冻结裁决同样约束本次：只改类型标注，不动字段名/序/默认值）。回滚验证 = 重跑 2.3 清单。

## 6. 单列决策点

- **D1（运行时校验，建议：不加）**：① cfg 的鸭子多态是被合同测试有意锁定的特性（test_dict_cfg_contract），加 `__post_init__` isinstance 校验直接打红 8 个测试文件 = 行为变更，超出 U01 范围；② cfg 已有响亮归一路径 `ensure_schedule_config_snapshot`（schedule_summary.py:122-129，带降级事件收集）；③ used_strategy 为 None 时 assembly:428 天然 AttributeError，已是 fail-loud，前移校验收益为零。
- **D2（best_metrics）**：TYPE_CHECKING 引 ScheduleMetrics vs 维持 Any。取决于对 design.md:69 裁决的解读宽严（分析见 2.1/2.2）。
- **D3（warning_merge_status TypedDict）**：形状已被测试锁死但仓内无 TypedDict 先例，默认不做。
- **D4（注解快照测试 + 是否入 gate 注册表）**：建议做测试；注册表变更单独确认。

## 证据不足处（明示）

1. pyright 对 SimpleNamespace vs Protocol 的匹配行为——未实测，列为第 2 批试点。
2. `used_strategy` 在候选比较生产路径下是否真的可能为 None（orchestrator:108 的 getattr 默认 None 只是防御写法）——不影响本计划，但若未来要标 Optional 需先补此考证。
3. `results` 在种子/执行回填路径中元素是否 100% 为 ScheduleResult（`coerce_seed_results` 的输出未逐行核）——现有声明与消费端全 getattr 兜底使风险为零，但严格意义上属声明信任。

## 关键文件

- core/services/scheduler/contracts/schedule_summary_types.py（唯一改动目标）
- core/services/scheduler/run/schedule_orchestrator.py（主生产构造点，字段来源对照）
- core/services/scheduler/run/schedule_input_collector.py（ScheduleRunInput 真实类型源）
- core/services/scheduler/summary/schedule_summary.py（消费端 + kwargs 通道 + cfg 重绑）
- tests/schedule/service/test_scheduler_a1_dependency_boundary.py（依赖圈/identity 验收闸门，新快照测试的参照与落点）
