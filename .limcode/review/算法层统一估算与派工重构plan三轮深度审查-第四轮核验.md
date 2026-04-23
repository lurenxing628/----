# 算法层统一估算与派工重构plan三轮深度审查_第四轮核验
- 日期: 2026-04-07
- 概述: 对 2026-04-07 算法层统一估算与派工重构 plan 进行三轮深度审查，逐条核验引用链、实现可行性、逻辑严谨性与潜在遗漏
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# 算法层统一估算与派工重构 plan 三轮深度审查（第四轮核验）

**审查日期**：2026-04-08
**审查对象**：`.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`
**审查范围**：plan 中所有引用链、代码事实断言、任务步骤可行性、边界约束完备性、潜在 BUG 与遗漏

## 审查方法

- 第一轮：核验 plan 中所有代码行号引用与事实断言
- 第二轮：追踪每个任务的实现路径，验证逻辑严谨性与边界完备性
- 第三轮：交叉审查任务间依赖、遗漏风险与整体架构优雅性

## 评审摘要

- 当前状态: 已完成
- 已审模块: 代码行号与事实断言核验, 任务1-统一内部工序估算器, 任务2-拆分dispatch_sgs评分, 任务3-时间线有序化与运行期状态收口, 任务4-算法层日期来源统一, 任务5-优化器微优化与全链回归, 任务间依赖与顺序, 完成判定与验收口径, 架构优雅性与简洁性, 遗漏风险
- 当前进度: 已记录 3 个里程碑；最新：M3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 9
- 问题严重级别分布: 高 1 / 中 3 / 低 5
- 最新结论: ## 三轮深度审查总结 经过三轮深入审查——第一轮逐条核验 plan 中 12 项修订前提、6 组引用链共 15+ 处代码行号引用；第二轮追踪 5 个任务的实现路径、算法正确性与边界完备性；第三轮交叉审查任务间依赖、完成判定口径与整体架构优雅性——对该 plan 做出以下判定： ### 总体评价 **这是一份质量极高的重构 plan。** 它在以下方面做得非常好： 1. **代码事实基础扎实**：12 项修订前提全部核验通过，行号引用仅有 1 处微偏（F1，不影响实施）。 2. **架构设计简洁优雅**：`internal_slot.py` 只做估算、`runtime_state.py` 只做状态更新、`validate_internal_hours()` 只做工时预检——职责分离清晰，不引入新的平行模式。 3. **约束体系严密**：每个任务都有明确的实施约束、暂停门槛和回归测试集合。"不做"清单完整且诚实。 4. **兼容性保护到位**：明确保留 `GreedyScheduler.schedule()` 的 raw 输入兼容边界，不静默收窄 direct-call 场景。 5. **测试先行**：每个任务先写失败用例，再实现，再验证——确保行为变更可观测。 ### 必须在实施前修正的问题（1 项高严重级别） - **F3**：`schedule_optimizer.py` 的 `_parse_date()` 硬编码 `field="due_date"`，被同时用于 `due_date` 和 `ready_date` 解析。plan 暂停条件已覆盖此 BUG，但实施步骤本身应显式要求 `ready_date` 使用 `field="ready_date"` 的包装，不能仅依赖暂停条件来"事后发现"。 ### 建议在实施前澄清的问题（3 项中严重级别） - **F4**：自动分配场景中评分估算存在已知重复（M×O 对被估算两次）。plan "明确不做"第 11 项已承认，但应在实施说明中更明确标注。 - **F5**：`ready_date` 下界调整的异常上浮可能导致日历服务异常时排产中断。建议区分"合法日期入参后日历服务内部异常"与"坏入参"两种情况。 - **F8**：`created_at` 的严格校验判断逻辑应基于 `keys`（当前轮次实际使用的策略列表）而非 `valid_strategies`（默认包含全部策略），避免在非 FIFO 场景下因坏 `created_at` 意外阻断排产。 ### 低风险观察（5 项低严重级别） - **F1**：引用行号微偏（278-340 → 278-341），不影响实施。 - **F2**：`_parse_date` 非严格模式双重解析，plan 任务 4 已计划修复。 - **F6**：大量 seed 碎片场景下上界较大，建议在基准测试中覆盖。 - **F7**：局部搜索 shake 后 `seen_hashes` 重置语义，plan 文字描述正确。 - **F9**：移除广域吞异常后 seed 预热可能暴露新异常，plan 回归列表已覆盖。 ### 最终判定 该 plan 能够达成其声明的目标。整体架构设计优雅简洁，没有过度兜底或静默回退，逻辑严谨。在修正 F3（将 `ready_date` 的 `field` 参数差异化写入实施步骤）和澄清 F8（`created_at` 严格校验判断逻辑）之后，可以开始实施。
- 下一步建议: 1. 修正 F3：在任务 4 步骤 4 正文中明确要求 ready_date 使用 field="ready_date" 而非复用 field="due_date" 的包装。2. 澄清 F8：将 created_at 严格校验的判断条件从 valid_strategies 改为 keys。3. 补充 F4 说明：在"明确不做"列表中标注自动分配场景的估算重复是已知性能取舍。完成以上修正后即可开始按任务顺序实施。
- 总体结论: 有条件通过

## 评审发现

### sgs.py 评分族范围少写一行

- ID: F1-LINE-DRIFT
- 严重级别: 低
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  plan 引用 sgs.py:278-340 为近似评分族范围，但 change_pen 赋值实际在第 341 行才结束，plan 遗漏了边界行。对实施无实际影响。
- 建议:

  将引用范围调整为 278-341。

### schedule_optimizer.py _parse_date 非严格模式双重解析

- ID: F2-PARSE-DATE-DOUBLE
- 严重级别: 低
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  schedule_optimizer.py:337-341 非严格模式下先调用 parse_optional_date() 再 except 回退为 None，本质是多余的双重解析。plan 任务 4 已正确识别此问题并计划修复。
- 建议:

  确认任务 4 实施时一并清理。

### schedule_optimizer ready_date 严格模式报错字段名错误

- ID: F3-READY-DATE-FIELD-BUG
- 严重级别: 高
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  schedule_optimizer.py:335-341 的 `_parse_date()` 硬编码 `field="due_date"`，但被同时用于解析 `due_date`（行 365）和 `ready_date`（行 367）。这意味着在严格模式下，坏 `ready_date` 会抛出 `ValidationError(field="due_date")`，错误文案指向了错误字段。

  plan 任务 4 暂停条件已覆盖此问题（"schedule_optimizer.py 解析坏 ready_date 仍以 due_date 名义报错"），但 plan 步骤本身没有在"要做什么"层面明确说"分别构造 `_parse_due_date()` 和 `_parse_ready_date()` 两个带正确字段名的包装函数"。实施者可能仅清理 `_parse_date()` 为统一导入后仍漏掉 `field` 参数的差异化。
- 建议:

  任务 4 步骤 4 应在正文中明确要求 `ready_date` 调用 `parse_optional_date(value, field="ready_date")` 而非复用 `field="due_date"` 的包装。这不仅是暂停条件，也应是显式实施步骤。
- 证据:
  - `core/services/scheduler/schedule_optimizer.py:335-341#_parse_date`
  - `core/services/scheduler/schedule_optimizer.py:365-367`
  - `core/services/scheduler/schedule_optimizer.py`

### sgs 评分升级后自动分配场景估算重复

- ID: F4-DOUBLE-ESTIMATE
- 严重级别: 中
- 分类: 性能
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  任务 2 将 sgs 评分中的顺序链式近似替换为三路时间线同时避让估算。这意味着：

  1. **每个候选对都执行完整避让循环**：当前的 `find_earliest_available_start()` 是 O(n) 线性扫描，而 `estimate_internal_slot()` 是一个 while 循环，每次迭代要检查三路时间线的重叠。
  2. **自动分配场景存在重复计算**：`probe_only=True` 的自动分配已经在 `auto_assign_internal_resources()` 中做过完整三路避让；之后 `_score_internal_candidate()` 又拿到返回的 `(mid, oid)` 再做一次 `estimate_internal_slot()`，相当于同一对设备人员被估算两次。plan 明确不做第 11 项承认了此重复。
  3. **大资源池加倍效应**：设 M 台设备、O 个操作员，当前自动分配评估 M×O 对各做一次避让循环，任务 2 后又额外做一次——总估算次数从 M×O 变为 2×M×O。

  plan 已设置 30% 退化阈值与基准测试，但应在实施说明中明确标注此已知重复源，避免基准测试通过后被遗忘。
- 建议:

  在 plan 的"明确不做"列表中补充说明：由于自动分配返回值未扩展，sgs 评分阶段对自动分配候选存在一次估算重复，这是本轮已知的性能取舍。

### ready_date 下界调整异常上浮可能导致非预期排产中断

- ID: F5-READY-DATE-EXCEPTION-RISK
- 严重级别: 中
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  scheduler.py:232-236 的 `ready_date` 下界调整：
  ```python
  try:
      dt_ready = self.calendar.adjust_to_working_time(dt0, priority=p)
  except Exception:
      dt_ready = dt0
  ```
  plan 任务 4 步骤 4.5 要求"异常直接上浮"。但 `adjust_to_working_time()` 抛异常的可能原因包括：
  - 日历数据缺失或损坏
  - `priority` 值不合法
  - 内部日期算术溢出

  如果直接上浮，一个坏优先级值就会导致整个排产失败，而当前行为是降级使用午夜零点。plan 没有区分"日历服务程序错误"与"日历数据配置错误"两种失败类型。

  此外，`schedule_optimizer.py` 中构造 `BatchForSort` 时也用 `_parse_date()` 处理 `ready_date`，但那里的 `ready_date` 只用于排序，不直接作为时间线下界。这两处的行为变更需要分别验证。
- 建议:

  建议在实施说明中明确：仅当 `adjust_to_working_time()` 收到合法 `date` 类型入参时才允许上浮异常；若调用方传入的已经是合法日期，则 `adjust_to_working_time()` 的内部异常确实应被视为不可忽略的程序错误。但需要在回归测试中覆盖"日历服务暂时不可用"的场景，确认上浮后的失败消息可读。
- 证据:
  - `core/algorithms/greedy/scheduler.py:230-237`
  - `core/algorithms/greedy/scheduler.py`

### 统一估算器在大量 seed 碎片场景下的上界可能过大

- ID: F6-UPPER-BOUND-LARGE-SEED
- 严重级别: 低
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  plan 任务 1 要求避让上界为 `len(machine_timeline[mid]) + len(operator_timeline[oid]) + len(downtime_segments) + 1`。但在 `auto_assign_internal_resources()` 中，每个候选对 `(mid, oid)` 拥有不同的时间线长度。如果 `estimate_internal_slot()` 在入口处一次性计算上界，那么在同一次 `auto_assign` 调用中，不同候选对的上界不同是正确的。

  但 `_schedule_internal()` 在调用 `estimate_internal_slot()` 之前已经确定了唯一的 `(machine_id, operator_id)`，所以这里只有一次计算。

  **潜在 BUG**：如果 `occupy_resource()` 在 seed 预热阶段向时间线添加了大量碎片段（例如来自上一轮冻结窗口的上百个 seed 结果），而估算器的上界基于时间线当前大小计算，则上界值会很大。在极端场景下（1000 个 seed + 大量停机段），while 循环可能执行上千次迭代。这虽然不会死循环（因为有上界），但可能导致单次估算耗时较长。plan 的基准测试应覆盖此场景。
- 建议:

  在 `benchmark_sgs_large_resource_pool.py` 中补充"大量 seed 结果导致时间线碎片化"的场景，验证估算器在此情况下的耗时。
- 证据:
  - `core/algorithms/greedy/scheduler.py:510-543`
  - `core/algorithms/greedy/scheduler.py`

### 局部搜索 shake 后 seen_hashes 重置的语义需明确

- ID: F7-SHAKE-RESET-CLARITY
- 严重级别: 低
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  plan 任务 5 步骤 4 要求 `_run_local_search()` 在 shake 后"允许做轻量重置（清空后立即写回当前 cur_order，并补写 tuple(best.get('order', []))）"。但 shake 本身就是从 `best['order']` 出发做随机扰动（schedule_optimizer.py:247）。shake 后 `cur_order` 已经是 `best['order']` 的变体。如果清空 `seen_hashes` 后立即写回 `cur_order` 和 `best['order']`，实际上只预热了两个点，接下来的邻域搜索可能会重新尝试 shake 前已经尝试过且失败的邻域。

  这不是 BUG（plan 明确允许"轻量重置"），但可能降低搜索效率。更优的做法是保留 `best['order']` 和 `cur_order` 在 `seen_hashes` 中，其余全部清空。plan 当前描述恰好就是这个做法。但实施时需注意 shake 后 `cur_order` 与 shake 前的 `cur_order` 不同，不需要保留旧的 `cur_order`。
- 建议:

  实施时确认：shake 后的 seen_hashes 只需保留 shake 后的 cur_order 与 best['order']，不需要保留 shake 前的旧 cur_order。plan 文字表述已正确。

### created_at 严格校验在默认配置下过于激进

- ID: F8-CREATED-AT-OVERSTRICT
- 严重级别: 中
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  plan 任务 4 要求在 `optimize_schedule()` 中检查候选策略集合是否包含 FIFO，只在包含时才对 `created_at` 做严格校验。但 `valid_strategies` 默认值为 `("priority_first", "due_date_first", "weighted", "fifo")`（schedule_optimizer.py:392），即默认总是包含 `fifo`。

  这意味着：只要用户没有显式配置将 `fifo` 从候选集中移除，严格模式下坏 `created_at` 就会导致排产失败，即使用户实际选择的是 `priority_first` 策略。这与 plan 任务 4 的意图（"仅在 FIFO 相关排序路径真正消费该字段时才允许 strict 硬失败"）矛盾。

  plan 的意图是“当前候选策略集合会实际构造 FIFO 排序”，但“默认包含 fifo”与“实际构造 fifo 排序”是两码事。需要明确：是按"候选集合是否包含 fifo"还是按"当前轮次实际构造了 fifo 排序器"来决定是否对 created_at 做 strict 校验。
