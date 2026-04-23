# 算法层统一估算与派工重构plan深度审查_第三轮
- 日期: 2026-04-07
- 概述: 围绕算法层统一估算、派工评分同源、时间线有序化、日期边界统一与优化器微优化的可达成性、风险点与潜在BUG进行第三轮深度审查。日期：2026-04-07。
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# 算法层统一估算与派工重构 plan 深度审查（第三轮）

- 日期：2026-04-07
- 审查范围：`core/algorithms/greedy/**`、`core/services/scheduler/**` 及相关测试与调用链
- 审查目标：验证当前 plan 是否能达成目标，是否存在设计缺口、实现风险、静默回退残留、边界遗漏与潜在 BUG

## 初始关注点

1. 统一内部工序估算器是否真能覆盖执行路径、自动分配路径与 SGS 评分路径，而不引入第三套语义。
2. 固定 `200` 次硬上限替换为“局部片段数上界”后，是否在当前时间线维护方式下仍然可证正确。
3. 运行期状态收口是否覆盖 seed 预热与两条派工分支的语义差异。
4. 日期函数统一是否会误伤严格模式边界包装。
5. 优化器微优化是否仅消重，不改变现有选择与留痕语义。

## 审查策略

按调用链与任务顺序分批核查，并在每个模块级审查单元结束后记录里程碑。

## 评审摘要

- 当前状态: 已完成
- 已审模块: core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_input_collector.py, core/services/scheduler/schedule_orchestrator.py, core/algorithms/greedy/scheduler.py, core/algorithms/greedy/auto_assign.py, core/services/scheduler/schedule_input_builder.py, core/algorithms/greedy/external_groups.py, core/services/scheduler/schedule_optimizer.py, core/algorithms/greedy/dispatch/sgs.py, core/algorithms/greedy/dispatch/batch_order.py, core/algorithms/greedy/downtime.py, core/algorithms/greedy/date_parsers.py, core/algorithms/evaluation.py, core/algorithms/dispatch_rules.py, core/algorithms/ortools_bottleneck.py, core/services/scheduler/schedule_optimizer_steps.py, core/services/scheduler/schedule_summary.py, core/services/report/calculations.py, core/algorithms/sort_strategies.py
- 当前进度: 已记录 3 个里程碑；最新：M3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 4
- 问题严重级别分布: 高 1 / 中 2 / 低 1
- 最新结论: 结论：当前 plan 的主线方向正确，统一估算器、SGS 评分同源、时间线有序化、日期工具收口与优化器微优化这五个任务的整体拆分是可执行的，且没有引入新的平行算法模式，主体设计也比现状更收敛。但以“可直接开工”的标准看，仍有 3 处应先补进 plan：1）把 `ready_date` / `created_at` 纳入任务 4 的日期边界说明，并处理 `ready_date` 初始化中的静默回退；2）把 seed 场景下空 `op_type_name` 的最近状态语义写进 `runtime_state.py` 契约与回归；3）把任务 5 的 `build_order()` 去重范围从仅覆盖 `dispatch_rule` 扩到同时覆盖 `dispatch_mode`。除此之外，再把 `seen_hashes` 预热当前顺序这一低风险细节补充进去，plan 就会更严谨、也更接近“优雅且不留暗口子”的状态。
- 下一步建议: 先修订 F11、F12、F13，再进入实现；F14 可在任务 5 编码时一并补入。
- 总体结论: 有条件通过

## 评审发现

### 非 due_date 日期边界遗漏

- ID: F11
- 严重级别: 高
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  当前 plan 的任务 4 只显式处理 `due_exclusive()`、非严格 `parse_date()` / `parse_datetime()` 与 `due_date` 的严格包装，但算法实际还消费了 `ready_date` 与 `created_at`。现状里有两层残留风险：1）`GreedyScheduler.schedule()` 在严格模式下只对 `due_date` 用 `parse_optional_date(..., field="due_date")`，`ready_date` 与 `created_at` 仍走非严格解析，坏值会静默变成 `None`；其中 `ready_date` 直接决定 `batch_progress` 的最早开工下界，坏值会让批次失去齐套下界。2）`ready_date` 初始化后调用 `calendar.adjust_to_working_time()` 时又有一层广域 `except Exception`，异常会静默回退到午夜 `dt0`。这条回退再叠加外协工序直接使用 `batch_progress` 作为 `prev_end` 的事实，会让外协工序在日历异常时悄悄提前起排。也就是说，即便任务 1~5 全部按 plan 落地，算法层仍不能彻底摆脱“日期边界不完整 + 静默回退”的残留口子。
- 建议:

  把任务 4 的边界说明从“只处理 due_date”提升为“显式声明其他日期字段是否接受静默降级”。若目标仍是消除算法层静默日期回退，至少应补两件事：一是给 `ready_date`、`created_at` 增加字段级严格/非严格包装，不再复用 `due_date` 名义；二是去掉 `scheduler.py:234-236` 这类日历异常后直接回退到 `dt0` 的静默逻辑，至少改成显式 warning + 统一计数，或在严格模式直接抛错。
