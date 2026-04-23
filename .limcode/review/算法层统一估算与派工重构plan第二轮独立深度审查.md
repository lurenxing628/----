# 算法层统一估算与派工重构plan第二轮独立深度审查
- 日期: 2026-04-07
- 概述: 对采纳前轮修订建议后的 plan 当前版本进行独立三轮深度审查（设计审查 → 隐性耦合猎杀 → 边界与遗漏分析）
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# 算法层统一估算与派工重构 Plan 第二轮独立深度审查

**审查日期**: 2026-04-07
**审查对象**: `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`（已采纳前轮全部修订建议的版本）
**审查目标**: 在前轮审查已验证引用链精确性的基础上，聚焦于：
1. 估算器接口设计是否最简且正确
2. 三重估算开销是否可能突破 30% 阈值
3. plan 步骤描述是否有遗漏的隐性状态操作
4. 新发现的代码问题或设计缺陷

## 审查策略

- **第一轮**：设计纯度与接口审查 — 检查 `estimate_internal_slot` 的参数表是否最精简、职责边界是否清晰
- **第二轮**：隐性耦合与遗漏猎杀 — 追踪 plan 步骤中可能遗漏的状态操作（`occupy_resource`、`batch.quantity` 来源、`priority` 传递）
- **第三轮**：性能风险与边界条件 — 分析三重估算的真实开销、邻域去重的内存模型、避让上界的数学证明

## 评审摘要

- 当前状态: 已完成
- 已审模块: core/algorithms/greedy/scheduler.py, core/algorithms/greedy/auto_assign.py, core/algorithms/greedy/dispatch/sgs.py, core/algorithms/greedy/downtime.py, core/algorithms/greedy/dispatch/batch_order.py, core/services/scheduler/schedule_optimizer_steps.py, core/services/scheduler/schedule_optimizer.py, core/algorithms/evaluation.py, core/algorithms/dispatch_rules.py, core/algorithms/ortools_bottleneck.py, core/algorithms/greedy/date_parsers.py, core/services/scheduler/schedule_input_builder.py
- 当前进度: 已记录 3 个里程碑；最新：M3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 6
- 问题严重级别分布: 高 0 / 中 3 / 低 3
- 最新结论: ## 审查总结 经过三轮深度审查（设计纯度审查 → 隐性耦合猎杀 → 性能风险与边界条件），对 11 个核心代码文件进行了独立逐行核实。 ### 总体评价 **Plan 质量优秀，在前轮审查后已经达到很高的完成度。** 前轮提出的全部 9 个发现（F1-F9）都已被采纳修订——参数表精简为 `prev_end`、避让上界表达式明确化、`abort_after` 两处检查点、导入清理、零时长边界用例、双重自动分配已知局限说明，全部到位。 ### 本轮新发现的 6 个问题 | 编号 | 严重级别 | 问题 | 建议 | |---|---|---|---| | G1 | 中 | 估算器参数应传 `calendar` 而非 `scheduler`——实际只用三个日历方法，传整个调度器暴露不必要的内部状态 | 改为 `calendar: Any`，调用方传 `scheduler.calendar` | | G2 | 中 | `occupy_resource` 保留位置未在任务 1 步骤 4 中显式说明——实施者可能在删除避让循环时连带删除，导致排产结果不占用资源 | 在步骤 4 增加"保留 `occupy_resource` 调用" | | G5 | 中 | SGS 三重估算（probe → score → schedule）在大规模资源池下可能突破 30% 阈值——`smoke_phase10` 的候选对数可能偏小 | 补充候选对 > 200 的大规模耗时测试 | | G3 | 低 | `sgs.py:97` 的 `isinstance(exc, Exception)` 是永真死条件，应在任务 2 简化 `avg_proc_hours` 时顺带删除 | 在任务 2 步骤 3 补充 | | G4 | 低 | `scheduler.py:476-488` 的工时计算块未明确列入删除范围——步骤 4 只说删 `_scaled_hours` 和避让循环 | 扩展步骤 4 描述范围 | | G6 | 低 | 避让上界数学证明成立——`earliest` 严格单调递增 + 每次至少越过一个片段 = 上界 N+1 ✅ | 无需修改 | ### 本轮验证通过的关键设计决策 1. **避让上界 `N_machine + N_operator + N_downtime + 1`**：数学证明成立 ✅ 2. **`bisect.insort` 兼容 Python 3.8**：不使用 `key=`，元组自然序排序 ✅ 3. **`build_order` 多策略共享**：调度器内部只读取不修改 ✅ 4. **日期函数替换**：`evaluation.py`、`dispatch_rules.py`、`ortools_bottleneck.py` 三份重复实现与共享版本功能等价 ✅ 5. **`schedule_optimizer._parse_datetime` 替换**：与 `date_parsers.parse_datetime` 功能等价 ✅ 6. **`conditional_op_type` 双模式设计**：seed 条件覆盖 vs 派工直接更新，两种语义精确匹配 ✅ 7. **邻域去重内存**：n=200 批次 × 5000 次迭代 ≈ 8MB，完全可控 ✅ ### 结论 Plan 可以按现有设计开始实施。建议先处理 **G2**（`occupy_resource` 保留位置）这一处最容易导致实施错误的 plan 文本修订，再进入任务 1。**G1** 和 **G5** 可在实施中顺带处理。
- 下一步建议: 修订 plan 中 G2（occupy_resource 保留位置显式说明）和 G4（工时计算块列入删除范围），然后开始任务 1 的实施。G1（calendar 替代 scheduler）和 G5（大规模资源池耗时测试）可在对应任务实施时顺带处理。
- 总体结论: 有条件通过

## 评审发现

### 估算器应接收 calendar 而非 scheduler

- ID: G1
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  estimate_internal_slot 的参数 scheduler 实际只使用 scheduler.calendar 的三个方法（adjust_to_working_time、get_efficiency、add_working_hours）。传入整个 scheduler 对象暴露了 config、logger、_last_algo_stats 等不相关状态，违反最小知识原则。改为传 calendar 对象可使估算器完全独立于 GreedyScheduler 类，便于独立测试和未来解耦。
- 建议:

  把参数从 scheduler: Any 改为 calendar: Any，调用方传入 scheduler.calendar。估算器内部直接调用 calendar.adjust_to_working_time / calendar.get_efficiency / calendar.add_working_hours。