- 建议:

  建议采用更保守的判断逻辑：只有当当前轮次实际会用 fifo 策略构造排序器时，才对 created_at 做 strict 校验。具体做法：在 `batch_for_sort` 构造循环之前，检查 `keys`（而非 `valid_strategies`）是否包含 `"fifo"`。在 `algo_mode == "improve"` 模式下 `keys` 包含所有 `valid_strategies`，但在非 improve 模式下 `keys = [current_key]`，只包含用户实际选择的策略。
- 证据:
  - `core/services/scheduler/schedule_optimizer.py:392`
  - `core/services/scheduler/schedule_optimizer.py:359-370`
  - `core/services/scheduler/schedule_optimizer.py`

### 移除广域吞异常后 seed 预热可能暴露新异常

- ID: F9-EXPOSED-EXCEPTION-RISK
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  plan 的完成判定第 9 条写道："在本轮触达的文件与链路内，未引入新的静默回退、广域吞异常、平行估算路径或新的算法模式"。但 plan 任务 3 是移除现有的广域吞异常（batch_order.py:102、sgs.py:470、scheduler.py:296），这意味着实施后这些位置可能暴露之前被静默吞掉的异常。

  scheduler.py:290-297 的 seed 预热忙时统计也有一个 `except Exception: pass`。如果任务 3 把这个也移除（plan 明确要求"seed 预热阶段三处运行期状态更新收口到 runtime_state.py"，且"共享函数内部没有广域吞异常"），那么 seed 结果中的 `end_time - start_time` 如果出现类型错误（比如 `start_time` 为 `None` 但通过了前置检查），就会直接抛异常而不是被静默跳过。这是正确的行为，但需要确保回归测试覆盖此场景。
- 建议:

  任务 3 的回归列表中应明确包含 `regression_seed_results_freeze_missing_resource.py`、`regression_seed_results_dedup.py`，并在实施时特别关注 seed 预热中 `h = (sr.end_time - sr.start_time).total_seconds() / 3600.0` 这行是否会因异常类型不再被吞掉而导致新的失败。plan 已在回归列表中列出了这些测试，符合预期。

## 评审里程碑

### M1 · 第一轮：代码行号引用与事实断言核验

- 状态: 已完成
- 记录时间: 2026-04-07T14:28:44.601Z
- 已审模块: 代码行号与事实断言核验
- 摘要:

  逐条核验 plan 修订前提与引用链总览中的代码行号与事实断言，检验与当前代码的一致性。

  ### 核验通过的断言

  1. **修订前提 1**：服务主链 `_run_schedule_impl() → collect_schedule_run_input() → orchestrate_schedule_run() → optimize_schedule() → GreedyScheduler.schedule()` 已核实，链路正确。
  2. **修订前提 2**：`scheduler.py:469-543` 与 `auto_assign.py:156-223` 确属同一估算族（三路时间线同时检查、循环推进直到稳定）。`sgs.py:278-340` 确实是顺序链式近似评分（连续三次 `find_earliest_available_start`）。
  3. **修订前提 3**：`schedule_input_builder.py:128-215` 已核实确实规范化 `setup_hours`、`unit_hours`、`ext_days`、`ext_group_total_days`。
  4. **修订前提 4**：`core/algorithms/__init__.py` 确实仍导出 `GreedyScheduler`。
  5. **修订前提 5**：`sgs.py:18-24` 确实对 `due_date` 使用 `parse_optional_date()` 做严格包装。
  6. **修订前提 6**：`strict_parse.py` 确实只有 `parse_required_date`/`parse_optional_date`，无日期时间版本。`schedule_optimizer.py:343-357` 的 `_parse_datetime()` 确实是本地非严格实现。
  7. **修订前提 7**：`scheduler.py:289-304` 确实在 seed 预热阶段维护 `machine_busy_hours`、`operator_busy_hours`、`last_end_by_machine`、`last_op_type_by_machine`。
  8. **修订前提 8**：`scheduler.py:513` 和 `auto_assign.py:185` 确实都写死 `guard < 200`。
  9. **修订前提 9**：`scheduler.py:494` 确实有 `or 1.0`；`sgs.py:323` 确实有 `or 1.0`；`auto_assign.py:165-169` 确实在内层用 `raw_eff is not None` 但外层有 `except Exception: eff = 1.0`。
  10. **修订前提 10**：已确认 `schedule_summary.py` 与 `report/calculations.py` 不在本轮范围。
  11. **修订前提 11**：`scheduler.py:138-146` 确实同时构造 `due_date`、`ready_date`、`created_at`。`sort_strategies.py:122` 确认 `created_at` 只在 FIFO 排序键中消费。
  12. **修订前提 12**：`schedule_params.py:105` 确认 `except Exception: pass` 存在，且确实不在本轮范围。

  ### 核验到的行号偏移/事实微偏

  1. **引用链 3.3**："`scheduler.py:215-245` 维护运行期变量"——实际变量声明范围是 215-245，但 `seed_count` 在第 246 行，紧接其后。这只是小偏移，不影响语义。
  2. **引用链 4.1**：plan 写 `batch_order.py:10-122`——实际为 10-122（核实一致），但注意 `batch_order.py` 总行数仅 124，文件更短小。
  3. **引用链 4.2**：plan 写 `sgs.py:27-506`——实际是 27-506（核实一致），总行数 508。
  4. **引用链 5.2**：plan 写 `sgs.py:278-340` 为近似评分族范围——核实一致，但评分与估算逻辑实际到第 341 行才结束（`change_pen = 0`），plan 写 340 少了一行。

  ### 重要事实补充

  - `scheduler.py` 从 `schedule_params.py` 转导出 `parse_date` 和 `parse_datetime`（第 30-31 行），而 `schedule_params.py` 从 `date_parsers.py` 导入。plan 任务 4 明确要切断这个转导出路径。
  - `sgs.py` 第 425 行 `best_pair = candidates[0]` 确实是死代码路径，plan 任务 2 步骤 3 第 5 点已明确要删除。
  - `batch_order.py:102` 的 `except Exception: pass` 和 `sgs.py:470-472` 的 `except Exception:` 都是广域吞异常，plan 任务 3 已计划收口。
  - `schedule_optimizer.py:337-341` 的 `_parse_date()` 对非严格模式也走了一次 `parse_optional_date()` 然后 `except` 回退，本质是双重解析；plan 任务 4 正确识别了这个问题。
- 结论:

  逐条核验 plan 修订前提与引用链总览中的代码行号与事实断言，检验与当前代码的一致性。 ### 核验通过的断言 1. **修订前提 1**：服务主链 `_run_schedule_impl() → collect_schedule_run_input() → orchestrate_schedule_run() → optimize_schedule() → GreedyScheduler.schedule()` 已核实，链路正确。 2. **修订前提 2**：`scheduler.py:469-543` 与 `auto_assign.py:156-223` 确属同一估算族（三路时间线同时检查、循环推进直到稳定）。`sgs.py:278-340` 确实是顺序链式近似评分（连续三次 `find_earliest_available_start`）。 3. **修订前提 3**：`schedule_input_builder.py:128-215` 已核实确实规范化 `setup_hours`、`unit_hours`、`ext_days`、`ext_group_total_days`。 4. **修订前提 4**：`core/algorithms/__init__.py` 确实仍导出 `GreedyScheduler`。 5. **修订前提 5**：`sgs.py:18-24` 确实对 `due_date` 使用 `parse_optional_date()` 做严格包装。 6. **修订前提 6**：`strict_parse.py` 确实只有 `parse_required_date`/`parse_optional_date`，无日期时间版本。`schedule_optimizer.py:343-357` 的 `_parse_datetime()` 确实是本地非严格实现。 7. **修订前提 7**：`scheduler.py:289-304` 确实在 seed 预热阶段维护 `machine_busy_hours`、`operator_busy_hours`、`last_end_by_machine`、`last_op_type_by_machine`。 8. **修订前提 8**：`scheduler.py:513` 和 `auto_assign.py:185` 确实都写死 `guard < 200`。 9. **修订前提 9**：`scheduler.py:494` 确实有 `or 1.0`；`sgs.py:323` 确实有 `or 1.0`；`auto_assign.py:165-169` 确实在内层用 `raw_eff is not None` 但外层有 `except Exception: eff = 1.0`。 10. **修订前提 10**：已确认 `schedule_summary.py` 与 `report/calculations.py` 不在本轮范围。 11. **修订前提 11**：`scheduler.py:138-146` 确实同时构造 `due_date`、`ready_date`、`created_at`。`sort_strategies.py:122` 确认 `created_at` 只在 FIFO 排序键中消费。 12. **修订前提 12**：`schedule_params.py:105` 确认 `except Exception: pass` 存在，且确实不在本轮范围。 ### 核验到的行号偏移/事实微偏 1. **引用链 3.3**："`scheduler.py:215-245` 维护运行期变量"——实际变量声明范围是 215-245，但 `seed_count` 在第 246 行，紧接其后。这只是小偏移，不影响语义。 2. **引用链 4.1**：plan 写 `batch_order.py:10-122`——实际为 10-122（核实一致），但注意 `batch_order.py` 总行数仅 124，文件更短小。 3. **引用链 4.2**：plan 写 `sgs.py:27-506`——实际是 27-506（核实一致），总行数 508。 4. **引用链 5.2**：plan 写 `sgs.py:278-340` 为近似评分族范围——核实一致，但评分与估算逻辑实际到第 341 行才结束（`change_pen = 0`），plan 写 340 少了一行。 ### 重要事实补充 - `scheduler.py` 从 `schedule_params.py` 转导出 `parse_date` 和 `parse_datetime`（第 30-31 行），而 `schedule_params.py` 从 `date_parsers.py` 导入。plan 任务 4 明确要切断这个转导出路径。 - `sgs.py` 第 425 行 `best_pair = candidates[0]` 确实是死代码路径，plan 任务 2 步骤 3 第 5 点已明确要删除。 - `batch_order.py:102` 的 `except Exception: pass` 和 `sgs.py:470-472` 的 `except Exception:` 都是广域吞异常，plan 任务 3 已计划收口。 - `schedule_optimizer.py:337-341` 的 `_parse_date()` 对非严格模式也走了一次 `parse_optional_date()` 然后 `except` 回退，本质是双重解析；plan 任务 4 正确识别了这个问题。
- 证据:
  - `core/algorithms/greedy/scheduler.py:469-543#_schedule_internal`
  - `core/algorithms/greedy/auto_assign.py:156-223#auto_assign_internal_resources`
  - `core/algorithms/greedy/dispatch/sgs.py:278-341#dispatch_sgs`
  - `core/algorithms/greedy/scheduler.py:215-246#schedule`
  - `core/algorithms/greedy/scheduler.py:289-304#seed_runtime_state`
  - `core/algorithms/greedy/downtime.py:20-28#occupy_resource`
  - `core/algorithms/greedy/date_parsers.py:7-41`
  - `core/algorithms/evaluation.py:55-58#_due_exclusive`
  - `core/algorithms/dispatch_rules.py:25-28#_due_exclusive`
  - `core/algorithms/ortools_bottleneck.py:39-42#_due_exclusive`
  - `core/services/common/strict_parse.py:85-102`
  - `core/services/scheduler/schedule_optimizer.py:335-357#_parse_datetime`
  - `core/algorithms/greedy/schedule_params.py:103-106`
- 问题:
  - [低] 文档: sgs.py 评分族范围少写一行
  - [低] JavaScript: schedule_optimizer.py _parse_date 非严格模式双重解析

### M2 · 第二轮：逐任务实现可行性、逻辑严谨性与潜在 BUG 审查