- 证据:
  - `core/algorithms/greedy/scheduler.py:138-146#GreedyScheduler.schedule`
  - `core/algorithms/greedy/scheduler.py:228-237#GreedyScheduler.schedule`
  - `core/services/scheduler/schedule_optimizer.py:335-368#optimize_schedule`
  - `core/algorithms/greedy/external_groups.py:35-45#schedule_external`
  - `core/algorithms/greedy/external_groups.py:120-121#schedule_external`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/algorithms/greedy/external_groups.py`
  - `core/services/scheduler/schedule_optimizer.py`

### seed 空工种名语义未写入 runtime_state 契约

- ID: F12
- 严重级别: 中
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  当前代码里，seed 预热与正式派工对“最近工种/最近结束时间”的更新并不只是 `conditional_op_type=True/False` 这么简单。`scheduler.py:299-304` 的 seed 分支有 `if mid and ot and sr.end_time:` 这个联合前提，意味着只要 `op_type_name` 为空，seed 连 `last_end_by_machine` 都不会更新；而 `batch_order.py:95-106` 与 `sgs.py:463-475` 的正式派工分支会先更新 `last_end_by_machine`，然后仅在 `ot` 非空时更新 `last_op_type_by_machine`。这两个语义如果被共享函数不小心揉成“seed 只做条件覆盖、正式派工做直接更新”，但没有显式保留空工种名分支，带空 `op_type_name` 的 seed 就会把机器最近结束时间推进到更晚，反过来压住后面合法 seed 的工种信息，最终改变 `dispatch_sgs()` 与自动分配里的换型惩罚判断。当前 plan 的任务 3 已经覆盖了条件覆盖/直接更新两种主模式，但还没把这条更细的空工种名语义写成实现约束或回归用例。
- 建议:

  把任务 3 的共享函数说明再细化一层：seed 模式下若 `op_type_name` 为空，则 `last_end_by_machine` 与 `last_op_type_by_machine` 都不更新；正式派工模式下则继续保持“`last_end_by_machine` 条件更新、`last_op_type_by_machine` 仅在非空时直接更新”。同时在 `tests/regression_downtime_timeline_ordered_insert.py` 或单独回归里补一个“更晚 seed 但空工种名不应覆盖最近状态”的用例。
- 证据:
  - `core/algorithms/greedy/scheduler.py:299-304#GreedyScheduler.schedule`
  - `core/algorithms/greedy/dispatch/batch_order.py:95-106#dispatch_batch_order`
  - `core/algorithms/greedy/dispatch/sgs.py:463-475#dispatch_sgs`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/dispatch/batch_order.py`
  - `core/algorithms/greedy/downtime.py`
  - `core/algorithms/greedy/scheduler.py`

### _run_multi_start 去重只覆盖 dispatch_rule

- ID: F13
- 严重级别: 中
- 分类: 性能
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  当前 plan 的任务 5 只要求把 `order = build_order(strat, params0)` 从 `for dr in dispatch_rules` 内层提升到 `for k in keys` 内层，但 `_run_multi_start()` 的真实重复并不止这一层。`order` 只依赖 `strategy/params0`，与 `dispatch_mode` 同样无关；而 `optimize_schedule()` 在 improve 模式下会显式构造多个 `dispatch_mode`（`batch_order` 与 `sgs`），因此即便按 plan 完成，系统仍会在每个 `dispatch_mode` 下为同一个 `strategy/params0` 重建一次完全相同的 `order`。这意味着任务 5 宣称的“消掉同一排序策略下重复构造 order 的开销”实际上只消掉了一半。
- 建议:

  把任务 5 的 `build_order()` 优化升级为显式缓存：键至少使用 `(strategy.value, tuple(sorted(params0.items())))`，并在 `dispatch_mode` 与 `dispatch_rule` 两层循环外复用。对应回归也应从“不因不同 dispatch_rule 重复执行”提升为“不因不同 dispatch_mode / dispatch_rule 重复执行”。
- 证据:
  - `core/services/scheduler/schedule_optimizer_steps.py:300-335#_run_multi_start`
  - `core/services/scheduler/schedule_optimizer.py:464-522#optimize_schedule`
  - `core/algorithms/greedy/date_parsers.py`
  - `core/algorithms/evaluation.py`
  - `core/algorithms/dispatch_rules.py`
  - `core/algorithms/ortools_bottleneck.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/scheduler/schedule_summary.py`
  - `core/services/report/calculations.py`
  - `core/algorithms/sort_strategies.py`

### local_search 去重未显式预热当前顺序