- 证据:
  - `core/algorithms/greedy/scheduler.py:474-532`
  - `core/algorithms/greedy/auto_assign.py:157-203`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/auto_assign.py`

### occupy_resource 保留位置未在任务步骤中显式说明

- ID: G2
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  plan 任务 1 步骤 4 对 `scheduler.py` 的修改指令是："1. 保留资源缺失判断、自动分配尝试、errors.append、increment_counter 这些调用方职责”，然后 "4. 删除 _schedule_internal 内本地 _scaled_hours 与避让循环"。

  但 `scheduler.py:545-546` 的 `occupy_resource(machine_timeline, machine_id, earliest, end)` 和 `occupy_resource(operator_timeline, operator_id, earliest, end)` 既不属于估算逻辑（不应入估算器），也不属于列举的四类调用方职责（资源缺失判断、自动分配、errors、increment_counter）。

  实施者可能在删除避让循环时连带删除 `occupy_resource` 调用，导致排产结果不再占用资源——后续工序会重叠上去。
- 建议:

  在任务 1 步骤 4 对 scheduler.py 的修改指令中显式增加："保留 occupy_resource 调用，在获得 InternalSlotEstimate 的 start_time/end_time 后执行"。
- 证据:
  - `core/algorithms/greedy/scheduler.py:545-546`
  - `core/algorithms/greedy/scheduler.py`

### sgs.py 的 avg_proc_hours 计算段有死条件代码

- ID: G3
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  sgs.py:92-93 对已是 float 的 `op.setup_hours`、`op.unit_hours` 尚在调用 `parse_required_float()`。plan 任务 2 步骤 3 第 3 点正确指出了这个问题，要求“直接使用已规范化的 `op.setup_hours`、`op.unit_hours`”。

  但 sgs.py:97 还有一处 `if strict_mode and isinstance(exc, Exception):` ——这个 `isinstance` 检查永远为 True（因为 `exc` 来自 `except Exception`），属于冗余死条件。任务 2 删除 `parse_required_float` 调用后，整个 try/except 块可简化为直接计算。
- 建议:

  在任务 2 步骤 3 第 3 点旁补充：简化 avg_proc_hours 计算段时顺带删除 sgs.py:97 的死条件 isinstance 检查。
- 证据:
  - `core/algorithms/greedy/dispatch/sgs.py:88-102`
  - `core/algorithms/greedy/dispatch/sgs.py`

### scheduler.py 的工时计算块未明确列入删除范围

- ID: G4
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  scheduler.py:476-488 对 `setup_hours`、`unit_hours` 使用 `getattr(op, "setup_hours", 0) or 0`。当 `schedule_input_builder.py` 已把这两个字段规范化为 `float` 后，`or 0` 会把合法的 `0.0`（零工时）转成整数 `0`——不影响结果（因后续 `float()` 会转回）但增加了无意义的类型抖动。plan 任务 1 步骤 3 第 1 点说“直接使用 op.setup_hours、op.unit_hours”——也就是不再 `or 0`。

  但任务 1 步骤 4 对 scheduler.py 的修改指令只说“删除 _scaled_hours 与避让循环”，没有明确提及同时删除 476-488 的 `setup_hours = getattr(...) or 0` + `total_hours_base` 计算块（因为这些已移入估算器）。实施者可能只删除避让循环却保留工时计算，导致重复计算。
- 建议:

  在任务 1 步骤 4 第 4 点扩展为："删除 _schedule_internal 内的本地工时计算（setup_hours / unit_hours / qty / total_hours_base / isfinite 校验）、_scaled_hours 与避让循环，这些已全部转入估算器"。
- 证据:
  - `core/algorithms/greedy/scheduler.py:476-488`
  - `core/algorithms/greedy/scheduler.py`

### SGS 三重估算在大规模资源池下可能突破 30% 阈值

- ID: G5
- 严重级别: 中
- 分类: 性能
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  SGS 评分阶段对每个候选内部工序最多执行三次估算：
  1. `auto_assign(probe_only=True)` 内部：对每个 (machine, operator) 候选对调用 `estimate_internal_slot()`，候选对数 = M × O
  2. `_score_internal_candidate()` 本身：用选出的最优对再调用一次 `estimate_internal_slot()`
  3. `_schedule_internal() → auto_assign(probe_only=False)` 正式排产：再次对所有候选对估算

  总估算次数 = 候选数 × (M×O + 1 + M×O)。当 M=5、O=5、候选数=20 时，每轮 SGS 迭代约 1020 次估算。这比当前的近似评分（仅调用 `find_earliest_available_start`，复杂度低得多）要慢很多。

  plan 的 30% 阈值是合理的守门，但当前只用 `smoke_phase10_sgs_auto_assign.py` 做耗时对照——这个测试的候选数和资源池规模可能偏小，无法暴露大规模场景的耗时曲线。
- 建议:

  在任务 2 步骤 6 的耗时对照中补充：若 `smoke_phase10` 的 `resource_pool` 候选对总数 < 50，应额外构造一个候选对 > 200 的场景做补充计时，确认三重估算在大规模资源池下仍在 30% 内。
- 证据:
  - `core/algorithms/greedy/dispatch/sgs.py:230-263`
  - `core/algorithms/greedy/dispatch/sgs.py`

### 避让上界数学证明成立

- ID: G6
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  避让上界 `guard_limit = N_machine + N_operator + N_downtime + 1` 的正确性取决于 `earliest` 严格单调递增。经数学证明：

  1. `shift_to = max(m_shift, o_shift, d_shift)` —— 取所有重叠片段的最迟结束时刻
  2. `earliest = max(earliest, shift_to)` —— `earliest` 严格递增
  3. `adjust_to_working_time(earliest)` —— 只会前移或不动，不会后退
  4. 每次推迟至少越过一个片段的 `end` 时刻（因为 `shift_to >= segment.end`）
  5. 不同片段的 `end` 互不相同（即使相同，合并处理不会增加迭代次数）

  因此最多迭代 N_machine + N_operator + N_downtime + 1 次。但注意：效率变化可能导致 `end` 扩大，使新 `(earliest, end)` 与之前未重叠的片段产生重叠。但每个新重叠片段只触发一次推迟，不会重复计算。

  上界证明成立 ✅
- 证据:
  - `core/algorithms/greedy/scheduler.py:510-533`
  - `core/algorithms/greedy/scheduler.py`

## 评审里程碑

### M1 · 第一轮：设计纯度与接口审查

- 状态: 已完成
- 记录时间: 2026-04-07T07:05:45.311Z
- 已审模块: core/algorithms/greedy/scheduler.py, core/algorithms/greedy/auto_assign.py, core/algorithms/greedy/dispatch/sgs.py
- 摘要:

  ## 前轮修订采纳情况核实

  前轮审查提出的 9 个发现（F1-F9），plan 已全部采纳修订：
  - **F1**（`batch_progress` 精简为 `prev_end`）：已采纳，任务 1 步骤 3 参数表明确列出 `prev_end`（调用方预计算）✅
  - **F2**（避让上界表达式明确化）：已采纳，任务 1 步骤 3 第 4 点写出了完整表达式 ✅
  - **F5**（导入清理）：已采纳，任务 2 步骤 3 第 6 点明确删除 `parse_required_float` 和 `find_earliest_available_start` ✅
  - **F7**（`abort_after` 两处检查点）：已采纳，任务 1 步骤 3 第 5 点明确列出初始早停和循环内早停 ✅
  - **F8**（零时长工序边界）：已采纳，任务 1 步骤 1 第 5 点增加了 `setup_hours=0` + `unit_hours=0` 用例 ✅
  - **F4**（双重自动分配已知局限）：已采纳，"不做的事项"第 10 条包含完整说明 ✅

  ## 估算器参数表设计审查

  Plan 定义 `estimate_internal_slot` 接收 `scheduler` 作为参数。但经逐行对照 `scheduler.py:474-532` 和 `auto_assign.py:157-203`，估算器实际仅使用三个日历方法：
  - `scheduler.calendar.adjust_to_working_time(earliest, priority=priority, operator_id=operator_id)`
  - `scheduler.calendar.get_efficiency(start, operator_id=operator_id)`
  - `scheduler.calendar.add_working_hours(earliest, total_hours, priority=priority, operator_id=operator_id)`

  传入 `scheduler` 对象会暴露 `config`、`logger`、`_last_algo_stats` 等完全不相关的内部状态，违反最小知识原则。更精简的设计是传入 `calendar`（即 `scheduler.calendar`），这样估算器只依赖日历服务接口，不依赖 `GreedyScheduler` 类本身。

  ## `priority` 参数缺失分析

  Plan 的参数"至少包含"列表缺少 `priority`。但三个日历方法都需要 `priority` 参数。当前代码从 `batch` 对象提取：`priority = getattr(batch, "priority", None)`。

  由于 `batch` 已经是参数之一，估算器可以在内部提取 `priority`。但这意味着估算器需要知道 `batch` 的 `priority` 属性语义——这在"只做估算、不做字段清洗"的职责边界下是合理的（`priority` 不需要解析，直接透传即可）。

  ## `InternalSlotEstimate.changeover_penalty` 职责归属

  Plan 把 `changeover_penalty` 放进估算结果。经核实：
  - `auto_assign.py:210-211`：基于 `last_op_type_by_machine.get(mid)` 与 `cur_type` 比较
  - `sgs.py:335-340`：同样逻辑

  这需要 `last_op_type_by_machine` 和 `op.op_type_name`——两者都已在参数表中。估算器返回 `changeover_penalty` 让调用方构建排序键或评分元组，避免调用方重复提取工种名。设计合理 ✅
- 结论:

  前轮修订已全部采纳。参数表有一处设计改进机会（传 `calendar` 而非 `scheduler`），但不阻断实施。
- 证据:
  - `core/algorithms/greedy/scheduler.py:413-562#_schedule_internal`
  - `core/algorithms/greedy/auto_assign.py:11-230#auto_assign_internal_resources`