- 状态: 已完成
- 记录时间: 2026-04-07T14:30:27.787Z
- 已审模块: 任务1-统一内部工序估算器, 任务2-拆分dispatch_sgs评分, 任务3-时间线有序化与运行期状态收口, 任务4-算法层日期来源统一, 任务5-优化器微优化与全链回归
- 摘要:

  ### 任务 1：统一内部工序估算器

  **可行性**：高。`_schedule_internal()` 和 `auto_assign_internal_resources()` 的核心估算逻辑几乎完全相同（三路时间线同时检查 + 循环避让），收口到一个函数是自然的重构。

  **逻辑严谨性验证**：
  - **避让上界公式**：`N_machine + N_operator + N_downtime + 1` 是正确的。每次避让至少跳过一个段的终点，而段总数有限。越过上界应视为实现错误而非业务失败，plan 的设计正确。
  - **`validate_internal_hours()` 的双重安全要求**：对 raw direct-call 输入做 `float()` 转换 + 有限性检查，对服务主链已规范化输入直接通过——这个设计可行，因为 `float(already_float)` 是无损操作。
  - **`abort_after` 早停语义**：plan 要求在 `adjust_to_working_time()` 之后和每次避让后都检查。对齐 `auto_assign.py:159` 和 `200` 的当前早停点。正确。
  - **零时长工序场景**：plan 步骤 1.6 要求 `start_time == end_time` 且不报错，但需注意零时长工序仍应占用资源（`occupy_resource` 调用）。当前 `add_working_hours(earliest, 0)` 应返回 `earliest`，所以 `start_time == end_time == earliest`。`occupy_resource(mid, earliest, earliest)` 会写入一个零长度区间，被 `find_overlap_shift_end()` 的 `e <= s` 检查自动跳过。设计正确。

  **遗漏/风险**：
  - `auto_assign` 内 `_scaled_hours()` 闭包捕获 `oid` 问题：当前代码通过默认参数 `_oid: str = oid` 解决。迁移到 `estimate_internal_slot()` 后此问题消失，因为 `oid` 作为显式参数传入。正确。
  - `efficiency_fallback_used` 在 `probe_only` 模式下不应计入全局计数器：plan 步骤 4.3 说"`probe_only=True` 时所有 `increment_counter(...)` 调用继续走空操作"，但 `estimate_internal_slot()` 内部设置 `efficiency_fallback_used=True` 是返回值属性，不是计数器调用。调用方需要根据 `probe_only` 决定是否调用 `increment_counter`。plan 步骤 4.4 在 `_schedule_internal()` 中处理了这个分支。可行。

  ### 任务 2：拆分 `dispatch_sgs()` 评分

  **可行性**：高。当前函数 ~480 行，拆分出 5 个子函数后主函数将大幅缩减。

  **关键逻辑审查**：
  - **`avg_proc_hours` 初始化段**：plan 要求复用 `validate_internal_hours()` 而不是保留第三套公式。但 `validate_internal_hours()` 抛 `ValueError` 时只意味着该样本不可用，不应让初始化段整体崩溃。plan 步骤 3.3 明确了这一点。
  - **评分阶段工时坏值与资源缺失的分离**：plan 要求 `validate_internal_hours()` 先于 `probe_only=True` 自动分配。这意味着坏 `setup_hours` 会在资源补全之前被检测到，不会与"缺资源"混淆。逻辑正确。
  - **`candidates[0]` 死代码删除**：第 424-425 行确认是死代码——`best_pair` 在循环中要么被赋值（`best_key` 被更新），要么至少有异常兜底 key。只要候选列表非空且循环执行了，`best_pair` 不可能为 `None`。plan 删除正确。

  **性能风险**：
  - 评分升级后，每个已有资源的候选对都从顺序链式估算变成三路避让估算。在非自动分配场景下（资源已确定），每个候选只做一次估算，影响有限。但在自动分配场景下，估算做了两次（一次在 `auto_assign` 内部找最优对，一次在 `_score_internal_candidate` 中取评分）。plan 的"明确不做"第 11 项承认了此重复。

  ### 任务 3：时间线有序化

  **可行性**：高。`occupy_resource()` 改为 `bisect.insort` 只需 2-3 行改动。

  **关键验证**：
  - **Python 3.8 兼容性**：`bisect.insort` 在 Python 3.8 只支持 `(a, x)` 两参数形式，不支持 `key=`。使用 `(start, end)` 元组自然顺序是兼容的。plan 正确。
  - **`find_overlap_shift_end()` 早停正确性**：有序时间线上，`segment.start >= end` 之后的所有段也满足 `segment.start >= end`（因为有序），所以可以安全跳出。正确。
  - **seed 预热与派工成功的语义差异**：
    - seed: `op_type_name` 为空时不推进 `last_end_by_machine` 和 `last_op_type_by_machine`
    - 派工: `last_end_by_machine` 条件更新（更晚才覆盖），`last_op_type_by_machine` 非空时直接更新
    - plan 通过 `conditional_op_type=True/False` 区分两种模式。正确。
  - **`batch_order.py:90-106` 的广域 `try/except`**：当前忙时统计和工种更新包在一个 `try/except` 里，任何一步失败都静默吞掉。plan 要求移除此 `except`，让调用方看到异常。这可能暴露当前被静默吞掉的 BUG。需要回归测试覆盖。

  ### 任务 4：算法层日期来源统一

  **可行性**：高。三份 `_due_exclusive()` 副本合并为一份、`_parse_date` / `_parse_datetime` 副本合并为统一导入，这是经典的消除重复重构。

  **关键问题发现**：
  - **`schedule_optimizer.py:367` 的 `ready_date` 通过 `_parse_date()` 解析，`_parse_date()` 硬编码 `field="due_date"`**：严格模式下坏 `ready_date` 会抛出文案为"due_date格式不合法"的错误。这是一个真实 BUG。plan 暂停条件已覆盖，但实施步骤应更明确。
  - **`scheduler.py:145` 的 `ready_date` 始终用非严格 `_parse_date()` 解析**：即使 `strict_mode=True`，`ready_date` 也不会抛错。这与 `due_date`（第 138 行严格模式下走 `parse_optional_date`）不一致。plan 任务 4 步骤 4.2 要求修复此不一致。
  - **`created_at` 的策略相关启用**：plan 要求在 `optimize_schedule()` 中检查候选策略集合是否包含 FIFO。由于 `batch_for_sort` 构造（行 359-370）发生在策略循环之前，`created_at` 解析也在策略循环之前。这意味着只要 `valid_strategies` 包含 `fifo`（默认包含），严格模式就会对 `created_at` 做 strict 校验。这在语义上可能过于激进——用户可能只想用 `priority_first` 策略，但因为默认候选集包含 `fifo` 而被坏 `created_at` 阻断。
  - **`ready_date` 下界的 `adjust_to_working_time()` 异常上浮**：当前代码静默回退到 `dt0`，plan 要求直接上浮。需要评估日历服务异常的常见原因，确保不会因为日历配置问题导致批量排产失败。

  ### 任务 5：优化器微优化

  **可行性**：高。`build_order()` 缓存是简单的字典记忆化，邻域去重是简单的集合查找。

  **逻辑验证**：
  - **`build_order()` 缓存键**：`(strategy.value, tuple(sorted(params0.items())))` 对于 `weighted` 策略，`params0` 包含两个 `float` 键值。`sorted()` 保证顺序一致性。对于非 `weighted` 策略，`params0 = {}` 或 `dict(strategy_params or {})`，哈希也稳定。正确。
  - **`seen_hashes` 预热**：初始化时写入 `tuple(cur_order)` 可以避免第一次生成与当前顺序相同的邻域。shake 后清空并写回 `cur_order` 和 `best['order']`。正确。
  - **重复跳过推进停滞计数**：plan 要求重复邻域"不计入 `attempts`，但必须继续推进用于触发 `restart_after` 的停滞计数"。当前代码 `no_improve += 1` 在非改进时触发（行 242）。如果重复邻域被跳过，需要额外在跳过分支中执行 `no_improve += 1`。plan 步骤 4.2 描述正确。
- 结论:

  ### 任务 1：统一内部工序估算器 **可行性**：高。`_schedule_internal()` 和 `auto_assign_internal_resources()` 的核心估算逻辑几乎完全相同（三路时间线同时检查 + 循环避让），收口到一个函数是自然的重构。 **逻辑严谨性验证**： - **避让上界公式**：`N_machine + N_operator + N_downtime + 1` 是正确的。每次避让至少跳过一个段的终点，而段总数有限。越过上界应视为实现错误而非业务失败，plan 的设计正确。 - **`validate_internal_hours()` 的双重安全要求**：对 raw direct-call 输入做 `float()` 转换 + 有限性检查，对服务主链已规范化输入直接通过——这个设计可行，因为 `float(already_float)` 是无损操作。 - **`abort_after` 早停语义**：plan 要求在 `adjust_to_working_time()` 之后和每次避让后都检查。对齐 `auto_assign.py:159` 和 `200` 的当前早停点。正确。 - **零时长工序场景**：plan 步骤 1.6 要求 `start_time == end_time` 且不报错，但需注意零时长工序仍应占用资源（`occupy_resource` 调用）。当前 `add_working_hours(earliest, 0)` 应返回 `earliest`，所以 `start_time == end_time == earliest`。`occupy_resource(mid, earliest, earliest)` 会写入一个零长度区间，被 `find_overlap_shift_end()` 的 `e <= s` 检查自动跳过。设计正确。 **遗漏/风险**： - `auto_assign` 内 `_scaled_hours()` 闭包捕获 `oid` 问题：当前代码通过默认参数 `_oid: str = oid` 解决。迁移到 `estimate_internal_slot()` 后此问题消失，因为 `oid` 作为显式参数传入。正确。 - `efficiency_fallback_used` 在 `probe_only` 模式下不应计入全局计数器：plan 步骤 4.3 说"`probe_only=True` 时所有 `increment_counter(...)` 调用继续走空操作"，但 `estimate_internal_slot()` 内部设置 `efficiency_fallback_used=True` 是返回值属性，不是计数器调用。调用方需要根据 `probe_only` 决定是否调用 `increment_counter`。plan 步骤 4.4 在 `_schedule_internal()` 中处理了这个分支。可行。 ### 任务 2：拆分 `dispatch_sgs()` 评分 **可行性**：高。当前函数 ~480 行，拆分出 5 个子函数后主函数将大幅缩减。 **关键逻辑审查**： - **`avg_proc_hours` 初始化段**：plan 要求复用 `validate_internal_hours()` 而不是保留第三套公式。但 `validate_internal_hours()` 抛 `ValueError` 时只意味着该样本不可用，不应让初始化段整体崩溃。plan 步骤 3.3 明确了这一点。 - **评分阶段工时坏值与资源缺失的分离**：plan 要求 `validate_internal_hours()` 先于 `probe_only=True` 自动分配。这意味着坏 `setup_hours` 会在资源补全之前被检测到，不会与"缺资源"混淆。逻辑正确。 - **`candidates[0]` 死代码删除**：第 424-425 行确认是死代码——`best_pair` 在循环中要么被赋值（`best_key` 被更新），要么至少有异常兜底 key。只要候选列表非空且循环执行了，`best_pair` 不可能为 `None`。plan 删除正确。 **性能风险**： - 评分升级后，每个已有资源的候选对都从顺序链式估算变成三路避让估算。在非自动分配场景下（资源已确定），每个候选只做一次估算，影响有限。但在自动分配场景下，估算做了两次（一次在 `auto_assign` 内部找最优对，一次在 `_score_internal_candidate` 中取评分）。plan 的"明确不做"第 11 项承认了此重复。 ### 任务 3：时间线有序化 **可行性**：高。`occupy_resource()` 改为 `bisect.insort` 只需 2-3 行改动。 **关键验证**： - **Python 3.8 兼容性**：`bisect.insort` 在 Python 3.8 只支持 `(a, x)` 两参数形式，不支持 `key=`。使用 `(start, end)` 元组自然顺序是兼容的。plan 正确。 - **`find_overlap_shift_end()` 早停正确性**：有序时间线上，`segment.start >= end` 之后的所有段也满足 `segment.start >= end`（因为有序），所以可以安全跳出。正确。 - **seed 预热与派工成功的语义差异**： - seed: `op_type_name` 为空时不推进 `last_end_by_machine` 和 `last_op_type_by_machine` - 派工: `last_end_by_machine` 条件更新（更晚才覆盖），`last_op_type_by_machine` 非空时直接更新 - plan 通过 `conditional_op_type=True/False` 区分两种模式。正确。 - **`batch_order.py:90-106` 的广域 `try/except`**：当前忙时统计和工种更新包在一个 `try/except` 里，任何一步失败都静默吞掉。plan 要求移除此 `except`，让调用方看到异常。这可能暴露当前被静默吞掉的 BUG。需要回归测试覆盖。 ### 任务 4：算法层日期来源统一 **可行性**：高。三份 `_due_exclusive()` 副本合并为一份、`_parse_date` / `_parse_datetime` 副本合并为统一导入，这是经典的消除重复重构。 **关键问题发现**： - **`schedule_optimizer.py:367` 的 `ready_date` 通过 `_parse_date()` 解析，`_parse_date()` 硬编码 `field="due_date"`**：严格模式下坏 `ready_date` 会抛出文案为"due_date格式不合法"的错误。这是一个真实 BUG。plan 暂停条件已覆盖，但实施步骤应更明确。 - **`scheduler.py:145` 的 `ready_date` 始终用非严格 `_parse_date()` 解析**：即使 `strict_mode=True`，`ready_date` 也不会抛错。这与 `due_date`（第 138 行严格模式下走 `parse_optional_date`）不一致。plan 任务 4 步骤 4.2 要求修复此不一致。 - **`created_at` 的策略相关启用**：plan 要求在 `optimize_schedule()` 中检查候选策略集合是否包含 FIFO。由于 `batch_for_sort` 构造（行 359-370）发生在策略循环之前，`created_at` 解析也在策略循环之前。这意味着只要 `valid_strategies` 包含 `fifo`（默认包含），严格模式就会对 `created_at` 做 strict 校验。这在语义上可能过于激进——用户可能只想用 `priority_first` 策略，但因为默认候选集包含 `fifo` 而被坏 `created_at` 阻断。 - **`ready_date` 下界的 `adjust_to_working_time()` 异常上浮**：当前代码静默回退到 `dt0`，plan 要求直接上浮。需要评估日历服务异常的常见原因，确保不会因为日历配置问题导致批量排产失败。 ### 任务 5：优化器微优化 **可行性**：高。`build_order()` 缓存是简单的字典记忆化，邻域去重是简单的集合查找。 **逻辑验证**： - **`build_order()` 缓存键**：`(strategy.value, tuple(sorted(params0.items())))` 对于 `weighted` 策略，`params0` 包含两个 `float` 键值。`sorted()` 保证顺序一致性。对于非 `weighted` 策略，`params0 = {}` 或 `dict(strategy_params or {})`，哈希也稳定。正确。 - **`seen_hashes` 预热**：初始化时写入 `tuple(cur_order)` 可以避免第一次生成与当前顺序相同的邻域。shake 后清空并写回 `cur_order` 和 `best['order']`。正确。 - **重复跳过推进停滞计数**：plan 要求重复邻域"不计入 `attempts`，但必须继续推进用于触发 `restart_after` 的停滞计数"。当前代码 `no_improve += 1` 在非改进时触发（行 242）。如果重复邻域被跳过，需要额外在跳过分支中执行 `no_improve += 1`。plan 步骤 4.2 描述正确。
