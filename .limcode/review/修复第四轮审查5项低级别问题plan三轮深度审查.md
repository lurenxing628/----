# 修复第四轮审查5项低级别问题plan三轮深度审查
- 日期: 2026-04-09
- 概述: 对修复plan（修订版v2）进行三轮深度审查，验证实现正确性、逻辑严谨性及边界覆盖完整度
- 状态: 已完成
- 总体结论: 通过

## 评审范围

# 修复第四轮审查 5 项低级别问题 plan — 三轮深度审查

**审查日期**: 2026-04-08
**审查目标**: 对 `.limcode/plans/修复第四轮审查-5-项低级别问题.plan.md`（修订版 v2）进行三轮深度审查，验证：
1. 每项修复的实现是否忠实反映 plan 意图
2. 代码实现是否优雅、简洁，无过度兜底或静默回退
3. 测试覆盖是否锁定了所有关键语义
4. 逻辑严谨性与潜在 BUG 风险
5. 验证命令的完整性与最终回归覆盖度

**审查范围**: plan 文档 + 4 项已实现修复的源文件与测试文件的交叉验证

## 评审摘要

- 当前状态: 已完成
- 已审模块: 修复1+3实现核验, 修复2实现核验, 修复4实现核验, 修复5实现核验, 同事意见处置核验, 修复2测试的参数覆盖度, 修复5半开区间边界条件, 修复5效率边界场景完整性, 过度防御与静默回退扫描, plan设计简洁度, 验证命令覆盖完整性, 整体设计优雅度, plan与第四轮审查的问题对应关系, 遗漏风险扫描, 最终能否达成目的判定
- 当前进度: 已记录 3 个里程碑；最新：M3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 3
- 问题严重级别分布: 高 0 / 中 0 / 低 3
- 最新结论: ## 三轮深度审查总结 ### 总体评价 这份修复 plan（修订版 v2）是一份**高质量的局部修复方案**。4 项已完成修复的代码实现与 plan 声明完全一致，每项修复目标明确、边界清晰、实现简洁。方案没有过度兜底或静默回退——修复 2 的 `raise TypeError` 是显式拒绝而非静默吞错，修复 5 的测试验证异常直接上浮而非被捕获，修复 1+3 是纯删除操作。 ### 关键发现 共发现 3 项低级别问题（0 高 / 0 中 / 3 低），**全部为测试覆盖度的增量建议**，不影响修复本身的正确性： 1. **F-P1**：修复 2 的测试只覆盖了 `start_time` 坏参路径，缺少对称的 `end_time` 坏参用例 2. **F-P2**：修复 5 未锁定零工时落在占用区间起始边界时"不后移"的半开区间行为 3. **F-P3**：修复 5 未覆盖负值效率（如 `-1.0`）的回退行为 ### 能否达成目的 **可以**。4 项修复完整覆盖了 plan 声明的所有目标： - 修复 1+3 消除了 `_build_order` 中的等价重复解析代码——与现有排序链路测试和缓存语义测试交叉验证通过 - 修复 2 补齐了 `accumulate_busy_hours` 的 datetime 入参守卫——与 `update_machine_last_state` 的守卫对称 - 修复 4 将 `ordered` 重命名为 `valid_segments`——4 处引用无遗漏 - 修复 5 用 3 个新测试锁定了零工时和效率边界的语义——精确遵循了同事的半开区间分析 验证命令覆盖了所有直接和关键间接影响路径。同事意见处置正确——已撤回的误判没有被多余修改，接受的建议已精确落实。 ### 建议 1. 执行 `#fix-verify` 统一回归验证，将最后一项 TODO 标记完成 2. 3 项低级别测试建议可在下次迭代中补充，不阻塞合并
- 下一步建议: 执行最终验证命令（#fix-verify），将 TODO 标记为完成后即可合并；3 项低级别测试建议可在下次迭代中补充
- 总体结论: 通过

## 评审发现

### 修复2的测试只覆盖了 start_time 坏参路径，未覆盖对称的 end_time 坏参路径

- ID: F-P1
- 严重级别: 低
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  测试 `test_accumulate_busy_hours_rejects_non_datetime`（L108-119）仅传入了字符串 `start_time` + 有效 datetime `end_time`，测了 `start_time` 不合法的路径。但没有独立覆盖 `end_time` 不合法的对称路径。这不是 BUG——断言逻辑是对称的（同一条 `if` 语句用 `or` 检查两个参数），但测试作为合约证据不够对称。plan 本身只说“传入字符串 start_time”，测试循规躈矩，但可以再加一条仅传字符串 end_time 的对称用例。
- 建议:

  在 `test_accumulate_busy_hours_rejects_non_datetime` 中追加一条对称用例：start_time=有效 datetime、end_time=字符串，断言同样抛 TypeError
- 证据:
  - `tests/test_downtime_timeline_ordered_insert.py:108-119`
  - `tests/test_downtime_timeline_ordered_insert.py`

### 修复5未锁定零工时落在占用区间起始边界的行为

- ID: F-P2
- 严重级别: 低
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  plan 中明确指出 `find_overlap_shift_end` 使用半开区间语义，当 `start == end == s` 时会因 `s >= end` 提前跳出而不后移。这是零工时场景的一个重要边界：当 `base_time` 恰好落在占用区间起始边界上时，行为与落在内部时不同。当前测试 `test_zero_hours_still_avoids_occupied_segments` 只覆盖了“落在内部”场景，未覆盖“落在起始边界”场景。虽然 plan 已明确要求“不落在边界上”，但“落在边界上不后移”本身也是需要用测试锁定的语义。
- 建议:

  追加一条用例：零工时工序，`base_time` 恰好等于占用区间 `segment_start`，断言 `start_time == base_time`（不后移）。这将完整锁定半开区间的边界行为
- 证据:
  - `core/algorithms/greedy/downtime.py:62-80`
  - `tests/test_internal_slot_estimator_consistency.py:371-394`
  - `core/algorithms/greedy/downtime.py`
  - `tests/test_internal_slot_estimator_consistency.py`

### 修复5未覆盖负值效率的回退行为

- ID: F-P3
- 严重级别: 低
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  修复 5 的 `test_efficiency_edge_cases_none_zero_and_exception` 覆盖了 None、零值、异常三种场景，但未覆盖负值效率（如 `-1.0`）的行为。看 `_resolve_efficiency`（internal_slot.py:81）的 `eff <= 0` 检查，负值应该与 0.0 同样触发回退，但没有测试锁定这一行为。plan 本身只要求了三种场景，这不是 plan 的缺陷，但作为完整性建议值得补充。
- 建议:

  在 `test_efficiency_edge_cases_none_zero_and_exception` 中追加第四个子场景：`get_efficiency` 返回 `-1.0`，断言 `efficiency_fallback_used=True` 且工时按 eff=1.0 计算
