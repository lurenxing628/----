# 算法层统一估算与派工重构plan三轮深度审查_第五轮核验
- 日期: 2026-04-07
- 概述: 对 plan 进行三轮深度审查：目标可达性、实现严谨性、潜在BUG与遗漏
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# 算法层统一估算与派工重构 plan 三轮深度审查（第五轮核验）

**审查日期**：2026-04-08
**审查范围**：`.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md` 及其引用链涉及的全部源文件
**审查方法**：逐条对照 plan 声明 → 源代码实际行为 → 逻辑推演可达性与副作用

---

## 审查结构

- **第一轮**：目标可达性与架构完整性 — 检验五个任务的分解是否能真正达成完成判定
- **第二轮**：实施细节严谨性 — 逐步骤检验是否存在过度兜底、静默回退、逻辑漏洞
- **第三轮**：潜在BUG、边界竞态与遗漏 — 检查 plan 未覆盖但代码中实际存在的风险

## 评审摘要

- 当前状态: 已完成
- 已审模块: core/algorithms/greedy/scheduler.py, core/algorithms/greedy/auto_assign.py, core/algorithms/greedy/dispatch/sgs.py, core/algorithms/greedy/dispatch/batch_order.py, core/algorithms/greedy/downtime.py, core/algorithms/greedy/date_parsers.py, core/algorithms/evaluation.py, core/algorithms/dispatch_rules.py, core/algorithms/ortools_bottleneck.py, core/services/common/strict_parse.py, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_optimizer_steps.py
- 当前进度: 已记录 3 个里程碑；最新：M3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 17
- 问题严重级别分布: 高 4 / 中 7 / 低 6
- 最新结论: ## 三轮深度审查总结 本次审查共完成三轮，覆盖 12 个核心模块，发现 **17 处问题**（高 4 / 中 7 / 低 6）。 ### 总体评价 plan 是一份**高质量的重构方案**——架构拆分清晰、任务依赖关系正确、暂停门槛设计合理、完成判定可验证。plan 对代码现状的理解与引用链描述与源代码实际行为高度一致，修订前提12条全部经核实准确。五个任务的分解能够达成全部九项完成判定。 ### 必须在实施前修正的高严重度问题（4项） 1. **R1-F02 / R1-F05**：`schedule_optimizer.py` 的 `_parse_date()` 对 `ready_date` 硬编码了 `field='due_date'`，plan 已正确识别此 BUG 并在暂停条件中列出——确认修复方向正确。但 `scheduler.py:228-229` 与 `scheduler.py:145` 两处 `ready_date` 解析也需要同步改造（R1-F04），plan 步骤中未显式列出这两处。 2. **R2-F04**：`sgs.py` 评分阶段第 360 行的广域 `except Exception` 是当前最大的静默回退源头。plan 的核心价值主张之一就是消除它。拆分后的评分函数必须严格只对五类业务不可估算场景做显式降级，不得保留广域异常兜底。 3. **R3-F04**：`optimize_schedule()` 中 `batch_for_sort` 的构造（第 359 行）早于 `keys` 的确定（第 399 行）。plan 要求根据 `keys` 是否包含 `fifo` 来决定 `created_at` 的 strict 校验——但这在当前执行顺序下无法实现。**实施时必须调整代码执行顺序**。 ### 需要在实施时注意的中等严重度问题（7项） - `validate_internal_hours()` 对 `quantity=0` 的零工时场景需在测试中显式覆盖（R1-F01） - seed 预热中 `last_end_by_machine` 与 `last_op_type_by_machine` 的原子绑定语义需在 `runtime_state.py` 中正确实现（R1-F03） - `scheduler.py:228` 的 `_parse_date(rd)` 需同步替换为字段级 strict 包装（R1-F04） - 拆分后的评分函数必须保证每条路径都返回明确的评分键（R2-F01） - 效率读取的测试必须使用替身日历绕过引擎层的 `or 1.0`（R2-F07） - `sgs.py` 评分阶段 `probe_only` 探测的双层 `except Exception` 必须全部移除（R3-F02） - 局部搜索去重中 `it += 1` 必须在去重判断之前执行以保证终止性（R3-F03） ### 审查结论 plan **有条件通过审查**。在修正上述 4 项高严重度问题后可以开始实施。其中 R3-F04（`batch_for_sort` 构造时序）是最容易被遗漏的隐蔽问题——如果不调整执行顺序，`created_at` 的策略相关 strict 校验将无法按 plan 设计工作。
- 下一步建议: 修正 plan 中的 4 项高严重度问题后开始实施：（1）在任务4步骤4中补充 scheduler.py:228 和 scheduler.py:145 两处 ready_date 解析的修改说明；（2）在任务4步骤4-3中补充执行顺序约束——keys 必须在 batch_for_sort 构造前确定；（3）在任务2步骤3中明确 probe_only 探测的双层 except 处理方案
- 总体结论: 有条件通过

## 评审发现

### validate_internal_hours 对 quantity=0 的零工时场景存在歧义

- ID: R1-F01
- 严重级别: 中
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  plan 要求 `validate_internal_hours()` 在 `total_hours_base` 非有限或为负时抛 `ValueError`，但允许零工时（步骤1-6要求 `start_time == end_time` 且不报错）。然而 `total_hours_base = 0.0` 既可能来自 `setup_hours=0 + unit_hours=0`（合法零时长工序），也可能来自 `quantity=0`（逻辑上可疑的零数量批次）。plan 对这两种情况未做区分，统一允许返回零工时。

  当前代码 `scheduler.py:480` 的行为是允许零工时通过（只拒绝负数和非有限值），所以 plan 在此处保持了行为兼容。但 `auto_assign.py:110` 也允许零工时通过，并会为零工时工序完成一次「选择最佳设备/人员」的全量扫描——这在语义上是否正确值得考量。

  建议：在 plan 的测试用例中补充 `quantity=0` 且 `unit_hours > 0` 的场景，显式声明此时 `validate_internal_hours()` 返回 0.0 是期望行为，并在自动分配路径中确认零工时候选评估的早停语义。
- 建议:

  在 `tests/regression_internal_slot_estimator_consistency.py` 的步骤1-6中增加 `quantity=0, unit_hours=1.0` 的子场景
- 证据:
  - `core/algorithms/greedy/scheduler.py:476-488`
  - `core/algorithms/greedy/auto_assign.py:102-112`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`

### 避让上界公式在自动分配场景下存在时间线不一致风险

- ID: R1-F02
- 严重级别: 高
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  plan 任务1步骤3-6规定避让上界为 `len(machine_timeline[mid]) + len(operator_timeline[oid]) + len(downtime_segments) + 1`。但 `auto_assign_internal_resources()` 会为每个候选 `(mid, oid)` 组合调用 `estimate_internal_slot()`，且不同组合使用同一个 `machine_timeline` 和 `operator_timeline`。

  关键问题：在同一轮自动分配调用中，`machine_timeline` 和 `operator_timeline` 不会被当前候选组合的估算过程修改（因为 `internal_slot.py` 只估算不占用），所以不同候选组合看到的片段数相同。但一轮 `dispatch_sgs()` 的多次迭代中，前一次迭代可能已经通过 `occupy_resource()` 新增了片段。因此上界在估算时是正确的——每次调用 `estimate_internal_slot()` 时所看到的片段数就是当时的真实片段数。

  然而，需要注意：`downtime_segments` 在整个排产过程中不会变化（由 `resource_pool_builder.py` 预构建），但 `machine_timeline[mid]` 和 `operator_timeline[oid]` 在 seed 预热后可能已经包含大量片段。如果 seed 结果有 200+ 条同一设备的片段，上界就会超过 200，这正是 plan 要消除固定 200 次上界的核心动机。

  这条本身不是 BUG 而是对 plan 正确性的确认：上界公式在此场景下是正确的。但需要确认 plan 实施时 `estimate_internal_slot()` 的避让循环确实以调用时的当前片段长度为上界，而不是预先计算一次就固定。
- 建议:

  在步骤3实现时明确：上界在 `estimate_internal_slot()` 入口计算一次即可（因为函数内部不修改时间线），但调用方每次调用前时间线可能已变化
- 证据:
  - `core/algorithms/greedy/auto_assign.py:183-206`
  - `core/algorithms/greedy/auto_assign.py`

### seed 预热运行期状态语义在 runtime_state.py 中有隐蔽差异

- ID: R1-F03
- 严重级别: 中
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  plan 任务3步骤4要求 `runtime_state.py` 显式区分 seed 预热与派工成功两种模式。经代码核实，三处运行期更新有以下差异：

  1. **seed 预热**（`scheduler.py:289-304`）：`last_op_type_by_machine` 只在 `mid and ot and sr.end_time` 时更新，且只在 `end_time > prev_end` 时才覆盖——即 seed 中同一设备有多条记录时，取最晚结束的那条的工种。

  2. **batch_order 派工**（`batch_order.py:90-106`）：`last_end_by_machine` 按 `prev_end is None or result.end_time > prev_end` 条件覆盖；但 `last_op_type_by_machine` 只要 `ot` 非空就直接覆盖——不检查 `end_time` 是否更晚。

  3. **sgs 派工**（`sgs.py:458-475`）：同 `batch_order`——`last_end_by_machine` 条件覆盖，`last_op_type_by_machine` 直接覆盖。

  plan 描述的「seed 条件覆盖」与「派工成功直接更新」这两种模式是正确的。但 plan 中的实施约束说「`last_end_by_machine` 条件更新、`last_op_type_by_machine` 仅在非空时直接更新」——这对 batch_order 和 sgs 是准确的。

  然而 seed 预热中 `last_op_type_by_machine` 的更新条件实际是 `mid and ot and sr.end_time` 且 `sr.end_time > prev_end`（第 302-304 行），也就是**工种和结束时间绑定在同一个 if 条件分支里**。这意味着 seed 预热如果有两条记录：第一条 end_time=10:00 op_type=A，第二条 end_time=8:00 op_type=B，那么结果是 last_op_type=A（只取更晚的那条）。而 batch_order/sgs 模式下，如果排产结果按顺序产生 end_time=10:00 op_type=A 然后 end_time=8:00 op_type=B，则 last_op_type=B（直接覆盖）。

  这个差异 plan 已正确识别，但 `runtime_state.py` 的共享函数如果用 `conditional_op_type=True/False` 来区分，需要确保 seed 模式下 `last_end_by_machine` 和 `last_op_type_by_machine` 的更新是原子绑定的——即只有当 `end_time > prev_end` 时才同时更新两个字典。
- 建议:

  在 `runtime_state.py` 的 seed 模式函数中，确保 `last_end_by_machine` 和 `last_op_type_by_machine` 在同一条件分支内原子更新
- 证据:
  - `core/algorithms/greedy/scheduler.py:299-304`
  - `core/algorithms/greedy/dispatch/batch_order.py:90-106`
  - `core/algorithms/greedy/dispatch/sgs.py:458-475`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/dispatch/batch_order.py`
  - `core/algorithms/greedy/dispatch/sgs.py`