- ID: F14
- 严重级别: 低
- 分类: 性能
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  任务 5 计划给 `_run_local_search()` 增加 `seen_hashes`，但文本没有写明应当先把 `cur_order`（也就是当前 best 的顺序）放入去重集合。当前实现里，邻域生成存在多处回退：`insert` 可能选到原位，`block` 可能回插原位，代码随后再做一次 `swap_fallback`。如果实施者只按字面新增一个空的 `seen_hashes`，那么“与当前 best 完全相同的顺序”仍可能在第一次命中时被当作新邻域送进 `_schedule_with_optional_strict_mode()`，这会让去重机制漏掉最基础的一类重复。问题不大，但会让任务 5 的收益打折。
- 建议:

  在任务 5 的实现说明中补一句：`seen_hashes` 初始化时先写入 `tuple(cur_order)`，并在每次接受更优解、执行 shake 后继续沿用同一个集合。若希望更彻底，还可以把已记录的 candidate 顺序同步进回归桩里，防止“等价邻域”被反复执行。
- 证据:
  - `core/services/scheduler/schedule_optimizer.py:128-181#_run_local_search`
  - `core/algorithms/greedy/date_parsers.py`
  - `core/algorithms/evaluation.py`
  - `core/algorithms/dispatch_rules.py`
  - `core/algorithms/ortools_bottleneck.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/scheduler/schedule_summary.py`
  - `core/services/report/calculations.py`
  - `core/algorithms/sort_strategies.py`

## 评审里程碑

### M1 · 第一轮：调用链、统一估算器入口与批次日期下界审查

- 状态: 已完成
- 记录时间: 2026-04-07T09:05:08.417Z
- 已审模块: core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_input_collector.py, core/services/scheduler/schedule_orchestrator.py, core/algorithms/greedy/scheduler.py, core/algorithms/greedy/auto_assign.py, core/services/scheduler/schedule_input_builder.py, core/algorithms/greedy/external_groups.py, core/services/scheduler/schedule_optimizer.py
- 摘要:

  已沿 `ScheduleService._run_schedule_impl()` → `collect_schedule_run_input()` → `orchestrate_schedule_run()` → `optimize_schedule()` → `GreedyScheduler.schedule()` 复核主链，并重点检查了 `scheduler.py`、`auto_assign.py`、`schedule_input_builder.py`、`external_groups.py`。结论：任务 1 的统一内部工序估算器方向正确，`prev_end`、资源时间线与工时预检的职责切分也基本优雅；但当前 plan 仍遗漏了一条会直接影响排产正确性的日期边界：`ready_date` 与 `created_at` 没有被纳入任务 4 的严格边界收口，且 `ready_date` 初始化阶段还保留了日历异常后的静默回退。该遗漏如果不补，重构完成后算法层仍然存在“严格模式不够严格、异常时静默提前开工”的残留口子。
- 结论:

  任务 1 的核心重构可以实施，但任务 4 需要补充 `ready_date`/`created_at` 的边界规则，否则无法宣称算法层日期事实源与严格模式边界已经真正收口。