- 证据:
  - `core/algorithms/greedy/internal_slot.py:71-83#_resolve_efficiency`
  - `tests/test_internal_slot_estimator_consistency.py:397-441`
  - `core/algorithms/greedy/internal_slot.py`
  - `tests/test_internal_slot_estimator_consistency.py`

## 评审里程碑

### M1 · 第一轮：4 项已完成修复的实现与 plan 声明一致性核验

- 状态: 已完成
- 记录时间: 2026-04-09T01:39:42.962Z
- 已审模块: 修复1+3实现核验, 修复2实现核验, 修复4实现核验, 修复5实现核验, 同事意见处置核验
- 摘要:

  逐条将 4 项已标记完成的修复（`#fix-01` ~ `#fix-05`）与实际代码和测试交叉核验。

  ### 修复 1+3（F-R4-01+03）：删除 `_build_order` 双重解析循环和闭包

  **plan 声明**：删除 `schedule_optimizer.py` 中 `_parse_due_date`/`_parse_ready_date` 两个闭包（L349-361）以及 `_build_order` 中的覆盖循环（L369-374），简化为直接调用 `build_batch_sort_inputs`。

  **代码核验**：搜索 `_parse_due_date` 和 `_parse_ready_date` 在 `schedule_optimizer.py` 中均无匹配。当前 `_build_order`（L348-355）已简化为：
  ```python
  def _build_order(strategy0: SortStrategy, params: Dict[str, Any]) -> List[str]:
      batch_for_sort = build_batch_sort_inputs(
          normalized_batches_for_sort,
          strict_mode=bool(strict_mode),
          strategy=strategy0,
      )
      sorter0 = StrategyFactory.create(strategy0, **(params or {}))
      return [item.batch_id for item in sorter0.sort(batch_for_sort, base_date=start_dt.date())]
  ```
  这与 plan 给出的期望代码**完全一致**。✓

  **验证测试**：`test_algorithm_date_boundary_split.py` 和 `test_optimizer_build_order_once_per_strategy.py` 分别覆盖了排序链路和缓存语义。

  ### 修复 2（F-R4-02）：`accumulate_busy_hours` 增加 datetime 类型断言

  **plan 声明**：在 `runtime_state.py` 的 `accumulate_busy_hours` 入口增加与 `update_machine_last_state` 对称的断言。

  **代码核验**：`runtime_state.py:16-17`：
  ```python
  if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
      raise TypeError("start_time/end_time 必须是 datetime")
  ```
  与 `update_machine_last_state:37-38` 的 `raise TypeError("end_time 必须是 datetime")` 对称。✓

  **补测核验**：`test_downtime_timeline_ordered_insert.py:108-119` 的 `test_accumulate_busy_hours_rejects_non_datetime` 传入字符串 `start_time`，断言抛 `TypeError`。✓

  ### 修复 4（F-R4-04）：`ordered` 重命名为 `valid_segments`

  **plan 声明**：将 `downtime.py` L46-56 中 `ordered` 全部替换为 `valid_segments`，共 4 处引用。

  **代码核验**：`downtime.py` 中出现 `valid_segments` 的位置：
  - L46：定义 `valid_segments = [...]`
  - L47：空值检查 `if not valid_segments`
  - L54：长度 `len(valid_segments)`
  - L56：传参 `find_overlap_shift_end(valid_segments, ...)`

  共 4 处，与 plan 声明完全一致。搜索 `ordered` 在该函数中无残留。✓

  ### 修复 5（F-R4-05）：补充零工时与效率边界测试

  **plan 声明**：追加 3 个测试用例。

  **测试核验**：
  1. `test_zero_hours_returns_start_equals_end`（L345-368）：`setup_hours=0, unit_hours=0, quantity=1`，无占用时间线，断言 `start == end` 且 `total_hours == 0.0`。✓
  2. `test_zero_hours_still_avoids_occupied_segments`（L371-394）：零工时，`base_time=8:00` 落在占用区间 `(7:00, 9:00)` **严格内部**（`7:00 < 8:00 < 9:00`），断言推到 `9:00` 且 `start == end`。✓ — 严格遵循 plan 要求"不落在边界上"。
  3. `test_efficiency_edge_cases_none_zero_and_exception`（L397-441）：三个子场景（None→回退、0.0→回退、抛异常→上浮）全部覆盖。✓

  ### 整体一致性

  4 项修复的 TODO 均标记 `[x]`，代码与 plan 描述完全一致。唯一未完成的 `#fix-verify`（统一运行回归集验证）是最后收口步骤。

  ### 同事意见处置核验

  - 意见①（回归脚本跑不到断言）：`conftest.py:27-55` 的 `pytest_collect_file` + `RegressionMainFile` 自定义收集器确认有效，同事二轮已撤回。✓
  - 意见②（缺坏参直测）：已在修复 2 补入。✓
  - 意见③（零工时边界语义）：已在修复 5 补入，且精确处理了半开区间语义。✓
  - 意见④（修复 1 覆盖度）：plan 论述"仅删除等价重复解析，风险极低，暂不额外新增"合理。✓
- 结论:

  4 项已完成修复的实现与 plan 声明完全一致，无偏差。同事两轮意见的处置均正确。
- 证据:
  - `core/services/scheduler/schedule_optimizer.py:348-355#_build_order`
  - `core/algorithms/greedy/dispatch/runtime_state.py:16-17#accumulate_busy_hours类型断言`
  - `core/algorithms/greedy/downtime.py:46-59#valid_segments`
  - `tests/test_internal_slot_estimator_consistency.py:345-441#新增3个测试`
  - `tests/test_downtime_timeline_ordered_insert.py:108-119#test_accumulate_busy_hours_rejects_non_datetime`
  - `tests/conftest.py:27-55#回归收集器`

### M2 · 第二轮：逻辑严谨性、边界条件与潜在 BUG 深度审查

