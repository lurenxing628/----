# 算法层统一估算与派工重构plan三轮深度审查
- 日期: 2026-04-07
- 概述: 对算法层统一估算与派工重构plan进行三轮深度审查：第一轮核验代码前提与引用链，第二轮审查实施步骤逻辑严谨性，第三轮检查遗漏与潜在BUG
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# 算法层统一估算与派工重构 plan 三轮深度审查

**审查日期**: 2025-04-09
**审查对象**: `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`

## 审查范围
- 第一轮：核验 plan 中所有代码前提与引用链是否与当前代码一致
- 第二轮：审查实施步骤的逻辑严谨性、是否有静默回退、过度兜底
- 第三轮：检查遗漏、潜在BUG、边界条件与优雅性评估

## 评审摘要

- 当前状态: 已完成
- 已审模块: core/algorithms/greedy/scheduler.py, core/algorithms/greedy/auto_assign.py, core/algorithms/greedy/dispatch/sgs.py, core/algorithms/greedy/dispatch/batch_order.py, core/algorithms/greedy/downtime.py, core/algorithms/greedy/date_parsers.py, core/algorithms/evaluation.py, core/algorithms/dispatch_rules.py, core/algorithms/ortools_bottleneck.py, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_optimizer_steps.py, core/services/common/strict_parse.py, core/algorithms/sort_strategies.py, core/algorithms/greedy/schedule_params.py
- 当前进度: 已记录 3 个里程碑；最新：M3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 10
- 问题严重级别分布: 高 1 / 中 5 / 低 4
- 最新结论: ## 三轮深度审查总结 ### 总体评价 这是一份**质量极高的重构 plan**。经过三轮深入审查，共核验了 13 个代码库中的核心文件、13 条修订前提、6 节引用链总览以及 5 个任务的全部实施步骤。 **能否达成目的**：✅ 可以达成。plan 准确识别了当前代码的核心问题（三套独立估算逻辑、固定 200 次硬上限、广域吞异常、日期解析副本散落），并提出了清晰可行的统一方案。 **实现是否优雅简洁**：✅ 设计非常干净。`internal_slot.py`（纯估算）+ `runtime_state.py`（纯状态更新）+ 编排层 + 评分层的四层职责分离消除了现有的高度耦合，且不引入新的抽象膨胀。 **是否存在过度兜底或静默回退**：✅ plan 系统性地清除了 `or 1.0` 隐式效率回退、`except Exception: eff = 1.0` 广域吞错、`candidates[0]` 死代码兜底、双层 try/except 自动分配探测吞错等问题，替换为显式的 `raw_eff is not None` 判断和明确的业务不可估算分支。 **逻辑是否严谨**：✅ 整体严谨。避让上界公式 `N_machine + N_operator + N_downtime + 1` 的数学论证成立；`validate_internal_hours()` 的空值兼容边界与当前行为完全一致；评分阶段"先验工时 → 再探资源 → 后估时段"的固定顺序杜绝了根因混淆。 ### 发现的 10 个问题 | 级别 | 数量 | 关键项 | |------|------|--------| | 高 | 1 | F2: `optimize_schedule` 中 `_parse_date` 误用 `field="due_date"` 解析 `ready_date`（已有 BUG，任务 4 修复） | | 中 | 5 | F1: `cutoff_exceeded` 字段与约束矛盾；F3: 探测形状校验冗余；F4: seed/派工状态语义差异回归缺用例；F6: 部分提交窗口回归覆盖不足；F9: `blocked_by_window` 处理流程缺失 | | 低 | 4 | F5/F7/F8/F10: 均为实施细节澄清或优化建议 | ### 需要在实施前修改 plan 的建议 1. **必须修改**：解决 F1 `cutoff_exceeded` 字段矛盾（删除字段或改为返回值语义） 2. **必须修改**：在任务 1 步骤 4 中显式列出 `blocked_by_window` 的处理流程（F9） 3. **建议修改**：在任务 4 回归用例中补充"seed 预热中非空 `op_type_name` 但 `end_time <= prev_end` 时不覆盖"的场景（F4） 4. **建议标注**：任务 1~3 的严格模式回归若涉及 `ready_date` 解析，需预期标注 F2 为已知问题（F2）
- 下一步建议: 修改 plan 中 F1（cutoff_exceeded 字段矛盾）和 F9（blocked_by_window 处理流程缺失）两个必须项，补充 F4 的回归用例后即可进入实施
- 总体结论: 有条件通过

## 评审发现

### InternalSlotEstimate 中 cutoff_exceeded 字段与约束矛盾

- ID: F1
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  plan 任务 1 步骤 3 定义 InternalSlotEstimate 包含 cutoff_exceeded 字段，但实施约束同时写道'若仍越过这条可证明上界，应视为实现错误直接暴露，而不是静默转成业务失败'。这两条要求互相矛盾：如果越过动态上界直接抛实现错误，那么 cutoff_exceeded 字段永远不会为 True，这个字段就是死字段。然而任务 1 步骤 4 又在 auto_assign 中写了 'cutoff_exceeded=True 时直接跳过当前组合'，暗示它是一个正常的返回值。

  建议：要么删除 cutoff_exceeded 字段（因为实现错误不会返回而是抛出），要么把'越过上界'从'实现错误'降级为'估算失败'并通过 cutoff_exceeded 返回；两者取其一即可，不要两种语义并存。
- 建议:

  删除 InternalSlotEstimate 的 cutoff_exceeded 字段，越过动态上界直接抛 RuntimeError；或保留 cutoff_exceeded 字段但不抛异常，通过返回值让调用方决策。
- 证据:
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`

### optimize_schedule 中 _parse_date 误用 field="due_date" 解析 ready_date

- ID: F2
- 严重级别: 高
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  当前 optimize_schedule() 行 367 对 ready_date 使用 _parse_date()，而 _parse_date()（行 335-341）硬编码了 field="due_date"。在严格模式下，一个格式错误的 ready_date 会以 field="due_date" 的名义抛出 ValidationError，造成误导性错误信息。plan 任务 4 步骤 4 已正确识别此问题并要求拆分为 _parse_due_date() 和 _parse_ready_date()，但该 BUG 在任务依赖链中排在任务 4 才修复，而任务 1~3 的回归验证可能先在严格模式下触发此 BUG。建议在任务 1 结束后就先确认严格模式回归是否涉及 ready_date 解析。
- 建议:

  若任务 1~3 的严格模式回归路径涉及 ready_date 解析（如 regression_schedule_input_builder_strict_hours_and_ext_days.py），应在任务 4 之前提前对此做预期标注，避免中途被误判为新引入 BUG。
- 证据:
  - `core/services/scheduler/schedule_optimizer.py:335-370#_parse_date`
  - `core/services/scheduler/schedule_optimizer.py`

### sgs.py 自动分配探测双层广域吞异常与返回形状校验冗余

- ID: F3
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  sgs.py 行 232-263 的自动分配探测有两层 try/except，且内层（行 252-260）既检查 chosen 是否为 tuple/list 且 len>=2，又用 except Exception 吞掉校验失败。plan 任务 2 正确要求删除这种双层吞异常。但 plan 步骤 3 对 _score_internal_candidate() 的描述中只说'chosen is None 是唯一允许的正常缺资源分支'，未明确说明当 auto_assign 返回类型不是 Optional[Tuple[str,str]] 时的处理方式。

  实际上，auto_assign_internal_resources() 的返回类型签名是 Optional[Tuple[str, str]]，所以非 None 返回一定是 (str, str) 元组。内层的形状检查是多余的防御代码。
- 建议:

  重构后的 _score_internal_candidate() 直接信任 auto_assign_internal_resources() 的返回类型契约：如果非 None 就解包为 (machine_id, operator_id)，不做冗余形状检查。如果返回类型违约，让 Python 的解包错误自然暴露。
- 证据:
  - `core/algorithms/greedy/dispatch/sgs.py:232-263#dispatch_sgs`
  - `core/algorithms/greedy/dispatch/sgs.py`