### 任务4对 ready_date 的 strict 包装在 scheduler.py 中缺少实际触达路径

- ID: R1-F04
- 严重级别: 中
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  plan 任务4步骤4-2要求 `scheduler.py` 中 `ready_date` 在 strict 模式下使用 `field='ready_date'` 的包装。但 `scheduler.py:228-229` 当前使用的是从 `schedule_params.py` 转导出的 `_parse_date(rd)`，这个函数内部调用的是 `core.algorithms.greedy.date_parsers.parse_date()`——一个永不抛异常的非严格解析器。

  当前 `scheduler.py:138` 在构造 `BatchForSort` 时已经分别处理了 `due_date` 的 strict/non-strict 模式，但 `ready_date`（第 145 行）始终使用 `_parse_date()`（非严格），`created_at`（第 146 行）始终使用 `_parse_datetime()`（非严格）。

  这意味着：**当前代码中 `ready_date` 的解析从未走过 strict 路径**。plan 任务4要给 `ready_date` 加上 strict 路径——既要在构造 `BatchForSort` 时加，也要在 `scheduler.py:228-229` 的 `batch_progress` 初始化处加。但 plan 只提到了构造 `BatchForSort` 的场景（步骤4-2），没有明确提到 `scheduler.py:228-229` 这处也需要同步改造。

  如果 `scheduler.py:228-229` 不改，那么 `ready_date` 在 strict 模式下可能通过了 `BatchForSort` 构造，却在 `batch_progress` 初始化时使用了不同的解析函数——导致解析结果不一致。
- 建议:

  在任务4步骤4中显式列出 `scheduler.py:228-229` 的 `_parse_date(rd)` 也需要替换为字段级 strict 包装
- 证据:
  - `core/algorithms/greedy/scheduler.py:228-237`
  - `core/algorithms/greedy/scheduler.py:138-146`
  - `core/algorithms/greedy/scheduler.py`

### optimize_schedule 中 _parse_date 对 ready_date 使用 field='due_date' 标签

- ID: R1-F05
- 严重级别: 高
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  plan 任务4暂停条件明确列出：「`schedule_optimizer.py` 解析坏 `ready_date` 仍以 `due_date` 名义报错」。

  经代码核实，`schedule_optimizer.py:335-341` 的 `_parse_date()` 函数硬编码了 `field='due_date'`，但第 367 行用 `_parse_date(getattr(b, 'ready_date', None))` 解析 `ready_date`——这意味着如果 strict 模式下 `ready_date` 不合法，报错信息会说 `due_date 格式不合法` 而不是 `ready_date 格式不合法`。

  这是一个现存 BUG，plan 正确地识别了它，并在任务4步骤4-2中要求拆成 `_parse_due_date()` 和 `_parse_ready_date()` 两个字段级包装。这条发现确认 plan 的修复方向正确。

  但进一步检查发现，`scheduler.py:138` 的 `due_date` strict 包装使用 `parse_optional_date(due_raw, field='due_date')`，而 `ready_date`（第 145 行）使用 `_parse_date()`（非严格，永不抛异常）。这意味着当前代码中 **`scheduler.py` 侧的 `ready_date` 在 strict 模式下不会报错**，但 `schedule_optimizer.py` 侧的 `ready_date` 在 strict 模式下会以 `due_date` 名义报错。两侧行为不一致。
- 建议:

  任务4必须同步修改 `scheduler.py:145` 和 `schedule_optimizer.py:367` 两处
- 证据:
  - `core/services/scheduler/schedule_optimizer.py:335-341`
  - `core/services/scheduler/schedule_optimizer.py:365-368`
  - `core/algorithms/greedy/scheduler.py:138-146`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/algorithms/greedy/scheduler.py`

### multi_start 中 build_order 确实在最内层循环重复执行

- ID: R1-F06
- 严重级别: 低
- 分类: 性能
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  plan 任务5断言 `build_order()` 在 `dispatch_mode` / `dispatch_rule` 内层循环重复执行。经 `schedule_optimizer_steps.py:331-334` 核实：`for dr in dispatch_rules:` 是 `for k in keys:` 的内层循环，`order = build_order(strat, params0)` 在第 334 行，位于 `dr` 循环内部。由于 `strat` 和 `params0` 在同一个 `k` 下不变，`build_order(strat, params0)` 每次返回值相同——确实是重复构造。

  但需要注意：`build_order` 实际调用的是 `_build_order()`（`schedule_optimizer.py:372-374`），它会创建一个新的 `StrategyFactory.create(strategy0, **(params or {}))` 并调用 `.sort()`。排序的输入 `batch_for_sort` 在整个 `optimize_schedule()` 调用期间不变。所以这确实是可以安全缓存的。

  但 `dispatch_rules` 循环也嵌套在 `for dm in dispatch_modes:` 内。如果 `keys` 有 4 个策略，`dispatch_modes` 有 2 个，`dispatch_rules` 有 3 个，那么同一个 `(strat, params0)` 组合最多被 `build_order()` 调用 2 * 3 = 6 次。plan 的缓存键 `(strategy.value, tuple(sorted(params0.items())))` 可以正确消除这些重复。
- 建议:

  确认无问题，plan 的优化方案正确
- 证据:
  - `core/services/scheduler/schedule_optimizer_steps.py:300-350`
  - `core/services/scheduler/schedule_optimizer_steps.py`

### sgs.py 中 candidates[0] 死代码删除后必须保证评分函数无静默跳过路径

- ID: R2-F01
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  plan 任务2步骤3-5要求：「`best_pair = candidates[0]` 属于死代码，必须直接删除」。经 `sgs.py:424-425` 核实，这行代码的确是死代码：在当前评分逻辑下，每个候选都会产生一个 key（无论正常还是降级），所以 `best_pair` 不会为 `None`。

  但这行死代码实际上是最后一道安全网——如果拆分后的 `_score_internal_candidate()` 或 `_score_external_candidate()` 在某些边界情况下没有返回 key，`best_pair` 就会为 `None`。

  plan 的策略是正确的（删除死代码，而不是保留它作为安全网），但实施时必须确保：拆分后的评分函数**总是**返回一个 key（要么正常要么降级），不存在「既不返回又不抛异常」的路径。
- 建议:

  在拆分后的 `_score_internal_candidate()` 和 `_score_external_candidate()` 中，确保每条路径都返回明确的 key 或抛出明确的异常，消除所有「静默跳过」路径
- 证据:
  - `core/algorithms/greedy/dispatch/sgs.py:424-425`
  - `core/algorithms/greedy/dispatch/sgs.py`

### sgs.py 的 avg_proc_hours 初始化段未被纳入导入清理前提

- ID: R2-F02
- 严重级别: 低
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  plan 任务2步骤3-6规定导入清理时序：「`parse_required_float` 仅在 `_build_unscorable_dispatch_key(...)` 与 `_score_internal_candidate(...)` 两条路径都彻底替换完成后才允许删除」。

  但 `parse_required_float` 当前还被 `sgs.py:92-94` 的 `avg_proc_hours` 初始化段使用。plan 步骤3-3 要求这里改用 `validate_internal_hours(op, batch)` 作为取样入口。但如果步骤3-3 的实施先于步骤3-6 的导入清理，那么 `parse_required_float` 的删除实际取决于步骤3-3 的完成。

  潜在风险：如果实施者先删除 `parse_required_float` 导入再改 `avg_proc_hours` 初始化，会导致中间版本编译失败。plan 已明确说「先替换再删除」，但没有明确将 `avg_proc_hours` 初始化段纳入导入清理的前提条件。
- 建议:

  在步骤3-6 的导入清理时序中明确列出：`parse_required_float` 的删除前提还包括 `avg_proc_hours` 初始化段的替换
- 证据:
  - `core/algorithms/greedy/dispatch/sgs.py:91-102`
  - `core/algorithms/greedy/dispatch/sgs.py`

### auto_assign.py 中 _scaled_hours 闭包变量陷阱在重构后自然规避

- ID: R2-F03
- 严重级别: 低
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  plan 任务1步骤4 要求删除 `auto_assign.py` 中本地 `_scaled_hours()` 与避让循环。经核实，`auto_assign.py:163-175` 的 `_scaled_hours()` 是一个在 `for oid in op_candidates:` 循环内定义的闭包函数，它通过默认参数 `_oid=oid` 来捕获当前循环变量。

  这是一个常见的闭包变量陷阱解决方案：`_oid=oid` 确保每次循环都创建一个新的 `_scaled_hours` 闭包，且每个闭包捕获的是当前迭代的 `oid` 值。

  当 plan 把 `_scaled_hours` 替换为 `estimate_internal_slot(...)` 时，这个闭包会被删除。但必须确保 `estimate_internal_slot(...)` 的 `operator_id` 参数是由调用方显式传入的（而不是通过闭包捕获），这样就自然避免了闭包陷阱。plan 已要求 `estimate_internal_slot()` 接受显式的 `operator_id` 参数，所以这个闎险已被规避。
- 证据:
  - `core/algorithms/greedy/auto_assign.py:163-175`
  - `core/algorithms/greedy/auto_assign.py`

### sgs.py 评分阶段的广域 except 是当前最大的静默回退源头

- ID: R2-F04
- 严重级别: 高
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  `sgs.py` 当前的评分阶段在第 360 行有一个大区域 `except Exception:`，它会捕获**所有**未被内层 `except` 捕获的异常（包括真正的程序错误如 `AttributeError`、`KeyError`、`NameError`），并把它们变成降级评分键。

  plan 任务2步骤3-4 要求「只有五类业务不可估算情况可以构造降级评分键」，并明确要求「探测返回形状错误、代码调用错误、实现异常等意外问题不得再变成最差 key」。

  这是 plan 的核心价值主张之一，完全正确。但实施时必须小心：

  1. 拆分后的 `_score_internal_candidate()` 和 `_score_external_candidate()` 不能再包广域 `except Exception`。
  2. 主函数 `dispatch_sgs()` 的 `for bid, op in candidates:` 循环内部不能再包广域 `try/except`。
  3. 当前第 489 行的外层 `except Exception as e:` 是捕获执行阶段的异常，这个应该保留（因为执行阶段的异常需要写入 errors 并阻断批次）。

  实施时必须确保：评分阶段的意外异常在 `strict_mode=True` 时上浮，在 `strict_mode=False` 时也应该通过计数器可见（但不是变成降级 key）。
- 建议:

  在拆分后的评分函数中，只对五类明确的业务不可估算场景做显式处理，意外异常在 non-strict 模式下通过计数器暴露但不降级
- 证据:
  - `core/algorithms/greedy/dispatch/sgs.py:360-418`
  - `core/algorithms/greedy/dispatch/sgs.py`

### 局部搜索去重的 seen_hashes 在大规模场景下内存占用可接受

- ID: R2-F05
- 严重级别: 低
- 分类: 性能
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  plan 任务5步骤4 要求 `_run_local_search()` 新增 `seen_hashes`，键为 `tuple(cand_order)`。在大规模排产中，`cand_order` 可能包含数百到数千个批次，而 `it_limit` 最高 5000 次。

  内存估算：假设 500 个批次、每个批次 ID 平均 10 字符，每个 tuple 约 500 * 10 * 8 = 40KB。 5000 次迭代的 `seen_hashes` 最多占 200MB。

  这对于单机单用户环境是可接受的，但需要注意：plan 要求 shake 后「允许做轻量重置（清空后立即写回当前 `cur_order`，并补写 `tuple(best.get('order', []))`）」。这个重置会释放大部分内存，因此实际峻值会远小于上述估算。

  但 `restart_after` 可能为 800（当 `it_limit=6400` 时），意味着在两次 shake 之间最多积累 800 个 tuple，占约 32MB。这是可接受的。
- 建议:

  可以接受，但建议在实施时加一行日志记录 `len(seen_hashes)` 的峻值，以便后续监控
- 证据:
  - `core/services/scheduler/schedule_optimizer.py:128-260`
  - `core/services/scheduler/schedule_optimizer.py`

### downtime.py 中 find_earliest_available_start 的静默回退未被 plan 纳入清理范围

- ID: R2-F06
- 严重级别: 低
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  `downtime.py:36-39` 的 `find_earliest_available_start()` 中有一个对 `duration_hours` 的静默回退：
  ```python
  try:
      dur = float(duration_hours)
  except Exception:
      dur = 0.0
  ```

  这意味着如果 `duration_hours` 是字符串「'abc'」或其他不可转换类型，它会被静默变成 0.0，然后因 `dur <= 0` 直接返回 `base_time`——相当于「没有占用」。

  plan 任务3将修改 `find_earliest_available_start()` 使其去掉内部 `sorted()`，但没有要求清理这个 `except Exception`。由于 plan 的实施约束说「不新增广域 `except Exception: pass`」但未要求删除现有的，且 `find_earliest_available_start()` 在任务2完成后可能被删除（「顺序链式近似评分路径彻底消失后删除」），所以这个静默回退可能会自然消失。

  但如果任务2完成后 `find_earliest_available_start()` 仍被其他地方使用，这个静默回退就会保留下来。
- 建议:

  确认任务2完成后 `find_earliest_available_start()` 是否仍有调用方；若仍保留则应把这个 `except Exception` 纳入完成判定的「未触达残留」类目
- 证据:
  - `core/algorithms/greedy/downtime.py:36-41`
  - `core/algorithms/greedy/downtime.py`

### 效率读取的三处静默回退与引擎层双重回退问题

- ID: R2-F07
- 严重级别: 中
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  plan 任务1步骤3-4 要求「读取效率时必须使用显式 `raw_eff is not None` 判断，不使用 `or 1.0`」。经核实当前代码中效率读取有三处：

  1. `scheduler.py:494`：`float(self.calendar.get_efficiency(start, operator_id=operator_id) or 1.0)` —— 使用 `or 1.0`，**是**静默回退。
  2. `auto_assign.py:166-167`：`raw_eff is not None` —— **正确**的显式判断。
  3. `sgs.py:323`：`float(scheduler.calendar.get_efficiency(...) or 1.0)` —— 使用 `or 1.0`，**是**静默回退。

  但 `auto_assign.py:168-169` 外层还有 `except Exception: eff = 1.0`，它会把 `get_efficiency()` 抛出的程序错误也吞掉。

  plan 已明确要求消除这些静默回退：
  - `scheduler.py:494` 中的 `or 1.0` → 使用 `raw_eff is not None`
  - `sgs.py:323` 中的 `or 1.0` → 同上
  - `auto_assign.py:168-169` 的 `except Exception` → 删除

  但修订前提9注意到 `CalendarEngine.get_efficiency()` 自身也有 `or 1.0`，所以算法层即使去掉 `or 1.0`，实际拿到的值仍然被引擎层抄底过了。plan 明确说「本轮只消除算法层冗余静默回退，不扩到引擎层」。

  这是一个已记录的取舱，不是 BUG。但意味着任务1的测试用例如果注入 `get_efficiency()` 返回 `0.0`，实际可能被引擎层的 `or 1.0` 截断，导致测试无法真正触发算法层的效率处理逻辑。

  因此 plan 步骤1-5 的测试用例必须用替身日历的 `get_efficiency()` 直接返回 `0.0`（而不是经过 `CalendarEngine`）才能真正验证算法层的处理逻辑。plan 已要求「通过替身日历 / 替身对象直接向算法层注入」，所以测试设计是正确的。
- 建议:

  确认无问题：测试用例必须用替身日历直接返回 0.0 而不是经过 CalendarEngine
- 证据:
  - `core/algorithms/greedy/scheduler.py:491-496`
  - `core/algorithms/greedy/auto_assign.py:163-169`
  - `core/algorithms/greedy/dispatch/sgs.py:321-327`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/algorithms/greedy/dispatch/sgs.py`