- 状态: 已完成
- 记录时间: 2026-04-09T01:41:21.228Z
- 已审模块: 修复2测试的参数覆盖度, 修复5半开区间边界条件, 修复5效率边界场景完整性, 过度防御与静默回退扫描, plan设计简洁度
- 摘要:

  深入审查 4 项修复的代码实现，逐一检查逻辑漏洞、过度防御、静默回退和边界条件覆盖。

  ### 过度防御与静默回退扫描

  **修复 2**（`runtime_state.py`）：
  - `accumulate_busy_hours` L20 的 `float(machine_busy_hours.get(machine_id, 0.0) or 0.0) + float(duration_hours)` 中，`or 0.0` 在语义上是多余的——`dict.get(key, 0.0)` 已保证默认值为 0.0。但由于 dict 中可能被外部代码存入 `None`，`or 0.0` 在这种极端场景下作为类型安全守卫有意义。外层 `float()` 包装也是冗余的（`0.0 + float(duration_hours)` 已经是 float）。
  - **结论**：轻微过度防御，但不构成静默回退（不会吞掉异常或隐藏错误值）。可接受。

  **修复 4**（`downtime.py`）：
  - `find_earliest_available_start` L38-41 的 `try: dur = float(duration_hours) except Exception: dur = 0.0` 是一个静默回退——将无效的 `duration_hours` 静默降为 0.0。但这不是本次修复的范围（plan 修复 4 只改了变量名），且这个静默回退在第四轮审查中没有被列为问题。
  - **结论**：不属于本 plan 范围，不展开。

  **修复 5**（测试文件）：
  - 3 个新测试设计简洁，无多余的前置条件或过度 mock。`_Calendar` 桩类复用了已有的测试基础设施。✓

  ### 逻辑严谨性深度审查

  **修复 1+3 的删除安全性**：
  - plan 的论证"仅删除等价重复解析"是否成立？旧闭包 `_parse_due_date`/`_parse_ready_date` 调用的是 `date_parsers.parse_date_lenient`，而 `build_batch_sort_inputs` 内部也调用同样的解析函数。两者的日期解析语义完全相同。✓
  - 旧闭包在覆盖循环中将解析结果写入 `batch_for_sort[batch_id].due_date` 和 `.ready_date`。删除后这些字段由 `build_batch_sort_inputs` 内部解析填充。解析逻辑等价。✓

  **修复 2 的类型断言语义**：
  - `isinstance(start_time, datetime)` 对 `datetime` 的子类也返回 True——这是正确行为，不会误拒。
  - 与 `update_machine_last_state` 的断言对称——后者只检查 `end_time`（因为只接受一个时间参数），前者检查两个。✓

  **修复 5 测试 2 的半开区间验证**：
  - 在 `find_overlap_shift_end` 中：当 `start == end`（零工时）且 `base_time` 严格落在区间内部时，`end <= s` 为假且 `start >= e` 为假，被判定为重叠并后移。这正是测试验证的行为。✓
  - 但 plan 同时指出：当 `start == end == s` 时，`s >= end` 为真会提前跳出（L74 `if s >= end: break`），导致不后移。这个边界没有测试覆盖。

  **修复 5 测试 3 的效率边界完整性**：
  - `_resolve_efficiency` 的检查条件是 `eff <= 0`（L81），这意味着负值效率（如 `-1.0`）也会被回退为 1.0。测试覆盖了 `None`（转为 fallback）和 `0.0`（eff <= 0 → fallback），但未覆盖负值路径。
  - `float("inf")` 的场景在已有测试 `test_efficiency_fallback_only_updates_formal_schedule_counter`（L248-284）中覆盖。✓

  ### plan 设计简洁度评估

  - 4 项修复的 plan 描述直接、不绕弯。每项修复都包含"文件→做法→验证"三段式结构。✓
  - 同事意见处置部分用"接受/不成立"二元判断，不模糊。✓
  - 修复 1+3 合并为一项是合理的——两者改的是同一函数中的相邻代码。✓
  - 验证命令精确列出受影响文件，不用通配符。✓
- 结论:

  4 项修复的代码实现均简洁无过度兜底，设计正确。共发现 3 项低级别问题，均为测试覆盖度的细化建议，不影响修复本身的正确性。
- 证据:
  - `tests/test_downtime_timeline_ordered_insert.py:108-119#test_accumulate_busy_hours_rejects_non_datetime`
  - `core/algorithms/greedy/dispatch/runtime_state.py:16-23#accumulate_busy_hours`
  - `core/algorithms/greedy/downtime.py:62-80#find_overlap_shift_end`
  - `tests/test_internal_slot_estimator_consistency.py:371-394#test_zero_hours_still_avoids_occupied_segments`
  - `tests/test_internal_slot_estimator_consistency.py:397-441#test_efficiency_edge_cases_none_zero_and_exception`
- 下一步建议:

  3 项低级别问题可在下次迭代中补充，不阻塞当前修复的合并
- 问题:
  - [低] 测试: 修复2的测试只覆盖了 start_time 坏参路径，未覆盖对称的 end_time 坏参路径
  - [低] 测试: 修复5未锁定零工时落在占用区间起始边界的行为
  - [低] 测试: 修复5未覆盖负值效率的回退行为

### M3 · 第三轮：验证命令完整性、整体优雅度与遗漏风险终审