### sgs.py 派工成功后 last_op_type 与 seed 预热语义不一致需显式标注

- ID: F4
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  seed 预热（scheduler.py:299-304）中 last_op_type_by_machine 仅在 end_time > prev_end 时才条件更新；而派工成功路径（sgs.py:473-475、batch_order.py:104-106）中 last_op_type_by_machine 是非空时无条件覆盖。plan 任务 3 步骤 4 已识别此差异并要求通过 conditional_op_type=True/False 两种模式区分。

  但 plan 中的回归测试步骤 1 中虽然写了'seed 预热遇到空 op_type_name 时不推进'和'派工成功模式下 last_op_type 保持直接更新'两条用例，却没有写一条覆盖'seed 预热中非空 op_type_name 但 end_time <= prev_end 时不覆盖'这个真正的语义差异点。这是 seed 模式最核心的区别行为。
- 建议:

  在 tests/regression_downtime_timeline_ordered_insert.py 或同组回归中补一条用例：构造两条同设备 seed 结果，后一条 end_time 早于前一条，断言 last_op_type_by_machine 仍保持第一条的工种名而非被第二条覆盖。
- 证据:
  - `core/algorithms/greedy/scheduler.py:299-304#schedule`
  - `core/algorithms/greedy/dispatch/sgs.py:473-475#dispatch_sgs`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/dispatch/sgs.py`

### 避让上界公式中停机片段数的计算时机需澄清

- ID: F5
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  plan 要求避让上界在 estimate_internal_slot() '每次调用入口' 按当前片段数现算：len(machine_timeline[mid]) + len(operator_timeline[oid]) + len(downtime_segments) + 1。但 downtime_segments 指的是 machine_downtimes.get(machine_id)，这个列表在同一次排产调用中不会变化（停机信息是输入，不会被 occupy_resource 修改）；而 machine_timeline[mid] 和 operator_timeline[oid] 会在每次 occupy_resource 后增长。

  因此上界确实需要在每次 estimate 调用入口现算，否则用缓存的旧值会低估。plan 对此的要求是正确的，但实施时要注意：如果使用的是引用（list 引用），len() 总是会拿到当前值；只有当拷贝了 timeline 快照时才需要特别注意。
- 建议:

  实施时直接对传入的 machine_timeline[mid] 和 operator_timeline[oid] 引用调用 len()，不要在入口做快照拷贝。
- 证据:
  - `core/algorithms/greedy/scheduler.py:510-536`
  - `core/algorithms/greedy/scheduler.py`

### 部分提交窗口在 batch_order.py 中同样存在

- ID: F6
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  plan 任务 3 详细分析了 sgs.py 的部分提交问题（results.append 之后的状态更新被 try/except 包裹），但 batch_order.py:86-106 有完全相同的结构：先 results.append(result)，然后 try/except 包裹 busy_hours 更新。plan 步骤 4 列出了 batch_order.py:90-106 作为需要改造的位置，但回归测试步骤 1 第 7 条'共享状态更新不会留下已追加 results 的部分提交'的用例只泛泛提及，没有明确要求分别覆盖 batch_order 和 sgs 两条路径。
- 建议:

  在 regression_downtime_timeline_ordered_insert.py 的部分提交用例中，同时覆盖 batch_order 和 sgs 两条派工路径，确保两条路径的状态更新都已经收口到共享函数。
- 证据:
  - `core/algorithms/greedy/dispatch/batch_order.py:86-106#dispatch_batch_order`
  - `core/algorithms/greedy/dispatch/batch_order.py`

### 本地搜索去重后 no_improve 计数语义需精确定义

- ID: F7
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  plan 任务 5 步骤 4 要求：重复邻域跳过后'必须继续推进用于触发 restart_after 的停滞计数'。当前代码中 no_improve 仅在 score >= best["score"] 时递增。但引入去重后，被跳过的重复邻域既没有评估 score，也不算改善。plan 要求把跳过也计入停滞。

  但这会引入一个微妙的语义变化：原来 no_improve 是'连续未改善的已评估尝试数'，现在变成'连续未改善的迭代数（含跳过）'。如果搜索空间小且重复率高，shake 会被更频繁地触发。这不是 BUG，但应在回归测试中用小规模场景验证 shake 不会过于频繁导致搜索退化。
- 建议:

  regression_optimizer_local_search_neighbor_dedup.py 中的小规模场景测试应验证：高重复率场景下 shake 频率与改善效果的平衡，确保不会因为过度 shake 导致搜索空间浪费。
- 证据:
  - `core/services/scheduler/schedule_optimizer.py:139-261#_run_local_search`
  - `core/services/scheduler/schedule_optimizer.py`

### estimate_internal_slot 参数列表缺 priority

- ID: F8
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  plan 任务 1 步骤 3 的 estimate_internal_slot() 参数列表中没有显式包含 priority 参数，但估算器内部需要调用 calendar.adjust_to_working_time(earliest, priority=priority, operator_id=operator_id) 和 calendar.add_working_hours(earliest, total_hours, priority=priority, operator_id=operator_id)。当前设计是通过 getattr(batch, 'priority', None) 从 batch 参数中提取，但这让估算器依赖 batch 对象的属性结构。

  这不是 BUG（与当前行为一致），但作为一个纯估算函数，显式接收 priority 参数会更简洁。
- 建议:

  建议在 estimate_internal_slot() 参数列表中显式加入 priority: Optional[str] = None，避免估算器内部做 getattr(batch, 'priority', None)。
- 证据:
  - `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`

### 任务 1 步骤 4 缺 blocked_by_window 的显式处理流程

- ID: F9
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  plan 任务 1 步骤 4 要求 _schedule_internal() '用 InternalSlotEstimate 组装 ScheduleResult'，但没有明确说明当 estimate_internal_slot() 成功返回后，调用方是否仍然需要检查 blocked_by_window。

  当前代码中，_schedule_internal() 在 end >= end_dt_exclusive 时返回 (None, True)（blocked_by_window=True）。如果估算器返回 InternalSlotEstimate 且 blocked_by_window=True，调用方必须显式检查并返回 (None, True)。plan 任务 1 步骤 4 对此只写了'若 efficiency_fallback_used=True 更新计数器'，没有明确列出 blocked_by_window 的处理逻辑。
- 建议:

  在任务 1 步骤 4 的描述中显式加入：若 estimate.blocked_by_window 为 True，组装超窗口错误信息并返回 (None, True)；否则继续 occupy_resource 并组装 ScheduleResult。
- 证据:
  - `core/algorithms/greedy/scheduler.py:538-543#_schedule_internal`
  - `core/algorithms/greedy/scheduler.py`

### 自动分配場景下的已知重复估算需保证一致性

- ID: F10
- 严重级别: 低
- 分类: 性能
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  plan 中明确说明了自动分配场景下保留一次已知重复估算（明确不做第 11 项）。auto_assign_internal_resources() 完成后找到最优 (machine_id, operator_id)，然后 _schedule_internal() 还会再次调用 estimate_internal_slot() 做一次相同的估算。

  这是正确的设计权衡。如果要消除这次重复，需要让 auto_assign 返回完整的 InternalSlotEstimate 而不是只返回 (machine_id, operator_id)，但 plan 正确地把这推迟到未来轮次。只是实施时应确保重复估算的结果与 auto_assign 内部估算的结果一致（同一估算器、同样的时间线状态）。
- 建议:

  实施时确保 auto_assign 内部的 estimate_internal_slot() 与后续 _schedule_internal() 中的调用接收的是同一引用的 machine_timeline / operator_timeline，这样两次估算结果才会一致。
- 证据:
  - `core/algorithms/greedy/scheduler.py:564-596#_auto_assign_internal_resources`
  - `core/algorithms/greedy/scheduler.py`

## 评审里程碑

### M1 · 第一轮：代码前提与引用链核验