### sgs.py:97 的 isinstance(exc, Exception) 判断永远为 True

- ID: R3-F01
- 严重级别: 低
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  sgs.py:97 的条件 `strict_mode and isinstance(exc, Exception)` 中，`isinstance(exc, Exception)` 始终为 True，因为 `except Exception as exc` 已经保证了 `exc` 一定是 `Exception` 的实例。这是一个无意义的冗余判断。

  plan 任务2步骤3-3 要求 `avg_proc_hours` 初始化段改用 `validate_internal_hours(op, batch)` 作为取样入口，这会替换掉第 91-99 行的逻辑。但重构时应该确保不会把这个冗余判断带入新代码。
- 建议:

  重构时直接简化为 `if strict_mode: raise`
- 证据:
  - `core/algorithms/greedy/dispatch/sgs.py:96-99`
  - `core/algorithms/greedy/dispatch/sgs.py`

### sgs.py 评分阶段 probe_only 探测的双层异常吐掉所有程序错误

- ID: R3-F02
- 严重级别: 中
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  `sgs.py:252-263` 的评分阶段 `probe_only=True` 自动分配探测有两层嵌套 `except Exception`：

  第一层（258-260行）：捕获探测结果的解构错误（例如 `chosen` 不是 `(list, tuple)` 或长度不足 2）。
  第二层（261-263行）：捕获整个 `_auto_assign_internal_resources` 调用过程中的任何异常。

  两层都只计数然后继续——意味着即使 `auto_assign_internal_resources` 抛出 `TypeError` / `KeyError` 等程序错误，也会被静默忽略，然后 `machine_id` / `operator_id` 保持为空，候选进入「缺资源且无法自动分配」降级路径。

  plan 要求「探测返回形状错误、代码调用错误、实现异常等意外问题不得再变成最差 key」。但 plan 没有明确说明这两层 `except` 应该如何处理：

  1. 内层的探测结果解构错误（`chosen` 不是合法对）是正当的业务不可估算场景吗？不是——如果 `auto_assign_internal_resources` 的返回值不是 `(str, str)` 元组，那是一个接口契约违反，应该被当作实现错误暴露。
  2. 外层的 `except Exception` 更不应该存在——它会吞掉 `auto_assign_internal_resources` 内部的所有程序错误。

  重构后应当：内层不包 `except`（因为 `auto_assign` 的返回类型是 `Optional[Tuple[str, str]]`，如果不是就是实现错误）；外层也不包 `except`（因为 `auto_assign` 内部的程序错误应该显式上浮）。
- 建议:

  plan 实施时应当把这两层 `except Exception` 全部移除，只保留 `chosen is None` 的正常分支判断
- 证据:
  - `core/algorithms/greedy/dispatch/sgs.py:230-263`
  - `core/algorithms/greedy/dispatch/sgs.py`

### 局部搜索去重与迭代计数器的交互需保证终止性

- ID: R3-F03
- 严重级别: 中
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  plan 任务5步骤4 要求「重复跳过不会被计入 `attempts`，但必须继续推进用于触发 `restart_after` 的停滞计数」。

  经检查当前 `_run_local_search()` 的逻辑：`no_improve` 计数器在每次迭代后，如果未改进则 `no_improve += 1`（第 242 行）。当 `no_improve >= restart_after` 时触发 shake（第 245 行）。

  plan 要求重复邻域跳过时：不计入 `attempts`，但**必须**推进 `no_improve`。这意味着即使跳过了实际排产调用，`no_improve` 仍然应该 +1。

  但这里有一个微妙的语义问题：如果重复跳过的邻域不计入 `it`（迭代计数器），那么 `it < it_limit` 的终止条件不会推进，可能导致在小规模场景中无限循环（如果所有可能的邻域都已经被访问过）。

  但经仔细分析，`it` 在 `while` 循环开始时无条件 `+= 1`（第 140 行），所以即使跳过了排产调用，`it` 仍然会推进。这保证了不会无限循环。

  plan 的描述说「不计入 `attempts`」但没说「不计入 `it`」——这是正确的，因为 `it` 应该始终推进以保证终止。
- 建议:

  实施时确保 `it += 1` 在去重判断之前执行，以保证终止条件始终推进
- 证据:
  - `core/services/scheduler/schedule_optimizer.py:139-260`
  - `core/services/scheduler/schedule_optimizer.py`

### optimize_schedule 中 batch_for_sort 构造早于 keys 确定，created_at strict 校验无法依据 keys 判断