- 证据:
  - `core/services/scheduler/schedule_service.py:262-289#ScheduleService._run_schedule_impl`
  - `core/services/scheduler/schedule_input_collector.py:387-421#collect_schedule_run_input`
  - `core/services/scheduler/schedule_orchestrator.py:113-128#orchestrate_schedule_run`
  - `core/algorithms/greedy/scheduler.py:138-146#GreedyScheduler.schedule`
  - `core/algorithms/greedy/scheduler.py:228-237#GreedyScheduler.schedule`
  - `core/algorithms/greedy/external_groups.py:35-45#schedule_external`
  - `core/algorithms/greedy/external_groups.py:120-121#schedule_external`
  - `core/services/scheduler/schedule_optimizer.py:335-368#optimize_schedule`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/algorithms/greedy/external_groups.py`
  - `core/services/scheduler/schedule_optimizer.py`
- 下一步建议:

  继续审查 `dispatch_sgs()`、`batch_order.py`、`downtime.py` 与计划中的 `runtime_state.py` 抽象，重点核对状态更新语义是否会在 seed 预热场景发生漂移。
- 问题:
  - [高] 其他: 非 due_date 日期边界遗漏

### M2 · 第二轮：SGS、批次派工、时间线与运行期状态收口审查

- 状态: 已完成
- 记录时间: 2026-04-07T09:05:38.758Z
- 已审模块: core/algorithms/greedy/dispatch/sgs.py, core/algorithms/greedy/dispatch/batch_order.py, core/algorithms/greedy/downtime.py, core/algorithms/greedy/scheduler.py
- 摘要:

  已复核 `dispatch_sgs()`、`dispatch_batch_order()`、`downtime.py` 以及 `scheduler.py` 中 seed 预热逻辑。结论：任务 2 对评分链路同源化、任务 3 对时间线有序化的主方向是对的，现有 `candidates[0]` 兜底、评分期广域吞异常、时间线每次排序等问题都值得收掉；但 `runtime_state.py` 的抽象文本仍少了一条非常关键的细语义：seed 预热分支在 `op_type_name` 为空时，当前代码连 `last_end_by_machine` 都不会推进，而派工成功分支则会先推进 `last_end_by_machine`、只跳过 `last_op_type_by_machine` 更新。若只用 `conditional_op_type=True/False` 两态去实现，而没有把“seed 空工种名完全跳过最近状态更新”写进 plan 和测试，实施者极易把两种语义揉平，导致换型 tie-break 在带空工种 seed 的场景发生漂移。
- 结论:

  任务 2 与任务 3 基本可实施，但 `runtime_state.py` 的共享函数契约还需再收紧一次：不仅要区分 seed 与正式派工，还要把 seed 场景下“空工种名不推进最近状态”的现有语义显式编码并补测试。
- 证据:
  - `core/algorithms/greedy/scheduler.py:289-304#GreedyScheduler.schedule`
  - `core/algorithms/greedy/dispatch/batch_order.py:90-106#dispatch_batch_order`
  - `core/algorithms/greedy/dispatch/sgs.py:458-475#dispatch_sgs`
  - `core/algorithms/greedy/downtime.py:20-28#occupy_resource`
  - `core/algorithms/greedy/downtime.py:31-77#find_earliest_available_start/find_overlap_shift_end`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/dispatch/batch_order.py`
  - `core/algorithms/greedy/downtime.py`
  - `core/algorithms/greedy/scheduler.py`
- 下一步建议:

  继续审查任务 4 与任务 5，重点检查日期统一是否真的覆盖全部算法输入字段，以及优化器“消重”是否仍有明显漏项。
- 问题:
  - [中] JavaScript: seed 空工种名语义未写入 runtime_state 契约

### M3 · 第三轮：日期工具收口与优化器消重完整性审查

- 状态: 已完成
- 记录时间: 2026-04-07T09:06:13.766Z
- 已审模块: core/algorithms/greedy/date_parsers.py, core/algorithms/evaluation.py, core/algorithms/dispatch_rules.py, core/algorithms/ortools_bottleneck.py, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_optimizer_steps.py, core/services/scheduler/schedule_summary.py, core/services/report/calculations.py, core/algorithms/sort_strategies.py
- 摘要:

  已复核 `date_parsers.py`、`evaluation.py`、`dispatch_rules.py`、`ortools_bottleneck.py`、`schedule_optimizer.py`、`schedule_optimizer_steps.py`、`schedule_summary.py`、`report/calculations.py` 与 `sort_strategies.py`。结论：任务 4 在“把算法层 due_date 相关重复实现并回 `greedy/date_parsers.py`”这件事上方向正确；但任务 5 对优化器重复工作的削减仍不够彻底。当前 `_run_multi_start()` 的重复不仅来自 `dispatch_rule`，同一 `strategy/params0` 在不同 `dispatch_mode` 下也会重复构造完全相同的 `order`。另外，计划虽然要求 `_run_local_search()` 加 `seen_hashes`，但没有把“应先把当前 best 的 `order` 放进 seen 集合”写出来，实施者若只按字面做空集合去重，当前基线顺序仍可能被当作新邻域执行一次，去重效果并不完整。
- 结论:

  任务 4 可继续按现方向推进；任务 5 需要再补两条实现约束，才能称得上真正把优化器里的明显重复工作收干净。
- 证据:
  - `core/services/scheduler/schedule_optimizer_steps.py:300-335#_run_multi_start`
  - `core/services/scheduler/schedule_optimizer.py:464-522#optimize_schedule`
  - `core/services/scheduler/schedule_optimizer.py:128-181#_run_local_search`
  - `core/algorithms/greedy/date_parsers.py:7-41#parse_date/parse_datetime`
  - `core/algorithms/evaluation.py:38-58#_parse_due_date/_due_exclusive`
  - `core/algorithms/dispatch_rules.py:25-28#_due_exclusive`
  - `core/algorithms/ortools_bottleneck.py:23-42#_parse_due_date/_due_exclusive`
  - `core/algorithms/greedy/date_parsers.py`
  - `core/algorithms/evaluation.py`
  - `core/algorithms/dispatch_rules.py`
  - `core/algorithms/ortools_bottleneck.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/scheduler/schedule_summary.py`
  - `core/services/report/calculations.py`
  - `core/algorithms/sort_strategies.py`
- 下一步建议:

  汇总三轮 findings，给出是否可按现状执行的最终判断，并明确哪些属于实施前必须先修 plan 的项。
- 问题:
  - [中] 性能: _run_multi_start 去重只覆盖 dispatch_rule
  - [低] 性能: local_search 去重未显式预热当前顺序

## 最终结论