- 下一步建议:

  进入第二轮：隐性耦合与遗漏猎杀
- 问题:
  - [中] 可维护性: 估算器应接收 calendar 而非 scheduler

### M2 · 第二轮：隐性耦合与遗漏猎杀

- 状态: 已完成
- 记录时间: 2026-04-07T07:06:17.821Z
- 已审模块: core/algorithms/greedy/downtime.py, core/algorithms/greedy/dispatch/batch_order.py, core/services/scheduler/schedule_optimizer_steps.py
- 摘要:

  ## 隐性状态操作追踪

  ### 1. `occupy_resource` 保留位置

  `_schedule_internal()` 在 `scheduler.py:545-546` 调用 `occupy_resource`，这是排产成功后的副作用操作。Plan 任务 1 步骤 4 列出了调用方应保留的职责清单（资源缺失判断、自动分配、errors、increment_counter），但**未显式提及 `occupy_resource`**。

  由于 plan 说"删除 `_schedule_internal()` 内本地 `_scaled_hours()` 与避让循环"，实施者可能在清理代码时连带删除 `occupy_resource` 调用。`occupy_resource` 不属于估算（不应进入 `internal_slot.py`），也不属于运行期状态更新（不在任务 3 的 `runtime_state.py` 范围——那里只收口忙时和工种更新），它属于资源占用，应保留在 `_schedule_internal()` 中。

  ### 2. 工时计算块清理范围不够明确

  `scheduler.py:476-488` 有一段独立的工时计算逻辑（`setup_hours = getattr(op, "setup_hours", 0) or 0` 到 `total_hours_base` 校验）。Plan 说删除 `_scaled_hours` 和避让循环，但这段工时计算也应同时删除（因为已移入估算器）。Plan 的步骤描述没有明确这一点。

  另外，当前代码的 `getattr(op, "setup_hours", 0) or 0` 模式会把 `0.0` 转成 `0`（整数）。虽然后续 `float()` 会转回来，但这是无意义的类型抖动。估算器直接使用 `op.setup_hours`（已是 float）更干净。

  ### 3. SGS `avg_proc_hours` 计算段的死条件

  `sgs.py:97` 有 `if strict_mode and isinstance(exc, Exception):`，由于 `exc` 来自 `except Exception`，`isinstance` 检查永远为 True。任务 2 简化 `avg_proc_hours` 计算时应顺带清除。

  ### 4. `batch_order.py` 和 `sgs.py` 的 `try/except Exception: pass` 吞异常

  Plan 任务 3 步骤 4 明确要求"调用共享函数后，删除现有吞异常分支"。经核实：
  - `batch_order.py:102-103`：`except Exception: pass` 包裹忙时累计
  - `sgs.py:470-472`：`except Exception: pass` 包裹忙时累计

  这两处的 `try/except` 保护的是简单的 `dict` 加法和 `timedelta` 除法——正常情况下不会抛异常。唯一可能失败的场景是 `result.end_time` 或 `result.start_time` 为 None，但前面的 `if result and result.start_time and result.end_time:` 已经守门。Plan 删除这些吞异常分支是正确的。

  ### 5. `runtime_state.py` 与 `occupy_resource` 的职责边界

  任务 3 新建的 `runtime_state.py` 只负责"忙时累计"和"工种/最近结束时间更新"。`occupy_resource`（往 `machine_timeline` / `operator_timeline` 插入区间）不在 `runtime_state.py` 的职责范围内——它在 `downtime.py` 中定义且直接被 `_schedule_internal()` 调用。这两个职责保持分离是正确的，但 plan 应在文件职责映射中明确这一点，避免实施者把 `occupy_resource` 也搬进 `runtime_state.py`。
- 结论:

  发现 3 处 plan 步骤描述中可能被实施者忽略的隐性状态操作，其中 G2 为中等严重级别（`occupy_resource` 保留位置未显式说明），G3 和 G4 为低级别。
- 证据:
  - `core/algorithms/greedy/scheduler.py:545-546`
  - `core/algorithms/greedy/scheduler.py:476-488`
  - `core/algorithms/greedy/dispatch/batch_order.py:86-106`
  - `core/algorithms/greedy/dispatch/sgs.py:453-475`
  - `core/algorithms/greedy/dispatch/sgs.py:92-99#avg_proc_hours`
- 下一步建议:

  进入第三轮：性能风险与边界条件
- 问题:
  - [中] 可维护性: occupy_resource 保留位置未在任务步骤中显式说明
  - [低] 其他: sgs.py 的 avg_proc_hours 计算段有死条件代码
  - [低] 其他: scheduler.py 的工时计算块未明确列入删除范围

### M3 · 第三轮：性能风险与边界条件

