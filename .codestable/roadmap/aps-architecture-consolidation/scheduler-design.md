---
doc_type: architecture-proposal
status: approved
created: 2026-11-09
updated: 2026-11-09
---

# 排产计算主链与求解职责收敛设计

本文是[整体优化路线图](aps-architecture-consolidation-roadmap.md)的调度专题，描述已对齐定稿的目标架构，尚未表示代码已经迁移。
设计基于 2026-11-09 的当前工作树；源码锚点是本次设计的调查位置，实施时重新核对。
本专题覆盖 `Preflight ↔ Admission ↔ Compute ↔ Trial ↔ Adoption` 全链路，只收敛内部职责、类型和调用关系，不改变排产业务规则。

## 1. 目标与统一切换原则

目标是让维护者沿“预检评估 → 业务准备（`PreparedBusinessInput`） → 求解资源与搜索（`SolverInput` + `SolverResources`） → 共同约束验证（`ScheduleValidationOutcome`） → 结果发布/正式采用”理解排产全链路，不必同时记住继承 DTO、双轨模式开关、回调装配和重复校验。
保留实际有价值的算法分层：工作台负责现场事实、准备准入、安排约束核验与运行生命周期，scheduler 负责搜索策略与图准备，algorithm 负责资源约束下的解码安排。
一次性迁移全部生产和测试调用者，统一切换后删除旧类型、旧函数、8 行纯转发模块和私有旁路；不保留 adapter、re-export 或兼容开关。
下文分块用于表达实施依赖与共享文件分工，不代表分批发布，不允许旧、新两条排产链并行运行。