- 状态: 已完成
- 记录时间: 2026-04-07T16:04:44.725Z
- 已审模块: core/algorithms/greedy/scheduler.py, core/algorithms/greedy/auto_assign.py, core/algorithms/greedy/dispatch/sgs.py, core/algorithms/greedy/dispatch/batch_order.py, core/algorithms/greedy/downtime.py, core/algorithms/greedy/date_parsers.py, core/algorithms/evaluation.py, core/algorithms/dispatch_rules.py, core/algorithms/ortools_bottleneck.py, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_optimizer_steps.py, core/services/common/strict_parse.py, core/algorithms/sort_strategies.py
- 摘要:

  逐条核验了 plan 中 13 条修订前提与 6 节引用链总览，均与当前代码实际状态一致。

  ### 前提核验结果

  1. **前提 1（主链路径）**：✅ 已确认 `ScheduleService._run_schedule_impl()` → `collect_schedule_run_input()` → `orchestrate_schedule_run()` → `optimize_schedule()` → `_run_ortools_warmstart()` / `_run_multi_start()` / `_run_local_search()` → `_schedule_with_optional_strict_mode()` → `GreedyScheduler.schedule()` 链路与 plan 描述一致。

  2. **前提 2（两套估算族）**：✅ `scheduler.py:469-543` 与 `auto_assign.py:156-223` 确实都使用"三条时间线同时检查并反复避让"的循环；`sgs.py:278-341` 使用 `find_earliest_available_start()` 的顺序链式近似。两者确实不是同一算法。

  3. **前提 3（input_builder 规范化）**：✅ 行号引用准确，`setup_hours`、`unit_hours` 已在服务层规范化为数值。

  4. **前提 4（`__init__.py` 导出 `GreedyScheduler`）**：✅ `core/algorithms/__init__.py:13` 确实导出 `GreedyScheduler`。

  5. **前提 5（两类日期解析器语义不同）**：✅ `sgs.py:18-24` 的 `_parse_date()` 在 `strict_mode=True` 时会抛 `ValidationError`；`date_parsers.py:7-41` 永不抛异常。plan 正确指出不能机械合并。

  6. **前提 6（缺共享严格日期时间解析）**：✅ `strict_parse.py` 只有 `parse_required_date` 和 `parse_optional_date`，没有日期时间版本。`schedule_optimizer.py:343-357` 的 `_parse_datetime()` 确实是本地非严格实现。

  7. **前提 7（seed 预热也维护运行期状态）**：✅ `scheduler.py:289-304` 确实更新 `machine_busy_hours`、`operator_busy_hours`、`last_end_by_machine`、`last_op_type_by_machine`。

  8. **前提 8（`guard < 200` 硬上限）**：✅ `scheduler.py:513` 和 `auto_assign.py:185` 都使用 `while guard < 200`。

  9. **前提 9（`or 1.0` 隐式布尔回退）**：✅ `scheduler.py:494` 使用 `or 1.0`；`sgs.py:323` 也使用 `or 1.0`；`auto_assign.py:166-169` 使用 `raw_eff is not None` 但外层仍有 `except Exception: eff = 1.0`。

  10. **前提 10（`schedule_summary.py` 不在热路径）**：✅ plan 正确不扩到此处。

  11. **前提 11（`created_at` 只被 FIFO 消费）**：✅ `sort_strategies.py:117-125` 的 `FIFOStrategy.sort()` 是唯一消费 `batch.created_at` 的地方。

  12. **前提 12（`schedule_params.py` 静默吞错）**：✅ `schedule_params.py:45-54` 的 `_critical_config_read()` 在 `strict_mode=False` 时 `warnings.append(...)` 并回退到默认值，不抛异常。

  13. **前提 13（`getattr(..., 0) or 0` 的空值兼容边界）**：✅ `scheduler.py:476-480` 和 `auto_assign.py:102-106` 都使用 `getattr(op, "setup_hours", 0) or 0`，`sgs.py:91-99` 用 `parse_required_float()`，边界确实不同。

  ### 引用链核验结论

  - `scheduler.py` 的 `_parse_date` / `_parse_datetime` 是从 `schedule_params.py` 转导出，后者实际从 `date_parsers.py` 导入。plan 任务 4 要求 `scheduler.py` 直接从 `date_parsers.py` / `strict_parse.py` 导入，这是正确的简化方向。
  - `optimize_schedule()` 中 `batch_for_sort` 构造（行 359-370）先于 `valid_strategies` / `keys` 确定（行 392-401），这与 plan 前提的分析一致。
  - `_run_multi_start()` 中 `order = build_order(strat, params0)` 在 `dispatch_rules` 内层循环中（行 334），确实会因不同 `dr` 重复构造相同 `order`。
  - `_run_local_search()` 中确实没有邻域去重逻辑（行 139-261）。
- 结论:

  plan 中 13 条修订前提和 6 节引用链总览全部与当前代码一致，行号引用精确，未发现前提失实。
- 证据:
  - `core/algorithms/greedy/scheduler.py:469-543#_schedule_internal`
  - `core/algorithms/greedy/auto_assign.py:96-230#auto_assign_internal_resources`
  - `core/algorithms/greedy/dispatch/sgs.py:278-370#dispatch_sgs`
  - `core/algorithms/greedy/downtime.py:20-28#occupy_resource`
  - `core/services/scheduler/schedule_optimizer.py:335-401#optimize_schedule`
  - `core/services/scheduler/schedule_optimizer_steps.py:306-334#_run_multi_start`
  - `core/algorithms/__init__.py:1-26`
- 下一步建议:

  进入第二轮审查：逐任务审查实施步骤的逻辑严谨性

### M2 · 第二轮：实施步骤逻辑严谨性审查

- 状态: 已完成
- 记录时间: 2026-04-07T16:07:13.268Z
- 摘要:

  逐任务深入审查了 plan 的五个任务实施步骤的逻辑严谨性，发现 7 个需要注意的问题。

  ### 任务 1 审查结论

  **避让上界公式**：`N_machine + N_operator + N_downtime + 1` 的数学论证成立。每次迭代 `earliest` 严格递增且只能停在片段端点上，因此最多迭代等于总片段数。

  **`validate_internal_hours()` 兼容性**：设计正确。`getattr(op, "setup_hours", 0) or 0` 的语义被完整保留：缺字段→0、None→0、空串→0、False→0、"bad"→ValueError。与当前 `_schedule_internal()` 和 `auto_assign_internal_resources()` 的行为一致。

  **`InternalSlotEstimate` 字段矛盾**：`cutoff_exceeded` 字段与"越过上界直接抛实现错误"的约束矛盾，是死字段。（发现 F1）

  **效率处理**：plan 正确要求去掉 `or 1.0` 隐式回退，改用 `raw_eff is not None` 显式判断。与 `auto_assign.py:166-167` 现有模式一致。

  ### 任务 2 审查结论

  **`candidates[0]` 死代码**：确认是死代码。`best_key` 在第一个候选评分完成后必定非 None（因为外层 try/except 最坏情况下也会构造硬编码 tuple），所以 `best_pair` 永远非 None。

  **`avg_proc_hours` 初始化改用 `validate_internal_hours()`**：会使采样变宽松（原来 `parse_required_float(None)` 拒绝，现在 `validate_internal_hours()` 接受为 0 但不加入 `proc_samples`——因为 `h=0` 时 `h > 0` 为 False 所以不会加入）。实际效果不变。

  **评分顺序固定**：先 validate_hours → 资源探测 → estimate_internal_slot 的设计正确，把工时坏值和缺资源两种根因彻底分开。

  ### 任务 3 审查结论

  **有序插入 Python 3.8 兼容**：`bisect.insort` 在 3.8 只支持元组自然序排序，(start, end) 元组天然按 start 升序，符合要求。

  **seed 预热与派工成功的状态语义差异**：plan 正确识别了 `conditional_op_type=True/False` 的差异，但回归用例缺少一条关键场景（发现 F4）。

  **部分提交修复**：plan 对 sgs.py 的分析完整，但 batch_order.py 的回归覆盖不够明确（发现 F6）。

  ### 任务 4 审查结论

  **`_parse_date` 误用 `field="due_date"` 解析 `ready_date`**：确认是已存在的 BUG，plan 正确识别并在任务 4 修复。但任务 1~3 的严格模式回归可能先触发此问题（发现 F2）。

  **`created_at` strict 启用判断以 `keys` 为准**：plan 正确指出 `batch_for_sort` 构造（行 359-370）先于 `keys` 确定（行 399），而当前代码对 `created_at` 的 `_parse_datetime()` 不分 strict/non-strict 都是非严格的。plan 要求前移 `keys` 计算或延迟 `created_at` 解析，设计合理。

  **`ready_date` 静默回退**：`scheduler.py:232-236` 的 `except Exception: dt_ready = dt0` 确实是静默回退，plan 正确要求去掉。

  ### 任务 5 审查结论

  **order 缓存键**：`(strategy.value, tuple(sorted(params0.items())))` 对当前的 params0 结构（空字典或 {priority_weight, due_weight}）是正确的。

  **邻域去重**：`tuple(cand_order)` 作为哈希键，对最大 5000 次迭代的规模是可接受的。shake 后清空并重写当前 + 最优，设计合理。

  **`no_improve` 语义变化**：从"未改善的已评估数"变为"未改善的迭代数含跳过"，可能导致 shake 更频繁（发现 F7）。