- ID: R3-F04
- 严重级别: 高
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  plan 任务4步骤4-3 要求：`optimize_schedule()` 仅当当前轮次实际用于构造排序器的 `keys` 包含 `fifo` 时，才对 `created_at` 使用共享 strict 日期时间包装。

  经 `schedule_optimizer.py:392-399` 核实：
  - `valid_strategies` 是从配置读取的全量策略候选集（默认包含 `fifo`）。
  - `keys` 在 `algo_mode == 'improve'` 时为 `[current_key] + [其他策略]`，即从 `valid_strategies` 中构建。
  - 在 `algo_mode != 'improve'` 时，`keys` 只包含 `[current_key]`。

  关键问题：当 `algo_mode == 'improve'` 时，`keys` 通常包含 `fifo`（因为 `valid_strategies` 默认包含它）。但如果用户显式配置 `VALID_STRATEGIES` 不包含 `fifo`，那么 `keys` 就不包含 `fifo`，`created_at` 的 strict 校验就不应触发。

  plan 的要求完全正确：以 `keys` 而非 `valid_strategies` 为准。但需要注意：在 `algo_mode != 'improve'` 时，`keys = [current_key]`，所以只有当用户显式选择 FIFO 策略时才会触发 `created_at` 的 strict 校验——这是正确的行为。

  但进一步考虑：`batch_for_sort` 的构造（`schedule_optimizer.py:359-370`）发生在 `keys` 确定之前。如果要根据 `keys` 来决定是否对 `created_at` 做 strict 校验，就需要在构造 `batch_for_sort` 时已知道 `keys` 的内容。经检查，`valid_strategies` 在第 392 行确定，`keys` 在第 399 行确定，而 `batch_for_sort` 的构造在第 359-370 行（早于 `keys`）。

  这意味着：如果要根据 `keys` 来决定 `created_at` 的 strict 校验，就需要把 `keys` 的确定提前到 `batch_for_sort` 构造之前，或者把 `created_at` 的 strict 校验延迟到 `batch_for_sort` 构造之后。

  plan 任务4步骤4-3 要求「`optimize_schedule()` 仅当当前轮次实际用于构造排序器的 `keys` 包含 `fifo` 时」——但没有注意到 `batch_for_sort` 的构造在 `keys` 确定之前。实施时需要调整执行顺序。
- 建议:

  plan 实施时必须把 `keys` / `valid_strategies` 的确定提前到 `batch_for_sort` 构造之前，或者延迟 `created_at` 的 strict 校验到 `keys` 确定之后
- 证据:
  - `core/services/scheduler/schedule_optimizer.py:359-401`
  - `core/services/scheduler/schedule_optimizer.py`

## 评审里程碑

### M1 · 第一轮：目标可达性与架构完整性审查

- 状态: 已完成
- 记录时间: 2026-04-07T14:46:31.940Z
- 已审模块: core/algorithms/greedy/scheduler.py, core/algorithms/greedy/auto_assign.py, core/algorithms/greedy/dispatch/sgs.py, core/algorithms/greedy/dispatch/batch_order.py, core/algorithms/greedy/downtime.py, core/algorithms/greedy/date_parsers.py, core/algorithms/evaluation.py, core/algorithms/dispatch_rules.py, core/algorithms/ortools_bottleneck.py, core/services/common/strict_parse.py, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_optimizer_steps.py
- 摘要:

  逐一核验五个任务的分解方案能否真正达成全部九项完成判定。以源代码实际行为为基准，检验 plan 的架构拆分、文件职责划分、引用链覆盖与公开边界约束是否完备。
- 结论:

  第一轮审查确认：plan 的五个任务分解在架构层面基本正确，引用链总览与代码实际一致。主要发现集中在任务4——`ready_date` 的 strict 包装在 `scheduler.py:228-229` 处被遗漏；`schedule_optimizer.py` 的 `_parse_date()` 对 `ready_date` 使用了错误的字段标签。任务1/2/3/5的架构拆分方案合理，完成判定可达。
- 下一步建议:

  进入第二轮审查——逐步骤检验实施细节严谨性
- 问题:
  - [中] JavaScript: validate_internal_hours 对 quantity=0 的零工时场景存在歧义
  - [高] JavaScript: 避让上界公式在自动分配场景下存在时间线不一致风险
  - [中] JavaScript: seed 预热运行期状态语义在 runtime_state.py 中有隐蔽差异
  - [中] JavaScript: 任务4对 ready_date 的 strict 包装在 scheduler.py 中缺少实际触达路径
  - [高] JavaScript: optimize_schedule 中 _parse_date 对 ready_date 使用 field='due_date' 标签
  - [低] 性能: multi_start 中 build_order 确实在最内层循环重复执行

### M2 · 第二轮：实施细节严谨性审查

- 状态: 已完成
- 记录时间: 2026-04-07T14:47:41.139Z
- 已审模块: core/algorithms/greedy/dispatch/sgs.py, core/algorithms/greedy/auto_assign.py, core/algorithms/greedy/downtime.py, core/services/scheduler/schedule_optimizer.py
- 摘要:

  逐步骤检验 plan 中每个任务的实施细节：效率回退层次、评分阶段异常处理、闭包变量陷阱、导入清理时序、局部搜索去重内存影响、downtime.py 静默回退等。重点检查「过度兜底」和「静默回退」在改造后是否能被真正消除。
- 结论:

  第二轮审查发现 plan 在实施细节层面总体严谨，但存在 7 处需要注意的具体问题：sgs.py 中 `candidates[0]` 死代码 plan 已识别但拆分后的导入时序约束可能被忽略；`_scaled_hours` 闭包在 auto_assign 中存在闭包变量陷阱；sgs.py 评分阶段的静默降级嵌套过深，拆分后必须严格保持现有注释中所描述的五类不可估算降级；局部搜索去重的 `seen_hashes` 在大规模排产中可能占用大量内存；`downtime.py:36-39` 的 `find_earliest_available_start` 中 `duration_hours` 坏值仍有静默回退。
- 下一步建议:

  进入第三轮审查——潜在BUG、边界竞态与遗漏
- 问题:
  - [中] 可维护性: sgs.py 中 candidates[0] 死代码删除后必须保证评分函数无静默跳过路径
  - [低] JavaScript: sgs.py 的 avg_proc_hours 初始化段未被纳入导入清理前提
  - [低] JavaScript: auto_assign.py 中 _scaled_hours 闭包变量陷阱在重构后自然规避
  - [高] JavaScript: sgs.py 评分阶段的广域 except 是当前最大的静默回退源头
  - [低] 性能: 局部搜索去重的 seen_hashes 在大规模场景下内存占用可接受
  - [低] JavaScript: downtime.py 中 find_earliest_available_start 的静默回退未被 plan 纳入清理范围
  - [中] JavaScript: 效率读取的三处静默回退与引擎层双重回退问题

### M3 · 第三轮：潜在BUG、边界竞态与遗漏审查

- 状态: 已完成
- 记录时间: 2026-04-07T14:48:29.372Z
- 已审模块: core/algorithms/greedy/dispatch/sgs.py, core/algorithms/greedy/downtime.py, core/algorithms/greedy/scheduler.py, core/services/scheduler/schedule_optimizer.py, core/algorithms/greedy/auto_assign.py
- 摘要:

  检查 plan 未覆盖但代码中实际存在的潜在 BUG、边界竞态与遗漏。重点关注：bisect.insort 在 Python 3.8 的兼容性、sgs.py 评分阶段的冗余判断与双层异常吞没、局部搜索去重的终止性保证、optimize_schedule 中 batch_for_sort 构造与 keys 确定的时序问题。
- 结论:

  第三轮审查完成。发现 4 处 plan 未覆盖的边界问题和潜在BUG：（1）`bisect.insort` 在 Python 3.8 中对元组排序的正确性需要关注——当两个区间起点相同时元组自然排序按结束时间排，这是正确的行为，但 plan 没有显式声明这一点。（2）`sgs.py:97` 的 `strict_mode and isinstance(exc, Exception)` 中 `isinstance(exc, Exception)` 始终为真（因为 `except Exception as exc` 已经保证），这是一个无意义的冗余判断，重构时应直接简化为 `if strict_mode: raise`。（3）`sgs.py` 评分阶段的 `probe_only=True` 自动分配探测在 non-strict 模式下有两层嵌套 `except Exception`（258-262行），内层捕获探测结果形状错误，外层捕获整个探测调用——两层吞异常意味着即使 `auto_assign_internal_resources` 抛出 `TypeError` / `KeyError` 等程序错误也会被静默忽略。plan 要求去掉评分阶段的广域异常降级，但需要明确这两层 `except` 的处理方案。（4）`downtime.py` 的有序插入要求兼容 Python 3.8，而 `bisect.insort` 在 Python 3.8 中不支持 `key=` 参数——plan 已正确识别这一点并要求使用元组自然排序。但 `occupy_resource` 当前接收的是 `(start, end)` 元组参数，改为有序插入后 `timeline` 列表中的每个元素仍然是 `(start, end)` 元组，`bisect.insort` 会按元组自然顺序（先比较 start，相同则比较 end）插入——这在语义上是正确的。
- 问题:
  - [低] JavaScript: sgs.py:97 的 isinstance(exc, Exception) 判断永远为 True
  - [中] JavaScript: sgs.py 评分阶段 probe_only 探测的双层异常吐掉所有程序错误
  - [中] JavaScript: 局部搜索去重与迭代计数器的交互需保证终止性
  - [高] JavaScript: optimize_schedule 中 batch_for_sort 构造早于 keys 确定，created_at strict 校验无法依据 keys 判断

## 最终结论

## 三轮深度审查总结

本次审查共完成三轮，覆盖 12 个核心模块，发现 **17 处问题**（高 4 / 中 7 / 低 6）。

### 总体评价

plan 是一份**高质量的重构方案**——架构拆分清晰、任务依赖关系正确、暂停门槛设计合理、完成判定可验证。plan 对代码现状的理解与引用链描述与源代码实际行为高度一致，修订前提12条全部经核实准确。五个任务的分解能够达成全部九项完成判定。

### 必须在实施前修正的高严重度问题（4项）

1. **R1-F02 / R1-F05**：`schedule_optimizer.py` 的 `_parse_date()` 对 `ready_date` 硬编码了 `field='due_date'`，plan 已正确识别此 BUG 并在暂停条件中列出——确认修复方向正确。但 `scheduler.py:228-229` 与 `scheduler.py:145` 两处 `ready_date` 解析也需要同步改造（R1-F04），plan 步骤中未显式列出这两处。

2. **R2-F04**：`sgs.py` 评分阶段第 360 行的广域 `except Exception` 是当前最大的静默回退源头。plan 的核心价值主张之一就是消除它。拆分后的评分函数必须严格只对五类业务不可估算场景做显式降级，不得保留广域异常兜底。