- 问题:
  - [高] JavaScript: schedule_optimizer ready_date 严格模式报错字段名错误
  - [中] 性能: sgs 评分升级后自动分配场景估算重复
  - [中] JavaScript: ready_date 下界调整异常上浮可能导致非预期排产中断
  - [低] JavaScript: 统一估算器在大量 seed 碎片场景下的上界可能过大
  - [低] JavaScript: 局部搜索 shake 后 seen_hashes 重置的语义需明确

### M3 · 第三轮：交叉审查——任务间依赖、遗漏风险与整体架构优雅性

- 状态: 已完成
- 记录时间: 2026-04-07T14:31:09.007Z
- 已审模块: 任务间依赖与顺序, 完成判定与验收口径, 架构优雅性与简洁性, 遗漏风险
- 摘要:

  ### 任务间依赖与执行顺序

  1. **任务 1 → 任务 2**：任务 2 的 `_score_internal_candidate()` 依赖任务 1 新建的 `estimate_internal_slot()` 和 `validate_internal_hours()`。顺序依赖正确。plan 在任务 2 步骤 2 的预期失败原因中也明确了这一点。
  2. **任务 3 独立性**：时间线有序化和运行期状态收口不依赖任务 1/2 的新 API，但会修改 `downtime.py`（被 `estimate_internal_slot()` 间接使用）。如果任务 3 先于任务 1 实施，`estimate_internal_slot()` 尚不存在，不影响；如果任务 3 后于任务 1 实施，`occupy_resource()` 的行为变更（有序插入）会影响 `estimate_internal_slot()` 内部的时间线假设。plan 将任务 3 放在任务 2 之后执行，这意味着任务 1/2 实施时 `occupy_resource()` 仍为无序 `append`，但 `estimate_internal_slot()` 不依赖有序假设（它通过 `find_overlap_shift_end()` 全扫描）。任务 3 之后 `find_overlap_shift_end()` 可以早停，但估算器不需要改动。**依赖关系处理正确。**
  3. **任务 4 独立性**：日期来源统一可以在任何时间实施，不依赖前三个任务。但如果任务 4 在任务 2 之后实施，需要注意 `sgs.py` 的导入已被任务 2 修改。plan 将任务 4 放在任务 3 之后，此时 `sgs.py` 已被任务 2 和 3 修改过。**文件冲突风险存在但可控。**
  4. **任务 5 依赖全部**：优化器微优化依赖前四个任务的成果来做全链回归。顺序正确。

  ### 完成判定与验收口径

  1. **完成判定第 9 条**："在本轮触达的文件与链路内，未引入新的静默回退、广域吞异常"——这要求实施者在每个任务完成后检查所有触达文件。但 plan 的回归测试集合已经很完善，覆盖了主要链路。
  2. **完成判定第 2 条**："因自动分配二次选择导致的最终 (machine, operator) 对差异不计为失败"——这承认了 `_score_internal_candidate()` 中的 `probe_only=True` 探测与正式排产时 `_schedule_internal()` 中的正式自动分配可能选出不同的 (mid, oid)。这是因为探测时不占用资源，正式排产时占用资源，导致时间线状态不同。plan 的处理正确。
  3. **完成判定第 8 条**："smoke_phase10 与大资源池基准在改动后都没有出现超过 30% 且未经确认的退化"——30% 阈值是否合理取决于具体场景。对于评分升级（从近似变为精确），一定程度的耗时增长是预期内的。30% 作为"需要暂停确认"而非"硬性失败"的阈值是合理的。

  ### 架构优雅性与简洁性评价

  **优点**：
  1. **职责分离清晰**：`internal_slot.py` 只做估算、`runtime_state.py` 只做状态更新、`validate_internal_hours()` 只做工时预检。每个新文件/函数的职责边界明确。
  2. **不引入新的平行模式**：plan 明确禁止"快速估算器/精确估算器"双模式，强制所有路径使用同一估算器。这简化了维护负担。
  3. **测试先行**：每个任务都先写失败用例，再实现，再验证。这确保了行为变更的可观测性。
  4. **暂停门槛设计合理**：每个任务都有明确的暂停条件，避免在不确定状态下继续前进。

  **不足/风险**：
  1. **`created_at` 严格校验在默认配置下过于激进**：详见 F8。
  2. **`ready_date` 异常上浮行为变更未充分评估影响**：详见 F5。
  3. **自动分配场景的估算重复**：详见 F4。这是一个有意识的取舍，但应在文档中更明确。

  ### 遗漏风险

  1. **`ortools_bottleneck.py` 的 `_parse_due_date()` 副本**：plan 任务 4 修改列表包含 `ortools_bottleneck.py`，但步骤 3 只提到"更新 `evaluation.py`、`dispatch_rules.py`、`ortools_bottleneck.py`"。需确认 `ortools_bottleneck.py:23-36` 的 `_parse_due_date()` 也会被替换为共享导入。
  2. **`sgs.py` 导入清理**：plan 任务 2 步骤 3.6 说"导入清理：`parse_required_float` 最终应从 `sgs.py` 导入列表删除"。但如果任务 2 在任务 4 之前完成，`parse_optional_date` 仍需要保留（给 `_parse_date()` 使用）。直到任务 4 将 `_parse_date()` 替换为 `date_parsers.py` 的共享导入后，`parse_optional_date` 才能从 `sgs.py` 中移除。**导入清理的时序需要谨慎。**
  3. **`scheduler.py` 导入路径变更**：当前 `scheduler.py` 通过 `schedule_params.py` 转导出 `parse_date` 和 `parse_datetime`。任务 4 要切断这条路径，改为直接从 `date_parsers.py` 导入。但 `schedule_params.py` 自身仍使用 `parse_date` 和 `parse_datetime`（第 15 行），不受影响。**变更范围可控。**
- 结论:

  ### 任务间依赖与执行顺序 1. **任务 1 → 任务 2**：任务 2 的 `_score_internal_candidate()` 依赖任务 1 新建的 `estimate_internal_slot()` 和 `validate_internal_hours()`。顺序依赖正确。plan 在任务 2 步骤 2 的预期失败原因中也明确了这一点。 2. **任务 3 独立性**：时间线有序化和运行期状态收口不依赖任务 1/2 的新 API，但会修改 `downtime.py`（被 `estimate_internal_slot()` 间接使用）。如果任务 3 先于任务 1 实施，`estimate_internal_slot()` 尚不存在，不影响；如果任务 3 后于任务 1 实施，`occupy_resource()` 的行为变更（有序插入）会影响 `estimate_internal_slot()` 内部的时间线假设。plan 将任务 3 放在任务 2 之后执行，这意味着任务 1/2 实施时 `occupy_resource()` 仍为无序 `append`，但 `estimate_internal_slot()` 不依赖有序假设（它通过 `find_overlap_shift_end()` 全扫描）。任务 3 之后 `find_overlap_shift_end()` 可以早停，但估算器不需要改动。**依赖关系处理正确。** 3. **任务 4 独立性**：日期来源统一可以在任何时间实施，不依赖前三个任务。但如果任务 4 在任务 2 之后实施，需要注意 `sgs.py` 的导入已被任务 2 修改。plan 将任务 4 放在任务 3 之后，此时 `sgs.py` 已被任务 2 和 3 修改过。**文件冲突风险存在但可控。** 4. **任务 5 依赖全部**：优化器微优化依赖前四个任务的成果来做全链回归。顺序正确。 ### 完成判定与验收口径 1. **完成判定第 9 条**："在本轮触达的文件与链路内，未引入新的静默回退、广域吞异常"——这要求实施者在每个任务完成后检查所有触达文件。但 plan 的回归测试集合已经很完善，覆盖了主要链路。 2. **完成判定第 2 条**："因自动分配二次选择导致的最终 (machine, operator) 对差异不计为失败"——这承认了 `_score_internal_candidate()` 中的 `probe_only=True` 探测与正式排产时 `_schedule_internal()` 中的正式自动分配可能选出不同的 (mid, oid)。这是因为探测时不占用资源，正式排产时占用资源，导致时间线状态不同。plan 的处理正确。 3. **完成判定第 8 条**："smoke_phase10 与大资源池基准在改动后都没有出现超过 30% 且未经确认的退化"——30% 阈值是否合理取决于具体场景。对于评分升级（从近似变为精确），一定程度的耗时增长是预期内的。30% 作为"需要暂停确认"而非"硬性失败"的阈值是合理的。 ### 架构优雅性与简洁性评价 **优点**： 1. **职责分离清晰**：`internal_slot.py` 只做估算、`runtime_state.py` 只做状态更新、`validate_internal_hours()` 只做工时预检。每个新文件/函数的职责边界明确。 2. **不引入新的平行模式**：plan 明确禁止"快速估算器/精确估算器"双模式，强制所有路径使用同一估算器。这简化了维护负担。 3. **测试先行**：每个任务都先写失败用例，再实现，再验证。这确保了行为变更的可观测性。 4. **暂停门槛设计合理**：每个任务都有明确的暂停条件，避免在不确定状态下继续前进。 **不足/风险**： 1. **`created_at` 严格校验在默认配置下过于激进**：详见 F8。 2. **`ready_date` 异常上浮行为变更未充分评估影响**：详见 F5。 3. **自动分配场景的估算重复**：详见 F4。这是一个有意识的取舍，但应在文档中更明确。 ### 遗漏风险 1. **`ortools_bottleneck.py` 的 `_parse_due_date()` 副本**：plan 任务 4 修改列表包含 `ortools_bottleneck.py`，但步骤 3 只提到"更新 `evaluation.py`、`dispatch_rules.py`、`ortools_bottleneck.py`"。需确认 `ortools_bottleneck.py:23-36` 的 `_parse_due_date()` 也会被替换为共享导入。 2. **`sgs.py` 导入清理**：plan 任务 2 步骤 3.6 说"导入清理：`parse_required_float` 最终应从 `sgs.py` 导入列表删除"。但如果任务 2 在任务 4 之前完成，`parse_optional_date` 仍需要保留（给 `_parse_date()` 使用）。直到任务 4 将 `_parse_date()` 替换为 `date_parsers.py` 的共享导入后，`parse_optional_date` 才能从 `sgs.py` 中移除。**导入清理的时序需要谨慎。** 3. **`scheduler.py` 导入路径变更**：当前 `scheduler.py` 通过 `schedule_params.py` 转导出 `parse_date` 和 `parse_datetime`。任务 4 要切断这条路径，改为直接从 `date_parsers.py` 导入。但 `schedule_params.py` 自身仍使用 `parse_date` 和 `parse_datetime`（第 15 行），不受影响。**变更范围可控。**
- 问题:
  - [中] JavaScript: created_at 严格校验在默认配置下过于激进
  - [低] 可维护性: 移除广域吞异常后 seed 预热可能暴露新异常

## 最终结论

## 三轮深度审查总结

经过三轮深入审查——第一轮逐条核验 plan 中 12 项修订前提、6 组引用链共 15+ 处代码行号引用；第二轮追踪 5 个任务的实现路径、算法正确性与边界完备性；第三轮交叉审查任务间依赖、完成判定口径与整体架构优雅性——对该 plan 做出以下判定：

### 总体评价

**这是一份质量极高的重构 plan。** 它在以下方面做得非常好：
1. **代码事实基础扎实**：12 项修订前提全部核验通过，行号引用仅有 1 处微偏（F1，不影响实施）。
2. **架构设计简洁优雅**：`internal_slot.py` 只做估算、`runtime_state.py` 只做状态更新、`validate_internal_hours()` 只做工时预检——职责分离清晰，不引入新的平行模式。
3. **约束体系严密**：每个任务都有明确的实施约束、暂停门槛和回归测试集合。"不做"清单完整且诚实。
4. **兼容性保护到位**：明确保留 `GreedyScheduler.schedule()` 的 raw 输入兼容边界，不静默收窄 direct-call 场景。
5. **测试先行**：每个任务先写失败用例，再实现，再验证——确保行为变更可观测。

### 必须在实施前修正的问题（1 项高严重级别）

- **F3**：`schedule_optimizer.py` 的 `_parse_date()` 硬编码 `field="due_date"`，被同时用于 `due_date` 和 `ready_date` 解析。plan 暂停条件已覆盖此 BUG，但实施步骤本身应显式要求 `ready_date` 使用 `field="ready_date"` 的包装，不能仅依赖暂停条件来"事后发现"。

### 建议在实施前澄清的问题（3 项中严重级别）

- **F4**：自动分配场景中评分估算存在已知重复（M×O 对被估算两次）。plan "明确不做"第 11 项已承认，但应在实施说明中更明确标注。
- **F5**：`ready_date` 下界调整的异常上浮可能导致日历服务异常时排产中断。建议区分"合法日期入参后日历服务内部异常"与"坏入参"两种情况。
- **F8**：`created_at` 的严格校验判断逻辑应基于 `keys`（当前轮次实际使用的策略列表）而非 `valid_strategies`（默认包含全部策略），避免在非 FIFO 场景下因坏 `created_at` 意外阻断排产。

### 低风险观察（5 项低严重级别）

