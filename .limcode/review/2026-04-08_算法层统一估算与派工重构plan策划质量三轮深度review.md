# 算法层统一估算与派工重构plan策划质量三轮深度review
- 日期: 2026-04-08
- 概述: 聚焦审查 plan 本身的策划质量、边界控制、任务拆分、风险控制与验收口径；必要时只做基线事实核对，不评判当前实现成果。
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# 算法层统一估算与派工重构plan策划质量三轮深度review

- 日期：2026-04-08
- 范围：仅审查 `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md` 的策划质量，重点看目标定义、边界约束、引用链、任务拆分、风险控制、暂停门槛、验收标准是否严谨。
- 说明：本轮不以“当前实现是否完成”为中心；如需核对 plan 中“经代码核实”的前提，只做最小必要的基线事实核验。

## 初始结论

待审查。先从三个层面展开：
1. plan 的目标、范围、非目标与约束是否自洽
2. plan 对基线事实、引用链、函数变量的描述是否准确
3. plan 的任务拆分、测试顺序、暂停门槛与完成判定是否足够可执行

## 评审摘要

- 当前状态: 已完成
- 已审模块: .limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md, core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_input_collector.py, core/services/scheduler/schedule_orchestrator.py, core/services/scheduler/schedule_optimizer.py, core/algorithms/__init__.py, core/algorithms/sort_strategies.py, core/algorithms/greedy/scheduler.py, core/algorithms/greedy/auto_assign.py, core/algorithms/greedy/dispatch/sgs.py, core/algorithms/greedy/dispatch/batch_order.py, core/algorithms/greedy/downtime.py, core/services/scheduler/resource_pool_builder.py, core/services/scheduler/schedule_optimizer_steps.py, core/services/common/strict_parse.py, core/algorithms/evaluation.py, core/algorithms/dispatch_rules.py, core/algorithms/ortools_bottleneck.py, tests/smoke_phase10_sgs_auto_assign.py, tests/regression_sgs_scoring_machine_operator_id_type_safe.py, tests/regression_dispatch_blocking_consistency.py, tests/regression_scheduler_nonfinite_efficiency_fallback.py
- 当前进度: 已记录 3 个里程碑；最新：round3-dates-optimizer-and-acceptance-gates
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 4
- 问题严重级别分布: 高 0 / 中 3 / 低 1
- 最新结论: 该 plan 不是空泛任务单，而是建立在真实主链、真实函数边界与现有回归事实上形成的可执行 plan。优点主要有四点：第一，目标聚焦，没有把范围扩散到 `schema.sql`、报表层日期函数或新的平行算法模式；第二，公开边界约束与 direct-call raw 输入兼容约束写得很清楚，能避免“重构顺手收紧入口”这类隐性破坏；第三，`internal_slot.py` 与 `dispatch/runtime_state.py` 的拆分方向总体简洁，确实对应了当前代码里的两组重复热点；第四，任务 4、任务 5 对日期事实源与优化器重复工作的识别是准确的，完成判定也覆盖到了关键语义。 但该 plan 还没有达到“可以零歧义直接开工”的程度，至少需要先修订四处策划级问题：1）`created_at` strict 边界仍停在整轮 `keys` 粒度，improve 模式下仍可能在非 FIFO 尝试提前硬失败；2）`validate_internal_hours()` 被要求把属性读取和数值转换失败统一改写为 `ValueError`，这和 plan 自己“真正的程序错误必须显式暴露”的原则不完全一致；3）停机片段规范化落点写成“公开入口或统一估算入口”过于宽泛，容易把一次性兼容工作放进高频估算路径，反向制造重复开销；4）性能暂停门槛依赖单次墙钟耗时，而当前 smoke 脚本本身包含较重的环境噪声来源，最好先补测量归一规则。 综合判断：这份 plan 的骨架是好的，方向也基本正确，我不建议推翻重写；但我建议先按上述四点把 text 再收紧一轮，再进入实现。
- 下一步建议: 先修订 `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md` 中 `created_at` strict 启用粒度、`validate_internal_hours()` 异常边界、停机规范化落点与性能暂停口径四处文字，再基于修订版进入实现。
- 总体结论: 有条件通过

## 评审发现

### created_at 严格边界启用粒度过粗

- ID: plan-created-at-strict-granularity
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: round1-chain-and-boundaries
- 说明:

  plan 已正确识别不能再用 `valid_strategies` 这种默认全量候选集去提前触发 `created_at` 的 strict 校验，但当前策划仍把启用条件放在整轮 `keys` 上。对 `optimize_schedule()` 的 improve 模式来说，`keys` 代表本轮准备探索的全量策略集合，而不是单次实际 `build_order()` 所用的当前策略。这样一来，只要 `keys` 含 `fifo`，就可能在非 FIFO 尝试上也提前对 `created_at` 做 strict 解析，和 plan 自身“仅在 FIFO 相关排序路径真正消费该字段时才允许 strict 硬失败”的目标仍不完全一致。更稳妥的策划应把 strict 启用点收紧到单次策略级，例如放到 `_build_order()` 或等价的按当前 `strategy0` 构造排序输入处。
- 建议:

  把 `created_at` 的 strict 启用条件从“本轮 `keys` 是否含 `fifo`”再收紧一层，改成“当前单次实际构造排序器的策略是否为 `fifo`”，并在 plan 的测试说明中显式补一条 improve 模式下‘全局策略集含 fifo、但当前尝试非 fifo’的断言。