- 状态: 已完成
- 记录时间: 2026-04-07T07:06:54.213Z
- 已审模块: core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_optimizer_steps.py, core/algorithms/evaluation.py, core/algorithms/dispatch_rules.py, core/algorithms/ortools_bottleneck.py, core/algorithms/greedy/date_parsers.py
- 摘要:

  ## 性能风险分析

  ### 1. 三重估算的乘数效应

  当前 SGS 评分路径（`sgs.py:230-263`）对缺资源的内部工序调用 `auto_assign(probe_only=True)`，返回 `(machine_id, operator_id)` 后使用 `find_earliest_available_start()` 做近似评分。改用 `estimate_internal_slot()` 后，评分路径变成：

  | 阶段 | 当前实现 | 改造后 |
  |---|---|---|
  | ① SGS 评分补资源 | `auto_assign(probe)` 内部循环 M×O 次，每次用快速 `find_overlap_shift_end` | `auto_assign(probe)` 内部循环 M×O 次，每次用完整 `estimate_internal_slot` |
  | ② SGS 评分取时间 | 3 次 `find_earliest_available_start`（链式近似） | 1 次 `estimate_internal_slot`（真实估算） |
  | ③ 正式排产 | `_schedule_internal` 内 `auto_assign(正式)` + 避让循环 | `_schedule_internal` 调 `estimate_internal_slot` |

  关键开销差异在 ① 阶段：当前的 `auto_assign` 只做"三路 `find_overlap_shift_end`"（每路扫一遍片段列表），改造后变成"完整避让循环"（可能迭代多次）。乘数 = M×O×候选数×每轮 SGS 迭代数。

  ### 2. `smoke_phase10` 的代表性分析

  `smoke_phase10_sgs_auto_assign.py` 被用作耗时基线。但这个测试的规模（批次数、设备数、人员数、碎片密度）可能偏小。Plan 的 30% 阈值守门是正确的，但如果测试数据集本身很小（例如 3 台设备、5 个人员），三重估算的开销会被掩盖。

  建议：在耗时对照步骤中检查 `resource_pool` 的候选对总数——若 < 50 则应额外构造大规模场景。

  ### 3. 邻域去重的内存与查找开销

  Plan 任务 5 步骤 4 使用 `seen_hashes` 以 `tuple(cand_order)` 为键。对于 n 个批次：
  - 每个键的内存：约 `n * 8` 字节（CPython 元组元素指针）
  - 哈希计算：O(n)
  - 集合查找：O(n)（哈希后比较）
  - 最多 `it_limit` 个键（≤ 5000）

  当 n=200 时，每个键约 1.6KB，5000 个键约 8MB——完全可控。当 n > 1000 时，可能达到 80MB，但这种规模下 `time.time() > deadline` 会先触发超时。

  ### 4. 避让上界的数学证明

  对 `guard_limit = N_machine + N_operator + N_downtime + 1` 的正确性：
  - `earliest` 严格单调递增（`max(earliest, shift_to)` + `adjust_to_working_time` 只前移不后退）
  - 每次迭代至少推过一个片段的 `end` 时刻
  - 三条时间线的片段互不混淆
  - 因此总迭代次数 ≤ 三条时间线的片段总数 + 1

  效率变化可能导致 `end` 扩大，使新 `(earliest, end)` 与之前未重叠的片段产生重叠。但每个片段只能"首次重叠"一次——一旦 `earliest` 推过其 `end`，就不会再回来。上界证明成立 ✅

  ### 5. `bisect.insort` 在 Python 3.8 下的兼容性

  `bisect.insort(list, (start, end))` 在 Python 3.8 下：
  - 不使用 `key=` 参数（Python 3.10 才引入）✅
  - 元组按自然序（先 start 后 end）排序 ✅
  - 不做区间合并——多个相邻或重叠片段仍然独立存在 ✅

  ### 6. `build_order` 共享安全性

  `scheduler.schedule()` 通过 `batch_order = batch_order_override or order_list` 接收外部顺序。内部只读取 `batch_order`，不修改 `batch_order_override`。多个 `dispatch_rule` 迭代共享同一 `order` 是安全的 ✅

  ### 7. 任务 4 日期替换等价性复核

  逐行对照三个模块的 `_due_exclusive()` / `_parse_due_date()` 实现：
  - `evaluation.py:38-58`：与 `date_parsers.parse_date()` 功能等价 ✅
  - `dispatch_rules.py:25-28`：与 `evaluation.py` 完全一致 ✅
  - `ortools_bottleneck.py:23-42`：与 `evaluation.py` 完全一致 ✅
  - `schedule_optimizer.py:343-357` `_parse_datetime()`：与 `date_parsers.parse_datetime()` 功能等价（同样的格式顺序、同样的字符替换）✅

  替换安全，任务 4 的设计正确。
- 结论:

  避让上界数学证明成立、邻域去重内存可控、有序插入兼容性已确认。新发现一处中等风险：SGS 路径的三重估算乘数效应可能在自动分配候选数多时突破 30% 阈值，plan 应在耗时对照步骤中明确候选数阈值。
- 证据:
  - `core/algorithms/greedy/downtime.py:31-57#find_earliest_available_start`
  - `core/algorithms/greedy/downtime.py:60-77#find_overlap_shift_end`
  - `core/services/scheduler/schedule_optimizer.py:139-261#_run_local_search`
  - `core/services/scheduler/schedule_optimizer_steps.py:331-392`
  - `core/algorithms/greedy/dispatch/sgs.py:230-263`
- 下一步建议:

  终结审查，给出最终结论
- 问题:
  - [中] 性能: SGS 三重估算在大规模资源池下可能突破 30% 阈值
  - [低] 其他: 避让上界数学证明成立

## 最终结论

## 审查总结

经过三轮深度审查（设计纯度审查 → 隐性耦合猎杀 → 性能风险与边界条件），对 11 个核心代码文件进行了独立逐行核实。

### 总体评价

**Plan 质量优秀，在前轮审查后已经达到很高的完成度。** 前轮提出的全部 9 个发现（F1-F9）都已被采纳修订——参数表精简为 `prev_end`、避让上界表达式明确化、`abort_after` 两处检查点、导入清理、零时长边界用例、双重自动分配已知局限说明，全部到位。

### 本轮新发现的 6 个问题

| 编号 | 严重级别 | 问题 | 建议 |
|---|---|---|---|
| G1 | 中 | 估算器参数应传 `calendar` 而非 `scheduler`——实际只用三个日历方法，传整个调度器暴露不必要的内部状态 | 改为 `calendar: Any`，调用方传 `scheduler.calendar` |
| G2 | 中 | `occupy_resource` 保留位置未在任务 1 步骤 4 中显式说明——实施者可能在删除避让循环时连带删除，导致排产结果不占用资源 | 在步骤 4 增加"保留 `occupy_resource` 调用" |
| G5 | 中 | SGS 三重估算（probe → score → schedule）在大规模资源池下可能突破 30% 阈值——`smoke_phase10` 的候选对数可能偏小 | 补充候选对 > 200 的大规模耗时测试 |
| G3 | 低 | `sgs.py:97` 的 `isinstance(exc, Exception)` 是永真死条件，应在任务 2 简化 `avg_proc_hours` 时顺带删除 | 在任务 2 步骤 3 补充 |
| G4 | 低 | `scheduler.py:476-488` 的工时计算块未明确列入删除范围——步骤 4 只说删 `_scaled_hours` 和避让循环 | 扩展步骤 4 描述范围 |
| G6 | 低 | 避让上界数学证明成立——`earliest` 严格单调递增 + 每次至少越过一个片段 = 上界 N+1 ✅ | 无需修改 |