结论：当前 plan 的主线方向正确，统一估算器、SGS 评分同源、时间线有序化、日期工具收口与优化器微优化这五个任务的整体拆分是可执行的，且没有引入新的平行算法模式，主体设计也比现状更收敛。但以“可直接开工”的标准看，仍有 3 处应先补进 plan：1）把 `ready_date` / `created_at` 纳入任务 4 的日期边界说明，并处理 `ready_date` 初始化中的静默回退；2）把 seed 场景下空 `op_type_name` 的最近状态语义写进 `runtime_state.py` 契约与回归；3）把任务 5 的 `build_order()` 去重范围从仅覆盖 `dispatch_rule` 扩到同时覆盖 `dispatch_mode`。除此之外，再把 `seen_hashes` 预热当前顺序这一低风险细节补充进去，plan 就会更严谨、也更接近“优雅且不留暗口子”的状态。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnodv3d5-rblv00",
  "createdAt": "2026-04-07T00:00:00.000Z",
  "updatedAt": "2026-04-07T09:06:45.799Z",
  "finalizedAt": "2026-04-07T09:06:45.799Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "算法层统一估算与派工重构plan深度审查_第三轮",
    "date": "2026-04-07",
    "overview": "围绕算法层统一估算、派工评分同源、时间线有序化、日期边界统一与优化器微优化的可达成性、风险点与潜在BUG进行第三轮深度审查。日期：2026-04-07。"
  },
  "scope": {
    "markdown": "# 算法层统一估算与派工重构 plan 深度审查（第三轮）\n\n- 日期：2026-04-07\n- 审查范围：`core/algorithms/greedy/**`、`core/services/scheduler/**` 及相关测试与调用链\n- 审查目标：验证当前 plan 是否能达成目标，是否存在设计缺口、实现风险、静默回退残留、边界遗漏与潜在 BUG\n\n## 初始关注点\n\n1. 统一内部工序估算器是否真能覆盖执行路径、自动分配路径与 SGS 评分路径，而不引入第三套语义。\n2. 固定 `200` 次硬上限替换为“局部片段数上界”后，是否在当前时间线维护方式下仍然可证正确。\n3. 运行期状态收口是否覆盖 seed 预热与两条派工分支的语义差异。\n4. 日期函数统一是否会误伤严格模式边界包装。\n5. 优化器微优化是否仅消重，不改变现有选择与留痕语义。\n\n## 审查策略\n\n按调用链与任务顺序分批核查，并在每个模块级审查单元结束后记录里程碑。"
  },
  "summary": {
    "latestConclusion": "结论：当前 plan 的主线方向正确，统一估算器、SGS 评分同源、时间线有序化、日期工具收口与优化器微优化这五个任务的整体拆分是可执行的，且没有引入新的平行算法模式，主体设计也比现状更收敛。但以“可直接开工”的标准看，仍有 3 处应先补进 plan：1）把 `ready_date` / `created_at` 纳入任务 4 的日期边界说明，并处理 `ready_date` 初始化中的静默回退；2）把 seed 场景下空 `op_type_name` 的最近状态语义写进 `runtime_state.py` 契约与回归；3）把任务 5 的 `build_order()` 去重范围从仅覆盖 `dispatch_rule` 扩到同时覆盖 `dispatch_mode`。除此之外，再把 `seen_hashes` 预热当前顺序这一低风险细节补充进去，plan 就会更严谨、也更接近“优雅且不留暗口子”的状态。",
    "recommendedNextAction": "先修订 F11、F12、F13，再进入实现；F14 可在任务 5 编码时一并补入。",
    "reviewedModules": [
      "core/services/scheduler/schedule_service.py",
      "core/services/scheduler/schedule_input_collector.py",
      "core/services/scheduler/schedule_orchestrator.py",
      "core/algorithms/greedy/scheduler.py",
      "core/algorithms/greedy/auto_assign.py",
      "core/services/scheduler/schedule_input_builder.py",
      "core/algorithms/greedy/external_groups.py",
      "core/services/scheduler/schedule_optimizer.py",
      "core/algorithms/greedy/dispatch/sgs.py",
      "core/algorithms/greedy/dispatch/batch_order.py",
      "core/algorithms/greedy/downtime.py",
      "core/algorithms/greedy/date_parsers.py",
      "core/algorithms/evaluation.py",
      "core/algorithms/dispatch_rules.py",
      "core/algorithms/ortools_bottleneck.py",
      "core/services/scheduler/schedule_optimizer_steps.py",
      "core/services/scheduler/schedule_summary.py",
      "core/services/report/calculations.py",
      "core/algorithms/sort_strategies.py"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 4,
    "severity": {
      "high": 1,
      "medium": 2,
      "low": 1
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "第一轮：调用链、统一估算器入口与批次日期下界审查",
      "status": "completed",
      "recordedAt": "2026-04-07T09:05:08.417Z",
      "summaryMarkdown": "已沿 `ScheduleService._run_schedule_impl()` → `collect_schedule_run_input()` → `orchestrate_schedule_run()` → `optimize_schedule()` → `GreedyScheduler.schedule()` 复核主链，并重点检查了 `scheduler.py`、`auto_assign.py`、`schedule_input_builder.py`、`external_groups.py`。结论：任务 1 的统一内部工序估算器方向正确，`prev_end`、资源时间线与工时预检的职责切分也基本优雅；但当前 plan 仍遗漏了一条会直接影响排产正确性的日期边界：`ready_date` 与 `created_at` 没有被纳入任务 4 的严格边界收口，且 `ready_date` 初始化阶段还保留了日历异常后的静默回退。该遗漏如果不补，重构完成后算法层仍然存在“严格模式不够严格、异常时静默提前开工”的残留口子。",
      "conclusionMarkdown": "任务 1 的核心重构可以实施，但任务 4 需要补充 `ready_date`/`created_at` 的边界规则，否则无法宣称算法层日期事实源与严格模式边界已经真正收口。",
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
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 138,
          "lineEnd": 146,
          "symbol": "GreedyScheduler.schedule"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 228,
          "lineEnd": 237,
          "symbol": "GreedyScheduler.schedule"
        },
        {
          "path": "core/algorithms/greedy/external_groups.py",
          "lineStart": 35,
          "lineEnd": 45,
          "symbol": "schedule_external"
        },
        {
          "path": "core/algorithms/greedy/external_groups.py",
          "lineStart": 120,
          "lineEnd": 121,
          "symbol": "schedule_external"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 335,
          "lineEnd": 368,
          "symbol": "optimize_schedule"
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
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py"
        },
        {
          "path": "core/algorithms/greedy/external_groups.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        }
      ],
      "reviewedModules": [
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/schedule_input_collector.py",
        "core/services/scheduler/schedule_orchestrator.py",
        "core/algorithms/greedy/scheduler.py",
        "core/algorithms/greedy/auto_assign.py",
        "core/services/scheduler/schedule_input_builder.py",
        "core/algorithms/greedy/external_groups.py",
        "core/services/scheduler/schedule_optimizer.py"
      ],
      "recommendedNextAction": "继续审查 `dispatch_sgs()`、`batch_order.py`、`downtime.py` 与计划中的 `runtime_state.py` 抽象，重点核对状态更新语义是否会在 seed 预热场景发生漂移。",
      "findingIds": [
        "F11"
      ]
    },
    {
      "id": "M2",
      "title": "第二轮：SGS、批次派工、时间线与运行期状态收口审查",
      "status": "completed",
      "recordedAt": "2026-04-07T09:05:38.758Z",
      "summaryMarkdown": "已复核 `dispatch_sgs()`、`dispatch_batch_order()`、`downtime.py` 以及 `scheduler.py` 中 seed 预热逻辑。结论：任务 2 对评分链路同源化、任务 3 对时间线有序化的主方向是对的，现有 `candidates[0]` 兜底、评分期广域吞异常、时间线每次排序等问题都值得收掉；但 `runtime_state.py` 的抽象文本仍少了一条非常关键的细语义：seed 预热分支在 `op_type_name` 为空时，当前代码连 `last_end_by_machine` 都不会推进，而派工成功分支则会先推进 `last_end_by_machine`、只跳过 `last_op_type_by_machine` 更新。若只用 `conditional_op_type=True/False` 两态去实现，而没有把“seed 空工种名完全跳过最近状态更新”写进 plan 和测试，实施者极易把两种语义揉平，导致换型 tie-break 在带空工种 seed 的场景发生漂移。",
      "conclusionMarkdown": "任务 2 与任务 3 基本可实施，但 `runtime_state.py` 的共享函数契约还需再收紧一次：不仅要区分 seed 与正式派工，还要把 seed 场景下“空工种名不推进最近状态”的现有语义显式编码并补测试。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 289,
          "lineEnd": 304,
          "symbol": "GreedyScheduler.schedule"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py",
          "lineStart": 90,
          "lineEnd": 106,
          "symbol": "dispatch_batch_order"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 458,
          "lineEnd": 475,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "core/algorithms/greedy/downtime.py",
          "lineStart": 20,
          "lineEnd": 28,
          "symbol": "occupy_resource"
        },
        {
          "path": "core/algorithms/greedy/downtime.py",
          "lineStart": 31,
          "lineEnd": 77,
          "symbol": "find_earliest_available_start/find_overlap_shift_end"
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
          "path": "core/algorithms/greedy/scheduler.py"
        }
      ],
      "reviewedModules": [
        "core/algorithms/greedy/dispatch/sgs.py",
        "core/algorithms/greedy/dispatch/batch_order.py",
        "core/algorithms/greedy/downtime.py",
        "core/algorithms/greedy/scheduler.py"
      ],
      "recommendedNextAction": "继续审查任务 4 与任务 5，重点检查日期统一是否真的覆盖全部算法输入字段，以及优化器“消重”是否仍有明显漏项。",
      "findingIds": [
        "F12"
      ]
    },
    {
      "id": "M3",
      "title": "第三轮：日期工具收口与优化器消重完整性审查",
      "status": "completed",
      "recordedAt": "2026-04-07T09:06:13.766Z",
      "summaryMarkdown": "已复核 `date_parsers.py`、`evaluation.py`、`dispatch_rules.py`、`ortools_bottleneck.py`、`schedule_optimizer.py`、`schedule_optimizer_steps.py`、`schedule_summary.py`、`report/calculations.py` 与 `sort_strategies.py`。结论：任务 4 在“把算法层 due_date 相关重复实现并回 `greedy/date_parsers.py`”这件事上方向正确；但任务 5 对优化器重复工作的削减仍不够彻底。当前 `_run_multi_start()` 的重复不仅来自 `dispatch_rule`，同一 `strategy/params0` 在不同 `dispatch_mode` 下也会重复构造完全相同的 `order`。另外，计划虽然要求 `_run_local_search()` 加 `seen_hashes`，但没有把“应先把当前 best 的 `order` 放进 seen 集合”写出来，实施者若只按字面做空集合去重，当前基线顺序仍可能被当作新邻域执行一次，去重效果并不完整。",
      "conclusionMarkdown": "任务 4 可继续按现方向推进；任务 5 需要再补两条实现约束，才能称得上真正把优化器里的明显重复工作收干净。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py",
          "lineStart": 300,
          "lineEnd": 335,
          "symbol": "_run_multi_start"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 464,
          "lineEnd": 522,
          "symbol": "optimize_schedule"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 128,
          "lineEnd": 181,
          "symbol": "_run_local_search"
        },
        {
          "path": "core/algorithms/greedy/date_parsers.py",
          "lineStart": 7,
          "lineEnd": 41,
          "symbol": "parse_date/parse_datetime"
        },
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
          "path": "core/algorithms/greedy/date_parsers.py"
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
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/scheduler/schedule_summary.py"
        },
        {
          "path": "core/services/report/calculations.py"
        },
        {
          "path": "core/algorithms/sort_strategies.py"
        }
      ],
      "reviewedModules": [
        "core/algorithms/greedy/date_parsers.py",
        "core/algorithms/evaluation.py",
        "core/algorithms/dispatch_rules.py",
        "core/algorithms/ortools_bottleneck.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/scheduler/schedule_optimizer_steps.py",
        "core/services/scheduler/schedule_summary.py",
        "core/services/report/calculations.py",
        "core/algorithms/sort_strategies.py"
      ],
      "recommendedNextAction": "汇总三轮 findings，给出是否可按现状执行的最终判断，并明确哪些属于实施前必须先修 plan 的项。",
      "findingIds": [
        "F13",
        "F14"
      ]
    }
  ],
  "findings": [
    {
      "id": "F11",
      "severity": "high",
      "category": "other",
      "title": "非 due_date 日期边界遗漏",
      "descriptionMarkdown": "当前 plan 的任务 4 只显式处理 `due_exclusive()`、非严格 `parse_date()` / `parse_datetime()` 与 `due_date` 的严格包装，但算法实际还消费了 `ready_date` 与 `created_at`。现状里有两层残留风险：1）`GreedyScheduler.schedule()` 在严格模式下只对 `due_date` 用 `parse_optional_date(..., field=\"due_date\")`，`ready_date` 与 `created_at` 仍走非严格解析，坏值会静默变成 `None`；其中 `ready_date` 直接决定 `batch_progress` 的最早开工下界，坏值会让批次失去齐套下界。2）`ready_date` 初始化后调用 `calendar.adjust_to_working_time()` 时又有一层广域 `except Exception`，异常会静默回退到午夜 `dt0`。这条回退再叠加外协工序直接使用 `batch_progress` 作为 `prev_end` 的事实，会让外协工序在日历异常时悄悄提前起排。也就是说，即便任务 1~5 全部按 plan 落地，算法层仍不能彻底摆脱“日期边界不完整 + 静默回退”的残留口子。",
      "recommendationMarkdown": "把任务 4 的边界说明从“只处理 due_date”提升为“显式声明其他日期字段是否接受静默降级”。若目标仍是消除算法层静默日期回退，至少应补两件事：一是给 `ready_date`、`created_at` 增加字段级严格/非严格包装，不再复用 `due_date` 名义；二是去掉 `scheduler.py:234-236` 这类日历异常后直接回退到 `dt0` 的静默逻辑，至少改成显式 warning + 统一计数，或在严格模式直接抛错。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 138,
          "lineEnd": 146,
          "symbol": "GreedyScheduler.schedule"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 228,
          "lineEnd": 237,
          "symbol": "GreedyScheduler.schedule"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 335,
          "lineEnd": 368,
          "symbol": "optimize_schedule"
        },
        {
          "path": "core/algorithms/greedy/external_groups.py",
          "lineStart": 35,
          "lineEnd": 45,
          "symbol": "schedule_external"
        },
        {
          "path": "core/algorithms/greedy/external_groups.py",
          "lineStart": 120,
          "lineEnd": 121,
          "symbol": "schedule_external"
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
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py"
        },
        {
          "path": "core/algorithms/greedy/external_groups.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F12",
      "severity": "medium",
      "category": "javascript",
      "title": "seed 空工种名语义未写入 runtime_state 契约",
      "descriptionMarkdown": "当前代码里，seed 预热与正式派工对“最近工种/最近结束时间”的更新并不只是 `conditional_op_type=True/False` 这么简单。`scheduler.py:299-304` 的 seed 分支有 `if mid and ot and sr.end_time:` 这个联合前提，意味着只要 `op_type_name` 为空，seed 连 `last_end_by_machine` 都不会更新；而 `batch_order.py:95-106` 与 `sgs.py:463-475` 的正式派工分支会先更新 `last_end_by_machine`，然后仅在 `ot` 非空时更新 `last_op_type_by_machine`。这两个语义如果被共享函数不小心揉成“seed 只做条件覆盖、正式派工做直接更新”，但没有显式保留空工种名分支，带空 `op_type_name` 的 seed 就会把机器最近结束时间推进到更晚，反过来压住后面合法 seed 的工种信息，最终改变 `dispatch_sgs()` 与自动分配里的换型惩罚判断。当前 plan 的任务 3 已经覆盖了条件覆盖/直接更新两种主模式，但还没把这条更细的空工种名语义写成实现约束或回归用例。",
      "recommendationMarkdown": "把任务 3 的共享函数说明再细化一层：seed 模式下若 `op_type_name` 为空，则 `last_end_by_machine` 与 `last_op_type_by_machine` 都不更新；正式派工模式下则继续保持“`last_end_by_machine` 条件更新、`last_op_type_by_machine` 仅在非空时直接更新”。同时在 `tests/regression_downtime_timeline_ordered_insert.py` 或单独回归里补一个“更晚 seed 但空工种名不应覆盖最近状态”的用例。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 299,
          "lineEnd": 304,
          "symbol": "GreedyScheduler.schedule"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py",
          "lineStart": 95,
          "lineEnd": 106,
          "symbol": "dispatch_batch_order"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 463,
          "lineEnd": 475,
          "symbol": "dispatch_sgs"
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
          "path": "core/algorithms/greedy/scheduler.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F13",
      "severity": "medium",
      "category": "performance",
      "title": "_run_multi_start 去重只覆盖 dispatch_rule",
      "descriptionMarkdown": "当前 plan 的任务 5 只要求把 `order = build_order(strat, params0)` 从 `for dr in dispatch_rules` 内层提升到 `for k in keys` 内层，但 `_run_multi_start()` 的真实重复并不止这一层。`order` 只依赖 `strategy/params0`，与 `dispatch_mode` 同样无关；而 `optimize_schedule()` 在 improve 模式下会显式构造多个 `dispatch_mode`（`batch_order` 与 `sgs`），因此即便按 plan 完成，系统仍会在每个 `dispatch_mode` 下为同一个 `strategy/params0` 重建一次完全相同的 `order`。这意味着任务 5 宣称的“消掉同一排序策略下重复构造 order 的开销”实际上只消掉了一半。",
      "recommendationMarkdown": "把任务 5 的 `build_order()` 优化升级为显式缓存：键至少使用 `(strategy.value, tuple(sorted(params0.items())))`，并在 `dispatch_mode` 与 `dispatch_rule` 两层循环外复用。对应回归也应从“不因不同 dispatch_rule 重复执行”提升为“不因不同 dispatch_mode / dispatch_rule 重复执行”。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py",
          "lineStart": 300,
          "lineEnd": 335,
          "symbol": "_run_multi_start"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 464,
          "lineEnd": 522,
          "symbol": "optimize_schedule"
        },
        {
          "path": "core/algorithms/greedy/date_parsers.py"
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
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/scheduler/schedule_summary.py"
        },
        {
          "path": "core/services/report/calculations.py"
        },
        {
          "path": "core/algorithms/sort_strategies.py"
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F14",
      "severity": "low",
      "category": "performance",
      "title": "local_search 去重未显式预热当前顺序",
      "descriptionMarkdown": "任务 5 计划给 `_run_local_search()` 增加 `seen_hashes`，但文本没有写明应当先把 `cur_order`（也就是当前 best 的顺序）放入去重集合。当前实现里，邻域生成存在多处回退：`insert` 可能选到原位，`block` 可能回插原位，代码随后再做一次 `swap_fallback`。如果实施者只按字面新增一个空的 `seen_hashes`，那么“与当前 best 完全相同的顺序”仍可能在第一次命中时被当作新邻域送进 `_schedule_with_optional_strict_mode()`，这会让去重机制漏掉最基础的一类重复。问题不大，但会让任务 5 的收益打折。",
      "recommendationMarkdown": "在任务 5 的实现说明中补一句：`seen_hashes` 初始化时先写入 `tuple(cur_order)`，并在每次接受更优解、执行 shake 后继续沿用同一个集合。若希望更彻底，还可以把已记录的 candidate 顺序同步进回归桩里，防止“等价邻域”被反复执行。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 128,
          "lineEnd": 181,
          "symbol": "_run_local_search"
        },
        {
          "path": "core/algorithms/greedy/date_parsers.py"
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
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/scheduler/schedule_summary.py"
        },
        {
          "path": "core/services/report/calculations.py"
        },
        {
          "path": "core/algorithms/sort_strategies.py"
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:7ad881b76c71636117a783938accb965acd41486c976938c2b298dc39a3ec0b2",
    "generatedAt": "2026-04-07T09:06:45.799Z",
    "locale": "zh-CN"
  }
}
```