- 证据:
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:483-487#任务 4 / 步骤 4`
  - `core/services/scheduler/schedule_optimizer.py:359-399#optimize_schedule`
  - `core/algorithms/sort_strategies.py:117-125#FIFOStrategy.sort`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/algorithms/__init__.py`
  - `core/algorithms/sort_strategies.py`
  - `tests/regression_sgs_scoring_machine_operator_id_type_safe.py`
  - `tests/regression_dispatch_blocking_consistency.py`

### validate_internal_hours 异常归一范围过宽

- ID: plan-validate-internal-hours-broad-except
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: round2-tasks1-to-3-and-module-split
- 说明:

  plan 在总原则里明确要求“真正的程序错误必须显式暴露”，但在 `validate_internal_hours()` 的细化步骤里，又要求用局部 `try/except` 把“属性读取与 `float(...)` 转换失败”统一重写为带 `repr` 的 `ValueError`。由于这个共享入口会同时服务 `_schedule_internal()`、`auto_assign_internal_resources()`、`dispatch_sgs()` 的采样与评分路径，这种写法会把对象属性实现异常、访问期程序错误与真正的 raw 数值坏值混到同一个业务异常口径里，仍然带有明显的过度防御色彩。plan 如果要保持 direct-call 的缺字段 / `None` / 空串 / `False` 兼容边界，并不需要把任意属性访问异常都业务化。
- 建议:

  把 `validate_internal_hours()` 的兼容范围缩成“显式保留的 raw 值边界 + 标量数值转换错误”，不要把任意属性读取异常统一重写成 `ValueError`；对对象访问期的非预期异常，应按程序错误直接上浮。
- 证据:
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:80-85#实施约束`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:215-219#任务 1 / 步骤 3`
  - `core/algorithms/greedy/scheduler.py:476-485#GreedyScheduler._schedule_internal`
  - `core/algorithms/greedy/auto_assign.py:102-112#auto_assign_internal_resources`
  - `tests/regression_sgs_scoring_machine_operator_id_type_safe.py:61-89#_build_case`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/dispatch/batch_order.py`
  - `core/algorithms/greedy/downtime.py`
  - `core/services/scheduler/resource_pool_builder.py`
  - `tests/regression_sgs_scoring_machine_operator_id_type_safe.py`
  - `tests/regression_scheduler_nonfinite_efficiency_fallback.py`

### 停机规范化落点不唯一

- ID: plan-downtime-normalization-placement-ambiguous
- 严重级别: 中
- 分类: 性能
- 跟踪状态: 开放
- 相关里程碑: round2-tasks1-to-3-and-module-split
- 说明:

  plan 对有序停机片段的前置规范化给出了“公开入口或统一估算入口”两个落点，但当前服务主链经 `load_machine_downtimes()` 与 `extend_downtime_map_for_resource_pool()` 已会对停机片段排序，真正需要补的一次性兼容主要是 direct-call 给 `GreedyScheduler.schedule()` 传入无序 `machine_downtimes` 的场景。若实现者把规范化放到 `estimate_internal_slot()` 这一高频入口，`auto_assign_internal_resources()` 与 `dispatch_sgs()` 评分阶段都可能对同一 `machine_downtimes[mid]` 反复排序或清洗，直接抵消任务 2 与任务 5 试图争取的性能收益。
- 建议:

  在 plan 里把规范化落点固定为 `GreedyScheduler.schedule()` 的一次性入口标准化，并让 `internal_slot.py`、`auto_assign.py`、`dispatch_sgs.py` 都基于“输入已按入口规范化”的前提工作。
- 证据:
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:97-99#实施约束`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:397-398#任务 3 / 步骤 3`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:612-613#完成判定`
  - `core/services/scheduler/resource_pool_builder.py:151-163#load_machine_downtimes`
  - `core/services/scheduler/resource_pool_builder.py:298-310#extend_downtime_map_for_resource_pool`
  - `core/algorithms/greedy/scheduler.py:506-532#GreedyScheduler._schedule_internal`
  - `core/algorithms/greedy/auto_assign.py:179-203#auto_assign_internal_resources`
  - `core/algorithms/greedy/dispatch/sgs.py:279-333#dispatch_sgs`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/dispatch/batch_order.py`
  - `core/algorithms/greedy/downtime.py`
  - `core/services/scheduler/resource_pool_builder.py`
  - `tests/regression_sgs_scoring_machine_operator_id_type_safe.py`
  - `tests/regression_scheduler_nonfinite_efficiency_fallback.py`

### 性能暂停门槛缺少测量归一规则

- ID: plan-performance-gate-not-normalized
- 严重级别: 低
- 分类: 性能
- 跟踪状态: 开放
- 相关里程碑: round3-dates-optimizer-and-acceptance-gates
- 说明:

  plan 把 `smoke_phase10_sgs_auto_assign.py` 与未来大资源池基准的单次 `总耗时` 变化直接作为 `30%` 暂停阈值，但现有 `smoke_phase10_sgs_auto_assign.py` 本身就包含临时目录创建、测试数据库初始化、建表、插数、配置切换和多轮服务调用，墙钟时间天然容易受机器负载与文件系统抖动影响。若没有最少重复次数、预热、使用中位数或明确的人工判读规则，这个阈值更适合作为“需要进一步解释”的提示，而不适合作为硬暂停门槛。
- 建议:

  把 `30%` 阈值改成带测量归一规则的口径，例如固定重复次数后取中位数，或在 plan 中明确“该阈值仅用于提示人工复核，不作为单次运行即可触发的硬暂停条件”。
- 证据:
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:550-566#任务 5 / 步骤 6`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:574-576#执行留痕与暂停门槛 / 任务 2`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:583-585#执行留痕与暂停门槛 / 任务 5`
  - `tests/smoke_phase10_sgs_auto_assign.py:46-57#main`
  - `tests/smoke_phase10_sgs_auto_assign.py:142-193#main`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/common/strict_parse.py`
  - `core/algorithms/evaluation.py`
  - `core/algorithms/dispatch_rules.py`
  - `core/algorithms/ortools_bottleneck.py`
  - `tests/smoke_phase10_sgs_auto_assign.py`

## 评审里程碑

### round1-chain-and-boundaries · 第一轮：目标、公开边界与引用链自洽性审查

- 状态: 已完成
- 记录时间: 2026-04-08T05:11:27.426Z
- 已审模块: .limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md, core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_input_collector.py, core/services/scheduler/schedule_orchestrator.py, core/services/scheduler/schedule_optimizer.py, core/algorithms/__init__.py, core/algorithms/sort_strategies.py
- 摘要:

  本轮先只审查 plan 的目标定义、公开边界约束与引用链是否建立在真实基线上。核对后，`ScheduleService._run_schedule_impl()` → `collect_schedule_run_input()` → `orchestrate_schedule_run()` → `optimize_schedule()` → `GreedyScheduler.schedule()` 的主链与 plan 描述一致；`core/algorithms/__init__.py` 仍导出 `GreedyScheduler`，而 `tests/regression_sgs_scoring_machine_operator_id_type_safe.py`、`tests/regression_dispatch_blocking_consistency.py` 这类回归确实直接喂 raw `op/batch` 给 `GreedyScheduler.schedule()`，所以 plan 把“不得静默收窄 direct-call raw 输入兼容边界”列为硬约束是合理的。整体上，plan 的目标、非目标、公开函数签名保护和任务顺序是自洽的，且没有把问题错误地下沉到服务边界外。但在任务 4 上仍存在一个策划粒度问题：plan 已意识到不能再用 `valid_strategies` 触发 `created_at` 的 strict 解析，却把启用条件停在整轮 `keys` 级别。对于 `optimize_schedule()` 的 improve 模式，`keys` 是本轮全量策略集合，而不是单次实际 `build_order()` 的当前策略；若 `keys` 里包含 `fifo`，就可能在非 FIFO 尝试也提前对 `created_at` 做 strict 解析，从而与 plan 自己提出的“只在 FIFO 相关排序路径真正消费该字段时才允许 strict 硬失败”仍有一层偏差。
- 结论:

  主链、公开边界与 direct-call 兼容约束的策划基础扎实；但 `created_at` 的 strict 启用粒度还需要从整轮 `keys` 再收紧到单次实际排序策略。
- 证据:
  - `core/services/scheduler/schedule_service.py:262-289#ScheduleService._run_schedule_impl`
  - `core/services/scheduler/schedule_input_collector.py:387-421#collect_schedule_run_input`
  - `core/services/scheduler/schedule_orchestrator.py:113-128#orchestrate_schedule_run`
  - `core/services/scheduler/schedule_optimizer.py:392-399#optimize_schedule`
  - `core/services/scheduler/schedule_optimizer.py:359-374#optimize_schedule`
  - `core/algorithms/sort_strategies.py:117-125#FIFOStrategy.sort`
  - `tests/regression_sgs_scoring_machine_operator_id_type_safe.py:109-131#main`
  - `tests/regression_dispatch_blocking_consistency.py:122-146#_run/main`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:483-487#任务 4 / 步骤 4`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/algorithms/__init__.py`
  - `core/algorithms/sort_strategies.py`
  - `tests/regression_sgs_scoring_machine_operator_id_type_safe.py`
  - `tests/regression_dispatch_blocking_consistency.py`