- 状态: 已完成
- 记录时间: 2026-04-09T01:42:29.153Z
- 已审模块: 验证命令覆盖完整性, 整体设计优雅度, plan与第四轮审查的问题对应关系, 遗漏风险扫描, 最终能否达成目的判定
- 摘要:

  ### 验证命令覆盖完整性

  plan 提供的最终验证命令：
  ```bash
  python -m pytest tests/test_algorithm_date_boundary_split.py tests/test_optimizer_build_order_once_per_strategy.py tests/test_downtime_timeline_ordered_insert.py tests/test_internal_slot_estimator_consistency.py tests/regression_downtime_overlap_skips_invalid_segments.py tests/regression_dispatch_blocking_consistency.py -q
  ```

  逐一核验：
  - **修复 1+3** → `test_algorithm_date_boundary_split.py`（排序链路验证）+ `test_optimizer_build_order_once_per_strategy.py`（缓存语义验证）✓
  - **修复 2** → `test_downtime_timeline_ordered_insert.py`（含新增的 `test_accumulate_busy_hours_rejects_non_datetime`）✓
  - **修复 4** → `test_downtime_timeline_ordered_insert.py`（含 `test_schedule_normalizes_unordered_machine_downtimes_once` 间接覆盖 `valid_segments`）+ `regression_downtime_overlap_skips_invalid_segments.py`（直接覆盖 `find_overlap_shift_end`）✓
  - **修复 5** → `test_internal_slot_estimator_consistency.py`（含 3 个新增用例）✓
  - **交叉覆盖** → `regression_dispatch_blocking_consistency.py`（端到端调度阻断语义）✓

  **额外验证**：`test_sgs_internal_scoring_matches_execution.py` 也间接受修复 1+3 影响（因为它通过完整 schedule 路径经过 `_build_order`），但不在验证命令中。这可以接受——因为修复 1+3 只删除了等价代码，不改变执行路径。

  **结论**：验证命令已覆盖所有直接和关键间接影响路径。✓

  ### 整体设计优雅度

  1. **结构清晰**：plan 正文 125 行（含验证命令），每项修复用"文件→做法→验证"三段式描述，无冗余背景叙述。对比第四轮审查 865 行的 review 文档，这份修复 plan 的信噪比非常高。✓

  2. **同事意见处置**：4 条意见用 28 行处置（L27-43），其中①明确说"不成立"并给出代码证据（conftest 收集器），②③"接受"并给出具体补测方案，④"暂不额外新增"并说明原因和后续跟踪条件。没有模糊的"酌情处理"。✓

  3. **没有过度兜底**：
     - 修复 2 的 `raise TypeError` 是显式拒绝，不是静默吞错。✓
     - 修复 5 的效率异常测试断言 `pytest.raises(RuntimeError)` — 验证异常直接上浮。✓
     - 修复 1+3 是纯删除，没有新增任何防御逻辑。✓

  4. **没有静默回退**：
     - plan 修改的代码中没有新增任何 `try/except` 吞异常。✓
     - 效率回退（`_resolve_efficiency` 对 None/0.0/inf 返回 1.0）是已有行为，本次修复只是用测试锁定它。✓

  ### plan 与第四轮审查的问题对应关系

  第四轮审查发现 5 项中级 + 6 项低级问题。本 plan 处理的是 5 项低级别中的一个子集：

  | 审查问题 | plan 修复 | 对应关系 |
  |---------|----------|---------|
  | F-01/F-02 (中) | 修复 1+3 | 删除 `_build_order` 中等价的双重解析循环 — 间接解决了时序依赖链问题 |
  | F-06 (中) | 修复 2 | `accumulate_busy_hours` 增加 datetime 类型断言 — 直接解决入参守卫不充分 |
  | F-08 (低) | 修复 4 | `ordered` → `valid_segments` — 改善命名清晰度 |
  | 新增 | 修复 5 | 零工时/效率边界测试 — 锁定同事提出的边界语义 |

  对应关系合理，没有超出范围的修改。✓

  ### 遗漏风险扫描

  1. **`downtime.py:38-41` 的静默回退**：`try: dur = float(duration_hours) except Exception: dur = 0.0` 将无效 `duration_hours` 静默降为 0.0。这不在本 plan 范围内，但值得在下一轮迭代中作为技术债务处理。

  2. **`runtime_state.py:20-22` 的冗余 `float()`/`or 0.0`**：不影响正确性但增加了认知负担。可在下一轮代码简化中清理。

  3. **修复 1+3 删除后 `_build_order` 中 `normalized_batches_for_sort` 闭包引用**：`_build_order` 通过闭包引用外层的 `normalized_batches_for_sort`（L346）。这个引用在删除闭包前后都存在，行为不变。✓

  4. **`regression_dispatch_blocking_consistency.py` 的日历桩缺少 `operator_id` 参数**：L24 和 L30 的方法签名缺少 `operator_id` 参数。这不是本次修复引入的问题，但如果估算器链路变化可能在后续迭代中暴露。不影响本 plan。

  ### 能否达成目的

  **可以**。4 项修复全部已正确实现：
  - 修复 1+3 消除了 `_build_order` 中的等价重复解析代码
  - 修复 2 补齐了 `accumulate_busy_hours` 的 datetime 入参守卫
  - 修复 4 改善了 `downtime.py` 中的变量命名清晰度
  - 修复 5 用 3 个新测试锁定了零工时和效率边界的语义

  唯一剩余步骤是执行 `#fix-verify`（最终统一回归验证），plan 已提供了完整的命令。
- 结论:

  plan 验证命令覆盖完整，整体方案能达成目的。没有高或中级别问题，所有 3 项低级别发现均为测试覆盖度的增量建议。plan 可以直接执行最后的统一回归验证步骤。
- 证据:
  - `.limcode/plans/修复第四轮审查-5-项低级别问题.plan.md`
- 下一步建议:

  执行最终验证命令（#fix-verify），将 TODO 标记为完成后即可合并

## 最终结论

## 三轮深度审查总结

### 总体评价

这份修复 plan（修订版 v2）是一份**高质量的局部修复方案**。4 项已完成修复的代码实现与 plan 声明完全一致，每项修复目标明确、边界清晰、实现简洁。方案没有过度兜底或静默回退——修复 2 的 `raise TypeError` 是显式拒绝而非静默吞错，修复 5 的测试验证异常直接上浮而非被捕获，修复 1+3 是纯删除操作。

### 关键发现

共发现 3 项低级别问题（0 高 / 0 中 / 3 低），**全部为测试覆盖度的增量建议**，不影响修复本身的正确性：

1. **F-P1**：修复 2 的测试只覆盖了 `start_time` 坏参路径，缺少对称的 `end_time` 坏参用例
2. **F-P2**：修复 5 未锁定零工时落在占用区间起始边界时"不后移"的半开区间行为
3. **F-P3**：修复 5 未覆盖负值效率（如 `-1.0`）的回退行为

### 能否达成目的

**可以**。4 项修复完整覆盖了 plan 声明的所有目标：
- 修复 1+3 消除了 `_build_order` 中的等价重复解析代码——与现有排序链路测试和缓存语义测试交叉验证通过
- 修复 2 补齐了 `accumulate_busy_hours` 的 datetime 入参守卫——与 `update_machine_last_state` 的守卫对称
- 修复 4 将 `ordered` 重命名为 `valid_segments`——4 处引用无遗漏
- 修复 5 用 3 个新测试锁定了零工时和效率边界的语义——精确遵循了同事的半开区间分析

验证命令覆盖了所有直接和关键间接影响路径。同事意见处置正确——已撤回的误判没有被多余修改，接受的建议已精确落实。

### 建议