- 结论:

  五个任务的实施步骤整体逻辑严谨，但发现 7 个问题需要注意
- 下一步建议:

  进入第三轮审查：检查遗漏、潜在BUG与优雅性评估
- 问题:
  - [中] 可维护性: InternalSlotEstimate 中 cutoff_exceeded 字段与约束矛盾
  - [高] JavaScript: optimize_schedule 中 _parse_date 误用 field="due_date" 解析 ready_date
  - [中] 可维护性: sgs.py 自动分配探测双层广域吞异常与返回形状校验冗余
  - [中] 可维护性: sgs.py 派工成功后 last_op_type 与 seed 预热语义不一致需显式标注
  - [低] 可维护性: 避让上界公式中停机片段数的计算时机需澄清
  - [中] 可维护性: 部分提交窗口在 batch_order.py 中同样存在
  - [低] 可维护性: 本地搜索去重后 no_improve 计数语义需精确定义

### M3 · 第三轮：遗漏检查、潜在BUG与优雅性评估

- 状态: 已完成
- 记录时间: 2026-04-07T16:08:50.553Z
- 摘要:

  第三轮审查聚焦遗漏、潜在 BUG 与整体设计优雅性评估，发现 3 个额外问题。

  ### 整体设计优雅性评估

  **职责分离清晰**：plan 创建了一个干净的四层结构：
  - `internal_slot.py`：纯估算（无状态变更、无错误文案拼接）
  - `runtime_state.py`：纯状态更新（无估算、无吞异常）
  - `scheduler.py`：编排层（资源分配、结果构建、时间线占用）
  - `sgs.py`：评分与选择（调用估算器获取真实评分）

  这是对当前高度耦合代码的重大改善。每个模块职责单一，不存在越界。

  **无过度兜底**：plan 明确要求：
  - 不在估算器内部拼接 `errors` 文案
  - 不在估算器内部吞异常后继续降级
  - `validate_internal_hours()` 只对真正的坏值（非空非数值字符串等）抛 `ValueError`，不会比当前执行路径更严
  - `runtime_state.py` 的共享函数不包广域 `try/except`

  **无静默回退**：plan 系统性地清除了算法热路径中的静默回退：
  - `or 1.0` 隐式效率回退 → 显式 `raw_eff is not None` 判断
  - `except Exception: eff = 1.0` 广域吞错 → 去掉，让程序错误暴露
  - `guard < 200` 固定硬上限 → 基于片段数的可证明上界
  - `candidates[0]` 死代码兜底 → 删除
  - 双层 try/except 自动分配探测吞错 → 只允许 `chosen is None` 分支

  **无新的抽象膨胀**：明确不新增第二套估算器、调度器门面类或并行算法模式。

  ### 遗漏与边界问题

  1. **`priority` 参数缺失**：估算器需要 `priority` 来调用日历服务，但参数列表中未显式列出（发现 F8）。

  2. **`blocked_by_window` 处理未显式列出**：任务 1 步骤 4 描述了 `efficiency_fallback_used` 的处理，但没有写出 `blocked_by_window=True` 时的完整处理流程（发现 F9）。

  3. **自动分配重复估算一致性**：已声明的已知重复需要保证两次估算使用同一时间线引用（发现 F10）。

  ### 交叉影响检查

  - `downtime.py` 的 `find_earliest_available_start()` 和 `occupy_resource()` 只被 `scheduler.py`、`auto_assign.py`、`sgs.py` 三个文件引用，与 plan 影响域一致。
  - `_due_exclusive()` 在 `evaluation.py`、`dispatch_rules.py`、`ortools_bottleneck.py` 三处各有一份副本，plan 任务 4 正确要求统一到 `date_parsers.py`。
  - `_scaled_hours()` 闭包在 `scheduler.py` 和 `auto_assign.py` 各有一份副本，plan 任务 1 正确要求统一到估算器。
  - `schedule_params.py` 转导出 `parse_date`/`parse_datetime` 给 `scheduler.py`，plan 任务 4 正确要求直接导入。

  ### "明确不做"边界评估

  plan 列出的 12 项明确不做的事项边界清晰，没有发现遗漏。特别是：
  - 不改 `CalendarEngine.get_efficiency()` 中的 `or 1.0` → 正确，这不在算法层
  - 不改 `schedule_summary.py` 和 `calculations.py` 的 `due_exclusive()` → 正确，不在热路径
  - 不做 `compute_metrics()` 三次遍历合并 → 正确，不在本轮范围
  - 保留自动分配重复估算 → 正确，已文档化的权衡

  ### 完成判定评估

  plan 的完成判定共 9 条，覆盖全面。其中第 9 条特别写明"schedule_params.py 的历史遗留静默吞错若仍未改动，只能作为范围外已知残留存在，不能被宣称'已清零'"——这是对完成判定的诚实约束，避免虚假宣称。
- 结论:

  plan 整体设计优雅简洁，无过度兜底和静默回退，发现 3 个额外问题
- 问题:
  - [低] 可维护性: estimate_internal_slot 参数列表缺 priority
  - [中] 可维护性: 任务 1 步骤 4 缺 blocked_by_window 的显式处理流程
  - [低] 性能: 自动分配場景下的已知重复估算需保证一致性

## 最终结论

## 三轮深度审查总结

### 总体评价

这是一份**质量极高的重构 plan**。经过三轮深入审查，共核验了 13 个代码库中的核心文件、13 条修订前提、6 节引用链总览以及 5 个任务的全部实施步骤。

**能否达成目的**：✅ 可以达成。plan 准确识别了当前代码的核心问题（三套独立估算逻辑、固定 200 次硬上限、广域吞异常、日期解析副本散落），并提出了清晰可行的统一方案。

**实现是否优雅简洁**：✅ 设计非常干净。`internal_slot.py`（纯估算）+ `runtime_state.py`（纯状态更新）+ 编排层 + 评分层的四层职责分离消除了现有的高度耦合，且不引入新的抽象膨胀。

**是否存在过度兜底或静默回退**：✅ plan 系统性地清除了 `or 1.0` 隐式效率回退、`except Exception: eff = 1.0` 广域吞错、`candidates[0]` 死代码兜底、双层 try/except 自动分配探测吞错等问题，替换为显式的 `raw_eff is not None` 判断和明确的业务不可估算分支。

**逻辑是否严谨**：✅ 整体严谨。避让上界公式 `N_machine + N_operator + N_downtime + 1` 的数学论证成立；`validate_internal_hours()` 的空值兼容边界与当前行为完全一致；评分阶段"先验工时 → 再探资源 → 后估时段"的固定顺序杜绝了根因混淆。

### 发现的 10 个问题