- 下一步建议:

  继续第二轮，集中审查任务 1~3、`internal_slot.py` / `runtime_state.py` 的职责边界，以及 plan 对异常语义和时间线有序化的约束是否存在自我冲突。
- 问题:
  - [中] 可维护性: created_at 严格边界启用粒度过粗

### round2-tasks1-to-3-and-module-split · 第二轮：任务 1~3、重复估算与运行期状态拆分审查

- 状态: 已完成
- 记录时间: 2026-04-08T05:12:18.413Z
- 已审模块: .limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md, core/algorithms/greedy/scheduler.py, core/algorithms/greedy/auto_assign.py, core/algorithms/greedy/dispatch/sgs.py, core/algorithms/greedy/dispatch/batch_order.py, core/algorithms/greedy/downtime.py, core/services/scheduler/resource_pool_builder.py
- 摘要:

  本轮聚焦 `#plan-t1`、`#plan-t2`、`#plan-t3` 是否真的贴着当前代码的重复点下刀，以及新文件 `core/algorithms/greedy/internal_slot.py`、`core/algorithms/greedy/dispatch/runtime_state.py` 是否必要且职责收口。基线核对后，`GreedyScheduler._schedule_internal()` 与 `auto_assign_internal_resources()` 当前确实共享同一类“工作时刻修正 → 三路时间线避让 → 效率折算”的估算骨架，而 `dispatch_sgs()` 内部评分仍保留另一套顺序链式近似路径；seed 预热、`dispatch_batch_order()`、`dispatch_sgs()` 也分别重复维护 `machine_busy_hours`、`operator_busy_hours`、`last_end_by_machine`、`last_op_type_by_machine`。因此，plan 选择把真实估算收口到 `internal_slot.py`、把成功后运行期状态更新收口到 `runtime_state.py`，总体上是简洁且必要的。与此同时，我也看到两处策划层面的风险：第一，plan 一方面要求“真正的程序错误必须显式暴露”，另一方面又要求 `validate_internal_hours()` 用局部 `try/except` 把“属性读取与 `float(...)` 转换失败”统一改写成 `ValueError`；这会把共享入口上的对象访问异常、属性实现异常等程序错误和真正的 raw 数值坏值混在一起。第二，plan 对有序停机片段的规范化落点给了“公开入口或统一估算入口”两个选项；在当前代码里，服务主链经 `resource_pool_builder.py` 已经会把停机区间排序，真正需要补的一次性规范化其实主要发生在 direct-call 入口。如果把规范化放到 `estimate_internal_slot()` 这一高频入口，`auto_assign` 与 `dispatch_sgs()` 评分阶段都可能对同一批停机片段反复排序，直接和任务 2、任务 5 的性能目标相冲突。
- 结论:

  任务 1~3 的拆分方向是对的，且新模块边界总体优雅；但 `validate_internal_hours()` 的异常归一范围和停机规范化落点都需要在 plan 上再收紧，否则很容易一边想去掉过度防御，一边又在共享入口重新引入。
- 证据:
  - `core/algorithms/greedy/scheduler.py:469-545#GreedyScheduler._schedule_internal`
  - `core/algorithms/greedy/auto_assign.py:102-223#auto_assign_internal_resources`
  - `core/algorithms/greedy/dispatch/sgs.py:227-341#dispatch_sgs`
  - `core/algorithms/greedy/dispatch/batch_order.py:86-106#dispatch_batch_order`
  - `core/algorithms/greedy/scheduler.py:264-304#GreedyScheduler.schedule`
  - `core/algorithms/greedy/downtime.py:20-57#occupy_resource/find_earliest_available_start`
  - `core/services/scheduler/resource_pool_builder.py:151-163#load_machine_downtimes`
  - `core/services/scheduler/resource_pool_builder.py:298-310#extend_downtime_map_for_resource_pool`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:80-85#实施约束`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:215-219#任务 1 / 步骤 3`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:97-99#实施约束`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:397-398#任务 3 / 步骤 3`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:612-613#完成判定`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/dispatch/batch_order.py`
  - `core/algorithms/greedy/downtime.py`
  - `core/services/scheduler/resource_pool_builder.py`
  - `tests/regression_sgs_scoring_machine_operator_id_type_safe.py`
  - `tests/regression_scheduler_nonfinite_efficiency_fallback.py`
- 下一步建议:

  继续第三轮，审查任务 4~5、性能门槛、暂停条件与完成判定是否真正可测、可执行且不被环境噪声误导。
- 问题:
  - [中] 可维护性: validate_internal_hours 异常归一范围过宽
  - [中] 性能: 停机规范化落点不唯一