**持久化存储格式 0 变更**：
现有业务数据与归档 schema 原样保留。候选发布在 [result_preparation.py:24](../../../core/services/workbench/run/result_preparation.py#L24) 使用 `fields(candidate)` 序列化；内部内存类型重构时显式保持落盘归档 JSON 键名与结构不变，无需历史归档迁移或运行期旧格式兼容分支。

**用两份明确的核心结果贯通业务链**：
避免给准备或验证函数增加 `for_adoption`、`strict=False`、`prevalidated=True` 等双轨模式开关，全链路围绕两份具名结构运转：
1. **第一份：业务评估与准备结果（`PreparedBusinessInput`）**——统一承载预检/受理/计算/候选采用/试调采用的业务事实、种子保护与范围约束。
2. **第二份：安排约束验证结果（`ScheduleValidationOutcome` / 共同验证核心）**——统一承载候选发布、普通/分件正式采用与试调保存/采用的排程约束核验产物。

## 2. 现状与需要解决的具体成本

当前主链存在四类结构性成本：

1. **输入准备与编排层叠床架屋**：
   当前计算链路是 `WorkbenchRunWorker` → `compute_candidate_run` → `prepare_candidate_run_input` → `orchestrate_schedule_run` → `run_candidate_comparison` → `optimize_shared_schedule` → `SharedDecodeSession` → `GreedyScheduler.schedule_prepared`。
   工作台的[计算入口](../../../core/services/workbench/run/compute.py#L21)既准备输入，又通过回调把候选计算与摘要构造交给[编排器](../../../core/services/scheduler/run/schedule_orchestrator.py#L21)。编排器先经过只做调用与解包的 `_run_plan_selection`，再构造摘要上下文；而生产调用只来自 [compute.py:81](../../../core/services/workbench/run/compute.py#L81)。
   [ScheduleRunInput](../../../core/services/scheduler/run/schedule_input_contracts.py#L16) 平铺业务工序、执行快照、求解输入、资源池、验证范围和摘要元信息；[CandidateRunInput](../../../core/services/workbench/run/input.py#L34) 继承它并追加现场 facts、分类、最新计划和分件范围。同一个 [prepare_candidate_run_input](../../../core/services/workbench/run/input.py#L53) 用 `for_adoption` 开关区分受理、计算和采用；[build_runtime](../../../core/services/workbench/run/input_runtime.py#L176) 在采用分支返回含 `[]/{}/None/0` 的九元位置元组，调用者在 [input.py:122](../../../core/services/workbench/run/input.py#L122) 按位置解包。试调采用还在 [trial/adoption_input.py:18](../../../core/services/workbench/trial/adoption_input.py#L18) 穿透调用 `input.py` 私有 `_prepare_facts`。

2. **预检与受理准备链断链**：
   虽然当前工作树 [input_admission.py:32](../../../core/services/workbench/run/input_admission.py#L32) 已复用 `held_arrangements`，但仍存在三处病灶：
   - [web/routes/workbench/preflight.py:54-56](../../../web/routes/workbench/preflight.py#L54-L56) 在重型 `evaluate_prepared` 之后才调 `_require_current` 核验 `input_ref` 指纹是否过期；
   - [core/services/workbench/run/preflight_result.py:76-78](../../../core/services/workbench/run/preflight_result.py#L76-L78) 在构造公开预检 DTO 时原地 `row.pop("op_id", None)`、`row.pop("external_execution_cycle", None)` 破坏了评估行，导致受理无法直接复用；
   - 跨阶段在 `PreparedPreflight` / `PreflightFacts` 上原地回填属性。

3. **候选、分件与试调约束校验多套并存且同事务双跑**：
   - [core/services/workbench/trial/adoption_validation.py:48-63](../../../core/services/workbench/trial/adoption_validation.py#L48-L63) 在同一写事务内先跑 `TrialValidator.evaluate_saved()`，隔 6 行又调 `prepare_trial_adoption_input + validate_candidate + validate_adoption_payload` 把全量校验重跑第二遍；
   - [candidate_adoption_constraints.py](../../../core/services/workbench/run/candidate_adoption_constraints.py) 与 [piece_adoption.py:121-189](../../../core/services/workbench/run/piece_adoption.py#L121-L189) 复制粘贴了两套逐行约束验证；
   - [schedule_execution_persistence_guard.py:95](../../../core/services/scheduler/run/schedule_execution_persistence_guard.py#L95) 仍保留按 `(batch_id, seq)` 线性平铺扫描下游的旧守卫；
   - [candidate_adoption_persistence.py:7](../../../core/services/workbench/run/candidate_adoption_persistence.py#L7) 与 [trial/adoption_persistence.py:7](../../../core/services/workbench/trial/adoption_persistence.py#L7) 存在两个 8 行纯转发文件。

4. **日历引擎存在连接型基类与多套快照子类**：
   `CalendarService`、[SnapshotCalendarEngine](../../../core/services/capacity/plan_calendar_engine.py#L9) 与 [_SavedCalendarEngine](../../../core/services/workbench/facts/archived_calendar.py#L32) 并存，[service.py:79](../../../core/services/scheduler/calendar/service.py#L79) 的断点证据依赖连接元数据 [connection_guards.py:53](../../../core/infrastructure/connection_guards.py#L53)，跨夜尾巴分段在 [engine.py:313](../../../core/services/scheduler/calendar/engine.py#L313) 与 [plan_calendar_windows.py:33](../../../core/services/capacity/plan_calendar_windows.py#L33) 重复实现。

已有正确机制继续保留：
- [worker.py:65](../../../core/services/workbench/run/worker.py#L65) 拥有运行锁、领取、失败记录及最终结果事务。
- [worker.py:93](../../../core/services/workbench/run/worker.py#L93) 在隔离数据库快照中共享一次生产 capture，[worker.py:111](../../../core/services/workbench/run/worker.py#L111) 在最终写事务重新取得当前事实。
- [ProductionFactsCapture.table](../../../core/services/workbench/facts/production_capture.py#L163) 与 [resource_facts](../../../core/services/workbench/facts/production_capture.py#L187) 复用原始表、业务类型转换和资源索引。
- [SharedDecodeSession](../../../core/services/scheduler/run/optimizer/shared_decode.py#L101) 拥有解码请求账本，[NativeSchedulePreparation](../../../core/algorithms/greedy/scheduler.py#L139) 拥有一次搜索的固定算法输入。

## 3. 目标职责与依赖方向

| 职责 | 目标拥有者 | 输入与输出 | 不承担的职责 |
|---|---|---|---|
| 预检评估与投影 | `workbench/run/preflight*.py` | 轻量指纹核验 → 内部不可变评估结果 → 公开预检 DTO | 不在重计算后才验版本，不原地 `pop` 篡改评估行 |
| 运行生命周期 | `workbench/run/worker.py` | 已受理归档 → 计算结果 → 原子保存回执 | 不选择邻域，不重算当日物料分类，不创建第二份算法事实 |
| 业务输入准备 | `workbench/run/input.py` | 本事务事实、设置、执行投影、保留安排 → `PreparedBusinessInput` | 不构建求解器，不生成空占位资源元组 |
| 现场资源提取 | `workbench/run/input_runtime.py` | `PreparedBusinessInput`、capture → `SolverResources`（含 `CalendarInputs`） | 不重新分类，不创建算法引擎，不重读相同表 |
| 共同排程约束验证 | `workbench/run/` 共同验证模块 | `PreparedBusinessInput`、`CalendarEngine`、待验安排 → `ScheduleValidationOutcome` | 不为普通/分件/试调维护三套逐行校验循环 |
| 候选计算用例 | `workbench/run/compute.py` | 业务输入、求解输入、资源 → 经验证的候选与摘要 | 不领取任务，不保存正式计划，不经 orchestrator 回调绕圈 |
| 固定算法准备与共同搜索 | `scheduler/run` | `SolverInput`、`SolverResources` → 纯 `CalendarEngine`、图/native preparation → `CandidateComparisonOutcome` | 不读数据库，不引用工作台 facts，不接受带连接服务 |
| 真实解码 | `optimizer/shared_decode.py` 与 `algorithms/greedy` | 固定准备、候选变化 → 实际安排与指标 | 不解释归档，不决定页面发布格式 |
| 输出发布与正式落库 | `result_preparation.py` 与 `official_persistence.py` | 已验证候选/采用命令 → 归档材料或正式计划回执 | 不再次求解，不保留 8 行纯转发文件 |

`scheduler` 不 import `workbench`；普通工序与分件工序都通过公共算法输入描述真实前置关系。
`workbench/facts` 继续保持叶子职责，不依赖 run/trial 服务；SQL 仍属于仓储与基础设施。

## 4. 数据所有权与阶段契约

### 4.1 业务准备结果（`PreparedBusinessInput`）

`PreparedBusinessInput` 替代工作台对 `CandidateRunInput` 的继承使用，是受理、计算、候选采用、试调采用共同消费的唯一业务准备结果。
它引用本事务的 `PreflightFacts/ProductionFactsCapture`，不复制事实表；只在所属事务或隔离计算进程内使用，不跨请求保存。

**`PreparedBusinessInput` 必须完整持有以下字段与精确边界**：
- **基础设置与事实**：`settings`、`facts`（`PreflightFacts`）、`batches`、`operations`（原始 `BatchOperation`）、`config`（`ScheduleConfigSnapshot`）、`start`、`end_date`、`readiness_gate_enabled`。
- **完整 `algo_ops: Sequence[OpForScheduleAlgo]`**：精确定义为**可排工序 + 执行/合并外协保护节点**（见 [input.py:153](../../../core/services/workbench/run/input.py#L153) `_algorithm_scope`）。既不能把 skipped/合法待料工序塞回求解图，也不能从 `PreparedBusinessInput` 移走——否则会导致候选验证 [compute_validation.py:16](../../../core/services/workbench/run/compute_validation.py#L16)、[:49](../../../core/services/workbench/run/compute_validation.py#L49)、采用复核 [candidate_adoption_constraints.py:83](../../../core/services/workbench/run/candidate_adoption_constraints.py#L83)、[:152](../../../core/services/workbench/run/candidate_adoption_constraints.py#L152) 以及分件采用 [piece_adoption.py:78](../../../core/services/workbench/run/piece_adoption.py#L78) 断链。
- **完整业务执行保护结构 `ExecutionGuardState`**：内聚 `execution_facts`（含多段实际资源占用 `execution_resource_segments`）、`execution_completed_op_ids`、`execution_seed_results` 以及 `execution_snapshot_revision / op_ids / op_count`（见 [input.py:104](../../../core/services/workbench/run/input.py#L104)、[candidate_adoption_constraints.py:27](../../../core/services/workbench/run/candidate_adoption_constraints.py#L27)、[schedule_orchestrator.py:83](../../../core/services/scheduler/run/schedule_orchestrator.py#L83)）。数量只在构造处求出一次，下游直接消费。
- **`seeds: SeedPreparation`**：包含 `frozen_op_ids`、`seed_results`、`freeze_meta` 以及在种子准备阶段形成的**待排子集 `to_schedule: Sequence[OpForScheduleAlgo]`**。固定人员资格校验与待排工时准入（[schedule_input_runtime_support.py:145](../../../core/services/scheduler/run/schedule_input_runtime_support.py#L145)）留在种子准备阶段完成，采用路径同样执行该业务准入，绝不跳过。
- **完整 `piece_scope: Optional[PieceScope]` 与显式前置关系 `predecessors: Mapping[int, Sequence[int]]`**：`piece_scope` 保留分件目标数量 `work.target_quantity` 与分件树范围（供 [piece_adoption.py:93](../../../core/services/workbench/run/piece_adoption.py#L93)、[:110](../../../core/services/workbench/run/piece_adoption.py#L110) 核验），`predecessors` 表达完整显式前置边。
- **分类与基线约束**：`dispositions`、`baseline_version`（原 `prev_version`）、`latest_plan_rows`、`allowed_op_ids`（原 `schedule_output_allowed_op_ids`）、`missing_internal_resource_op_ids`、`operation_sources`。
- **`operation_efforts: Sequence[OperationEffort]`**：在受理回执（[jobs.py:94-97](../../../core/services/workbench/run/jobs.py#L94-L97)）与计算结果发布（[result_preparation.py:78](../../../core/services/workbench/run/result_preparation.py#L78)）两个出口消费，供下游决策、候选工时与试调消费。其构造依赖 `seeds.to_schedule` 和 [input_effort.py:19](../../../core/services/workbench/run/input_effort.py#L19) 的 `saved_seed_efforts` 按原正式版本读取保留安排的历史工时需求（不能用当前模板重算保留安排）；仅正式采用路径不构造 `operation_efforts`（传 `()`）。

### 4.2 算法输入（`SolverInput`）与求解资源（`SolverResources`）

`SolverInput` 仅在计算路径构造，只保留真实供图构建、搜索、评分与解码使用的字段，不继承工作台上下文：
- **借用 `business.algo_ops`**：供 [schedule_graph_report.py:110](../../../core/services/scheduler/run/schedule_graph_report.py#L110) 构建完整图节点（包含保护工序节点）。
- **借用 `business.seeds.to_schedule`**：作为本次待排工序子集，与 `seeds` 一起驱动解码。
- **剔除无关字段**：不再往 `SolverInput` 中塞入搜索与解码根本不读的 `operation_efforts`、`PreflightFacts`、数据库连接或页面投影。

`SolverResources` 集中表达本次无连接日历事实 `calendar_inputs: CalendarInputs`、停机映射 `downtime_map`、资源池 `resource_pool`、派生元信息及 `optimizer_seed_version`；采用入口不构建 `SolverResources`，也不创建九元空值占位元组。

### 4.3 冗余模块与私有旁路清理清单

| 待清理目标 | 具体动作与去向 |
|---|---|
| [schedule_orchestrator.py](../../../core/services/scheduler/run/schedule_orchestrator.py) | 彻底删除；结果规范化与 `SummaryBuildContext` / `build_result_summary` 调用直接并入 [compute.py](../../../core/services/workbench/run/compute.py) |
| [input_effort.py:19](../../../core/services/workbench/run/input_effort.py#L19) (`saved_seed_efforts`) | 并入工时准备模块，完整保留其按历史正式版本读取保留安排工时需求的职责 |
| [candidate_adoption_persistence.py:7](../../../core/services/workbench/run/candidate_adoption_persistence.py#L7) 与 [trial/adoption_persistence.py:7](../../../core/services/workbench/trial/adoption_persistence.py#L7) | 删除两个 8 行纯转发文件；将其承担的审计来源、采用理由、声明操作人、实体回执字段及试调 `run_window`（[official_persistence.py:62](../../../core/services/workbench/plan/official_persistence.py#L62)）迁入对应 adoption 命令后直接调用 `persist_official_plan_in_tx` |
| [trial/adoption_input.py:18](../../../core/services/workbench/trial/adoption_input.py#L18) | 改为调用公开的 `prepare_business_input`（传入已准备的 `held`），删除穿透调用 `input.py` 私有 `_prepare_facts` 的旁路 |
| [schedule_execution_persistence_guard.py:95](../../../core/services/scheduler/run/schedule_execution_persistence_guard.py#L95) | 直接退役旧平铺扫描守卫（详见第 6.2 节） |

### 4.4 单一日历引擎 `CalendarEngine(CalendarInputs)`

删除 `CalendarService` 的计算转发方法、删除 [SnapshotCalendarEngine](../../../core/services/capacity/plan_calendar_engine.py#L9) 与 [_SavedCalendarEngine](../../../core/services/workbench/facts/archived_calendar.py#L32) 两个子类，并随不可变 `CalendarInputs` 断点证书一起退役 [core/infrastructure/connection_guards.py:53](../../../core/infrastructure/connection_guards.py#L53) 的 `connection_snapshot_metadata`。
排产、产能、报表、归档与月历读取统一使用唯一纯计算引擎 `CalendarEngine(CalendarInputs)`；日历写维护仍归属 `CalendarAdmin / CalendarNormalizationContext`。

**单一日历引擎必须守住的 4 条细节契约**：

1. **Checkpoint 证书注册**：
   目前 `CalendarService`（[service.py:79](../../../core/services/scheduler/calendar/service.py#L79)、[:96](../../../core/services/scheduler/calendar/service.py#L96)）注册了 `register_checkpoint_calendar`，而消费者（[checkpoint_calendar.py:16](../../../core/algorithm_runtime/checkpoint_calendar.py#L16)）严格按 `type(calendar)` 查表。迁移时必须改为在 `CalendarEngine` 上注册基于固定 `CalendarInputs` 的断点证书，避免触发 `decode_checkpoint_unsupported_calendar`。断点证书仅在搜索首次捕获/恢复断点时按 [calendar_checkpoint_repo.py:15](../../../data/repositories/calendar_checkpoint_repo.py#L15) 的业务含义从 `CalendarInputs` 生成一次不可变结构，普通解码不构造。

2. **缺表按实际依赖惰性解释**：
   `CalendarInputs` 显式区分缺表（`None`）与空表（`()`）。个人显式覆盖命中时不读取全局/班次表；轮休保持 `available + [] + 0`；只有实际计算走到缺失表的日期或人员时，才抛出携带 `missing_fact / policy_date` 的结构化异常，由 [archived_calendar.py:59](../../../core/services/workbench/facts/archived_calendar.py#L59) 转为局部 `unavailable`（完整保留其他 `known_windows`，见 [test_archived_calendar.py:193](../../../tests/workbench/test_archived_calendar.py#L193)）。

3. **`provenance()` 与 `CalendarProjection`（[calendar_reading.py:20](../../../core/services/workbench/resource/calendar_reading.py#L20)、[calendars.py:128](../../../core/services/workbench/resource/calendars.py#L128)）**：
   保留 `provenance()`；月历跨夜合计所需的次月 1 日通过显式扩展视图读取，按日惰性解析。次月 1 日坏数据只让月合计为 `None`，绝不阻断本月日格正常显示（见 [test_calendar_periods.py:445](../../../tests/calendar_maintenance/test_calendar_periods.py#L445)）；个人月历“未设置”保持 `explicit=False`。

4. **跨夜尾巴分段计算同源**：
   提取消费已解析 `DayPolicy` 的“今日安排覆盖昨日跨夜尾巴”纯分段函数，同时服务排产引擎（[engine.py:313](../../../core/services/scheduler/calendar/engine.py#L313)）与容量投影（[plan_calendar_windows.py:33](../../../core/services/capacity/plan_calendar_windows.py#L33)），消除两处镜像分段逻辑。

日历事实准备提供可独立复用的 `prepare_calendar_inputs(facts, operator_ids) -> CalendarInputs`。正式采用与试调验证只为被检验安排与保护种子涉及的人员范围准备 `CalendarInputs` 并构造 `CalendarEngine`，不调用 `prepare_solver_resources`、不建立自动选择资源池。

## 5. Python 3.8 接口草图

以下是目标签名与核心具名结果（遵循 Python 3.8 类型契约），实施时直接替换旧结构，不保留空壳转发层。

```python
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, FrozenSet, Mapping, Optional, Sequence, Set, Tuple

@dataclass(frozen=True)
class ExecutionGuardState:
    execution_facts: Mapping[int, "ExecutionFact"]
    execution_resource_segments: Mapping[Tuple[str, str], Sequence[Tuple[datetime, Optional[datetime], int]]]
    execution_completed_op_ids: Set[int]
    execution_seed_results: Sequence[Dict[str, Any]]
    execution_snapshot_revision: str
    execution_snapshot_op_ids: Tuple[int, ...]
    execution_snapshot_op_count: int

@dataclass(frozen=True)
class SeedPreparation:
    frozen_op_ids: Set[int]
    seed_results: Sequence[Dict[str, Any]]
    freeze_meta: Mapping[str, Any]
    to_schedule: Sequence["OpForScheduleAlgo"]

@dataclass(frozen=True)
class CalendarInputs:
    operator_ids: FrozenSet[str]
    defaults: Optional[Sequence[Mapping[str, Any]]]
    public_days: Optional[Sequence[Mapping[str, Any]]]
    personal_days: Optional[Sequence[Mapping[str, Any]]]
    operator_profiles: Optional[Sequence[Mapping[str, Any]]]
    shift_profiles: Optional[Sequence[Mapping[str, Any]]]
    shift_patterns: Optional[Sequence[Mapping[str, Any]]]
    default_periods: Optional[Sequence[Mapping[str, Any]]]
    decoded_periods: Mapping[str, Sequence[Mapping[str, Any]]]

@dataclass(frozen=True)
class SolverResources:
    calendar_inputs: CalendarInputs
    downtime_map: Mapping[str, Sequence[Tuple[datetime, datetime]]]
    resource_pool: Optional[Mapping[str, Any]]
    downtime_meta: Mapping[str, Any]
    resource_pool_meta: Mapping[str, Any]
    optimizer_seed_version: int

@dataclass(frozen=True)
class SolverInput:
    batches: Mapping[str, "Batch"]
    algo_ops: Sequence["OpForScheduleAlgo"]
    to_schedule: Sequence["OpForScheduleAlgo"]
    config: "ScheduleConfigSnapshot"
    start: datetime
    end_date: date
    readiness_gate_enabled: bool
    seeds: SeedPreparation
    predecessors: Mapping[int, Sequence[int]]

@dataclass(frozen=True)
class PreparedBusinessInput:
    settings: Mapping[str, Any]
    facts: "PreflightFacts"
    batches: Mapping[str, "Batch"]
    operations: Sequence["BatchOperation"]
    algo_ops: Sequence["OpForScheduleAlgo"]
    config: "ScheduleConfigSnapshot"
    start: datetime
    end_date: date
    readiness_gate_enabled: bool
    execution_guard: ExecutionGuardState
    seeds: SeedPreparation
    piece_scope: Optional["PieceScope"]
    predecessors: Mapping[int, Sequence[int]]
    dispositions: Sequence[Mapping[str, Any]]
    baseline_version: int
    latest_plan_rows: Mapping[int, Mapping[str, Any]]
    allowed_op_ids: Set[int]
    missing_internal_resource_op_ids: Set[int]
    operation_sources: Mapping[int, str]
    operation_efforts: Sequence["OperationEffort"]

@dataclass(frozen=True)
class ScheduleValidationOutcome:
    validated_payload: "ValidatedSchedulePayload"
    resolved_intervals: Mapping[int, Tuple[datetime, datetime]]
    resource_segments: Mapping[Tuple[str, str], Sequence[Tuple[datetime, Optional[datetime], int]]]
    issues: Tuple[Dict[str, Any], ...]

def prepare_business_input(
    facts: "PreflightFacts",
    settings: Mapping[str, Any],
    *,
    dispositions: Sequence[Mapping[str, Any]],
    held: Optional["HeldArrangements"] = None,
    include_efforts: bool = True,
) -> PreparedBusinessInput: ...

def prepare_solver_input(business: PreparedBusinessInput) -> SolverInput: ...

def prepare_calendar_inputs(
    facts: "PreflightFacts", operator_ids: FrozenSet[str],
) -> CalendarInputs: ...

def prepare_solver_resources(
    business: PreparedBusinessInput, solver_input: SolverInput,
) -> SolverResources: ...

def evaluate_schedule_constraints(
    business: PreparedBusinessInput,
    calendar: "CalendarEngine",
    arrangements: Sequence[Mapping[str, Any]],
) -> ScheduleValidationOutcome: ...

def run_candidate_comparison(
    solver_input: SolverInput, resources: SolverResources,
) -> "CandidateComparisonOutcome": ...
```

## 6. 全链路关键收敛设计

### 6.1 预检（Preflight）与受理（Admission）准备链收敛

针对预检与受理准备链的三处现存病灶，按以下方式在源头收敛：

1. **进门先验轻量指纹，杜绝“先算后扔”**：
   改造 [web/routes/workbench/preflight.py:54-56](../../../web/routes/workbench/preflight.py#L54-L56)，在进入重型 `evaluate_prepared` 之前先调用轻量修订指纹核验（`_require_current`）；`input_ref` 过期时直接返回 `409 snapshot_stale`，不再白跑整套预检评估。
2. **拆开“内部不可变业务评估结果”与“公开预检 DTO 投影”**：
   禁止 [core/services/workbench/run/preflight_result.py:76-78](../../../core/services/workbench/run/preflight_result.py#L76-L78) 在构造公开 DTO 时原地执行 `row.pop("op_id", None)` 和 `row.pop("external_execution_cycle", None)`，同时禁止跨阶段在 `PreparedPreflight` / `PreflightFacts` 上原地回填属性。内部评估行保持只读完整结构，公开预检响应在出口投影时按需选取对外字段，使同作用域内受理可直接复用评估产物与 `held_arrangements`（[input_admission.py:32](../../../core/services/workbench/run/input_admission.py#L32)）。
3. **严守预检与受理/计算的真实业务口径边界**：
   - **报工投影范围**：预检初始只投影**选中工序**；受理（[jobs_facts.py:7](../../../core/services/workbench/run/jobs_facts.py#L7)、[input_execution.py:35](../../../core/services/workbench/run/input_execution.py#L35)）必须扩展为 **选中工序 ∪ 上版正式计划全部工序**，并在复用预检结果时只增量补查未选工序的缺失报工投影。
   - **冲突报告 vs 严格准入**：预检收集 `external_cycle_actuals_differ` 等全量 blocker 供界面一次性展示；受理与计算要求严格证明无冲突。
   - **跨请求/跨午夜边界**：后台 Worker 必须消费受理归档保存的 `dispositions`（[test_run_jobs_atomic.py:31](../../../tests/workbench/test_run_jobs_atomic.py#L31)），绝不在后台重调挂钟时间重算当天物料分类。

### 6.2 候选、分件与试调（Trial）排程约束验证统一

消除 [trial/adoption_validation.py:48-63](../../../core/services/workbench/trial/adoption_validation.py#L48-L63) 同事务双跑全量校验，以及 [candidate_adoption_constraints.py](../../../core/services/workbench/run/candidate_adoption_constraints.py) 与 [piece_adoption.py:121-189](../../../core/services/workbench/run/piece_adoption.py#L121-L189) 复制粘贴两套逐行验证的问题：

1. **提取唯一的排程约束验证核心（`evaluate_schedule_constraints` → `ScheduleValidationOutcome`）**：
   一次扫描产出一个结构化的“安排约束结果”（含已解析区间 `resolved_intervals`、资源占用 `resource_segments`、违规项 `issues` 与有效 `validated_payload`），统一覆盖：
   - 保护种子原样保持（`seeds`）；
   - 显式前驱 `predecessors` 与分件树范围（`piece_scope`）；
   - 资源存在性与人员资格、机台/人员时间重叠；
   - **范围外正式安排占用、范围外实际报工占用、多资源多段占用与释放时间未知占用**（见 [trial/constraints.py:157](../../../core/services/workbench/trial/constraints.py#L157)、[test_trial_validation.py:301](../../../tests/workbench/test_trial_validation.py#L301)）；
   - 设备停机避让、批次齐套日、内制日历时长 `estimate_internal_slot`、外协周期一致性。

2. **保留三类消费者的真实业务边界**：
   - **试调草稿与方案保存**（[trial/validation.py:94](../../../core/services/workbench/trial/validation.py#L94)、[trial/service.py:151](../../../core/services/workbench/trial/service.py#L151)）：允许保存含冲突草稿，消费结构化 `issues`（完整保留 [adoption_validation.py:96](../../../core/services/workbench/trial/adoption_validation.py#L96) 从 `source_task_ref` 到当前 `task_ref` 的映射）、原始/当前 interval 与多段占用供页面和容量展示。**试调正式采用在同一写事务内直接消费该完整核验结果**，不再二次重建 `CandidateRunInput` 重跑第二遍；同时删掉 [adoption_validation.py:85](../../../core/services/workbench/trial/adoption_validation.py#L85) 已被父类捕获的 `PieceAdoptionBlocked` 死分支。
   - **候选发布**（[compute.py:50](../../../core/services/workbench/run/compute.py#L50)、[piece_adoption.py:109](../../../core/services/workbench/run/piece_adoption.py#L109)、[test_piece_chain_boundaries.py:90](../../../tests/workbench/test_piece_chain_boundaries.py#L90)）：允许非空、闭合的部分候选（partial），不套用正式采用的完整范围要求；验证通过的 `validated_payload`（[compute_validation.py:20](../../../core/services/workbench/run/compute_validation.py#L20)）直接复用于摘要构造与归档保存。
   - **正式采用（普通批次与分件批次）**：要求覆盖完整范围（扣除合法待料工序）并覆盖已有正式安排（`_require_official_scope`）。普通批次与分件批次的错误码差异（`candidate_*` vs `piece_*`，如 `piece_external_duration_conflict`，见 [candidate_adoption_constraints.py:102](../../../core/services/workbench/run/candidate_adoption_constraints.py#L102) vs [piece_adoption.py:132](../../../core/services/workbench/run/piece_adoption.py#L132)）通过出口薄映射保留；已完工历史工序只核对资源身份可辨认，不按今日资格或今日齐套重算。

3. **直接退役旧平铺扫描守卫 [schedule_execution_persistence_guard.py:95](../../../core/services/scheduler/run/schedule_execution_persistence_guard.py#L95)**：
   该守卫按 `(batch_id, seq)` 线性扫描下游，而账本准入、实际种子保持和显式前驱 `predecessors` 已由业务准备阶段与共同验证核心完整覆盖，无需再留一层平铺重复扫描。

### 6.3 直接编排、图准备与结果发布

`compute_candidate_run` 直接表达下列顺序，删除 `schedule_orchestrator.py`、`ScheduleOrchestrationOutcome` 和 `_run_plan_selection`：
1. 工作台在只读计算快照中调用 `prepare_business_input` 取得业务输入、保护种子与 `operation_efforts`，再显式调用 `prepare_solver_input` 与 `prepare_solver_resources`。
2. 直接调用 `run_candidate_comparison`；scheduler 从 `SolverResources.calendar_inputs` 创建纯 `CalendarEngine`，在预算内完成图准备、`NativeSchedulePreparation` 与共享搜索，全程零数据库访问。
3. 对实际发布的候选逐个调用共同约束验证；选中候选的验证结果直接供 `SummaryBuildContext / build_result_summary` 和 `prepare_run_result` 复用。
4. [分件图准备](../../../core/services/workbench/run/compute_graph.py#L27)与[普通图准备](../../../core/services/scheduler/run/schedule_graph_report.py#L62)归入 scheduler 统一图准备机制（消费 `SolverInput.algo_ops` 与显式 `predecessors`），删除 `partial(compare, prepare_graph_fn=...)` 回调装配；图准备保持在 `run_candidate_comparison` 创建预算之后执行。

## 7. 搜索与算法热路径

保留 `SharedSearch / SharedScheduleArchive / SharedDecodeSession` 的分工：动作轮转、共同安排与评分、实际解码账本分别拥有一份状态。
[shared_optimizer.py:150](../../../core/services/scheduler/run/schedule_shared_optimizer.py#L150) 的一次评分准备和 [shared_decode.py:119](../../../core/services/scheduler/run/optimizer/shared_decode.py#L119) 的一次 native preparation 继续使用。
[scheduler.py:50](../../../core/algorithms/greedy/scheduler.py#L50) 继续只解码已准备输入；候选参数只表达批序、资源变化、图优先级与断点请求等真正变化。

性能约束：
- 输入和归档只在真实边界解析一次；解码循环不再 JSON 编解码、扫描数据库或校验受控 DTO。
- 候选复用由实际有效请求身份决定，不新增整份输入内容哈希、重复内容证明或每轮深拷贝。
- 同一候选的 slot 评分与最终落安排继续共用已计算结果，保留时间线变更后证据失效规则。
- 只在真实捕获或恢复断点时准备断点证书，不为普通完整解码额外扫描一遍相同内容。

## 8. 旧入口到目标入口的统一迁移表

| 当前入口/结构 | 目标动作 | 必须一起迁移的消费者 |
|---|---|---|
| `CandidateRunInput(ScheduleRunInput)` | 拆分为 `PreparedBusinessInput` 与仅计算构造的 `SolverInput`，删除继承关系 | worker、受理、候选/试调采用、验证、结果准备及相应 fixture |
| `prepare_candidate_run_input(..., for_adoption=...)` | 改为 `prepare_business_input`；求解资源由计算路径显式另取，删除模式开关 | `input_admission.py`、`compute.py`、`candidate_adoption_validation.py`、`trial/adoption_input.py` |
| `trial/adoption_input.py:18` 穿透调 `_prepare_facts` | 改为调用公开 `prepare_business_input(..., held=held, include_efforts=False)` | 试调采用准备与验证链 |
| `build_runtime` 九元位置元组 | 保护种子（含 `to_schedule`）归 `SeedPreparation`，资源归 `SolverResources`，删空占位元组 | 输入组装、采用复核、资源/种子相关测试 |
| `preflight.py:54` 后置指纹核验与 `preflight_result.py:76` 原地 `pop` | 进门先验 `_require_current`；拆开内部不可变评估结果与公开 DTO 投影 | 预检路由、预检服务、受理复用链 |
| `candidate_adoption_constraints.py` + `piece_adoption.py` + `trial/adoption_validation.py` 双跑 | 收敛为单一 `evaluate_schedule_constraints -> ScheduleValidationOutcome` 核心，三类消费者按边界消费 | 候选验证、普通采用、分件采用、试调保存与试调采用（删除 `PieceAdoptionBlocked` 死分支） |
| `schedule_execution_persistence_guard.py:95` | 直接退役线性下游扫描守卫 | 采用与持久化校验调用点 |
| `candidate_adoption_persistence.py` 与 `trial/adoption_persistence.py` | 删除两个 8 行纯转发文件，参数组装并入 adoption 命令后直调 `persist_official_plan_in_tx` | 候选采用与试调采用命令 |
| `CalendarService` 计算转发、`SnapshotCalendarEngine`、`_SavedCalendarEngine`、`connection_snapshot_metadata` | 统一为 `CalendarEngine(CalendarInputs)`，在 `CalendarEngine` 注册断点证书，提取跨夜尾巴同源分段函数 | 排产、产能、报表、归档、月历读取、checkpoint 证书与回滚契约 |
| `orchestrate_schedule_run / _run_plan_selection` 与 `compute_graph.piece_graph_preparer` | 删除 `schedule_orchestrator.py`，结果组装并入 `compute.py`；普通/分件图准备在 scheduler 内统一 | `compute.py`、candidate runner、shared optimizer 与图准备预算测试 |

## 9. 不变量与既有验证入口

必须保留：运行领取/结果保存的原子性；落盘归档 JSON 格式 0 变更；受理分类不在 worker 重算；保护安排不变；正式采用覆盖完整范围；微秒日期、分件前置链、外协合并周期、零工时点事件及多段资源占用语义不变；离线 Win7 x64 / Python 3.8 产品约束。

| 验证职责 | 现有证据入口 | 本次迁移应证明的结果 |
|---|---|---|
| capture 复用与最终复核 | [test_run_jobs_atomic.py:421](../../../tests/workbench/test_run_jobs_atomic.py#L421) | 计算副本与最终事务各一份 capture，每张表各作用域只读一次 |
| 受理分类、跨午夜一致 | [test_run_jobs_atomic.py:31](../../../tests/workbench/test_run_jobs_atomic.py#L31) | Worker 消费受理归档 `dispositions`，不重分类 |
| 日历、停机、共同资源 | [test_run_compute_integration.py:37](../../../tests/workbench/test_run_compute_integration.py#L37) | 夜班、效率、停机与合并外协安排不变 |
| 候选采用原子性与 capture | [test_run_candidate_adoption_atomic.py:60](../../../tests/workbench/test_run_candidate_adoption_atomic.py#L60) | 采用不构造 `SolverInput/SolverResources`，仍完整执行种子准入与约束复核 |
| 分件部分候选发布与完整采用边界 | [test_piece_chain_boundaries.py:90](../../../tests/workbench/test_piece_chain_boundaries.py#L90) 与 [test_piece_chain_end_to_end.py:29](../../../tests/workbench/test_piece_chain_end_to_end.py#L29) | 候选发布允许闭合 partial，正式采用强制完整范围并保留 `piece_*` 错误码映射 |
| 试调多段占用与同事务单次校验 | [test_trial_validation.py:301](../../../tests/workbench/test_trial_validation.py#L301) | 范围外报工、多资源多段占用、未知释放时间准确拦截；试调采用同事务只验一次 |
| 共享账本、评分与断点恢复 | [test_shared_optimizer.py:669](../../../tests/candidate/test_shared_optimizer.py#L669)、[test_sgs_internal_scoring_matches_execution.py:49](../../../tests/algorithm/test_sgs_internal_scoring_matches_execution.py#L49)、[test_decode_checkpoint_content_evidence.py:467](../../../tests/algorithm/test_decode_checkpoint_content_evidence.py#L467) | `CalendarEngine` 断点证书注册生效、回滚前后证据隔离、搜索阶段零数据库访问 |
| 归档日历局部缺表与月历次月容错 | [test_archived_calendar.py:193](../../../tests/workbench/test_archived_calendar.py#L193) 与 [test_calendar_periods.py:445](../../../tests/calendar_maintenance/test_calendar_periods.py#L445) | 缺表按实际依赖惰性转局部 `unavailable`；次月 1 日坏数据仅置月合计为 `None` |

最终验证沿[质量治理入口](../../../开发文档/README.md#质量治理入口)运行适用门禁；定点、完整门禁和 clean proof 分别按实际范围报告。

## 10. 实施分工、合并条件与结束标准

1. **阶段一：预检与业务准备收敛**：修复预检前置指纹核验与原地 `pop`，落地 `PreparedBusinessInput`、`ExecutionGuardState`、`SeedPreparation`（含 `to_schedule`）与工时准备合并，迁移受理、计算、候选采用、试调采用准备入口。
2. **阶段二：单一日历引擎收敛**：落地 `CalendarEngine(CalendarInputs)`，完成 `CalendarEngine` 断点证书注册、缺表惰性解释、`provenance()` 扩展视图与跨夜尾巴同源分段，删除 `SnapshotCalendarEngine`、`_SavedCalendarEngine`、`CalendarService` 计算转发及 `connection_snapshot_metadata`。
3. **阶段三：共同排程约束验证与持久化收口**：落地 `evaluate_schedule_constraints -> ScheduleValidationOutcome`，统一候选发布、普通/分件采用与试调保存/采用验证，消除试调采用同事务双跑，退役 `schedule_execution_persistence_guard.py` 及两个 8 行 persistence 转发文件。
4. **阶段四：求解输入与直接编排收口**：落地 `SolverInput` 与 `SolverResources`，删除 `schedule_orchestrator.py` 与 `piece_graph_preparer` 回调装配，完成全量测试与门禁验收。

结束标准是“预检到采用一条连贯主链、两份核心结果贯通、单一日历引擎零连接计算、旧转发壳与重复校验全部清零、持久化归档格式 0 变更”。