3. **R3-F04**：`optimize_schedule()` 中 `batch_for_sort` 的构造（第 359 行）早于 `keys` 的确定（第 399 行）。plan 要求根据 `keys` 是否包含 `fifo` 来决定 `created_at` 的 strict 校验——但这在当前执行顺序下无法实现。**实施时必须调整代码执行顺序**。

### 需要在实施时注意的中等严重度问题（7项）

- `validate_internal_hours()` 对 `quantity=0` 的零工时场景需在测试中显式覆盖（R1-F01）
- seed 预热中 `last_end_by_machine` 与 `last_op_type_by_machine` 的原子绑定语义需在 `runtime_state.py` 中正确实现（R1-F03）
- `scheduler.py:228` 的 `_parse_date(rd)` 需同步替换为字段级 strict 包装（R1-F04）
- 拆分后的评分函数必须保证每条路径都返回明确的评分键（R2-F01）
- 效率读取的测试必须使用替身日历绕过引擎层的 `or 1.0`（R2-F07）
- `sgs.py` 评分阶段 `probe_only` 探测的双层 `except Exception` 必须全部移除（R3-F02）
- 局部搜索去重中 `it += 1` 必须在去重判断之前执行以保证终止性（R3-F03）

### 审查结论

plan **有条件通过审查**。在修正上述 4 项高严重度问题后可以开始实施。其中 R3-F04（`batch_for_sort` 构造时序）是最容易被遗漏的隐蔽问题——如果不调整执行顺序，`created_at` 的策略相关 strict 校验将无法按 plan 设计工作。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnoqemp8-5xb161",
  "createdAt": "2026-04-07T00:00:00.000Z",
  "updatedAt": "2026-04-07T14:50:10.053Z",
  "finalizedAt": "2026-04-07T14:50:10.053Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "算法层统一估算与派工重构plan三轮深度审查_第五轮核验",
    "date": "2026-04-07",
    "overview": "对 plan 进行三轮深度审查：目标可达性、实现严谨性、潜在BUG与遗漏"
  },
  "scope": {
    "markdown": "# 算法层统一估算与派工重构 plan 三轮深度审查（第五轮核验）\n\n**审查日期**：2026-04-08\n**审查范围**：`.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md` 及其引用链涉及的全部源文件\n**审查方法**：逐条对照 plan 声明 → 源代码实际行为 → 逻辑推演可达性与副作用\n\n---\n\n## 审查结构\n\n- **第一轮**：目标可达性与架构完整性 — 检验五个任务的分解是否能真正达成完成判定\n- **第二轮**：实施细节严谨性 — 逐步骤检验是否存在过度兜底、静默回退、逻辑漏洞\n- **第三轮**：潜在BUG、边界竞态与遗漏 — 检查 plan 未覆盖但代码中实际存在的风险"
  },
  "summary": {
    "latestConclusion": "## 三轮深度审查总结\n\n本次审查共完成三轮，覆盖 12 个核心模块，发现 **17 处问题**（高 4 / 中 7 / 低 6）。\n\n### 总体评价\n\nplan 是一份**高质量的重构方案**——架构拆分清晰、任务依赖关系正确、暂停门槛设计合理、完成判定可验证。plan 对代码现状的理解与引用链描述与源代码实际行为高度一致，修订前提12条全部经核实准确。五个任务的分解能够达成全部九项完成判定。\n\n### 必须在实施前修正的高严重度问题（4项）\n\n1. **R1-F02 / R1-F05**：`schedule_optimizer.py` 的 `_parse_date()` 对 `ready_date` 硬编码了 `field='due_date'`，plan 已正确识别此 BUG 并在暂停条件中列出——确认修复方向正确。但 `scheduler.py:228-229` 与 `scheduler.py:145` 两处 `ready_date` 解析也需要同步改造（R1-F04），plan 步骤中未显式列出这两处。\n\n2. **R2-F04**：`sgs.py` 评分阶段第 360 行的广域 `except Exception` 是当前最大的静默回退源头。plan 的核心价值主张之一就是消除它。拆分后的评分函数必须严格只对五类业务不可估算场景做显式降级，不得保留广域异常兜底。\n\n3. **R3-F04**：`optimize_schedule()` 中 `batch_for_sort` 的构造（第 359 行）早于 `keys` 的确定（第 399 行）。plan 要求根据 `keys` 是否包含 `fifo` 来决定 `created_at` 的 strict 校验——但这在当前执行顺序下无法实现。**实施时必须调整代码执行顺序**。\n\n### 需要在实施时注意的中等严重度问题（7项）\n\n- `validate_internal_hours()` 对 `quantity=0` 的零工时场景需在测试中显式覆盖（R1-F01）\n- seed 预热中 `last_end_by_machine` 与 `last_op_type_by_machine` 的原子绑定语义需在 `runtime_state.py` 中正确实现（R1-F03）\n- `scheduler.py:228` 的 `_parse_date(rd)` 需同步替换为字段级 strict 包装（R1-F04）\n- 拆分后的评分函数必须保证每条路径都返回明确的评分键（R2-F01）\n- 效率读取的测试必须使用替身日历绕过引擎层的 `or 1.0`（R2-F07）\n- `sgs.py` 评分阶段 `probe_only` 探测的双层 `except Exception` 必须全部移除（R3-F02）\n- 局部搜索去重中 `it += 1` 必须在去重判断之前执行以保证终止性（R3-F03）\n\n### 审查结论\n\nplan **有条件通过审查**。在修正上述 4 项高严重度问题后可以开始实施。其中 R3-F04（`batch_for_sort` 构造时序）是最容易被遗漏的隐蔽问题——如果不调整执行顺序，`created_at` 的策略相关 strict 校验将无法按 plan 设计工作。",
    "recommendedNextAction": "修正 plan 中的 4 项高严重度问题后开始实施：（1）在任务4步骤4中补充 scheduler.py:228 和 scheduler.py:145 两处 ready_date 解析的修改说明；（2）在任务4步骤4-3中补充执行顺序约束——keys 必须在 batch_for_sort 构造前确定；（3）在任务2步骤3中明确 probe_only 探测的双层 except 处理方案",
    "reviewedModules": [
      "core/algorithms/greedy/scheduler.py",
      "core/algorithms/greedy/auto_assign.py",
      "core/algorithms/greedy/dispatch/sgs.py",
      "core/algorithms/greedy/dispatch/batch_order.py",
      "core/algorithms/greedy/downtime.py",
      "core/algorithms/greedy/date_parsers.py",
      "core/algorithms/evaluation.py",
      "core/algorithms/dispatch_rules.py",
      "core/algorithms/ortools_bottleneck.py",
      "core/services/common/strict_parse.py",
      "core/services/scheduler/schedule_optimizer.py",
      "core/services/scheduler/schedule_optimizer_steps.py"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 17,
    "severity": {
      "high": 4,
      "medium": 7,
      "low": 6
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "第一轮：目标可达性与架构完整性审查",
      "status": "completed",
      "recordedAt": "2026-04-07T14:46:31.940Z",
      "summaryMarkdown": "逐一核验五个任务的分解方案能否真正达成全部九项完成判定。以源代码实际行为为基准，检验 plan 的架构拆分、文件职责划分、引用链覆盖与公开边界约束是否完备。",
      "conclusionMarkdown": "第一轮审查确认：plan 的五个任务分解在架构层面基本正确，引用链总览与代码实际一致。主要发现集中在任务4——`ready_date` 的 strict 包装在 `scheduler.py:228-229` 处被遗漏；`schedule_optimizer.py` 的 `_parse_date()` 对 `ready_date` 使用了错误的字段标签。任务1/2/3/5的架构拆分方案合理，完成判定可达。",
      "evidence": [],
      "reviewedModules": [
        "core/algorithms/greedy/scheduler.py",
        "core/algorithms/greedy/auto_assign.py",
        "core/algorithms/greedy/dispatch/sgs.py",
        "core/algorithms/greedy/dispatch/batch_order.py",
        "core/algorithms/greedy/downtime.py",
        "core/algorithms/greedy/date_parsers.py",
        "core/algorithms/evaluation.py",
        "core/algorithms/dispatch_rules.py",
        "core/algorithms/ortools_bottleneck.py",
        "core/services/common/strict_parse.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/scheduler/schedule_optimizer_steps.py"
      ],
      "recommendedNextAction": "进入第二轮审查——逐步骤检验实施细节严谨性",
      "findingIds": [
        "R1-F01",
        "R1-F02",
        "R1-F03",
        "R1-F04",
        "R1-F05",
        "R1-F06"
      ]
    },
    {
      "id": "M2",
      "title": "第二轮：实施细节严谨性审查",
      "status": "completed",
      "recordedAt": "2026-04-07T14:47:41.139Z",
      "summaryMarkdown": "逐步骤检验 plan 中每个任务的实施细节：效率回退层次、评分阶段异常处理、闭包变量陷阱、导入清理时序、局部搜索去重内存影响、downtime.py 静默回退等。重点检查「过度兜底」和「静默回退」在改造后是否能被真正消除。",
      "conclusionMarkdown": "第二轮审查发现 plan 在实施细节层面总体严谨，但存在 7 处需要注意的具体问题：sgs.py 中 `candidates[0]` 死代码 plan 已识别但拆分后的导入时序约束可能被忽略；`_scaled_hours` 闭包在 auto_assign 中存在闭包变量陷阱；sgs.py 评分阶段的静默降级嵌套过深，拆分后必须严格保持现有注释中所描述的五类不可估算降级；局部搜索去重的 `seen_hashes` 在大规模排产中可能占用大量内存；`downtime.py:36-39` 的 `find_earliest_available_start` 中 `duration_hours` 坏值仍有静默回退。",
      "evidence": [],
      "reviewedModules": [
        "core/algorithms/greedy/dispatch/sgs.py",
        "core/algorithms/greedy/auto_assign.py",
        "core/algorithms/greedy/downtime.py",
        "core/services/scheduler/schedule_optimizer.py"
      ],
      "recommendedNextAction": "进入第三轮审查——潜在BUG、边界竞态与遗漏",
      "findingIds": [
        "R2-F01",
        "R2-F02",
        "R2-F03",
        "R2-F04",
        "R2-F05",
        "R2-F06",
        "R2-F07"
      ]
    },
    {
      "id": "M3",
      "title": "第三轮：潜在BUG、边界竞态与遗漏审查",
      "status": "completed",
      "recordedAt": "2026-04-07T14:48:29.372Z",
      "summaryMarkdown": "检查 plan 未覆盖但代码中实际存在的潜在 BUG、边界竞态与遗漏。重点关注：bisect.insort 在 Python 3.8 的兼容性、sgs.py 评分阶段的冗余判断与双层异常吞没、局部搜索去重的终止性保证、optimize_schedule 中 batch_for_sort 构造与 keys 确定的时序问题。",
      "conclusionMarkdown": "第三轮审查完成。发现 4 处 plan 未覆盖的边界问题和潜在BUG：（1）`bisect.insort` 在 Python 3.8 中对元组排序的正确性需要关注——当两个区间起点相同时元组自然排序按结束时间排，这是正确的行为，但 plan 没有显式声明这一点。（2）`sgs.py:97` 的 `strict_mode and isinstance(exc, Exception)` 中 `isinstance(exc, Exception)` 始终为真（因为 `except Exception as exc` 已经保证），这是一个无意义的冗余判断，重构时应直接简化为 `if strict_mode: raise`。（3）`sgs.py` 评分阶段的 `probe_only=True` 自动分配探测在 non-strict 模式下有两层嵌套 `except Exception`（258-262行），内层捕获探测结果形状错误，外层捕获整个探测调用——两层吞异常意味着即使 `auto_assign_internal_resources` 抛出 `TypeError` / `KeyError` 等程序错误也会被静默忽略。plan 要求去掉评分阶段的广域异常降级，但需要明确这两层 `except` 的处理方案。（4）`downtime.py` 的有序插入要求兼容 Python 3.8，而 `bisect.insort` 在 Python 3.8 中不支持 `key=` 参数——plan 已正确识别这一点并要求使用元组自然排序。但 `occupy_resource` 当前接收的是 `(start, end)` 元组参数，改为有序插入后 `timeline` 列表中的每个元素仍然是 `(start, end)` 元组，`bisect.insort` 会按元组自然顺序（先比较 start，相同则比较 end）插入——这在语义上是正确的。",
      "evidence": [],
      "reviewedModules": [
        "core/algorithms/greedy/dispatch/sgs.py",
        "core/algorithms/greedy/downtime.py",
        "core/algorithms/greedy/scheduler.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/algorithms/greedy/auto_assign.py"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "R3-F01",
        "R3-F02",
        "R3-F03",
        "R3-F04"
      ]
    }
  ],
  "findings": [
    {
      "id": "R1-F01",
      "severity": "medium",
      "category": "javascript",
      "title": "validate_internal_hours 对 quantity=0 的零工时场景存在歧义",
      "descriptionMarkdown": "plan 要求 `validate_internal_hours()` 在 `total_hours_base` 非有限或为负时抛 `ValueError`，但允许零工时（步骤1-6要求 `start_time == end_time` 且不报错）。然而 `total_hours_base = 0.0` 既可能来自 `setup_hours=0 + unit_hours=0`（合法零时长工序），也可能来自 `quantity=0`（逻辑上可疑的零数量批次）。plan 对这两种情况未做区分，统一允许返回零工时。\n\n当前代码 `scheduler.py:480` 的行为是允许零工时通过（只拒绝负数和非有限值），所以 plan 在此处保持了行为兼容。但 `auto_assign.py:110` 也允许零工时通过，并会为零工时工序完成一次「选择最佳设备/人员」的全量扫描——这在语义上是否正确值得考量。\n\n建议：在 plan 的测试用例中补充 `quantity=0` 且 `unit_hours > 0` 的场景，显式声明此时 `validate_internal_hours()` 返回 0.0 是期望行为，并在自动分配路径中确认零工时候选评估的早停语义。",
      "recommendationMarkdown": "在 `tests/regression_internal_slot_estimator_consistency.py` 的步骤1-6中增加 `quantity=0, unit_hours=1.0` 的子场景",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 476,
          "lineEnd": 488
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 102,
          "lineEnd": 112
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R1-F02",
      "severity": "high",
      "category": "javascript",
      "title": "避让上界公式在自动分配场景下存在时间线不一致风险",
      "descriptionMarkdown": "plan 任务1步骤3-6规定避让上界为 `len(machine_timeline[mid]) + len(operator_timeline[oid]) + len(downtime_segments) + 1`。但 `auto_assign_internal_resources()` 会为每个候选 `(mid, oid)` 组合调用 `estimate_internal_slot()`，且不同组合使用同一个 `machine_timeline` 和 `operator_timeline`。\n\n关键问题：在同一轮自动分配调用中，`machine_timeline` 和 `operator_timeline` 不会被当前候选组合的估算过程修改（因为 `internal_slot.py` 只估算不占用），所以不同候选组合看到的片段数相同。但一轮 `dispatch_sgs()` 的多次迭代中，前一次迭代可能已经通过 `occupy_resource()` 新增了片段。因此上界在估算时是正确的——每次调用 `estimate_internal_slot()` 时所看到的片段数就是当时的真实片段数。\n\n然而，需要注意：`downtime_segments` 在整个排产过程中不会变化（由 `resource_pool_builder.py` 预构建），但 `machine_timeline[mid]` 和 `operator_timeline[oid]` 在 seed 预热后可能已经包含大量片段。如果 seed 结果有 200+ 条同一设备的片段，上界就会超过 200，这正是 plan 要消除固定 200 次上界的核心动机。\n\n这条本身不是 BUG 而是对 plan 正确性的确认：上界公式在此场景下是正确的。但需要确认 plan 实施时 `estimate_internal_slot()` 的避让循环确实以调用时的当前片段长度为上界，而不是预先计算一次就固定。",
      "recommendationMarkdown": "在步骤3实现时明确：上界在 `estimate_internal_slot()` 入口计算一次即可（因为函数内部不修改时间线），但调用方每次调用前时间线可能已变化",
      "evidence": [
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 183,
          "lineEnd": 206
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R1-F03",
      "severity": "medium",
      "category": "javascript",
      "title": "seed 预热运行期状态语义在 runtime_state.py 中有隐蔽差异",
      "descriptionMarkdown": "plan 任务3步骤4要求 `runtime_state.py` 显式区分 seed 预热与派工成功两种模式。经代码核实，三处运行期更新有以下差异：\n\n1. **seed 预热**（`scheduler.py:289-304`）：`last_op_type_by_machine` 只在 `mid and ot and sr.end_time` 时更新，且只在 `end_time > prev_end` 时才覆盖——即 seed 中同一设备有多条记录时，取最晚结束的那条的工种。\n\n2. **batch_order 派工**（`batch_order.py:90-106`）：`last_end_by_machine` 按 `prev_end is None or result.end_time > prev_end` 条件覆盖；但 `last_op_type_by_machine` 只要 `ot` 非空就直接覆盖——不检查 `end_time` 是否更晚。\n\n3. **sgs 派工**（`sgs.py:458-475`）：同 `batch_order`——`last_end_by_machine` 条件覆盖，`last_op_type_by_machine` 直接覆盖。\n\nplan 描述的「seed 条件覆盖」与「派工成功直接更新」这两种模式是正确的。但 plan 中的实施约束说「`last_end_by_machine` 条件更新、`last_op_type_by_machine` 仅在非空时直接更新」——这对 batch_order 和 sgs 是准确的。\n\n然而 seed 预热中 `last_op_type_by_machine` 的更新条件实际是 `mid and ot and sr.end_time` 且 `sr.end_time > prev_end`（第 302-304 行），也就是**工种和结束时间绑定在同一个 if 条件分支里**。这意味着 seed 预热如果有两条记录：第一条 end_time=10:00 op_type=A，第二条 end_time=8:00 op_type=B，那么结果是 last_op_type=A（只取更晚的那条）。而 batch_order/sgs 模式下，如果排产结果按顺序产生 end_time=10:00 op_type=A 然后 end_time=8:00 op_type=B，则 last_op_type=B（直接覆盖）。\n\n这个差异 plan 已正确识别，但 `runtime_state.py` 的共享函数如果用 `conditional_op_type=True/False` 来区分，需要确保 seed 模式下 `last_end_by_machine` 和 `last_op_type_by_machine` 的更新是原子绑定的——即只有当 `end_time > prev_end` 时才同时更新两个字典。",
      "recommendationMarkdown": "在 `runtime_state.py` 的 seed 模式函数中，确保 `last_end_by_machine` 和 `last_op_type_by_machine` 在同一条件分支内原子更新",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 299,
          "lineEnd": 304
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py",
          "lineStart": 90,
          "lineEnd": 106
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 458,
          "lineEnd": 475
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R1-F04",
      "severity": "medium",
      "category": "javascript",
      "title": "任务4对 ready_date 的 strict 包装在 scheduler.py 中缺少实际触达路径",
      "descriptionMarkdown": "plan 任务4步骤4-2要求 `scheduler.py` 中 `ready_date` 在 strict 模式下使用 `field='ready_date'` 的包装。但 `scheduler.py:228-229` 当前使用的是从 `schedule_params.py` 转导出的 `_parse_date(rd)`，这个函数内部调用的是 `core.algorithms.greedy.date_parsers.parse_date()`——一个永不抛异常的非严格解析器。\n\n当前 `scheduler.py:138` 在构造 `BatchForSort` 时已经分别处理了 `due_date` 的 strict/non-strict 模式，但 `ready_date`（第 145 行）始终使用 `_parse_date()`（非严格），`created_at`（第 146 行）始终使用 `_parse_datetime()`（非严格）。\n\n这意味着：**当前代码中 `ready_date` 的解析从未走过 strict 路径**。plan 任务4要给 `ready_date` 加上 strict 路径——既要在构造 `BatchForSort` 时加，也要在 `scheduler.py:228-229` 的 `batch_progress` 初始化处加。但 plan 只提到了构造 `BatchForSort` 的场景（步骤4-2），没有明确提到 `scheduler.py:228-229` 这处也需要同步改造。\n\n如果 `scheduler.py:228-229` 不改，那么 `ready_date` 在 strict 模式下可能通过了 `BatchForSort` 构造，却在 `batch_progress` 初始化时使用了不同的解析函数——导致解析结果不一致。",
      "recommendationMarkdown": "在任务4步骤4中显式列出 `scheduler.py:228-229` 的 `_parse_date(rd)` 也需要替换为字段级 strict 包装",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 228,
          "lineEnd": 237
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 138,
          "lineEnd": 146
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R1-F05",
      "severity": "high",
      "category": "javascript",
      "title": "optimize_schedule 中 _parse_date 对 ready_date 使用 field='due_date' 标签",
      "descriptionMarkdown": "plan 任务4暂停条件明确列出：「`schedule_optimizer.py` 解析坏 `ready_date` 仍以 `due_date` 名义报错」。\n\n经代码核实，`schedule_optimizer.py:335-341` 的 `_parse_date()` 函数硬编码了 `field='due_date'`，但第 367 行用 `_parse_date(getattr(b, 'ready_date', None))` 解析 `ready_date`——这意味着如果 strict 模式下 `ready_date` 不合法，报错信息会说 `due_date 格式不合法` 而不是 `ready_date 格式不合法`。\n\n这是一个现存 BUG，plan 正确地识别了它，并在任务4步骤4-2中要求拆成 `_parse_due_date()` 和 `_parse_ready_date()` 两个字段级包装。这条发现确认 plan 的修复方向正确。\n\n但进一步检查发现，`scheduler.py:138` 的 `due_date` strict 包装使用 `parse_optional_date(due_raw, field='due_date')`，而 `ready_date`（第 145 行）使用 `_parse_date()`（非严格，永不抛异常）。这意味着当前代码中 **`scheduler.py` 侧的 `ready_date` 在 strict 模式下不会报错**，但 `schedule_optimizer.py` 侧的 `ready_date` 在 strict 模式下会以 `due_date` 名义报错。两侧行为不一致。",
      "recommendationMarkdown": "任务4必须同步修改 `scheduler.py:145` 和 `schedule_optimizer.py:367` 两处",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 335,
          "lineEnd": 341
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 365,
          "lineEnd": 368
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 138,
          "lineEnd": 146
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R1-F06",
      "severity": "low",
      "category": "performance",
      "title": "multi_start 中 build_order 确实在最内层循环重复执行",
      "descriptionMarkdown": "plan 任务5断言 `build_order()` 在 `dispatch_mode` / `dispatch_rule` 内层循环重复执行。经 `schedule_optimizer_steps.py:331-334` 核实：`for dr in dispatch_rules:` 是 `for k in keys:` 的内层循环，`order = build_order(strat, params0)` 在第 334 行，位于 `dr` 循环内部。由于 `strat` 和 `params0` 在同一个 `k` 下不变，`build_order(strat, params0)` 每次返回值相同——确实是重复构造。\n\n但需要注意：`build_order` 实际调用的是 `_build_order()`（`schedule_optimizer.py:372-374`），它会创建一个新的 `StrategyFactory.create(strategy0, **(params or {}))` 并调用 `.sort()`。排序的输入 `batch_for_sort` 在整个 `optimize_schedule()` 调用期间不变。所以这确实是可以安全缓存的。\n\n但 `dispatch_rules` 循环也嵌套在 `for dm in dispatch_modes:` 内。如果 `keys` 有 4 个策略，`dispatch_modes` 有 2 个，`dispatch_rules` 有 3 个，那么同一个 `(strat, params0)` 组合最多被 `build_order()` 调用 2 * 3 = 6 次。plan 的缓存键 `(strategy.value, tuple(sorted(params0.items())))` 可以正确消除这些重复。",
      "recommendationMarkdown": "确认无问题，plan 的优化方案正确",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py",
          "lineStart": 300,
          "lineEnd": 350
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R2-F01",
      "severity": "medium",
      "category": "maintainability",
      "title": "sgs.py 中 candidates[0] 死代码删除后必须保证评分函数无静默跳过路径",
      "descriptionMarkdown": "plan 任务2步骤3-5要求：「`best_pair = candidates[0]` 属于死代码，必须直接删除」。经 `sgs.py:424-425` 核实，这行代码的确是死代码：在当前评分逻辑下，每个候选都会产生一个 key（无论正常还是降级），所以 `best_pair` 不会为 `None`。\n\n但这行死代码实际上是最后一道安全网——如果拆分后的 `_score_internal_candidate()` 或 `_score_external_candidate()` 在某些边界情况下没有返回 key，`best_pair` 就会为 `None`。\n\nplan 的策略是正确的（删除死代码，而不是保留它作为安全网），但实施时必须确保：拆分后的评分函数**总是**返回一个 key（要么正常要么降级），不存在「既不返回又不抛异常」的路径。",
      "recommendationMarkdown": "在拆分后的 `_score_internal_candidate()` 和 `_score_external_candidate()` 中，确保每条路径都返回明确的 key 或抛出明确的异常，消除所有「静默跳过」路径",
      "evidence": [
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 424,
          "lineEnd": 425
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R2-F02",
      "severity": "low",
      "category": "javascript",
      "title": "sgs.py 的 avg_proc_hours 初始化段未被纳入导入清理前提",
      "descriptionMarkdown": "plan 任务2步骤3-6规定导入清理时序：「`parse_required_float` 仅在 `_build_unscorable_dispatch_key(...)` 与 `_score_internal_candidate(...)` 两条路径都彻底替换完成后才允许删除」。\n\n但 `parse_required_float` 当前还被 `sgs.py:92-94` 的 `avg_proc_hours` 初始化段使用。plan 步骤3-3 要求这里改用 `validate_internal_hours(op, batch)` 作为取样入口。但如果步骤3-3 的实施先于步骤3-6 的导入清理，那么 `parse_required_float` 的删除实际取决于步骤3-3 的完成。\n\n潜在风险：如果实施者先删除 `parse_required_float` 导入再改 `avg_proc_hours` 初始化，会导致中间版本编译失败。plan 已明确说「先替换再删除」，但没有明确将 `avg_proc_hours` 初始化段纳入导入清理的前提条件。",
      "recommendationMarkdown": "在步骤3-6 的导入清理时序中明确列出：`parse_required_float` 的删除前提还包括 `avg_proc_hours` 初始化段的替换",
      "evidence": [
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 91,
          "lineEnd": 102
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R2-F03",
      "severity": "low",
      "category": "javascript",
      "title": "auto_assign.py 中 _scaled_hours 闭包变量陷阱在重构后自然规避",
      "descriptionMarkdown": "plan 任务1步骤4 要求删除 `auto_assign.py` 中本地 `_scaled_hours()` 与避让循环。经核实，`auto_assign.py:163-175` 的 `_scaled_hours()` 是一个在 `for oid in op_candidates:` 循环内定义的闭包函数，它通过默认参数 `_oid=oid` 来捕获当前循环变量。\n\n这是一个常见的闭包变量陷阱解决方案：`_oid=oid` 确保每次循环都创建一个新的 `_scaled_hours` 闭包，且每个闭包捕获的是当前迭代的 `oid` 值。\n\n当 plan 把 `_scaled_hours` 替换为 `estimate_internal_slot(...)` 时，这个闭包会被删除。但必须确保 `estimate_internal_slot(...)` 的 `operator_id` 参数是由调用方显式传入的（而不是通过闭包捕获），这样就自然避免了闭包陷阱。plan 已要求 `estimate_internal_slot()` 接受显式的 `operator_id` 参数，所以这个闎险已被规避。",
      "recommendationMarkdown": null,
      "evidence": [
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 163,
          "lineEnd": 175
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R2-F04",
      "severity": "high",
      "category": "javascript",
      "title": "sgs.py 评分阶段的广域 except 是当前最大的静默回退源头",
      "descriptionMarkdown": "`sgs.py` 当前的评分阶段在第 360 行有一个大区域 `except Exception:`，它会捕获**所有**未被内层 `except` 捕获的异常（包括真正的程序错误如 `AttributeError`、`KeyError`、`NameError`），并把它们变成降级评分键。\n\nplan 任务2步骤3-4 要求「只有五类业务不可估算情况可以构造降级评分键」，并明确要求「探测返回形状错误、代码调用错误、实现异常等意外问题不得再变成最差 key」。\n\n这是 plan 的核心价值主张之一，完全正确。但实施时必须小心：\n\n1. 拆分后的 `_score_internal_candidate()` 和 `_score_external_candidate()` 不能再包广域 `except Exception`。\n2. 主函数 `dispatch_sgs()` 的 `for bid, op in candidates:` 循环内部不能再包广域 `try/except`。\n3. 当前第 489 行的外层 `except Exception as e:` 是捕获执行阶段的异常，这个应该保留（因为执行阶段的异常需要写入 errors 并阻断批次）。\n\n实施时必须确保：评分阶段的意外异常在 `strict_mode=True` 时上浮，在 `strict_mode=False` 时也应该通过计数器可见（但不是变成降级 key）。",
      "recommendationMarkdown": "在拆分后的评分函数中，只对五类明确的业务不可估算场景做显式处理，意外异常在 non-strict 模式下通过计数器暴露但不降级",
      "evidence": [
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 360,
          "lineEnd": 418
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R2-F05",
      "severity": "low",
      "category": "performance",
      "title": "局部搜索去重的 seen_hashes 在大规模场景下内存占用可接受",
      "descriptionMarkdown": "plan 任务5步骤4 要求 `_run_local_search()` 新增 `seen_hashes`，键为 `tuple(cand_order)`。在大规模排产中，`cand_order` 可能包含数百到数千个批次，而 `it_limit` 最高 5000 次。\n\n内存估算：假设 500 个批次、每个批次 ID 平均 10 字符，每个 tuple 约 500 * 10 * 8 = 40KB。 5000 次迭代的 `seen_hashes` 最多占 200MB。\n\n这对于单机单用户环境是可接受的，但需要注意：plan 要求 shake 后「允许做轻量重置（清空后立即写回当前 `cur_order`，并补写 `tuple(best.get('order', []))`）」。这个重置会释放大部分内存，因此实际峻值会远小于上述估算。\n\n但 `restart_after` 可能为 800（当 `it_limit=6400` 时），意味着在两次 shake 之间最多积累 800 个 tuple，占约 32MB。这是可接受的。",
      "recommendationMarkdown": "可以接受，但建议在实施时加一行日志记录 `len(seen_hashes)` 的峻值，以便后续监控",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 128,
          "lineEnd": 260
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R2-F06",
      "severity": "low",
      "category": "javascript",
      "title": "downtime.py 中 find_earliest_available_start 的静默回退未被 plan 纳入清理范围",
      "descriptionMarkdown": "`downtime.py:36-39` 的 `find_earliest_available_start()` 中有一个对 `duration_hours` 的静默回退：\n```python\ntry:\n    dur = float(duration_hours)\nexcept Exception:\n    dur = 0.0\n```\n\n这意味着如果 `duration_hours` 是字符串「'abc'」或其他不可转换类型，它会被静默变成 0.0，然后因 `dur <= 0` 直接返回 `base_time`——相当于「没有占用」。\n\nplan 任务3将修改 `find_earliest_available_start()` 使其去掉内部 `sorted()`，但没有要求清理这个 `except Exception`。由于 plan 的实施约束说「不新增广域 `except Exception: pass`」但未要求删除现有的，且 `find_earliest_available_start()` 在任务2完成后可能被删除（「顺序链式近似评分路径彻底消失后删除」），所以这个静默回退可能会自然消失。\n\n但如果任务2完成后 `find_earliest_available_start()` 仍被其他地方使用，这个静默回退就会保留下来。",
      "recommendationMarkdown": "确认任务2完成后 `find_earliest_available_start()` 是否仍有调用方；若仍保留则应把这个 `except Exception` 纳入完成判定的「未触达残留」类目",
      "evidence": [
        {
          "path": "core/algorithms/greedy/downtime.py",
          "lineStart": 36,
          "lineEnd": 41
        },
        {
          "path": "core/algorithms/greedy/downtime.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R2-F07",
      "severity": "medium",
      "category": "javascript",
      "title": "效率读取的三处静默回退与引擎层双重回退问题",
      "descriptionMarkdown": "plan 任务1步骤3-4 要求「读取效率时必须使用显式 `raw_eff is not None` 判断，不使用 `or 1.0`」。经核实当前代码中效率读取有三处：\n\n1. `scheduler.py:494`：`float(self.calendar.get_efficiency(start, operator_id=operator_id) or 1.0)` —— 使用 `or 1.0`，**是**静默回退。\n2. `auto_assign.py:166-167`：`raw_eff is not None` —— **正确**的显式判断。\n3. `sgs.py:323`：`float(scheduler.calendar.get_efficiency(...) or 1.0)` —— 使用 `or 1.0`，**是**静默回退。\n\n但 `auto_assign.py:168-169` 外层还有 `except Exception: eff = 1.0`，它会把 `get_efficiency()` 抛出的程序错误也吞掉。\n\nplan 已明确要求消除这些静默回退：\n- `scheduler.py:494` 中的 `or 1.0` → 使用 `raw_eff is not None`\n- `sgs.py:323` 中的 `or 1.0` → 同上\n- `auto_assign.py:168-169` 的 `except Exception` → 删除\n\n但修订前提9注意到 `CalendarEngine.get_efficiency()` 自身也有 `or 1.0`，所以算法层即使去掉 `or 1.0`，实际拿到的值仍然被引擎层抄底过了。plan 明确说「本轮只消除算法层冗余静默回退，不扩到引擎层」。\n\n这是一个已记录的取舱，不是 BUG。但意味着任务1的测试用例如果注入 `get_efficiency()` 返回 `0.0`，实际可能被引擎层的 `or 1.0` 截断，导致测试无法真正触发算法层的效率处理逻辑。\n\n因此 plan 步骤1-5 的测试用例必须用替身日历的 `get_efficiency()` 直接返回 `0.0`（而不是经过 `CalendarEngine`）才能真正验证算法层的处理逻辑。plan 已要求「通过替身日历 / 替身对象直接向算法层注入」，所以测试设计是正确的。",
      "recommendationMarkdown": "确认无问题：测试用例必须用替身日历直接返回 0.0 而不是经过 CalendarEngine",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 491,
          "lineEnd": 496
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 163,
          "lineEnd": 169
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 321,
          "lineEnd": 327
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R3-F01",
      "severity": "low",
      "category": "javascript",
      "title": "sgs.py:97 的 isinstance(exc, Exception) 判断永远为 True",
      "descriptionMarkdown": "sgs.py:97 的条件 `strict_mode and isinstance(exc, Exception)` 中，`isinstance(exc, Exception)` 始终为 True，因为 `except Exception as exc` 已经保证了 `exc` 一定是 `Exception` 的实例。这是一个无意义的冗余判断。\n\nplan 任务2步骤3-3 要求 `avg_proc_hours` 初始化段改用 `validate_internal_hours(op, batch)` 作为取样入口，这会替换掉第 91-99 行的逻辑。但重构时应该确保不会把这个冗余判断带入新代码。",
      "recommendationMarkdown": "重构时直接简化为 `if strict_mode: raise`",
      "evidence": [
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 96,
          "lineEnd": 99
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R3-F02",
      "severity": "medium",
      "category": "javascript",
      "title": "sgs.py 评分阶段 probe_only 探测的双层异常吐掉所有程序错误",
      "descriptionMarkdown": "`sgs.py:252-263` 的评分阶段 `probe_only=True` 自动分配探测有两层嵌套 `except Exception`：\n\n第一层（258-260行）：捕获探测结果的解构错误（例如 `chosen` 不是 `(list, tuple)` 或长度不足 2）。\n第二层（261-263行）：捕获整个 `_auto_assign_internal_resources` 调用过程中的任何异常。\n\n两层都只计数然后继续——意味着即使 `auto_assign_internal_resources` 抛出 `TypeError` / `KeyError` 等程序错误，也会被静默忽略，然后 `machine_id` / `operator_id` 保持为空，候选进入「缺资源且无法自动分配」降级路径。\n\nplan 要求「探测返回形状错误、代码调用错误、实现异常等意外问题不得再变成最差 key」。但 plan 没有明确说明这两层 `except` 应该如何处理：\n\n1. 内层的探测结果解构错误（`chosen` 不是合法对）是正当的业务不可估算场景吗？不是——如果 `auto_assign_internal_resources` 的返回值不是 `(str, str)` 元组，那是一个接口契约违反，应该被当作实现错误暴露。\n2. 外层的 `except Exception` 更不应该存在——它会吞掉 `auto_assign_internal_resources` 内部的所有程序错误。\n\n重构后应当：内层不包 `except`（因为 `auto_assign` 的返回类型是 `Optional[Tuple[str, str]]`，如果不是就是实现错误）；外层也不包 `except`（因为 `auto_assign` 内部的程序错误应该显式上浮）。",
      "recommendationMarkdown": "plan 实施时应当把这两层 `except Exception` 全部移除，只保留 `chosen is None` 的正常分支判断",
      "evidence": [
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 230,
          "lineEnd": 263
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R3-F03",
      "severity": "medium",
      "category": "javascript",
      "title": "局部搜索去重与迭代计数器的交互需保证终止性",
      "descriptionMarkdown": "plan 任务5步骤4 要求「重复跳过不会被计入 `attempts`，但必须继续推进用于触发 `restart_after` 的停滞计数」。\n\n经检查当前 `_run_local_search()` 的逻辑：`no_improve` 计数器在每次迭代后，如果未改进则 `no_improve += 1`（第 242 行）。当 `no_improve >= restart_after` 时触发 shake（第 245 行）。\n\nplan 要求重复邻域跳过时：不计入 `attempts`，但**必须**推进 `no_improve`。这意味着即使跳过了实际排产调用，`no_improve` 仍然应该 +1。\n\n但这里有一个微妙的语义问题：如果重复跳过的邻域不计入 `it`（迭代计数器），那么 `it < it_limit` 的终止条件不会推进，可能导致在小规模场景中无限循环（如果所有可能的邻域都已经被访问过）。\n\n但经仔细分析，`it` 在 `while` 循环开始时无条件 `+= 1`（第 140 行），所以即使跳过了排产调用，`it` 仍然会推进。这保证了不会无限循环。\n\nplan 的描述说「不计入 `attempts`」但没说「不计入 `it`」——这是正确的，因为 `it` 应该始终推进以保证终止。",
      "recommendationMarkdown": "实施时确保 `it += 1` 在去重判断之前执行，以保证终止条件始终推进",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 139,
          "lineEnd": 260
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "R3-F04",
      "severity": "high",
      "category": "javascript",
      "title": "optimize_schedule 中 batch_for_sort 构造早于 keys 确定，created_at strict 校验无法依据 keys 判断",
      "descriptionMarkdown": "plan 任务4步骤4-3 要求：`optimize_schedule()` 仅当当前轮次实际用于构造排序器的 `keys` 包含 `fifo` 时，才对 `created_at` 使用共享 strict 日期时间包装。\n\n经 `schedule_optimizer.py:392-399` 核实：\n- `valid_strategies` 是从配置读取的全量策略候选集（默认包含 `fifo`）。\n- `keys` 在 `algo_mode == 'improve'` 时为 `[current_key] + [其他策略]`，即从 `valid_strategies` 中构建。\n- 在 `algo_mode != 'improve'` 时，`keys` 只包含 `[current_key]`。\n\n关键问题：当 `algo_mode == 'improve'` 时，`keys` 通常包含 `fifo`（因为 `valid_strategies` 默认包含它）。但如果用户显式配置 `VALID_STRATEGIES` 不包含 `fifo`，那么 `keys` 就不包含 `fifo`，`created_at` 的 strict 校验就不应触发。\n\nplan 的要求完全正确：以 `keys` 而非 `valid_strategies` 为准。但需要注意：在 `algo_mode != 'improve'` 时，`keys = [current_key]`，所以只有当用户显式选择 FIFO 策略时才会触发 `created_at` 的 strict 校验——这是正确的行为。\n\n但进一步考虑：`batch_for_sort` 的构造（`schedule_optimizer.py:359-370`）发生在 `keys` 确定之前。如果要根据 `keys` 来决定是否对 `created_at` 做 strict 校验，就需要在构造 `batch_for_sort` 时已知道 `keys` 的内容。经检查，`valid_strategies` 在第 392 行确定，`keys` 在第 399 行确定，而 `batch_for_sort` 的构造在第 359-370 行（早于 `keys`）。\n\n这意味着：如果要根据 `keys` 来决定 `created_at` 的 strict 校验，就需要把 `keys` 的确定提前到 `batch_for_sort` 构造之前，或者把 `created_at` 的 strict 校验延迟到 `batch_for_sort` 构造之后。\n\nplan 任务4步骤4-3 要求「`optimize_schedule()` 仅当当前轮次实际用于构造排序器的 `keys` 包含 `fifo` 时」——但没有注意到 `batch_for_sort` 的构造在 `keys` 确定之前。实施时需要调整执行顺序。",
      "recommendationMarkdown": "plan 实施时必须把 `keys` / `valid_strategies` 的确定提前到 `batch_for_sort` 构造之前，或者延迟 `created_at` 的 strict 校验到 `keys` 确定之后",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 359,
          "lineEnd": 401
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
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
    "bodyHash": "sha256:6cc86cc73587fcc2b0b28412f59127ff414cbb896a40e3380b5e9ae43135d477",
    "generatedAt": "2026-04-07T14:50:10.053Z",
    "locale": "zh-CN"
  }
}
```