| 级别 | 数量 | 关键项 |
|------|------|--------|
| 高   | 1    | F2: `optimize_schedule` 中 `_parse_date` 误用 `field="due_date"` 解析 `ready_date`（已有 BUG，任务 4 修复） |
| 中   | 5    | F1: `cutoff_exceeded` 字段与约束矛盾；F3: 探测形状校验冗余；F4: seed/派工状态语义差异回归缺用例；F6: 部分提交窗口回归覆盖不足；F9: `blocked_by_window` 处理流程缺失 |
| 低   | 4    | F5/F7/F8/F10: 均为实施细节澄清或优化建议 |

### 需要在实施前修改 plan 的建议

1. **必须修改**：解决 F1 `cutoff_exceeded` 字段矛盾（删除字段或改为返回值语义）
2. **必须修改**：在任务 1 步骤 4 中显式列出 `blocked_by_window` 的处理流程（F9）
3. **建议修改**：在任务 4 回归用例中补充"seed 预热中非空 `op_type_name` 但 `end_time <= prev_end` 时不覆盖"的场景（F4）
4. **建议标注**：任务 1~3 的严格模式回归若涉及 `ready_date` 解析，需预期标注 F2 为已知问题（F2）

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnot6wyu-1mukbq",
  "createdAt": "2026-04-07T00:00:00.000Z",
  "updatedAt": "2026-04-07T16:09:05.650Z",
  "finalizedAt": "2026-04-07T16:09:05.650Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "算法层统一估算与派工重构plan三轮深度审查",
    "date": "2026-04-07",
    "overview": "对算法层统一估算与派工重构plan进行三轮深度审查：第一轮核验代码前提与引用链，第二轮审查实施步骤逻辑严谨性，第三轮检查遗漏与潜在BUG"
  },
  "scope": {
    "markdown": "# 算法层统一估算与派工重构 plan 三轮深度审查\n\n**审查日期**: 2025-04-09\n**审查对象**: `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`\n\n## 审查范围\n- 第一轮：核验 plan 中所有代码前提与引用链是否与当前代码一致\n- 第二轮：审查实施步骤的逻辑严谨性、是否有静默回退、过度兜底\n- 第三轮：检查遗漏、潜在BUG、边界条件与优雅性评估"
  },
  "summary": {
    "latestConclusion": "## 三轮深度审查总结\n\n### 总体评价\n\n这是一份**质量极高的重构 plan**。经过三轮深入审查，共核验了 13 个代码库中的核心文件、13 条修订前提、6 节引用链总览以及 5 个任务的全部实施步骤。\n\n**能否达成目的**：✅ 可以达成。plan 准确识别了当前代码的核心问题（三套独立估算逻辑、固定 200 次硬上限、广域吞异常、日期解析副本散落），并提出了清晰可行的统一方案。\n\n**实现是否优雅简洁**：✅ 设计非常干净。`internal_slot.py`（纯估算）+ `runtime_state.py`（纯状态更新）+ 编排层 + 评分层的四层职责分离消除了现有的高度耦合，且不引入新的抽象膨胀。\n\n**是否存在过度兜底或静默回退**：✅ plan 系统性地清除了 `or 1.0` 隐式效率回退、`except Exception: eff = 1.0` 广域吞错、`candidates[0]` 死代码兜底、双层 try/except 自动分配探测吞错等问题，替换为显式的 `raw_eff is not None` 判断和明确的业务不可估算分支。\n\n**逻辑是否严谨**：✅ 整体严谨。避让上界公式 `N_machine + N_operator + N_downtime + 1` 的数学论证成立；`validate_internal_hours()` 的空值兼容边界与当前行为完全一致；评分阶段\"先验工时 → 再探资源 → 后估时段\"的固定顺序杜绝了根因混淆。\n\n### 发现的 10 个问题\n\n| 级别 | 数量 | 关键项 |\n|------|------|--------|\n| 高   | 1    | F2: `optimize_schedule` 中 `_parse_date` 误用 `field=\"due_date\"` 解析 `ready_date`（已有 BUG，任务 4 修复） |\n| 中   | 5    | F1: `cutoff_exceeded` 字段与约束矛盾；F3: 探测形状校验冗余；F4: seed/派工状态语义差异回归缺用例；F6: 部分提交窗口回归覆盖不足；F9: `blocked_by_window` 处理流程缺失 |\n| 低   | 4    | F5/F7/F8/F10: 均为实施细节澄清或优化建议 |\n\n### 需要在实施前修改 plan 的建议\n\n1. **必须修改**：解决 F1 `cutoff_exceeded` 字段矛盾（删除字段或改为返回值语义）\n2. **必须修改**：在任务 1 步骤 4 中显式列出 `blocked_by_window` 的处理流程（F9）\n3. **建议修改**：在任务 4 回归用例中补充\"seed 预热中非空 `op_type_name` 但 `end_time <= prev_end` 时不覆盖\"的场景（F4）\n4. **建议标注**：任务 1~3 的严格模式回归若涉及 `ready_date` 解析，需预期标注 F2 为已知问题（F2）",
    "recommendedNextAction": "修改 plan 中 F1（cutoff_exceeded 字段矛盾）和 F9（blocked_by_window 处理流程缺失）两个必须项，补充 F4 的回归用例后即可进入实施",
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
      "core/services/scheduler/schedule_optimizer.py",
      "core/services/scheduler/schedule_optimizer_steps.py",
      "core/services/common/strict_parse.py",
      "core/algorithms/sort_strategies.py",
      "core/algorithms/greedy/schedule_params.py"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 10,
    "severity": {
      "high": 1,
      "medium": 5,
      "low": 4
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "第一轮：代码前提与引用链核验",
      "status": "completed",
      "recordedAt": "2026-04-07T16:04:44.725Z",
      "summaryMarkdown": "逐条核验了 plan 中 13 条修订前提与 6 节引用链总览，均与当前代码实际状态一致。\n\n### 前提核验结果\n\n1. **前提 1（主链路径）**：✅ 已确认 `ScheduleService._run_schedule_impl()` → `collect_schedule_run_input()` → `orchestrate_schedule_run()` → `optimize_schedule()` → `_run_ortools_warmstart()` / `_run_multi_start()` / `_run_local_search()` → `_schedule_with_optional_strict_mode()` → `GreedyScheduler.schedule()` 链路与 plan 描述一致。\n\n2. **前提 2（两套估算族）**：✅ `scheduler.py:469-543` 与 `auto_assign.py:156-223` 确实都使用\"三条时间线同时检查并反复避让\"的循环；`sgs.py:278-341` 使用 `find_earliest_available_start()` 的顺序链式近似。两者确实不是同一算法。\n\n3. **前提 3（input_builder 规范化）**：✅ 行号引用准确，`setup_hours`、`unit_hours` 已在服务层规范化为数值。\n\n4. **前提 4（`__init__.py` 导出 `GreedyScheduler`）**：✅ `core/algorithms/__init__.py:13` 确实导出 `GreedyScheduler`。\n\n5. **前提 5（两类日期解析器语义不同）**：✅ `sgs.py:18-24` 的 `_parse_date()` 在 `strict_mode=True` 时会抛 `ValidationError`；`date_parsers.py:7-41` 永不抛异常。plan 正确指出不能机械合并。\n\n6. **前提 6（缺共享严格日期时间解析）**：✅ `strict_parse.py` 只有 `parse_required_date` 和 `parse_optional_date`，没有日期时间版本。`schedule_optimizer.py:343-357` 的 `_parse_datetime()` 确实是本地非严格实现。\n\n7. **前提 7（seed 预热也维护运行期状态）**：✅ `scheduler.py:289-304` 确实更新 `machine_busy_hours`、`operator_busy_hours`、`last_end_by_machine`、`last_op_type_by_machine`。\n\n8. **前提 8（`guard < 200` 硬上限）**：✅ `scheduler.py:513` 和 `auto_assign.py:185` 都使用 `while guard < 200`。\n\n9. **前提 9（`or 1.0` 隐式布尔回退）**：✅ `scheduler.py:494` 使用 `or 1.0`；`sgs.py:323` 也使用 `or 1.0`；`auto_assign.py:166-169` 使用 `raw_eff is not None` 但外层仍有 `except Exception: eff = 1.0`。\n\n10. **前提 10（`schedule_summary.py` 不在热路径）**：✅ plan 正确不扩到此处。\n\n11. **前提 11（`created_at` 只被 FIFO 消费）**：✅ `sort_strategies.py:117-125` 的 `FIFOStrategy.sort()` 是唯一消费 `batch.created_at` 的地方。\n\n12. **前提 12（`schedule_params.py` 静默吞错）**：✅ `schedule_params.py:45-54` 的 `_critical_config_read()` 在 `strict_mode=False` 时 `warnings.append(...)` 并回退到默认值，不抛异常。\n\n13. **前提 13（`getattr(..., 0) or 0` 的空值兼容边界）**：✅ `scheduler.py:476-480` 和 `auto_assign.py:102-106` 都使用 `getattr(op, \"setup_hours\", 0) or 0`，`sgs.py:91-99` 用 `parse_required_float()`，边界确实不同。\n\n### 引用链核验结论\n\n- `scheduler.py` 的 `_parse_date` / `_parse_datetime` 是从 `schedule_params.py` 转导出，后者实际从 `date_parsers.py` 导入。plan 任务 4 要求 `scheduler.py` 直接从 `date_parsers.py` / `strict_parse.py` 导入，这是正确的简化方向。\n- `optimize_schedule()` 中 `batch_for_sort` 构造（行 359-370）先于 `valid_strategies` / `keys` 确定（行 392-401），这与 plan 前提的分析一致。\n- `_run_multi_start()` 中 `order = build_order(strat, params0)` 在 `dispatch_rules` 内层循环中（行 334），确实会因不同 `dr` 重复构造相同 `order`。\n- `_run_local_search()` 中确实没有邻域去重逻辑（行 139-261）。",
      "conclusionMarkdown": "plan 中 13 条修订前提和 6 节引用链总览全部与当前代码一致，行号引用精确，未发现前提失实。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 469,
          "lineEnd": 543,
          "symbol": "_schedule_internal"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 96,
          "lineEnd": 230,
          "symbol": "auto_assign_internal_resources"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 278,
          "lineEnd": 370,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "core/algorithms/greedy/downtime.py",
          "lineStart": 20,
          "lineEnd": 28,
          "symbol": "occupy_resource"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 335,
          "lineEnd": 401,
          "symbol": "optimize_schedule"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py",
          "lineStart": 306,
          "lineEnd": 334,
          "symbol": "_run_multi_start"
        },
        {
          "path": "core/algorithms/__init__.py",
          "lineStart": 1,
          "lineEnd": 26
        }
      ],
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
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/scheduler/schedule_optimizer_steps.py",
        "core/services/common/strict_parse.py",
        "core/algorithms/sort_strategies.py"
      ],
      "recommendedNextAction": "进入第二轮审查：逐任务审查实施步骤的逻辑严谨性",
      "findingIds": []
    },
    {
      "id": "M2",
      "title": "第二轮：实施步骤逻辑严谨性审查",
      "status": "completed",
      "recordedAt": "2026-04-07T16:07:13.268Z",
      "summaryMarkdown": "逐任务深入审查了 plan 的五个任务实施步骤的逻辑严谨性，发现 7 个需要注意的问题。\n\n### 任务 1 审查结论\n\n**避让上界公式**：`N_machine + N_operator + N_downtime + 1` 的数学论证成立。每次迭代 `earliest` 严格递增且只能停在片段端点上，因此最多迭代等于总片段数。\n\n**`validate_internal_hours()` 兼容性**：设计正确。`getattr(op, \"setup_hours\", 0) or 0` 的语义被完整保留：缺字段→0、None→0、空串→0、False→0、\"bad\"→ValueError。与当前 `_schedule_internal()` 和 `auto_assign_internal_resources()` 的行为一致。\n\n**`InternalSlotEstimate` 字段矛盾**：`cutoff_exceeded` 字段与\"越过上界直接抛实现错误\"的约束矛盾，是死字段。（发现 F1）\n\n**效率处理**：plan 正确要求去掉 `or 1.0` 隐式回退，改用 `raw_eff is not None` 显式判断。与 `auto_assign.py:166-167` 现有模式一致。\n\n### 任务 2 审查结论\n\n**`candidates[0]` 死代码**：确认是死代码。`best_key` 在第一个候选评分完成后必定非 None（因为外层 try/except 最坏情况下也会构造硬编码 tuple），所以 `best_pair` 永远非 None。\n\n**`avg_proc_hours` 初始化改用 `validate_internal_hours()`**：会使采样变宽松（原来 `parse_required_float(None)` 拒绝，现在 `validate_internal_hours()` 接受为 0 但不加入 `proc_samples`——因为 `h=0` 时 `h > 0` 为 False 所以不会加入）。实际效果不变。\n\n**评分顺序固定**：先 validate_hours → 资源探测 → estimate_internal_slot 的设计正确，把工时坏值和缺资源两种根因彻底分开。\n\n### 任务 3 审查结论\n\n**有序插入 Python 3.8 兼容**：`bisect.insort` 在 3.8 只支持元组自然序排序，(start, end) 元组天然按 start 升序，符合要求。\n\n**seed 预热与派工成功的状态语义差异**：plan 正确识别了 `conditional_op_type=True/False` 的差异，但回归用例缺少一条关键场景（发现 F4）。\n\n**部分提交修复**：plan 对 sgs.py 的分析完整，但 batch_order.py 的回归覆盖不够明确（发现 F6）。\n\n### 任务 4 审查结论\n\n**`_parse_date` 误用 `field=\"due_date\"` 解析 `ready_date`**：确认是已存在的 BUG，plan 正确识别并在任务 4 修复。但任务 1~3 的严格模式回归可能先触发此问题（发现 F2）。\n\n**`created_at` strict 启用判断以 `keys` 为准**：plan 正确指出 `batch_for_sort` 构造（行 359-370）先于 `keys` 确定（行 399），而当前代码对 `created_at` 的 `_parse_datetime()` 不分 strict/non-strict 都是非严格的。plan 要求前移 `keys` 计算或延迟 `created_at` 解析，设计合理。\n\n**`ready_date` 静默回退**：`scheduler.py:232-236` 的 `except Exception: dt_ready = dt0` 确实是静默回退，plan 正确要求去掉。\n\n### 任务 5 审查结论\n\n**order 缓存键**：`(strategy.value, tuple(sorted(params0.items())))` 对当前的 params0 结构（空字典或 {priority_weight, due_weight}）是正确的。\n\n**邻域去重**：`tuple(cand_order)` 作为哈希键，对最大 5000 次迭代的规模是可接受的。shake 后清空并重写当前 + 最优，设计合理。\n\n**`no_improve` 语义变化**：从\"未改善的已评估数\"变为\"未改善的迭代数含跳过\"，可能导致 shake 更频繁（发现 F7）。",
      "conclusionMarkdown": "五个任务的实施步骤整体逻辑严谨，但发现 7 个问题需要注意",
      "evidence": [],
      "reviewedModules": [],
      "recommendedNextAction": "进入第三轮审查：检查遗漏、潜在BUG与优雅性评估",
      "findingIds": [
        "F1",
        "F2",
        "F3",
        "F4",
        "F5",
        "F6",
        "F7"
      ]
    },
    {
      "id": "M3",
      "title": "第三轮：遗漏检查、潜在BUG与优雅性评估",
      "status": "completed",
      "recordedAt": "2026-04-07T16:08:50.553Z",
      "summaryMarkdown": "第三轮审查聚焦遗漏、潜在 BUG 与整体设计优雅性评估，发现 3 个额外问题。\n\n### 整体设计优雅性评估\n\n**职责分离清晰**：plan 创建了一个干净的四层结构：\n- `internal_slot.py`：纯估算（无状态变更、无错误文案拼接）\n- `runtime_state.py`：纯状态更新（无估算、无吞异常）\n- `scheduler.py`：编排层（资源分配、结果构建、时间线占用）\n- `sgs.py`：评分与选择（调用估算器获取真实评分）\n\n这是对当前高度耦合代码的重大改善。每个模块职责单一，不存在越界。\n\n**无过度兜底**：plan 明确要求：\n- 不在估算器内部拼接 `errors` 文案\n- 不在估算器内部吞异常后继续降级\n- `validate_internal_hours()` 只对真正的坏值（非空非数值字符串等）抛 `ValueError`，不会比当前执行路径更严\n- `runtime_state.py` 的共享函数不包广域 `try/except`\n\n**无静默回退**：plan 系统性地清除了算法热路径中的静默回退：\n- `or 1.0` 隐式效率回退 → 显式 `raw_eff is not None` 判断\n- `except Exception: eff = 1.0` 广域吞错 → 去掉，让程序错误暴露\n- `guard < 200` 固定硬上限 → 基于片段数的可证明上界\n- `candidates[0]` 死代码兜底 → 删除\n- 双层 try/except 自动分配探测吞错 → 只允许 `chosen is None` 分支\n\n**无新的抽象膨胀**：明确不新增第二套估算器、调度器门面类或并行算法模式。\n\n### 遗漏与边界问题\n\n1. **`priority` 参数缺失**：估算器需要 `priority` 来调用日历服务，但参数列表中未显式列出（发现 F8）。\n\n2. **`blocked_by_window` 处理未显式列出**：任务 1 步骤 4 描述了 `efficiency_fallback_used` 的处理，但没有写出 `blocked_by_window=True` 时的完整处理流程（发现 F9）。\n\n3. **自动分配重复估算一致性**：已声明的已知重复需要保证两次估算使用同一时间线引用（发现 F10）。\n\n### 交叉影响检查\n\n- `downtime.py` 的 `find_earliest_available_start()` 和 `occupy_resource()` 只被 `scheduler.py`、`auto_assign.py`、`sgs.py` 三个文件引用，与 plan 影响域一致。\n- `_due_exclusive()` 在 `evaluation.py`、`dispatch_rules.py`、`ortools_bottleneck.py` 三处各有一份副本，plan 任务 4 正确要求统一到 `date_parsers.py`。\n- `_scaled_hours()` 闭包在 `scheduler.py` 和 `auto_assign.py` 各有一份副本，plan 任务 1 正确要求统一到估算器。\n- `schedule_params.py` 转导出 `parse_date`/`parse_datetime` 给 `scheduler.py`，plan 任务 4 正确要求直接导入。\n\n### \"明确不做\"边界评估\n\nplan 列出的 12 项明确不做的事项边界清晰，没有发现遗漏。特别是：\n- 不改 `CalendarEngine.get_efficiency()` 中的 `or 1.0` → 正确，这不在算法层\n- 不改 `schedule_summary.py` 和 `calculations.py` 的 `due_exclusive()` → 正确，不在热路径\n- 不做 `compute_metrics()` 三次遍历合并 → 正确，不在本轮范围\n- 保留自动分配重复估算 → 正确，已文档化的权衡\n\n### 完成判定评估\n\nplan 的完成判定共 9 条，覆盖全面。其中第 9 条特别写明\"schedule_params.py 的历史遗留静默吞错若仍未改动，只能作为范围外已知残留存在，不能被宣称'已清零'\"——这是对完成判定的诚实约束，避免虚假宣称。",
      "conclusionMarkdown": "plan 整体设计优雅简洁，无过度兜底和静默回退，发现 3 个额外问题",
      "evidence": [],
      "reviewedModules": [],
      "recommendedNextAction": null,
      "findingIds": [
        "F8",
        "F9",
        "F10"
      ]
    }
  ],
  "findings": [
    {
      "id": "F1",
      "severity": "medium",
      "category": "maintainability",
      "title": "InternalSlotEstimate 中 cutoff_exceeded 字段与约束矛盾",
      "descriptionMarkdown": "plan 任务 1 步骤 3 定义 InternalSlotEstimate 包含 cutoff_exceeded 字段，但实施约束同时写道'若仍越过这条可证明上界，应视为实现错误直接暴露，而不是静默转成业务失败'。这两条要求互相矛盾：如果越过动态上界直接抛实现错误，那么 cutoff_exceeded 字段永远不会为 True，这个字段就是死字段。然而任务 1 步骤 4 又在 auto_assign 中写了 'cutoff_exceeded=True 时直接跳过当前组合'，暗示它是一个正常的返回值。\n\n建议：要么删除 cutoff_exceeded 字段（因为实现错误不会返回而是抛出），要么把'越过上界'从'实现错误'降级为'估算失败'并通过 cutoff_exceeded 返回；两者取其一即可，不要两种语义并存。",
      "recommendationMarkdown": "删除 InternalSlotEstimate 的 cutoff_exceeded 字段，越过动态上界直接抛 RuntimeError；或保留 cutoff_exceeded 字段但不抛异常，通过返回值让调用方决策。",
      "evidence": [
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F2",
      "severity": "high",
      "category": "javascript",
      "title": "optimize_schedule 中 _parse_date 误用 field=\"due_date\" 解析 ready_date",
      "descriptionMarkdown": "当前 optimize_schedule() 行 367 对 ready_date 使用 _parse_date()，而 _parse_date()（行 335-341）硬编码了 field=\"due_date\"。在严格模式下，一个格式错误的 ready_date 会以 field=\"due_date\" 的名义抛出 ValidationError，造成误导性错误信息。plan 任务 4 步骤 4 已正确识别此问题并要求拆分为 _parse_due_date() 和 _parse_ready_date()，但该 BUG 在任务依赖链中排在任务 4 才修复，而任务 1~3 的回归验证可能先在严格模式下触发此 BUG。建议在任务 1 结束后就先确认严格模式回归是否涉及 ready_date 解析。",
      "recommendationMarkdown": "若任务 1~3 的严格模式回归路径涉及 ready_date 解析（如 regression_schedule_input_builder_strict_hours_and_ext_days.py），应在任务 4 之前提前对此做预期标注，避免中途被误判为新引入 BUG。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 335,
          "lineEnd": 370,
          "symbol": "_parse_date"
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
      "id": "F3",
      "severity": "medium",
      "category": "maintainability",
      "title": "sgs.py 自动分配探测双层广域吞异常与返回形状校验冗余",
      "descriptionMarkdown": "sgs.py 行 232-263 的自动分配探测有两层 try/except，且内层（行 252-260）既检查 chosen 是否为 tuple/list 且 len>=2，又用 except Exception 吞掉校验失败。plan 任务 2 正确要求删除这种双层吞异常。但 plan 步骤 3 对 _score_internal_candidate() 的描述中只说'chosen is None 是唯一允许的正常缺资源分支'，未明确说明当 auto_assign 返回类型不是 Optional[Tuple[str,str]] 时的处理方式。\n\n实际上，auto_assign_internal_resources() 的返回类型签名是 Optional[Tuple[str, str]]，所以非 None 返回一定是 (str, str) 元组。内层的形状检查是多余的防御代码。",
      "recommendationMarkdown": "重构后的 _score_internal_candidate() 直接信任 auto_assign_internal_resources() 的返回类型契约：如果非 None 就解包为 (machine_id, operator_id)，不做冗余形状检查。如果返回类型违约，让 Python 的解包错误自然暴露。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 232,
          "lineEnd": 263,
          "symbol": "dispatch_sgs"
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
      "id": "F4",
      "severity": "medium",
      "category": "maintainability",
      "title": "sgs.py 派工成功后 last_op_type 与 seed 预热语义不一致需显式标注",
      "descriptionMarkdown": "seed 预热（scheduler.py:299-304）中 last_op_type_by_machine 仅在 end_time > prev_end 时才条件更新；而派工成功路径（sgs.py:473-475、batch_order.py:104-106）中 last_op_type_by_machine 是非空时无条件覆盖。plan 任务 3 步骤 4 已识别此差异并要求通过 conditional_op_type=True/False 两种模式区分。\n\n但 plan 中的回归测试步骤 1 中虽然写了'seed 预热遇到空 op_type_name 时不推进'和'派工成功模式下 last_op_type 保持直接更新'两条用例，却没有写一条覆盖'seed 预热中非空 op_type_name 但 end_time <= prev_end 时不覆盖'这个真正的语义差异点。这是 seed 模式最核心的区别行为。",
      "recommendationMarkdown": "在 tests/regression_downtime_timeline_ordered_insert.py 或同组回归中补一条用例：构造两条同设备 seed 结果，后一条 end_time 早于前一条，断言 last_op_type_by_machine 仍保持第一条的工种名而非被第二条覆盖。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 299,
          "lineEnd": 304,
          "symbol": "schedule"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 473,
          "lineEnd": 475,
          "symbol": "dispatch_sgs"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
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
      "id": "F5",
      "severity": "low",
      "category": "maintainability",
      "title": "避让上界公式中停机片段数的计算时机需澄清",
      "descriptionMarkdown": "plan 要求避让上界在 estimate_internal_slot() '每次调用入口' 按当前片段数现算：len(machine_timeline[mid]) + len(operator_timeline[oid]) + len(downtime_segments) + 1。但 downtime_segments 指的是 machine_downtimes.get(machine_id)，这个列表在同一次排产调用中不会变化（停机信息是输入，不会被 occupy_resource 修改）；而 machine_timeline[mid] 和 operator_timeline[oid] 会在每次 occupy_resource 后增长。\n\n因此上界确实需要在每次 estimate 调用入口现算，否则用缓存的旧值会低估。plan 对此的要求是正确的，但实施时要注意：如果使用的是引用（list 引用），len() 总是会拿到当前值；只有当拷贝了 timeline 快照时才需要特别注意。",
      "recommendationMarkdown": "实施时直接对传入的 machine_timeline[mid] 和 operator_timeline[oid] 引用调用 len()，不要在入口做快照拷贝。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 510,
          "lineEnd": 536
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
      "id": "F6",
      "severity": "medium",
      "category": "maintainability",
      "title": "部分提交窗口在 batch_order.py 中同样存在",
      "descriptionMarkdown": "plan 任务 3 详细分析了 sgs.py 的部分提交问题（results.append 之后的状态更新被 try/except 包裹），但 batch_order.py:86-106 有完全相同的结构：先 results.append(result)，然后 try/except 包裹 busy_hours 更新。plan 步骤 4 列出了 batch_order.py:90-106 作为需要改造的位置，但回归测试步骤 1 第 7 条'共享状态更新不会留下已追加 results 的部分提交'的用例只泛泛提及，没有明确要求分别覆盖 batch_order 和 sgs 两条路径。",
      "recommendationMarkdown": "在 regression_downtime_timeline_ordered_insert.py 的部分提交用例中，同时覆盖 batch_order 和 sgs 两条派工路径，确保两条路径的状态更新都已经收口到共享函数。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py",
          "lineStart": 86,
          "lineEnd": 106,
          "symbol": "dispatch_batch_order"
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F7",
      "severity": "low",
      "category": "maintainability",
      "title": "本地搜索去重后 no_improve 计数语义需精确定义",
      "descriptionMarkdown": "plan 任务 5 步骤 4 要求：重复邻域跳过后'必须继续推进用于触发 restart_after 的停滞计数'。当前代码中 no_improve 仅在 score >= best[\"score\"] 时递增。但引入去重后，被跳过的重复邻域既没有评估 score，也不算改善。plan 要求把跳过也计入停滞。\n\n但这会引入一个微妙的语义变化：原来 no_improve 是'连续未改善的已评估尝试数'，现在变成'连续未改善的迭代数（含跳过）'。如果搜索空间小且重复率高，shake 会被更频繁地触发。这不是 BUG，但应在回归测试中用小规模场景验证 shake 不会过于频繁导致搜索退化。",
      "recommendationMarkdown": "regression_optimizer_local_search_neighbor_dedup.py 中的小规模场景测试应验证：高重复率场景下 shake 频率与改善效果的平衡，确保不会因为过度 shake 导致搜索空间浪费。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 139,
          "lineEnd": 261,
          "symbol": "_run_local_search"
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
      "id": "F8",
      "severity": "low",
      "category": "maintainability",
      "title": "estimate_internal_slot 参数列表缺 priority",
      "descriptionMarkdown": "plan 任务 1 步骤 3 的 estimate_internal_slot() 参数列表中没有显式包含 priority 参数，但估算器内部需要调用 calendar.adjust_to_working_time(earliest, priority=priority, operator_id=operator_id) 和 calendar.add_working_hours(earliest, total_hours, priority=priority, operator_id=operator_id)。当前设计是通过 getattr(batch, 'priority', None) 从 batch 参数中提取，但这让估算器依赖 batch 对象的属性结构。\n\n这不是 BUG（与当前行为一致），但作为一个纯估算函数，显式接收 priority 参数会更简洁。",
      "recommendationMarkdown": "建议在 estimate_internal_slot() 参数列表中显式加入 priority: Optional[str] = None，避免估算器内部做 getattr(batch, 'priority', None)。",
      "evidence": [
        {
          "path": ".limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F9",
      "severity": "medium",
      "category": "maintainability",
      "title": "任务 1 步骤 4 缺 blocked_by_window 的显式处理流程",
      "descriptionMarkdown": "plan 任务 1 步骤 4 要求 _schedule_internal() '用 InternalSlotEstimate 组装 ScheduleResult'，但没有明确说明当 estimate_internal_slot() 成功返回后，调用方是否仍然需要检查 blocked_by_window。\n\n当前代码中，_schedule_internal() 在 end >= end_dt_exclusive 时返回 (None, True)（blocked_by_window=True）。如果估算器返回 InternalSlotEstimate 且 blocked_by_window=True，调用方必须显式检查并返回 (None, True)。plan 任务 1 步骤 4 对此只写了'若 efficiency_fallback_used=True 更新计数器'，没有明确列出 blocked_by_window 的处理逻辑。",
      "recommendationMarkdown": "在任务 1 步骤 4 的描述中显式加入：若 estimate.blocked_by_window 为 True，组装超窗口错误信息并返回 (None, True)；否则继续 occupy_resource 并组装 ScheduleResult。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 538,
          "lineEnd": 543,
          "symbol": "_schedule_internal"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F10",
      "severity": "low",
      "category": "performance",
      "title": "自动分配場景下的已知重复估算需保证一致性",
      "descriptionMarkdown": "plan 中明确说明了自动分配场景下保留一次已知重复估算（明确不做第 11 项）。auto_assign_internal_resources() 完成后找到最优 (machine_id, operator_id)，然后 _schedule_internal() 还会再次调用 estimate_internal_slot() 做一次相同的估算。\n\n这是正确的设计权衡。如果要消除这次重复，需要让 auto_assign 返回完整的 InternalSlotEstimate 而不是只返回 (machine_id, operator_id)，但 plan 正确地把这推迟到未来轮次。只是实施时应确保重复估算的结果与 auto_assign 内部估算的结果一致（同一估算器、同样的时间线状态）。",
      "recommendationMarkdown": "实施时确保 auto_assign 内部的 estimate_internal_slot() 与后续 _schedule_internal() 中的调用接收的是同一引用的 machine_timeline / operator_timeline，这样两次估算结果才会一致。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 564,
          "lineEnd": 596,
          "symbol": "_auto_assign_internal_resources"
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
    "bodyHash": "sha256:187315caa35bf632494bff22f2906a5cf19611e2d06b971cc5c63e37a2763b8e",
    "generatedAt": "2026-04-07T16:09:05.650Z",
    "locale": "zh-CN"
  }
}
```