### round3-dates-optimizer-and-acceptance-gates · 第三轮：任务 4~5、暂停门槛与完成判定可执行性审查

- 状态: 已完成
- 记录时间: 2026-04-08T05:12:54.953Z
- 已审模块: .limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_optimizer_steps.py, core/services/common/strict_parse.py, core/algorithms/evaluation.py, core/algorithms/dispatch_rules.py, core/algorithms/ortools_bottleneck.py, tests/smoke_phase10_sgs_auto_assign.py
- 摘要:

  本轮审查 `#plan-t4`、`#plan-t5`、`执行留痕与暂停门槛`、`完成判定` 是否真正可执行。基线核对显示，task 4 与 task 5 锚定的问题都是真问题：`core/algorithms/evaluation.py`、`core/algorithms/dispatch_rules.py`、`core/algorithms/ortools_bottleneck.py` 目前各自维护 `due_exclusive()` 副本；`core/services/common/strict_parse.py` 只有严格日期解析，没有严格日期时间解析；`schedule_optimizer.py` 既有本地 `_parse_datetime()`，又在 `keys` 计算前构造 `batch_for_sort`；`_run_multi_start()` 也确实在 `dispatch_rule` 内层重复 `build_order()`，`_run_local_search()` 则没有邻域去重。因此，plan 对 task 4 / task 5 的目标判断是准确的，且“先统一边界，再做微优化与回归”的顺序也合理。真正的策划弱点主要出现在执行门槛：plan 多处把 `smoke_phase10_sgs_auto_assign.py` 与未来新增的大资源池基准的单次 `总耗时` 变化，直接作为 `30%` 暂停阈值。问题在于，现有 `smoke_phase10_sgs_auto_assign.py` 本身就包含临时目录创建、测试数据库初始化、建表、插数、配置切换与多轮服务调用，墙钟时间受环境抖动影响很大；如果 plan 不再补一层“重复次数 / 中位数 / 预热 / 允许人工判读”的测量归一规则，这个阈值更像人工排查提示，而不像稳定的执行闸门。
- 结论:

  任务 4~5 的技术目标与验收方向总体成立，完成判定也覆盖到了核心语义；但性能暂停门槛还缺少测量归一规则，建议在 plan 中改成可重复、可解释的比较口径。