- **F1**：引用行号微偏（278-340 → 278-341），不影响实施。
- **F2**：`_parse_date` 非严格模式双重解析，plan 任务 4 已计划修复。
- **F6**：大量 seed 碎片场景下上界较大，建议在基准测试中覆盖。
- **F7**：局部搜索 shake 后 `seen_hashes` 重置语义，plan 文字描述正确。
- **F9**：移除广域吞异常后 seed 预热可能暴露新异常，plan 回归列表已覆盖。

### 最终判定

该 plan 能够达成其声明的目标。整体架构设计优雅简洁，没有过度兜底或静默回退，逻辑严谨。在修正 F3（将 `ready_date` 的 `field` 参数差异化写入实施步骤）和澄清 F8（`created_at` 严格校验判断逻辑）之后，可以开始实施。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnoprmwg-2bkfhs",
  "createdAt": "2026-04-07T00:00:00.000Z",
  "updatedAt": "2026-04-07T14:31:26.269Z",
  "finalizedAt": "2026-04-07T14:31:26.269Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "算法层统一估算与派工重构plan三轮深度审查_第四轮核验",
    "date": "2026-04-07",
    "overview": "对 2026-04-07 算法层统一估算与派工重构 plan 进行三轮深度审查，逐条核验引用链、实现可行性、逻辑严谨性与潜在遗漏"
  },
  "scope": {
    "markdown": "# 算法层统一估算与派工重构 plan 三轮深度审查（第四轮核验）\n\n**审查日期**：2026-04-08\n**审查对象**：`.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`\n**审查范围**：plan 中所有引用链、代码事实断言、任务步骤可行性、边界约束完备性、潜在 BUG 与遗漏\n\n## 审查方法\n\n- 第一轮：核验 plan 中所有代码行号引用与事实断言\n- 第二轮：追踪每个任务的实现路径，验证逻辑严谨性与边界完备性\n- 第三轮：交叉审查任务间依赖、遗漏风险与整体架构优雅性"
  },
  "summary": {
    "latestConclusion": "## 三轮深度审查总结\n\n经过三轮深入审查——第一轮逐条核验 plan 中 12 项修订前提、6 组引用链共 15+ 处代码行号引用；第二轮追踪 5 个任务的实现路径、算法正确性与边界完备性；第三轮交叉审查任务间依赖、完成判定口径与整体架构优雅性——对该 plan 做出以下判定：\n\n### 总体评价\n\n**这是一份质量极高的重构 plan。** 它在以下方面做得非常好：\n1. **代码事实基础扎实**：12 项修订前提全部核验通过，行号引用仅有 1 处微偏（F1，不影响实施）。\n2. **架构设计简洁优雅**：`internal_slot.py` 只做估算、`runtime_state.py` 只做状态更新、`validate_internal_hours()` 只做工时预检——职责分离清晰，不引入新的平行模式。\n3. **约束体系严密**：每个任务都有明确的实施约束、暂停门槛和回归测试集合。\"不做\"清单完整且诚实。\n4. **兼容性保护到位**：明确保留 `GreedyScheduler.schedule()` 的 raw 输入兼容边界，不静默收窄 direct-call 场景。\n5. **测试先行**：每个任务先写失败用例，再实现，再验证——确保行为变更可观测。\n\n### 必须在实施前修正的问题（1 项高严重级别）\n\n- **F3**：`schedule_optimizer.py` 的 `_parse_date()` 硬编码 `field=\"due_date\"`，被同时用于 `due_date` 和 `ready_date` 解析。plan 暂停条件已覆盖此 BUG，但实施步骤本身应显式要求 `ready_date` 使用 `field=\"ready_date\"` 的包装，不能仅依赖暂停条件来\"事后发现\"。\n\n### 建议在实施前澄清的问题（3 项中严重级别）\n\n- **F4**：自动分配场景中评分估算存在已知重复（M×O 对被估算两次）。plan \"明确不做\"第 11 项已承认，但应在实施说明中更明确标注。\n- **F5**：`ready_date` 下界调整的异常上浮可能导致日历服务异常时排产中断。建议区分\"合法日期入参后日历服务内部异常\"与\"坏入参\"两种情况。\n- **F8**：`created_at` 的严格校验判断逻辑应基于 `keys`（当前轮次实际使用的策略列表）而非 `valid_strategies`（默认包含全部策略），避免在非 FIFO 场景下因坏 `created_at` 意外阻断排产。\n\n### 低风险观察（5 项低严重级别）\n\n- **F1**：引用行号微偏（278-340 → 278-341），不影响实施。\n- **F2**：`_parse_date` 非严格模式双重解析，plan 任务 4 已计划修复。\n- **F6**：大量 seed 碎片场景下上界较大，建议在基准测试中覆盖。\n- **F7**：局部搜索 shake 后 `seen_hashes` 重置语义，plan 文字描述正确。\n- **F9**：移除广域吞异常后 seed 预热可能暴露新异常，plan 回归列表已覆盖。\n\n### 最终判定\n\n该 plan 能够达成其声明的目标。整体架构设计优雅简洁，没有过度兜底或静默回退，逻辑严谨。在修正 F3（将 `ready_date` 的 `field` 参数差异化写入实施步骤）和澄清 F8（`created_at` 严格校验判断逻辑）之后，可以开始实施。",
    "recommendedNextAction": "1. 修正 F3：在任务 4 步骤 4 正文中明确要求 ready_date 使用 field=\"ready_date\" 而非复用 field=\"due_date\" 的包装。2. 澄清 F8：将 created_at 严格校验的判断条件从 valid_strategies 改为 keys。3. 补充 F4 说明：在\"明确不做\"列表中标注自动分配场景的估算重复是已知性能取舍。完成以上修正后即可开始按任务顺序实施。",
    "reviewedModules": [
      "代码行号与事实断言核验",
      "任务1-统一内部工序估算器",
      "任务2-拆分dispatch_sgs评分",
      "任务3-时间线有序化与运行期状态收口",
      "任务4-算法层日期来源统一",
      "任务5-优化器微优化与全链回归",
      "任务间依赖与顺序",
      "完成判定与验收口径",
      "架构优雅性与简洁性",
      "遗漏风险"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 9,
    "severity": {
      "high": 1,
      "medium": 3,
      "low": 5
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "第一轮：代码行号引用与事实断言核验",
      "status": "completed",
      "recordedAt": "2026-04-07T14:28:44.601Z",
      "summaryMarkdown": "逐条核验 plan 修订前提与引用链总览中的代码行号与事实断言，检验与当前代码的一致性。\n\n### 核验通过的断言\n\n1. **修订前提 1**：服务主链 `_run_schedule_impl() → collect_schedule_run_input() → orchestrate_schedule_run() → optimize_schedule() → GreedyScheduler.schedule()` 已核实，链路正确。\n2. **修订前提 2**：`scheduler.py:469-543` 与 `auto_assign.py:156-223` 确属同一估算族（三路时间线同时检查、循环推进直到稳定）。`sgs.py:278-340` 确实是顺序链式近似评分（连续三次 `find_earliest_available_start`）。\n3. **修订前提 3**：`schedule_input_builder.py:128-215` 已核实确实规范化 `setup_hours`、`unit_hours`、`ext_days`、`ext_group_total_days`。\n4. **修订前提 4**：`core/algorithms/__init__.py` 确实仍导出 `GreedyScheduler`。\n5. **修订前提 5**：`sgs.py:18-24` 确实对 `due_date` 使用 `parse_optional_date()` 做严格包装。\n6. **修订前提 6**：`strict_parse.py` 确实只有 `parse_required_date`/`parse_optional_date`，无日期时间版本。`schedule_optimizer.py:343-357` 的 `_parse_datetime()` 确实是本地非严格实现。\n7. **修订前提 7**：`scheduler.py:289-304` 确实在 seed 预热阶段维护 `machine_busy_hours`、`operator_busy_hours`、`last_end_by_machine`、`last_op_type_by_machine`。\n8. **修订前提 8**：`scheduler.py:513` 和 `auto_assign.py:185` 确实都写死 `guard < 200`。\n9. **修订前提 9**：`scheduler.py:494` 确实有 `or 1.0`；`sgs.py:323` 确实有 `or 1.0`；`auto_assign.py:165-169` 确实在内层用 `raw_eff is not None` 但外层有 `except Exception: eff = 1.0`。\n10. **修订前提 10**：已确认 `schedule_summary.py` 与 `report/calculations.py` 不在本轮范围。\n11. **修订前提 11**：`scheduler.py:138-146` 确实同时构造 `due_date`、`ready_date`、`created_at`。`sort_strategies.py:122` 确认 `created_at` 只在 FIFO 排序键中消费。\n12. **修订前提 12**：`schedule_params.py:105` 确认 `except Exception: pass` 存在，且确实不在本轮范围。\n\n### 核验到的行号偏移/事实微偏\n\n1. **引用链 3.3**：\"`scheduler.py:215-245` 维护运行期变量\"——实际变量声明范围是 215-245，但 `seed_count` 在第 246 行，紧接其后。这只是小偏移，不影响语义。\n2. **引用链 4.1**：plan 写 `batch_order.py:10-122`——实际为 10-122（核实一致），但注意 `batch_order.py` 总行数仅 124，文件更短小。\n3. **引用链 4.2**：plan 写 `sgs.py:27-506`——实际是 27-506（核实一致），总行数 508。\n4. **引用链 5.2**：plan 写 `sgs.py:278-340` 为近似评分族范围——核实一致，但评分与估算逻辑实际到第 341 行才结束（`change_pen = 0`），plan 写 340 少了一行。\n\n### 重要事实补充\n\n- `scheduler.py` 从 `schedule_params.py` 转导出 `parse_date` 和 `parse_datetime`（第 30-31 行），而 `schedule_params.py` 从 `date_parsers.py` 导入。plan 任务 4 明确要切断这个转导出路径。\n- `sgs.py` 第 425 行 `best_pair = candidates[0]` 确实是死代码路径，plan 任务 2 步骤 3 第 5 点已明确要删除。\n- `batch_order.py:102` 的 `except Exception: pass` 和 `sgs.py:470-472` 的 `except Exception:` 都是广域吞异常，plan 任务 3 已计划收口。\n- `schedule_optimizer.py:337-341` 的 `_parse_date()` 对非严格模式也走了一次 `parse_optional_date()` 然后 `except` 回退，本质是双重解析；plan 任务 4 正确识别了这个问题。",
      "conclusionMarkdown": "逐条核验 plan 修订前提与引用链总览中的代码行号与事实断言，检验与当前代码的一致性。 ### 核验通过的断言 1. **修订前提 1**：服务主链 `_run_schedule_impl() → collect_schedule_run_input() → orchestrate_schedule_run() → optimize_schedule() → GreedyScheduler.schedule()` 已核实，链路正确。 2. **修订前提 2**：`scheduler.py:469-543` 与 `auto_assign.py:156-223` 确属同一估算族（三路时间线同时检查、循环推进直到稳定）。`sgs.py:278-340` 确实是顺序链式近似评分（连续三次 `find_earliest_available_start`）。 3. **修订前提 3**：`schedule_input_builder.py:128-215` 已核实确实规范化 `setup_hours`、`unit_hours`、`ext_days`、`ext_group_total_days`。 4. **修订前提 4**：`core/algorithms/__init__.py` 确实仍导出 `GreedyScheduler`。 5. **修订前提 5**：`sgs.py:18-24` 确实对 `due_date` 使用 `parse_optional_date()` 做严格包装。 6. **修订前提 6**：`strict_parse.py` 确实只有 `parse_required_date`/`parse_optional_date`，无日期时间版本。`schedule_optimizer.py:343-357` 的 `_parse_datetime()` 确实是本地非严格实现。 7. **修订前提 7**：`scheduler.py:289-304` 确实在 seed 预热阶段维护 `machine_busy_hours`、`operator_busy_hours`、`last_end_by_machine`、`last_op_type_by_machine`。 8. **修订前提 8**：`scheduler.py:513` 和 `auto_assign.py:185` 确实都写死 `guard < 200`。 9. **修订前提 9**：`scheduler.py:494` 确实有 `or 1.0`；`sgs.py:323` 确实有 `or 1.0`；`auto_assign.py:165-169` 确实在内层用 `raw_eff is not None` 但外层有 `except Exception: eff = 1.0`。 10. **修订前提 10**：已确认 `schedule_summary.py` 与 `report/calculations.py` 不在本轮范围。 11. **修订前提 11**：`scheduler.py:138-146` 确实同时构造 `due_date`、`ready_date`、`created_at`。`sort_strategies.py:122` 确认 `created_at` 只在 FIFO 排序键中消费。 12. **修订前提 12**：`schedule_params.py:105` 确认 `except Exception: pass` 存在，且确实不在本轮范围。 ### 核验到的行号偏移/事实微偏 1. **引用链 3.3**：\"`scheduler.py:215-245` 维护运行期变量\"——实际变量声明范围是 215-245，但 `seed_count` 在第 246 行，紧接其后。这只是小偏移，不影响语义。 2. **引用链 4.1**：plan 写 `batch_order.py:10-122`——实际为 10-122（核实一致），但注意 `batch_order.py` 总行数仅 124，文件更短小。 3. **引用链 4.2**：plan 写 `sgs.py:27-506`——实际是 27-506（核实一致），总行数 508。 4. **引用链 5.2**：plan 写 `sgs.py:278-340` 为近似评分族范围——核实一致，但评分与估算逻辑实际到第 341 行才结束（`change_pen = 0`），plan 写 340 少了一行。 ### 重要事实补充 - `scheduler.py` 从 `schedule_params.py` 转导出 `parse_date` 和 `parse_datetime`（第 30-31 行），而 `schedule_params.py` 从 `date_parsers.py` 导入。plan 任务 4 明确要切断这个转导出路径。 - `sgs.py` 第 425 行 `best_pair = candidates[0]` 确实是死代码路径，plan 任务 2 步骤 3 第 5 点已明确要删除。 - `batch_order.py:102` 的 `except Exception: pass` 和 `sgs.py:470-472` 的 `except Exception:` 都是广域吞异常，plan 任务 3 已计划收口。 - `schedule_optimizer.py:337-341` 的 `_parse_date()` 对非严格模式也走了一次 `parse_optional_date()` 然后 `except` 回退，本质是双重解析；plan 任务 4 正确识别了这个问题。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 469,
          "lineEnd": 543,
          "symbol": "_schedule_internal"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 156,
          "lineEnd": 223,
          "symbol": "auto_assign_internal_resources"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 278,
          "lineEnd": 341,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 215,
          "lineEnd": 246,
          "symbol": "schedule"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 289,
          "lineEnd": 304,
          "symbol": "seed_runtime_state"
        },
        {
          "path": "core/algorithms/greedy/downtime.py",
          "lineStart": 20,
          "lineEnd": 28,
          "symbol": "occupy_resource"
        },
        {
          "path": "core/algorithms/greedy/date_parsers.py",
          "lineStart": 7,
          "lineEnd": 41
        },
        {
          "path": "core/algorithms/evaluation.py",
          "lineStart": 55,
          "lineEnd": 58,
          "symbol": "_due_exclusive"
        },
        {
          "path": "core/algorithms/dispatch_rules.py",
          "lineStart": 25,
          "lineEnd": 28,
          "symbol": "_due_exclusive"
        },
        {
          "path": "core/algorithms/ortools_bottleneck.py",
          "lineStart": 39,
          "lineEnd": 42,
          "symbol": "_due_exclusive"
        },
        {
          "path": "core/services/common/strict_parse.py",
          "lineStart": 85,
          "lineEnd": 102
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 335,
          "lineEnd": 357,
          "symbol": "_parse_datetime"
        },
        {
          "path": "core/algorithms/greedy/schedule_params.py",
          "lineStart": 103,
          "lineEnd": 106
        }
      ],
      "reviewedModules": [
        "代码行号与事实断言核验"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F1-LINE-DRIFT",
        "F2-PARSE-DATE-DOUBLE"
      ]
    },
    {
      "id": "M2",
      "title": "第二轮：逐任务实现可行性、逻辑严谨性与潜在 BUG 审查",
      "status": "completed",
      "recordedAt": "2026-04-07T14:30:27.787Z",
      "summaryMarkdown": "### 任务 1：统一内部工序估算器\n\n**可行性**：高。`_schedule_internal()` 和 `auto_assign_internal_resources()` 的核心估算逻辑几乎完全相同（三路时间线同时检查 + 循环避让），收口到一个函数是自然的重构。\n\n**逻辑严谨性验证**：\n- **避让上界公式**：`N_machine + N_operator + N_downtime + 1` 是正确的。每次避让至少跳过一个段的终点，而段总数有限。越过上界应视为实现错误而非业务失败，plan 的设计正确。\n- **`validate_internal_hours()` 的双重安全要求**：对 raw direct-call 输入做 `float()` 转换 + 有限性检查，对服务主链已规范化输入直接通过——这个设计可行，因为 `float(already_float)` 是无损操作。\n- **`abort_after` 早停语义**：plan 要求在 `adjust_to_working_time()` 之后和每次避让后都检查。对齐 `auto_assign.py:159` 和 `200` 的当前早停点。正确。\n- **零时长工序场景**：plan 步骤 1.6 要求 `start_time == end_time` 且不报错，但需注意零时长工序仍应占用资源（`occupy_resource` 调用）。当前 `add_working_hours(earliest, 0)` 应返回 `earliest`，所以 `start_time == end_time == earliest`。`occupy_resource(mid, earliest, earliest)` 会写入一个零长度区间，被 `find_overlap_shift_end()` 的 `e <= s` 检查自动跳过。设计正确。\n\n**遗漏/风险**：\n- `auto_assign` 内 `_scaled_hours()` 闭包捕获 `oid` 问题：当前代码通过默认参数 `_oid: str = oid` 解决。迁移到 `estimate_internal_slot()` 后此问题消失，因为 `oid` 作为显式参数传入。正确。\n- `efficiency_fallback_used` 在 `probe_only` 模式下不应计入全局计数器：plan 步骤 4.3 说\"`probe_only=True` 时所有 `increment_counter(...)` 调用继续走空操作\"，但 `estimate_internal_slot()` 内部设置 `efficiency_fallback_used=True` 是返回值属性，不是计数器调用。调用方需要根据 `probe_only` 决定是否调用 `increment_counter`。plan 步骤 4.4 在 `_schedule_internal()` 中处理了这个分支。可行。\n\n### 任务 2：拆分 `dispatch_sgs()` 评分\n\n**可行性**：高。当前函数 ~480 行，拆分出 5 个子函数后主函数将大幅缩减。\n\n**关键逻辑审查**：\n- **`avg_proc_hours` 初始化段**：plan 要求复用 `validate_internal_hours()` 而不是保留第三套公式。但 `validate_internal_hours()` 抛 `ValueError` 时只意味着该样本不可用，不应让初始化段整体崩溃。plan 步骤 3.3 明确了这一点。\n- **评分阶段工时坏值与资源缺失的分离**：plan 要求 `validate_internal_hours()` 先于 `probe_only=True` 自动分配。这意味着坏 `setup_hours` 会在资源补全之前被检测到，不会与\"缺资源\"混淆。逻辑正确。\n- **`candidates[0]` 死代码删除**：第 424-425 行确认是死代码——`best_pair` 在循环中要么被赋值（`best_key` 被更新），要么至少有异常兜底 key。只要候选列表非空且循环执行了，`best_pair` 不可能为 `None`。plan 删除正确。\n\n**性能风险**：\n- 评分升级后，每个已有资源的候选对都从顺序链式估算变成三路避让估算。在非自动分配场景下（资源已确定），每个候选只做一次估算，影响有限。但在自动分配场景下，估算做了两次（一次在 `auto_assign` 内部找最优对，一次在 `_score_internal_candidate` 中取评分）。plan 的\"明确不做\"第 11 项承认了此重复。\n\n### 任务 3：时间线有序化\n\n**可行性**：高。`occupy_resource()` 改为 `bisect.insort` 只需 2-3 行改动。\n\n**关键验证**：\n- **Python 3.8 兼容性**：`bisect.insort` 在 Python 3.8 只支持 `(a, x)` 两参数形式，不支持 `key=`。使用 `(start, end)` 元组自然顺序是兼容的。plan 正确。\n- **`find_overlap_shift_end()` 早停正确性**：有序时间线上，`segment.start >= end` 之后的所有段也满足 `segment.start >= end`（因为有序），所以可以安全跳出。正确。\n- **seed 预热与派工成功的语义差异**：\n  - seed: `op_type_name` 为空时不推进 `last_end_by_machine` 和 `last_op_type_by_machine`\n  - 派工: `last_end_by_machine` 条件更新（更晚才覆盖），`last_op_type_by_machine` 非空时直接更新\n  - plan 通过 `conditional_op_type=True/False` 区分两种模式。正确。\n- **`batch_order.py:90-106` 的广域 `try/except`**：当前忙时统计和工种更新包在一个 `try/except` 里，任何一步失败都静默吞掉。plan 要求移除此 `except`，让调用方看到异常。这可能暴露当前被静默吞掉的 BUG。需要回归测试覆盖。\n\n### 任务 4：算法层日期来源统一\n\n**可行性**：高。三份 `_due_exclusive()` 副本合并为一份、`_parse_date` / `_parse_datetime` 副本合并为统一导入，这是经典的消除重复重构。\n\n**关键问题发现**：\n- **`schedule_optimizer.py:367` 的 `ready_date` 通过 `_parse_date()` 解析，`_parse_date()` 硬编码 `field=\"due_date\"`**：严格模式下坏 `ready_date` 会抛出文案为\"due_date格式不合法\"的错误。这是一个真实 BUG。plan 暂停条件已覆盖，但实施步骤应更明确。\n- **`scheduler.py:145` 的 `ready_date` 始终用非严格 `_parse_date()` 解析**：即使 `strict_mode=True`，`ready_date` 也不会抛错。这与 `due_date`（第 138 行严格模式下走 `parse_optional_date`）不一致。plan 任务 4 步骤 4.2 要求修复此不一致。\n- **`created_at` 的策略相关启用**：plan 要求在 `optimize_schedule()` 中检查候选策略集合是否包含 FIFO。由于 `batch_for_sort` 构造（行 359-370）发生在策略循环之前，`created_at` 解析也在策略循环之前。这意味着只要 `valid_strategies` 包含 `fifo`（默认包含），严格模式就会对 `created_at` 做 strict 校验。这在语义上可能过于激进——用户可能只想用 `priority_first` 策略，但因为默认候选集包含 `fifo` 而被坏 `created_at` 阻断。\n- **`ready_date` 下界的 `adjust_to_working_time()` 异常上浮**：当前代码静默回退到 `dt0`，plan 要求直接上浮。需要评估日历服务异常的常见原因，确保不会因为日历配置问题导致批量排产失败。\n\n### 任务 5：优化器微优化\n\n**可行性**：高。`build_order()` 缓存是简单的字典记忆化，邻域去重是简单的集合查找。\n\n**逻辑验证**：\n- **`build_order()` 缓存键**：`(strategy.value, tuple(sorted(params0.items())))` 对于 `weighted` 策略，`params0` 包含两个 `float` 键值。`sorted()` 保证顺序一致性。对于非 `weighted` 策略，`params0 = {}` 或 `dict(strategy_params or {})`，哈希也稳定。正确。\n- **`seen_hashes` 预热**：初始化时写入 `tuple(cur_order)` 可以避免第一次生成与当前顺序相同的邻域。shake 后清空并写回 `cur_order` 和 `best['order']`。正确。\n- **重复跳过推进停滞计数**：plan 要求重复邻域\"不计入 `attempts`，但必须继续推进用于触发 `restart_after` 的停滞计数\"。当前代码 `no_improve += 1` 在非改进时触发（行 242）。如果重复邻域被跳过，需要额外在跳过分支中执行 `no_improve += 1`。plan 步骤 4.2 描述正确。",
      "conclusionMarkdown": "### 任务 1：统一内部工序估算器 **可行性**：高。`_schedule_internal()` 和 `auto_assign_internal_resources()` 的核心估算逻辑几乎完全相同（三路时间线同时检查 + 循环避让），收口到一个函数是自然的重构。 **逻辑严谨性验证**： - **避让上界公式**：`N_machine + N_operator + N_downtime + 1` 是正确的。每次避让至少跳过一个段的终点，而段总数有限。越过上界应视为实现错误而非业务失败，plan 的设计正确。 - **`validate_internal_hours()` 的双重安全要求**：对 raw direct-call 输入做 `float()` 转换 + 有限性检查，对服务主链已规范化输入直接通过——这个设计可行，因为 `float(already_float)` 是无损操作。 - **`abort_after` 早停语义**：plan 要求在 `adjust_to_working_time()` 之后和每次避让后都检查。对齐 `auto_assign.py:159` 和 `200` 的当前早停点。正确。 - **零时长工序场景**：plan 步骤 1.6 要求 `start_time == end_time` 且不报错，但需注意零时长工序仍应占用资源（`occupy_resource` 调用）。当前 `add_working_hours(earliest, 0)` 应返回 `earliest`，所以 `start_time == end_time == earliest`。`occupy_resource(mid, earliest, earliest)` 会写入一个零长度区间，被 `find_overlap_shift_end()` 的 `e <= s` 检查自动跳过。设计正确。 **遗漏/风险**： - `auto_assign` 内 `_scaled_hours()` 闭包捕获 `oid` 问题：当前代码通过默认参数 `_oid: str = oid` 解决。迁移到 `estimate_internal_slot()` 后此问题消失，因为 `oid` 作为显式参数传入。正确。 - `efficiency_fallback_used` 在 `probe_only` 模式下不应计入全局计数器：plan 步骤 4.3 说\"`probe_only=True` 时所有 `increment_counter(...)` 调用继续走空操作\"，但 `estimate_internal_slot()` 内部设置 `efficiency_fallback_used=True` 是返回值属性，不是计数器调用。调用方需要根据 `probe_only` 决定是否调用 `increment_counter`。plan 步骤 4.4 在 `_schedule_internal()` 中处理了这个分支。可行。 ### 任务 2：拆分 `dispatch_sgs()` 评分 **可行性**：高。当前函数 ~480 行，拆分出 5 个子函数后主函数将大幅缩减。 **关键逻辑审查**： - **`avg_proc_hours` 初始化段**：plan 要求复用 `validate_internal_hours()` 而不是保留第三套公式。但 `validate_internal_hours()` 抛 `ValueError` 时只意味着该样本不可用，不应让初始化段整体崩溃。plan 步骤 3.3 明确了这一点。 - **评分阶段工时坏值与资源缺失的分离**：plan 要求 `validate_internal_hours()` 先于 `probe_only=True` 自动分配。这意味着坏 `setup_hours` 会在资源补全之前被检测到，不会与\"缺资源\"混淆。逻辑正确。 - **`candidates[0]` 死代码删除**：第 424-425 行确认是死代码——`best_pair` 在循环中要么被赋值（`best_key` 被更新），要么至少有异常兜底 key。只要候选列表非空且循环执行了，`best_pair` 不可能为 `None`。plan 删除正确。 **性能风险**： - 评分升级后，每个已有资源的候选对都从顺序链式估算变成三路避让估算。在非自动分配场景下（资源已确定），每个候选只做一次估算，影响有限。但在自动分配场景下，估算做了两次（一次在 `auto_assign` 内部找最优对，一次在 `_score_internal_candidate` 中取评分）。plan 的\"明确不做\"第 11 项承认了此重复。 ### 任务 3：时间线有序化 **可行性**：高。`occupy_resource()` 改为 `bisect.insort` 只需 2-3 行改动。 **关键验证**： - **Python 3.8 兼容性**：`bisect.insort` 在 Python 3.8 只支持 `(a, x)` 两参数形式，不支持 `key=`。使用 `(start, end)` 元组自然顺序是兼容的。plan 正确。 - **`find_overlap_shift_end()` 早停正确性**：有序时间线上，`segment.start >= end` 之后的所有段也满足 `segment.start >= end`（因为有序），所以可以安全跳出。正确。 - **seed 预热与派工成功的语义差异**： - seed: `op_type_name` 为空时不推进 `last_end_by_machine` 和 `last_op_type_by_machine` - 派工: `last_end_by_machine` 条件更新（更晚才覆盖），`last_op_type_by_machine` 非空时直接更新 - plan 通过 `conditional_op_type=True/False` 区分两种模式。正确。 - **`batch_order.py:90-106` 的广域 `try/except`**：当前忙时统计和工种更新包在一个 `try/except` 里，任何一步失败都静默吞掉。plan 要求移除此 `except`，让调用方看到异常。这可能暴露当前被静默吞掉的 BUG。需要回归测试覆盖。 ### 任务 4：算法层日期来源统一 **可行性**：高。三份 `_due_exclusive()` 副本合并为一份、`_parse_date` / `_parse_datetime` 副本合并为统一导入，这是经典的消除重复重构。 **关键问题发现**： - **`schedule_optimizer.py:367` 的 `ready_date` 通过 `_parse_date()` 解析，`_parse_date()` 硬编码 `field=\"due_date\"`**：严格模式下坏 `ready_date` 会抛出文案为\"due_date格式不合法\"的错误。这是一个真实 BUG。plan 暂停条件已覆盖，但实施步骤应更明确。 - **`scheduler.py:145` 的 `ready_date` 始终用非严格 `_parse_date()` 解析**：即使 `strict_mode=True`，`ready_date` 也不会抛错。这与 `due_date`（第 138 行严格模式下走 `parse_optional_date`）不一致。plan 任务 4 步骤 4.2 要求修复此不一致。 - **`created_at` 的策略相关启用**：plan 要求在 `optimize_schedule()` 中检查候选策略集合是否包含 FIFO。由于 `batch_for_sort` 构造（行 359-370）发生在策略循环之前，`created_at` 解析也在策略循环之前。这意味着只要 `valid_strategies` 包含 `fifo`（默认包含），严格模式就会对 `created_at` 做 strict 校验。这在语义上可能过于激进——用户可能只想用 `priority_first` 策略，但因为默认候选集包含 `fifo` 而被坏 `created_at` 阻断。 - **`ready_date` 下界的 `adjust_to_working_time()` 异常上浮**：当前代码静默回退到 `dt0`，plan 要求直接上浮。需要评估日历服务异常的常见原因，确保不会因为日历配置问题导致批量排产失败。 ### 任务 5：优化器微优化 **可行性**：高。`build_order()` 缓存是简单的字典记忆化，邻域去重是简单的集合查找。 **逻辑验证**： - **`build_order()` 缓存键**：`(strategy.value, tuple(sorted(params0.items())))` 对于 `weighted` 策略，`params0` 包含两个 `float` 键值。`sorted()` 保证顺序一致性。对于非 `weighted` 策略，`params0 = {}` 或 `dict(strategy_params or {})`，哈希也稳定。正确。 - **`seen_hashes` 预热**：初始化时写入 `tuple(cur_order)` 可以避免第一次生成与当前顺序相同的邻域。shake 后清空并写回 `cur_order` 和 `best['order']`。正确。 - **重复跳过推进停滞计数**：plan 要求重复邻域\"不计入 `attempts`，但必须继续推进用于触发 `restart_after` 的停滞计数\"。当前代码 `no_improve += 1` 在非改进时触发（行 242）。如果重复邻域被跳过，需要额外在跳过分支中执行 `no_improve += 1`。plan 步骤 4.2 描述正确。",
      "evidence": [],
      "reviewedModules": [
        "任务1-统一内部工序估算器",
        "任务2-拆分dispatch_sgs评分",
        "任务3-时间线有序化与运行期状态收口",
        "任务4-算法层日期来源统一",
        "任务5-优化器微优化与全链回归"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F3-READY-DATE-FIELD-BUG",
        "F4-DOUBLE-ESTIMATE",
        "F5-READY-DATE-EXCEPTION-RISK",
        "F6-UPPER-BOUND-LARGE-SEED",
        "F7-SHAKE-RESET-CLARITY"
      ]
    },
    {
      "id": "M3",
      "title": "第三轮：交叉审查——任务间依赖、遗漏风险与整体架构优雅性",
      "status": "completed",
      "recordedAt": "2026-04-07T14:31:09.007Z",
      "summaryMarkdown": "### 任务间依赖与执行顺序\n\n1. **任务 1 → 任务 2**：任务 2 的 `_score_internal_candidate()` 依赖任务 1 新建的 `estimate_internal_slot()` 和 `validate_internal_hours()`。顺序依赖正确。plan 在任务 2 步骤 2 的预期失败原因中也明确了这一点。\n2. **任务 3 独立性**：时间线有序化和运行期状态收口不依赖任务 1/2 的新 API，但会修改 `downtime.py`（被 `estimate_internal_slot()` 间接使用）。如果任务 3 先于任务 1 实施，`estimate_internal_slot()` 尚不存在，不影响；如果任务 3 后于任务 1 实施，`occupy_resource()` 的行为变更（有序插入）会影响 `estimate_internal_slot()` 内部的时间线假设。plan 将任务 3 放在任务 2 之后执行，这意味着任务 1/2 实施时 `occupy_resource()` 仍为无序 `append`，但 `estimate_internal_slot()` 不依赖有序假设（它通过 `find_overlap_shift_end()` 全扫描）。任务 3 之后 `find_overlap_shift_end()` 可以早停，但估算器不需要改动。**依赖关系处理正确。**\n3. **任务 4 独立性**：日期来源统一可以在任何时间实施，不依赖前三个任务。但如果任务 4 在任务 2 之后实施，需要注意 `sgs.py` 的导入已被任务 2 修改。plan 将任务 4 放在任务 3 之后，此时 `sgs.py` 已被任务 2 和 3 修改过。**文件冲突风险存在但可控。**\n4. **任务 5 依赖全部**：优化器微优化依赖前四个任务的成果来做全链回归。顺序正确。\n\n### 完成判定与验收口径\n\n1. **完成判定第 9 条**：\"在本轮触达的文件与链路内，未引入新的静默回退、广域吞异常\"——这要求实施者在每个任务完成后检查所有触达文件。但 plan 的回归测试集合已经很完善，覆盖了主要链路。\n2. **完成判定第 2 条**：\"因自动分配二次选择导致的最终 (machine, operator) 对差异不计为失败\"——这承认了 `_score_internal_candidate()` 中的 `probe_only=True` 探测与正式排产时 `_schedule_internal()` 中的正式自动分配可能选出不同的 (mid, oid)。这是因为探测时不占用资源，正式排产时占用资源，导致时间线状态不同。plan 的处理正确。\n3. **完成判定第 8 条**：\"smoke_phase10 与大资源池基准在改动后都没有出现超过 30% 且未经确认的退化\"——30% 阈值是否合理取决于具体场景。对于评分升级（从近似变为精确），一定程度的耗时增长是预期内的。30% 作为\"需要暂停确认\"而非\"硬性失败\"的阈值是合理的。\n\n### 架构优雅性与简洁性评价\n\n**优点**：\n1. **职责分离清晰**：`internal_slot.py` 只做估算、`runtime_state.py` 只做状态更新、`validate_internal_hours()` 只做工时预检。每个新文件/函数的职责边界明确。\n2. **不引入新的平行模式**：plan 明确禁止\"快速估算器/精确估算器\"双模式，强制所有路径使用同一估算器。这简化了维护负担。\n3. **测试先行**：每个任务都先写失败用例，再实现，再验证。这确保了行为变更的可观测性。\n4. **暂停门槛设计合理**：每个任务都有明确的暂停条件，避免在不确定状态下继续前进。\n\n**不足/风险**：\n1. **`created_at` 严格校验在默认配置下过于激进**：详见 F8。\n2. **`ready_date` 异常上浮行为变更未充分评估影响**：详见 F5。\n3. **自动分配场景的估算重复**：详见 F4。这是一个有意识的取舍，但应在文档中更明确。\n\n### 遗漏风险\n\n1. **`ortools_bottleneck.py` 的 `_parse_due_date()` 副本**：plan 任务 4 修改列表包含 `ortools_bottleneck.py`，但步骤 3 只提到\"更新 `evaluation.py`、`dispatch_rules.py`、`ortools_bottleneck.py`\"。需确认 `ortools_bottleneck.py:23-36` 的 `_parse_due_date()` 也会被替换为共享导入。\n2. **`sgs.py` 导入清理**：plan 任务 2 步骤 3.6 说\"导入清理：`parse_required_float` 最终应从 `sgs.py` 导入列表删除\"。但如果任务 2 在任务 4 之前完成，`parse_optional_date` 仍需要保留（给 `_parse_date()` 使用）。直到任务 4 将 `_parse_date()` 替换为 `date_parsers.py` 的共享导入后，`parse_optional_date` 才能从 `sgs.py` 中移除。**导入清理的时序需要谨慎。**\n3. **`scheduler.py` 导入路径变更**：当前 `scheduler.py` 通过 `schedule_params.py` 转导出 `parse_date` 和 `parse_datetime`。任务 4 要切断这条路径，改为直接从 `date_parsers.py` 导入。但 `schedule_params.py` 自身仍使用 `parse_date` 和 `parse_datetime`（第 15 行），不受影响。**变更范围可控。**",
      "conclusionMarkdown": "### 任务间依赖与执行顺序 1. **任务 1 → 任务 2**：任务 2 的 `_score_internal_candidate()` 依赖任务 1 新建的 `estimate_internal_slot()` 和 `validate_internal_hours()`。顺序依赖正确。plan 在任务 2 步骤 2 的预期失败原因中也明确了这一点。 2. **任务 3 独立性**：时间线有序化和运行期状态收口不依赖任务 1/2 的新 API，但会修改 `downtime.py`（被 `estimate_internal_slot()` 间接使用）。如果任务 3 先于任务 1 实施，`estimate_internal_slot()` 尚不存在，不影响；如果任务 3 后于任务 1 实施，`occupy_resource()` 的行为变更（有序插入）会影响 `estimate_internal_slot()` 内部的时间线假设。plan 将任务 3 放在任务 2 之后执行，这意味着任务 1/2 实施时 `occupy_resource()` 仍为无序 `append`，但 `estimate_internal_slot()` 不依赖有序假设（它通过 `find_overlap_shift_end()` 全扫描）。任务 3 之后 `find_overlap_shift_end()` 可以早停，但估算器不需要改动。**依赖关系处理正确。** 3. **任务 4 独立性**：日期来源统一可以在任何时间实施，不依赖前三个任务。但如果任务 4 在任务 2 之后实施，需要注意 `sgs.py` 的导入已被任务 2 修改。plan 将任务 4 放在任务 3 之后，此时 `sgs.py` 已被任务 2 和 3 修改过。**文件冲突风险存在但可控。** 4. **任务 5 依赖全部**：优化器微优化依赖前四个任务的成果来做全链回归。顺序正确。 ### 完成判定与验收口径 1. **完成判定第 9 条**：\"在本轮触达的文件与链路内，未引入新的静默回退、广域吞异常\"——这要求实施者在每个任务完成后检查所有触达文件。但 plan 的回归测试集合已经很完善，覆盖了主要链路。 2. **完成判定第 2 条**：\"因自动分配二次选择导致的最终 (machine, operator) 对差异不计为失败\"——这承认了 `_score_internal_candidate()` 中的 `probe_only=True` 探测与正式排产时 `_schedule_internal()` 中的正式自动分配可能选出不同的 (mid, oid)。这是因为探测时不占用资源，正式排产时占用资源，导致时间线状态不同。plan 的处理正确。 3. **完成判定第 8 条**：\"smoke_phase10 与大资源池基准在改动后都没有出现超过 30% 且未经确认的退化\"——30% 阈值是否合理取决于具体场景。对于评分升级（从近似变为精确），一定程度的耗时增长是预期内的。30% 作为\"需要暂停确认\"而非\"硬性失败\"的阈值是合理的。 ### 架构优雅性与简洁性评价 **优点**： 1. **职责分离清晰**：`internal_slot.py` 只做估算、`runtime_state.py` 只做状态更新、`validate_internal_hours()` 只做工时预检。每个新文件/函数的职责边界明确。 2. **不引入新的平行模式**：plan 明确禁止\"快速估算器/精确估算器\"双模式，强制所有路径使用同一估算器。这简化了维护负担。 3. **测试先行**：每个任务都先写失败用例，再实现，再验证。这确保了行为变更的可观测性。 4. **暂停门槛设计合理**：每个任务都有明确的暂停条件，避免在不确定状态下继续前进。 **不足/风险**： 1. **`created_at` 严格校验在默认配置下过于激进**：详见 F8。 2. **`ready_date` 异常上浮行为变更未充分评估影响**：详见 F5。 3. **自动分配场景的估算重复**：详见 F4。这是一个有意识的取舍，但应在文档中更明确。 ### 遗漏风险 1. **`ortools_bottleneck.py` 的 `_parse_due_date()` 副本**：plan 任务 4 修改列表包含 `ortools_bottleneck.py`，但步骤 3 只提到\"更新 `evaluation.py`、`dispatch_rules.py`、`ortools_bottleneck.py`\"。需确认 `ortools_bottleneck.py:23-36` 的 `_parse_due_date()` 也会被替换为共享导入。 2. **`sgs.py` 导入清理**：plan 任务 2 步骤 3.6 说\"导入清理：`parse_required_float` 最终应从 `sgs.py` 导入列表删除\"。但如果任务 2 在任务 4 之前完成，`parse_optional_date` 仍需要保留（给 `_parse_date()` 使用）。直到任务 4 将 `_parse_date()` 替换为 `date_parsers.py` 的共享导入后，`parse_optional_date` 才能从 `sgs.py` 中移除。**导入清理的时序需要谨慎。** 3. **`scheduler.py` 导入路径变更**：当前 `scheduler.py` 通过 `schedule_params.py` 转导出 `parse_date` 和 `parse_datetime`。任务 4 要切断这条路径，改为直接从 `date_parsers.py` 导入。但 `schedule_params.py` 自身仍使用 `parse_date` 和 `parse_datetime`（第 15 行），不受影响。**变更范围可控。**",
      "evidence": [],
      "reviewedModules": [
        "任务间依赖与顺序",
        "完成判定与验收口径",
        "架构优雅性与简洁性",
        "遗漏风险"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F8-CREATED-AT-OVERSTRICT",
        "F9-EXPOSED-EXCEPTION-RISK"
      ]
    }
  ],
  "findings": [
    {
      "id": "F1-LINE-DRIFT",
      "severity": "low",
      "category": "docs",
      "title": "sgs.py 评分族范围少写一行",
      "descriptionMarkdown": "plan 引用 sgs.py:278-340 为近似评分族范围，但 change_pen 赋值实际在第 341 行才结束，plan 遗漏了边界行。对实施无实际影响。",
      "recommendationMarkdown": "将引用范围调整为 278-341。",
      "evidence": [],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F2-PARSE-DATE-DOUBLE",
      "severity": "low",
      "category": "javascript",
      "title": "schedule_optimizer.py _parse_date 非严格模式双重解析",
      "descriptionMarkdown": "schedule_optimizer.py:337-341 非严格模式下先调用 parse_optional_date() 再 except 回退为 None，本质是多余的双重解析。plan 任务 4 已正确识别此问题并计划修复。",
      "recommendationMarkdown": "确认任务 4 实施时一并清理。",
      "evidence": [],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F3-READY-DATE-FIELD-BUG",
      "severity": "high",
      "category": "javascript",
      "title": "schedule_optimizer ready_date 严格模式报错字段名错误",
      "descriptionMarkdown": "schedule_optimizer.py:335-341 的 `_parse_date()` 硬编码 `field=\"due_date\"`，但被同时用于解析 `due_date`（行 365）和 `ready_date`（行 367）。这意味着在严格模式下，坏 `ready_date` 会抛出 `ValidationError(field=\"due_date\")`，错误文案指向了错误字段。\n\nplan 任务 4 暂停条件已覆盖此问题（\"schedule_optimizer.py 解析坏 ready_date 仍以 due_date 名义报错\"），但 plan 步骤本身没有在\"要做什么\"层面明确说\"分别构造 `_parse_due_date()` 和 `_parse_ready_date()` 两个带正确字段名的包装函数\"。实施者可能仅清理 `_parse_date()` 为统一导入后仍漏掉 `field` 参数的差异化。",
      "recommendationMarkdown": "任务 4 步骤 4 应在正文中明确要求 `ready_date` 调用 `parse_optional_date(value, field=\"ready_date\")` 而非复用 `field=\"due_date\"` 的包装。这不仅是暂停条件，也应是显式实施步骤。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 335,
          "lineEnd": 341,
          "symbol": "_parse_date"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 365,
          "lineEnd": 367
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
      "id": "F4-DOUBLE-ESTIMATE",
      "severity": "medium",
      "category": "performance",
      "title": "sgs 评分升级后自动分配场景估算重复",
      "descriptionMarkdown": "任务 2 将 sgs 评分中的顺序链式近似替换为三路时间线同时避让估算。这意味着：\n\n1. **每个候选对都执行完整避让循环**：当前的 `find_earliest_available_start()` 是 O(n) 线性扫描，而 `estimate_internal_slot()` 是一个 while 循环，每次迭代要检查三路时间线的重叠。\n2. **自动分配场景存在重复计算**：`probe_only=True` 的自动分配已经在 `auto_assign_internal_resources()` 中做过完整三路避让；之后 `_score_internal_candidate()` 又拿到返回的 `(mid, oid)` 再做一次 `estimate_internal_slot()`，相当于同一对设备人员被估算两次。plan 明确不做第 11 项承认了此重复。\n3. **大资源池加倍效应**：设 M 台设备、O 个操作员，当前自动分配评估 M×O 对各做一次避让循环，任务 2 后又额外做一次——总估算次数从 M×O 变为 2×M×O。\n\nplan 已设置 30% 退化阈值与基准测试，但应在实施说明中明确标注此已知重复源，避免基准测试通过后被遗忘。",
      "recommendationMarkdown": "在 plan 的\"明确不做\"列表中补充说明：由于自动分配返回值未扩展，sgs 评分阶段对自动分配候选存在一次估算重复，这是本轮已知的性能取舍。",
      "evidence": [],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F5-READY-DATE-EXCEPTION-RISK",
      "severity": "medium",
      "category": "javascript",
      "title": "ready_date 下界调整异常上浮可能导致非预期排产中断",
      "descriptionMarkdown": "scheduler.py:232-236 的 `ready_date` 下界调整：\n```python\ntry:\n    dt_ready = self.calendar.adjust_to_working_time(dt0, priority=p)\nexcept Exception:\n    dt_ready = dt0\n```\nplan 任务 4 步骤 4.5 要求\"异常直接上浮\"。但 `adjust_to_working_time()` 抛异常的可能原因包括：\n- 日历数据缺失或损坏\n- `priority` 值不合法\n- 内部日期算术溢出\n\n如果直接上浮，一个坏优先级值就会导致整个排产失败，而当前行为是降级使用午夜零点。plan 没有区分\"日历服务程序错误\"与\"日历数据配置错误\"两种失败类型。\n\n此外，`schedule_optimizer.py` 中构造 `BatchForSort` 时也用 `_parse_date()` 处理 `ready_date`，但那里的 `ready_date` 只用于排序，不直接作为时间线下界。这两处的行为变更需要分别验证。",
      "recommendationMarkdown": "建议在实施说明中明确：仅当 `adjust_to_working_time()` 收到合法 `date` 类型入参时才允许上浮异常；若调用方传入的已经是合法日期，则 `adjust_to_working_time()` 的内部异常确实应被视为不可忽略的程序错误。但需要在回归测试中覆盖\"日历服务暂时不可用\"的场景，确认上浮后的失败消息可读。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 230,
          "lineEnd": 237
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
      "id": "F6-UPPER-BOUND-LARGE-SEED",
      "severity": "low",
      "category": "javascript",
      "title": "统一估算器在大量 seed 碎片场景下的上界可能过大",
      "descriptionMarkdown": "plan 任务 1 要求避让上界为 `len(machine_timeline[mid]) + len(operator_timeline[oid]) + len(downtime_segments) + 1`。但在 `auto_assign_internal_resources()` 中，每个候选对 `(mid, oid)` 拥有不同的时间线长度。如果 `estimate_internal_slot()` 在入口处一次性计算上界，那么在同一次 `auto_assign` 调用中，不同候选对的上界不同是正确的。\n\n但 `_schedule_internal()` 在调用 `estimate_internal_slot()` 之前已经确定了唯一的 `(machine_id, operator_id)`，所以这里只有一次计算。\n\n**潜在 BUG**：如果 `occupy_resource()` 在 seed 预热阶段向时间线添加了大量碎片段（例如来自上一轮冻结窗口的上百个 seed 结果），而估算器的上界基于时间线当前大小计算，则上界值会很大。在极端场景下（1000 个 seed + 大量停机段），while 循环可能执行上千次迭代。这虽然不会死循环（因为有上界），但可能导致单次估算耗时较长。plan 的基准测试应覆盖此场景。",
      "recommendationMarkdown": "在 `benchmark_sgs_large_resource_pool.py` 中补充\"大量 seed 结果导致时间线碎片化\"的场景，验证估算器在此情况下的耗时。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 510,
          "lineEnd": 543
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
      "id": "F7-SHAKE-RESET-CLARITY",
      "severity": "low",
      "category": "javascript",
      "title": "局部搜索 shake 后 seen_hashes 重置的语义需明确",
      "descriptionMarkdown": "plan 任务 5 步骤 4 要求 `_run_local_search()` 在 shake 后\"允许做轻量重置（清空后立即写回当前 cur_order，并补写 tuple(best.get('order', []))）\"。但 shake 本身就是从 `best['order']` 出发做随机扰动（schedule_optimizer.py:247）。shake 后 `cur_order` 已经是 `best['order']` 的变体。如果清空 `seen_hashes` 后立即写回 `cur_order` 和 `best['order']`，实际上只预热了两个点，接下来的邻域搜索可能会重新尝试 shake 前已经尝试过且失败的邻域。\n\n这不是 BUG（plan 明确允许\"轻量重置\"），但可能降低搜索效率。更优的做法是保留 `best['order']` 和 `cur_order` 在 `seen_hashes` 中，其余全部清空。plan 当前描述恰好就是这个做法。但实施时需注意 shake 后 `cur_order` 与 shake 前的 `cur_order` 不同，不需要保留旧的 `cur_order`。",
      "recommendationMarkdown": "实施时确认：shake 后的 seen_hashes 只需保留 shake 后的 cur_order 与 best['order']，不需要保留 shake 前的旧 cur_order。plan 文字表述已正确。",
      "evidence": [],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F8-CREATED-AT-OVERSTRICT",
      "severity": "medium",
      "category": "javascript",
      "title": "created_at 严格校验在默认配置下过于激进",
      "descriptionMarkdown": "plan 任务 4 要求在 `optimize_schedule()` 中检查候选策略集合是否包含 FIFO，只在包含时才对 `created_at` 做严格校验。但 `valid_strategies` 默认值为 `(\"priority_first\", \"due_date_first\", \"weighted\", \"fifo\")`（schedule_optimizer.py:392），即默认总是包含 `fifo`。\n\n这意味着：只要用户没有显式配置将 `fifo` 从候选集中移除，严格模式下坏 `created_at` 就会导致排产失败，即使用户实际选择的是 `priority_first` 策略。这与 plan 任务 4 的意图（\"仅在 FIFO 相关排序路径真正消费该字段时才允许 strict 硬失败\"）矛盾。\n\nplan 的意图是“当前候选策略集合会实际构造 FIFO 排序”，但“默认包含 fifo”与“实际构造 fifo 排序”是两码事。需要明确：是按\"候选集合是否包含 fifo\"还是按\"当前轮次实际构造了 fifo 排序器\"来决定是否对 created_at 做 strict 校验。",
      "recommendationMarkdown": "建议采用更保守的判断逻辑：只有当当前轮次实际会用 fifo 策略构造排序器时，才对 created_at 做 strict 校验。具体做法：在 `batch_for_sort` 构造循环之前，检查 `keys`（而非 `valid_strategies`）是否包含 `\"fifo\"`。在 `algo_mode == \"improve\"` 模式下 `keys` 包含所有 `valid_strategies`，但在非 improve 模式下 `keys = [current_key]`，只包含用户实际选择的策略。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 392,
          "lineEnd": 392
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 359,
          "lineEnd": 370
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
      "id": "F9-EXPOSED-EXCEPTION-RISK",
      "severity": "low",
      "category": "maintainability",
      "title": "移除广域吞异常后 seed 预热可能暴露新异常",
      "descriptionMarkdown": "plan 的完成判定第 9 条写道：\"在本轮触达的文件与链路内，未引入新的静默回退、广域吞异常、平行估算路径或新的算法模式\"。但 plan 任务 3 是移除现有的广域吞异常（batch_order.py:102、sgs.py:470、scheduler.py:296），这意味着实施后这些位置可能暴露之前被静默吞掉的异常。\n\nscheduler.py:290-297 的 seed 预热忙时统计也有一个 `except Exception: pass`。如果任务 3 把这个也移除（plan 明确要求\"seed 预热阶段三处运行期状态更新收口到 runtime_state.py\"，且\"共享函数内部没有广域吞异常\"），那么 seed 结果中的 `end_time - start_time` 如果出现类型错误（比如 `start_time` 为 `None` 但通过了前置检查），就会直接抛异常而不是被静默跳过。这是正确的行为，但需要确保回归测试覆盖此场景。",
      "recommendationMarkdown": "任务 3 的回归列表中应明确包含 `regression_seed_results_freeze_missing_resource.py`、`regression_seed_results_dedup.py`，并在实施时特别关注 seed 预热中 `h = (sr.end_time - sr.start_time).total_seconds() / 3600.0` 这行是否会因异常类型不再被吞掉而导致新的失败。plan 已在回归列表中列出了这些测试，符合预期。",
      "evidence": [],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:6e909790dbdb04a81285a555f2f8ec175306f500d0d6056796feedf0a9480e1a",
    "generatedAt": "2026-04-07T14:31:26.269Z",
    "locale": "zh-CN"
  }
}
```