### 本轮验证通过的关键设计决策

1. **避让上界 `N_machine + N_operator + N_downtime + 1`**：数学证明成立 ✅
2. **`bisect.insort` 兼容 Python 3.8**：不使用 `key=`，元组自然序排序 ✅
3. **`build_order` 多策略共享**：调度器内部只读取不修改 ✅
4. **日期函数替换**：`evaluation.py`、`dispatch_rules.py`、`ortools_bottleneck.py` 三份重复实现与共享版本功能等价 ✅
5. **`schedule_optimizer._parse_datetime` 替换**：与 `date_parsers.parse_datetime` 功能等价 ✅
6. **`conditional_op_type` 双模式设计**：seed 条件覆盖 vs 派工直接更新，两种语义精确匹配 ✅
7. **邻域去重内存**：n=200 批次 × 5000 次迭代 ≈ 8MB，完全可控 ✅

### 结论

Plan 可以按现有设计开始实施。建议先处理 **G2**（`occupy_resource` 保留位置）这一处最容易导致实施错误的 plan 文本修订，再进入任务 1。**G1** 和 **G5** 可在实施中顺带处理。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mno9yrl5-pah4pa",
  "createdAt": "2026-04-07T00:00:00.000Z",
  "updatedAt": "2026-04-07T07:07:11.247Z",
  "finalizedAt": "2026-04-07T07:07:11.247Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "算法层统一估算与派工重构plan第二轮独立深度审查",
    "date": "2026-04-07",
    "overview": "对采纳前轮修订建议后的 plan 当前版本进行独立三轮深度审查（设计审查 → 隐性耦合猎杀 → 边界与遗漏分析）"
  },
  "scope": {
    "markdown": "# 算法层统一估算与派工重构 Plan 第二轮独立深度审查\n\n**审查日期**: 2026-04-07\n**审查对象**: `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`（已采纳前轮全部修订建议的版本）\n**审查目标**: 在前轮审查已验证引用链精确性的基础上，聚焦于：\n1. 估算器接口设计是否最简且正确\n2. 三重估算开销是否可能突破 30% 阈值\n3. plan 步骤描述是否有遗漏的隐性状态操作\n4. 新发现的代码问题或设计缺陷\n\n## 审查策略\n\n- **第一轮**：设计纯度与接口审查 — 检查 `estimate_internal_slot` 的参数表是否最精简、职责边界是否清晰\n- **第二轮**：隐性耦合与遗漏猎杀 — 追踪 plan 步骤中可能遗漏的状态操作（`occupy_resource`、`batch.quantity` 来源、`priority` 传递）\n- **第三轮**：性能风险与边界条件 — 分析三重估算的真实开销、邻域去重的内存模型、避让上界的数学证明"
  },
  "summary": {
    "latestConclusion": "## 审查总结\n\n经过三轮深度审查（设计纯度审查 → 隐性耦合猎杀 → 性能风险与边界条件），对 11 个核心代码文件进行了独立逐行核实。\n\n### 总体评价\n\n**Plan 质量优秀，在前轮审查后已经达到很高的完成度。** 前轮提出的全部 9 个发现（F1-F9）都已被采纳修订——参数表精简为 `prev_end`、避让上界表达式明确化、`abort_after` 两处检查点、导入清理、零时长边界用例、双重自动分配已知局限说明，全部到位。\n\n### 本轮新发现的 6 个问题\n\n| 编号 | 严重级别 | 问题 | 建议 |\n|---|---|---|---|\n| G1 | 中 | 估算器参数应传 `calendar` 而非 `scheduler`——实际只用三个日历方法，传整个调度器暴露不必要的内部状态 | 改为 `calendar: Any`，调用方传 `scheduler.calendar` |\n| G2 | 中 | `occupy_resource` 保留位置未在任务 1 步骤 4 中显式说明——实施者可能在删除避让循环时连带删除，导致排产结果不占用资源 | 在步骤 4 增加\"保留 `occupy_resource` 调用\" |\n| G5 | 中 | SGS 三重估算（probe → score → schedule）在大规模资源池下可能突破 30% 阈值——`smoke_phase10` 的候选对数可能偏小 | 补充候选对 > 200 的大规模耗时测试 |\n| G3 | 低 | `sgs.py:97` 的 `isinstance(exc, Exception)` 是永真死条件，应在任务 2 简化 `avg_proc_hours` 时顺带删除 | 在任务 2 步骤 3 补充 |\n| G4 | 低 | `scheduler.py:476-488` 的工时计算块未明确列入删除范围——步骤 4 只说删 `_scaled_hours` 和避让循环 | 扩展步骤 4 描述范围 |\n| G6 | 低 | 避让上界数学证明成立——`earliest` 严格单调递增 + 每次至少越过一个片段 = 上界 N+1 ✅ | 无需修改 |\n\n### 本轮验证通过的关键设计决策\n\n1. **避让上界 `N_machine + N_operator + N_downtime + 1`**：数学证明成立 ✅\n2. **`bisect.insort` 兼容 Python 3.8**：不使用 `key=`，元组自然序排序 ✅\n3. **`build_order` 多策略共享**：调度器内部只读取不修改 ✅\n4. **日期函数替换**：`evaluation.py`、`dispatch_rules.py`、`ortools_bottleneck.py` 三份重复实现与共享版本功能等价 ✅\n5. **`schedule_optimizer._parse_datetime` 替换**：与 `date_parsers.parse_datetime` 功能等价 ✅\n6. **`conditional_op_type` 双模式设计**：seed 条件覆盖 vs 派工直接更新，两种语义精确匹配 ✅\n7. **邻域去重内存**：n=200 批次 × 5000 次迭代 ≈ 8MB，完全可控 ✅\n\n### 结论\n\nPlan 可以按现有设计开始实施。建议先处理 **G2**（`occupy_resource` 保留位置）这一处最容易导致实施错误的 plan 文本修订，再进入任务 1。**G1** 和 **G5** 可在实施中顺带处理。",
    "recommendedNextAction": "修订 plan 中 G2（occupy_resource 保留位置显式说明）和 G4（工时计算块列入删除范围），然后开始任务 1 的实施。G1（calendar 替代 scheduler）和 G5（大规模资源池耗时测试）可在对应任务实施时顺带处理。",
    "reviewedModules": [
      "core/algorithms/greedy/scheduler.py",
      "core/algorithms/greedy/auto_assign.py",
      "core/algorithms/greedy/dispatch/sgs.py",
      "core/algorithms/greedy/downtime.py",
      "core/algorithms/greedy/dispatch/batch_order.py",
      "core/services/scheduler/schedule_optimizer_steps.py",
      "core/services/scheduler/schedule_optimizer.py",
      "core/algorithms/evaluation.py",
      "core/algorithms/dispatch_rules.py",
      "core/algorithms/ortools_bottleneck.py",
      "core/algorithms/greedy/date_parsers.py",
      "core/services/scheduler/schedule_input_builder.py"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 6,
    "severity": {
      "high": 0,
      "medium": 3,
      "low": 3
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "第一轮：设计纯度与接口审查",
      "status": "completed",
      "recordedAt": "2026-04-07T07:05:45.311Z",
      "summaryMarkdown": "## 前轮修订采纳情况核实\n\n前轮审查提出的 9 个发现（F1-F9），plan 已全部采纳修订：\n- **F1**（`batch_progress` 精简为 `prev_end`）：已采纳，任务 1 步骤 3 参数表明确列出 `prev_end`（调用方预计算）✅\n- **F2**（避让上界表达式明确化）：已采纳，任务 1 步骤 3 第 4 点写出了完整表达式 ✅\n- **F5**（导入清理）：已采纳，任务 2 步骤 3 第 6 点明确删除 `parse_required_float` 和 `find_earliest_available_start` ✅\n- **F7**（`abort_after` 两处检查点）：已采纳，任务 1 步骤 3 第 5 点明确列出初始早停和循环内早停 ✅\n- **F8**（零时长工序边界）：已采纳，任务 1 步骤 1 第 5 点增加了 `setup_hours=0` + `unit_hours=0` 用例 ✅\n- **F4**（双重自动分配已知局限）：已采纳，\"不做的事项\"第 10 条包含完整说明 ✅\n\n## 估算器参数表设计审查\n\nPlan 定义 `estimate_internal_slot` 接收 `scheduler` 作为参数。但经逐行对照 `scheduler.py:474-532` 和 `auto_assign.py:157-203`，估算器实际仅使用三个日历方法：\n- `scheduler.calendar.adjust_to_working_time(earliest, priority=priority, operator_id=operator_id)`\n- `scheduler.calendar.get_efficiency(start, operator_id=operator_id)`\n- `scheduler.calendar.add_working_hours(earliest, total_hours, priority=priority, operator_id=operator_id)`\n\n传入 `scheduler` 对象会暴露 `config`、`logger`、`_last_algo_stats` 等完全不相关的内部状态，违反最小知识原则。更精简的设计是传入 `calendar`（即 `scheduler.calendar`），这样估算器只依赖日历服务接口，不依赖 `GreedyScheduler` 类本身。\n\n## `priority` 参数缺失分析\n\nPlan 的参数\"至少包含\"列表缺少 `priority`。但三个日历方法都需要 `priority` 参数。当前代码从 `batch` 对象提取：`priority = getattr(batch, \"priority\", None)`。\n\n由于 `batch` 已经是参数之一，估算器可以在内部提取 `priority`。但这意味着估算器需要知道 `batch` 的 `priority` 属性语义——这在\"只做估算、不做字段清洗\"的职责边界下是合理的（`priority` 不需要解析，直接透传即可）。\n\n## `InternalSlotEstimate.changeover_penalty` 职责归属\n\nPlan 把 `changeover_penalty` 放进估算结果。经核实：\n- `auto_assign.py:210-211`：基于 `last_op_type_by_machine.get(mid)` 与 `cur_type` 比较\n- `sgs.py:335-340`：同样逻辑\n\n这需要 `last_op_type_by_machine` 和 `op.op_type_name`——两者都已在参数表中。估算器返回 `changeover_penalty` 让调用方构建排序键或评分元组，避免调用方重复提取工种名。设计合理 ✅",
      "conclusionMarkdown": "前轮修订已全部采纳。参数表有一处设计改进机会（传 `calendar` 而非 `scheduler`），但不阻断实施。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 413,
          "lineEnd": 562,
          "symbol": "_schedule_internal"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 11,
          "lineEnd": 230,
          "symbol": "auto_assign_internal_resources"
        }
      ],
      "reviewedModules": [
        "core/algorithms/greedy/scheduler.py",
        "core/algorithms/greedy/auto_assign.py",
        "core/algorithms/greedy/dispatch/sgs.py"
      ],
      "recommendedNextAction": "进入第二轮：隐性耦合与遗漏猎杀",
      "findingIds": [
        "G1"
      ]
    },
    {
      "id": "M2",
      "title": "第二轮：隐性耦合与遗漏猎杀",
      "status": "completed",
      "recordedAt": "2026-04-07T07:06:17.821Z",
      "summaryMarkdown": "## 隐性状态操作追踪\n\n### 1. `occupy_resource` 保留位置\n\n`_schedule_internal()` 在 `scheduler.py:545-546` 调用 `occupy_resource`，这是排产成功后的副作用操作。Plan 任务 1 步骤 4 列出了调用方应保留的职责清单（资源缺失判断、自动分配、errors、increment_counter），但**未显式提及 `occupy_resource`**。\n\n由于 plan 说\"删除 `_schedule_internal()` 内本地 `_scaled_hours()` 与避让循环\"，实施者可能在清理代码时连带删除 `occupy_resource` 调用。`occupy_resource` 不属于估算（不应进入 `internal_slot.py`），也不属于运行期状态更新（不在任务 3 的 `runtime_state.py` 范围——那里只收口忙时和工种更新），它属于资源占用，应保留在 `_schedule_internal()` 中。\n\n### 2. 工时计算块清理范围不够明确\n\n`scheduler.py:476-488` 有一段独立的工时计算逻辑（`setup_hours = getattr(op, \"setup_hours\", 0) or 0` 到 `total_hours_base` 校验）。Plan 说删除 `_scaled_hours` 和避让循环，但这段工时计算也应同时删除（因为已移入估算器）。Plan 的步骤描述没有明确这一点。\n\n另外，当前代码的 `getattr(op, \"setup_hours\", 0) or 0` 模式会把 `0.0` 转成 `0`（整数）。虽然后续 `float()` 会转回来，但这是无意义的类型抖动。估算器直接使用 `op.setup_hours`（已是 float）更干净。\n\n### 3. SGS `avg_proc_hours` 计算段的死条件\n\n`sgs.py:97` 有 `if strict_mode and isinstance(exc, Exception):`，由于 `exc` 来自 `except Exception`，`isinstance` 检查永远为 True。任务 2 简化 `avg_proc_hours` 计算时应顺带清除。\n\n### 4. `batch_order.py` 和 `sgs.py` 的 `try/except Exception: pass` 吞异常\n\nPlan 任务 3 步骤 4 明确要求\"调用共享函数后，删除现有吞异常分支\"。经核实：\n- `batch_order.py:102-103`：`except Exception: pass` 包裹忙时累计\n- `sgs.py:470-472`：`except Exception: pass` 包裹忙时累计\n\n这两处的 `try/except` 保护的是简单的 `dict` 加法和 `timedelta` 除法——正常情况下不会抛异常。唯一可能失败的场景是 `result.end_time` 或 `result.start_time` 为 None，但前面的 `if result and result.start_time and result.end_time:` 已经守门。Plan 删除这些吞异常分支是正确的。\n\n### 5. `runtime_state.py` 与 `occupy_resource` 的职责边界\n\n任务 3 新建的 `runtime_state.py` 只负责\"忙时累计\"和\"工种/最近结束时间更新\"。`occupy_resource`（往 `machine_timeline` / `operator_timeline` 插入区间）不在 `runtime_state.py` 的职责范围内——它在 `downtime.py` 中定义且直接被 `_schedule_internal()` 调用。这两个职责保持分离是正确的，但 plan 应在文件职责映射中明确这一点，避免实施者把 `occupy_resource` 也搬进 `runtime_state.py`。",
      "conclusionMarkdown": "发现 3 处 plan 步骤描述中可能被实施者忽略的隐性状态操作，其中 G2 为中等严重级别（`occupy_resource` 保留位置未显式说明），G3 和 G4 为低级别。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 545,
          "lineEnd": 546
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 476,
          "lineEnd": 488
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py",
          "lineStart": 86,
          "lineEnd": 106
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 453,
          "lineEnd": 475
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 92,
          "lineEnd": 99,
          "symbol": "avg_proc_hours"
        }
      ],
      "reviewedModules": [
        "core/algorithms/greedy/downtime.py",
        "core/algorithms/greedy/dispatch/batch_order.py",
        "core/services/scheduler/schedule_optimizer_steps.py"
      ],
      "recommendedNextAction": "进入第三轮：性能风险与边界条件",
      "findingIds": [
        "G2",
        "G3",
        "G4"
      ]
    },
    {
      "id": "M3",
      "title": "第三轮：性能风险与边界条件",
      "status": "completed",
      "recordedAt": "2026-04-07T07:06:54.213Z",
      "summaryMarkdown": "## 性能风险分析\n\n### 1. 三重估算的乘数效应\n\n当前 SGS 评分路径（`sgs.py:230-263`）对缺资源的内部工序调用 `auto_assign(probe_only=True)`，返回 `(machine_id, operator_id)` 后使用 `find_earliest_available_start()` 做近似评分。改用 `estimate_internal_slot()` 后，评分路径变成：\n\n| 阶段 | 当前实现 | 改造后 |\n|---|---|---|\n| ① SGS 评分补资源 | `auto_assign(probe)` 内部循环 M×O 次，每次用快速 `find_overlap_shift_end` | `auto_assign(probe)` 内部循环 M×O 次，每次用完整 `estimate_internal_slot` |\n| ② SGS 评分取时间 | 3 次 `find_earliest_available_start`（链式近似） | 1 次 `estimate_internal_slot`（真实估算） |\n| ③ 正式排产 | `_schedule_internal` 内 `auto_assign(正式)` + 避让循环 | `_schedule_internal` 调 `estimate_internal_slot` |\n\n关键开销差异在 ① 阶段：当前的 `auto_assign` 只做\"三路 `find_overlap_shift_end`\"（每路扫一遍片段列表），改造后变成\"完整避让循环\"（可能迭代多次）。乘数 = M×O×候选数×每轮 SGS 迭代数。\n\n### 2. `smoke_phase10` 的代表性分析\n\n`smoke_phase10_sgs_auto_assign.py` 被用作耗时基线。但这个测试的规模（批次数、设备数、人员数、碎片密度）可能偏小。Plan 的 30% 阈值守门是正确的，但如果测试数据集本身很小（例如 3 台设备、5 个人员），三重估算的开销会被掩盖。\n\n建议：在耗时对照步骤中检查 `resource_pool` 的候选对总数——若 < 50 则应额外构造大规模场景。\n\n### 3. 邻域去重的内存与查找开销\n\nPlan 任务 5 步骤 4 使用 `seen_hashes` 以 `tuple(cand_order)` 为键。对于 n 个批次：\n- 每个键的内存：约 `n * 8` 字节（CPython 元组元素指针）\n- 哈希计算：O(n)\n- 集合查找：O(n)（哈希后比较）\n- 最多 `it_limit` 个键（≤ 5000）\n\n当 n=200 时，每个键约 1.6KB，5000 个键约 8MB——完全可控。当 n > 1000 时，可能达到 80MB，但这种规模下 `time.time() > deadline` 会先触发超时。\n\n### 4. 避让上界的数学证明\n\n对 `guard_limit = N_machine + N_operator + N_downtime + 1` 的正确性：\n- `earliest` 严格单调递增（`max(earliest, shift_to)` + `adjust_to_working_time` 只前移不后退）\n- 每次迭代至少推过一个片段的 `end` 时刻\n- 三条时间线的片段互不混淆\n- 因此总迭代次数 ≤ 三条时间线的片段总数 + 1\n\n效率变化可能导致 `end` 扩大，使新 `(earliest, end)` 与之前未重叠的片段产生重叠。但每个片段只能\"首次重叠\"一次——一旦 `earliest` 推过其 `end`，就不会再回来。上界证明成立 ✅\n\n### 5. `bisect.insort` 在 Python 3.8 下的兼容性\n\n`bisect.insort(list, (start, end))` 在 Python 3.8 下：\n- 不使用 `key=` 参数（Python 3.10 才引入）✅\n- 元组按自然序（先 start 后 end）排序 ✅\n- 不做区间合并——多个相邻或重叠片段仍然独立存在 ✅\n\n### 6. `build_order` 共享安全性\n\n`scheduler.schedule()` 通过 `batch_order = batch_order_override or order_list` 接收外部顺序。内部只读取 `batch_order`，不修改 `batch_order_override`。多个 `dispatch_rule` 迭代共享同一 `order` 是安全的 ✅\n\n### 7. 任务 4 日期替换等价性复核\n\n逐行对照三个模块的 `_due_exclusive()` / `_parse_due_date()` 实现：\n- `evaluation.py:38-58`：与 `date_parsers.parse_date()` 功能等价 ✅\n- `dispatch_rules.py:25-28`：与 `evaluation.py` 完全一致 ✅\n- `ortools_bottleneck.py:23-42`：与 `evaluation.py` 完全一致 ✅\n- `schedule_optimizer.py:343-357` `_parse_datetime()`：与 `date_parsers.parse_datetime()` 功能等价（同样的格式顺序、同样的字符替换）✅\n\n替换安全，任务 4 的设计正确。",
      "conclusionMarkdown": "避让上界数学证明成立、邻域去重内存可控、有序插入兼容性已确认。新发现一处中等风险：SGS 路径的三重估算乘数效应可能在自动分配候选数多时突破 30% 阈值，plan 应在耗时对照步骤中明确候选数阈值。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/downtime.py",
          "lineStart": 31,
          "lineEnd": 57,
          "symbol": "find_earliest_available_start"
        },
        {
          "path": "core/algorithms/greedy/downtime.py",
          "lineStart": 60,
          "lineEnd": 77,
          "symbol": "find_overlap_shift_end"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 139,
          "lineEnd": 261,
          "symbol": "_run_local_search"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py",
          "lineStart": 331,
          "lineEnd": 392
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 230,
          "lineEnd": 263
        }
      ],
      "reviewedModules": [
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/scheduler/schedule_optimizer_steps.py",
        "core/algorithms/evaluation.py",
        "core/algorithms/dispatch_rules.py",
        "core/algorithms/ortools_bottleneck.py",
        "core/algorithms/greedy/date_parsers.py"
      ],
      "recommendedNextAction": "终结审查，给出最终结论",
      "findingIds": [
        "G5",
        "G6"
      ]
    }
  ],
  "findings": [
    {
      "id": "G1",
      "severity": "medium",
      "category": "maintainability",
      "title": "估算器应接收 calendar 而非 scheduler",
      "descriptionMarkdown": "estimate_internal_slot 的参数 scheduler 实际只使用 scheduler.calendar 的三个方法（adjust_to_working_time、get_efficiency、add_working_hours）。传入整个 scheduler 对象暴露了 config、logger、_last_algo_stats 等不相关状态，违反最小知识原则。改为传 calendar 对象可使估算器完全独立于 GreedyScheduler 类，便于独立测试和未来解耦。",
      "recommendationMarkdown": "把参数从 scheduler: Any 改为 calendar: Any，调用方传入 scheduler.calendar。估算器内部直接调用 calendar.adjust_to_working_time / calendar.get_efficiency / calendar.add_working_hours。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 474,
          "lineEnd": 532
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 157,
          "lineEnd": 203
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
      "id": "G2",
      "severity": "medium",
      "category": "maintainability",
      "title": "occupy_resource 保留位置未在任务步骤中显式说明",
      "descriptionMarkdown": "plan 任务 1 步骤 4 对 `scheduler.py` 的修改指令是：\"1. 保留资源缺失判断、自动分配尝试、errors.append、increment_counter 这些调用方职责”，然后 \"4. 删除 _schedule_internal 内本地 _scaled_hours 与避让循环\"。\n\n但 `scheduler.py:545-546` 的 `occupy_resource(machine_timeline, machine_id, earliest, end)` 和 `occupy_resource(operator_timeline, operator_id, earliest, end)` 既不属于估算逻辑（不应入估算器），也不属于列举的四类调用方职责（资源缺失判断、自动分配、errors、increment_counter）。\n\n实施者可能在删除避让循环时连带删除 `occupy_resource` 调用，导致排产结果不再占用资源——后续工序会重叠上去。",
      "recommendationMarkdown": "在任务 1 步骤 4 对 scheduler.py 的修改指令中显式增加：\"保留 occupy_resource 调用，在获得 InternalSlotEstimate 的 start_time/end_time 后执行\"。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 545,
          "lineEnd": 546
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
      "id": "G3",
      "severity": "low",
      "category": "other",
      "title": "sgs.py 的 avg_proc_hours 计算段有死条件代码",
      "descriptionMarkdown": "sgs.py:92-93 对已是 float 的 `op.setup_hours`、`op.unit_hours` 尚在调用 `parse_required_float()`。plan 任务 2 步骤 3 第 3 点正确指出了这个问题，要求“直接使用已规范化的 `op.setup_hours`、`op.unit_hours`”。\n\n但 sgs.py:97 还有一处 `if strict_mode and isinstance(exc, Exception):` ——这个 `isinstance` 检查永远为 True（因为 `exc` 来自 `except Exception`），属于冗余死条件。任务 2 删除 `parse_required_float` 调用后，整个 try/except 块可简化为直接计算。",
      "recommendationMarkdown": "在任务 2 步骤 3 第 3 点旁补充：简化 avg_proc_hours 计算段时顺带删除 sgs.py:97 的死条件 isinstance 检查。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 88,
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
      "id": "G4",
      "severity": "low",
      "category": "other",
      "title": "scheduler.py 的工时计算块未明确列入删除范围",
      "descriptionMarkdown": "scheduler.py:476-488 对 `setup_hours`、`unit_hours` 使用 `getattr(op, \"setup_hours\", 0) or 0`。当 `schedule_input_builder.py` 已把这两个字段规范化为 `float` 后，`or 0` 会把合法的 `0.0`（零工时）转成整数 `0`——不影响结果（因后续 `float()` 会转回）但增加了无意义的类型抖动。plan 任务 1 步骤 3 第 1 点说“直接使用 op.setup_hours、op.unit_hours”——也就是不再 `or 0`。\n\n但任务 1 步骤 4 对 scheduler.py 的修改指令只说“删除 _scaled_hours 与避让循环”，没有明确提及同时删除 476-488 的 `setup_hours = getattr(...) or 0` + `total_hours_base` 计算块（因为这些已移入估算器）。实施者可能只删除避让循环却保留工时计算，导致重复计算。",
      "recommendationMarkdown": "在任务 1 步骤 4 第 4 点扩展为：\"删除 _schedule_internal 内的本地工时计算（setup_hours / unit_hours / qty / total_hours_base / isfinite 校验）、_scaled_hours 与避让循环，这些已全部转入估算器\"。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 476,
          "lineEnd": 488
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
      "id": "G5",
      "severity": "medium",
      "category": "performance",
      "title": "SGS 三重估算在大规模资源池下可能突破 30% 阈值",
      "descriptionMarkdown": "SGS 评分阶段对每个候选内部工序最多执行三次估算：\n1. `auto_assign(probe_only=True)` 内部：对每个 (machine, operator) 候选对调用 `estimate_internal_slot()`，候选对数 = M × O\n2. `_score_internal_candidate()` 本身：用选出的最优对再调用一次 `estimate_internal_slot()`\n3. `_schedule_internal() → auto_assign(probe_only=False)` 正式排产：再次对所有候选对估算\n\n总估算次数 = 候选数 × (M×O + 1 + M×O)。当 M=5、O=5、候选数=20 时，每轮 SGS 迭代约 1020 次估算。这比当前的近似评分（仅调用 `find_earliest_available_start`，复杂度低得多）要慢很多。\n\nplan 的 30% 阈值是合理的守门，但当前只用 `smoke_phase10_sgs_auto_assign.py` 做耗时对照——这个测试的候选数和资源池规模可能偏小，无法暴露大规模场景的耗时曲线。",
      "recommendationMarkdown": "在任务 2 步骤 6 的耗时对照中补充：若 `smoke_phase10` 的 `resource_pool` 候选对总数 < 50，应额外构造一个候选对 > 200 的场景做补充计时，确认三重估算在大规模资源池下仍在 30% 内。",
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
      "id": "G6",
      "severity": "low",
      "category": "other",
      "title": "避让上界数学证明成立",
      "descriptionMarkdown": "避让上界 `guard_limit = N_machine + N_operator + N_downtime + 1` 的正确性取决于 `earliest` 严格单调递增。经数学证明：\n\n1. `shift_to = max(m_shift, o_shift, d_shift)` —— 取所有重叠片段的最迟结束时刻\n2. `earliest = max(earliest, shift_to)` —— `earliest` 严格递增\n3. `adjust_to_working_time(earliest)` —— 只会前移或不动，不会后退\n4. 每次推迟至少越过一个片段的 `end` 时刻（因为 `shift_to >= segment.end`）\n5. 不同片段的 `end` 互不相同（即使相同，合并处理不会增加迭代次数）\n\n因此最多迭代 N_machine + N_operator + N_downtime + 1 次。但注意：效率变化可能导致 `end` 扩大，使新 `(earliest, end)` 与之前未重叠的片段产生重叠。但每个新重叠片段只触发一次推迟，不会重复计算。\n\n上界证明成立 ✅",
      "recommendationMarkdown": null,
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 510,
          "lineEnd": 533
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
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
    "bodyHash": "sha256:17035a9ced2ae04c7a8c14db58c24a369a94269b539679520a9b0053a91616c2",
    "generatedAt": "2026-04-07T07:07:11.247Z",
    "locale": "zh-CN"
  }
}
```