- 证据:
  - `core/algorithms/evaluation.py:38-58#_parse_due_date/_due_exclusive`
  - `core/algorithms/dispatch_rules.py:25-28#_due_exclusive`
  - `core/algorithms/ortools_bottleneck.py:23-42#_parse_due_date/_due_exclusive`
  - `core/services/common/strict_parse.py:85-103#parse_required_date/parse_optional_date`
  - `core/services/scheduler/schedule_optimizer.py:335-399#optimize_schedule`
  - `core/services/scheduler/schedule_optimizer_steps.py:300-335#_run_multi_start`
  - `core/services/scheduler/schedule_optimizer.py:127-181#_run_local_search`
  - `tests/smoke_phase10_sgs_auto_assign.py:46-57#main`
  - `tests/smoke_phase10_sgs_auto_assign.py:142-193#main`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:550-566#任务 5 / 步骤 6`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:574-576#执行留痕与暂停门槛 / 任务 2`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md:583-585#执行留痕与暂停门槛 / 任务 5`
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/common/strict_parse.py`
  - `core/algorithms/evaluation.py`
  - `core/algorithms/dispatch_rules.py`
  - `core/algorithms/ortools_bottleneck.py`
  - `tests/smoke_phase10_sgs_auto_assign.py`
- 下一步建议:

  综合三轮结论，给出最终 review 结论；建议在执行前先修订 `created_at` strict 粒度、`validate_internal_hours()` 异常边界、停机规范化落点与性能暂停口径。
- 问题:
  - [低] 性能: 性能暂停门槛缺少测量归一规则

## 最终结论

该 plan 不是空泛任务单，而是建立在真实主链、真实函数边界与现有回归事实上形成的可执行 plan。优点主要有四点：第一，目标聚焦，没有把范围扩散到 `schema.sql`、报表层日期函数或新的平行算法模式；第二，公开边界约束与 direct-call raw 输入兼容约束写得很清楚，能避免“重构顺手收紧入口”这类隐性破坏；第三，`internal_slot.py` 与 `dispatch/runtime_state.py` 的拆分方向总体简洁，确实对应了当前代码里的两组重复热点；第四，任务 4、任务 5 对日期事实源与优化器重复工作的识别是准确的，完成判定也覆盖到了关键语义。

但该 plan 还没有达到“可以零歧义直接开工”的程度，至少需要先修订四处策划级问题：1）`created_at` strict 边界仍停在整轮 `keys` 粒度，improve 模式下仍可能在非 FIFO 尝试提前硬失败；2）`validate_internal_hours()` 被要求把属性读取和数值转换失败统一改写为 `ValueError`，这和 plan 自己“真正的程序错误必须显式暴露”的原则不完全一致；3）停机片段规范化落点写成“公开入口或统一估算入口”过于宽泛，容易把一次性兼容工作放进高频估算路径，反向制造重复开销；4）性能暂停门槛依赖单次墙钟耗时，而当前 smoke 脚本本身包含较重的环境噪声来源，最好先补测量归一规则。

综合判断：这份 plan 的骨架是好的，方向也基本正确，我不建议推翻重写；但我建议先按上述四点把 text 再收紧一轮，再进入实现。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnpl2181-63hzim",
  "createdAt": "2026-04-08T00:00:00.000Z",
  "updatedAt": "2026-04-08T05:13:16.348Z",
  "finalizedAt": "2026-04-08T05:13:16.348Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "算法层统一估算与派工重构plan策划质量三轮深度review",
    "date": "2026-04-08",
    "overview": "聚焦审查 plan 本身的策划质量、边界控制、任务拆分、风险控制与验收口径；必要时只做基线事实核对，不评判当前实现成果。"
  },
  "scope": {
    "markdown": "# 算法层统一估算与派工重构plan策划质量三轮深度review\n\n- 日期：2026-04-08\n- 范围：仅审查 `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md` 的策划质量，重点看目标定义、边界约束、引用链、任务拆分、风险控制、暂停门槛、验收标准是否严谨。\n- 说明：本轮不以“当前实现是否完成”为中心；如需核对 plan 中“经代码核实”的前提，只做最小必要的基线事实核验。\n\n## 初始结论\n\n待审查。先从三个层面展开：\n1. plan 的目标、范围、非目标与约束是否自洽\n2. plan 对基线事实、引用链、函数变量的描述是否准确\n3. plan 的任务拆分、测试顺序、暂停门槛与完成判定是否足够可执行"
  },
  "summary": {
    "latestConclusion": "该 plan 不是空泛任务单，而是建立在真实主链、真实函数边界与现有回归事实上形成的可执行 plan。优点主要有四点：第一，目标聚焦，没有把范围扩散到 `schema.sql`、报表层日期函数或新的平行算法模式；第二，公开边界约束与 direct-call raw 输入兼容约束写得很清楚，能避免“重构顺手收紧入口”这类隐性破坏；第三，`internal_slot.py` 与 `dispatch/runtime_state.py` 的拆分方向总体简洁，确实对应了当前代码里的两组重复热点；第四，任务 4、任务 5 对日期事实源与优化器重复工作的识别是准确的，完成判定也覆盖到了关键语义。\n\n但该 plan 还没有达到“可以零歧义直接开工”的程度，至少需要先修订四处策划级问题：1）`created_at` strict 边界仍停在整轮 `keys` 粒度，improve 模式下仍可能在非 FIFO 尝试提前硬失败；2）`validate_internal_hours()` 被要求把属性读取和数值转换失败统一改写为 `ValueError`，这和 plan 自己“真正的程序错误必须显式暴露”的原则不完全一致；3）停机片段规范化落点写成“公开入口或统一估算入口”过于宽泛，容易把一次性兼容工作放进高频估算路径，反向制造重复开销；4）性能暂停门槛依赖单次墙钟耗时，而当前 smoke 脚本本身包含较重的环境噪声来源，最好先补测量归一规则。\n\n综合判断：这份 plan 的骨架是好的，方向也基本正确，我不建议推翻重写；但我建议先按上述四点把 text 再收紧一轮，再进入实现。",
    "recommendedNextAction": "先修订 `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md` 中 `created_at` strict 启用粒度、`validate_internal_hours()` 异常边界、停机规范化落点与性能暂停口径四处文字，再基于修订版进入实现。",
    "reviewedModules": [
      ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
      "core/services/scheduler/schedule_service.py",
      "core/services/scheduler/schedule_input_collector.py",
      "core/services/scheduler/schedule_orchestrator.py",
      "core/services/scheduler/schedule_optimizer.py",
      "core/algorithms/__init__.py",
      "core/algorithms/sort_strategies.py",
      "core/algorithms/greedy/scheduler.py",
      "core/algorithms/greedy/auto_assign.py",
      "core/algorithms/greedy/dispatch/sgs.py",
      "core/algorithms/greedy/dispatch/batch_order.py",
      "core/algorithms/greedy/downtime.py",
      "core/services/scheduler/resource_pool_builder.py",
      "core/services/scheduler/schedule_optimizer_steps.py",
      "core/services/common/strict_parse.py",
      "core/algorithms/evaluation.py",
      "core/algorithms/dispatch_rules.py",
      "core/algorithms/ortools_bottleneck.py",
      "tests/smoke_phase10_sgs_auto_assign.py",
      "tests/regression_sgs_scoring_machine_operator_id_type_safe.py",
      "tests/regression_dispatch_blocking_consistency.py",
      "tests/regression_scheduler_nonfinite_efficiency_fallback.py"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 4,
    "severity": {
      "high": 0,
      "medium": 3,
      "low": 1
    }
  },
  "milestones": [
    {
      "id": "round1-chain-and-boundaries",
      "title": "第一轮：目标、公开边界与引用链自洽性审查",
      "status": "completed",
      "recordedAt": "2026-04-08T05:11:27.426Z",
      "summaryMarkdown": "本轮先只审查 plan 的目标定义、公开边界约束与引用链是否建立在真实基线上。核对后，`ScheduleService._run_schedule_impl()` → `collect_schedule_run_input()` → `orchestrate_schedule_run()` → `optimize_schedule()` → `GreedyScheduler.schedule()` 的主链与 plan 描述一致；`core/algorithms/__init__.py` 仍导出 `GreedyScheduler`，而 `tests/regression_sgs_scoring_machine_operator_id_type_safe.py`、`tests/regression_dispatch_blocking_consistency.py` 这类回归确实直接喂 raw `op/batch` 给 `GreedyScheduler.schedule()`，所以 plan 把“不得静默收窄 direct-call raw 输入兼容边界”列为硬约束是合理的。整体上，plan 的目标、非目标、公开函数签名保护和任务顺序是自洽的，且没有把问题错误地下沉到服务边界外。但在任务 4 上仍存在一个策划粒度问题：plan 已意识到不能再用 `valid_strategies` 触发 `created_at` 的 strict 解析，却把启用条件停在整轮 `keys` 级别。对于 `optimize_schedule()` 的 improve 模式，`keys` 是本轮全量策略集合，而不是单次实际 `build_order()` 的当前策略；若 `keys` 里包含 `fifo`，就可能在非 FIFO 尝试也提前对 `created_at` 做 strict 解析，从而与 plan 自己提出的“只在 FIFO 相关排序路径真正消费该字段时才允许 strict 硬失败”仍有一层偏差。",
      "conclusionMarkdown": "主链、公开边界与 direct-call 兼容约束的策划基础扎实；但 `created_at` 的 strict 启用粒度还需要从整轮 `keys` 再收紧到单次实际排序策略。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 262,
          "lineEnd": 289,
          "symbol": "ScheduleService._run_schedule_impl"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py",
          "lineStart": 387,
          "lineEnd": 421,
          "symbol": "collect_schedule_run_input"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py",
          "lineStart": 113,
          "lineEnd": 128,
          "symbol": "orchestrate_schedule_run"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 392,
          "lineEnd": 399,
          "symbol": "optimize_schedule"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 359,
          "lineEnd": 374,
          "symbol": "optimize_schedule"
        },
        {
          "path": "core/algorithms/sort_strategies.py",
          "lineStart": 117,
          "lineEnd": 125,
          "symbol": "FIFOStrategy.sort"
        },
        {
          "path": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py",
          "lineStart": 109,
          "lineEnd": 131,
          "symbol": "main"
        },
        {
          "path": "tests/regression_dispatch_blocking_consistency.py",
          "lineStart": 122,
          "lineEnd": 146,
          "symbol": "_run/main"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 483,
          "lineEnd": 487,
          "symbol": "任务 4 / 步骤 4"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/algorithms/__init__.py"
        },
        {
          "path": "core/algorithms/sort_strategies.py"
        },
        {
          "path": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py"
        },
        {
          "path": "tests/regression_dispatch_blocking_consistency.py"
        }
      ],
      "reviewedModules": [
        ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/schedule_input_collector.py",
        "core/services/scheduler/schedule_orchestrator.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/algorithms/__init__.py",
        "core/algorithms/sort_strategies.py"
      ],
      "recommendedNextAction": "继续第二轮，集中审查任务 1~3、`internal_slot.py` / `runtime_state.py` 的职责边界，以及 plan 对异常语义和时间线有序化的约束是否存在自我冲突。",
      "findingIds": [
        "plan-created-at-strict-granularity"
      ]
    },
    {
      "id": "round2-tasks1-to-3-and-module-split",
      "title": "第二轮：任务 1~3、重复估算与运行期状态拆分审查",
      "status": "completed",
      "recordedAt": "2026-04-08T05:12:18.413Z",
      "summaryMarkdown": "本轮聚焦 `#plan-t1`、`#plan-t2`、`#plan-t3` 是否真的贴着当前代码的重复点下刀，以及新文件 `core/algorithms/greedy/internal_slot.py`、`core/algorithms/greedy/dispatch/runtime_state.py` 是否必要且职责收口。基线核对后，`GreedyScheduler._schedule_internal()` 与 `auto_assign_internal_resources()` 当前确实共享同一类“工作时刻修正 → 三路时间线避让 → 效率折算”的估算骨架，而 `dispatch_sgs()` 内部评分仍保留另一套顺序链式近似路径；seed 预热、`dispatch_batch_order()`、`dispatch_sgs()` 也分别重复维护 `machine_busy_hours`、`operator_busy_hours`、`last_end_by_machine`、`last_op_type_by_machine`。因此，plan 选择把真实估算收口到 `internal_slot.py`、把成功后运行期状态更新收口到 `runtime_state.py`，总体上是简洁且必要的。与此同时，我也看到两处策划层面的风险：第一，plan 一方面要求“真正的程序错误必须显式暴露”，另一方面又要求 `validate_internal_hours()` 用局部 `try/except` 把“属性读取与 `float(...)` 转换失败”统一改写成 `ValueError`；这会把共享入口上的对象访问异常、属性实现异常等程序错误和真正的 raw 数值坏值混在一起。第二，plan 对有序停机片段的规范化落点给了“公开入口或统一估算入口”两个选项；在当前代码里，服务主链经 `resource_pool_builder.py` 已经会把停机区间排序，真正需要补的一次性规范化其实主要发生在 direct-call 入口。如果把规范化放到 `estimate_internal_slot()` 这一高频入口，`auto_assign` 与 `dispatch_sgs()` 评分阶段都可能对同一批停机片段反复排序，直接和任务 2、任务 5 的性能目标相冲突。",
      "conclusionMarkdown": "任务 1~3 的拆分方向是对的，且新模块边界总体优雅；但 `validate_internal_hours()` 的异常归一范围和停机规范化落点都需要在 plan 上再收紧，否则很容易一边想去掉过度防御，一边又在共享入口重新引入。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 469,
          "lineEnd": 545,
          "symbol": "GreedyScheduler._schedule_internal"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 102,
          "lineEnd": 223,
          "symbol": "auto_assign_internal_resources"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 227,
          "lineEnd": 341,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py",
          "lineStart": 86,
          "lineEnd": 106,
          "symbol": "dispatch_batch_order"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 264,
          "lineEnd": 304,
          "symbol": "GreedyScheduler.schedule"
        },
        {
          "path": "core/algorithms/greedy/downtime.py",
          "lineStart": 20,
          "lineEnd": 57,
          "symbol": "occupy_resource/find_earliest_available_start"
        },
        {
          "path": "core/services/scheduler/resource_pool_builder.py",
          "lineStart": 151,
          "lineEnd": 163,
          "symbol": "load_machine_downtimes"
        },
        {
          "path": "core/services/scheduler/resource_pool_builder.py",
          "lineStart": 298,
          "lineEnd": 310,
          "symbol": "extend_downtime_map_for_resource_pool"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 80,
          "lineEnd": 85,
          "symbol": "实施约束"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 215,
          "lineEnd": 219,
          "symbol": "任务 1 / 步骤 3"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 97,
          "lineEnd": 99,
          "symbol": "实施约束"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 397,
          "lineEnd": 398,
          "symbol": "任务 3 / 步骤 3"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 612,
          "lineEnd": 613,
          "symbol": "完成判定"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py"
        },
        {
          "path": "core/algorithms/greedy/downtime.py"
        },
        {
          "path": "core/services/scheduler/resource_pool_builder.py"
        },
        {
          "path": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py"
        },
        {
          "path": "tests/regression_scheduler_nonfinite_efficiency_fallback.py"
        }
      ],
      "reviewedModules": [
        ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
        "core/algorithms/greedy/scheduler.py",
        "core/algorithms/greedy/auto_assign.py",
        "core/algorithms/greedy/dispatch/sgs.py",
        "core/algorithms/greedy/dispatch/batch_order.py",
        "core/algorithms/greedy/downtime.py",
        "core/services/scheduler/resource_pool_builder.py"
      ],
      "recommendedNextAction": "继续第三轮，审查任务 4~5、性能门槛、暂停条件与完成判定是否真正可测、可执行且不被环境噪声误导。",
      "findingIds": [
        "plan-validate-internal-hours-broad-except",
        "plan-downtime-normalization-placement-ambiguous"
      ]
    },
    {
      "id": "round3-dates-optimizer-and-acceptance-gates",
      "title": "第三轮：任务 4~5、暂停门槛与完成判定可执行性审查",
      "status": "completed",
      "recordedAt": "2026-04-08T05:12:54.953Z",
      "summaryMarkdown": "本轮审查 `#plan-t4`、`#plan-t5`、`执行留痕与暂停门槛`、`完成判定` 是否真正可执行。基线核对显示，task 4 与 task 5 锚定的问题都是真问题：`core/algorithms/evaluation.py`、`core/algorithms/dispatch_rules.py`、`core/algorithms/ortools_bottleneck.py` 目前各自维护 `due_exclusive()` 副本；`core/services/common/strict_parse.py` 只有严格日期解析，没有严格日期时间解析；`schedule_optimizer.py` 既有本地 `_parse_datetime()`，又在 `keys` 计算前构造 `batch_for_sort`；`_run_multi_start()` 也确实在 `dispatch_rule` 内层重复 `build_order()`，`_run_local_search()` 则没有邻域去重。因此，plan 对 task 4 / task 5 的目标判断是准确的，且“先统一边界，再做微优化与回归”的顺序也合理。真正的策划弱点主要出现在执行门槛：plan 多处把 `smoke_phase10_sgs_auto_assign.py` 与未来新增的大资源池基准的单次 `总耗时` 变化，直接作为 `30%` 暂停阈值。问题在于，现有 `smoke_phase10_sgs_auto_assign.py` 本身就包含临时目录创建、测试数据库初始化、建表、插数、配置切换与多轮服务调用，墙钟时间受环境抖动影响很大；如果 plan 不再补一层“重复次数 / 中位数 / 预热 / 允许人工判读”的测量归一规则，这个阈值更像人工排查提示，而不像稳定的执行闸门。",
      "conclusionMarkdown": "任务 4~5 的技术目标与验收方向总体成立，完成判定也覆盖到了核心语义；但性能暂停门槛还缺少测量归一规则，建议在 plan 中改成可重复、可解释的比较口径。",
      "evidence": [
        {
          "path": "core/algorithms/evaluation.py",
          "lineStart": 38,
          "lineEnd": 58,
          "symbol": "_parse_due_date/_due_exclusive"
        },
        {
          "path": "core/algorithms/dispatch_rules.py",
          "lineStart": 25,
          "lineEnd": 28,
          "symbol": "_due_exclusive"
        },
        {
          "path": "core/algorithms/ortools_bottleneck.py",
          "lineStart": 23,
          "lineEnd": 42,
          "symbol": "_parse_due_date/_due_exclusive"
        },
        {
          "path": "core/services/common/strict_parse.py",
          "lineStart": 85,
          "lineEnd": 103,
          "symbol": "parse_required_date/parse_optional_date"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 335,
          "lineEnd": 399,
          "symbol": "optimize_schedule"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py",
          "lineStart": 300,
          "lineEnd": 335,
          "symbol": "_run_multi_start"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 127,
          "lineEnd": 181,
          "symbol": "_run_local_search"
        },
        {
          "path": "tests/smoke_phase10_sgs_auto_assign.py",
          "lineStart": 46,
          "lineEnd": 57,
          "symbol": "main"
        },
        {
          "path": "tests/smoke_phase10_sgs_auto_assign.py",
          "lineStart": 142,
          "lineEnd": 193,
          "symbol": "main"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 550,
          "lineEnd": 566,
          "symbol": "任务 5 / 步骤 6"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 574,
          "lineEnd": 576,
          "symbol": "执行留痕与暂停门槛 / 任务 2"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 583,
          "lineEnd": 585,
          "symbol": "执行留痕与暂停门槛 / 任务 5"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
        },
        {
          "path": "core/algorithms/evaluation.py"
        },
        {
          "path": "core/algorithms/dispatch_rules.py"
        },
        {
          "path": "core/algorithms/ortools_bottleneck.py"
        },
        {
          "path": "tests/smoke_phase10_sgs_auto_assign.py"
        }
      ],
      "reviewedModules": [
        ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/scheduler/schedule_optimizer_steps.py",
        "core/services/common/strict_parse.py",
        "core/algorithms/evaluation.py",
        "core/algorithms/dispatch_rules.py",
        "core/algorithms/ortools_bottleneck.py",
        "tests/smoke_phase10_sgs_auto_assign.py"
      ],
      "recommendedNextAction": "综合三轮结论，给出最终 review 结论；建议在执行前先修订 `created_at` strict 粒度、`validate_internal_hours()` 异常边界、停机规范化落点与性能暂停口径。",
      "findingIds": [
        "plan-performance-gate-not-normalized"
      ]
    }
  ],
  "findings": [
    {
      "id": "plan-created-at-strict-granularity",
      "severity": "medium",
      "category": "maintainability",
      "title": "created_at 严格边界启用粒度过粗",
      "descriptionMarkdown": "plan 已正确识别不能再用 `valid_strategies` 这种默认全量候选集去提前触发 `created_at` 的 strict 校验，但当前策划仍把启用条件放在整轮 `keys` 上。对 `optimize_schedule()` 的 improve 模式来说，`keys` 代表本轮准备探索的全量策略集合，而不是单次实际 `build_order()` 所用的当前策略。这样一来，只要 `keys` 含 `fifo`，就可能在非 FIFO 尝试上也提前对 `created_at` 做 strict 解析，和 plan 自身“仅在 FIFO 相关排序路径真正消费该字段时才允许 strict 硬失败”的目标仍不完全一致。更稳妥的策划应把 strict 启用点收紧到单次策略级，例如放到 `_build_order()` 或等价的按当前 `strategy0` 构造排序输入处。",
      "recommendationMarkdown": "把 `created_at` 的 strict 启用条件从“本轮 `keys` 是否含 `fifo`”再收紧一层，改成“当前单次实际构造排序器的策略是否为 `fifo`”，并在 plan 的测试说明中显式补一条 improve 模式下‘全局策略集含 fifo、但当前尝试非 fifo’的断言。",
      "evidence": [
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 483,
          "lineEnd": 487,
          "symbol": "任务 4 / 步骤 4"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 359,
          "lineEnd": 399,
          "symbol": "optimize_schedule"
        },
        {
          "path": "core/algorithms/sort_strategies.py",
          "lineStart": 117,
          "lineEnd": 125,
          "symbol": "FIFOStrategy.sort"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/algorithms/__init__.py"
        },
        {
          "path": "core/algorithms/sort_strategies.py"
        },
        {
          "path": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py"
        },
        {
          "path": "tests/regression_dispatch_blocking_consistency.py"
        }
      ],
      "relatedMilestoneIds": [
        "round1-chain-and-boundaries"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "plan-validate-internal-hours-broad-except",
      "severity": "medium",
      "category": "maintainability",
      "title": "validate_internal_hours 异常归一范围过宽",
      "descriptionMarkdown": "plan 在总原则里明确要求“真正的程序错误必须显式暴露”，但在 `validate_internal_hours()` 的细化步骤里，又要求用局部 `try/except` 把“属性读取与 `float(...)` 转换失败”统一重写为带 `repr` 的 `ValueError`。由于这个共享入口会同时服务 `_schedule_internal()`、`auto_assign_internal_resources()`、`dispatch_sgs()` 的采样与评分路径，这种写法会把对象属性实现异常、访问期程序错误与真正的 raw 数值坏值混到同一个业务异常口径里，仍然带有明显的过度防御色彩。plan 如果要保持 direct-call 的缺字段 / `None` / 空串 / `False` 兼容边界，并不需要把任意属性访问异常都业务化。",
      "recommendationMarkdown": "把 `validate_internal_hours()` 的兼容范围缩成“显式保留的 raw 值边界 + 标量数值转换错误”，不要把任意属性读取异常统一重写成 `ValueError`；对对象访问期的非预期异常，应按程序错误直接上浮。",
      "evidence": [
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 80,
          "lineEnd": 85,
          "symbol": "实施约束"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 215,
          "lineEnd": 219,
          "symbol": "任务 1 / 步骤 3"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 476,
          "lineEnd": 485,
          "symbol": "GreedyScheduler._schedule_internal"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 102,
          "lineEnd": 112,
          "symbol": "auto_assign_internal_resources"
        },
        {
          "path": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py",
          "lineStart": 61,
          "lineEnd": 89,
          "symbol": "_build_case"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py"
        },
        {
          "path": "core/algorithms/greedy/downtime.py"
        },
        {
          "path": "core/services/scheduler/resource_pool_builder.py"
        },
        {
          "path": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py"
        },
        {
          "path": "tests/regression_scheduler_nonfinite_efficiency_fallback.py"
        }
      ],
      "relatedMilestoneIds": [
        "round2-tasks1-to-3-and-module-split"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "plan-downtime-normalization-placement-ambiguous",
      "severity": "medium",
      "category": "performance",
      "title": "停机规范化落点不唯一",
      "descriptionMarkdown": "plan 对有序停机片段的前置规范化给出了“公开入口或统一估算入口”两个落点，但当前服务主链经 `load_machine_downtimes()` 与 `extend_downtime_map_for_resource_pool()` 已会对停机片段排序，真正需要补的一次性兼容主要是 direct-call 给 `GreedyScheduler.schedule()` 传入无序 `machine_downtimes` 的场景。若实现者把规范化放到 `estimate_internal_slot()` 这一高频入口，`auto_assign_internal_resources()` 与 `dispatch_sgs()` 评分阶段都可能对同一 `machine_downtimes[mid]` 反复排序或清洗，直接抵消任务 2 与任务 5 试图争取的性能收益。",
      "recommendationMarkdown": "在 plan 里把规范化落点固定为 `GreedyScheduler.schedule()` 的一次性入口标准化，并让 `internal_slot.py`、`auto_assign.py`、`dispatch_sgs.py` 都基于“输入已按入口规范化”的前提工作。",
      "evidence": [
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 97,
          "lineEnd": 99,
          "symbol": "实施约束"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 397,
          "lineEnd": 398,
          "symbol": "任务 3 / 步骤 3"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 612,
          "lineEnd": 613,
          "symbol": "完成判定"
        },
        {
          "path": "core/services/scheduler/resource_pool_builder.py",
          "lineStart": 151,
          "lineEnd": 163,
          "symbol": "load_machine_downtimes"
        },
        {
          "path": "core/services/scheduler/resource_pool_builder.py",
          "lineStart": 298,
          "lineEnd": 310,
          "symbol": "extend_downtime_map_for_resource_pool"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 506,
          "lineEnd": 532,
          "symbol": "GreedyScheduler._schedule_internal"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 179,
          "lineEnd": 203,
          "symbol": "auto_assign_internal_resources"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 279,
          "lineEnd": 333,
          "symbol": "dispatch_sgs"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py"
        },
        {
          "path": "core/algorithms/greedy/downtime.py"
        },
        {
          "path": "core/services/scheduler/resource_pool_builder.py"
        },
        {
          "path": "tests/regression_sgs_scoring_machine_operator_id_type_safe.py"
        },
        {
          "path": "tests/regression_scheduler_nonfinite_efficiency_fallback.py"
        }
      ],
      "relatedMilestoneIds": [
        "round2-tasks1-to-3-and-module-split"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "plan-performance-gate-not-normalized",
      "severity": "low",
      "category": "performance",
      "title": "性能暂停门槛缺少测量归一规则",
      "descriptionMarkdown": "plan 把 `smoke_phase10_sgs_auto_assign.py` 与未来大资源池基准的单次 `总耗时` 变化直接作为 `30%` 暂停阈值，但现有 `smoke_phase10_sgs_auto_assign.py` 本身就包含临时目录创建、测试数据库初始化、建表、插数、配置切换和多轮服务调用，墙钟时间天然容易受机器负载与文件系统抖动影响。若没有最少重复次数、预热、使用中位数或明确的人工判读规则，这个阈值更适合作为“需要进一步解释”的提示，而不适合作为硬暂停门槛。",
      "recommendationMarkdown": "把 `30%` 阈值改成带测量归一规则的口径，例如固定重复次数后取中位数，或在 plan 中明确“该阈值仅用于提示人工复核，不作为单次运行即可触发的硬暂停条件”。",
      "evidence": [
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 550,
          "lineEnd": 566,
          "symbol": "任务 5 / 步骤 6"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 574,
          "lineEnd": 576,
          "symbol": "执行留痕与暂停门槛 / 任务 2"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md",
          "lineStart": 583,
          "lineEnd": 585,
          "symbol": "执行留痕与暂停门槛 / 任务 5"
        },
        {
          "path": "tests/smoke_phase10_sgs_auto_assign.py",
          "lineStart": 46,
          "lineEnd": 57,
          "symbol": "main"
        },
        {
          "path": "tests/smoke_phase10_sgs_auto_assign.py",
          "lineStart": 142,
          "lineEnd": 193,
          "symbol": "main"
        },
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/common/strict_parse.py"
        },
        {
          "path": "core/algorithms/evaluation.py"
        },
        {
          "path": "core/algorithms/dispatch_rules.py"
        },
        {
          "path": "core/algorithms/ortools_bottleneck.py"
        },
        {
          "path": "tests/smoke_phase10_sgs_auto_assign.py"
        }
      ],
      "relatedMilestoneIds": [
        "round3-dates-optimizer-and-acceptance-gates"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:f81e32f885f4fc81ff0af468b909a43064a1c137ad962db9fe14fcc661a36aa1",
    "generatedAt": "2026-04-08T05:13:16.348Z",
    "locale": "zh-CN"
  }
}
```