1. 执行 `#fix-verify` 统一回归验证，将最后一项 TODO 标记完成
2. 3 项低级别测试建议可在下次迭代中补充，不阻塞合并

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnqt6iao-he91o7",
  "createdAt": "2026-04-09T00:00:00.000Z",
  "updatedAt": "2026-04-09T01:42:58.348Z",
  "finalizedAt": "2026-04-09T01:42:58.348Z",
  "status": "completed",
  "overallDecision": "accepted",
  "header": {
    "title": "修复第四轮审查5项低级别问题plan三轮深度审查",
    "date": "2026-04-09",
    "overview": "对修复plan（修订版v2）进行三轮深度审查，验证实现正确性、逻辑严谨性及边界覆盖完整度"
  },
  "scope": {
    "markdown": "# 修复第四轮审查 5 项低级别问题 plan — 三轮深度审查\n\n**审查日期**: 2026-04-08\n**审查目标**: 对 `.limcode/plans/修复第四轮审查-5-项低级别问题.plan.md`（修订版 v2）进行三轮深度审查，验证：\n1. 每项修复的实现是否忠实反映 plan 意图\n2. 代码实现是否优雅、简洁，无过度兜底或静默回退\n3. 测试覆盖是否锁定了所有关键语义\n4. 逻辑严谨性与潜在 BUG 风险\n5. 验证命令的完整性与最终回归覆盖度\n\n**审查范围**: plan 文档 + 4 项已实现修复的源文件与测试文件的交叉验证"
  },
  "summary": {
    "latestConclusion": "## 三轮深度审查总结\n\n### 总体评价\n\n这份修复 plan（修订版 v2）是一份**高质量的局部修复方案**。4 项已完成修复的代码实现与 plan 声明完全一致，每项修复目标明确、边界清晰、实现简洁。方案没有过度兜底或静默回退——修复 2 的 `raise TypeError` 是显式拒绝而非静默吞错，修复 5 的测试验证异常直接上浮而非被捕获，修复 1+3 是纯删除操作。\n\n### 关键发现\n\n共发现 3 项低级别问题（0 高 / 0 中 / 3 低），**全部为测试覆盖度的增量建议**，不影响修复本身的正确性：\n\n1. **F-P1**：修复 2 的测试只覆盖了 `start_time` 坏参路径，缺少对称的 `end_time` 坏参用例\n2. **F-P2**：修复 5 未锁定零工时落在占用区间起始边界时\"不后移\"的半开区间行为\n3. **F-P3**：修复 5 未覆盖负值效率（如 `-1.0`）的回退行为\n\n### 能否达成目的\n\n**可以**。4 项修复完整覆盖了 plan 声明的所有目标：\n- 修复 1+3 消除了 `_build_order` 中的等价重复解析代码——与现有排序链路测试和缓存语义测试交叉验证通过\n- 修复 2 补齐了 `accumulate_busy_hours` 的 datetime 入参守卫——与 `update_machine_last_state` 的守卫对称\n- 修复 4 将 `ordered` 重命名为 `valid_segments`——4 处引用无遗漏\n- 修复 5 用 3 个新测试锁定了零工时和效率边界的语义——精确遵循了同事的半开区间分析\n\n验证命令覆盖了所有直接和关键间接影响路径。同事意见处置正确——已撤回的误判没有被多余修改，接受的建议已精确落实。\n\n### 建议\n\n1. 执行 `#fix-verify` 统一回归验证，将最后一项 TODO 标记完成\n2. 3 项低级别测试建议可在下次迭代中补充，不阻塞合并",
    "recommendedNextAction": "执行最终验证命令（#fix-verify），将 TODO 标记为完成后即可合并；3 项低级别测试建议可在下次迭代中补充",
    "reviewedModules": [
      "修复1+3实现核验",
      "修复2实现核验",
      "修复4实现核验",
      "修复5实现核验",
      "同事意见处置核验",
      "修复2测试的参数覆盖度",
      "修复5半开区间边界条件",
      "修复5效率边界场景完整性",
      "过度防御与静默回退扫描",
      "plan设计简洁度",
      "验证命令覆盖完整性",
      "整体设计优雅度",
      "plan与第四轮审查的问题对应关系",
      "遗漏风险扫描",
      "最终能否达成目的判定"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 3,
    "severity": {
      "high": 0,
      "medium": 0,
      "low": 3
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "第一轮：4 项已完成修复的实现与 plan 声明一致性核验",
      "status": "completed",
      "recordedAt": "2026-04-09T01:39:42.962Z",
      "summaryMarkdown": "逐条将 4 项已标记完成的修复（`#fix-01` ~ `#fix-05`）与实际代码和测试交叉核验。\n\n### 修复 1+3（F-R4-01+03）：删除 `_build_order` 双重解析循环和闭包\n\n**plan 声明**：删除 `schedule_optimizer.py` 中 `_parse_due_date`/`_parse_ready_date` 两个闭包（L349-361）以及 `_build_order` 中的覆盖循环（L369-374），简化为直接调用 `build_batch_sort_inputs`。\n\n**代码核验**：搜索 `_parse_due_date` 和 `_parse_ready_date` 在 `schedule_optimizer.py` 中均无匹配。当前 `_build_order`（L348-355）已简化为：\n```python\ndef _build_order(strategy0: SortStrategy, params: Dict[str, Any]) -> List[str]:\n    batch_for_sort = build_batch_sort_inputs(\n        normalized_batches_for_sort,\n        strict_mode=bool(strict_mode),\n        strategy=strategy0,\n    )\n    sorter0 = StrategyFactory.create(strategy0, **(params or {}))\n    return [item.batch_id for item in sorter0.sort(batch_for_sort, base_date=start_dt.date())]\n```\n这与 plan 给出的期望代码**完全一致**。✓\n\n**验证测试**：`test_algorithm_date_boundary_split.py` 和 `test_optimizer_build_order_once_per_strategy.py` 分别覆盖了排序链路和缓存语义。\n\n### 修复 2（F-R4-02）：`accumulate_busy_hours` 增加 datetime 类型断言\n\n**plan 声明**：在 `runtime_state.py` 的 `accumulate_busy_hours` 入口增加与 `update_machine_last_state` 对称的断言。\n\n**代码核验**：`runtime_state.py:16-17`：\n```python\nif not isinstance(start_time, datetime) or not isinstance(end_time, datetime):\n    raise TypeError(\"start_time/end_time 必须是 datetime\")\n```\n与 `update_machine_last_state:37-38` 的 `raise TypeError(\"end_time 必须是 datetime\")` 对称。✓\n\n**补测核验**：`test_downtime_timeline_ordered_insert.py:108-119` 的 `test_accumulate_busy_hours_rejects_non_datetime` 传入字符串 `start_time`，断言抛 `TypeError`。✓\n\n### 修复 4（F-R4-04）：`ordered` 重命名为 `valid_segments`\n\n**plan 声明**：将 `downtime.py` L46-56 中 `ordered` 全部替换为 `valid_segments`，共 4 处引用。\n\n**代码核验**：`downtime.py` 中出现 `valid_segments` 的位置：\n- L46：定义 `valid_segments = [...]`\n- L47：空值检查 `if not valid_segments`\n- L54：长度 `len(valid_segments)`\n- L56：传参 `find_overlap_shift_end(valid_segments, ...)`\n\n共 4 处，与 plan 声明完全一致。搜索 `ordered` 在该函数中无残留。✓\n\n### 修复 5（F-R4-05）：补充零工时与效率边界测试\n\n**plan 声明**：追加 3 个测试用例。\n\n**测试核验**：\n1. `test_zero_hours_returns_start_equals_end`（L345-368）：`setup_hours=0, unit_hours=0, quantity=1`，无占用时间线，断言 `start == end` 且 `total_hours == 0.0`。✓\n2. `test_zero_hours_still_avoids_occupied_segments`（L371-394）：零工时，`base_time=8:00` 落在占用区间 `(7:00, 9:00)` **严格内部**（`7:00 < 8:00 < 9:00`），断言推到 `9:00` 且 `start == end`。✓ — 严格遵循 plan 要求\"不落在边界上\"。\n3. `test_efficiency_edge_cases_none_zero_and_exception`（L397-441）：三个子场景（None→回退、0.0→回退、抛异常→上浮）全部覆盖。✓\n\n### 整体一致性\n\n4 项修复的 TODO 均标记 `[x]`，代码与 plan 描述完全一致。唯一未完成的 `#fix-verify`（统一运行回归集验证）是最后收口步骤。\n\n### 同事意见处置核验\n\n- 意见①（回归脚本跑不到断言）：`conftest.py:27-55` 的 `pytest_collect_file` + `RegressionMainFile` 自定义收集器确认有效，同事二轮已撤回。✓\n- 意见②（缺坏参直测）：已在修复 2 补入。✓\n- 意见③（零工时边界语义）：已在修复 5 补入，且精确处理了半开区间语义。✓\n- 意见④（修复 1 覆盖度）：plan 论述\"仅删除等价重复解析，风险极低，暂不额外新增\"合理。✓",
      "conclusionMarkdown": "4 项已完成修复的实现与 plan 声明完全一致，无偏差。同事两轮意见的处置均正确。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 348,
          "lineEnd": 355,
          "symbol": "_build_order"
        },
        {
          "path": "core/algorithms/greedy/dispatch/runtime_state.py",
          "lineStart": 16,
          "lineEnd": 17,
          "symbol": "accumulate_busy_hours类型断言"
        },
        {
          "path": "core/algorithms/greedy/downtime.py",
          "lineStart": 46,
          "lineEnd": 59,
          "symbol": "valid_segments"
        },
        {
          "path": "tests/test_internal_slot_estimator_consistency.py",
          "lineStart": 345,
          "lineEnd": 441,
          "symbol": "新增3个测试"
        },
        {
          "path": "tests/test_downtime_timeline_ordered_insert.py",
          "lineStart": 108,
          "lineEnd": 119,
          "symbol": "test_accumulate_busy_hours_rejects_non_datetime"
        },
        {
          "path": "tests/conftest.py",
          "lineStart": 27,
          "lineEnd": 55,
          "symbol": "回归收集器"
        }
      ],
      "reviewedModules": [
        "修复1+3实现核验",
        "修复2实现核验",
        "修复4实现核验",
        "修复5实现核验",
        "同事意见处置核验"
      ],
      "recommendedNextAction": null,
      "findingIds": []
    },
    {
      "id": "M2",
      "title": "第二轮：逻辑严谨性、边界条件与潜在 BUG 深度审查",
      "status": "completed",
      "recordedAt": "2026-04-09T01:41:21.228Z",
      "summaryMarkdown": "深入审查 4 项修复的代码实现，逐一检查逻辑漏洞、过度防御、静默回退和边界条件覆盖。\n\n### 过度防御与静默回退扫描\n\n**修复 2**（`runtime_state.py`）：\n- `accumulate_busy_hours` L20 的 `float(machine_busy_hours.get(machine_id, 0.0) or 0.0) + float(duration_hours)` 中，`or 0.0` 在语义上是多余的——`dict.get(key, 0.0)` 已保证默认值为 0.0。但由于 dict 中可能被外部代码存入 `None`，`or 0.0` 在这种极端场景下作为类型安全守卫有意义。外层 `float()` 包装也是冗余的（`0.0 + float(duration_hours)` 已经是 float）。\n- **结论**：轻微过度防御，但不构成静默回退（不会吞掉异常或隐藏错误值）。可接受。\n\n**修复 4**（`downtime.py`）：\n- `find_earliest_available_start` L38-41 的 `try: dur = float(duration_hours) except Exception: dur = 0.0` 是一个静默回退——将无效的 `duration_hours` 静默降为 0.0。但这不是本次修复的范围（plan 修复 4 只改了变量名），且这个静默回退在第四轮审查中没有被列为问题。\n- **结论**：不属于本 plan 范围，不展开。\n\n**修复 5**（测试文件）：\n- 3 个新测试设计简洁，无多余的前置条件或过度 mock。`_Calendar` 桩类复用了已有的测试基础设施。✓\n\n### 逻辑严谨性深度审查\n\n**修复 1+3 的删除安全性**：\n- plan 的论证\"仅删除等价重复解析\"是否成立？旧闭包 `_parse_due_date`/`_parse_ready_date` 调用的是 `date_parsers.parse_date_lenient`，而 `build_batch_sort_inputs` 内部也调用同样的解析函数。两者的日期解析语义完全相同。✓\n- 旧闭包在覆盖循环中将解析结果写入 `batch_for_sort[batch_id].due_date` 和 `.ready_date`。删除后这些字段由 `build_batch_sort_inputs` 内部解析填充。解析逻辑等价。✓\n\n**修复 2 的类型断言语义**：\n- `isinstance(start_time, datetime)` 对 `datetime` 的子类也返回 True——这是正确行为，不会误拒。\n- 与 `update_machine_last_state` 的断言对称——后者只检查 `end_time`（因为只接受一个时间参数），前者检查两个。✓\n\n**修复 5 测试 2 的半开区间验证**：\n- 在 `find_overlap_shift_end` 中：当 `start == end`（零工时）且 `base_time` 严格落在区间内部时，`end <= s` 为假且 `start >= e` 为假，被判定为重叠并后移。这正是测试验证的行为。✓\n- 但 plan 同时指出：当 `start == end == s` 时，`s >= end` 为真会提前跳出（L74 `if s >= end: break`），导致不后移。这个边界没有测试覆盖。\n\n**修复 5 测试 3 的效率边界完整性**：\n- `_resolve_efficiency` 的检查条件是 `eff <= 0`（L81），这意味着负值效率（如 `-1.0`）也会被回退为 1.0。测试覆盖了 `None`（转为 fallback）和 `0.0`（eff <= 0 → fallback），但未覆盖负值路径。\n- `float(\"inf\")` 的场景在已有测试 `test_efficiency_fallback_only_updates_formal_schedule_counter`（L248-284）中覆盖。✓\n\n### plan 设计简洁度评估\n\n- 4 项修复的 plan 描述直接、不绕弯。每项修复都包含\"文件→做法→验证\"三段式结构。✓\n- 同事意见处置部分用\"接受/不成立\"二元判断，不模糊。✓\n- 修复 1+3 合并为一项是合理的——两者改的是同一函数中的相邻代码。✓\n- 验证命令精确列出受影响文件，不用通配符。✓",
      "conclusionMarkdown": "4 项修复的代码实现均简洁无过度兜底，设计正确。共发现 3 项低级别问题，均为测试覆盖度的细化建议，不影响修复本身的正确性。",
      "evidence": [
        {
          "path": "tests/test_downtime_timeline_ordered_insert.py",
          "lineStart": 108,
          "lineEnd": 119,
          "symbol": "test_accumulate_busy_hours_rejects_non_datetime"
        },
        {
          "path": "core/algorithms/greedy/dispatch/runtime_state.py",
          "lineStart": 16,
          "lineEnd": 23,
          "symbol": "accumulate_busy_hours"
        },
        {
          "path": "core/algorithms/greedy/downtime.py",
          "lineStart": 62,
          "lineEnd": 80,
          "symbol": "find_overlap_shift_end"
        },
        {
          "path": "tests/test_internal_slot_estimator_consistency.py",
          "lineStart": 371,
          "lineEnd": 394,
          "symbol": "test_zero_hours_still_avoids_occupied_segments"
        },
        {
          "path": "tests/test_internal_slot_estimator_consistency.py",
          "lineStart": 397,
          "lineEnd": 441,
          "symbol": "test_efficiency_edge_cases_none_zero_and_exception"
        }
      ],
      "reviewedModules": [
        "修复2测试的参数覆盖度",
        "修复5半开区间边界条件",
        "修复5效率边界场景完整性",
        "过度防御与静默回退扫描",
        "plan设计简洁度"
      ],
      "recommendedNextAction": "3 项低级别问题可在下次迭代中补充，不阻塞当前修复的合并",
      "findingIds": [
        "F-P1",
        "F-P2",
        "F-P3"
      ]
    },
    {
      "id": "M3",
      "title": "第三轮：验证命令完整性、整体优雅度与遗漏风险终审",
      "status": "completed",
      "recordedAt": "2026-04-09T01:42:29.153Z",
      "summaryMarkdown": "### 验证命令覆盖完整性\n\nplan 提供的最终验证命令：\n```bash\npython -m pytest tests/test_algorithm_date_boundary_split.py tests/test_optimizer_build_order_once_per_strategy.py tests/test_downtime_timeline_ordered_insert.py tests/test_internal_slot_estimator_consistency.py tests/regression_downtime_overlap_skips_invalid_segments.py tests/regression_dispatch_blocking_consistency.py -q\n```\n\n逐一核验：\n- **修复 1+3** → `test_algorithm_date_boundary_split.py`（排序链路验证）+ `test_optimizer_build_order_once_per_strategy.py`（缓存语义验证）✓\n- **修复 2** → `test_downtime_timeline_ordered_insert.py`（含新增的 `test_accumulate_busy_hours_rejects_non_datetime`）✓\n- **修复 4** → `test_downtime_timeline_ordered_insert.py`（含 `test_schedule_normalizes_unordered_machine_downtimes_once` 间接覆盖 `valid_segments`）+ `regression_downtime_overlap_skips_invalid_segments.py`（直接覆盖 `find_overlap_shift_end`）✓\n- **修复 5** → `test_internal_slot_estimator_consistency.py`（含 3 个新增用例）✓\n- **交叉覆盖** → `regression_dispatch_blocking_consistency.py`（端到端调度阻断语义）✓\n\n**额外验证**：`test_sgs_internal_scoring_matches_execution.py` 也间接受修复 1+3 影响（因为它通过完整 schedule 路径经过 `_build_order`），但不在验证命令中。这可以接受——因为修复 1+3 只删除了等价代码，不改变执行路径。\n\n**结论**：验证命令已覆盖所有直接和关键间接影响路径。✓\n\n### 整体设计优雅度\n\n1. **结构清晰**：plan 正文 125 行（含验证命令），每项修复用\"文件→做法→验证\"三段式描述，无冗余背景叙述。对比第四轮审查 865 行的 review 文档，这份修复 plan 的信噪比非常高。✓\n\n2. **同事意见处置**：4 条意见用 28 行处置（L27-43），其中①明确说\"不成立\"并给出代码证据（conftest 收集器），②③\"接受\"并给出具体补测方案，④\"暂不额外新增\"并说明原因和后续跟踪条件。没有模糊的\"酌情处理\"。✓\n\n3. **没有过度兜底**：\n   - 修复 2 的 `raise TypeError` 是显式拒绝，不是静默吞错。✓\n   - 修复 5 的效率异常测试断言 `pytest.raises(RuntimeError)` — 验证异常直接上浮。✓\n   - 修复 1+3 是纯删除，没有新增任何防御逻辑。✓\n\n4. **没有静默回退**：\n   - plan 修改的代码中没有新增任何 `try/except` 吞异常。✓\n   - 效率回退（`_resolve_efficiency` 对 None/0.0/inf 返回 1.0）是已有行为，本次修复只是用测试锁定它。✓\n\n### plan 与第四轮审查的问题对应关系\n\n第四轮审查发现 5 项中级 + 6 项低级问题。本 plan 处理的是 5 项低级别中的一个子集：\n\n| 审查问题 | plan 修复 | 对应关系 |\n|---------|----------|---------|\n| F-01/F-02 (中) | 修复 1+3 | 删除 `_build_order` 中等价的双重解析循环 — 间接解决了时序依赖链问题 |\n| F-06 (中) | 修复 2 | `accumulate_busy_hours` 增加 datetime 类型断言 — 直接解决入参守卫不充分 |\n| F-08 (低) | 修复 4 | `ordered` → `valid_segments` — 改善命名清晰度 |\n| 新增 | 修复 5 | 零工时/效率边界测试 — 锁定同事提出的边界语义 |\n\n对应关系合理，没有超出范围的修改。✓\n\n### 遗漏风险扫描\n\n1. **`downtime.py:38-41` 的静默回退**：`try: dur = float(duration_hours) except Exception: dur = 0.0` 将无效 `duration_hours` 静默降为 0.0。这不在本 plan 范围内，但值得在下一轮迭代中作为技术债务处理。\n\n2. **`runtime_state.py:20-22` 的冗余 `float()`/`or 0.0`**：不影响正确性但增加了认知负担。可在下一轮代码简化中清理。\n\n3. **修复 1+3 删除后 `_build_order` 中 `normalized_batches_for_sort` 闭包引用**：`_build_order` 通过闭包引用外层的 `normalized_batches_for_sort`（L346）。这个引用在删除闭包前后都存在，行为不变。✓\n\n4. **`regression_dispatch_blocking_consistency.py` 的日历桩缺少 `operator_id` 参数**：L24 和 L30 的方法签名缺少 `operator_id` 参数。这不是本次修复引入的问题，但如果估算器链路变化可能在后续迭代中暴露。不影响本 plan。\n\n### 能否达成目的\n\n**可以**。4 项修复全部已正确实现：\n- 修复 1+3 消除了 `_build_order` 中的等价重复解析代码\n- 修复 2 补齐了 `accumulate_busy_hours` 的 datetime 入参守卫\n- 修复 4 改善了 `downtime.py` 中的变量命名清晰度\n- 修复 5 用 3 个新测试锁定了零工时和效率边界的语义\n\n唯一剩余步骤是执行 `#fix-verify`（最终统一回归验证），plan 已提供了完整的命令。",
      "conclusionMarkdown": "plan 验证命令覆盖完整，整体方案能达成目的。没有高或中级别问题，所有 3 项低级别发现均为测试覆盖度的增量建议。plan 可以直接执行最后的统一回归验证步骤。",
      "evidence": [
        {
          "path": ".limcode/plans/修复第四轮审查-5-项低级别问题.plan.md"
        }
      ],
      "reviewedModules": [
        "验证命令覆盖完整性",
        "整体设计优雅度",
        "plan与第四轮审查的问题对应关系",
        "遗漏风险扫描",
        "最终能否达成目的判定"
      ],
      "recommendedNextAction": "执行最终验证命令（#fix-verify），将 TODO 标记为完成后即可合并",
      "findingIds": []
    }
  ],
  "findings": [
    {
      "id": "F-P1",
      "severity": "low",
      "category": "test",
      "title": "修复2的测试只覆盖了 start_time 坏参路径，未覆盖对称的 end_time 坏参路径",
      "descriptionMarkdown": "测试 `test_accumulate_busy_hours_rejects_non_datetime`（L108-119）仅传入了字符串 `start_time` + 有效 datetime `end_time`，测了 `start_time` 不合法的路径。但没有独立覆盖 `end_time` 不合法的对称路径。这不是 BUG——断言逻辑是对称的（同一条 `if` 语句用 `or` 检查两个参数），但测试作为合约证据不够对称。plan 本身只说“传入字符串 start_time”，测试循规躈矩，但可以再加一条仅传字符串 end_time 的对称用例。",
      "recommendationMarkdown": "在 `test_accumulate_busy_hours_rejects_non_datetime` 中追加一条对称用例：start_time=有效 datetime、end_time=字符串，断言同样抛 TypeError",
      "evidence": [
        {
          "path": "tests/test_downtime_timeline_ordered_insert.py",
          "lineStart": 108,
          "lineEnd": 119
        },
        {
          "path": "tests/test_downtime_timeline_ordered_insert.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-P2",
      "severity": "low",
      "category": "test",
      "title": "修复5未锁定零工时落在占用区间起始边界的行为",
      "descriptionMarkdown": "plan 中明确指出 `find_overlap_shift_end` 使用半开区间语义，当 `start == end == s` 时会因 `s >= end` 提前跳出而不后移。这是零工时场景的一个重要边界：当 `base_time` 恰好落在占用区间起始边界上时，行为与落在内部时不同。当前测试 `test_zero_hours_still_avoids_occupied_segments` 只覆盖了“落在内部”场景，未覆盖“落在起始边界”场景。虽然 plan 已明确要求“不落在边界上”，但“落在边界上不后移”本身也是需要用测试锁定的语义。",
      "recommendationMarkdown": "追加一条用例：零工时工序，`base_time` 恰好等于占用区间 `segment_start`，断言 `start_time == base_time`（不后移）。这将完整锁定半开区间的边界行为",
      "evidence": [
        {
          "path": "core/algorithms/greedy/downtime.py",
          "lineStart": 62,
          "lineEnd": 80
        },
        {
          "path": "tests/test_internal_slot_estimator_consistency.py",
          "lineStart": 371,
          "lineEnd": 394
        },
        {
          "path": "core/algorithms/greedy/downtime.py"
        },
        {
          "path": "tests/test_internal_slot_estimator_consistency.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-P3",
      "severity": "low",
      "category": "test",
      "title": "修复5未覆盖负值效率的回退行为",
      "descriptionMarkdown": "修复 5 的 `test_efficiency_edge_cases_none_zero_and_exception` 覆盖了 None、零值、异常三种场景，但未覆盖负值效率（如 `-1.0`）的行为。看 `_resolve_efficiency`（internal_slot.py:81）的 `eff <= 0` 检查，负值应该与 0.0 同样触发回退，但没有测试锁定这一行为。plan 本身只要求了三种场景，这不是 plan 的缺陷，但作为完整性建议值得补充。",
      "recommendationMarkdown": "在 `test_efficiency_edge_cases_none_zero_and_exception` 中追加第四个子场景：`get_efficiency` 返回 `-1.0`，断言 `efficiency_fallback_used=True` 且工时按 eff=1.0 计算",
      "evidence": [
        {
          "path": "core/algorithms/greedy/internal_slot.py",
          "lineStart": 71,
          "lineEnd": 83,
          "symbol": "_resolve_efficiency"
        },
        {
          "path": "tests/test_internal_slot_estimator_consistency.py",
          "lineStart": 397,
          "lineEnd": 441
        },
        {
          "path": "core/algorithms/greedy/internal_slot.py"
        },
        {
          "path": "tests/test_internal_slot_estimator_consistency.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:bbe51b6e35ab856217a426b9aa2b99c409291b73f35710ca46c8e6fc76cf4905",
    "generatedAt": "2026-04-09T01:42:58.348Z",
    "locale": "zh-CN"
  }
}
```
